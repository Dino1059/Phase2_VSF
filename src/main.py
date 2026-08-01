import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.config import get_settings
from src.services.dataset_engine import seed_dataset
from src.services.scheduler import scheduler_service

UI_DIR = os.path.join(os.path.dirname(__file__), "ui")
INDEX_HTML = os.path.join(UI_DIR, "index.html")
APP_HTML = os.path.join(UI_DIR, "app.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    # Pre-seed dataset if not exists
    seed_dataset()
    scheduler_service.start()
    yield
    scheduler_service.shutdown()
    print("Shutting down DataTrust OS...")


app = FastAPI(
    title="DataTrust OS API",
    description="AI-Augmented Data Trust & Governance Operating System",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router under both /api and /api/v1 for compatibility
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "DataTrust OS", "env": settings.app_env}


# Serve Guided Workflow Web UI at GET / and GET /ui
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    target_path = INDEX_HTML if os.path.exists(INDEX_HTML) else APP_HTML
    if os.path.exists(target_path):
        return FileResponse(target_path)
    return HTMLResponse("<html><body><h1>DataTrust OS Web UI</h1><p>UI loading...</p></body></html>")


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    target_path = APP_HTML if os.path.exists(APP_HTML) else INDEX_HTML
    if os.path.exists(target_path):
        return FileResponse(target_path)
    return HTMLResponse("<html><body><h1>DataTrust OS Web UI</h1><p>UI loading...</p></body></html>")


if os.path.exists(UI_DIR):
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")
    assets_dir = os.path.join(UI_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
