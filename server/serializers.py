"""
JSON serialization helpers for game objects.

All functions that serialize GameState accept a `perspective_player_id`
parameter — unrevealed cards belonging to opponents are returned with
`character: null` so the wire format never leaks hidden information.
"""
from __future__ import annotations
from typing import Any

from coup.constants import Action, Character
from coup.models import Card, Player, ActionContext, GameState


CHAR_ICON: dict[Character, str] = {
    Character.DUKE:       "👑",
    Character.ASSASSIN:   "🗡️",
    Character.CAPTAIN:    "⚓",
    Character.AMBASSADOR: "🤝",
    Character.CONTESSA:   "💎",
}

ACTION_ICON: dict[Action, str] = {
    Action.INCOME:      "💰",
    Action.FOREIGN_AID: "🤲",
    Action.TAX:         "💸",
    Action.STEAL:       "🦝",
    Action.ASSASSINATE: "🗡️",
    Action.EXCHANGE:    "🔄",
    Action.COUP:        "💥",
}


def serialize_card(card: Card, visible: bool) -> dict[str, Any]:
    """Serialize a card. `visible` controls whether the character is revealed."""
    if visible or card.revealed:
        return {
            "character": card.character.value,
            "character_icon": CHAR_ICON[card.character],
            "revealed": card.revealed,
        }
    return {
        "character": None,
        "character_icon": None,
        "revealed": False,
    }


def serialize_player(player: Player, perspective_player_id: int) -> dict[str, Any]:
    """
    Serialize a player. Own cards are always shown; opponents' unrevealed
    cards have character=null to prevent information leakage.
    """
    is_self = player.player_id == perspective_player_id
    return {
        "player_id": player.player_id,
        "name": player.name,
        "coins": player.coins,
        "is_alive": player.is_alive,
        "influence_count": player.influence_count,
        "is_human": player.is_human,
        "hand": [serialize_card(c, is_self) for c in player.hand],
    }


def serialize_state(state: GameState, perspective_player_id: int) -> dict[str, Any]:
    return {
        "turn_number": state.turn_number,
        "current_player_id": state.current_player.player_id,
        "players": [serialize_player(p, perspective_player_id) for p in state.players],
        "deck_size": len(state.deck),
    }


def serialize_ctx(ctx: ActionContext) -> dict[str, Any]:
    return {
        "actor": {"player_id": ctx.actor.player_id, "name": ctx.actor.name},
        "action": ctx.action.value,
        "action_icon": ACTION_ICON.get(ctx.action, ""),
        "target": (
            {"player_id": ctx.target.player_id, "name": ctx.target.name}
            if ctx.target else None
        ),
        "claimed_character": ctx.claimed_character.value if ctx.claimed_character else None,
        "claimed_character_icon": CHAR_ICON[ctx.claimed_character] if ctx.claimed_character else None,
        "challenger": (
            {"player_id": ctx.challenger.player_id, "name": ctx.challenger.name}
            if ctx.challenger else None
        ),
        "blocker": (
            {"player_id": ctx.blocker.player_id, "name": ctx.blocker.name}
            if ctx.blocker else None
        ),
        "block_claimed_character": (
            ctx.block_claimed_character.value if ctx.block_claimed_character else None
        ),
        "block_claimed_character_icon": (
            CHAR_ICON[ctx.block_claimed_character] if ctx.block_claimed_character else None
        ),
    }
