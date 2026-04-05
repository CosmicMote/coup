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


def _challenge_tendency_from_name(name: str) -> int:
    """Derive a stable 0–99 challenge tendency from a CPU player's name.

    Uses a different salt ("_challenge") so the value differs from the
    bluff tendency even for the same name.
    """
    digest = hashlib.md5((name + "_challenge").encode()).hexdigest()
    return int(digest, 16) % 100


def _confidence_from_name(name: str) -> int:
    """Derive a stable 0–99 confidence value from a CPU player's name."""
    digest = hashlib.md5((name + "_confidence").encode()).hexdigest()
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
        bluff_str = str(pc.bluff_tendency) if pc.bluff_tendency is not None else "random"
        challenge_str = str(pc.challenge_tendency) if pc.challenge_tendency is not None else "random"
        conf_str = str(pc.confidence) if pc.confidence is not None else "random"
        cards_str = " + ".join(pc.starting_cards) if pc.starting_cards else "random"
        seat_str = f"  seat {i+1}" if config.seat_order == "fixed" else ""
        print(f"  {_SLOT_LABELS[i]}{seat_str}  {pc.name:<14}  bluff {bluff_str:<6}  challenge {challenge_str:<6}  conf {conf_str:<6}  cards: {cards_str}")
    print()


def _print_report(stats: list[SlotStats], config: SimConfig) -> None:
    fixed_seats = config.seat_order == "fixed"
    num_games = config.games

    def _bluff_label(t: int | None) -> str:
        if t is None:
            return ""
        ai = AIStrategy.__new__(AIStrategy)
        ai.bluff_tendency = t
        return ai.personality_label

    def _challenge_label(t: int | None) -> str:
        if t is None:
            return ""
        ai = AIStrategy.__new__(AIStrategy)
        ai.challenge_tendency = t
        return ai.challenge_label

    def _confidence_label(t: int | None) -> str:
        if t is None:
            return ""
        ai = AIStrategy.__new__(AIStrategy)
        ai.confidence = t
        return ai.confidence_label

    # Build column values first so we can size columns dynamically
    rows = []
    sort_key = (lambda x: x.seat) if fixed_seats else (lambda x: -x.wins)
    for s in sorted(stats, key=sort_key):
        pct = s.wins / num_games * 100
        seat_col = str(s.seat + 1) if fixed_seats and s.seat is not None else ""
        rows.append((
            s.label, seat_col, s.name,
            s.tendency_display, _bluff_label(s.bluff_tendency),
            s.challenge_display, _challenge_label(s.challenge_tendency),
            s.confidence_display, _confidence_label(s.confidence),
            s.cards_display, s.wins, pct,
        ))

    # Column widths (at least as wide as the header)
    def _col_w(idx: int, header: str) -> int:
        return max(max(len(r[idx]) for r in rows), len(header))

    name_w      = _col_w(2, "Name")
    bluff_w     = _col_w(3, "Bluff")
    bluff_lbl_w = _col_w(4, "Bluff style")
    chall_w     = _col_w(5, "Challenge")
    chall_lbl_w = _col_w(6, "Challenge style")
    conf_w      = _col_w(7, "Conf")
    conf_lbl_w  = _col_w(8, "Confidence style")
    cards_w     = _col_w(9, "Starting Cards")
    total_w = (6 + (7 if fixed_seats else 0)
               + name_w + 2 + bluff_w + 2 + bluff_lbl_w + 2
               + chall_w + 2 + chall_lbl_w + 2
               + conf_w + 2 + conf_lbl_w + 2 + cards_w + 2 + 12)

    sep = "─" * total_w
    seat_hdr = f"{'Seat':<7}" if fixed_seats else ""
    print(f"\n  Simulation complete — {num_games:,} games  ({config.seat_order} seating)\n")
    print(f"  {sep}")
    print(f"  {'Slot':<6}{seat_hdr}{'Name':<{name_w+2}}{'Bluff':<{bluff_w+2}}{'Bluff style':<{bluff_lbl_w+2}}"
          f"{'Challenge':<{chall_w+2}}{'Challenge style':<{chall_lbl_w+2}}"
          f"{'Conf':<{conf_w+2}}{'Confidence style':<{conf_lbl_w+2}}"
          f"{'Starting Cards':<{cards_w+2}}{'Wins':>5}  {'Win%':>5}")
    print(f"  {sep}")
    for label, seat, name, bluff, bluff_lbl, chall, chall_lbl, conf, conf_lbl, cards, wins, pct in rows:
        seat_col = f"{seat:<7}" if fixed_seats else ""
        print(f"  {label:<6}{seat_col}{name:<{name_w+2}}{bluff:<{bluff_w+2}}{bluff_lbl:<{bluff_lbl_w+2}}"
              f"{chall:<{chall_w+2}}{chall_lbl:<{chall_lbl_w+2}}"
              f"{conf:<{conf_w+2}}{conf_lbl:<{conf_lbl_w+2}}{cards:<{cards_w+2}}{wins:>5}  {pct:>4.1f}%")
    print(f"  {sep}\n")


_SLOT_LABELS = ["A", "B", "C", "D", "E", "F"]


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def run_interactive_mode(
    num_players: int, pause_seconds: float, ai_type: str = "basic"
) -> None:
    from coup.adaptive_ai import AdaptiveAIStrategy

    ui = CliUI(pause_seconds=pause_seconds)
    player_configs = ui.setup_players(num_players)  # [(name, is_human), ...]

    deck = build_deck()
    players: list[Player] = []
    for i, (name, is_human) in enumerate(player_configs):
        hand = [deck.pop(), deck.pop()]
        players.append(Player(player_id=i, name=name, coins=2, hand=hand, is_human=is_human))

    state = GameState(players=players, deck=deck)

    ai_players = {}
    for p in players:
        if not p.is_human:
            conf = _confidence_from_name(p.name)
            p.confidence = conf
            if ai_type == "adaptive":
                ai_players[p.player_id] = AdaptiveAIStrategy(
                    p,
                    profiles={},
                    bluff_tendency=_tendency_from_name(p.name),
                    confidence=conf,
                )
            else:
                ai_players[p.player_id] = AIStrategy(
                    p,
                    bluff_tendency=_tendency_from_name(p.name),
                    challenge_tendency=_challenge_tendency_from_name(p.name),
                    confidence=conf,
                )

    # Announce CPU personalities so the human can size up their opponents
    if ai_players:
        print("  CPU personalities:")
        for strategy in ai_players.values():
            if isinstance(strategy, AdaptiveAIStrategy):
                print(f"    {strategy.player.name}: 🧠 Adaptive AI (confidence {strategy.confidence})")
            else:
                print(
                    f"    {strategy.player.name}: {strategy.personality_label} / {strategy.challenge_label} / {strategy.confidence_label} "
                    f"(bluff {strategy.bluff_tendency}, challenge {strategy.challenge_tendency}, confidence {strategy.confidence})"
                )
        print()

    observers = [s for s in ai_players.values() if hasattr(s, "notify")]
    engine = GameEngine(state=state, ui=ui, ai_players=ai_players, observers=observers)
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
        "--pause", type=float, nargs="?", const=7.0, default=7.0, metavar="SECONDS",
        help="Pause after each CPU action (default 1.0s when flag given without a value)"
    )
    parser.add_argument(
        "--ai", choices=["basic", "adaptive"], default="basic",
        help="CPU AI strategy for interactive mode: 'basic' (default) or 'adaptive'"
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
        run_interactive_mode(args.players, args.pause, ai_type=args.ai)


if __name__ == "__main__":
    main()
