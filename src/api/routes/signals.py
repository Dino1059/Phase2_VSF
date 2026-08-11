from fastapi import APIRouter, Query
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=List[Dict[str, Any]])
def list_signals(
    project_id: str = Query("proj-vingroup-pilot"),
    layer: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None)
):
    """
    List detected L1-L4 anomaly signals.
    """
    sample_signals = [
        {
            "signal_id": "sig-l1-001",
            "project_id": project_id,
            "entity_ids": [entity_id or "VIN-001"],
            "layer": "L1",
            "signal_type": "RANGE_VIOLATION",
            "metric_or_relationship": "battery_soc",
            "score": 1.0,
            "severity": "CRITICAL",
            "detector": "L1_Constraint_Detector",
            "provenance": "SEMI_SYNTHETIC"
        },
        {
            "signal_id": "sig-l2-002",
            "project_id": project_id,
            "entity_ids": [entity_id or "VIN-002"],
            "layer": "L2",
            "signal_type": "CONTEXTUAL_DRIFT",
            "metric_or_relationship": "discharge_rate",
            "score": 4.2,
            "severity": "HIGH",
            "detector": "L2_Contextual_Detector",
            "provenance": "SEMI_SYNTHETIC"
        }
    ]

    if layer:
        return [s for s in sample_signals if s["layer"] == layer]
    return sample_signals
