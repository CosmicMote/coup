from __future__ import annotations
from typing import Protocol, runtime_checkable
from coup.constants import Action, Character, EventType
from coup.models import Card, Player, ActionContext, GameState


@runtime_checkable
class UIProtocol(Protocol):
    """
    Interface between the game engine and any UI implementation.

    The engine calls these methods to request decisions and report events.
    The UI never holds a reference to the engine — information is one-directional.

    For CPU-controlled players the engine routes to AIStrategy instead of
    calling these methods, so every method here is only ever invoked for
    human players (except notify, which is always called).
    """

    def setup_players(self, num_players: int) -> list[tuple[str, bool]]:
        """
        Called once before the game starts.
        Returns a list of (name, is_human) tuples, one per player slot.
        """
        ...

    def choose_action(self, state: GameState, player: Player) -> Action:
        """Human player selects their action for the turn."""
        ...

    def choose_target(
        self, state: GameState, player: Player, action: Action
    ) -> Player:
        """Human player selects a target for COUP / ASSASSINATE / STEAL."""
        ...

    def choose_block(
        self,
        state: GameState,
        potential_blocker: Player,
        ctx: ActionContext,
    ) -> Character | None:
        """
        Ask a human player whether they want to block the current action.
        Returns the Character they claim in order to block, or None to pass.
        """
        ...

    def choose_challenge_action(
        self,
        state: GameState,
        potential_challenger: Player,
        ctx: ActionContext,
    ) -> bool:
        """
        Ask a human player whether they want to challenge.
        Used both for challenging an action and for the actor challenging a block
        (the engine distinguishes via ctx: if ctx.blocker is set it is a block challenge).
        Returns True to challenge.
        """
        ...

    def choose_card_to_lose(
        self, state: GameState, player: Player, reason: str
    ) -> Card:
        """
        Ask a human player which of their unrevealed cards to sacrifice.
        Called when a player must lose an influence.
        """
        ...

    def choose_exchange_cards(
        self,
        state: GameState,
        player: Player,
        all_cards: list[Card],
    ) -> list[Card]:
        """
        Ambassador exchange: player sees their alive cards plus two drawn cards
        (all_cards) and returns exactly player.influence_count cards to keep.
        """
        ...

    def notify(self, event: EventType, **kwargs) -> None:
        """
        Fire-and-forget event notification.  The UI decides what to display.

        Common kwargs by event type:
          TURN_START:            player, state
          ACTION_DECLARED:       ctx, state
          CHALLENGE_ISSUED:      ctx, state
          CHALLENGE_WON:         ctx, state
          CHALLENGE_LOST:        ctx, player_proved, proved_card, state
          BLOCK_DECLARED:        ctx, state
          BLOCK_CHALLENGE_ISSUED: ctx, state
          BLOCK_CHALLENGE_WON:   ctx, state
          BLOCK_CHALLENGE_LOST:  ctx, player_proved, proved_card, state
          INFLUENCE_LOST:        player, card, reason, state
          PLAYER_ELIMINATED:     player, state
          ACTION_EXECUTED:       ctx, state
          ACTION_BLOCKED:        ctx, state
          ACTION_FAILED:         ctx, state
          GAME_OVER:             winner, state
        """
        ...
