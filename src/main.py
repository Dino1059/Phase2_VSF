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
    search_router,
    projects_router,
    signals_router,
    incidents_router,
    controls_router,
    authorizations_router,
    audit_router,
    summary_router,
    evaluation_router,
    system_router,
)
from src.api.hitl import hitl_router
from src.api.dashboard import dashboard_router
from src.api.pipeline import pipeline_router
from src.api.traces import traces_router
from src.api.quarantine_api import quarantine_router
from src.api.snapshots import snapshots_router
from src.api.routes.telemetry import telemetry_router
from src.services.ingestion import streaming_worker
from src.config import get_settings
from src.services.dataset_engine import seed_dataset
from src.services.scheduler import scheduler_service
from src.db.connection import get_db

UI_DIR_V2 = os.path.join(os.path.dirname(__file__), "ui")
UI_DIR_V3 = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

INDEX_HTML_V2 = os.path.join(UI_DIR_V2, "index.html")
APP_HTML_V2 = os.path.join(UI_DIR_V2, "app.html")
INDEX_HTML_V3 = os.path.join(UI_DIR_V3, "index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            integrations=[FastApiIntegration()],
        )
        print("Sentry Backend SDK initialized successfully")
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    # Pre-seed dataset if not exists
    seed_dataset()
    # Initialize DuckDB schema
    db = get_db()
    db.init_schema()
    print(f"DuckDB initialized at {db.db_path}")
    streaming_worker.start()
    scheduler_service.start()
    yield
    streaming_worker.stop()
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
app.include_router(search_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(controls_router, prefix="/api/v1")
app.include_router(authorizations_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")

app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(traces_router, prefix="/api/v1")
app.include_router(quarantine_router, prefix="/api/v1")
app.include_router(snapshots_router, prefix="/api/v1")
app.include_router(hitl_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")



@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env, "version": settings.app_version}


# Static asset handlers for /vite.svg and /favicon.ico
@app.get("/vite.svg")
async def serve_vite_svg():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "vite.svg"),
        os.path.join(UI_DIR_V3, "vite.svg"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "src", "assets", "vite.svg"),
        os.path.join(UI_DIR_V2, "vite.svg"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/svg+xml")
    return HTMLResponse(status_code=404, content="vite.svg not found")


@app.get("/favicon.ico")
async def serve_favicon_ico():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "favicon.ico"),
        os.path.join(UI_DIR_V3, "favicon.ico"),
        os.path.join(UI_DIR_V2, "favicon.ico"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "favicon.svg"),
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
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "favicon.svg"),
        os.path.join(UI_DIR_V3, "favicon.svg"),
        os.path.join(UI_DIR_V2, "favicon.svg"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/svg+xml")
    return HTMLResponse(status_code=404, content="favicon.svg not found")


# Mount static assets
dist_assets_dir = os.path.join(UI_DIR_V3, "assets")
if os.path.exists(dist_assets_dir):
    app.mount("/assets", StaticFiles(directory=dist_assets_dir), name="assets")
elif os.path.exists(os.path.join(UI_DIR_V2, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(UI_DIR_V2, "assets")), name="assets")

if os.path.exists(UI_DIR_V2):
    app.mount("/static", StaticFiles(directory=UI_DIR_V2), name="static")

if os.path.exists(UI_DIR_V3):
    app.mount("/v3/assets", StaticFiles(directory=dist_assets_dir if os.path.exists(dist_assets_dir) else UI_DIR_V3), name="v3_assets")


# Primary Frontend SPA Endpoint at root /
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists(INDEX_HTML_V3):
        return FileResponse(INDEX_HTML_V3)
    frontend_src_index = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(frontend_src_index):
        return FileResponse(frontend_src_index)
    if os.path.exists(INDEX_HTML_V2):
        return FileResponse(INDEX_HTML_V2)
    return HTMLResponse("<html><body><h1>DataTrust OS</h1><p>Frontend loading...</p></body></html>")


# Redirect legacy /v3 to /
@app.get("/v3", response_class=HTMLResponse)
@app.get("/v3/", response_class=HTMLResponse)
@app.get("/v3/{full_path:path}", response_class=HTMLResponse)
async def serve_v3(full_path: str = ""):
    if os.path.exists(INDEX_HTML_V3):
        return FileResponse(INDEX_HTML_V3)
    return await serve_index()


# Legacy V2 Guided Workflow Web UI at GET /ui
@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    target_path = APP_HTML_V2 if os.path.exists(APP_HTML_V2) else INDEX_HTML_V2
    if os.path.exists(target_path):
        return FileResponse(target_path)
    return await serve_index()
