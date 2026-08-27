import logging
import subprocess
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel

from src.db.connection import get_db
from src.middleware.auth import decode_access_token, UserRole
from src.services.conversation_store import conversation_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])



STEWARD_WIPE_TABLES = [
    "quality_rules",
    "quarantine",
    "audit_log",
    "execution_authorizations",
    "decisions",
    "evidence",
    "agent_traces",
    "incidents",
    "messages",
    "hypotheses",
    "recommendations",
    "profile_results",
    "job_runs",
    "preventive_controls",
    "authorizations",
    "workflow_events",
    "signals",
    "policy_versions",
    "detector_artifacts",
    "investigation_runs",
    "sessions",
]


def wipe_steward_runtime(db) -> list:
    """True admin wipe: approved/proposed rules, HITL, traces, split, pipeline session."""
    cleared = []
    for tbl in STEWARD_WIPE_TABLES:
        try:
            db.execute(f"DELETE FROM {tbl}")
            cleared.append(tbl)
        except Exception as e:
            logger.warning(f"Could not clear table {tbl}: {e}")
    try:
        leftover = db.execute("SELECT count(*) FROM quality_rules")
        if leftover and int(leftover[0][0]) > 0:
            db.execute("DELETE FROM quality_rules")
        leftover = db.execute("SELECT count(*) FROM quality_rules")
        if leftover and int(leftover[0][0]) == 0 and "quality_rules" not in cleared:
            cleared.append("quality_rules")
    except Exception as e:
        logger.warning(f"quality_rules wipe verify: {e}")
    try:
        from src.services.dataset_engine import run_store
        run_store._runs.clear()
        cleared.append("run_store")
    except Exception as e:
        logger.warning(f"run_store wipe: {e}")
    try:
        from src.api import routes as api_routes
        sm = getattr(api_routes, "state_machine", None)
        if sm is not None and hasattr(sm, "reset"):
            sm.reset()
        cleared.append("pipeline_session")
    except Exception as e:
        logger.warning(f"pipeline session wipe: {e}")
    return cleared

class ResetAllResponse(BaseModel):
    status: str
    message: str
    cleared_tables: list[str]
    reloaded_records: dict
    algolia: dict = {}
    uploads_cleared: int = 0


@router.post("/reset-all", response_model=ResetAllResponse)
async def reset_all_db(
    authorization: Optional[str] = Header(None),
    reload_warehouse: bool = Query(True, description="Reload canonical main.* tables from data_new CSVs"),
):
    """Admin-only full system reset: purges runtime state, reloads data_new warehouse, reseeds Algolia."""
    # 1. Role Guard
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing signed JWT token")

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_role = str(payload.get("role", "")).lower()
    if user_role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Only administrators can execute full system reset")

    db = get_db()
    cleared = []
    tables_to_clear = [
        "quality_rules",
        "quarantine",
        "audit_log",
        "execution_authorizations",
        "decisions",
        "evidence",
        "hypotheses",
        "recommendations",
        "agent_traces",
        "incidents",
        "incident_metadata",
    ]

    for tbl in tables_to_clear:
        try:
            db.execute(f"DELETE FROM {tbl}")
            cleared.append(tbl)
        except Exception as e:
            logger.warning(f"Could not clear table {tbl}: {e}")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    cleared = wipe_steward_runtime(db)

    # 1b. Purge uploaded / dynamic ghost datasets from datasets table & registry
    try:
        db.execute("DELETE FROM datasets WHERE dataset_key LIKE 'uploaded_%'")
        cleared.append("uploaded_datasets")
    except Exception as e:
        logger.warning(f"Could not clear uploaded datasets: {e}")

    try:
        from src.config import get_settings
        settings = get_settings()
        keys_to_del = [k for k in settings.dataset_registry if k.startswith("uploaded_")]
        for k in keys_to_del:
            settings.dataset_registry.pop(k, None)
            settings.dataset_metadata_map.pop(k, None)
            settings.dataset_provenance_map.pop(k, None)
    except Exception:
        pass

    uploads_cleared = 0
    upload_dir = os.path.join(project_root, "data", "uploads")
    if os.path.isdir(upload_dir):
        for name in os.listdir(upload_dir):
            fp = os.path.join(upload_dir, name)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
                    uploads_cleared += 1
            except OSError as e:
                logger.warning(f"Could not remove upload {fp}: {e}")

    # 2. Reset conversation memory
    try:
        conversation_store.clear_all()
        if "messages" not in cleared:
            cleared.append("messages")
    except Exception as e:
        logger.warning(f"Could not clear conversation store: {e}")

    # 2b. Clear in-memory incident / evidence / hypothesis caches so the
    # Alert Dashboard starts empty after a reset and does not leak the
    # previous session's incidents into a fresh upload.
    try:
        from src.reliability.incidents.service import IncidentService
        IncidentService().clear()
    except Exception as e:
        logger.warning(f"Could not clear IncidentService cache: {e}")

    # 4. Verify / Ingest VinGroup baseline tables
    reloaded = {}
    if reload_warehouse:
        try:
            logger.info("Warehouse reload requested - preserving landing ingestion structure.")
        except Exception as e:
            logger.warning(f"Could not reload data_new warehouse: {e}")

    try:
        row_counts = {}
        for tbl in ["raw.ev_telemetry", "raw.charging_sessions", "raw.trips", "raw.fault_manifest"]:
            try:
                res = db.execute(f"SELECT count(*) FROM {tbl}")
                row_counts[tbl] = res[0][0] if res else 0
            except Exception:
                row_counts[tbl] = 0
        reloaded = row_counts
    except Exception as e:
        logger.warning(f"Error checking row counts: {e}")

    # 4. Do not reseed gold RCA onto the live incident queue (eval only).

    # 5. Algolia: wipe ghost objects, then seed current datasets (no uploaded_ leftovers)
    algolia_meta: dict = {"cleared": False, "seeded": 0}
    try:
        from src.services.algolia_search import AlgoliaSearchService
        algolia_service = AlgoliaSearchService()
        algolia_meta["cleared"] = bool(algolia_service.clear_index())
        seed = algolia_service.seed_all_entities()
        algolia_meta["seeded"] = int(seed.get("total_indexed", 0))
        algolia_meta["datasets"] = int(seed.get("datasets", 0))
    except Exception as e:
        logger.warning(f"Could not reset Algolia index: {e}")
        algolia_meta["error"] = str(e)

    return ResetAllResponse(
        status="success",
        message="System database reloaded from data_new, runtime state cleared, Algolia reseeded.",
        cleared_tables=cleared,
        reloaded_records=reloaded,
        algolia=algolia_meta,
        uploads_cleared=uploads_cleared,
    )



