from __future__ import annotations
from coup.constants import Action, Character, EventType
from coup.models import Card, Player, ActionContext, GameState
from coup import rules

# Emoji per character — shown next to card names throughout the UI
_CHAR_ICON: dict[Character, str] = {
    Character.DUKE:       "👑",
    Character.ASSASSIN:   "🗡️",
    Character.CAPTAIN:    "⚓",
    Character.AMBASSADOR: "🤝",
    Character.CONTESSA:   "💎",
}

# Emoji per action — shown next to action names throughout the UI
_ACTION_ICON: dict[Action, str] = {
    Action.INCOME:      "💰",
    Action.FOREIGN_AID: "🤲",
    Action.TAX:         "💸",
    Action.STEAL:       "🦝",
    Action.ASSASSINATE: "🗡️",
    Action.EXCHANGE:    "🔄",
    Action.COUP:        "💥",
}

# Characters that can be blocked and what can block them — used in prompts
_BLOCK_CHARS_DISPLAY: dict[Action, str] = {
    Action.FOREIGN_AID: f"{_CHAR_ICON[Character.DUKE]} Duke",
    Action.ASSASSINATE: f"{_CHAR_ICON[Character.CONTESSA]} Contessa",
    Action.STEAL:       f"{_CHAR_ICON[Character.CAPTAIN]} Captain or {_CHAR_ICON[Character.AMBASSADOR]} Ambassador",
}

_SEP = "─" * 60


def _char(c: Character) -> str:
    """Return 'Icon Name' for a character."""
    return f"{_CHAR_ICON[c]} {c.value}"


def _action(a: Action) -> str:
    """Return 'Icon Name' for an action."""
    return f"{_ACTION_ICON[a]} {a.value}"


