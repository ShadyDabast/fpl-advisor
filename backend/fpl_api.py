"""
Client for the official Fantasy Premier League API.

Owner: Member 2 (FPL API Integration)

No API key is required. The two endpoints used here:
  - GET https://fantasy.premierleague.com/api/bootstrap-static/
        -> all players, teams, positions, current gameweek
  - GET https://fantasy.premierleague.com/api/fixtures/
        -> all fixtures with FPL difficulty ratings

This module only fetches and normalizes raw data into our own Player /
Fixture objects — it does not know about Squads or Gemini.
"""

import time
import requests
from models import Player, Fixture

BASE_URL = "https://fantasy.premierleague.com/api"
POSITION_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


class FPLAPIError(Exception):
    """Raised when the FPL API can't be reached or returns bad data."""
    pass


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.0


def _is_transient_status(status_code: int) -> bool:
    return 500 <= status_code < 600


class FPLClient:
    def __init__(self, cache_ttl_seconds: int = 300):
        self._cache: dict = {}
        self._cache_time: dict = {}
        self.cache_ttl = cache_ttl_seconds

    def _get(self, endpoint: str) -> dict:
        """Fetch a JSON endpoint, with simple time-based caching and retries."""
        now = time.time()
        if endpoint in self._cache and (now - self._cache_time[endpoint]) < self.cache_ttl:
            return self._cache[endpoint]

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.get(
                    f"{BASE_URL}/{endpoint}",
                    headers={"User-Agent": USER_AGENT},
                    timeout=10,
                )
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                raise FPLAPIError(f"Failed to fetch {endpoint} after {attempt + 1} attempts: {e}") from e

            if response.ok:
                break

            last_error = FPLAPIError(f"Unexpected status {response.status_code} from {endpoint}")
            if attempt < MAX_RETRIES and _is_transient_status(response.status_code):
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
            raise last_error

        if last_error is not None and not response.ok:
            raise last_error

        data = response.json()
        self._cache[endpoint] = data
        self._cache_time[endpoint] = now
        return data

    def get_all_players(self) -> list[Player]:
        """Fetch every Premier League player with current FPL stats."""
        data = self._get("bootstrap-static/")
        teams_by_id = {t["id"]: t["name"] for t in data["teams"]}

        players = []
        for p in data["elements"]:
            try:
                players.append(Player(
                    fpl_id=p["id"],
                    name=p["web_name"],
                    team=teams_by_id[p["team"]],
                    position=POSITION_MAP[p["element_type"]],
                    price=p["now_cost"] / 10,       # FPL stores price *10
                    form=float(p["form"] or 0.0),
                    total_points=p["total_points"],
                    ownership_percent=float(p["selected_by_percent"] or 0.0),
                ))
            except (KeyError, ValueError) as e:
                # Skip malformed entries rather than failing the whole fetch
                print(f"Warning: skipped player id={p.get('id')} due to {e}")
        return players

    def get_player_by_name(self, name: str) -> Player | None:
        matches = [p for p in self.get_all_players() if name.lower() in p.name.lower()]
        return matches[0] if matches else None

    def get_current_gameweek(self) -> int:
        data = self._get("bootstrap-static/")
        for event in data["events"]:
            if event["is_current"]:
                return event["id"]
        # Fall back to next gameweek if none is marked current (e.g. off-season)
        for event in data["events"]:
            if event["is_next"]:
                return event["id"]
        raise FPLAPIError("Could not determine current gameweek.")

    def get_next_gameweek(self) -> int:
        """
        The gameweek advice should target: the next one whose deadline hasn't passed.

        FPL keeps a gameweek flagged `is_current` from its deadline until the NEXT
        deadline, so `is_current` can be a gameweek that is already locked or finished.
        Transfers/captain picks made now apply to `is_next`.
        """
        data = self._get("bootstrap-static/")
        for event in data["events"]:
            if event["is_next"]:
                return event["id"]
        # No next gameweek (end of season): fall back to the current one
        for event in data["events"]:
            if event["is_current"]:
                return event["id"]
        raise FPLAPIError("Could not determine the next gameweek.")

    def get_fixtures(self, gameweek: int | None = None) -> list[Fixture]:
        """Fetch fixtures, optionally filtered to a single gameweek."""
        data = self._get("fixtures/")
        bootstrap = self._get("bootstrap-static/")
        teams_by_id = {t["id"]: t["name"] for t in bootstrap["teams"]}

        fixtures = []
        for f in data:
            if gameweek is not None and f.get("event") != gameweek:
                continue
            if f.get("team_h") is None or f.get("team_a") is None:
                continue  # unscheduled fixture
            fixtures.append(Fixture(
                gameweek=f.get("event") or 0,
                home_team=teams_by_id[f["team_h"]],
                away_team=teams_by_id[f["team_a"]],
                home_difficulty=f["team_h_difficulty"],
                away_difficulty=f["team_a_difficulty"],
            ))
        return fixtures


if __name__ == "__main__":
    # Quick manual smoke test — run `python fpl_api.py` to sanity-check the client.
    client = FPLClient()
    print(f"Current gameweek: {client.get_current_gameweek()}")
    gw = client.get_next_gameweek()
    print(f"Next gameweek (used for advice): {gw}")

    players = client.get_all_players()
    print(f"Fetched {len(players)} players")
    top_5_by_form = sorted(players, key=lambda p: p.form, reverse=True)[:5]
    for p in top_5_by_form:
        print(" ", p)

    fixtures = client.get_fixtures(gameweek=gw)
    print(f"\n{len(fixtures)} fixtures in gameweek {gw}")
    for f in fixtures[:5]:
        print(f"  {f.home_team} (diff {f.home_difficulty}) vs {f.away_team} (diff {f.away_difficulty})")
