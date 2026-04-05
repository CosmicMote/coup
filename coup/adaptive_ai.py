from __future__ import annotations
import math
import random
from dataclasses import dataclass
from coup.constants import Action, Character, EventType
from coup.models import GameState, Player, ActionContext, Card
from coup import rules
from coup.ai import _CHAR_SCORE


# ─────────────────────────────────────────────────────────────────────────────
# Opponent profile
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OpponentProfile:
    """
    Running Bayesian model of one named opponent's behaviour.

    Uses Laplace (add-1) smoothing so rates never collapse to 0 or 1 even
    with no observations. Raw observation counts are tracked separately so
    `enough_data` can be checked without subtracting the prior.
    """
    name: str

    # Bluff tracking — updated when character claims are challenged and resolved
    _claims_honest: int = 0   # actor proved the card (CHALLENGE_LOST)
    _claims_bluff: int = 0    # actor caught bluffing (CHALLENGE_WON)

    # Challenge-rate tracking — updated from observed opportunities & decisions.
    # Prior of 8 virtual non-challenge observations gives an initial rate of
    # (0+1)/(8+2) = 0.10, which is much closer to the realistic ~10-15% than
    # the flat Laplace prior of 0.50 that zero observations would produce.
    _challenge_opps: int = 8   # challengeable actions this player witnessed
    _challenges_taken: int = 0 # how many they actually challenged

    # Block-bluff tracking — updated when block challenges resolve
    _blocks_honest: int = 0   # blocker proved the card (BLOCK_CHALLENGE_LOST)
    _blocks_bluff: int = 0    # blocker caught bluffing (BLOCK_CHALLENGE_WON)

    # ── Derived rates (all Laplace smoothed) ─────────────────────────────── #

    @property
    def bluff_rate(self) -> float:
        """Estimated P(claim is a bluff)."""
        return (self._claims_bluff + 1) / (self._claims_honest + self._claims_bluff + 2)

    @property
    def challenge_rate(self) -> float:
        """Estimated P(challenges when given the opportunity)."""
        return (self._challenges_taken + 1) / (self._challenge_opps + 2)

    @property
    def block_bluff_rate(self) -> float:
        """Estimated P(block is a bluff)."""
        return (self._blocks_bluff + 1) / (self._blocks_honest + self._blocks_bluff + 2)

    @property
    def bluff_observations(self) -> int:
        """Raw count of resolved challenge outcomes (excludes prior)."""
        return self._claims_honest + self._claims_bluff

    @property
    def enough_data(self) -> bool:
        """True once at least 3 challenge resolutions have been observed."""
        return self.bluff_observations >= 3


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive strategy
# ─────────────────────────────────────────────────────────────────────────────

