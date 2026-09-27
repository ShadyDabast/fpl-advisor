"""
Tests for the data & persistence layer.

Owner: Member 4 (Testing), with each member expected to add tests for
their own module (see README).

Run with: pytest test_models.py -v
"""

import os
import pytest
from models import Player, Squad, Fixture, InvalidSquadError
from storage import save_squad, load_squad


# ---------- Player ----------

def test_player_valid_creation():
    p = Player(1, "Haaland", "Man City", "FWD", 14.5, 8.2, 210, 65.3)
    assert p.name == "Haaland"
    assert p.position == "FWD"


def test_player_invalid_position_raises():
    with pytest.raises(ValueError):
        Player(1, "Bad", "X", "GOALKEEPER", 5.0, 1.0, 1, 1.0)


def test_player_invalid_price_raises():
    with pytest.raises(ValueError):
        Player(1, "Bad", "X", "GK", -1.0, 1.0, 1, 1.0)


def test_player_str_contains_name_and_team():
    p = Player(1, "Salah", "Liverpool", "MID", 13.0, 7.9, 195, 58.1)
    assert "Salah" in str(p)
    assert "Liverpool" in str(p)


# ---------- Fixture ----------

def test_fixture_difficulty_for_home_team():
    f = Fixture(5, "Man City", "Arsenal", 3, 4)
    assert f.difficulty_for("Man City") == 3


def test_fixture_difficulty_for_away_team():
    f = Fixture(5, "Man City", "Arsenal", 3, 4)
    assert f.difficulty_for("Arsenal") == 4


def test_fixture_difficulty_for_unknown_team_raises():
    f = Fixture(5, "Man City", "Arsenal", 3, 4)
    with pytest.raises(ValueError):
        f.difficulty_for("Chelsea")


# ---------- Squad: adding players ----------

@pytest.fixture
def sample_players():
    return {
        "gk": Player(1, "Raya", "Arsenal", "GK", 5.0, 6.0, 100, 20.0),
        "fwd_cheap": Player(2, "Wood", "Nottm Forest", "FWD", 6.5, 6.0, 120, 15.0),
        "fwd_expensive": Player(3, "Haaland", "Man City", "FWD", 14.5, 8.2, 210, 65.3),
    }


def test_add_player_increases_squad_size(sample_players):
    squad = Squad()
    squad.add_player(sample_players["gk"])
    assert len(squad.players) == 1


def test_add_player_updates_total_value(sample_players):
    squad = Squad()
    squad.add_player(sample_players["fwd_cheap"])
    assert squad.total_value() == 6.5
    assert squad.remaining_budget() == 93.5


def test_cannot_exceed_position_limit():
    squad = Squad()
    # GK limit is 2
    squad.add_player(Player(1, "GK1", "Arsenal", "GK", 5.0, 5.0, 50, 10.0))
    squad.add_player(Player(2, "GK2", "Chelsea", "GK", 4.5, 5.0, 50, 10.0))
    with pytest.raises(InvalidSquadError):
        squad.add_player(Player(3, "GK3", "Liverpool", "GK", 4.0, 5.0, 50, 10.0))


def test_cannot_exceed_club_limit():
    squad = Squad()
    for i in range(3):
        squad.add_player(Player(i, f"Player{i}", "Arsenal", "MID", 5.0, 5.0, 50, 10.0))
    with pytest.raises(InvalidSquadError):
        squad.add_player(Player(99, "OneTooMany", "Arsenal", "DEF", 5.0, 5.0, 50, 10.0))


def test_cannot_exceed_budget():
    squad = Squad(budget=10.0)
    squad.add_player(Player(1, "Cheap1", "Arsenal", "FWD", 6.0, 5.0, 50, 10.0))
    with pytest.raises(InvalidSquadError):
        squad.add_player(Player(2, "TooExpensive", "Chelsea", "FWD", 5.0, 5.0, 50, 10.0))


def test_cannot_exceed_15_players():
    squad = Squad(budget=1000.0)  # high budget so budget isn't the limiting factor
    positions = (["GK"] * 2) + (["DEF"] * 5) + (["MID"] * 5) + (["FWD"] * 3)
    clubs = ["Arsenal", "Chelsea", "Liverpool", "Man City", "Spurs"]
    for i, pos in enumerate(positions):
        squad.add_player(Player(i, f"P{i}", clubs[i % len(clubs)], pos, 5.0, 5.0, 50, 10.0))
    assert len(squad.players) == 15
    with pytest.raises(InvalidSquadError):
        squad.add_player(Player(99, "Extra", "Everton", "FWD", 4.0, 5.0, 50, 10.0))


# ---------- Squad: removing players ----------

def test_remove_existing_player_returns_it(sample_players):
    squad = Squad()
    squad.add_player(sample_players["gk"])
    removed = squad.remove_player(1)
    assert removed.name == "Raya"
    assert len(squad.players) == 0


def test_remove_nonexistent_player_returns_none(sample_players):
    squad = Squad()
    squad.add_player(sample_players["gk"])
    removed = squad.remove_player(999)
    assert removed is None
    assert len(squad.players) == 1


# ---------- Squad: completeness & filtering ----------

def test_is_complete_false_when_not_15():
    squad = Squad()
    squad.add_player(Player(1, "Solo", "Arsenal", "GK", 5.0, 5.0, 50, 10.0))
    assert squad.is_complete() is False


def test_by_position_filters_correctly(sample_players):
    squad = Squad()
    squad.add_player(sample_players["gk"])
    squad.add_player(sample_players["fwd_cheap"])
    assert len(squad.by_position("GK")) == 1
    assert len(squad.by_position("FWD")) == 1
    assert len(squad.by_position("MID")) == 0


# ---------- Storage: save/load round-trip ----------

def test_save_and_load_round_trip(tmp_path, sample_players):
    squad = Squad()
    squad.add_player(sample_players["gk"])
    squad.add_player(sample_players["fwd_cheap"])

    path = tmp_path / "test_squad.json"
    save_squad(squad, str(path))
    loaded = load_squad(str(path))

    assert len(loaded.players) == 2
    assert {p.name for p in loaded.players} == {"Raya", "Wood"}
    assert loaded.budget == squad.budget


def test_load_missing_file_returns_empty_squad(tmp_path):
    path = tmp_path / "does_not_exist.json"
    squad = load_squad(str(path))
    assert squad.players == []
    assert squad.budget == 100.0
