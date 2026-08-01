import json
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
import pandas as pd

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.api.audit_store import AuditStore
from src.api.state_machine import StateMachine, WorkflowState
from src.models.schemas import (
    AlertCreateRequest,
    AnomalyDetectRequest,
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
    ScheduleCreate,
    ScheduleResponse,
    WebhookDispatchRequest,
)
from src.services.alerting import alert_service
from src.services.conversation_store import conversation_store
from src.services.scheduler import scheduler_service
from src.services.ws_manager import ws_manager
from src.tools.anomaly import AnomalyDetector
from src.tools.compiler import Compiler
from src.tools.executor import Executor
from src.tools.profiler import Profiler
from src.tools.validator import RuleSpec


async def check_user_role(request: Request, x_user_role: Optional[str] = Header(None, alias="X-User-Role")):
    """Middleware dependency for X-User-Role role-based access control."""
    role = (x_user_role or "Admin").strip().capitalize()
    valid_roles = {"Admin", "Steward", "Viewer"}
    if role not in valid_roles:
        role = "Admin"

    request.state.user_role = role
    method = request.method.upper()
    path = request.url.path

    if role == "Viewer":
        if method not in ("GET", "HEAD", "OPTIONS"):
            raise HTTPException(
                status_code=403,
                detail=f"Role 'Viewer' has read-only access. '{method}' operation is forbidden.",
            )

    if role == "Steward":
        if method == "DELETE" or path.rstrip("/").endswith("/reset"):
            raise HTTPException(
                status_code=403,
                detail=f"Role 'Steward' does not have permission for administrative operation.",
            )

    return role


router = APIRouter(dependencies=[Depends(check_user_role)])

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


# --- Scheduler API Routes ---
@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule_endpoint(request: ScheduleCreate) -> ScheduleResponse:
    try:
        sched = scheduler_service.add_schedule(
            name=request.name,
            dataset_name=request.dataset_name,
            schedule_type=request.schedule_type,
            interval_seconds=request.interval_seconds,
            cron_expression=request.cron_expression,
            action=request.action,
        )
        return ScheduleResponse(**sched)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules", response_model=List[ScheduleResponse])
async def get_schedules_endpoint() -> List[ScheduleResponse]:
    schedules = scheduler_service.get_schedules()
    return [ScheduleResponse(**s) for s in schedules]


