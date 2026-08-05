import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    router,
    ws_router,
    auth_router,
    datasets_router,
    profiling_router,
    rules_router,
    approvals_router,
    executions_router,
    benchmarks_router,
    schedules_router,
)
from src.api.hitl import hitl_router
from src.api.dashboard import dashboard_router
from src.api.pipeline import pipeline_router
from src.api.traces import traces_router
from src.api.quarantine_api import quarantine_router
from src.api.snapshots import snapshots_router
from src.config import get_settings
from src.services.dataset_engine import seed_dataset
from src.services.scheduler import scheduler_service
from src.db.connection import get_db

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
    # Initialize DuckDB schema
    db = get_db()
    db.init_schema()
    print(f"DuckDB initialized at {db.db_path}")
    scheduler_service.start()
    yield
    scheduler_service.shutdown()
    get_db().close()
    print("Shutting down DataTrust OS...")


app = FastAPI(
    title="DataTrust OS API",
    description="AI-Augmented Data Trust & Governance Operating System",
    version="4.2.0",
    lifespan=lifespan,
)

from src.api.middleware import RoleMiddleware

settings = get_settings()
cors_origins = (
    settings.allowed_cors_origins
    if hasattr(settings, "allowed_cors_origins")
    else settings.cors_origins
)
if isinstance(cors_origins, str):
    cors_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(RoleMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket router and domain API routers
app.include_router(ws_router)
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")
app.include_router(profiling_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(benchmarks_router, prefix="/api/v1")
app.include_router(schedules_router, prefix="/api/v1")

app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(traces_router, prefix="/api/v1")
app.include_router(quarantine_router, prefix="/api/v1")
app.include_router(snapshots_router, prefix="/api/v1")
app.include_router(hitl_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env, "version": settings.app_version}


# Static asset handlers for /vite.svg and /favicon.ico
@app.get("/vite.svg")
async def serve_vite_svg():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "public", "vite.svg"),
        os.path.join(UI_DIR_V3, "vite.svg"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "src", "assets", "vite.svg"),
        os.path.join(UI_DIR_V2, "vite.svg"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/svg+xml")
    return HTMLResponse(status_code=404, content="vite.svg not found")


@app.get("/favicon.ico")
async def serve_favicon_ico():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "public", "favicon.ico"),
        os.path.join(UI_DIR_V3, "favicon.ico"),
        os.path.join(UI_DIR_V2, "favicon.ico"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "public", "favicon.svg"),
        os.path.join(UI_DIR_V3, "favicon.svg"),
        os.path.join(UI_DIR_V2, "favicon.svg"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            media_type = "image/x-icon" if candidate.endswith(".ico") else "image/svg+xml"
            return FileResponse(candidate, media_type=media_type)
    return HTMLResponse(status_code=404, content="favicon not found")


@app.get("/favicon.svg")
async def serve_favicon_svg():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "public", "favicon.svg"),
        os.path.join(UI_DIR_V3, "favicon.svg"),
        os.path.join(UI_DIR_V2, "favicon.svg"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/svg+xml")
    return HTMLResponse(status_code=404, content="favicon.svg not found")


# Mount static assets
if os.path.exists(UI_DIR_V2):
    app.mount("/static", StaticFiles(directory=UI_DIR_V2), name="static")
    assets_dir = os.path.join(UI_DIR_V2, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Mount /v3/assets to frontend-v3/dist/assets (or fallback)
v3_assets_dir = os.path.join(UI_DIR_V3, "assets")
if not os.path.exists(v3_assets_dir):
    v3_src_assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "src", "assets")
    v2_assets_dir = os.path.join(UI_DIR_V2, "assets")
    if os.path.exists(v3_src_assets):
        v3_assets_dir = v3_src_assets
    elif os.path.exists(v2_assets_dir):
        v3_assets_dir = v2_assets_dir

if os.path.exists(v3_assets_dir):
    app.mount("/v3/assets", StaticFiles(directory=v3_assets_dir), name="v3_assets")

if os.path.exists(UI_DIR_V3):
    app.mount("/v3/static", StaticFiles(directory=UI_DIR_V3), name="v3_static")


# v3 UI Endpoint (handles /v3, /v3/, and SPA client-side routes under /v3/*)
@app.get("/v3", response_class=HTMLResponse)
@app.get("/v3/", response_class=HTMLResponse)
@app.get("/v3/{full_path:path}", response_class=HTMLResponse)
async def serve_v3(full_path: str = ""):
    if os.path.exists(INDEX_HTML_V3):
        return FileResponse(INDEX_HTML_V3)
    frontend_v3_src_index = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "index.html")
    if os.path.exists(frontend_v3_src_index):
        return FileResponse(frontend_v3_src_index)
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
