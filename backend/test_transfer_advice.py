import pytest
from ai_advisor import AIAdvisor
from models import Squad, Player, Fixture

class CaptureAdvisor(AIAdvisor):
    def __init__(self):
        # Bypass real Gemini init by providing dummy key
        super().__init__(api_key='dummy')
        self.captured_prompt = None

    def _generate(self, prompt: str) -> str:
        # Capture the prompt and return it for inspection
        self.captured_prompt = prompt
        return 'captured'

def test_three_gw_fixture_horizon():
    advisor = CaptureAdvisor()
    squad = Squad()
    squad.players = [Player(1, 'Haaland', 'Man City', 'FWD', 14.5, 8.2, 210, 65.3)]
    candidates = [Player(2, 'Isak', 'Newcastle', 'FWD', 8.5, 7.1, 140, 22.4)]
    # Fixtures for next three GWs for both teams
    fixtures = [
        # GW1 for Man City
        Fixture(6, 'Man City', 'Arsenal', 3, 4),
        Fixture(7, 'Man City', 'Chelsea', 2, 3),
        Fixture(8, 'Man City', 'Liverpool', 4, 2),
        # GW1-3 for Newcastle
        Fixture(6, 'Newcastle', 'Brentford', 2, 3),
        Fixture(7, 'Newcastle', 'Tottenham', 3, 2),
        Fixture(8, 'Newcastle', 'Everton', 1, 4),
    ]
    # Call advice (prompt will be captured)
    advisor.get_transfer_advice(squad, candidates, fixtures, free_transfers=1)
    prompt = advisor.captured_prompt
    # Verify horizon sentence present
    assert 'next three gameweeks' in prompt.lower()
    # Verify each GW appears for squad player summary
    assert 'GW6 vs Arsenal' in prompt
    assert 'GW7 vs Chelsea' in prompt
    assert 'GW8 vs Liverpool' in prompt
    # Verify candidate fixtures also appear
    assert 'GW6 vs Brentford' in prompt
    assert 'GW7 vs Tottenham' in prompt
    assert 'GW8 vs Everton' in prompt

def test_transfer_that_would_create_4_players_from_one_club():
    'Test that a transfer creating 4 players from one club is filtered out.'
    advisor = CaptureAdvisor()
    squad = Squad()
    # Start with 3 players from Man City (already at max)
    squad.players = [
        Player(1, 'Haaland', 'Man City', 'FWD', 14.5, 8.2, 210, 65.3),
        Player(2, 'De Bruyne', 'Man City', 'MID', 12.0, 7.8, 180, 45.2),
        Player(3, 'Foden', 'Man City', 'MID', 10.0, 7.5, 160, 30.1),
    ]
    # Try to add a 4th Man City player
    candidates = [
        Player(4, 'Silva', 'Man City', 'MID', 9.0, 7.2, 140, 25.0),
    ]
    fixtures = [
        Fixture(6, 'Man City', 'Arsenal', 3, 4),
    ]
    advisor.get_transfer_advice(squad, candidates, fixtures, free_transfers=1)
    prompt = advisor.captured_prompt
    # The Man City player should NOT appear in candidates because it would make 4
    assert 'Silva' not in prompt
    assert 'Man City' in prompt  # Squad players should still be there

def test_legal_transfer_keeps_club_count_at_3_or_fewer():
    'Test that a transfer keeping club count at 3 or fewer is allowed.'
    advisor = CaptureAdvisor()
    squad = Squad()
    # Start with 2 players from Man City (room for one more)
    squad.players = [
        Player(1, 'Haaland', 'Man City', 'FWD', 14.5, 8.2, 210, 65.3),
        Player(2, 'De Bruyne', 'Man City', 'MID', 12.0, 7.8, 180, 45.2),
        Player(3, 'Salah', 'Liverpool', 'FWD', 13.0, 7.9, 195, 58.1),  # Different club
    ]
    # Try to add a 3rd Man City player (should be allowed)
    candidates = [
        Player(4, 'Foden', 'Man City', 'MID', 10.0, 7.5, 160, 30.1),
        Player(5, 'Isak', 'Newcastle', 'FWD', 8.5, 7.1, 140, 22.4),   # Different club
    ]
    fixtures = [
        Fixture(6, 'Man City', 'Arsenal', 3, 4),
        Fixture(6, 'Liverpool', 'Chelsea', 2, 3),
        Fixture(6, 'Newcastle', 'Brentford', 2, 3),
    ]
    advisor.get_transfer_advice(squad, candidates, fixtures, free_transfers=1)
    prompt = advisor.captured_prompt
    # Both candidates should appear since neither would create a 4th player
    assert 'Foden' in prompt
    assert 'Isak' in prompt

def test_mixed_scenario_some_filtered_some_allowed():
    'Test mixed scenario where some candidates are filtered and some allowed.'
    advisor = CaptureAdvisor()
    squad = Squad()
    # Start with 3 players from Man City (already at max)
    squad.players = [
        Player(1, 'Haaland', 'Man City', 'FWD', 14.5, 8.2, 210, 65.3),
        Player(2, 'De Bruyne', 'Man City', 'MID', 12.0, 7.8, 180, 45.2),
        Player(3, 'Foden', 'Man City', 'MID', 10.0, 7.5, 160, 30.1),
        Player(4, 'Salah', 'Liverpool', 'FWD', 13.0, 7.9, 195, 58.1),  # Different club
    ]
    # Try to add: 4th Man City (should be filtered) vs 2nd Liverpool (should be allowed)
    candidates = [
        Player(5, 'Silva', 'Man City', 'MID', 9.0, 7.2, 140, 25.0),   # Would make 4 Man City - FILTERED
        Player(6, 'Nunez', 'Liverpool', 'FWD', 8.0, 6.8, 120, 15.0), # Would make 2 Liverpool - ALLOWED
    ]
    fixtures = [
        Fixture(6, 'Man City', 'Arsenal', 3, 4),
        Fixture(6, 'Liverpool', 'Chelsea', 2, 3),
    ]
    advisor.get_transfer_advice(squad, candidates, fixtures, free_transfers=1)
    prompt = advisor.captured_prompt
    # Silva should NOT appear (would make 4 Man City)
    assert 'Silva' not in prompt
    # Nunez should appear (would make only 2 Liverpool)
    assert 'Nunez' in prompt
    # Squad players should still be there
    assert 'Haaland' in prompt
    assert 'Salah' in prompt
