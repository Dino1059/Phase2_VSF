from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from src.reliability.governance.preventive_controls import PreventiveControlManager

router = APIRouter(prefix="/controls", tags=["controls"])
manager = PreventiveControlManager()


@router.post("/propose", response_model=Dict[str, Any])
def propose_control(payload: Dict[str, Any] = Body(...)):
    """
    Propose a new preventive Data Quality control.
    """
    ctrl = manager.propose_control(
        control_id=payload["control_id"],
        rule_type=payload.get("rule_type", "range"),
        rule_expression=payload["rule_expression"],
        target_table=payload["target_table"],
        target_column=payload["target_column"]
    )
    return ctrl.model_dump(mode="json")


@router.post("/{control_id}/approve", response_model=Dict[str, Any])
def approve_control(control_id: str, actor: str = Body(..., embed=True)):
    """
    HITL approval for a control proposal. Generates execution authorization.
    """
    try:
        auth = manager.approve_control(control_id, actor)
        return auth.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
