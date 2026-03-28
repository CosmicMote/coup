# Coup 🎮

A Python CLI implementation of the tabletop bluffing game **Coup**.

---

## Setup

```bash
# Create and activate a virtual environment (Python 3.13+)
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# No external dependencies required — stdlib only
```

---

## Running the Game

```bash
python main.py                   # 4 players, no pause
python main.py --players 2       # 2-player game
python main.py --players 6       # 6-player game (maximum)
python main.py --pause           # pause 1 second after each CPU action
python main.py --pause 2.5       # pause 2.5 seconds after each CPU action
```

At startup you are prompted for each player's name. **Leave a name blank** to make that slot a CPU player. CPU players are given random names drawn from a pool of historical political schemers.

If exactly one human player is in the game, your hand is shown at the start of every turn so you can make informed decisions about whether to bluff, challenge, or block.

---

## How to Play

### Objective
Be the **last player standing**. Eliminate opponents by forcing them to reveal and lose both of their influence cards.

### Setup
- Each player starts with **2 coins** and **2 face-down character cards** (their *influence*).
- The deck contains **3 copies** of each of the 5 characters (15 cards total).
- Losing both influence cards eliminates you from the game.

---

### On Your Turn
Choose **one action** from those available to you:

| Action | Cost | Effect | Claimable character |
|---|---|---|---|
| 💰 Income | — | Take 1 coin | — |
| 🤲 Foreign Aid | — | Take 2 coins | — |
| 💥 Coup | 7 🪙 | Force a target to lose 1 influence. Cannot be blocked or challenged. | — |
| 💸 Tax | — | Take 3 coins | 👑 Duke |
| 🗡️ Assassinate | 3 🪙 | Force a target to lose 1 influence | 🗡️ Assassin |
| 🦝 Steal | — | Take up to 2 coins from a target | ⚓ Captain |
| 🔄 Exchange | — | Draw 2 cards from the deck, keep any combination totalling your current influence count, return the rest | 🤝 Ambassador |

> **Forced Coup:** If you have **10 or more coins** you *must* perform a Coup on your turn.

---

### The Bluffing System

You may **claim any character** regardless of what you actually hold. Other players can call your bluff with a **Challenge**, or prevent the action with a **Block**.

#### Challenges
Any opponent can challenge a character-based action claim (Tax, Assassinate, Steal, Exchange).

- **Challenger wins** (actor was bluffing): the actor reveals a card and loses 1 influence. The action fails.
- **Challenger loses** (actor proves the card): the challenger loses 1 influence. The actor shuffles their proved card back into the deck and draws a replacement. The action proceeds.

> A player who challenges and loses their influence **cannot also block** the same action.

#### Blocks
Certain actions can be blocked by claiming the appropriate character:

| Action being blocked | Character claimed to block |
|---|---|
| 🤲 Foreign Aid | 👑 Duke |
| 🗡️ Assassinate | 💎 Contessa |
| 🦝 Steal | ⚓ Captain or 🤝 Ambassador |

When an action is blocked, the original actor may **challenge the block**:

- **Challenge succeeds** (blocker was bluffing): the blocker loses 1 influence and the action proceeds.
- **Challenge fails** (blocker proves the card): the actor loses 1 influence and the action is blocked.

If the actor does not challenge, the block stands and the action is cancelled.

> Coins spent on Assassinate or Coup are **non-refundable** — you pay on declaration, regardless of whether the action is later blocked or fails.

---

### Characters

| Character | Action | Can Block |
|---|---|---|
| 👑 Duke | 💸 Tax — take 3 coins | 🤲 Foreign Aid |
| 🗡️ Assassin | 🗡️ Assassinate — pay 3 coins to force a target to lose 1 influence | — |
| ⚓ Captain | 🦝 Steal — take up to 2 coins from a target | 🦝 Steal |
| 🤝 Ambassador | 🔄 Exchange — swap cards with the deck | 🦝 Steal |
| 💎 Contessa | — | 🗡️ Assassinate |

---

### Turn Summary

```
1. Actor declares action (coins deducted immediately for Assassinate / Coup)
2. [Character actions only] Challenge window — any opponent may challenge
     └─ Challenged & actor bluffing  → actor loses influence, action fails
     └─ Challenged & actor proved    → challenger loses influence, action continues
3. [Blockable actions only] Block window — eligible opponent(s) may block
     └─ Blocked & actor challenges   → resolve block challenge (as above)
     └─ Blocked & actor passes       → action cancelled
4. Action resolves
```

---

### Winning
The last player with at least one influence card remaining wins. 🏆
