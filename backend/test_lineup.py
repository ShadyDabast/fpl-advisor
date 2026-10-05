"""
Tests for Squad.select_starting_xi().

Run with: pytest test_lineup.py -v
"""

import pytest
from models import Squad, Player, InvalidSquadError


def mk(fpl_id, name, team, position, form):
    return Player(fpl_id, name, team, position, 5.0, form, 50, 10.0)


def full_squad(gk_forms, def_forms, mid_forms, fwd_forms):
    """Build a valid 15-player squad with given form values per position,
    each player on a distinct club to avoid tripping the 3-per-club rule."""
    assert len(gk_forms) == 2 and len(def_forms) == 5
    assert len(mid_forms) == 5 and len(fwd_forms) == 3
    squad = Squad(budget=10_000)  # high budget so it never blocks the test
    clubs = iter(f"CLUB{i}" for i in range(15))
    fpl_id = 1
    for form in gk_forms:
        squad.add_player(mk(fpl_id, f"GK{fpl_id}", next(clubs), "GK", form))
        fpl_id += 1
    for form in def_forms:
        squad.add_player(mk(fpl_id, f"DEF{fpl_id}", next(clubs), "DEF", form))
        fpl_id += 1
    for form in mid_forms:
        squad.add_player(mk(fpl_id, f"MID{fpl_id}", next(clubs), "MID", form))
        fpl_id += 1
    for form in fwd_forms:
        squad.add_player(mk(fpl_id, f"FWD{fpl_id}", next(clubs), "FWD", form))
        fpl_id += 1
    return squad


def test_selects_11_starters_and_4_bench():
    squad = full_squad([7, 4], [8, 7, 6, 5, 4], [9, 8, 7, 6, 5], [6, 5, 4])
    result = squad.select_starting_xi()
    assert len(result["starters"]) == 11
    assert len(result["bench"]) == 4


def test_exactly_one_goalkeeper_starts():
    squad = full_squad([7, 4], [8, 7, 6, 5, 4], [9, 8, 7, 6, 5], [6, 5, 4])
    result = squad.select_starting_xi()
    starting_gks = [p for p in result["starters"] if p.position == "GK"]
    bench_gks = [p for p in result["bench"] if p.position == "GK"]
    assert len(starting_gks) == 1
    assert len(bench_gks) == 1


def test_higher_form_goalkeeper_starts():
    squad = full_squad([4, 9], [8, 7, 6, 5, 4], [9, 8, 7, 6, 5], [6, 5, 4])
    result = squad.select_starting_xi()
    starting_gk = [p for p in result["starters"] if p.position == "GK"][0]
    assert starting_gk.form == 9


def test_formation_respects_fpl_min_max_rules():
    squad = full_squad([7, 4], [8, 7, 6, 5, 4], [9, 8, 7, 6, 5], [6, 5, 4])
    result = squad.select_starting_xi()
    counts = {"DEF": 0, "MID": 0, "FWD": 0}
    for p in result["starters"]:
        if p.position in counts:
            counts["DEF"] = counts["DEF"] + (p.position == "DEF")
    def_count = sum(1 for p in result["starters"] if p.position == "DEF")
    mid_count = sum(1 for p in result["starters"] if p.position == "MID")
    fwd_count = sum(1 for p in result["starters"] if p.position == "FWD")

    assert 3 <= def_count <= 5
    assert 2 <= mid_count <= 5
    assert 1 <= fwd_count <= 3
    assert def_count + mid_count + fwd_count == 10
    assert result["formation"] == f"{def_count}-{mid_count}-{fwd_count}"


def test_highest_form_outfield_players_start_over_lower_form_bench():
    # Give one FWD a very high form so it should be pulled into one of the
    # 4 flexible spots even though FWD's minimum is already met at 1.
    squad = full_squad(
        gk_forms=[7, 4],
        def_forms=[6, 5.5, 5, 4.5, 4],
        mid_forms=[6, 5.5, 5, 4.5, 4],
        fwd_forms=[9, 3, 2],  # FWD0 (form 9) should start alongside the minimum
    )
    result = squad.select_starting_xi()
    starting_fwds = [p for p in result["starters"] if p.position == "FWD"]
    assert any(p.form == 9 for p in starting_fwds)


def test_no_overlap_between_starters_and_bench():
    squad = full_squad([7, 4], [8, 7, 6, 5, 4], [9, 8, 7, 6, 5], [6, 5, 4])
    result = squad.select_starting_xi()
    starter_ids = {p.fpl_id for p in result["starters"]}
    bench_ids = {p.fpl_id for p in result["bench"]}
    assert starter_ids.isdisjoint(bench_ids)
    assert len(starter_ids) + len(bench_ids) == 15


def test_incomplete_squad_raises():
    squad = Squad()
    squad.add_player(mk(1, "Solo", "ClubA", "GK", 5.0))
    with pytest.raises(InvalidSquadError):
        squad.select_starting_xi()


def test_wrong_position_distribution_raises():
    # 3 GK / 4 DEF / 5 MID / 3 FWD = 15 players but not a valid 2/5/5/3 split
    squad = Squad(budget=10_000)
    clubs = iter(f"CLUB{i}" for i in range(15))
    fpl_id = 1
    for _ in range(3):
        squad.players.append(mk(fpl_id, f"GK{fpl_id}", next(clubs), "GK", 5.0))
        fpl_id += 1
    for _ in range(4):
        squad.players.append(mk(fpl_id, f"DEF{fpl_id}", next(clubs), "DEF", 5.0))
        fpl_id += 1
    for _ in range(5):
        squad.players.append(mk(fpl_id, f"MID{fpl_id}", next(clubs), "MID", 5.0))
        fpl_id += 1
    for _ in range(3):
        squad.players.append(mk(fpl_id, f"FWD{fpl_id}", next(clubs), "FWD", 5.0))
        fpl_id += 1
    with pytest.raises(InvalidSquadError):
        squad.select_starting_xi()
