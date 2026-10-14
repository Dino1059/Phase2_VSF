"""Render production entry point serving the API and the built SPA."""

from pathlib import Path

from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.main import app


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def ready(response: Response) -> dict[str, str]:
    """A lightweight readiness probe; DB-dependent routes report their own errors."""
    if not FRONTEND_DIST.joinpath("index.html").is_file():
        response.status_code = 503
        return {"status": "not_ready", "reason": "frontend build is missing"}
    return {"status": "ready"}


if FRONTEND_DIST.is_dir():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def serve_spa(spa_path: str):
        candidate = (FRONTEND_DIST / spa_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            candidate = FRONTEND_DIST / "index.html"
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
