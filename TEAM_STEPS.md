# FPL Advisor — Team Action Steps

Step-by-step checklist for each team member. Follow your section in order.

---

## Member 1 — Data, Auth & Persistence

1. Clone the repo, checkout your branch: `git checkout -b feature/member1-data-auth`
2. `cd backend`, `pip install -r requirements.txt`
3. Run the existing tests to confirm your starting point works:
   ```bash
   pytest test_models.py test_auth_db.py -v
   ```
   All 31 should pass. If any fail, stop and message the group before continuing.
4. Read through `models.py`, `db.py`, and `auth.py` — you own these.
5. Decide if anything needs extending (e.g. more player stats, squad history tracking). If yes, add it now while it's still early.
6. Commit and push: `git push origin feature/member1-data-auth` → open a PR.

## Member 2 — FPL API Integration

1. `git checkout -b feature/member2-fpl-api`
2. `cd backend`, `pip install -r requirements.txt`
3. Run the live smoke test:
   ```bash
   python fpl_api.py
   ```
4. If it errors, check the actual response shape — open `https://fantasy.premierleague.com/api/bootstrap-static/` in a browser and compare field names to what `fpl_api.py` expects (`p["now_cost"]`, `p["form"]`, etc.). Fix any mismatches.
5. Once it runs cleanly, add basic retry logic on failure (a simple `try/except` with one retry after a short delay is enough).
6. Write 3–5 pytest tests for `fpl_api.py` using **mocked** responses (don't hit the real API in tests) — save a real response as a fixture, then test that `get_all_players()` parses it correctly.
7. Commit, push, open a PR.

## Member 3 — AI Integration

1. `git checkout -b feature/member3-ai-integration`
2. `cd backend`, `pip install -r requirements.txt`
3. Get a free Gemini API key: https://aistudio.google.com/apikey
4. `export GEMINI_API_KEY="your-key"` then run:
   ```bash
   python ai_advisor.py
   ```
5. Read the actual advice it generates. If it's vague, too long, or ignores the fixture data, edit the prompts in `ai_advisor.py` (`get_transfer_advice`, `get_captain_advice`) and re-run until it's consistently useful.
6. Write 3–5 pytest tests using a **mocked** Gemini client (don't call the real API in tests — costs money/rate limits). Test that the prompt-building logic includes the right data, not the actual AI output.
7. Commit, push, open a PR.

## Member 4 — Backend, Frontend & Deployment

1. `git checkout -b feature/member4-integration`
2. Wait until Members 2 & 3 have pushed their verified versions (or coordinate to test with their branches merged locally first).
3. `cd backend`, `pip install -r requirements.txt`
4. Set both env vars:
   ```bash
   export GEMINI_API_KEY="your-key"
   export FPL_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
   ```
5. Run the backend: `uvicorn app:app --reload --port 8000`
6. Open `frontend/index.html` directly in a browser (or serve it: `python3 -m http.server 5500` from `/frontend`).
7. Test the full flow manually: register → log in → search a player → add to squad → get transfer advice → get captain advice → log out → log back in and confirm squad persisted.
8. Fix whatever breaks. Common issues: CORS errors (check the browser console), token not being sent correctly, mismatched field names between frontend and backend responses.
9. Once it works locally, deploy:
   - **Backend → Railway:** railway.app → New Project → Deploy from GitHub repo → root directory `/backend` → add env vars `GEMINI_API_KEY` and `FPL_SECRET_KEY` → start command `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Frontend → GitHub Pages:** update `API_BASE` in `app.js` to the Railway URL first → repo Settings → Pages → source = `/frontend` folder on `main`
10. Test the **live deployed URL** end to end, same checklist as step 7.
11. Update the README with the live URL.
12. Merge everyone's PRs into `main`, resolving conflicts as needed.

---

## Everyone, throughout
- Pull `main` before starting each session to stay current: `git checkout main && git pull origin main`
- Small, frequent commits with clear messages beat one giant commit at the end
- If you're blocked on someone else's piece, message the group rather than guessing at their interface
