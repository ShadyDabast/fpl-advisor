
"""
Tests for fpl_api.py (FPLClient) using mocked API responses.

Owner: Member 2 (FPL API Integration)

Run with: pytest test_fpl_api.py -v
"""

import pytest
import requests
from fpl_api import FPLClient, FPLAPIError


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if not self.ok:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def sample_bootstrap_and_fixtures():
    bootstrap = {
        "teams": [
            {"id": 1, "name": "Arsenal"},
            {"id": 2, "name": "Chelsea"}
        ],
        "elements": [
            {
                "id": 10,
                "web_name": "Saka",
                "team": 1,
                "element_type": 3,
                "now_cost": 100,
                "form": "7.5",
                "total_points": 120,
                "selected_by_percent": "35.0"
            },
            {
                "id": 20,
                "web_name": "Palmer",
                "team": 2,
                "element_type": 3,
                "now_cost": 105,
                "form": "8.0",
                "total_points": 130,
                "selected_by_percent": "40.5"
            }
        ],
        "events": [
            {"id": 5, "is_current": True, "is_next": False},
            {"id": 6, "is_current": False, "is_next": True}
        ]
    }
    fixtures = [
        {
            "event": 6,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 2,
            "team_a_difficulty": 3
        }
    ]
    return bootstrap, fixtures


def test_get_all_players_parses_correctly(monkeypatch, sample_bootstrap_and_fixtures):
    bootstrap, fixtures = sample_bootstrap_and_fixtures
    
    def mock_get(url, **kwargs):
        if "bootstrap-static" in url:
            return MockResponse(bootstrap)
        return MockResponse(fixtures)

    monkeypatch.setattr(requests, "get", mock_get)

    client = FPLClient()
    players = client.get_all_players()

    assert len(players) == 2
    saka = [p for p in players if p.name == "Saka"][0]
    assert saka.team == "Arsenal"
    assert saka.position == "MID"
    assert saka.price == 10.0
    assert saka.form == 7.5
    assert saka.total_points == 120
    assert saka.ownership_percent == 35.0


def test_get_player_by_name(monkeypatch, sample_bootstrap_and_fixtures):
    bootstrap, fixtures = sample_bootstrap_and_fixtures
    monkeypatch.setattr(requests, "get", lambda url, **kw: MockResponse(bootstrap))

    client = FPLClient()
    player = client.get_player_by_name("palm")
    assert player is not None
    assert player.name == "Palmer"

    missing = client.get_player_by_name("nonexistent")
    assert missing is None


def test_get_fixtures_filters_by_gameweek(monkeypatch, sample_bootstrap_and_fixtures):
    bootstrap, fixtures = sample_bootstrap_and_fixtures

    def mock_get(url, **kwargs):
        if "bootstrap-static" in url:
            return MockResponse(bootstrap)
        return MockResponse(fixtures)

    monkeypatch.setattr(requests, "get", mock_get)

    client = FPLClient()
    gw6_fixtures = client.get_fixtures(gameweek=6)
    assert len(gw6_fixtures) == 1
    assert gw6_fixtures[0].home_team == "Arsenal"
    assert gw6_fixtures[0].away_team == "Chelsea"
    assert gw6_fixtures[0].home_difficulty == 2

    gw7_fixtures = client.get_fixtures(gameweek=7)
    assert len(gw7_fixtures) == 0


def test_cache_is_reused_within_ttl(monkeypatch, sample_bootstrap_and_fixtures):
    bootstrap, _ = sample_bootstrap_and_fixtures
    calls = 0

    def mock_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return MockResponse(bootstrap)

    monkeypatch.setattr(requests, "get", mock_get)

    client = FPLClient(cache_ttl_seconds=300)
    client.get_current_gameweek()
    client.get_current_gameweek()

    assert calls == 1  # second call hit cache


def test_api_error_raised_on_failure(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, **kw: MockResponse({}, status_code=500))
    monkeypatch.setattr("time.sleep", lambda s: None)

    client = FPLClient()
    with pytest.raises(FPLAPIError):
        client.get_all_players()

