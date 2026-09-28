"""
Tests that advice targets the right gameweek.

Uses fake bootstrap data instead of the live FPL API.
Run with: pytest test_gameweek.py -v
"""

from fpl_api import FPLClient, FPLAPIError
import pytest


def client_with_events(events):
    client = FPLClient()
    client._get = lambda endpoint: {"events": events, "teams": []}
    return client


def event(gw, is_current=False, is_next=False):
    return {"id": gw, "is_current": is_current, "is_next": is_next}


def test_mid_season_targets_next_gameweek_not_current():
    # GW5 is 'current' (deadline passed / finished), GW6 is the one still open
    events = [event(4), event(5, is_current=True), event(6, is_next=True), event(7)]
    client = client_with_events(events)
    assert client.get_current_gameweek() == 5
    assert client.get_next_gameweek() == 6


def test_start_of_season_targets_gameweek_1():
    events = [event(1, is_next=True), event(2), event(3)]
    assert client_with_events(events).get_next_gameweek() == 1


def test_end_of_season_falls_back_to_current():
    events = [event(37), event(38, is_current=True)]
    assert client_with_events(events).get_next_gameweek() == 38


def test_no_gameweek_info_raises():
    with pytest.raises(FPLAPIError):
        client_with_events([event(1), event(2)]).get_next_gameweek()
