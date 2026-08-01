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

UI_DIR_V2 = os.path.join(os.path.dirname(__file__), "ui")
UI_DIR_V3 = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "dist")

INDEX_HTML_V2 = os.path.join(UI_DIR_V2, "index.html")
APP_HTML_V2 = os.path.join(UI_DIR_V2, "app.html")
INDEX_HTML_V3 = os.path.join(UI_DIR_V3, "index.html")


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
    version="3.0.0",
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

# Include router under /api and /api/v1 for compatibility
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "DataTrust OS", "env": settings.app_env, "version": "v3.0"}


# v3 UI Endpoint
@app.get("/v3", response_class=HTMLResponse)
async def serve_v3():
    if os.path.exists(INDEX_HTML_V3):
        return FileResponse(INDEX_HTML_V3)
    return HTMLResponse("<html><body><h1>DataTrust OS v3</h1><p>v3 build pending. Run <code>pnpm run build</code> in frontend-v3.</p></body></html>")


# v2 Guided Workflow Web UI at GET / and GET /ui
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    target_path = INDEX_HTML_V2 if os.path.exists(INDEX_HTML_V2) else APP_HTML_V2
    if os.path.exists(target_path):
        return FileResponse(target_path)
    return HTMLResponse("<html><body><h1>DataTrust OS Web UI</h1><p>UI loading...</p></body></html>")


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    target_path = APP_HTML_V2 if os.path.exists(APP_HTML_V2) else INDEX_HTML_V2
    if os.path.exists(target_path):
        return FileResponse(target_path)
    return HTMLResponse("<html><body><h1>DataTrust OS Web UI</h1><p>UI loading...</p></body></html>")


# Mount static assets
if os.path.exists(UI_DIR_V2):
    app.mount("/static", StaticFiles(directory=UI_DIR_V2), name="static")
    assets_dir = os.path.join(UI_DIR_V2, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

if os.path.exists(UI_DIR_V3):
    app.mount("/v3/static", StaticFiles(directory=UI_DIR_V3), name="v3_static")
    v3_assets = os.path.join(UI_DIR_V3, "assets")
    if os.path.exists(v3_assets):
        app.mount("/v3/assets", StaticFiles(directory=v3_assets), name="v3_assets")