class AdaptiveAIStrategy:
    """
    A strategy that combines two improvements over the baseline AIStrategy:

    1. Opponent modelling — builds a per-opponent statistical profile from game
       events observed via notify().  Profiles persist across multiple games when
       the strategy object is reused with reset_for_game(), enabling genuine
       cross-game learning in simulation mode.

    2. Threat-aware decisions — scores every legal action by strategic value
       (threat level of targets, near-coup denial, elimination priority) rather
       than random weighted sampling.  Challenge and block decisions use the
       opponent model instead of a fixed tendency dial.
    """

    def __init__(
        self,
        player: Player,
        profiles: dict[str, OpponentProfile] | None = None,
        bluff_tendency: int = 50,
        confidence: int = 50,
    ) -> None:
        self.player = player
        # Profiles are shared by reference — pass the same dict across strategy
        # instances in a simulation to let all players build on one shared model,
        # or pass separate dicts for fully independent models.
        self.profiles: dict[str, OpponentProfile] = profiles if profiles is not None else {}
        self.bluff_tendency = max(0, min(100, bluff_tendency))
        self.confidence = max(0, min(100, confidence))

    def reset_for_game(self, player: Player) -> None:
        """
        Update the player reference for a new game while preserving profiles.

        Call this at the start of each game in simulation mode so the strategy
        does not hold a stale reference to a Player from the previous game.
        Accumulated opponent knowledge is intentionally kept intact.
        """
        self.player = player

    # ── Observer interface ────────────────────────────────────────────────── #

    def notify(self, event_type: EventType, **kwargs) -> None:
        """
        Called by the engine after each game event.

        Updates the opponent profile for whoever was involved in the event.
        Self-observations are skipped (we model opponents, not ourselves).
        """
        ctx: ActionContext | None = kwargs.get("ctx")
        state: GameState | None = kwargs.get("state")

        if event_type == EventType.ACTION_DECLARED:
            # Every living opponent of the actor had an opportunity to challenge
            if ctx and state and rules.is_challengeable(ctx.action):
                for p in state.active_players:
                    if p.player_id != ctx.actor.player_id and p.name != self.player.name:
                        self._profile(p.name)._challenge_opps += 1

        elif event_type == EventType.CHALLENGE_ISSUED:
            # The challenger exercised their challenge opportunity
            if ctx and ctx.challenger and ctx.challenger.name != self.player.name:
                self._profile(ctx.challenger.name)._challenges_taken += 1

        elif event_type == EventType.CHALLENGE_LOST:
            # Actor proved the card — their claim was genuine
            if ctx and ctx.actor.name != self.player.name:
                self._profile(ctx.actor.name)._claims_honest += 1

        elif event_type == EventType.CHALLENGE_WON:
            # Actor was caught bluffing
            if ctx and ctx.actor.name != self.player.name:
                self._profile(ctx.actor.name)._claims_bluff += 1

        elif event_type == EventType.BLOCK_CHALLENGE_LOST:
            # Blocker proved the card — their block was genuine
            if ctx and ctx.blocker and ctx.blocker.name != self.player.name:
                self._profile(ctx.blocker.name)._blocks_honest += 1

        elif event_type == EventType.BLOCK_CHALLENGE_WON:
            # Blocker was caught bluffing
            if ctx and ctx.blocker and ctx.blocker.name != self.player.name:
                self._profile(ctx.blocker.name)._blocks_bluff += 1

    def _profile(self, name: str) -> OpponentProfile:
        if name not in self.profiles:
            self.profiles[name] = OpponentProfile(name=name)
        return self.profiles[name]

    # ── Action selection ──────────────────────────────────────────────────── #

    def choose_action(self, state: GameState) -> tuple[Action, Player | None]:
        legal = rules.legal_actions(self.player)

        # Forced coup
        if legal == [Action.COUP]:
            return Action.COUP, self._best_coup_target(state)

        # Strong coup preference at 7+ coins (mirrors base AI to avoid regression
        # on the most critical late-game branch)
        if Action.COUP in legal and self.player.coins >= 7:
            if random.random() < 0.85:
                return Action.COUP, self._best_coup_target(state)

        # Score every legal action then select via softmax.
        # Pure argmax would always pick the same action in the same state,
        # concentrating all bluffing on the single highest-value bluff action
        # (usually Tax) and making the AI highly predictable.  Softmax strongly
        # favours higher-scoring actions while preserving enough randomness that
        # opponents cannot trivially exploit the pattern.
        # Temperature = 1.0: meaningful spread; lower → more deterministic.
        _TEMPERATURE = 1.0

        scored: list[tuple[Action, Player | None, float]] = []
        for action in legal:
            target = self._best_target_for(state, action)
            score = self._score_action(action, target, state)
            scored.append((action, target, score))

        max_score = max(s for _, _, s in scored)
        weights = [math.exp((s - max_score) / _TEMPERATURE) for _, _, s in scored]
        (best_action, best_target, _) = random.choices(scored, weights=weights)[0]
        return best_action, best_target

    def _score_action(
        self, action: Action, target: Player | None, state: GameState
    ) -> float:
        """Strategic value score for taking this action against this target."""
        our_chars = {c.character for c in self.player.alive_cards}

        if action == Action.INCOME:
            return 1.0

        if action == Action.FOREIGN_AID:
            # 2 coins but blockable — discount by estimated block likelihood
            return 1.6 * (1.0 - self._avg_block_threat(state))

        if action == Action.COUP:
            # No bluff possible; pure strategic value
            return 9.0 + self._elimination_bonus(target)

        if action == Action.TAX:
            base = 3.0
            if Character.DUKE not in our_chars:
                base *= self._bluff_scale(state)
            return base

        if action == Action.ASSASSINATE:
            if target is None:
                return 0.0
            base = 6.5 + self._elimination_bonus(target)
            if Character.ASSASSIN not in our_chars:
                base *= self._bluff_scale(state)
            # Spending 3 coins may leave us cash-starved
            if self.player.coins - 3 < 4:
                base -= 1.5
            return base

        if action == Action.STEAL:
            if target is None:
                return 0.0
            stolen = min(2, target.coins)
            base = stolen * 1.4
            # Denying a near-coup opponent is worth extra
            if target.coins >= 7:
                base += 3.0
            elif target.coins >= 5:
                base += 1.2
            if Character.CAPTAIN not in our_chars and Character.AMBASSADOR not in our_chars:
                base *= self._bluff_scale(state)
            return base

        if action == Action.EXCHANGE:
            # Modest value; higher when our hand scores poorly
            hand_score = sum(_CHAR_SCORE.get(c.character, 0) for c in self.player.alive_cards)
            base = 1.5 + max(0.0, (8.0 - hand_score) * 0.25)
            if Character.AMBASSADOR not in our_chars:
                base *= self._bluff_scale(state)
            return base

        return 0.0

    def _elimination_bonus(self, target: Player | None) -> float:
        """Extra score for targeting a dangerous or near-dead opponent."""
        if target is None:
            return 0.0
        bonus = 0.0
        if target.influence_count == 1:
            bonus += 4.0  # eliminates them
        if target.coins >= 7:
            bonus += 2.5  # removes an imminent coup threat
        elif target.coins >= 5:
            bonus += 1.0
        return bonus

    def _bluff_scale(self, state: GameState) -> float:
        """
        Discount applied when we'd be bluffing an action.
        Combines our own willingness to bluff with the joint probability of
        surviving unchallenged by all living opponents.

        The key correction vs. the naive formula: in an N-player game each
        opponent independently decides whether to challenge, so the survival
        probability is (1 - per_opponent_rate)^N, not 1 - rate.  With 4
        opponents at 10% each the real catch probability is 34%, not 10%.
        """
        avg_challenge = self._avg_challenge_rate(state)
        num_opponents = sum(
            1 for p in state.active_players if p.player_id != self.player.player_id
        )
        tendency_scale = self.bluff_tendency / 100.0
        # Joint probability that no opponent challenges
        safety_scale = (1.0 - avg_challenge) ** num_opponents
        return tendency_scale * safety_scale

    def _avg_challenge_rate(self, state: GameState) -> float:
        """Average estimated challenge rate across living opponents.

        For opponents not yet in the profile dict we use the same informative
        prior as OpponentProfile itself: (0+1)/(8+2) = 0.10.  Using a higher
        fallback (e.g. 0.30) would make bluff_scale far too conservative early
        in a simulation run before profiles are built up.
        """
        _PRIOR_CHALLENGE_RATE = 1 / 10  # matches OpponentProfile's _challenge_opps=8 prior
        opponents = [p for p in state.active_players if p.player_id != self.player.player_id]
        if not opponents:
            return _PRIOR_CHALLENGE_RATE
        rates = [
            self.profiles[p.name].challenge_rate if p.name in self.profiles
            else _PRIOR_CHALLENGE_RATE
            for p in opponents
        ]
        return sum(rates) / len(rates)

    def _avg_block_threat(self, state: GameState) -> float:
        """
        Probability that at least one opponent blocks Foreign Aid (via Duke or bluff).

        Uses card accounting to estimate how many Dukes are in opponent hands
        rather than a fixed prior.  In a 5-player game with 3 Dukes unaccounted
        for, the true block probability is ~90%+, not 25%.
        """
        opponents = [p for p in state.active_players if p.player_id != self.player.player_id]
        if not opponents:
            return 0.0

        our_dukes = sum(1 for c in self.player.alive_cards if c.character == Character.DUKE)
        revealed_dukes = sum(
            1 for p in state.players for c in p.hand
            if c.character == Character.DUKE and c.revealed
        )
        unaccounted_dukes = 3 - our_dukes - revealed_dukes

        if unaccounted_dukes <= 0:
            # No Dukes unaccounted for — only bluff-blocks possible
            bluff_block_per_opp = 0.15
            return 1.0 - (1.0 - bluff_block_per_opp) ** len(opponents)

        # Treat each hidden card as an independent draw from the unseen pool.
        # This is an approximation (cards are dealt without replacement) but
        # gives a good estimate without full hypergeometric computation.
        hidden_total = sum(p.influence_count for p in opponents) + len(state.deck)
        if hidden_total == 0:
            return 0.0

        duke_density = unaccounted_dukes / hidden_total
        opponent_cards = sum(p.influence_count for p in opponents)
        # P(no opponent holds any Duke)
        p_no_duke = (1.0 - duke_density) ** opponent_cards

        # Also account for bluff-blocks by players without a Duke
        bluff_block_per_opp = 0.15
        p_no_bluff_block = (1.0 - bluff_block_per_opp) ** len(opponents)

        return 1.0 - (p_no_duke * p_no_bluff_block)

    # ── Target selection ──────────────────────────────────────────────────── #

    def _best_target_for(self, state: GameState, action: Action) -> Player | None:
        if not rules.requires_target(action):
            return None
        opponents = [p for p in state.active_players if p.player_id != self.player.player_id]
        if not opponents:
            return None
        if action == Action.STEAL:
            return max(opponents, key=lambda p: p.coins)
        # COUP and ASSASSINATE: highest threat
        return max(opponents, key=self._threat_score)

    def _best_coup_target(self, state: GameState) -> Player | None:
        opponents = [p for p in state.active_players if p.player_id != self.player.player_id]
        if not opponents:
            return None
        return max(opponents, key=self._threat_score)

    def _threat_score(self, player: Player) -> float:
        """How dangerous is this player? Higher = higher priority target."""
        score = player.influence_count * 3.0 + player.coins * 0.5
        if player.coins >= 7:
            score += 4.0   # can coup on their next turn
        elif player.coins >= 5:
            score += 1.5   # two steps away from coup
        # Known bluffers are harder to read and thus slightly more dangerous
        profile = self.profiles.get(player.name)
        if profile and profile.enough_data:
            score += profile.bluff_rate * 1.5
        return score

    # ── Block decision ────────────────────────────────────────────────────── #

    def choose_block(self, state: GameState, ctx: ActionContext) -> Character | None:
        blocking_chars = rules.BLOCKABLE_BY.get(ctx.action, [])
        if not blocking_chars:
            return None

        our_chars = [c.character for c in self.player.alive_cards]

        # Always block with a card we genuinely hold
        for char in blocking_chars:
            if char in our_chars:
                return char

        # Bluff-block: evaluate expected value
        harm = _action_harm(ctx.action, self.player)

        # Estimate how likely the actor is to challenge our block
        profile = self.profiles.get(ctx.actor.name)
        if profile and profile.bluff_observations >= 2:
            # Use their observed challenge rate as a proxy
            challenge_risk = profile.challenge_rate
        else:
            challenge_risk = 0.35  # moderate prior

        # Be considerably more conservative on last influence
        if self.player.influence_count == 1:
            challenge_risk = min(0.99, challenge_risk * 1.5)

        # EV = save the harm with prob (1 - cr) minus lose an influence with prob cr
        ev = harm * (1.0 - challenge_risk) - 1.0 * challenge_risk

        # Higher bluff_tendency tolerates slightly negative EV bluff-blocks
        ev_threshold = -(self.bluff_tendency / 100.0) * 0.3

        if ev > ev_threshold:
            return random.choice(blocking_chars)
        return None

    # ── Challenge decision ────────────────────────────────────────────────── #

    def choose_challenge(
        self, state: GameState, ctx: ActionContext, is_block_challenge: bool
    ) -> bool:
        if is_block_challenge:
            if ctx.block_claimed_character is None or ctx.blocker is None:
                return False
            return self._should_challenge(state, ctx.block_claimed_character, ctx.blocker)
        else:
            if ctx.claimed_character is None:
                return False
            return self._should_challenge(state, ctx.claimed_character, ctx.actor)

    def _should_challenge(
        self, state: GameState, claimed: Character, claimant: Player
    ) -> bool:
        # Card accounting: how many copies are already accounted for?
        our_count = sum(1 for c in self.player.alive_cards if c.character == claimed)
        revealed_count = sum(
            1 for p in state.players for c in p.hand
            if c.character == claimed and c.revealed
        )
        accounted_for = our_count + revealed_count

        if accounted_for >= 3:
            return True  # mathematically impossible claim

        # Base probability from card accounting alone
        base_prob = {2: 0.55, 1: 0.20, 0: 0.08}[accounted_for]

        # Only boost the challenge probability when the opponent model clearly
        # identifies this player as a heavier bluffer than the card-accounting
        # baseline.  A low cap (0.25) prevents the model from driving challenges
        # much above the basic AI's rate — important because the bluff_rate
        # estimate comes only from *challenged* claims (selection bias) and
        # challenging when P(bluff) < 0.5 is EV-negative.
        profile = self.profiles.get(claimant.name)
        if profile and profile.enough_data and profile.bluff_rate > base_prob + 0.15:
            weight = min(0.25, profile.bluff_observations / 20.0)
            p_bluff = (1.0 - weight) * base_prob + weight * profile.bluff_rate
        else:
            p_bluff = base_prob

        # Scale by the claimant's confidence (same formula as AIStrategy)
        confidence_scale = 1.25 - (claimant.confidence / 200.0)
        p_bluff *= confidence_scale

        # Be more conservative when on our last influence
        if self.player.influence_count == 1:
            p_bluff *= 0.7

        return random.random() < p_bluff

    # ── Influence sacrifice ───────────────────────────────────────────────── #

    def choose_card_to_lose(self, state: GameState, reason: str) -> Card:
        alive = self.player.alive_cards
        if len(alive) == 1:
            return alive[0]
        # Sacrifice the card with the lowest strategic value
        return min(alive, key=lambda c: _CHAR_SCORE.get(c.character, 0))

    # ── Ambassador exchange ───────────────────────────────────────────────── #

    def choose_exchange_cards(
        self, state: GameState, all_cards: list[Card], keep_count: int
    ) -> list[Card]:
        """Keep the highest-scoring cards."""
        scored = sorted(all_cards, key=lambda c: _CHAR_SCORE.get(c.character, 0), reverse=True)
        return scored[:keep_count]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _action_harm(action: Action, player: Player) -> float:
    """
    Estimate the harm of an action to the given player, in influence-equivalents.
    Used to decide whether a bluff-block is worth the risk.
    """
    if action in (Action.ASSASSINATE, Action.COUP):
        return 2.0  # losing an influence is very serious
    if action == Action.STEAL:
        stolen = min(2, player.coins)
        # Coin loss + strategic harm of being denied coup resources
        return 0.4 + stolen * 0.35
    if action == Action.FOREIGN_AID:
        return 0.4  # opponent gains 2 coins; indirect harm
    return 0.2
