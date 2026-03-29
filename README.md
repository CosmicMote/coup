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

At startup you are prompted for each player's name. **Leave a name blank** to make that slot a CPU player. CPU players are given random names drawn from a pool of historical political schemers, and each is assigned a random **bluff tendency** (see [CPU Personalities](#cpu-personalities) below).

If exactly one human player is in the game, your hand is shown at the start of every turn so you can make informed decisions about whether to bluff, challenge, or block.

---

## Simulation Mode

Simulation mode runs many CPU-only games automatically to measure which bluff tendency performs best. All human interaction is suppressed and results are reported as win counts and percentages.

```bash
python main.py --simulate                                      # default: 5 players (tendencies 0 25 50 75 100), 100 games
python main.py --simulate --games 1000                         # 1 000 games with default tendencies
python main.py --simulate --tendencies 0 50 100               # 3 players, 100 games
python main.py --simulate --tendencies 0 25 50 75 100 --games 2000
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--simulate` | — | Enable simulation mode |
| `--tendencies T [T ...]` | `0 25 50 75 100` | Bluff tendency for each CPU player (2–6 values, 0–100 each) |
| `--games N` | `100` | Number of games to simulate |

### How it works

- Each value passed to `--tendencies` defines one CPU player. The number of values determines the player count.
- Player **seating order is reshuffled every game** so that going-first advantage does not skew the results.
- Progress is printed at every 10% increment with a visual progress bar.
- The final report lists each player's win count and win percentage, sorted from most to fewest wins.

### Example output

```
  Running 2,000 simulations with 5 players...
  Tendencies: [0, 25, 50, 75, 100]

  [ 200/2000]   10.0%  ▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░
  [ 400/2000]   20.0%  ▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░
  ...
  [2000/2000]  100.0%  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

  Simulation complete — 2,000 games

  ──────────────────────────────────────────────────────────
  Slot   Tendency  Personality             Wins   Win %
  ──────────────────────────────────────────────────────────
  A             0  😇 Straight-laced       1090   54.5%
  B            25  🤔 Cautious              412   20.6%
  C            50  😏 Balanced              240   12.0%
  D            75  😈 Bold                  146    7.3%
  E           100  🎲 Reckless              112    5.6%
  ──────────────────────────────────────────────────────────
```

You can use duplicate tendency values to test multiple agents with the same style:

```bash
python main.py --simulate --tendencies 0 0 50 50 100 100 --games 500
```

---

## CPU Personalities

Each CPU player is assigned a random **bluff tendency** (0–100) at the start of a game. This single value shapes their entire play style:

| Tendency | Personality | Action bluffs | Bluff-blocks | Challenge rate |
|---|---|---|---|---|
| 0–20 | 😇 Straight-laced | Never | Never | Lower |
| 21–40 | 🤔 Cautious | Rarely | Rarely | Slightly lower |
| 41–60 | 😏 Balanced | Sometimes | Sometimes | Neutral |
| 61–80 | 😈 Bold | Often | Often | Slightly higher |
| 81–100 | 🎲 Reckless | Frequently | Frequently | Higher |

Specifically:
- **Action weight for bluffs** scales from `0` (tendency 0, never bluff) to `4` (tendency 100, equally weighted with honest plays).
- **Bluff-block probability** scales from `0%` to `50%`.
- **Challenge probability** is scaled by `0.75×` at tendency 0 up to `1.25×` at tendency 100 — a reckless bluffer assumes opponents bluff freely too.

CPU personalities are announced before the first turn so you can size up your opponents.

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
