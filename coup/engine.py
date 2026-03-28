from __future__ import annotations
import random
from coup.constants import Action, Character, EventType
from coup.models import GameState, ActionContext, Player, Card
from coup.ui.base import UIProtocol
from coup import rules


class GameEngine:
    def __init__(
        self,
        state: GameState,
        ui: UIProtocol,
        ai_players: dict[int, object],  # player_id -> AIStrategy
    ) -> None:
        self.state = state
        self.ui = ui
        self.ai_players = ai_players

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self) -> Player:
        """Drive the game to completion. Returns the winning Player."""
        while len(self.state.active_players) > 1:
            current = self.state.current_player
            self.ui.notify(EventType.TURN_START, player=current, state=self.state)
            self._run_turn()
            if len(self.state.active_players) > 1:
                self._advance_turn()

        winner = self.state.active_players[0]
        self.ui.notify(EventType.GAME_OVER, winner=winner, state=self.state)
        return winner

    # ------------------------------------------------------------------ #
    #  Turn execution                                                      #
    # ------------------------------------------------------------------ #

    def _run_turn(self) -> None:
        actor = self.state.current_player

        # Step 1: Declare action (deducts cost immediately)
        ctx = self._declare_action(actor)

        # COUP and INCOME skip challenge/block windows entirely
        if ctx.action in (Action.COUP, Action.INCOME):
            self._apply_action(ctx)
            return

        # Step 2: Challenge window (character-based actions only)
        if rules.is_challengeable(ctx.action):
            if self._open_challenge_window(ctx):
                actor_proved = self._resolve_challenge(ctx)
                if not actor_proved:
                    self.ui.notify(EventType.ACTION_FAILED, ctx=ctx, state=self.state)
                    return
                # Actor proved — challenger already lost influence; action continues

        # Step 3: Block window
        if rules.is_blockable(ctx.action):
            if self._open_block_window(ctx):
                self.ui.notify(EventType.BLOCK_DECLARED, ctx=ctx, state=self.state)
                if self._actor_challenge_block(ctx):
                    blocker_proved = self._resolve_block_challenge(ctx)
                    if blocker_proved:
                        # Actor lost the block challenge; action is blocked
                        self.ui.notify(EventType.ACTION_BLOCKED, ctx=ctx, state=self.state)
                        return
                    # Blocker was bluffing; block fails; action continues
                else:
                    # Actor did not challenge; block stands
                    self.ui.notify(EventType.ACTION_BLOCKED, ctx=ctx, state=self.state)
                    return

        # Step 4: Execute
        self._apply_action(ctx)

    def _advance_turn(self) -> None:
        n = len(self.state.players)
        self.state.current_player_index = (self.state.current_player_index + 1) % n
        attempts = 0
        while not self.state.current_player.is_alive:
            self.state.current_player_index = (self.state.current_player_index + 1) % n
            attempts += 1
            if attempts >= n:
                break  # safety guard; should not happen while active_players > 1
        self.state.turn_number += 1

    # ------------------------------------------------------------------ #
    #  Action declaration                                                  #
    # ------------------------------------------------------------------ #

    def _declare_action(self, actor: Player) -> ActionContext:
        action, target = self._get_action(actor)
        claimed_character = rules.get_claimed_character(action)

        # Deduct cost before challenge/block windows (coins are spent on declaration)
        actor.coins -= rules.action_cost(action)

        ctx = ActionContext(
            actor=actor,
            action=action,
            target=target,
            claimed_character=claimed_character,
        )
        self.ui.notify(EventType.ACTION_DECLARED, ctx=ctx, state=self.state)
        return ctx

    # ------------------------------------------------------------------ #
    #  Challenge / block windows                                           #
    # ------------------------------------------------------------------ #

    def _open_challenge_window(self, ctx: ActionContext) -> bool:
        """Poll opponents in seat order. First challenger wins. Returns True if challenged."""
        for player in self._opponents_in_order(ctx.actor):
            if self._get_challenge_response(player, ctx, is_block_challenge=False):
                ctx.challenger = player
                self.ui.notify(EventType.CHALLENGE_ISSUED, ctx=ctx, state=self.state)
                return True
        return False

    def _open_block_window(self, ctx: ActionContext) -> bool:
        """Poll eligible opponents. First blocker wins. Returns True if blocked."""
        for player in self._opponents_in_order(ctx.actor):
            # ASSASSINATE and STEAL can only be blocked by the target
            if ctx.action in rules.BLOCK_RESTRICTED_TO_TARGET and player is not ctx.target:
                continue
            block_char = self._get_block_response(player, ctx)
            if block_char is not None:
                ctx.blocker = player
                ctx.block_claimed_character = block_char
                return True
        return False

    def _actor_challenge_block(self, ctx: ActionContext) -> bool:
        """Ask the actor whether they want to challenge the declared block."""
        wants_challenge = self._get_challenge_response(ctx.actor, ctx, is_block_challenge=True)
        if wants_challenge:
            ctx.block_challenger = ctx.actor
            self.ui.notify(EventType.BLOCK_CHALLENGE_ISSUED, ctx=ctx, state=self.state)
        return wants_challenge

    # ------------------------------------------------------------------ #
    #  Challenge resolution                                                #
    # ------------------------------------------------------------------ #

    def _resolve_challenge(self, ctx: ActionContext) -> bool:
        """
        Resolve a challenge against the actor's claimed character.
        Returns True if the actor proved their card (challenger loses influence).
        Returns False if the actor was bluffing (actor loses influence).
        """
        actor = ctx.actor
        claimed = ctx.claimed_character
        matching = [c for c in actor.alive_cards if c.character == claimed]

        if matching:
            # Actor proves it: reveal the card, shuffle back, draw a replacement
            proved_card = matching[0]
            self.ui.notify(
                EventType.CHALLENGE_LOST,
                ctx=ctx,
                player_proved=actor,
                proved_card=proved_card,
                state=self.state,
            )
            self._replace_proved_card(actor, proved_card)
            self._lose_influence(ctx.challenger, "lost challenge")
            return True
        else:
            self.ui.notify(EventType.CHALLENGE_WON, ctx=ctx, state=self.state)
            self._lose_influence(actor, "caught bluffing")
            return False

    def _resolve_block_challenge(self, ctx: ActionContext) -> bool:
        """
        Resolve a challenge against the blocker's claimed block character.
        Returns True if the blocker proved their card (block stands; actor loses influence).
        Returns False if the blocker was bluffing (block fails; action proceeds).
        """
        blocker = ctx.blocker
        claimed = ctx.block_claimed_character
        matching = [c for c in blocker.alive_cards if c.character == claimed]

        if matching:
            proved_card = matching[0]
            self.ui.notify(
                EventType.BLOCK_CHALLENGE_LOST,
                ctx=ctx,
                player_proved=blocker,
                proved_card=proved_card,
                state=self.state,
            )
            self._replace_proved_card(blocker, proved_card)
            self._lose_influence(ctx.actor, "lost block challenge")
            return True
        else:
            self.ui.notify(EventType.BLOCK_CHALLENGE_WON, ctx=ctx, state=self.state)
            self._lose_influence(blocker, "caught bluffing on block")
            return False

    # ------------------------------------------------------------------ #
    #  Action effects                                                      #
    # ------------------------------------------------------------------ #

    def _apply_action(self, ctx: ActionContext) -> None:
        action = ctx.action
        actor = ctx.actor
        target = ctx.target

        if action == Action.INCOME:
            actor.coins += 1

        elif action == Action.FOREIGN_AID:
            actor.coins += 2

        elif action == Action.TAX:
            actor.coins += 3

        elif action == Action.STEAL:
            if target and target.is_alive:
                stolen = min(2, target.coins)
                target.coins -= stolen
                actor.coins += stolen

        elif action == Action.COUP:
            if target and target.is_alive:
                self._lose_influence(target, "targeted by Coup")

        elif action == Action.ASSASSINATE:
            if target and target.is_alive:
                self._lose_influence(target, "targeted by Assassin")

        elif action == Action.EXCHANGE:
            self._do_exchange(actor)

        self.ui.notify(EventType.ACTION_EXECUTED, ctx=ctx, state=self.state)

    def _do_exchange(self, actor: Player) -> None:
        drawn: list[Card] = []
        for _ in range(2):
            if self.state.deck:
                drawn.append(self.state.deck.pop())

        all_options = actor.alive_cards + drawn
        keep_count = actor.influence_count
        kept = self._get_exchange_cards(actor, all_options, keep_count)

        # Return unchosen cards to the deck
        for card in all_options:
            if card not in kept:
                self.state.deck.append(card)
        random.shuffle(self.state.deck)

        # Rebuild hand: keep revealed cards as-is, replace alive cards with kept
        actor.hand = [c for c in actor.hand if c.revealed] + kept

    # ------------------------------------------------------------------ #
    #  Influence management                                                #
    # ------------------------------------------------------------------ #

    def _lose_influence(self, player: Player, reason: str) -> None:
        if not player.alive_cards:
            return
        card = self._get_card_to_lose(player, reason)
        card.revealed = True
        self.ui.notify(EventType.INFLUENCE_LOST, player=player, card=card, reason=reason, state=self.state)
        if not player.is_alive:
            self.ui.notify(EventType.PLAYER_ELIMINATED, player=player, state=self.state)

    def _replace_proved_card(self, player: Player, card: Card) -> None:
        """Shuffle a proved card back into the deck and deal a replacement."""
        player.hand.remove(card)
        self.state.deck.append(card)
        random.shuffle(self.state.deck)
        if self.state.deck:
            player.hand.append(self.state.deck.pop())

    # ------------------------------------------------------------------ #
    #  Routing helpers (human vs. CPU)                                     #
    # ------------------------------------------------------------------ #

    def _get_action(self, actor: Player) -> tuple[Action, Player | None]:
        if actor.is_human:
            action = self.ui.choose_action(self.state, actor)
            target = None
            if rules.requires_target(action):
                target = self.ui.choose_target(self.state, actor, action)
            return action, target
        else:
            ai = self.ai_players[actor.player_id]
            return ai.choose_action(self.state)  # type: ignore[union-attr]

    def _get_challenge_response(
        self, player: Player, ctx: ActionContext, is_block_challenge: bool
    ) -> bool:
        if player.is_human:
            return self.ui.choose_challenge_action(self.state, player, ctx)
        else:
            ai = self.ai_players[player.player_id]
            return ai.choose_challenge(self.state, ctx, is_block_challenge)  # type: ignore[union-attr]

    def _get_block_response(self, player: Player, ctx: ActionContext) -> Character | None:
        if player.is_human:
            return self.ui.choose_block(self.state, player, ctx)
        else:
            ai = self.ai_players[player.player_id]
            return ai.choose_block(self.state, ctx)  # type: ignore[union-attr]

    def _get_card_to_lose(self, player: Player, reason: str) -> Card:
        alive = player.alive_cards
        if len(alive) == 1:
            return alive[0]
        if player.is_human:
            return self.ui.choose_card_to_lose(self.state, player, reason)
        else:
            ai = self.ai_players[player.player_id]
            return ai.choose_card_to_lose(self.state, reason)  # type: ignore[union-attr]

    def _get_exchange_cards(
        self, actor: Player, all_cards: list[Card], keep_count: int
    ) -> list[Card]:
        if actor.is_human:
            return self.ui.choose_exchange_cards(self.state, actor, all_cards)
        else:
            ai = self.ai_players[actor.player_id]
            return ai.choose_exchange_cards(self.state, all_cards, keep_count)  # type: ignore[union-attr]

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    def _opponents_in_order(self, actor: Player) -> list[Player]:
        """Living opponents in seat order starting from the player left of actor."""
        players = self.state.players
        n = len(players)
        actor_idx = players.index(actor)
        result = []
        for i in range(1, n):
            p = players[(actor_idx + i) % n]
            if p.is_alive:
                result.append(p)
        return result
