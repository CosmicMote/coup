"""
Game session management.

`create_session` builds a GameSession and registers it in `active_sessions`.
`start_session` attaches a live WebSocket and launches the engine thread.
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import threading
from dataclasses import dataclass, field
from typing import Literal

from fastapi import WebSocket

from coup.constants import Character
from coup.models import Card, Player, GameState
from coup.engine import GameEngine
from coup.ai import AIStrategy
from coup.adaptive_ai import AdaptiveAIStrategy
from server.ws_ui import WebSocketUI


# ── Name pool (same as CLI) ───────────────────────────────────────────── #

_CPU_NAMES: list[str] = [
    "Machiavelli", "Borgia",    "Medici",   "Richelieu", "Talleyrand",
    "Metternich",  "Bismarck",  "Cavour",   "Fouché",    "Mazarin",
    "Colbert",     "Walpole",   "Disraeli", "Metella",   "Agrippina",
    "Lucrezia",    "Sforza",    "Gonzaga",  "Visconti",  "Farnese",
    "Orsini",      "Colonna",   "Pazzi",    "Albizzi",   "Strozzi",
]


def _tendency_from_name(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest(), 16) % 100


def _challenge_tendency_from_name(name: str) -> int:
    return int(hashlib.md5((name + "_challenge").encode()).hexdigest(), 16) % 100


def _confidence_from_name(name: str) -> int:
    return int(hashlib.md5((name + "_confidence").encode()).hexdigest(), 16) % 100


def _build_deck() -> list[Card]:
    cards = [Card(character=char) for char in Character for _ in range(3)]
    random.shuffle(cards)
    return cards


# ── Session dataclass ─────────────────────────────────────────────────── #

@dataclass
class GameSession:
    game_id: str
    ws_ui: WebSocketUI
    player_configs: list[tuple[str, bool]]  # (name, is_human)
    num_players: int
    cpu_ai_type: str                         # "basic" | "adaptive"
    status: Literal["waiting", "running", "finished"] = "waiting"
    engine_thread: threading.Thread | None = None
    error: str | None = None


# Global session store — keyed by game_id.
active_sessions: dict[str, GameSession] = {}


# ── Public API ────────────────────────────────────────────────────────── #

def create_session(
    num_players: int,
    human_name: str,
    cpu_ai_type: str = "basic",
    cpu_names: list[str] | None = None,
) -> GameSession:
    """
    Build a GameSession and register it.  Does not start the engine thread —
    call start_session() once the WebSocket connection is established.
    """
    import uuid
    game_id = uuid.uuid4().hex[:12]

    # CPU names: use caller-supplied list first, then random pool.
    cpu_count = num_players - 1
    name_pool = random.sample(_CPU_NAMES, min(cpu_count, len(_CPU_NAMES)))
    resolved_cpu_names = [
        (cpu_names[i] if cpu_names and i < len(cpu_names) else name_pool[i])
        for i in range(cpu_count)
    ]

    # Human player is always slot 0.
    player_configs: list[tuple[str, bool]] = (
        [(human_name, True)] + [(n, False) for n in resolved_cpu_names]
    )

    ws_ui = WebSocketUI(player_configs=player_configs)
    session = GameSession(
        game_id=game_id,
        ws_ui=ws_ui,
        player_configs=player_configs,
        num_players=num_players,
        cpu_ai_type=cpu_ai_type,
    )
    active_sessions[game_id] = session
    return session


def attach_websocket(
    session: GameSession,
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Attach (or re-attach) the live WebSocket without starting the engine."""
    session.ws_ui.attach(websocket, loop)


def launch_engine(session: GameSession) -> None:
    """
    Start the engine background thread.

    Must be called after attach_websocket(), and only once the client has
    confirmed its WebSocket connection is stable (i.e. after receiving the
    'ready' message).  Keeping these two steps separate prevents the engine
    from starting on a WebSocket that React StrictMode is about to tear down.
    """
    session.status = "running"
    thread = threading.Thread(
        target=_run_engine,
        args=(session,),
        daemon=True,
        name=f"engine-{session.game_id}",
    )
    session.engine_thread = thread
    thread.start()


# ── Engine thread ─────────────────────────────────────────────────────── #

def _run_engine(session: GameSession) -> None:
    """
    Runs entirely in a background thread.

    Builds game state, wires up AI players, then calls engine.run().
    Any unhandled exception is caught, logged into the session, and
    reported to the client before the thread exits.
    """
    ws_ui = session.ws_ui
    loop = ws_ui.loop

    try:
        # setup_players() returns the pre-populated list synchronously.
        player_configs = ws_ui.setup_players(session.num_players)

        deck = _build_deck()
        players: list[Player] = []
        for i, (name, is_human) in enumerate(player_configs):
            hand = [deck.pop(), deck.pop()]
            conf = _confidence_from_name(name)
            players.append(Player(
                player_id=i,
                name=name,
                coins=2,
                hand=hand,
                is_human=is_human,
                confidence=conf,
            ))

        # Tell ws_ui which player_id to use as the perspective for serialisation.
        human = next((p for p in players if p.is_human), None)
        if human:
            ws_ui.human_player_id = human.player_id

        state = GameState(players=players, deck=deck)

        ai_players: dict[int, object] = {}
        for p in players:
            if not p.is_human:
                conf = p.confidence
                if session.cpu_ai_type == "adaptive":
                    ai_players[p.player_id] = AdaptiveAIStrategy(
                        p,
                        profiles={},
                        bluff_tendency=_tendency_from_name(p.name),
                        confidence=conf,
                    )
                else:
                    ai_players[p.player_id] = AIStrategy(
                        p,
                        bluff_tendency=_tendency_from_name(p.name),
                        challenge_tendency=_challenge_tendency_from_name(p.name),
                        confidence=conf,
                    )

        observers = [s for s in ai_players.values() if hasattr(s, "notify")]
        engine = GameEngine(
            state=state,
            ui=ws_ui,
            ai_players=ai_players,
            observers=observers,
        )
        engine.run()
        session.status = "finished"

    except Exception as exc:
        session.status = "finished"
        session.error = str(exc)
        if loop and ws_ui.websocket:
            try:
                asyncio.run_coroutine_threadsafe(
                    ws_ui.websocket.send_json({
                        "type": "error",
                        "code": "ENGINE_ERROR",
                        "message": str(exc),
                    }),
                    loop,
                ).result(timeout=5)
            except Exception:
                pass
