"""
AI advice layer — turns squad/player/fixture data into natural-language
transfer and captaincy recommendations using Google Gemini.

Owner: Member 3 (AI Integration)

This module never talks to the FPL API or storage directly — it only takes
domain objects (Squad, Player, Fixture) that other layers have already
fetched, and returns plain text. That keeps it easy to test with fake data
and easy to swap models later if needed.
"""

import os
import time
import google.generativeai as genai
from models import Squad, Player, Fixture

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")  # override with the GEMINI_MODEL env var if Google renames/retires models again


class AIAdvisorError(Exception):
    """Raised when the Gemini API can't be reached or returns something unusable."""
    pass


class AIRateLimitError(AIAdvisorError):
    """Raised when Gemini reports the usage quota has been exceeded (HTTP 429)."""
    pass


# Identical requests (same squad, candidates, fixtures) reuse the last answer for
# this long instead of spending another API call. Free-tier quotas are small.
CACHE_TTL_SECONDS = int(os.environ.get("GEMINI_CACHE_TTL_SECONDS", "3600"))


def _looks_like_rate_limit(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "429" in text
        or "quota" in text
        or "resourceexhausted" in type(error).__name__.lower()
    )


class AIAdvisor:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise AIAdvisorError(
                "No Gemini API key found. Set the GEMINI_API_KEY environment "
                "variable or pass api_key explicitly."
            )
        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(MODEL_NAME)
        self._cache: dict[str, tuple[float, str]] = {}

    def _generate(self, prompt: str) -> str:
        """Send a prompt to Gemini, with caching and friendly quota errors."""
        now = time.time()
        cached = self._cache.get(prompt)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

        try:
            response = self.model.generate_content(prompt)
        except Exception as e:
            if _looks_like_rate_limit(e):
                raise AIRateLimitError(
                    "The AI advisor has reached its usage limit for now. "
                    "Please try again in a few minutes, or later today if the daily limit is used up."
                ) from e
            raise AIAdvisorError(f"Gemini request failed: {e}") from e

        if not response.text:
            raise AIAdvisorError("Gemini returned an empty response.")

        text = response.text.strip()
        self._cache[prompt] = (now, text)
        return text

    def _build_player_summary(self, player: Player, fixtures: list[Fixture]) -> str:
        """One line of stats + upcoming fixture difficulty for a player."""
        upcoming = [f for f in fixtures if player.team in (f.home_team, f.away_team)]
        difficulty_str = ", ".join(
            f"GW{f.gameweek} vs {f.away_team if f.home_team == player.team else f.home_team} "
            f"(difficulty {f.difficulty_for(player.team)})"
            for f in upcoming[:3]
        ) or "no upcoming fixtures found"

        return (
            f"- {player.name} ({player.team}, {player.position}): £{player.price}m, "
            f"form {player.form}, {player.total_points} pts season, "
            f"{player.ownership_percent}% owned. Fixtures: {difficulty_str}"
        )

    def get_transfer_advice(
        self,
        squad: Squad,
        candidates: list[Player],
        fixtures: list[Fixture],
        free_transfers: int = 1,
    ) -> str:
        """
        Recommend transfer(s) in/out based on the current squad, a pool of
        candidate players to consider bringing in, and upcoming fixtures.
        """
        squad_summary = "\n".join(self._build_player_summary(p, fixtures) for p in squad.players)

        # --- Enforce max-3-players-per-club rule ---
        # Count how many players from each club are already in the squad.
        club_counts: dict[str, int] = {}
        for p in squad.players:
            club_counts[p.team] = club_counts.get(p.team, 0) + 1

        # Filter out any candidate that would breach the rule if added.
        # (We assume the manager will transfer out *some* player, but we cannot
        # guarantee that the outgoing player is from the same club, so we err on
        # the side of safety and exclude candidates that would create a 4th
        # player from a club.)
        allowed_candidates = [
            c for c in candidates if club_counts.get(c.team, 0) < Squad.MAX_PER_CLUB
        ]

        # Build the candidate summary from the filtered list.
        candidate_summary = "\n".join(
            self._build_player_summary(p, fixtures) for p in allowed_candidates
        )

        prompt = f"""You are an expert Fantasy Premier League (FPL) advisor.

Current squad (budget £{squad.budget}m, £{squad.remaining_budget()}m remaining):
{squad_summary}

Candidate players to consider bringing in:
{candidate_summary}

The manager has {free_transfers} free transfer(s) available this gameweek.

The fixture list above covers the next three gameweeks (GW+1, GW+2, GW+3).
Evaluate each player’s expected usefulness across the full 3-gameweek horizon,
not just the next fixture. A difficult GW+1 followed by two good fixtures may
make holding reasonable; an easy GW+1 followed by several difficult fixtures may
limit the value of a short-term transfer. Consistently favourable fixtures across
all 3 GWs strengthen the transfer case; consistently difficult fixtures strengthen
the sell/avoid consideration. Also weigh player form, price, squad composition,
and the manager’s transfer/budget constraints.

Based on form, price, and upcoming fixture difficulty, recommend whether the
manager should make a transfer this gameweek. If yes, say exactly who to
transfer OUT and who to bring IN, and explain why in 2-3 sentences using the
data above. If no transfer is worth it, say so and explain why. Keep the
whole response under 150 words and avoid generic filler."""

        return self._generate(prompt)

    def get_captain_advice(self, squad: Squad, fixtures: list[Fixture]) -> str:
        """Recommend a captain and vice-captain from the current squad."""
        squad_summary = "\n".join(self._build_player_summary(p, fixtures) for p in squad.players)

        prompt = f"""You are an expert Fantasy Premier League (FPL) advisor.

Current squad:
{squad_summary}

Based on form and upcoming fixture difficulty, recommend a captain and a
vice-captain for the next gameweek from this squad only. Explain the choice
in 2-3 sentences using the data above. Keep the whole response under 100
words and avoid generic filler."""

        return self._generate(prompt)


if __name__ == "__main__":
    # Quick manual smoke test with fake data — run `python ai_advisor.py`
    # after setting GEMINI_API_KEY to sanity-check prompts against real output.
    squad = Squad()
    squad.players = [
        Player(1, "Haaland", "Man City", "FWD", 14.5, 8.2, 210, 65.3),
        Player(2, "Salah", "Liverpool", "MID", 13.0, 7.9, 195, 58.1),
    ]
    candidates = [
        Player(3, "Isak", "Newcastle", "FWD", 8.5, 7.1, 140, 22.4),
    ]
    fixtures = [
        Fixture(5, "Man City", "Arsenal", 3, 4),
        Fixture(5, "Liverpool", "Everton", 2, 4),
        Fixture(5, "Newcastle", "Brentford", 2, 3),
    ]

    advisor = AIAdvisor()
    print("=== Transfer Advice ===")
    print(advisor.get_transfer_advice(squad, candidates, fixtures))
    print("\n=== Captain Advice ===")
    print(advisor.get_captain_advice(squad, fixtures))
