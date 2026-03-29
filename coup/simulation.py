from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Callable

from coup.constants import Character, EventType
from coup.models import Card, Player, GameState
from coup.engine import GameEngine
from coup.ai import AIStrategy


# ---------------------------------------------------------------------------
# Silent UI — satisfies UIProtocol structurally; all methods are no-ops or
# stubs.  Human-decision methods are never called in simulation mode because
# every player is CPU-controlled.
# ---------------------------------------------------------------------------

class SilentUI:
    """Discards all events and raises if a human-decision method is called."""

    def setup_players(self, num_players: int) -> list[tuple[str, bool]]:
        return []  # not used in simulation; players are built directly

    def choose_action(self, state, player):
        raise RuntimeError("SilentUI.choose_action should never be called in simulation mode")

    def choose_target(self, state, player, action):
        raise RuntimeError("SilentUI.choose_target should never be called in simulation mode")

    def choose_block(self, state, potential_blocker, ctx):
        raise RuntimeError("SilentUI.choose_block should never be called in simulation mode")

    def choose_challenge_action(self, state, potential_challenger, ctx):
        raise RuntimeError("SilentUI.choose_challenge_action should never be called in simulation mode")

    def choose_card_to_lose(self, state, player, reason):
        raise RuntimeError("SilentUI.choose_card_to_lose should never be called in simulation mode")

    def choose_exchange_cards(self, state, player, all_cards):
        raise RuntimeError("SilentUI.choose_exchange_cards should never be called in simulation mode")

    def notify(self, event: EventType, **kwargs) -> None:
        pass  # discard all events


# ---------------------------------------------------------------------------
# Simulation results
# ---------------------------------------------------------------------------

@dataclass
class SlotStats:
    """Win statistics for one tendency slot across all simulated games."""
    label: str          # display name, e.g. "A"
    bluff_tendency: int
    wins: int = 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _build_deck() -> list[Card]:
    cards = [Card(character=char) for char in Character for _ in range(3)]
    random.shuffle(cards)
    return cards


# Labels for up to 6 players
_SLOT_LABELS = ["A", "B", "C", "D", "E", "F"]


def run_simulation(
    tendencies: list[int],
    num_games: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[SlotStats]:
    """
    Run ``num_games`` games with CPU players whose bluff tendencies are given
    by ``tendencies`` (one entry per player).

    Player seating order is reshuffled every game so that going-first advantage
    does not bias the win-rate comparison between tendencies.

    ``progress_callback(games_done, total)`` is called after every completed
    game if provided — the caller decides how often to actually print something.

    Returns a list of SlotStats (one per tendency slot, in input order).
    """
    if not (2 <= len(tendencies) <= 6):
        raise ValueError("tendencies must have between 2 and 6 entries")

    num_players = len(tendencies)
    stats = [
        SlotStats(label=_SLOT_LABELS[i], bluff_tendency=t)
        for i, t in enumerate(tendencies)
    ]
    ui = SilentUI()

    for game_num in range(1, num_games + 1):
        # Shuffle which tendency occupies which seat this game.
        # seat_to_slot[seat] = index into stats / tendencies
        seat_to_slot = list(range(num_players))
        random.shuffle(seat_to_slot)

        deck = _build_deck()
        players: list[Player] = []
        ai_players: dict[int, AIStrategy] = {}

        for seat, slot_idx in enumerate(seat_to_slot):
            t = tendencies[slot_idx]
            hand = [deck.pop(), deck.pop()]
            player = Player(
                player_id=seat,
                name=f"{stats[slot_idx].label}(t={t})",
                coins=2,
                hand=hand,
                is_human=False,
            )
            players.append(player)
            ai_players[seat] = AIStrategy(player, bluff_tendency=t)

        state = GameState(players=players, deck=deck)
        engine = GameEngine(state=state, ui=ui, ai_players=ai_players)
        winner = engine.run()

        # Map winner's seat back to the tendency slot they represent
        winner_slot_idx = seat_to_slot[winner.player_id]
        stats[winner_slot_idx].wins += 1

        if progress_callback:
            progress_callback(game_num, num_games)

    return stats