class CliUI:
    """
    Terminal-based UI.  All print() and input() calls live exclusively here.
    Satisfies UIProtocol structurally (no import of base.py needed at runtime).
    """

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def setup_players(self, num_players: int) -> list[tuple[str, bool]]:
        print(_SEP)
        print("  🎮  COUP — Player Setup")
        print(_SEP)
        configs: list[tuple[str, bool]] = []
        for i in range(1, num_players + 1):
            name = input(f"  Player {i} name (blank = CPU): ").strip()
            if name:
                is_human = True
            else:
                name = f"CPU-{i}"
                is_human = False
            configs.append((name, is_human))
        print(_SEP)
        return configs

    # ------------------------------------------------------------------ #
    #  Human decision methods                                              #
    # ------------------------------------------------------------------ #

    def choose_action(self, state: GameState, player: Player) -> Action:
        self._print_state(state, viewing_player=player)
        legal = rules.legal_actions(player)
        print(f"\n  {player.name}, choose your action:")
        for idx, action in enumerate(legal, 1):
            print(f"    {idx}. {_action(action)}")
        choice = self._prompt_index(len(legal))
        return legal[choice]

    def choose_target(self, state: GameState, player: Player, action: Action) -> Player:
        targets = [p for p in state.active_players if p is not player]
        print(f"\n  Choose a target for {_action(action)}:")
        for idx, p in enumerate(targets, 1):
            coins_str = "🪙" * p.coins if p.coins <= 10 else f"🪙×{p.coins}"
            inf_str = "❤️" * p.influence_count
            print(f"    {idx}. {p.name}  {coins_str}  {inf_str}")
        choice = self._prompt_index(len(targets))
        return targets[choice]

    def choose_block(
        self,
        state: GameState,
        potential_blocker: Player,
        ctx: ActionContext,
    ) -> Character | None:
        blocking_chars = rules.BLOCKABLE_BY.get(ctx.action, [])
        if not blocking_chars:
            return None

        chars_str = _BLOCK_CHARS_DISPLAY.get(ctx.action, "a character")
        print(
            f"\n  {potential_blocker.name}: {ctx.actor.name} is attempting "
            f"{_action(ctx.action)}. 🛡️ Block with {chars_str}?"
        )
        print("    1. 🛡️  Block")
        print("    2.    Pass")
        choice = self._prompt_index(2)
        if choice == 0:  # Block
            if len(blocking_chars) == 1:
                return blocking_chars[0]
            print("  Which character do you claim?")
            for idx, char in enumerate(blocking_chars, 1):
                print(f"    {idx}. {_char(char)}")
            char_choice = self._prompt_index(len(blocking_chars))
            return blocking_chars[char_choice]
        return None

    def choose_challenge_action(
        self,
        state: GameState,
        potential_challenger: Player,
        ctx: ActionContext,
    ) -> bool:
        if ctx.blocker is not None:
            # Actor challenging a block
            print(
                f"\n  {potential_challenger.name}: {ctx.blocker.name} claims "
                f"{_char(ctx.block_claimed_character)} to block your "  # type: ignore[union-attr]
                f"{_action(ctx.action)}. ⚔️  Challenge?"
            )
        else:
            # Opponent challenging an action
            claimed = ctx.claimed_character
            if claimed:
                print(
                    f"\n  {potential_challenger.name}: {ctx.actor.name} claims "
                    f"{_char(claimed)} for {_action(ctx.action)}. ⚔️  Challenge?"
                )
            else:
                return False

        print("    1. ⚔️  Challenge")
        print("    2.    Pass")
        choice = self._prompt_index(2)
        return choice == 0

    def choose_card_to_lose(
        self, state: GameState, player: Player, reason: str
    ) -> Card:
        alive = player.alive_cards
        if len(alive) == 1:
            return alive[0]
        print(f"\n  💀 {player.name}, you must lose an influence ({reason}).")
        print("  Choose which card to reveal:")
        for idx, card in enumerate(alive, 1):
            print(f"    {idx}. {_char(card.character)}")
        choice = self._prompt_index(len(alive))
        return alive[choice]

    def choose_exchange_cards(
        self,
        state: GameState,
        player: Player,
        all_cards: list[Card],
    ) -> list[Card]:
        keep_count = player.influence_count
        print(f"\n  🔄 {player.name}: Ambassador exchange — choose {keep_count} card(s) to keep.")
        print("  Available cards:")
        for idx, card in enumerate(all_cards, 1):
            print(f"    {idx}. {_char(card.character)}")

        kept: list[Card] = []
        chosen_indices: set[int] = set()
        for slot in range(1, keep_count + 1):
            while True:
                raw = input(f"  Keep card {slot}/{keep_count} (enter number): ").strip()
                try:
                    idx = int(raw) - 1
                    if 0 <= idx < len(all_cards) and idx not in chosen_indices:
                        chosen_indices.add(idx)
                        kept.append(all_cards[idx])
                        break
                    else:
                        print("  Invalid choice, try again.")
                except ValueError:
                    print("  Please enter a number.")
        return kept

    # ------------------------------------------------------------------ #
    #  Event notifications                                                 #
    # ------------------------------------------------------------------ #

    def notify(self, event: EventType, **kwargs) -> None:
        handlers = {
            EventType.TURN_START:             self._on_turn_start,
            EventType.ACTION_DECLARED:        self._on_action_declared,
            EventType.CHALLENGE_ISSUED:       self._on_challenge_issued,
            EventType.CHALLENGE_WON:          self._on_challenge_won,
            EventType.CHALLENGE_LOST:         self._on_challenge_lost,
            EventType.BLOCK_DECLARED:         self._on_block_declared,
            EventType.BLOCK_CHALLENGE_ISSUED: self._on_block_challenge_issued,
            EventType.BLOCK_CHALLENGE_WON:    self._on_block_challenge_won,
            EventType.BLOCK_CHALLENGE_LOST:   self._on_block_challenge_lost,
            EventType.INFLUENCE_LOST:         self._on_influence_lost,
            EventType.PLAYER_ELIMINATED:      self._on_player_eliminated,
            EventType.ACTION_EXECUTED:        self._on_action_executed,
            EventType.ACTION_BLOCKED:         self._on_action_blocked,
            EventType.ACTION_FAILED:          self._on_action_failed,
            EventType.GAME_OVER:              self._on_game_over,
        }
        handler = handlers.get(event)
        if handler:
            handler(**kwargs)

    # ------------------------------------------------------------------ #
    #  Notification handlers                                               #
    # ------------------------------------------------------------------ #

    def _on_turn_start(self, player: Player, state: GameState, **_) -> None:
        print(f"\n{_SEP}")
        coins_str = ("🪙" * player.coins) if player.coins <= 10 else f"🪙×{player.coins}"
        coins_str = coins_str or "broke"
        print(f"  🎲 Turn {state.turn_number + 1} — {player.name}'s turn  {coins_str}")
        self._print_scoreboard(state)

    def _on_action_declared(self, ctx: ActionContext, state: GameState, **_) -> None:
        actor = ctx.actor
        target_str = f" → {ctx.target.name}" if ctx.target else ""
        char_str = f" (claiming {_char(ctx.claimed_character)})" if ctx.claimed_character else ""
        print(f"  ▶  {actor.name} declares {_action(ctx.action)}{char_str}{target_str}.")

    def _on_challenge_issued(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(
            f"  ⚔️  {ctx.challenger.name} challenges {ctx.actor.name}'s "
            f"claim of {_char(ctx.claimed_character)}!"  # type: ignore[union-attr]
        )

    def _on_challenge_won(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(f"  ✅ Challenge succeeded! {ctx.actor.name} was bluffing.")

    def _on_challenge_lost(
        self, ctx: ActionContext, player_proved: Player, proved_card: Card, state: GameState, **_
    ) -> None:
        print(
            f"  😬 Challenge failed! {player_proved.name} reveals "
            f"{_char(proved_card.character)} and shuffles it back."
        )

    def _on_block_declared(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(
            f"  🛡️  {ctx.blocker.name} claims {_char(ctx.block_claimed_character)} "  # type: ignore[union-attr]
            f"to block {ctx.actor.name}'s {_action(ctx.action)}!"
        )

    def _on_block_challenge_issued(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(
            f"  ⚔️  {ctx.actor.name} challenges {ctx.blocker.name}'s "  # type: ignore[union-attr]
            f"claim of {_char(ctx.block_claimed_character)}!"  # type: ignore[union-attr]
        )

    def _on_block_challenge_won(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(f"  ✅ Block challenge succeeded! {ctx.blocker.name} was bluffing.")  # type: ignore[union-attr]

    def _on_block_challenge_lost(
        self, ctx: ActionContext, player_proved: Player, proved_card: Card, state: GameState, **_
    ) -> None:
        print(
            f"  😬 Block challenge failed! {player_proved.name} reveals "
            f"{_char(proved_card.character)} and shuffles it back."
        )

    def _on_influence_lost(
        self, player: Player, card: Card, reason: str, state: GameState, **_
    ) -> None:
        print(f"  💀 {player.name} reveals {_char(card.character)} ({reason}).")

    def _on_player_eliminated(self, player: Player, state: GameState, **_) -> None:
        print(f"  ☠️  {player.name} has been eliminated!")

    def _on_action_executed(self, ctx: ActionContext, state: GameState, **_) -> None:
        actor = ctx.actor
        action = ctx.action
        coins_str = f"🪙×{actor.coins}" if actor.coins > 10 else "🪙" * actor.coins
        if action == Action.INCOME:
            print(f"  💰 {actor.name} takes 1 coin.  ({coins_str})")
        elif action == Action.FOREIGN_AID:
            print(f"  🤲 {actor.name} takes 2 coins.  ({coins_str})")
        elif action == Action.TAX:
            print(f"  💸 {actor.name} collects tax: 3 coins.  ({coins_str})")
        elif action == Action.STEAL:
            print(f"  🦝 {actor.name} steals from {ctx.target.name}.")  # type: ignore[union-attr]
        elif action == Action.COUP:
            print(f"  💥 {actor.name} stages a Coup against {ctx.target.name}.")  # type: ignore[union-attr]
        elif action == Action.ASSASSINATE:
            print(f"  🗡️  {actor.name} assassinates {ctx.target.name}.")  # type: ignore[union-attr]
        elif action == Action.EXCHANGE:
            print(f"  🔄 {actor.name} completes an Ambassador exchange.")

    def _on_action_blocked(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(
            f"  🚫 {_action(ctx.action)} by {ctx.actor.name} was blocked by "
            f"{ctx.blocker.name}."  # type: ignore[union-attr]
        )

    def _on_action_failed(self, ctx: ActionContext, state: GameState, **_) -> None:
        print(f"  ❌ {ctx.actor.name}'s {_action(ctx.action)} failed (lost challenge).")

    def _on_game_over(self, winner: Player, state: GameState, **_) -> None:
        print(f"\n{'═' * 60}")
        print(f"  🏆  GAME OVER — {winner.name} wins!")
        print(f"{'═' * 60}\n")

    # ------------------------------------------------------------------ #
    #  Display helpers                                                     #
    # ------------------------------------------------------------------ #

    def _print_state(self, state: GameState, viewing_player: Player | None = None) -> None:
        if viewing_player:
            hand_str = "  ".join(_char(c.character) for c in viewing_player.alive_cards)
            print(f"\n  Your hand: {hand_str}")

    def _print_scoreboard(self, state: GameState) -> None:
        parts = []
        for p in state.players:
            if p.is_alive:
                coins_str = ("🪙" * p.coins) if p.coins <= 10 else f"🪙×{p.coins}"
                coins_str = coins_str or "broke"
                inf_str = "❤️" * p.influence_count
                parts.append(f"{p.name}: {coins_str} {inf_str}")
            else:
                parts.append(f"{p.name}: ☠️")
        print("  " + "  │  ".join(parts))

    def _prompt_index(self, count: int) -> int:
        """Prompt for a 1-based choice from 1..count. Returns 0-based index."""
        while True:
            raw = input(f"  Enter choice (1-{count}): ").strip()
            try:
                idx = int(raw) - 1
                if 0 <= idx < count:
                    return idx
            except ValueError:
                pass
            print(f"  Please enter a number between 1 and {count}.")
