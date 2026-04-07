from __future__ import annotations

import asyncio
import queue
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.session import active_sessions, attach_websocket, launch_engine

router = APIRouter()


@router.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
    session = active_sessions.get(game_id)
    if not session:
        await websocket.close(code=4004, reason="Game not found")
        return

    if session.status == "finished":
        await websocket.close(code=4009, reason="Game already finished")
        return

    await websocket.accept()

    loop = asyncio.get_event_loop()
    attach_websocket(session, websocket, loop)

    if session.status == "running":
        # Reconnection — engine is already running.
        # Drain any stale "__disconnected__" sentinel the previous connection
        # may have left behind, then re-send the pending decision (if any) so
        # the client can catch up.
        _drain_disconnected(session.ws_ui.decision_queue)
        if session.ws_ui._pending_decision:
            await websocket.send_json(session.ws_ui._pending_decision)

    # Capture this connection's generation so the finally block can tell
    # whether a newer connection has already taken over.
    my_generation = session.ws_ui._generation

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ready":
                # The client sends "ready" from its onopen handler only when the
                # connection is confirmed stable (active flag is true).
                # React StrictMode's cleanup fires before onopen, so the
                # StrictMode-discarded WS never sends "ready" — the engine is
                # never started on a socket that's about to be torn down.
                if session.status == "waiting":
                    launch_engine(session)

            elif msg_type == "decision_response":
                decision_id = data.get("decision_id")
                value = data.get("value")

                # Validate the decision_id to reject stale/duplicate responses.
                pending = session.ws_ui._pending_decision
                if pending and pending.get("decision_id") == decision_id:
                    session.ws_ui.decision_queue.put(value)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        # Only signal the engine to stop if no newer connection has taken over.
        if session.status == "running" and session.ws_ui._generation == my_generation:
            session.ws_ui.decision_queue.put("__disconnected__")


def _drain_disconnected(q: queue.Queue[Any]) -> None:
    """Remove any '__disconnected__' sentinels left by a previous connection."""
    items: list[Any] = []
    while True:
        try:
            item = q.get_nowait()
            if item != "__disconnected__":
                items.append(item)
        except queue.Empty:
            break
    for item in items:
        q.put(item)
