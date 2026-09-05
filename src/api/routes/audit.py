from typing import Any

from fastapi import APIRouter, Query

from src.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[dict[str, Any]])
def list_audit_trail(
    limit: int = 50,
    action: str | None = None,
    actor: str | None = None,
    target_table: str | None = None,
    target_id: str | None = None,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
):
    """
    Retrieve SHA-256 hash-chained audit trail entries.
    """
    audit = AuditService()
    entries = audit.get_history(
        limit=limit,
        action=action,
        actor=actor,
        target_table=target_table,
        target_id=target_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return entries
