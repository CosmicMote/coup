from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.routes import games, websocket


def create_app() -> FastAPI:
    app = FastAPI(title="Coup")

    # Allow the Vite dev server (port 5173) to reach the API during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(games.router, prefix="/api")
    app.include_router(websocket.router)

    # In production, serve the built React app.  In development the Vite dev
    # server runs separately and proxies /api + /ws to this FastAPI process.
    #
    # We intentionally avoid app.mount("/", StaticFiles(..., html=True)) because
    # Starlette's StaticFiles only handles GET/HEAD and returns 405 for POST
    # requests — which would break POST /api/games.  Instead we mount the
    # hashed asset bundle at /assets and add explicit GET-only SPA fallback
    # routes that can never interfere with the API.
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @app.get("/")
        async def serve_root() -> FileResponse:
            return FileResponse(str(frontend_dist / "index.html"))

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            candidate = frontend_dist / full_path
            if candidate.exists() and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(frontend_dist / "index.html"))

    return app


app = create_app()
