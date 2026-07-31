import time
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
import pandas as pd

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.api.audit_store import AuditStore
from src.api.state_machine import StateMachine, WorkflowState
from src.models.schemas import (
    ChatRequest,
    ChatResponse,
    ExecuteTransformRequest,
    ExecuteTransformResponse,
    ProfileRequest,
    ProfileResponse,
    ProposeRulesRequest,
    ProposeRulesResponse,
    ResetResponse,
    RuleSchema,
)
from src.tools.compiler import Compiler
from src.tools.executor import Executor
from src.tools.profiler import Profiler
from src.tools.validator import RuleSpec

router = APIRouter()

# Global in-memory state for API demo
state_machine = StateMachine()
audit_store = AuditStore()
profiler = Profiler()
compiler = Compiler()
executor = Executor()


@router.post("/profile", response_model=ProfileResponse)
async def profile_endpoint(request: ProfileRequest) -> ProfileResponse:
    try:
        df = pd.DataFrame(request.data)
        report = profiler.profile(df)
        state_machine.row_count = report.row_count

        if state_machine.current_state == WorkflowState.INIT:
            state_machine.transition_to(WorkflowState.PROFILED)

        audit_store.record_event("profile", {"row_count": report.row_count, "column_count": report.column_count})

        return ProfileResponse(
            snapshot_id=report.snapshot_id,
            row_count=report.row_count,
            column_count=report.column_count,
            duplicate_count=report.duplicate_count,
            columns=[c.model_dump() for c in report.columns],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/propose", response_model=ProposeRulesResponse)
async def propose_rules_endpoint(request: ProposeRulesRequest) -> ProposeRulesResponse:
    try:
        df = pd.DataFrame(request.data) if request.data else pd.DataFrame([{"hvfhs_license_num": "HV0003", "driver_pay": 15.0}])
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
            "rule_proposal", {"variant": variant, "rules_count": len(rules_out), "cost_usd": result.cost_usd}
        )

        return ProposeRulesResponse(
            variant=variant,
            rules=rules_out,
            reasoning=f"Generated {len(rules_out)} rules using variant {variant}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transform/execute", response_model=ExecuteTransformResponse)
async def execute_transform_endpoint(request: ExecuteTransformRequest) -> ExecuteTransformResponse:
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

        if state_machine.current_state in (WorkflowState.RULES_PROPOSED, WorkflowState.HITL_REVIEWED):
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/store")
async def get_audit_store() -> List[Dict[str, Any]]:
    return [r.model_dump() for r in audit_store.get_records()]


@router.post("/reset", response_model=ResetResponse)
async def reset_endpoint() -> ResetResponse:
    t0 = time.time()
    state_machine.reset()
    audit_store.clear()
    dt = time.time() - t0
    return ResetResponse(status="success", message="Reset complete", reset_time_sec=round(dt, 4))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return ChatResponse(
            response=f"DataTrust Agent received: '{request.message}'. Current workflow state is {state_machine.current_state.value}.",
            analysis="Agent is operating within bounded execution framework.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def agent_status():
    return {
        "status": "ready",
        "agent": "DataTrust OS Agent v1.0",
        "state": state_machine.current_state.value,
        "audit_events_count": len(audit_store.get_records()),
    }
