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
    reload_warehouse: bool = Query(True, description="Reload raw.* tables from data_new CSVs"),
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
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    cleared = []
    tables_to_clear = [
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
    ]

    for tbl in tables_to_clear:
        try:
            db.execute(f"DELETE FROM {tbl}")
            cleared.append(tbl)
        except Exception as e:
            logger.warning(f"Could not clear table {tbl}: {e}")

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

    # 3. Reload VinGroup warehouse from data_new (same live DuckDB connection)
    reloaded = {}
    if reload_warehouse:
        try:
            import importlib.util
            from pathlib import Path
            ingest_py = os.path.join(project_root, "data_new", "Ingestion", "ingest_vingroup_pilot_to_duckdb.py")
            spec = importlib.util.spec_from_file_location("vingroup_ingest", ingest_py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            source = Path(mod.DEFAULT_SOURCE)
            live_con = db._get_master_conn()
            mod.ingest(source, Path(db.db_path), con=live_con)
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

    charging = _count("SELECT count(DISTINCT session_id) FROM raw.charging_sessions")
    if charging == 0:
        charging = _count("SELECT count(DISTINCT session_id) FROM vgreen_charging_sessions")
    return {
        "telemetry": _count("SELECT count(*) FROM raw.ev_telemetry"),
        "charging_sessions": charging,
        "trips": _count("SELECT count(*) FROM raw.trips"),
        "soc_below_zero": _count("SELECT count(*) FROM raw.ev_telemetry WHERE battery_soc < 0"),
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
    ingest_py = os.path.join(project_root, "data_new", "Ingestion", "ingest_vingroup_pilot_to_duckdb.py")
    spec = importlib.util.spec_from_file_location("vingroup_ingest", ingest_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    live_con = db._get_master_conn()
    mod.ingest(source, P(db.db_path), con=live_con)

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
