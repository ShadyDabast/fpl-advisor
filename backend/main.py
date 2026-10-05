"""
Command-line interface for FPL Advisor — ties together the data, API,
storage, and AI layers into something runnable end to end.

Owner: Member 4 (Interface, Testing & Docs)

Run with: python main.py
"""

from models import Squad, InvalidSquadError
from fpl_api import FPLClient, FPLAPIError
from storage import save_squad, load_squad, DEFAULT_PATH
from ai_advisor import AIAdvisor, AIAdvisorError

MENU = """
==== FPL Advisor ====
1. View squad
2. Add player
3. Remove player
4. Save squad
5. Get transfer advice
6. Get captain advice
7. Exit
"""


def print_squad(squad: Squad) -> None:
    if not squad.players:
        print("Squad is empty.")
        return
    print(f"\nSquad ({len(squad.players)}/15 players) — "
          f"£{squad.total_value()}m used, £{squad.remaining_budget()}m remaining")
    for pos in ("GK", "DEF", "MID", "FWD"):
        players = squad.by_position(pos)
        if players:
            print(f"  {pos}:")
            for p in players:
                print(f"    {p}")


def add_player_flow(squad: Squad, client: FPLClient) -> None:
    name = input("Player name to search: ").strip()
    try:
        player = client.get_player_by_name(name)
    except FPLAPIError as e:
        print(f"Could not reach FPL API: {e}")
        return

    if not player:
        print(f"No player found matching '{name}'.")
        return

    print(f"Found: {player}")
    confirm = input("Add this player to your squad? (y/n): ").strip().lower()
    if confirm != "y":
        return

    try:
        squad.add_player(player)
        print(f"Added {player.name}.")
    except InvalidSquadError as e:
        print(f"Could not add player: {e}")


def remove_player_flow(squad: Squad) -> None:
    if not squad.players:
        print("Squad is empty.")
        return
    print_squad(squad)
    try:
        fpl_id = int(input("Enter the fpl_id of the player to remove: ").strip())
    except ValueError:
        print("Please enter a valid numeric id.")
        return
    removed = squad.remove_player(fpl_id)
    print(f"Removed {removed.name}." if removed else "No player with that id found.")


def transfer_advice_flow(squad: Squad, client: FPLClient, advisor: AIAdvisor) -> None:
    if not squad.players:
        print("Add some players to your squad first.")
        return

    position = input("Which position are you considering transferring in? (GK/DEF/MID/FWD): ").strip().upper()
    try:
        max_price = float(input("Max price for a replacement (£m): ").strip())
    except ValueError:
        print("Please enter a valid number.")
        return

    try:
        all_players = client.get_all_players()
        gw = client.get_current_gameweek()
        fixtures = client.get_fixtures(gameweek=gw)
    except FPLAPIError as e:
        print(f"Could not reach FPL API: {e}")
        return

    squad_ids = {p.fpl_id for p in squad.players}
    candidates = sorted(
        [p for p in all_players
         if p.position == position and p.price <= max_price and p.fpl_id not in squad_ids],
        key=lambda p: p.form, reverse=True
    )[:5]

    if not candidates:
        print("No candidates found matching that position/price.")
        return

    print("\nAsking Gemini for advice...")
    try:
        advice = advisor.get_transfer_advice(squad, candidates, fixtures)
    except AIAdvisorError as e:
        print(f"AI advisor failed: {e}")
        return

    print(f"\n--- Transfer Advice ---\n{advice}\n")


def captain_advice_flow(squad: Squad, client: FPLClient, advisor: AIAdvisor) -> None:
    if not squad.players:
        print("Add some players to your squad first.")
        return
    try:
        gw = client.get_current_gameweek()
        fixtures = client.get_fixtures(gameweek=gw)
    except FPLAPIError as e:
        print(f"Could not reach FPL API: {e}")
        return

    print("\nAsking Gemini for advice...")
    try:
        advice = advisor.get_captain_advice(squad, fixtures)
    except AIAdvisorError as e:
        print(f"AI advisor failed: {e}")
        return

    print(f"\n--- Captain Advice ---\n{advice}\n")


def main() -> None:
    print("Loading squad...")
    squad = load_squad()
    
    # Show mode selection if new squad or user hasn't chosen
    if not squad.players:
        print("\nAre you building a new squad or entering your current squad?")
        print("1. Build a new squad")
        print("2. Enter my current squad")
        choice = input("Choose (1/2): ").strip()
        if choice == "2":
            squad.mode = "CURRENT"
        else:
            squad.mode = "BUILDING" 
    client = FPLClient()

    # AI advisor needs an API key; don't crash the whole app if it's missing —
    # let the user still manage their squad without AI features.
    advisor = None
    try:
        advisor = AIAdvisor()
    except AIAdvisorError as e:
        print(f"(AI features disabled: {e})")

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()

        if choice == "1":
            print_squad(squad)
        elif choice == "2":
            add_player_flow(squad, client)
        elif choice == "3":
            remove_player_flow(squad)
        elif choice == "4":
            save_squad(squad)
            print(f"Squad saved to {DEFAULT_PATH}.")
        elif choice == "5":
            if advisor is None:
                print("AI advisor is not available (missing API key).")
            else:
                transfer_advice_flow(squad, client, advisor)
        elif choice == "6":
            if advisor is None:
                print("AI advisor is not available (missing API key).")
            else:
                captain_advice_flow(squad, client, advisor)
        elif choice == "7":
            print("Goodbye!")
            break
        else:
            print("Invalid option, try again.")


if __name__ == "__main__":
    main()
