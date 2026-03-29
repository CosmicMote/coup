import argparse
import hashlib
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
from coup.simulation import run_simulation, SlotStats


def _tendency_from_name(name: str) -> int:
    """Derive a stable 0–99 bluff tendency from a CPU player's name.

    Uses MD5 rather than Python's built-in hash() because hash() is
    randomised per-process (PYTHONHASHSEED), which would give a different
    tendency every run.  MD5 is deterministic regardless of environment.
    """
    digest = hashlib.md5(name.encode()).hexdigest()
    return int(digest, 16) % 100


def build_deck() -> list[Card]:
    """Standard Coup deck: 3 copies of each of the 5 characters (15 cards total)."""
    cards = [Card(character=char) for char in Character for _ in range(3)]
    random.shuffle(cards)
    return cards


# ---------------------------------------------------------------------------
# Simulation mode
# ---------------------------------------------------------------------------

def _progress_bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / total)
    return "▓" * filled + "░" * (width - filled)


def run_simulation_mode(tendencies: list[int], num_games: int) -> None:
    from coup.ai import AIStrategy  # for personality_label lookup

    print(f"\n  Running {num_games:,} simulations with {len(tendencies)} players...")
    print(f"  Tendencies: {tendencies}\n")

    report_interval = max(1, num_games // 10)   # print ~10 progress lines
    last_reported = 0

    def on_progress(done: int, total: int) -> None:
        nonlocal last_reported
        if done == total or done - last_reported >= report_interval:
            pct = done / total * 100
            bar = _progress_bar(done, total)
            print(f"  [{done:>{len(str(total))}}/{total}]  {pct:5.1f}%  {bar}")
            last_reported = done

    stats = run_simulation(tendencies, num_games, progress_callback=on_progress)

    # ---- Report ----
    sep = "─" * 58
    print(f"\n  Simulation complete — {num_games:,} games\n")
    print(f"  {sep}")
    print(f"  {'Slot':<6}{'Tendency':>9}  {'Personality':<22}{'Wins':>6}  {'Win %':>6}")
    print(f"  {sep}")
    for s in sorted(stats, key=lambda x: x.wins, reverse=True):
        # Reuse AIStrategy just to get the personality label
        label = AIStrategy.__new__(AIStrategy)
        label.bluff_tendency = s.bluff_tendency
        pct = s.wins / num_games * 100
        print(
            f"  {s.label:<6}{s.bluff_tendency:>9}  "
            f"{label.personality_label:<22}{s.wins:>6}  {pct:>5.1f}%"
        )
    print(f"  {sep}\n")


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def run_interactive_mode(num_players: int, pause_seconds: float) -> None:
    ui = CliUI(pause_seconds=pause_seconds)
    player_configs = ui.setup_players(num_players)  # [(name, is_human), ...]

    deck = build_deck()
    players: list[Player] = []
    for i, (name, is_human) in enumerate(player_configs):
        hand = [deck.pop(), deck.pop()]
        players.append(Player(player_id=i, name=name, coins=2, hand=hand, is_human=is_human))

    state = GameState(players=players, deck=deck)

    ai_players = {
        p.player_id: AIStrategy(p, bluff_tendency=_tendency_from_name(p.name))
        for p in players if not p.is_human
    }

    # Announce CPU personalities so the human can size up their opponents
    if ai_players:
        print("  CPU personalities:")
        for ai in ai_players.values():
            print(f"    {ai.player.name}: {ai.personality_label} (bluff tendency {ai.bluff_tendency})")
        print()

    engine = GameEngine(state=state, ui=ui, ai_players=ai_players)
    engine.run()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Play Coup interactively, or run bluff-tendency simulations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                              # interactive, 4 players\n"
            "  python main.py --players 2 --pause 1       # 2-player game, 1s CPU pause\n"
            "  python main.py --simulate                  # simulate default tendencies\n"
            "  python main.py --simulate --tendencies 0 50 100 --games 500\n"
        ),
    )

    # Interactive options
    parser.add_argument(
        "--players", type=int, default=4, metavar="N",
        help="Number of players for interactive mode (2–6, default 4)"
    )
    parser.add_argument(
        "--pause", type=float, nargs="?", const=7.0, default=7.0, metavar="SECONDS",
        help="Pause after each CPU action (default 1.0s when flag given without a value)"
    )

    # Simulation options
    parser.add_argument(
        "--simulate", action="store_true",
        help="Run in simulation mode (no human players)"
    )
    parser.add_argument(
        "--tendencies", type=int, nargs="+", metavar="T",
        default=[0, 25, 50, 75, 100],
        help="Bluff tendencies for simulation players (2–6 values, default: 0 25 50 75 100)"
    )
    parser.add_argument(
        "--games", type=int, default=100, metavar="N",
        help="Number of games to simulate (default 100)"
    )

    args = parser.parse_args()

    if args.simulate:
        if not (2 <= len(args.tendencies) <= 6):
            print("Error: --tendencies requires between 2 and 6 values.")
            raise SystemExit(1)
        if args.games < 1:
            print("Error: --games must be at least 1.")
            raise SystemExit(1)
        run_simulation_mode(args.tendencies, args.games)
    else:
        if not (2 <= args.players <= 6):
            print("Error: --players must be between 2 and 6.")
            raise SystemExit(1)
        run_interactive_mode(args.players, args.pause)


if __name__ == "__main__":
    main()
