"""
ingestion.py — Giai đoạn 5: API layer cho demo landing ingestion.
Lưu tại: src/api/ingestion.py

Responsibilities:
1. Mount /api/ingestion/* endpoints
2. Expose demo state, day timeline, activate, runs, realtime controls
3. Smoke test qua /docs
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.connection import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


# === Request/Response Models ===

class DemoStateResponse(BaseModel):
    current_day_idx: int
    warmup_completed: bool
    realtime_active: bool
    last_activated_at: Optional[str]


class DaySnapshot(BaseModel):
    day_idx: int
    snapshot_id: str
    day_date: str
    is_activated: bool
    is_ingested: bool
    ingested_rows: int


class DayTimelineResponse(BaseModel):
    days: list[DaySnapshot]
    total_days: int
    activated_days: int


class ActivateRequest(BaseModel):
    force_replay: bool = False


class ActivateResponse(BaseModel):
    day_idx: int
    status: str  # "warmup_started" | "activated" | "already_active"
    message: str
    ingestion_run_id: Optional[str] = None


class IngestionRun(BaseModel):
    run_id: str
    run_type: str  # "WARMUP_10D" | "DAILY_PLUS1"
    day_idx: int
    started_at: str
    completed_at: Optional[str]
    status: str  # "running" | "completed" | "error"
    rows_ingested: int
    violations_detected: int
    duration_ms: int


class IngestionRunsResponse(BaseModel):
    runs: list[IngestionRun]
    total: int


class RealtimeStatusResponse(BaseModel):
    active: bool
    current_day_idx: int
    tick_count: int
    last_tick_at: Optional[str]
    status: str  # "idle" | "running" | "error"
    message: str


class RealtimeControlResponse(BaseModel):
    action: str  # "started" | "stopped"
    status: str
    message: str


class ResetResponse(BaseModel):
    status: str
    message: str


# === Internal helpers ===

def _get_demo_state(db) -> dict:
    """Read demo_ops.demo_state singleton."""
    rows = db.execute("SELECT current_day_idx, warmup_completed, realtime_active, last_activated_at FROM demo_ops.demo_state LIMIT 1")
    if not rows:
        return {"current_day_idx": -1, "warmup_completed": False, "realtime_active": False, "last_activated_at": None}
    r = rows[0]
    return {
        "current_day_idx": int(r[0]) if r[0] is not None else -1,
        "warmup_completed": bool(r[1]) if r[1] is not None else False,
        "realtime_active": bool(r[2]) if r[2] is not None else False,
        "last_activated_at": str(r[3]) if r[3] else None,
    }


def _get_day_snapshots(db) -> list[DaySnapshot]:
    """Read landing_day_snapshots timeline."""
    rows = db.execute("""
        SELECT day_idx, snapshot_id, day_date, is_activated, is_ingested, ingested_rows
        FROM demo_ops.landing_day_snapshots
        ORDER BY day_idx ASC
    """)
    days = []
    for r in rows:
        days.append(DaySnapshot(
            day_idx=int(r[0]) if r[0] is not None else 0,
            snapshot_id=str(r[1]) if r[1] else "",
            day_date=str(r[2]) if r[2] else "",
            is_activated=bool(r[3]) if r[3] is not None else False,
            is_ingested=bool(r[4]) if r[4] is not None else False,
            ingested_rows=int(r[5]) if r[5] is not None else 0,
        ))
    return days


def _get_ingestion_runs(db, limit: int = 50) -> list[IngestionRun]:
    """Read demo_ops.ingestion_runs history."""
    rows = db.execute("""
        SELECT run_id, run_type, day_idx, started_at, completed_at, status, rows_ingested, violations_detected, duration_ms
        FROM demo_ops.ingestion_runs
        ORDER BY started_at DESC
        LIMIT ?
    """, [limit])
    runs = []
    for r in rows:
        runs.append(IngestionRun(
            run_id=str(r[0]) if r[0] else "",
            run_type=str(r[1]) if r[1] else "",
            day_idx=int(r[2]) if r[2] is not None else -1,
            started_at=str(r[3]) if r[3] else "",
            completed_at=str(r[4]) if r[4] else None,
            status=str(r[5]) if r[5] else "unknown",
            rows_ingested=int(r[6]) if r[6] is not None else 0,
            violations_detected=int(r[7]) if r[7] is not None else 0,
            duration_ms=int(r[8]) if r[8] is not None else 0,
        ))
    return runs


# === Endpoints ===

@router.get("/status", response_model=DemoStateResponse)
async def get_demo_status():
    """
    GET /api/v1/ingestion/status
    Returns current demo state (day_idx, warmup_completed, realtime_active).
    """
    db = get_db()
    state = _get_demo_state(db)
    return DemoStateResponse(**state)


@router.get("/days", response_model=DayTimelineResponse)
async def get_day_timeline():
    """
    GET /api/v1/ingestion/days
    Returns 15-day timeline from landing_day_snapshots.
    """
    db = get_db()
    days = _get_day_snapshots(db)
    return DayTimelineResponse(
        days=days,
        total_days=len(days),
        activated_days=sum(1 for d in days if d.is_activated),
    )


@router.get("/days/{day_idx}", response_model=DaySnapshot)
async def get_day_detail(day_idx: int):
    """
    GET /api/v1/ingestion/days/{day_idx}
    Returns detail for a specific day.
    """
    db = get_db()
    rows = db.execute("""
        SELECT day_idx, snapshot_id, day_date, is_activated, is_ingested, ingested_rows
        FROM demo_ops.landing_day_snapshots
        WHERE day_idx = ?
    """, [day_idx])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Day {day_idx} not found")
    r = rows[0]
    return DaySnapshot(
        day_idx=int(r[0]) if r[0] is not None else day_idx,
        snapshot_id=str(r[1]) if r[1] else "",
        day_date=str(r[2]) if r[2] else "",
        is_activated=bool(r[3]) if r[3] is not None else False,
        is_ingested=bool(r[4]) if r[4] is not None else False,
        ingested_rows=int(r[5]) if r[5] is not None else 0,
    )


@router.post("/days/{day_idx}/activate", response_model=ActivateResponse)
async def activate_day(day_idx: int, request: ActivateRequest):
    """
    POST /api/v1/ingestion/days/{day_idx}/activate
    Activate a day: triggers warmup (day 0-9) or daily batch (day 10+).
    """
    db = get_db()
    
    # Check day exists
    rows = db.execute("SELECT is_activated, snapshot_id FROM demo_ops.landing_day_snapshots WHERE day_idx = ?", [day_idx])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Day {day_idx} not found in landing_day_snapshots")
    
    is_activated, snapshot_id = rows[0][0], rows[0][1]
    
    # Check demo state
    state = _get_demo_state(db)
    warmup_completed = state["warmup_completed"]
    
    # Determine run type
    if day_idx <= 9 and not warmup_completed:
        run_type = "WARMUP_10D"
    else:
        run_type = "DAILY_PLUS1"
    
    # Check if already activated (no force)
    if is_activated and not request.force_replay:
        return ActivateResponse(
            day_idx=day_idx,
            status="already_active",
            message=f"Day {day_idx} already activated. Use force_replay=true to re-run.",
            ingestion_run_id=None,
        )
    
    # Import and run batch (deferred to background in real impl)
    # For now, just mark as activated and return run_id
    ingestion_run_id = f"ING-{day_idx:04d}-{day_idx * 17 % 1000000:06d}"
    
    try:
        from scripts.landing_data_ingestion.batch_runner import run_warmup_then_day
        
        # Run async in background - for sync API, just trigger and return
        run_warmup_then_day(target_day_idx=day_idx)
        
        # Update snapshot activated flag
        db.execute(
            "UPDATE demo_ops.landing_day_snapshots SET is_activated = TRUE WHERE day_idx = ?",
            [day_idx]
        )
        
        # Update demo_state
        db.execute(
            "UPDATE demo_ops.demo_state SET current_day_idx = ?, warmup_completed = TRUE, last_activated_at = ? WHERE TRUE",
            [day_idx, datetime.now(timezone.utc).isoformat()]
        )
        
        return ActivateResponse(
            day_idx=day_idx,
            status="activated" if day_idx > 0 else "warmup_started",
            message=f"Day {day_idx} batch triggered successfully.",
            ingestion_run_id=ingestion_run_id,
        )
        
    except ImportError:
        # Fallback: just mark activated
        db.execute(
            "UPDATE demo_ops.landing_day_snapshots SET is_activated = TRUE WHERE day_idx = ?",
            [day_idx]
        )
        return ActivateResponse(
            day_idx=day_idx,
            status="activated",
            message=f"Day {day_idx} marked as activated (batch_runner not available).",
            ingestion_run_id=ingestion_run_id,
        )


@router.get("/runs", response_model=IngestionRunsResponse)
async def get_ingestion_runs(limit: int = 50):
    """
    GET /api/v1/ingestion/runs
    Returns ingestion_runs history.
    """
    db = get_db()
    runs = _get_ingestion_runs(db, limit)
    total = db.execute("SELECT COUNT(*) FROM demo_ops.ingestion_runs")[0][0] if db.execute("SELECT COUNT(*) FROM demo_ops.ingestion_runs") else 0
    return IngestionRunsResponse(runs=runs, total=total)


@router.post("/reset", response_model=ResetResponse)
async def reset_demo_state():
    """
    POST /api/v1/ingestion/reset
    Reset demo state: clear quarantine, batch_run_log, reset demo_state to -1.
    Does NOT touch raw.* tables.
    """
    db = get_db()
    
    try:
        # Stop realtime first
        try:
            from src.services.ingestion.realtime_runner import get_realtime_state, stop_realtime
            stop_realtime()
        except ImportError:
            pass
        
        # Clear quarantine tables
        quarantine_tables = db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'quarantine'")
        for row in quarantine_tables:
            tbl = row[0]
            try:
                db.execute(f"DELETE FROM quarantine.{tbl}" if tbl != "quarantine" else f"DELETE FROM quarantine")
            except Exception as e:
                logger.warning(f"Could not clear quarantine.{tbl}: {e}")
        
        # Clear demo_ops batch_run_log
        db.execute("DELETE FROM demo_ops.batch_run_log")
        
        # Reset demo_state to -1
        db.execute("UPDATE demo_ops.demo_state SET current_day_idx = -1, warmup_completed = FALSE, realtime_active = FALSE, last_activated_at = NULL")
        
        # Mark all snapshots as not activated
        db.execute("UPDATE demo_ops.landing_day_snapshots SET is_activated = FALSE, is_ingested = FALSE, ingested_rows = 0")
        
        return ResetResponse(
            status="success",
            message="Demo state reset complete. Quarantine cleared, demo_state reset to -1. Raw data preserved.",
        )
        
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.get("/realtime/status", response_model=RealtimeStatusResponse)
async def get_realtime_status():
    """
    GET /api/v1/ingestion/realtime/status
    Returns current realtime runner status.
    """
    try:
        from src.services.ingestion.realtime_runner import get_realtime_state
        state = get_realtime_state()
        
        return RealtimeStatusResponse(
            active=state.is_running,
            current_day_idx=state.current_day_idx,
            tick_count=state.tick_count,
            last_tick_at=str(state.last_tick_at) if state.last_tick_at else None,
            status=state.status,
            message=state.message,
        )
    except ImportError:
        return RealtimeStatusResponse(
            active=False,
            current_day_idx=-1,
            tick_count=0,
            last_tick_at=None,
            status="unavailable",
            message="Realtime runner not available",
        )


@router.post("/realtime/start", response_model=RealtimeControlResponse)
async def start_realtime():
    """
    POST /api/v1/ingestion/realtime/start
    Start the realtime runner.
    """
    try:
        from src.services.ingestion.realtime_runner import start_realtime as rt_start
        
        db = get_db()
        state = _get_demo_state(db)
        target_day = state["current_day_idx"]
        
        rt_start(target_day_idx=target_day)
        
        return RealtimeControlResponse(
            action="started",
            status="running",
            message=f"Realtime runner started for day {target_day}.",
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Realtime runner not available: {e}")


@router.post("/realtime/stop", response_model=RealtimeControlResponse)
async def stop_realtime():
    """
    POST /api/v1/ingestion/realtime/stop
    Stop the realtime runner.
    """
    try:
        from src.services.ingestion.realtime_runner import stop_realtime as rt_stop
        
        rt_stop()
        
        return RealtimeControlResponse(
            action="stopped",
            status="idle",
            message="Realtime runner stopped.",
        )
    except ImportError:
        return RealtimeControlResponse(
            action="stopped",
            status="idle",
            message="Realtime runner already stopped or not available.",
        )


@router.get("/health")
async def ingestion_health():
    """Health check endpoint for monitoring."""
    db = get_db()
    try:
        rows = db.execute("SELECT 1")
        return {"status": "ok", "service": "ingestion"}
    except Exception as e:
        return {"status": "error", "service": "ingestion", "detail": str(e)}
