# FPL Advisor

An AI-powered Fantasy Premier League assistant. Tracks your squad, pulls live
data from the official FPL API, and uses Google Gemini to generate transfer
and captaincy advice.

## What's here
- `models.py` — `Player`, `Fixture`, `Squad` classes (Member 1). Enforces FPL
  squad rules: 15 players, 2/5/5/3 by position, max 3 per club, budget cap.
- `fpl_api.py` — `FPLClient` (Member 2), wraps the official FPL API (no key
  needed). Fetches all players, fixtures by gameweek, current gameweek.
- `storage.py` — save/load a `Squad` to/from a JSON file (Member 1).
- `ai_advisor.py` — `AIAdvisor` (Member 3), Gemini-powered transfer and
  captaincy advice.
- `main.py` — the CLI (Member 4) that ties everything together.
- `test_models.py` — pytest suite for `models.py`/`storage.py` (19 tests, all
  passing).

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
export GEMINI_API_KEY="your-key-here"   # skip this and the app still runs, just without AI features
python main.py
```

## Run tests
```bash
pytest test_models.py -v
```

## Status
- `models.py`, `storage.py`, `test_models.py`: fully tested and working.
- `main.py`: CLI logic fully tested with mocked data.
- `fpl_api.py`, `ai_advisor.py`: written and logic-tested with mocks, but
  **not yet verified against the real FPL/Gemini APIs** — no network access
  was available while building these. See action items below.

## Action items by member
- **Member 2:** run `python fpl_api.py`, confirm it fetches real players and
  fixtures without errors. Fix anything that breaks if the live API's field
  names differ from what's assumed. Add retry/backoff on failure. Write
  pytest tests for `fpl_api.py` using mocked API responses (capture a real
  response once and reuse it as test fixture data).
- **Member 3:** get a Gemini API key, set `GEMINI_API_KEY`, run
  `python ai_advisor.py`. Read the real advice it generates — tighten the
  prompts in `ai_advisor.py` if output is too generic or too long. Write
  pytest tests for `ai_advisor.py` using a mocked Gemini client (see the
  mocking pattern used to test this file during development, ask if you
  want it referenced).
- **Member 4:** once Members 2 & 3 confirm their layers work live, do a full
  end-to-end run of `main.py` against real data and fix any integration
  issues. Keep the README up to date as things change.
- **Everyone:** work on your own branch, open a PR into `main` when your
  piece is verified — don't push straight to `main`.

## FPL squad rules encoded in `Squad`
- 15 players: 2 GK, 5 DEF, 5 MID, 3 FWD
- Max 3 players from any club
- Total price must not exceed budget (default £100.0m)
