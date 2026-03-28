import argparse
import random
import sys

# Ensure emoji and Unicode box-drawing characters render on all terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

from coup.models import GameState, Card, Player
from coup.constants import Character
from coup.engine import GameEngine
from coup.ui.cli import CliUI
from coup.ai import AIStrategy


def build_deck() -> list[Card]:
    """Standard Coup deck: 3 copies of each of the 5 characters (15 cards total)."""
    cards = [Card(character=char) for char in Character for _ in range(3)]
    random.shuffle(cards)
    return cards


def main() -> None:
    parser = argparse.ArgumentParser(description="Play Coup (CPU vs CPU or Human vs CPU)")
    parser.add_argument(
        "--players", type=int, default=4,
        help="Total number of players (2–6, default 4)"
    )
    args = parser.parse_args()

    if not (2 <= args.players <= 6):
        print("Error: --players must be between 2 and 6.")
        raise SystemExit(1)

    ui = CliUI()
    player_configs = ui.setup_players(args.players)  # [(name, is_human), ...]

    deck = build_deck()
    players: list[Player] = []
    for i, (name, is_human) in enumerate(player_configs):
        hand = [deck.pop(), deck.pop()]
        players.append(Player(player_id=i, name=name, coins=2, hand=hand, is_human=is_human))

    state = GameState(players=players, deck=deck)

    ai_players = {
        p.player_id: AIStrategy(p)
        for p in players if not p.is_human
    }

    engine = GameEngine(state=state, ui=ui, ai_players=ai_players)
    engine.run()


if __name__ == "__main__":
    main()
