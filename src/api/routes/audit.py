from fastapi import APIRouter
from typing import List, Dict, Any
from src.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=List[Dict[str, Any]])
def list_audit_trail(limit: int = 50):
    """
    Retrieve SHA-256 hash-chained audit trail entries.
    """
    audit = AuditService()
    entries = audit.get_history(limit=limit)
    return entries
