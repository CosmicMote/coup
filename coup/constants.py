from enum import Enum, auto


class Character(Enum):
    DUKE = "Duke"
    ASSASSIN = "Assassin"
    CAPTAIN = "Captain"
    AMBASSADOR = "Ambassador"
    CONTESSA = "Contessa"


class Action(Enum):
    INCOME = "Income"
    FOREIGN_AID = "Foreign Aid"
    COUP = "Coup"
    TAX = "Tax"
    ASSASSINATE = "Assassinate"
    STEAL = "Steal"
    EXCHANGE = "Exchange"


class EventType(Enum):
    TURN_START = auto()
    ACTION_DECLARED = auto()
    CHALLENGE_ISSUED = auto()
    CHALLENGE_WON = auto()       # challenger won — actor was bluffing
    CHALLENGE_LOST = auto()      # challenger lost — actor proved their card
    BLOCK_DECLARED = auto()
    BLOCK_CHALLENGE_ISSUED = auto()
    BLOCK_CHALLENGE_WON = auto()   # actor won block challenge — blocker was bluffing
    BLOCK_CHALLENGE_LOST = auto()  # actor lost block challenge — blocker proved their card
    INFLUENCE_LOST = auto()
    PLAYER_ELIMINATED = auto()
    ACTION_EXECUTED = auto()
    ACTION_BLOCKED = auto()
    ACTION_FAILED = auto()        # action failed because actor lost a challenge
    GAME_OVER = auto()
