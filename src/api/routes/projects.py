from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[Dict[str, Any]])
def list_projects():
    """
    List active fleet & data reliability projects.
    """
    return [
        {
            "project_id": "proj-vingroup-pilot",
            "name": "Vingroup Faulty Fleet Pilot",
            "status": "ACTIVE",
            "provenance": "SEMI_SYNTHETIC",
            "entities_count": 30,
            "stations_count": 4,
            "datasets": ["vinfast_bms", "xanhsm_trips", "vgreen_telemetry", "xanhsm_feedback"]
        }
    ]
