"""Render production entry point serving the API and the built SPA."""

from pathlib import Path
import os

import psycopg2

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
    """Verify the frontend, PostgreSQL, and every required production migration."""
    if not FRONTEND_DIST.joinpath("index.html").is_file():
        response.status_code = 503
        return {"status": "not_ready", "reason": "frontend build is missing"}
    try:
        from database.run_migrations import INCREMENTAL_MIGRATIONS

        conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT migration_name FROM orchestration.schema_migrations")
                applied = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()
        missing = [name for name in INCREMENTAL_MIGRATIONS if name not in applied]
        if missing:
            response.status_code = 503
            return {"status": "not_ready", "reason": f"missing migrations: {', '.join(missing)}"}
    except Exception as exc:
        response.status_code = 503
        return {"status": "not_ready", "reason": f"database readiness failed: {exc}"}
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
