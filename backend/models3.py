"""
Core domain classes for the FPL Advisor app.

Owner: Member 1 (Data & Persistence)

These classes are intentionally independent of the FPL API layer and the
AI layer — they only know about football/FPL concepts, not where the data
came from. That keeps them easy to test in isolation.
"""

from dataclasses import dataclass, field
from typing import Optional


class InvalidSquadError(Exception):
    """Raised when a squad violates FPL rules (budget, size, etc.)."""
    pass


@dataclass
class Player:
    """A single Premier League player, as relevant to FPL decisions."""

    fpl_id: int
    name: str
    team: str                # Premier League club, e.g. "Arsenal"
    position: str             # "GK", "DEF", "MID", or "FWD"
    price: float               # in £m, e.g. 8.5
    form: float                 # FPL's rolling form metric
    total_points: int
    ownership_percent: float     # e.g. 34.2 for 34.2%

    def __post_init__(self):
        valid_positions = {"GK", "DEF", "MID", "FWD"}
        if self.position not in valid_positions:
            raise ValueError(
                f"Invalid position '{self.position}'. Must be one of {valid_positions}"
            )
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")

    def __str__(self):
        return f"{self.name} ({self.team}, {self.position}) — £{self.price}m, form {self.form}"


@dataclass
class Fixture:
    """A single Premier League fixture with FPL's difficulty rating."""

    gameweek: int
    home_team: str
    away_team: str
    home_difficulty: int   # FPL difficulty rating, 1 (easy) to 5 (hard)
    away_difficulty: int

    def difficulty_for(self, team: str) -> int:
        if team == self.home_team:
            return self.home_difficulty
        elif team == self.away_team:
            return self.away_difficulty
        raise ValueError(f"'{team}' is not playing in this fixture")


