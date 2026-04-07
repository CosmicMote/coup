from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.session import create_session, active_sessions

router = APIRouter()


class CreateGameRequest(BaseModel):
    num_players: int = Field(default=4, ge=2, le=6)
    human_name: str = Field(default="You", min_length=1, max_length=30)
    cpu_ai_type: str = Field(default="basic")
    cpu_names: list[str] | None = None


class PlayerInfo(BaseModel):
    name: str
    is_human: bool


class CreateGameResponse(BaseModel):
    game_id: str
    num_players: int
    players: list[PlayerInfo]


@router.post("/games", response_model=CreateGameResponse)
def create_game(body: CreateGameRequest) -> CreateGameResponse:
    if body.cpu_ai_type not in ("basic", "adaptive"):
        raise HTTPException(
            status_code=400,
            detail="cpu_ai_type must be 'basic' or 'adaptive'",
        )

    session = create_session(
        num_players=body.num_players,
        human_name=body.human_name,
        cpu_ai_type=body.cpu_ai_type,
        cpu_names=body.cpu_names,
    )
    return CreateGameResponse(
        game_id=session.game_id,
        num_players=session.num_players,
        players=[PlayerInfo(name=n, is_human=h) for n, h in session.player_configs],
    )


@router.get("/games/{game_id}")
def get_game(game_id: str) -> dict:
    session = active_sessions.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    return {
        "game_id": session.game_id,
        "status": session.status,
        "num_players": session.num_players,
        "players": [{"name": n, "is_human": h} for n, h in session.player_configs],
        "error": session.error,
    }
