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
from coup.simulation import (
    run_simulation, SlotStats, SimConfig,
    load_sim_config,
    SAMPLE_CONFIG, SAMPLE_CONFIG_NOTES,
)


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


def run_simulation_mode(config: SimConfig) -> None:
    fixed_seats = config.seat_order == "fixed"
    seating_note = "fixed seating" if fixed_seats else "random seating"

    print(f"\n  Running {config.games:,} simulations — {len(config.players)} players, {seating_note}")
    _print_player_summary(config)

    report_interval = max(1, config.games // 10)
    last_reported = 0

    def on_progress(done: int, total: int) -> None:
        nonlocal last_reported
        if done == total or done - last_reported >= report_interval:
            pct = done / total * 100
            bar = _progress_bar(done, total)
            print(f"  [{done:>{len(str(total))}}/{total}]  {pct:5.1f}%  {bar}")
            last_reported = done

    stats = run_simulation(config, progress_callback=on_progress)
    _print_report(stats, config)


def _print_player_summary(config: SimConfig) -> None:
    """Print a compact pre-game summary of each player's configuration."""
    print()
    for i, pc in enumerate(config.players):
        label = AIStrategy.__new__(AIStrategy)
        label.bluff_tendency = pc.bluff_tendency if pc.bluff_tendency is not None else 50
        tendency_str = str(pc.bluff_tendency) if pc.bluff_tendency is not None else "random"
        cards_str = " + ".join(pc.starting_cards) if pc.starting_cards else "random"
        seat_str = f"  seat {i+1}" if config.seat_order == "fixed" else ""
        print(f"  {_SLOT_LABELS[i]}{seat_str}  {pc.name:<14}  tendency {tendency_str:<6}  cards: {cards_str}")
    print()


def _print_report(stats: list[SlotStats], config: SimConfig) -> None:
    fixed_seats = config.seat_order == "fixed"
    num_games = config.games

    # Build column values first so we can size columns dynamically
    rows = []
    sort_key = (lambda x: x.seat) if fixed_seats else (lambda x: -x.wins)
    for s in sorted(stats, key=sort_key):
        ai_label = AIStrategy.__new__(AIStrategy)
        ai_label.bluff_tendency = s.bluff_tendency if s.bluff_tendency is not None else 50
        pct = s.wins / num_games * 100
        seat_col = str(s.seat + 1) if fixed_seats and s.seat is not None else ""
        rows.append((s.label, seat_col, s.name, s.tendency_display,
                     ai_label.personality_label, s.cards_display, s.wins, pct))

    # Column widths
    name_w  = max(len(r[2]) for r in rows)
    cards_w = max(len(r[5]) for r in rows)
    total_w = 6 + (7 if fixed_seats else 0) + name_w + 11 + 22 + cards_w + 14

    sep = "─" * total_w
    seat_hdr = f"{'Seat':<7}" if fixed_seats else ""
    print(f"\n  Simulation complete — {num_games:,} games  ({config.seat_order} seating)\n")
    print(f"  {sep}")
    print(f"  {'Slot':<6}{seat_hdr}{'Name':<{name_w+2}}{'Tendency':<11}{'Personality':<22}"
          f"{'Starting Cards':<{cards_w+2}}{'Wins':>5}  {'Win%':>5}")
    print(f"  {sep}")
    for label, seat, name, tendency, personality, cards, wins, pct in rows:
        seat_col = f"{seat:<7}" if fixed_seats else ""
        print(f"  {label:<6}{seat_col}{name:<{name_w+2}}{tendency:<11}{personality:<22}"
              f"{cards:<{cards_w+2}}{wins:>5}  {pct:>4.1f}%")
    print(f"  {sep}\n")


_SLOT_LABELS = ["A", "B", "C", "D", "E", "F"]


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
            "  python main.py --simulate sim.json\n"
            "  python main.py --generate-config            # print a sample config file\n"
        ),
    )

    # Interactive options
    parser.add_argument(
        "--players", type=int, default=4, metavar="N",
        help="Number of players for interactive mode (2–6, default 4)"
    )
    parser.add_argument(
        "--pause", type=float, nargs="?", const=1.0, default=0.0, metavar="SECONDS",
        help="Pause after each CPU action (default 1.0s when flag given without a value)"
    )

    # Simulation options
    parser.add_argument(
        "--simulate", metavar="CONFIG",
        help="Run simulation mode using the given JSON config file"
    )
    parser.add_argument(
        "--generate-config", action="store_true",
        help="Print a sample simulation config file and exit"
    )

    args = parser.parse_args()

    if args.generate_config:
        print(SAMPLE_CONFIG)
        print(SAMPLE_CONFIG_NOTES)
        return

    if args.simulate:
        try:
            config = load_sim_config(args.simulate)
        except (ValueError, FileNotFoundError) as exc:
            print(f"Error: {exc}")
            raise SystemExit(1)
        run_simulation_mode(config)
    else:
        if not (2 <= args.players <= 6):
            print("Error: --players must be between 2 and 6.")
            raise SystemExit(1)
        run_interactive_mode(args.players, args.pause)


if __name__ == "__main__":
    main()
