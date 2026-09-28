"""
Tests for caching and rate-limit handling in ai_advisor.py.

Uses a fake Gemini model, so no API key, network or quota is used.
Run with: pytest test_ai_cache.py -v
"""

import pytest
from ai_advisor import AIAdvisor, AIAdvisorError, AIRateLimitError
from models import Squad, Player, Fixture


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModel:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def generate_content(self, prompt):
        self.calls += 1
        if self.error:
            raise self.error
        return FakeResponse(f"advice #{self.calls}")


def make_advisor(model):
    advisor = AIAdvisor(api_key="fake-key")
    advisor.model = model
    return advisor


def sample_data():
    squad = Squad()
    squad.players = [Player(1, "Haaland", "Man City", "FWD", 14.5, 8.2, 210, 65.3)]
    fixtures = [Fixture(6, "Man City", "Arsenal", 3, 4)]
    return squad, fixtures


def test_identical_requests_use_cache_and_call_gemini_once():
    model = FakeModel()
    advisor = make_advisor(model)
    squad, fixtures = sample_data()

    first = advisor.get_captain_advice(squad, fixtures)
    second = advisor.get_captain_advice(squad, fixtures)

    assert first == second
    assert model.calls == 1


def test_different_squad_is_not_served_from_cache():
    model = FakeModel()
    advisor = make_advisor(model)
    squad, fixtures = sample_data()
    advisor.get_captain_advice(squad, fixtures)

    squad.players.append(Player(2, "Salah", "Liverpool", "MID", 13.0, 7.9, 195, 58.1))
    advisor.get_captain_advice(squad, fixtures)

    assert model.calls == 2


def test_quota_error_becomes_friendly_rate_limit_error():
    model = FakeModel(error=Exception("429 You exceeded your current quota"))
    advisor = make_advisor(model)
    squad, fixtures = sample_data()

    with pytest.raises(AIRateLimitError) as info:
        advisor.get_captain_advice(squad, fixtures)
    assert "usage limit" in str(info.value)


def test_other_errors_are_not_reported_as_rate_limits():
    model = FakeModel(error=Exception("connection reset"))
    advisor = make_advisor(model)
    squad, fixtures = sample_data()

    with pytest.raises(AIAdvisorError) as info:
        advisor.get_captain_advice(squad, fixtures)
    assert not isinstance(info.value, AIRateLimitError)


def test_failed_requests_are_not_cached():
    model = FakeModel(error=Exception("429 quota"))
    advisor = make_advisor(model)
    squad, fixtures = sample_data()

    with pytest.raises(AIRateLimitError):
        advisor.get_captain_advice(squad, fixtures)

    model.error = None  # quota is back
    assert advisor.get_captain_advice(squad, fixtures) == "advice #2"
