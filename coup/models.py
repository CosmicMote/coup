from __future__ import annotations
from dataclasses import dataclass, field
from coup.constants import Character, Action


@dataclass
class Card:
    character: Character
    revealed: bool = False


@dataclass
class Player:
    player_id: int
    name: str
    coins: int = 2
    hand: list[Card] = field(default_factory=list)
    is_human: bool = False
    confidence: int = 50  # 0–100; how convincing this player appears when claiming characters

    @property
    def alive_cards(self) -> list[Card]:
        return [c for c in self.hand if not c.revealed]

    @property
    def influence_count(self) -> int:
        return len(self.alive_cards)

    @property
    def is_alive(self) -> bool:
        return self.influence_count > 0

    def __repr__(self) -> str:
        return f"Player({self.name!r}, coins={self.coins}, influence={self.influence_count})"


@dataclass
class ActionContext:
    """Carries all state for the action currently being resolved."""
    actor: Player
    action: Action
    target: Player | None = None
    claimed_character: Character | None = None
    # Challenge against the action
    challenger: Player | None = None
    # Block against the action
    blocker: Player | None = None
    block_claimed_character: Character | None = None
    # Challenge against the block
    block_challenger: Player | None = None


@dataclass
class GameState:
    players: list[Player]
    deck: list[Card]
    current_player_index: int = 0
    turn_number: int = 0

    @property
    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]
