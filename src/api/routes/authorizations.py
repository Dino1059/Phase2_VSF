from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(prefix="/authorizations", tags=["authorizations"])


@router.get("", response_model=List[Dict[str, Any]])
def list_authorizations():
    """
    List valid execution authorizations.
    """
    return [
        {
            "authorization_id": "auth-sample-001",
            "control_id": "ctrl-01",
            "version": 1,
            "authorized_actor": "data_steward_primary",
            "payload_hash": "a1b2c3d4e5f6...",
            "status": "VALID"
        }
    ]
