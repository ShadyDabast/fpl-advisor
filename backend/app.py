"""
FastAPI backend for FPL Advisor, with user accounts.

Owner: Member 4 (Interface), building on top of Members 1-3's modules.

Run with: uvicorn app:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import InvalidSquadError
from fpl_api import FPLClient, FPLAPIError
from ai_advisor import AIAdvisor, AIAdvisorError, AIRateLimitError
import db
import auth

app = FastAPI(title="FPL Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your actual frontend URL before deploying for real
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()
client = FPLClient()

try:
    advisor: AIAdvisor | None = AIAdvisor()
except AIAdvisorError:
    advisor = None  # AI endpoints return a clear error instead of crashing the app


# ---------- request models ----------

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AddPlayerRequest(BaseModel):
    name: str


class SetSquadModeRequest(BaseModel):
    mode: str


class TransferAdviceRequest(BaseModel):
    position: str
    max_price: float
    free_transfers: int = 1


# ---------- auth helper ----------
# Called explicitly at the top of each protected endpoint (rather than via
# FastAPI's Depends()) to keep the auth flow easy to follow for a class
# project. Swap to Depends(get_current_user_id) later if you prefer that.

def get_current_user_id(authorization: str) -> int:
    """Expects header: Authorization: Bearer <token>. Raises 401 if invalid."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = auth.verify_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


# ---------- auth endpoints ----------

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if db.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="Username already taken")

    password_hash, salt = auth.hash_password(req.password)
    user_id = db.create_user(req.username, password_hash, salt)
    token = auth.create_token(user_id)
    return {"token": token, "username": req.username}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = db.get_user_by_username(req.username)
    if not user or not auth.verify_password(req.password, user["password_hash"], user["salt"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth.create_token(user["id"])
    return {"token": token, "username": user["username"]}


# ---------- squad endpoints (all require a valid token) ----------

@app.get("/api/squad")
def squad_view(authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    squad = db.load_squad_for_user(user_id)

    try:
        squad.refresh_stats_from(client.get_all_players())
    except FPLAPIError:
        pass  # show stored stats rather than failing the whole page

    return {
        "mode": squad.mode,
        "players": [p.__dict__ for p in squad.players],
        "total_value": squad.total_value(),
        "remaining_budget": squad.remaining_budget(),
        "is_complete": squad.is_complete(),
    }


@app.get("/api/squad/lineup")
def squad_lineup(authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    squad = db.load_squad_for_user(user_id)

    try:
        squad.refresh_stats_from(client.get_all_players())
    except FPLAPIError:
        pass  # fall back to stored stats rather than failing the whole lineup

    try:
        lineup = squad.select_starting_xi()
    except InvalidSquadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "formation": lineup["formation"],
        "starters": [p.__dict__ for p in lineup["starters"]],
        "bench": [p.__dict__ for p in lineup["bench"]],
    }


@app.post("/api/squad/players")
def add_player(req: AddPlayerRequest, authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    squad = db.load_squad_for_user(user_id)

    try:
        player = client.get_player_by_name(req.name)
    except FPLAPIError as e:
        raise HTTPException(status_code=502, detail=f"FPL API error: {e}")

    if not player:
        raise HTTPException(status_code=404, detail=f"No player found matching '{req.name}'")

    try:
        squad.add_player(player)
    except InvalidSquadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.save_squad_for_user(user_id, squad)
    return {"added": player.__dict__}


@app.delete("/api/squad/players/{fpl_id}")
def remove_player(fpl_id: int, authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    squad = db.load_squad_for_user(user_id)

    removed = squad.remove_player(fpl_id)
    if not removed:
        raise HTTPException(status_code=404, detail="No player with that id in squad")

    db.save_squad_for_user(user_id, squad)
    return {"removed": removed.__dict__}


@app.post("/api/squad/mode")
def set_squad_mode(req: SetSquadModeRequest, authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    if req.mode not in ("BUILDING", "CURRENT"):
        raise HTTPException(status_code=400, detail="Mode must be 'BUILDING' or 'CURRENT'")
    squad = db.load_squad_for_user(user_id)
    squad.mode = req.mode
    db.save_squad_for_user(user_id, squad)
    return {"mode": squad.mode}


# ---------- player search ----------

@app.get("/api/players/search")
def search_players(q: str, position: str | None = None, max_price: float | None = None,
                    authorization: str = Header(default="")):
    get_current_user_id(authorization)  # require login, though the results aren't user-specific

    try:
        all_players = client.get_all_players()
    except FPLAPIError as e:
        raise HTTPException(status_code=502, detail=f"FPL API error: {e}")

    results = [p for p in all_players if q.lower() in p.name.lower()]
    if position:
        results = [p for p in results if p.position == position.upper()]
    if max_price is not None:
        results = [p for p in results if p.price <= max_price]

    return {"results": [p.__dict__ for p in results[:20]]}


# ---------- AI advice endpoints ----------

@app.post("/api/advice/transfer")
def transfer_advice(req: TransferAdviceRequest, authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    if advisor is None:
        raise HTTPException(status_code=503, detail="AI advisor unavailable: no Gemini API key configured")

    squad = db.load_squad_for_user(user_id)
    if not squad.players:
        raise HTTPException(status_code=400, detail="Squad is empty")

    try:
        all_players = client.get_all_players()
        gw = client.get_next_gameweek()
        # Gather fixtures for the next three gameweeks (gw, gw+1, gw+2)
        all_fixtures = []
        for offset in range(3):
            gw_n = gw + offset
            all_fixtures.extend(client.get_fixtures(gameweek=gw_n))
        fixtures = all_fixtures
    except FPLAPIError as e:
        raise HTTPException(status_code=502, detail=f"FPL API error: {e}")

    squad.refresh_stats_from(all_players)  # so advice is based on current form, not a stale snapshot

    squad_ids = {p.fpl_id for p in squad.players}
    candidates = sorted(
        [p for p in all_players
         if p.position == req.position.upper()
         and p.price <= req.max_price
         and p.fpl_id not in squad_ids],
        key=lambda p: p.form, reverse=True
    )[:5]

    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates found for that position/price")

    try:
        advice = advisor.get_transfer_advice(squad, candidates, fixtures, req.free_transfers)
    except AIRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AIAdvisorError as e:
        raise HTTPException(status_code=502, detail=f"AI advisor error: {e}")

    return {"advice": advice, "gameweek": gw, "candidates_considered": [p.__dict__ for p in candidates]}


@app.get("/api/advice/captain")
def captain_advice(authorization: str = Header(default="")):
    user_id = get_current_user_id(authorization)
    if advisor is None:
        raise HTTPException(status_code=503, detail="AI advisor unavailable: no Gemini API key configured")

    squad = db.load_squad_for_user(user_id)
    if not squad.players:
        raise HTTPException(status_code=400, detail="Squad is empty")

    try:
        all_players = client.get_all_players()
        gw = client.get_next_gameweek()
        fixtures = client.get_fixtures(gameweek=gw)
    except FPLAPIError as e:
        raise HTTPException(status_code=502, detail=f"FPL API error: {e}")

    squad.refresh_stats_from(all_players)  # so advice is based on current form, not a stale snapshot

    try:
        advice = advisor.get_captain_advice(squad, fixtures)
    except AIRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AIAdvisorError as e:
        raise HTTPException(status_code=502, detail=f"AI advisor error: {e}")

    return {"advice": advice, "gameweek": gw}


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_available": advisor is not None}