class Squad:
    """
    A user's FPL squad: 15 players within FPL's budget and composition rules.

    Standard FPL rules (kept here so validation logic has one home):
      - 15 players total
      - 2 GK, 5 DEF, 5 MID, 3 FWD
      - Max 3 players from any one club
      - Total value must not exceed the budget (default £100.0m)
    """

    REQUIRED_COUNTS = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    MAX_PER_CLUB = 3

    def __init__(self, budget: float = 100.0, mode: str = " new\):
        self.budget = budget
        self.mode = mode  # " new\ or \current\
        self.players: list[Player] = []

    def add_player(self, player: Player) -> None:
        if len(self.players) >= 15:
            raise InvalidSquadError("Squad already has 15 players.")

        position_count = sum(1 for p in self.players if p.position == player.position)
        if position_count >= self.REQUIRED_COUNTS[player.position]:
            raise InvalidSquadError(
                f"Squad already has the max {self.REQUIRED_COUNTS[player.position]} "
                f"{player.position} players."
            )

        club_count = sum(1 for p in self.players if p.team == player.team)
        if club_count >= self.MAX_PER_CLUB:
            raise InvalidSquadError(f"Squad already has {self.MAX_PER_CLUB} players from {player.team}.")

        if self.total_value() + player.price > self.budget:
            raise InvalidSquadError(
                f"Adding {player.name} (£{player.price}m) would exceed the "
                f"£{self.budget}m budget."
            )

        self.players.append(player)

    def remove_player(self, fpl_id: int) -> Optional[Player]:
        for i, p in enumerate(self.players):
            if p.fpl_id == fpl_id:
                return self.players.pop(i)
        return None

    def total_value(self) -> float:
        return round(sum(p.price for p in self.players), 1)

    def remaining_budget(self) -> float:
        return round(self.budget - self.total_value(), 1)

    def is_complete(self) -> bool:
        if len(self.players) != 15:
            return False
        counts = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
        for p in self.players:
            counts[p.position] += 1
        return counts == self.REQUIRED_COUNTS

    def by_position(self, position: str) -> list[Player]:
        return [p for p in self.players if p.position == position]

    def to_dict(self) -> dict:
        return {
            "budget": self.budget,
            "players": [p.__dict__ for p in self.players],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Squad":
        squad = cls(budget=data.get("budget", 100.0))
        for p in data.get("players", []):
            squad.players.append(Player(**p))
        return squad

    def select_starting_xi(self) -> dict:
        """
        Pick a starting XI (11 players) and bench (4 players) from this
        squad's 15 players, using real FPL formation rules:
          - exactly 1 goalkeeper starts
          - outfield: 3-5 DEF, 2-5 MID, 1-3 FWD, totalling 10 players

        Selection is form-based: within each position, higher form starts
        first. The 3 position minimums (3 DEF / 2 MID / 1 FWD) are filled
        first, then the remaining 4 outfield spots go to whichever
        remaining players (any position) have the highest form, without
        breaking the max caps (5 DEF / 5 MID / 3 FWD).

        Returns {"formation": "3-4-3", "starters": [...], "bench": [...]}
        with starters/bench as lists of Player objects (GK first, then
        DEF, MID, FWD, each sorted by form descending).

        Raises InvalidSquadError if the squad doesn't have a valid 15
        (2 GK / 5 DEF / 5 MID / 3 FWD) to choose from.
        """
        if not self.is_complete():
            raise InvalidSquadError(
                "Squad needs a full, valid 15 players (2 GK, 5 DEF, 5 MID, 3 FWD) "
                "before a lineup can be selected."
            )

        gks = sorted(self.by_position("GK"), key=lambda p: p.form, reverse=True)
        defs = sorted(self.by_position("DEF"), key=lambda p: p.form, reverse=True)
        mids = sorted(self.by_position("MID"), key=lambda p: p.form, reverse=True)
        fwds = sorted(self.by_position("FWD"), key=lambda p: p.form, reverse=True)

        starting_gk = gks[0]
        bench_gk = gks[1]

        # Lock in the minimums first: top 3 DEF, top 2 MID, top 1 FWD
        MIN_DEF, MIN_MID, MIN_FWD = 3, 2, 1
        MAX_DEF, MAX_MID, MAX_FWD = 5, 5, 3

        starting_def = defs[:MIN_DEF]
        starting_mid = mids[:MIN_MID]
        starting_fwd = fwds[:MIN_FWD]

        remaining_def = defs[MIN_DEF:]
        remaining_mid = mids[MIN_MID:]
        remaining_fwd = fwds[MIN_FWD:]

        # Fill the remaining 4 outfield spots from whichever leftover
        # players (any position) have the highest form, respecting caps.
        pool = (
            [(p, "DEF") for p in remaining_def]
            + [(p, "MID") for p in remaining_mid]
            + [(p, "FWD") for p in remaining_fwd]
        )
        pool.sort(key=lambda item: item[0].form, reverse=True)

        spots_left = 11 - 1 - len(starting_def) - len(starting_mid) - len(starting_fwd)
        for player, pos in pool:
            if spots_left <= 0:
                break
            if pos == "DEF" and len(starting_def) < MAX_DEF:
                starting_def.append(player)
                spots_left -= 1
            elif pos == "MID" and len(starting_mid) < MAX_MID:
                starting_mid.append(player)
                spots_left -= 1
            elif pos == "FWD" and len(starting_fwd) < MAX_FWD:
                starting_fwd.append(player)
                spots_left -= 1

        starting_ids = {starting_gk.fpl_id} | {
            p.fpl_id for p in starting_def + starting_mid + starting_fwd
        }
        bench_outfield = [p for p in self.players if p.fpl_id not in starting_ids and p.position != "GK"]
        bench_outfield.sort(key=lambda p: p.form, reverse=True)

        formation = f"{len(starting_def)}-{len(starting_mid)}-{len(starting_fwd)}"

        return {
            "formation": formation,
            "starters": [starting_gk] + starting_def + starting_mid + starting_fwd,
            "bench": [bench_gk] + bench_outfield,
        }


