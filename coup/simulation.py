from __future__ import annotations
import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from coup.constants import Character, EventType
from coup.models import Card, Player, GameState
from coup.engine import GameEngine
from coup.ai import AIStrategy
from coup.adaptive_ai import AdaptiveAIStrategy, OpponentProfile


# ---------------------------------------------------------------------------
# Silent UI
# ---------------------------------------------------------------------------

class SilentUI:
    """Discards all events; raises if a human-decision method is called."""

    def setup_players(self, num_players: int) -> list[tuple[str, bool]]:
        return []

    def choose_action(self, state, player):
        raise RuntimeError("SilentUI: choose_action called — all sim players must be CPU")

    def choose_target(self, state, player, action):
        raise RuntimeError("SilentUI: choose_target called — all sim players must be CPU")

    def choose_block(self, state, potential_blocker, ctx):
        raise RuntimeError("SilentUI: choose_block called — all sim players must be CPU")

    def choose_challenge_action(self, state, potential_challenger, ctx):
        raise RuntimeError("SilentUI: choose_challenge_action called — all sim players must be CPU")

    def choose_card_to_lose(self, state, player, reason):
        raise RuntimeError("SilentUI: choose_card_to_lose called — all sim players must be CPU")

    def choose_exchange_cards(self, state, player, all_cards):
        raise RuntimeError("SilentUI: choose_exchange_cards called — all sim players must be CPU")

    def notify(self, event: EventType, **kwargs) -> None:
        pass


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

_VALID_CHARACTERS = {c.value.lower(): c for c in Character}
_SLOT_LABELS = ["A", "B", "C", "D", "E", "F"]

# Pool of random names (same pool as CliUI)
_CPU_NAMES: list[str] = [
    "Machiavelli", "Borgia",    "Medici",   "Richelieu", "Talleyrand",
    "Metternich",  "Bismarck",  "Cavour",   "Fouché",    "Mazarin",
    "Colbert",     "Walpole",   "Disraeli", "Metella",   "Agrippina",
    "Lucrezia",    "Sforza",    "Gonzaga",  "Visconti",  "Farnese",
    "Orsini",      "Colonna",   "Pazzi",    "Albizzi",   "Strozzi",
]


@dataclass
class PlayerConfig:
    """Configuration for one player slot in a simulation."""
    name: str | None = None               # None → pick a random name once at load time
    bluff_tendency: int | None = None     # None → pick a fresh random value each game
    challenge_tendency: int | None = None # None → pick a fresh random value each game
    confidence: int | None = None         # None → pick a fresh random value each game
    ai_type: str = "basic"                # "basic" | "adaptive"
    starting_cards: list[str] | None = None  # None → deal randomly each game
                                             # e.g. ["Duke", "Captain"]


@dataclass
class SimConfig:
    """Full simulation configuration."""
    players: list[PlayerConfig]
    games: int = 100
    seat_order: str = "random"   # "random" | "fixed"

    def __post_init__(self) -> None:
        _validate_config(self)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_config(cfg: SimConfig) -> None:
    if not (2 <= len(cfg.players) <= 6):
        raise ValueError(f"Need 2–6 players, got {len(cfg.players)}")

    if cfg.seat_order not in ("random", "fixed"):
        raise ValueError(f"seat_order must be 'random' or 'fixed', got {cfg.seat_order!r}")

    if cfg.games < 1:
        raise ValueError(f"games must be >= 1, got {cfg.games}")

    card_demand: Counter[Character] = Counter()
    for i, p in enumerate(cfg.players):
        slot = f"Player {_SLOT_LABELS[i]}"
        if p.bluff_tendency is not None and not (0 <= p.bluff_tendency <= 100):
            raise ValueError(f"{slot}: bluff_tendency must be 0–100, got {p.bluff_tendency}")

        if p.challenge_tendency is not None and not (0 <= p.challenge_tendency <= 100):
            raise ValueError(f"{slot}: challenge_tendency must be 0–100, got {p.challenge_tendency}")

        if p.confidence is not None and not (0 <= p.confidence <= 100):
            raise ValueError(f"{slot}: confidence must be 0–100, got {p.confidence}")

        if p.ai_type not in ("basic", "adaptive"):
            raise ValueError(f"{slot}: ai_type must be 'basic' or 'adaptive', got {p.ai_type!r}")

        if p.starting_cards is not None:
            if len(p.starting_cards) != 2:
                raise ValueError(f"{slot}: starting_cards must list exactly 2 cards")
            for card_name in p.starting_cards:
                char = _parse_character(card_name, slot)
                card_demand[char] += 1

    for char, count in card_demand.items():
        if count > 3:
            raise ValueError(
                f"{char.value} is requested as a starting card by {count} players "
                f"but only 3 copies exist in the deck"
            )


def _parse_character(name: str, context: str = "") -> Character:
    key = name.strip().lower()
    if key not in _VALID_CHARACTERS:
        valid = ", ".join(c.value for c in Character)
        raise ValueError(
            f"{context + ': ' if context else ''}Unknown character {name!r}. "
            f"Valid names: {valid}"
        )
    return _VALID_CHARACTERS[key]


