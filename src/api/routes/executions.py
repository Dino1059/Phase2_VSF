from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
import pandas as pd

from src.api.middleware import check_user_role
from src.api.state_machine import WorkflowState
from src.api.routes import state_machine, audit_store
from src.models.schemas import ExecuteTransformRequest, ExecuteTransformResponse
from src.tools.compiler import Compiler
from src.tools.executor import Executor
from src.tools.validator import RuleSpec


router = APIRouter(prefix="/executions", tags=["executions"], dependencies=[Depends(check_user_role)])
compiler = Compiler()
executor = Executor()


@router.post("/transform", response_model=ExecuteTransformResponse)
async def execute_transform_endpoint(
    request: ExecuteTransformRequest,
) -> ExecuteTransformResponse:
    from src.db.connection import get_db

    db = get_db()
    for r in request.rules:
        if r.rule_id:
            rows = db.execute("SELECT status FROM quality_rules WHERE id = ?", [r.rule_id])
            if not rows or rows[0][0] not in ("approved", "edited"):
                raise HTTPException(
                    status_code=403,
                    detail="Rule execution denied: Rule is not approved by HITL",
                )

    try:
        df = pd.DataFrame(request.data)
        rules_spec = [
            RuleSpec(
                rule_id=r.rule_id,
                rule_type=r.rule_type,
                target_column=r.target_column,
                action=r.action,
                parameters=r.parameters,
                severity=r.severity,
                description=r.description,
            )
            for r in request.rules
        ]

        plan = compiler.compile(rules_spec)
        clean_df, q_df, manifest = executor.execute(df, plan)

        if state_machine.current_state in (
            WorkflowState.RULES_PROPOSED,
            WorkflowState.COMPILED,
            WorkflowState.TESTED,
            WorkflowState.HITL_REVIEWED,
        ):
            if state_machine.current_state in (
                WorkflowState.RULES_PROPOSED,
                WorkflowState.COMPILED,
            ):
                state_machine.transition_to(WorkflowState.HITL_REVIEWED)
            if state_machine.current_state in (
                WorkflowState.TESTED,
                WorkflowState.HITL_REVIEWED,
            ):
                state_machine.transition_to(WorkflowState.EXECUTED)
                state_machine.transition_to(WorkflowState.COMPLETED)

        audit_store.record_event(
            "execution",
            {
                "initial_rows": manifest.initial_rows,
                "clean_rows": manifest.clean_rows,
                "quarantine_rows": manifest.quarantine_rows,
                "time_sec": manifest.execution_time_sec,
            },
        )

        return ExecuteTransformResponse(
            initial_rows=manifest.initial_rows,
            clean_rows=manifest.clean_rows,
            quarantine_rows=manifest.quarantine_rows,
            execution_time_sec=manifest.execution_time_sec,
            quarantine_summary=manifest.quarantine_summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
@router.post("/")
async def execute_endpoint(request: Request, payload: Optional[dict] = None):
    rule_id = (
        (payload or {}).get("rule_id") if payload else request.query_params.get("rule_id")
    )
    from src.db.connection import get_db

    db = get_db()
    if rule_id:
        rows = db.execute("SELECT status FROM quality_rules WHERE id = ?", [rule_id])
        if not rows or rows[0][0] not in ("approved", "edited"):
            raise HTTPException(
                status_code=403, detail="Rule execution denied: Rule is not approved by HITL"
            )
    else:
        unapproved = db.execute(
            "SELECT id FROM quality_rules WHERE status NOT IN ('approved', 'edited')"
        )
        if unapproved:
            raise HTTPException(
                status_code=403, detail="Rule execution denied: Rule is not approved by HITL"
            )
    return {"status": "executed", "rule_id": rule_id}


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
async def list_executions() -> List[Dict[str, Any]]:
    records = audit_store.get_records()
    return [
        r.model_dump()
        for r in records
        if r.event_type in ("execution", "transform", "profile_async")
    ]
