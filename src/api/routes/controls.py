from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from src.reliability.governance.preventive_controls import global_control_manager as manager

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_controls():
    """
    List all preventive controls.
    """
    ctrls = manager.list_controls()
    return [c.model_dump(mode="json") for c in ctrls]


@router.get("/{control_id}", response_model=Dict[str, Any])
def get_control(control_id: str):
    """
    Retrieve details of a specific control by ID.
    """
    ctrl = manager.get_control(control_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail=f"Control '{control_id}' not found")
    return ctrl.model_dump(mode="json")


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