# ---------------------------------------------------------------------------
# Config loading / helpers
# ---------------------------------------------------------------------------

def load_sim_config(path: str | Path) -> SimConfig:
    """Parse a JSON simulation config file and return a validated SimConfig."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    raw_players = data.get("players")
    if not raw_players or not isinstance(raw_players, list):
        raise ValueError("Config must contain a non-empty 'players' list")

    # Resolve null names eagerly so the same name is used throughout the run
    name_pool = random.sample(_CPU_NAMES, min(len(raw_players), len(_CPU_NAMES)))
    name_iter = iter(name_pool)

    players: list[PlayerConfig] = []
    for raw in raw_players:
        raw_cards = raw.get("starting_cards")
        players.append(PlayerConfig(
            name=raw.get("name") or next(name_iter, f"CPU-{len(players)+1}"),
            bluff_tendency=raw.get("bluff_tendency"),         # None → random per game
            challenge_tendency=raw.get("challenge_tendency"), # None → random per game
            confidence=raw.get("confidence"),                 # None → random per game
            ai_type=raw.get("ai_type", "basic"),
            starting_cards=[c.strip() for c in raw_cards] if raw_cards else None,
        ))

    return SimConfig(
        players=players,
        games=int(data.get("games", 100)),
        seat_order=str(data.get("seat_order", "random")),
    )



SAMPLE_CONFIG = """\
{
  "games": 500,
  "seat_order": "random",
  "players": [
    {
      "name": "Honest",
      "ai_type": "basic",
      "bluff_tendency": 0,
      "challenge_tendency": 50,
      "confidence": 20,
      "starting_cards": null
    },
    {
      "name": "Balanced",
      "ai_type": "basic",
      "bluff_tendency": 50,
      "challenge_tendency": 50,
      "confidence": 50,
      "starting_cards": null
    },
    {
      "name": "Reckless",
      "ai_type": "basic",
      "bluff_tendency": 100,
      "challenge_tendency": 50,
      "confidence": 80,
      "starting_cards": null
    },
    {
      "name": "Adaptive",
      "ai_type": "adaptive",
      "bluff_tendency": 50,
      "confidence": 50,
      "starting_cards": null
    }
  ]
}
"""

# Annotated explanation printed alongside the sample
SAMPLE_CONFIG_NOTES = """
Config file notes
─────────────────
games        : number of games to simulate (integer >= 1)

seat_order   : "random" — reshuffle seating each game (fair tendency comparison)
               "fixed"  — keep seats constant (measures first-mover advantage)

players      : list of 2–6 player slots (all fields optional)
  name               : display name; omit or null for a random historical name
  ai_type            : "basic" (default) or "adaptive"
                       basic    = personality-driven random weighted selection
                       adaptive = threat-aware scoring + opponent model that learns
                                  bluff/challenge rates across games
                       note: challenge_tendency is only used by the basic AI;
                             the adaptive AI derives challenge decisions from its
                             opponent model instead
  bluff_tendency     : 0–100; omit or null for a fresh random value each game
                       controls willingness to claim characters not in hand, and
                       to bluff-block incoming actions
                       0   = never bluffs (😇 Straight-laced)
                       25  = rarely bluffs (🤔 Cautious)
                       50  = sometimes bluffs (😏 Balanced)
                       75  = often bluffs (😈 Bold)
                       100 = bluffs as freely as plays honestly (🎲 Reckless)
  challenge_tendency : 0–100; omit or null for a fresh random value each game
                       controls willingness to challenge opponents' claims
                       0   = almost never challenges (🫡 Trusting)
                       50  = challenges at a neutral rate (🧐 Skeptical)
                       100 = challenges aggressively (🔥 Paranoid)
  confidence         : 0–100; omit or null for a fresh random value each game
                       how convincing this player appears when claiming characters;
                       opponents are less likely to challenge a high-confidence player
                       0   = very unconvincing (😬 Jittery)
                       50  = neutral (🙂 Composed)
                       100 = extremely convincing (🦁 Intimidating)
  starting_cards     : ["Duke","Captain"] to fix starting hand; omit or null for random
                       Valid names: Duke, Assassin, Captain, Ambassador, Contessa
                       (max 3 players may request the same character)
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SlotStats:
    label: str                          # "A", "B", …
    name: str
    ai_type: str                        # "basic" | "adaptive"
    bluff_tendency: int | None          # None = was random per game
    challenge_tendency: int | None      # None = was random per game
    confidence: int | None              # None = was random per game
    starting_cards: list[str] | None    # None = random per game
    seat: int | None = None             # set only when seat_order = "fixed"
    wins: int = 0

    @property
    def cards_display(self) -> str:
        if self.starting_cards is None:
            return "random"
        return " + ".join(self.starting_cards)

    @property
    def tendency_display(self) -> str:
        return str(self.bluff_tendency) if self.bluff_tendency is not None else "random"

    @property
    def challenge_display(self) -> str:
        if self.ai_type == "adaptive":
            return "model"   # derived from opponent profiles, not a fixed tendency
        return str(self.challenge_tendency) if self.challenge_tendency is not None else "random"

    @property
    def confidence_display(self) -> str:
        return str(self.confidence) if self.confidence is not None else "random"


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------

