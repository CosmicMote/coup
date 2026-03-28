from __future__ import annotations
import random
from coup.constants import Action, Character
from coup.models import GameState, Player, ActionContext, Card
from coup import rules

# Character priority scores for the Ambassador exchange
_CHAR_SCORE: dict[Character, int] = {
    Character.DUKE:       5,
    Character.CAPTAIN:    4,
    Character.ASSASSIN:   4,
    Character.AMBASSADOR: 3,
    Character.CONTESSA:   3,
}


class AIStrategy:
    """
    Default CPU strategy: legal random play with light heuristics.

    The AI only uses information it would legitimately know:
      - Its own hand (unrevealed cards)
      - All revealed (face-up) cards visible to everyone
    It does NOT peek at opponents' hidden cards.
    """

    def __init__(self, player: Player) -> None:
        self.player = player

    # ------------------------------------------------------------------ #
    #  Action selection                                                    #
    # ------------------------------------------------------------------ #

    def choose_action(self, state: GameState) -> tuple[Action, Player | None]:
        legal = rules.legal_actions(self.player)

        # Forced coup
        if legal == [Action.COUP]:
            return Action.COUP, self._pick_target(state, Action.COUP)

        # Strongly prefer Coup when affordable
        if Action.COUP in legal:
            if random.random() < 0.85:
                return Action.COUP, self._pick_target(state, Action.COUP)

        # Weight actions: prefer those that match a card we actually hold
        our_chars = {c.character for c in self.player.alive_cards}
        weights = []
        for action in legal:
            claimed = rules.get_claimed_character(action)
            if claimed and claimed in our_chars:
                weights.append(4)
            elif claimed is None:
                weights.append(2)  # general actions are always safe
            else:
                weights.append(1)  # bluff — lower weight

        action = random.choices(legal, weights=weights)[0]
        target = self._pick_target(state, action) if rules.requires_target(action) else None
        return action, target

    # ------------------------------------------------------------------ #
    #  Block decision                                                      #
    # ------------------------------------------------------------------ #

    def choose_block(self, state: GameState, ctx: ActionContext) -> Character | None:
        blocking_chars = rules.BLOCKABLE_BY.get(ctx.action, [])
        if not blocking_chars:
            return None

        our_chars = [c.character for c in self.player.alive_cards]

        # Always block with a card we genuinely hold
        for char in blocking_chars:
            if char in our_chars:
                return char

        # Occasionally bluff-block (15 % chance)
        if random.random() < 0.15:
            return random.choice(blocking_chars)

        return None

    # ------------------------------------------------------------------ #
    #  Challenge decision                                                  #
    # ------------------------------------------------------------------ #

    def choose_challenge(
        self, state: GameState, ctx: ActionContext, is_block_challenge: bool
    ) -> bool:
        if is_block_challenge:
            # Actor challenging the blocker's claim
            claimed = ctx.block_claimed_character
            if claimed is None:
                return False
            return self._should_challenge_claim(state, claimed)
        else:
            # Opponent challenging the actor's claim
            claimed = ctx.claimed_character
            if claimed is None:
                return False
            return self._should_challenge_claim(state, claimed)

    def _should_challenge_claim(self, state: GameState, claimed: Character) -> bool:
        """
        Decide whether to challenge a claim using only public/own-hand information.
        There are 3 copies of each character in the 15-card deck.
        The more copies we can account for, the more likely the claim is a bluff.
        """
        our_count = sum(1 for c in self.player.alive_cards if c.character == claimed)
        revealed_count = sum(
            1 for p in state.players for c in p.hand
            if c.character == claimed and c.revealed
        )
        accounted_for = our_count + revealed_count

        if accounted_for >= 3:
            return True           # impossible — definitely a bluff
        elif accounted_for == 2:
            return random.random() < 0.55
        elif accounted_for == 1:
            return random.random() < 0.20
        else:
            return random.random() < 0.08

    # ------------------------------------------------------------------ #
    #  Influence sacrifice                                                 #
    # ------------------------------------------------------------------ #

    def choose_card_to_lose(self, state: GameState, reason: str) -> Card:
        alive = self.player.alive_cards
        if len(alive) == 1:
            return alive[0]

        # Sacrifice the card with the lowest score (least useful to keep)
        return min(alive, key=lambda c: _CHAR_SCORE.get(c.character, 0))

    # ------------------------------------------------------------------ #
    #  Ambassador exchange                                                 #
    # ------------------------------------------------------------------ #

    def choose_exchange_cards(
        self, state: GameState, all_cards: list[Card], keep_count: int
    ) -> list[Card]:
        """Keep the highest-scoring cards."""
        scored = sorted(all_cards, key=lambda c: _CHAR_SCORE.get(c.character, 0), reverse=True)
        return scored[:keep_count]

    # ------------------------------------------------------------------ #
    #  Target selection                                                    #
    # ------------------------------------------------------------------ #

    def _pick_target(self, state: GameState, action: Action) -> Player | None:
        opponents = [p for p in state.active_players if p.player_id != self.player.player_id]
        if not opponents:
            return None

        if action == Action.STEAL:
            # Target the richest opponent (most coins to steal)
            return max(opponents, key=lambda p: p.coins)

        if action in (Action.ASSASSINATE, Action.COUP):
            # Target the most threatening opponent: most influence, then most coins
            return max(opponents, key=lambda p: (p.influence_count, p.coins))

        return random.choice(opponents)