@router.delete("/schedules/{id}")
async def delete_schedule_endpoint(id: str):
    success = scheduler_service.delete_schedule(id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Schedule '{id}' not found.")
    return {"status": "success", "message": f"Schedule '{id}' deleted successfully."}


# --- Anomaly Detector API Routes ---
@router.post("/anomalies/detect")
async def detect_anomalies_endpoint(request: AnomalyDetectRequest):
    try:
        detector = AnomalyDetector()
        result = detector.detect_all(
            current_profile=request.current_profile,
            historical_profiles=request.historical_profiles,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Alerting & Notification API Routes ---
@router.get("/alerts")
async def get_alerts_endpoint(severity: Optional[str] = None, status: Optional[str] = None):
    alerts = alert_service.get_alerts(severity=severity, status=status)
    return [a.model_dump() for a in alerts]


@router.post("/alerts")
async def create_alert_endpoint(request: AlertCreateRequest):
    try:
        alert = alert_service.create_alert(
            title=request.title,
            message=request.message,
            severity=request.severity,
            source=request.source,
            webhook_url=request.webhook_url,
            root_cause=request.root_cause,
            metadata=request.metadata,
        )
        return alert.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{id}/acknowledge")
async def acknowledge_alert_endpoint(id: str):
    alert = alert_service.acknowledge_alert(id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{id}' not found.")
    return alert.model_dump()


@router.post("/alerts/{id}/resolve")
async def resolve_alert_endpoint(id: str):
    alert = alert_service.resolve_alert(id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{id}' not found.")
    return alert.model_dump()


@router.post("/alerts/dispatch-webhook")
async def dispatch_webhook_endpoint(request: WebhookDispatchRequest):
    if request.alert_id:
        target_alert = alert_service.get_alert(request.alert_id)
        if not target_alert:
            raise HTTPException(status_code=404, detail=f"Alert '{request.alert_id}' not found.")
    else:
        alerts = alert_service.get_alerts()
        if not alerts:
            target_alert = alert_service.create_alert(
                title="Webhook Dispatch Verification",
                message="Test payload dispatch for alert webhook service.",
                severity="LOW",
                webhook_url=request.webhook_url,
                auto_dispatch=False,
            )
        else:
            target_alert = alerts[0]

    success = alert_service.dispatch_webhook(target_alert, webhook_url=request.webhook_url)
    return {
        "status": "success" if success else "failed",
        "alert_id": target_alert.alert_id,
        "webhook_url": request.webhook_url or target_alert.webhook_url,
    }


# === Dataset Registry Endpoints ===


def _sanitize_nans(val: Any) -> Any:
    import math
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, dict):
        return {k: _sanitize_nans(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_nans(v) for v in val]
    return val


@router.get("/datasets")
async def list_datasets():
    """List all registered datasets."""
    try:
        import os
        from src.config import get_settings

        settings = get_settings()
        result = []
        for key, path in settings.dataset_registry.items():
            full_path = settings.get_dataset_path(key)
            exists = os.path.exists(full_path)
            size_mb = os.path.getsize(full_path) / 1024**2 if exists else 0
            result.append({"key": key, "path": path, "exists": exists, "size_mb": round(size_mb, 1)})
        return {"datasets": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/{dataset_key}/profile")
async def profile_dataset(dataset_key: str, sample_size: int = 100_000):
    """Profile a registered dataset with server-side file loading."""
    try:
        from src.services.dataset_engine import load_dataset
        from src.tools.profiler import Profiler

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        profiler = Profiler()
        result = profiler.profile(df, file_path=dataset_key)
        profile_data = result.model_dump() if hasattr(result, "model_dump") else result.model_dump()
        return {
            "dataset": dataset_key,
            "sample_size": len(df),
            "profile": _sanitize_nans(profile_data),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/{dataset_key}/propose")
async def propose_rules_for_dataset(
    dataset_key: str,
    variant: str = "A1",
    sample_size: int = 100_000,
):
    """Propose data quality rules for a registered dataset."""
    try:
        from src.services.dataset_engine import (
            generate_rules_for_baseline,
            load_dataset,
            profile_rows,
        )

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        profile_data = profile_rows(df.to_dict("records"))
        rules, duration = generate_rules_for_baseline(variant, profile_data)
        return {
            "dataset": dataset_key,
            "variant": variant,
            "rules_count": len(rules),
            "rules": _sanitize_nans(rules),
            "generation_time_seconds": round(duration, 3),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/{dataset_key}/execute")
async def execute_rules_on_dataset(
    dataset_key: str,
    sample_size: Optional[int] = None,
):
    """Execute proposed rules on a dataset, returning clean/quarantine split."""
    try:
        from src.services.dataset_engine import (
            execute_compiled_rules,
            generate_rules_for_baseline,
            load_dataset,
            profile_rows,
        )

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        rows = df.to_dict("records")
        profile_data = profile_rows(rows)
        rules, _ = generate_rules_for_baseline("A1", profile_data)
        result = execute_compiled_rules(rows, rules)
        clean_result = _sanitize_nans(result)
        return {
            "dataset": dataset_key,
            "input_rows": len(rows),
            "clean_rows": clean_result.get("clean_count", 0),
            "quarantine_rows": clean_result.get("quarantine_count", 0),
            "rules_applied": len(rules),
            "execution_result": clean_result,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/{dataset_key}/benchmark")
async def benchmark_dataset(dataset_key: str, sample_size: int = 50_000):
    """Run C0 vs C1 vs A1 benchmark on a dataset."""
    try:
        from src.services.dataset_engine import load_dataset

        try:
            from eval.benchmark import BenchmarkHarness
            from eval.injector import ErrorInjector
        except ImportError as ie:
            raise HTTPException(status_code=500, detail=f"Benchmark import failed: {str(ie)}")

        df = load_dataset(dataset_key=dataset_key, sample_size=sample_size)
        injector = ErrorInjector(seed=42)
        datasets = injector.generate_datasets(df)
        harness = BenchmarkHarness()
        results = harness.run_benchmark(datasets)
        return {
            "dataset": dataset_key,
            "sample_size": len(df),
            "results": _sanitize_nans(results),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === WebSocket & Chat Endpoints ===

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process incoming socket commands if needed
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@router.post("/chat/send")
async def send_chat_message(request: ChatRequest):
    """Process user chat command, run AI agent orchestrator, broadcast events, and return agent response."""
    user_msg = conversation_store.save_message({
        "type": "user",
        "content": request.message,
    })

    # Broadcast user message via WS
    await ws_manager.broadcast({
        "type": "chat.message",
        "data": user_msg
    })

    command = request.message.lower()

    # Determine command action and invoke engine/tools
    if "profile" in command:
        # Notify profiler starting
        await ws_manager.broadcast({
            "type": "agent.status",
            "agent": "profiler",
            "status": "working"
        })
        
        from src.services.dataset_engine import load_dataset, profile_rows
        df = load_dataset()
        profile_data = profile_rows(df.to_dict('records'))

        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": "profiler",
            "content": f"Scanned {len(df)} rows and analyzed {len(df.columns)} columns. Generated dataset profile.",
            "metadata": {"profile": profile_data}
        })

        await ws_manager.broadcast({
            "type": "agent.status",
            "agent": "profiler",
            "status": "done"
        })

        await ws_manager.broadcast({
            "type": "workspace.update",
            "panel": "profile",
            "data": {
                "totalRows": len(df),
                "columns": [
                    {
                        "name": col,
                        "type": str(df[col].dtype),
                        "nullRate": float(df[col].isnull().mean()),
                        "uniqueRate": float(df[col].nunique() / max(len(df), 1)),
                        "health": "healthy" if df[col].isnull().mean() < 0.05 else ("warning" if df[col].isnull().mean() < 0.2 else "critical")
                    }
                    for col in df.columns
                ]
            }
        })

        return ChatResponse(
            response=agent_msg["content"],
            state="PROFILED",
            agent_execution={"agent": "profiler", "profile": profile_data}
        )

    elif "rule" in command or "propose" in command:
        await ws_manager.broadcast({
            "type": "agent.status",
            "agent": "ruleProposer",
            "status": "working"
        })

        from src.services.dataset_engine import load_dataset, generate_rules_for_baseline, profile_rows
        df = load_dataset()
        profile_data = profile_rows(df.to_dict('records'))
        rules, _ = generate_rules_for_baseline("A1", profile_data)

        proposals = []
        for i, r in enumerate(rules):
            proposals.append({
                "id": f"prop_{i+1}",
                "type": r.get("rule_type", "range_check"),
                "column": r.get("column", "column"),
                "expression": r.get("expression", "val != null"),
                "description": r.get("description", f"Quality check for {r.get('column')}"),
                "severity": r.get("severity", "warning"),
                "status": "pending",
                "agentId": "ruleProposer"
            })

        agent_msg = conversation_store.save_message({
            "type": "proposal",
            "agentId": "ruleProposer",
            "content": f"Proposed {len(proposals)} data quality rules for governance review.",
            "metadata": {"proposals": proposals}
        })

        await ws_manager.broadcast({
            "type": "agent.status",
            "agent": "ruleProposer",
            "status": "done"
        })

        await ws_manager.broadcast({
            "type": "agent.proposal",
            "proposals": proposals
        })

        await ws_manager.broadcast({
            "type": "workspace.update",
            "panel": "rules",
            "data": proposals
        })

        return ChatResponse(
            response=agent_msg["content"],
            state="RULES_PROPOSED",
            agent_execution={"agent": "ruleProposer", "proposals": proposals}
        )

    else:
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": "orchestrator",
            "content": f"Received command: '{request.message}'. You can try typing 'Profile dataset' or 'Propose rules'.",
        })

        return ChatResponse(
            response=agent_msg["content"],
            state="READY",
            agent_execution={"agent": "orchestrator"}
        )


@router.get("/chat/history")
async def get_chat_history(session_id: str = "default"):
    """Retrieve persisted chat messages."""
    return {"messages": conversation_store.get_messages(session_id=session_id)}



