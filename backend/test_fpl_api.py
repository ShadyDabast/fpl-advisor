"""Tests for fpl_api.py — all HTTP calls are mocked; the real FPL API is never hit."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from fpl_api import FPLClient, FPLAPIError

FIXTURE = Path(__file__).parent / "fixtures" / "bootstrap_static_sample.json"


def load_bootstrap() -> dict:
    return json.loads(FIXTURE.read_text())


def ok_response(payload) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def test_get_all_players_parses_fixture():
    with patch("fpl_api.requests.get", return_value=ok_response(load_bootstrap())):
        players = FPLClient().get_all_players()

    assert len(players) == 3
    salah = next(p for p in players if p.name == "Salah")
    assert salah.fpl_id == 1
    assert salah.team == "Liverpool"
    assert salah.position == "MID"
    assert salah.price == 12.5          # now_cost 125 -> 12.5
    assert salah.form == 8.5
    assert salah.total_points == 120
    assert salah.ownership_percent == 45.2
    assert {p.position for p in players} == {"MID", "FWD", "GK"}


def test_get_all_players_skips_malformed_entries():
    data = load_bootstrap()
    del data["elements"][1]["now_cost"]        # Haaland loses a required field
    data["elements"][2]["team"] = 99           # Raya points at an unknown team

    with patch("fpl_api.requests.get", return_value=ok_response(data)):
        players = FPLClient().get_all_players()

    assert [p.name for p in players] == ["Salah"]


def test_retries_once_then_succeeds():
    responses = [requests.exceptions.ConnectionError("boom"), ok_response(load_bootstrap())]
    with patch("fpl_api.requests.get", side_effect=responses) as mock_get, \
         patch("fpl_api.time.sleep") as mock_sleep:
        players = FPLClient(retry_delay_seconds=0.5).get_all_players()

    assert len(players) == 3
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(0.5)


def test_raises_fpl_api_error_when_all_attempts_fail():
    with patch("fpl_api.requests.get",
               side_effect=requests.exceptions.Timeout("slow")) as mock_get, \
         patch("fpl_api.time.sleep"):
        with pytest.raises(FPLAPIError):
            FPLClient().get_all_players()

    assert mock_get.call_count == 2     # first try + one retry


def test_second_call_is_served_from_cache():
    with patch("fpl_api.requests.get", return_value=ok_response(load_bootstrap())) as mock_get:
        client = FPLClient()
        client.get_all_players()
        client.get_all_players()

    assert mock_get.call_count == 1


def test_current_and_next_gameweek():
    with patch("fpl_api.requests.get", return_value=ok_response(load_bootstrap())):
        client = FPLClient()
        assert client.get_current_gameweek() == 6
        assert client.get_next_gameweek() == 7


def test_get_fixtures_filters_by_gameweek_and_skips_unscheduled():
    fixtures_payload = [
        {"event": 7, "team_h": 1, "team_a": 2, "team_h_difficulty": 4, "team_a_difficulty": 3},
        {"event": 8, "team_h": 3, "team_a": 1, "team_h_difficulty": 2, "team_a_difficulty": 5},
        {"event": 7, "team_h": None, "team_a": None, "team_h_difficulty": 3, "team_a_difficulty": 3},
    ]

    def fake_get(url, timeout=None):
        if url.endswith("fixtures/"):
            return ok_response(fixtures_payload)
        return ok_response(load_bootstrap())

    with patch("fpl_api.requests.get", side_effect=fake_get):
        fixtures = FPLClient().get_fixtures(gameweek=7)

    assert len(fixtures) == 1
    f = fixtures[0]
    assert (f.home_team, f.away_team) == ("Liverpool", "Man City")
    assert (f.home_difficulty, f.away_difficulty) == (4, 3)
