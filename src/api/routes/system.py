import logging
import subprocess
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
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


@router.post("/reset-all", response_model=ResetAllResponse)
async def reset_all_db(authorization: Optional[str] = Header(None)):
    """Admin-only full system reset: purges runtime rules/quarantine/audit and restores clean VinGroup baseline."""
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
    except Exception:
        pass

    # 1c. Clear Algolia search index to eliminate ghost .db records
    try:
        from src.services.algolia_search import AlgoliaSearchService
        algolia_service = AlgoliaSearchService()
        algolia_service.clear_index()
    except Exception as e:
        logger.warning(f"Could not clear Algolia index: {e}")

    # 2. Reset conversation memory & prompt injection caches
    try:
        if hasattr(conversation_store, "clear_all"):
            conversation_store.clear_all()
        elif hasattr(conversation_store, "sessions"):
            conversation_store.sessions.clear()
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
    try:
        row_counts = {}
        for tbl in ["raw.ev_telemetry", "raw.charging_sessions", "raw.trips", "raw.fault_manifest"]:
            try:
                res = db.execute(f"SELECT count(*) FROM {tbl}").fetchone()
                row_counts[tbl] = res[0] if res else 0
            except Exception:
                row_counts[tbl] = 0
        reloaded = row_counts
    except Exception as e:
        logger.warning(f"Error checking row counts: {e}")

    return ResetAllResponse(
        status="success",
        message="System database, rules, audit logs, and conversation memory successfully reset.",
        cleared_tables=cleared,
        reloaded_records=reloaded,
    )



