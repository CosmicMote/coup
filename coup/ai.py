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
    CPU strategy with configurable bluff_tendency and challenge_tendency (both 0–100).

    bluff_tendency controls two interrelated behaviours:
      - Action selection: higher tendency → more willing to claim characters
        the player does not actually hold.
      - Blocking:         higher tendency → more willing to bluff-block.

    challenge_tendency controls one behaviour:
      - Challenging:      higher tendency → more likely to challenge opponents'
        character claims.  A natural interpretation: a player who challenges
        often is naturally sceptical, regardless of how much they bluff themselves.

    The AI only uses information it would legitimately know:
      - Its own hand (unrevealed cards)
      - All revealed (face-up) cards visible to everyone
    It does NOT peek at opponents' hidden cards.
    """

    _PERSONALITY_LABELS: list[tuple[int, str]] = [
        (20, "😇 Straight-laced"),
        (40, "🤔 Cautious"),
        (60, "😏 Balanced"),
        (80, "😈 Bold"),
        (100, "🎲 Reckless"),
    ]

    def __init__(
        self,
        player: Player,
        bluff_tendency: int = 50,
        challenge_tendency: int = 50,
    ) -> None:
        self.player = player
        self.bluff_tendency = max(0, min(100, bluff_tendency))
        self.challenge_tendency = max(0, min(100, challenge_tendency))

    @property
    def personality_label(self) -> str:
        for threshold, label in self._PERSONALITY_LABELS:
            if self.bluff_tendency <= threshold:
                return label
        return self._PERSONALITY_LABELS[-1][1]

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

        # Weight actions by honesty vs. bluff tendency.
        # Honest weight (holding the card) = 4; general actions = 2.
        # Bluff weight scales linearly with bluff_tendency:
        #   tendency 0   → 0.0  (never bluff)
        #   tendency 50  → 2.0  (half as likely as honest)
        #   tendency 100 → 4.0  (just as likely as honest)
        our_chars = {c.character for c in self.player.alive_cards}
        bluff_weight = (self.bluff_tendency / 100) * 4
        weights = []
        for action in legal:
            claimed = rules.get_claimed_character(action)
            if claimed and claimed in our_chars:
                weights.append(4)
            elif claimed is None:
                weights.append(2)  # general actions are always safe
            else:
                weights.append(bluff_weight)  # bluff — scaled by tendency

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

        # Bluff-block probability scales with tendency:
        #   tendency 0   → 0%   (never bluff-block)
        #   tendency 50  → 25%
        #   tendency 100 → 50%
        bluff_block_prob = (self.bluff_tendency / 100) * 0.5
        if bluff_block_prob > 0 and random.random() < bluff_block_prob:
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

        challenge_tendency scales the base probabilities:
        scale ranges from 0.75× (tendency 0) to 1.25× (tendency 100).
        """
        our_count = sum(1 for c in self.player.alive_cards if c.character == claimed)
        revealed_count = sum(
            1 for p in state.players for c in p.hand
            if c.character == claimed and c.revealed
        )
        accounted_for = our_count + revealed_count

        if accounted_for >= 3:
            return True  # impossible — definitely a bluff

        # Base probabilities by how many copies are accounted for
        base_prob = {2: 0.55, 1: 0.20, 0: 0.08}[accounted_for]

        # Scale by challenge_tendency: 0.75 at tendency 0, 1.0 at 50, 1.25 at 100
        scale = 0.75 + (self.challenge_tendency / 200)
        return random.random() < (base_prob * scale)

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