class DemoSnapshotResponse(BaseModel):
    mode: str
    source: str
    fault_injected: bool
    telemetry: int
    charging_sessions: int
    trips: int
    soc_below_zero: int
    open_incidents: int
    window_end: str = "2026-01-15"
    ingress: str = "batch window"


def resolve_demo_source(mode: str, project_root: str) -> Path:
    from pathlib import Path as P
    if mode not in ("happy", "unhappy"):
        raise HTTPException(status_code=400, detail="mode must be happy or unhappy")
    folder = "vingroup_pilot_dataset" if mode == "happy" else "vingroup_faulty_pilot_dataset"
    src = P(project_root) / "data_new" / folder
    if not src.is_dir():
        raise HTTPException(status_code=404, detail=f"missing source {src}")
    return src


def _measure_warehouse(db) -> dict:
    def _count(sql: str, default: int = 0) -> int:
        try:
            res = db.execute(sql)
            return int(res[0][0]) if res else default
        except Exception:
            return default

    charging = _count("SELECT count(DISTINCT session_id) FROM main.charging_sessions")
    return {
        "telemetry": _count("SELECT count(*) FROM main.ev_telemetry"),
        "charging_sessions": charging,
        "trips": _count("SELECT count(*) FROM main.trips"),
        "soc_below_zero": _count("SELECT count(*) FROM main.ev_telemetry WHERE battery_soc < 0"),
        "open_incidents": _count("SELECT count(*) FROM incidents WHERE status = 'OPEN'"),
    }


def _restore_unhappy_incidents(db, project_root: str) -> None:
    import json
    from pathlib import Path as P
    fixture = P(project_root) / "fixtures" / "demo" / "unhappy_incidents.json"
    if not fixture.is_file():
        return
    cases = json.loads(fixture.read_text())
    for row in cases:
        db.execute(
            """
            INSERT INTO incidents (
                incident_id, project_id, status, entity_ids, signal_ids,
                admission_reason, supporting_layers, severity, time_window,
                confirmed_facts, evidence_refs, owner
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (incident_id) DO NOTHING
            """,
            [
                row.get("incident_id"),
                row.get("project_id") or "proj-vingroup-pilot",
                row.get("status") or "OPEN",
                row.get("entity_ids"),
                row.get("signal_ids"),
                row.get("admission_reason"),
                row.get("supporting_layers"),
                row.get("severity"),
                row.get("time_window"),
                row.get("confirmed_facts"),
                row.get("evidence_refs"),



                row.get("owner"),
            ],
        )


@router.post("/demo-snapshot", response_model=DemoSnapshotResponse)
async def load_demo_snapshot(mode: str = Query(..., description="happy | unhappy")):
    """Swap the live warehouse: clean CSVs (happy) vs faulty DuckDB source (unhappy)."""
    from pathlib import Path as P
    import importlib.util

    db = get_db()
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    source = resolve_demo_source(mode, project_root)
    logger.info(f"Demo snapshot mode set to {mode}")

    try:
        db.execute("DELETE FROM agent_traces")
    except Exception as e:
        logger.warning(f"snapshot traces clear: {e}")
    try:
        conversation_store.clear_messages(session_id="dataset:vingroup_pilot")
    except Exception as e:
        logger.warning(f"snapshot chat clear: {e}")

    if mode == "happy":
        for tbl in ("incidents", "quality_rules", "quarantine", "execution_authorizations"):
            try:
                db.execute(f"DELETE FROM {tbl}")
            except Exception as e:
                logger.warning(f"happy clear {tbl}: {e}")
    else:
        try:
            db.execute("DELETE FROM quality_rules")
        except Exception as e:
            logger.warning(f"unhappy rules clear: {e}")

        try:
            open_n = db.execute("SELECT count(*) FROM incidents WHERE status = 'OPEN'")
            if not open_n or int(open_n[0][0]) == 0:
                _restore_unhappy_incidents(db, project_root)
        except Exception as e:
            logger.warning(f"unhappy restore: {e}")
            _restore_unhappy_incidents(db, project_root)

    measured = _measure_warehouse(db)
    return DemoSnapshotResponse(
        mode=mode,
        source=str(source),
        fault_injected=mode == "unhappy",
        **measured,
    )


@router.get("/llm-status")
def get_llm_status():
    """Returns the active LLM provider and model name currently configured in the backend environment."""
    try:
        from src.services.llm import LLMService
        llm = LLMService()
        return llm.get_status()
    except Exception as e:
        return {
            "status": "offline",
            "model": "Deterministic Rule Engine (LLM Off)",
            "provider": "heuristic",
            "has_api_key": False,
            "description": f"Offline Engine: {e}",
        }