def _build_deck() -> list[Card]:
    cards = [Card(character=char) for char in Character for _ in range(3)]
    random.shuffle(cards)
    return cards


def _deal_hand(deck: list[Card], specified: list[str] | None) -> list[Card]:
    """Deal a 2-card hand. If specified, pull those exact characters from the deck."""
    if specified is None:
        return [deck.pop(), deck.pop()]
    hand: list[Card] = []
    for char_name in specified:
        char = _parse_character(char_name)
        idx = next((i for i, c in enumerate(deck) if c.character == char), None)
        if idx is None:
            raise RuntimeError(
                f"Could not deal {char_name} — no copies left in deck. "
                "Check that starting_cards don't exceed 3 copies of any character."
            )
        hand.append(deck.pop(idx))
    return hand


def run_simulation(
    config: SimConfig,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[SlotStats]:
    """
    Run config.games games according to config and return per-slot win stats.

    seat_order="random"  — seat assignment reshuffled every game.
    seat_order="fixed"   — players sit in the same seat every game.
    """
    num_players = len(config.players)

    stats: list[SlotStats] = []
    for i, pc in enumerate(config.players):
        seat = i if config.seat_order == "fixed" else None
        stats.append(SlotStats(
            label=_SLOT_LABELS[i],
            name=pc.name or f"CPU-{i+1}",
            ai_type=pc.ai_type,
            bluff_tendency=pc.bluff_tendency,
            challenge_tendency=pc.challenge_tendency,
            confidence=pc.confidence,
            starting_cards=pc.starting_cards,
            seat=seat,
        ))

    ui = SilentUI()

    # Pre-create adaptive strategy objects so their profiles persist across games.
    # Keyed by slot index (not seat — seats shuffle each game, slots are stable).
    # Basic slots use None here and get a fresh AIStrategy each game as before.
    slot_adaptive: dict[int, AdaptiveAIStrategy] = {}
    for i, pc in enumerate(config.players):
        if pc.ai_type == "adaptive":
            conf = pc.confidence if pc.confidence is not None else random.randint(0, 100)
            # Create a temporary placeholder player; reset_for_game() will replace it
            placeholder = Player(player_id=i, name=stats[i].name, coins=2, is_human=False)
            slot_adaptive[i] = AdaptiveAIStrategy(
                player=placeholder,
                profiles={},
                bluff_tendency=pc.bluff_tendency if pc.bluff_tendency is not None else random.randint(0, 100),
                confidence=conf,
            )

    for game_num in range(1, config.games + 1):

        # Determine which slot sits in which seat this game
        if config.seat_order == "random":
            seat_to_slot = list(range(num_players))
            random.shuffle(seat_to_slot)
        else:
            seat_to_slot = list(range(num_players))  # slot i → seat i, always

        deck = _build_deck()

        # Fixed starting cards must be dealt first (before the deck is disturbed
        # by random deals) so that requested cards are still available.
        # Sort so that slots with specified cards go first.
        dealing_order = sorted(
            range(num_players),
            key=lambda seat: 0 if config.players[seat_to_slot[seat]].starting_cards else 1,
        )

        seat_players: dict[int, Player] = {}
        ai_players: dict[int, object] = {}
        for seat in dealing_order:
            slot_idx = seat_to_slot[seat]
            pc = config.players[slot_idx]
            tendency = pc.bluff_tendency if pc.bluff_tendency is not None else random.randint(0, 100)
            challenge = pc.challenge_tendency if pc.challenge_tendency is not None else random.randint(0, 100)
            conf = pc.confidence if pc.confidence is not None else random.randint(0, 100)
            hand = _deal_hand(deck, pc.starting_cards)
            player = Player(
                player_id=seat,
                name=stats[slot_idx].name,
                coins=2,
                hand=hand,
                is_human=False,
                confidence=conf,
            )
            seat_players[seat] = player

            if pc.ai_type == "adaptive" and slot_idx in slot_adaptive:
                slot_adaptive[slot_idx].reset_for_game(player)
                ai_players[seat] = slot_adaptive[slot_idx]
            else:
                ai_players[seat] = AIStrategy(
                    player,
                    bluff_tendency=tendency,
                    challenge_tendency=challenge,
                    confidence=conf,
                )

        players = [seat_players[seat] for seat in range(num_players)]
        state = GameState(players=players, deck=deck)
        observers = [s for s in ai_players.values() if hasattr(s, "notify")]
        engine = GameEngine(state=state, ui=ui, ai_players=ai_players, observers=observers)
        winner = engine.run()

        winner_slot_idx = seat_to_slot[winner.player_id]
        stats[winner_slot_idx].wins += 1

        if progress_callback:
            progress_callback(game_num, config.games)

    return stats
