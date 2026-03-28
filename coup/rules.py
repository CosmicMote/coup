from __future__ import annotations
from coup.constants import Action, Character


# Which character a player must claim to perform each action (None = no claim needed)
ACTION_CHARACTER: dict[Action, Character | None] = {
    Action.INCOME:     None,
    Action.FOREIGN_AID: None,
    Action.COUP:       None,
    Action.TAX:        Character.DUKE,
    Action.ASSASSINATE: Character.ASSASSIN,
    Action.STEAL:      Character.CAPTAIN,
    Action.EXCHANGE:   Character.AMBASSADOR,
}

# Actions that can be challenged (actor must prove their claimed character)
CHALLENGEABLE_ACTIONS: set[Action] = {
    Action.TAX,
    Action.ASSASSINATE,
    Action.STEAL,
    Action.EXCHANGE,
}

# Actions that can be blocked, mapped to characters that can block them
BLOCKABLE_BY: dict[Action, list[Character]] = {
    Action.FOREIGN_AID: [Character.DUKE],
    Action.ASSASSINATE: [Character.CONTESSA],
    Action.STEAL:       [Character.CAPTAIN, Character.AMBASSADOR],
}

# Coin cost to perform the action (deducted at declaration time)
ACTION_COST: dict[Action, int] = {
    Action.ASSASSINATE: 3,
    Action.COUP:        7,
}

# Actions that require choosing a living opponent as a target
TARGETED_ACTIONS: set[Action] = {
    Action.COUP,
    Action.ASSASSINATE,
    Action.STEAL,
}

# For STEAL and ASSASSINATE, only the target may block.
# For FOREIGN_AID, any opponent may block.
BLOCK_RESTRICTED_TO_TARGET: set[Action] = {
    Action.ASSASSINATE,
    Action.STEAL,
}


def is_challengeable(action: Action) -> bool:
    return action in CHALLENGEABLE_ACTIONS


def is_blockable(action: Action) -> bool:
    return action in BLOCKABLE_BY


def can_block_with(action: Action, character: Character) -> bool:
    return character in BLOCKABLE_BY.get(action, [])


def action_cost(action: Action) -> int:
    return ACTION_COST.get(action, 0)


def requires_target(action: Action) -> bool:
    return action in TARGETED_ACTIONS


def get_claimed_character(action: Action) -> Character | None:
    return ACTION_CHARACTER.get(action)


def legal_actions(player: Player) -> list[Action]:  # type: ignore[name-defined]
    """Return all actions the player may legally declare this turn."""
    from coup.models import Player  # local import to avoid circular
    if player.coins >= 10:
        # Forced coup
        return [Action.COUP]

    actions: list[Action] = [
        Action.INCOME,
        Action.FOREIGN_AID,
        Action.TAX,
        Action.EXCHANGE,
        Action.STEAL,
    ]

    if player.coins >= 3:
        actions.append(Action.ASSASSINATE)

    if player.coins >= 7:
        actions.append(Action.COUP)

    return actions
