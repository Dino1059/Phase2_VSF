import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
import pandas as pd
from pydantic import BaseModel

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.api.middleware import check_user_role
from src.api.routes import audit_store, state_machine
from src.api.state_machine import WorkflowState
from src.models.schemas import ProposeRulesRequest, ProposeRulesResponse, RuleSchema


router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(check_user_role)])


class CreateRuleRequest(BaseModel):
    rule_type: str
    target_column: str
    action: str = "quarantine"
    parameters: Optional[Dict[str, Any]] = None
    severity: str = "warning"
    description: Optional[str] = None


@router.post("/propose", response_model=ProposeRulesResponse)
async def propose_rules_endpoint(request: ProposeRulesRequest) -> ProposeRulesResponse:
    try:
        df = (
            pd.DataFrame(request.data)
            if request.data
            else pd.DataFrame([{"hvfhs_license_num": "HV0003", "driver_pay": 15.0}])
        )
        variant = request.variant.upper()

        if variant == "C0":
            runner = C0Baseline()
        elif variant == "C1":
            runner = C1Baseline()
        else:
            runner = A1Agent()

        result = runner.run(df)
        rules_out = [
            RuleSchema(
                rule_id=r.rule_id,
                rule_type=r.rule_type,
                target_column=r.target_column,
                action=r.action,
                parameters=r.parameters,
                severity=r.severity,
                description=r.description,
            )
            for r in result.rules_proposed
        ]

        state_machine.proposed_rules_count = len(rules_out)
        if state_machine.current_state == WorkflowState.PROFILED:
            state_machine.transition_to(WorkflowState.RULES_PROPOSED)

        audit_store.record_event(
            "rule_proposal",
            {"variant": variant, "rules_count": len(rules_out), "cost_usd": result.cost_usd},
        )

        return ProposeRulesResponse(
            variant=variant,
            rules=rules_out,
            reasoning=f"Generated {len(rules_out)} rules using variant {variant}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
async def list_rules():
    from src.db.connection import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, rule_type, rule_name, status, rule_expression FROM quality_rules"
        )
        return [
            {
                "id": r[0],
                "rule_type": r[1],
                "rule_name": r[2],
                "status": r[3],
                "description": r[4],
            }
            for r in rows
        ]
    except Exception:
        return []


@router.post("")
@router.post("/")
async def create_rule(request: CreateRuleRequest):
    from src.db.connection import get_db

    db = get_db()
    rule_id = f"rule_{uuid.uuid4().hex[:8]}"
    rule_name = f"{request.rule_type}_{request.target_column}"
    expr = request.description or f"CHECK({request.target_column})"
    try:
        db.execute(
            """INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            [rule_id, rule_name, request.rule_type, expr],
        )
        return {"status": "created", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    from src.db.connection import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, rule_type, rule_name, status, rule_expression FROM quality_rules WHERE id = ?",
            [rule_id],
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
        r = rows[0]
        return {
            "id": r[0],
            "rule_type": r[1],
            "rule_name": r[2],
            "status": r[3],
            "description": r[4],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    from src.db.connection import get_db

    db = get_db()
    try:
        db.execute("DELETE FROM quality_rules WHERE id = ?", [rule_id])
        return {"status": "deleted", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
