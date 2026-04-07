"""
WebSocketUI — UIProtocol implementation that drives decisions over a WebSocket.

Architecture
────────────
The GameEngine runs in a background OS thread (not an asyncio task) so that
the engine's synchronous blocking calls do not starve the asyncio event loop.

Decision flow:
  1. Engine thread calls e.g. ws_ui.choose_action(state, player)
  2. choose_action() serialises a "decision" message and pushes it to the
     browser via asyncio.run_coroutine_threadsafe() + future.result().
  3. choose_action() then calls decision_queue.get() — this blocks only the
     engine thread, leaving the event loop free to receive the reply.
  4. The FastAPI WebSocket handler receives {"type":"decision_response",...}
     and calls decision_queue.put(value), unblocking the engine thread.
  5. choose_action() returns the resolved Action to the engine.

Notify flow:
  notify() is fire-and-forget: it pushes an "event" message and does not
  wait on the decision queue.
"""
from __future__ import annotations

import asyncio
import queue
import uuid
from typing import Any

from fastapi import WebSocket

from coup.constants import Action, Character, EventType
from coup.models import Card, Player, ActionContext, GameState
from coup import rules
from server.serializers import (
    CHAR_ICON, ACTION_ICON,
    serialize_state, serialize_ctx,
)


class WebSocketUI:
    """UIProtocol implementation backed by a WebSocket connection."""

    def __init__(self, player_configs: list[tuple[str, bool]]) -> None:
        # Pre-built player list returned immediately by setup_players().
        self._player_configs = player_configs

        # Set by attach() once the browser connects.
        self.websocket: WebSocket | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

        # Thread-safe queue: WebSocket handler puts answers, engine thread gets them.
        self.decision_queue: queue.Queue[Any] = queue.Queue()

        # Tracks the message that is currently awaiting a response so we can
        # validate decision_id echoes and resend on reconnect.
        self._pending_decision: dict[str, Any] | None = None

        # Set after game state is built so notify() can use the right perspective.
        self.human_player_id: int = 0

        # Monotonically increasing counter — incremented each time a new WebSocket
        # attaches.  The WS handler captures this on connect and checks it in its
        # finally block so that a stale close doesn't signal disconnect when a
        # newer connection has already taken over (handles React StrictMode double-
        # effect and genuine browser reconnects).
        self._generation: int = 0

    def attach(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
        """Register (or re-register) the live WebSocket connection."""
        self.websocket = websocket
        self.loop = loop
        self._generation += 1

    # ── Internal send helpers ─────────────────────────────────────────── #

    def _send(self, msg: dict[str, Any]) -> None:
        """
        Send a JSON message to the browser from the engine thread.
        Blocks until the send coroutine completes (or times out).
        """
        assert self.websocket is not None and self.loop is not None, \
            "WebSocketUI.attach() must be called before the engine starts"
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send_json(msg), self.loop
        )
        future.result(timeout=30)

    def _ask(self, msg: dict[str, Any]) -> Any:
        """Send a decision prompt and block the engine thread until answered."""
        msg["decision_id"] = uuid.uuid4().hex[:8]
        self._pending_decision = msg
        self._send(msg)
        answer = self.decision_queue.get()   # blocks only the engine thread
        self._pending_decision = None
        if answer == "__disconnected__":
            raise RuntimeError("WebSocket client disconnected during decision")
        return answer

    # ── UIProtocol: setup ─────────────────────────────────────────────── #

    def setup_players(self, num_players: int) -> list[tuple[str, bool]]:
        """Return the pre-populated player list without blocking."""
        return self._player_configs

    # ── UIProtocol: decision methods ──────────────────────────────────── #

    def choose_action(self, state: GameState, player: Player) -> Action:
        legal = rules.legal_actions(player)
        options = [
            {"id": a.name, "label": a.value, "icon": ACTION_ICON.get(a, "")}
            for a in legal
        ]
        value = self._ask({
            "type": "decision",
            "prompt": "choose_action",
            "state": serialize_state(state, player.player_id),
            "options": options,
        })
        return Action[value]

    def choose_target(self, state: GameState, player: Player, action: Action) -> Player:
        targets = [p for p in state.active_players if p.player_id != player.player_id]
        options = [
            {
                "id": str(p.player_id),
                "label": p.name,
                "coins": p.coins,
                "influence": p.influence_count,
            }
            for p in targets
        ]
        value = self._ask({
            "type": "decision",
            "prompt": "choose_target",
            "action": action.value,
            "action_icon": ACTION_ICON.get(action, ""),
            "state": serialize_state(state, player.player_id),
            "options": options,
        })
        target_id = int(value)
        return next(p for p in targets if p.player_id == target_id)

    def choose_block(
        self, state: GameState, potential_blocker: Player, ctx: ActionContext
    ) -> Character | None:
        blocking_chars = rules.BLOCKABLE_BY.get(ctx.action, [])
        if not blocking_chars:
            return None
        options = [
            {"id": c.name, "label": f"Block with {c.value}", "icon": CHAR_ICON.get(c, "")}
            for c in blocking_chars
        ]
        options.append({"id": "PASS", "label": "Pass", "icon": ""})
        value = self._ask({
            "type": "decision",
            "prompt": "choose_block",
            "ctx": serialize_ctx(ctx),
            "state": serialize_state(state, potential_blocker.player_id),
            "options": options,
        })
        if value == "PASS":
            return None
        return Character[value]

    def choose_challenge_action(
        self, state: GameState, potential_challenger: Player, ctx: ActionContext
    ) -> bool:
        value = self._ask({
            "type": "decision",
            "prompt": "choose_challenge",
            "ctx": serialize_ctx(ctx),
            "state": serialize_state(state, potential_challenger.player_id),
            "options": [
                {"id": "true",  "label": "⚔️ Challenge", "icon": "⚔️"},
                {"id": "false", "label": "Pass",          "icon": ""},
            ],
        })
        return value == "true"

    def choose_card_to_lose(self, state: GameState, player: Player, reason: str) -> Card:
        alive = player.alive_cards
        if len(alive) == 1:
            return alive[0]
        options = [
            {"id": str(i), "label": c.character.value, "icon": CHAR_ICON.get(c.character, "")}
            for i, c in enumerate(alive)
        ]
        value = self._ask({
            "type": "decision",
            "prompt": "choose_card_to_lose",
            "reason": reason,
            "state": serialize_state(state, player.player_id),
            "options": options,
        })
        return alive[int(value)]

    def choose_exchange_cards(
        self, state: GameState, player: Player, all_cards: list[Card]
    ) -> list[Card]:
        keep_count = player.influence_count
        options = [
            {"id": str(i), "label": c.character.value, "icon": CHAR_ICON.get(c.character, "")}
            for i, c in enumerate(all_cards)
        ]
        value = self._ask({
            "type": "decision",
            "prompt": "choose_exchange",
            "keep_count": keep_count,
            "state": serialize_state(state, player.player_id),
            "options": options,
        })
        # value is a list of string indices sent by the browser
        indices = [int(v) for v in value]
        return [all_cards[i] for i in indices]

    # ── UIProtocol: notify ────────────────────────────────────────────── #

    def notify(self, event: EventType, **kwargs: Any) -> None:
        state = kwargs.get("state")
        msg: dict[str, Any] = {
            "type": "event",
            "event": event.name,
            "state": serialize_state(state, self.human_player_id) if state else None,
        }

        ctx = kwargs.get("ctx")
        if ctx is not None:
            msg["ctx"] = serialize_ctx(ctx)

        if "player" in kwargs:
            p = kwargs["player"]
            msg["player"] = {"player_id": p.player_id, "name": p.name}

        if "winner" in kwargs:
            w = kwargs["winner"]
            msg["winner"] = {"player_id": w.player_id, "name": w.name}

        if "card" in kwargs:
            c = kwargs["card"]
            msg["card"] = {
                "character": c.character.value,
                "icon": CHAR_ICON.get(c.character, ""),
            }

        if "reason" in kwargs:
            msg["reason"] = kwargs["reason"]

        if "player_proved" in kwargs:
            pp = kwargs["player_proved"]
            msg["player_proved"] = {"player_id": pp.player_id, "name": pp.name}

        if "proved_card" in kwargs:
            pc = kwargs["proved_card"]
            msg["proved_card"] = {
                "character": pc.character.value,
                "icon": CHAR_ICON.get(pc.character, ""),
            }

        try:
            self._send(msg)
        except Exception:
            # Never let a notify failure crash the engine thread.
            pass
