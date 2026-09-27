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

    def __init__(self, budget: float = 100.0):
        self.budget = budget
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
