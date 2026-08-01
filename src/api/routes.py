import json
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, File, UploadFile
import pandas as pd
from pydantic import BaseModel

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.agents.react import BoundedReActEngine
from src.api.audit_store import AuditStore
from src.api.state_machine import StateMachine, WorkflowState
from src.models.schemas import (
    AlertCreateRequest,
    AnomalyDetectRequest,
    ChatRequest,
    ChatResponse,
    DecisionObject,
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
from src.services.llm import LLMService
from src.services.scheduler import scheduler_service
from src.services.ws_manager import ws_manager
from src.tools.anomaly import AnomalyDetector
from src.tools.compiler import Compiler
from src.tools.executor import Executor
from src.tools.profiler import Profiler
from src.tools.validator import RuleSpec


async def check_user_role(request: Request):
    """Middleware dependency for X-User-Role role-based access control."""
    if request.scope.get("type") == "websocket":
        return "Admin"

    x_user_role = request.headers.get("X-User-Role")
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

        if state_machine.current_state in (WorkflowState.RULES_PROPOSED, WorkflowState.COMPILED, WorkflowState.TESTED, WorkflowState.HITL_REVIEWED):
            if state_machine.current_state in (WorkflowState.RULES_PROPOSED, WorkflowState.COMPILED):
                state_machine.transition_to(WorkflowState.HITL_REVIEWED)
            if state_machine.current_state in (WorkflowState.TESTED, WorkflowState.HITL_REVIEWED):
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

ws_router = APIRouter()


@ws_router.websocket("/ws")
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
    """Process user chat command using True Agentic Multi-Agent Function Calling LLM Orchestrator."""
    session_id = request.session_id or "default"
    user_msg = conversation_store.save_message({
        "type": "user",
        "content": request.message,
    }, session_id=session_id)

    # Broadcast user message via WS
    await ws_manager.broadcast({
        "type": "chat.message",
        "data": user_msg
    })

    # Broadcast working status
    await ws_manager.broadcast({
        "type": "agent.status",
        "agent": "orchestrator",
        "status": "working"
    })

    llm_service = LLMService()
    react_engine = BoundedReActEngine(llm_service=llm_service)
    command = request.message.lower()

    # Determine default/inferred dataset key from context
    dataset_key = "vietnam_trips_dirty"
    if "nyc" in command or "fhvhv" in command or "taxi" in command:
        dataset_key = "nyc_fhvhv"
    elif "clean" in command:
        dataset_key = "vietnam_trips"
    elif "weather" in command:
        dataset_key = "weather_hcmc"
    elif "grab" in command or "sea" in command:
        dataset_key = "grab_sea_demand"

    GOVERNANCE_TOOLS = [
        {
            "name": "profile_dataset",
            "description": "Scans a dataset, computes null rates, column data types, distinct counts, and health score. Call this tool when user asks to profile or scan a dataset.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "dataset_key": {
                        "type": "STRING",
                        "description": "Target dataset key (defaults to vietnam_trips_dirty)"
                    }
                }
            }
        },
        {
            "name": "detect_anomalies",
            "description": "Detects statistical anomalies, z-score outliers, IQR anomalies, and schema drift. Call this tool when user asks to detect anomalies.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "dataset_key": {
                        "type": "STRING",
                        "description": "Target dataset key (defaults to vietnam_trips_dirty)"
                    }
                }
            }
        },
        {
            "name": "propose_quality_rules",
            "description": "Generates data quality rules and constraints for Human-In-The-Loop review. Call this tool when user asks to propose quality rules.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "dataset_key": {
                        "type": "STRING",
                        "description": "Target dataset key (defaults to vietnam_trips_dirty)"
                    }
                }
            }
        },
        {
            "name": "diagnose_root_cause",
            "description": "Performs root-cause analysis on corrupted rows, type mismatches, and data defects. Call this tool when user asks to diagnose root cause.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "dataset_key": {
                        "type": "STRING",
                        "description": "Target dataset key (defaults to vietnam_trips_dirty)"
                    }
                }
            }
        },
        {
            "name": "clean_database",
            "description": "Applies approved quality constraints, partitions corrupted rows into quarantine, and creates clean database with lineage trace and diff view. Call this tool when user asks for next step, clean db, apply rules, run clean pipeline, or proceed.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "dataset_key": {
                        "type": "STRING",
                        "description": "Target dataset key (defaults to active dataset)"
                    }
                }
            }
        },
        {
            "name": "list_datasets",
            "description": "Lists all available registered datasets in DataTrust OS repository. Use only when user specifically asks to list datasets or databases."
        }
    ]

    # Evaluate dynamic LLM Function Calling decision
    decision = llm_service.generate_agentic_tool_call(request.message, GOVERNANCE_TOOLS)
    tool_name = decision.get("name")
    tool_args = decision.get("args", {})
    target_key = tool_args.get("dataset_key") or dataset_key

    # Fallback to keyword matching if LLM returned text, fallback, or misdirected list_datasets
    if decision.get("type") != "function_call" or (tool_name == "list_datasets" and not any(k in command for k in ["list db", "show db", "databases", "how many", "list dataset", "dbs", "my db"])):
        if any(k in command for k in ["next step", "continue", "proceed", "clean db", "clean database", "run clean", "create clean", "apply rules", "partition"]):
            tool_name = "clean_database"
        elif "profile" in command or "scan" in command or "health" in command:
            tool_name = "profile_dataset"
        elif "anomal" in command or "outlier" in command or "drift" in command:
            tool_name = "detect_anomalies"
        elif "rule" in command or "propose" in command or "constraint" in command:
            tool_name = "propose_quality_rules"
        elif "diagnos" in command or "defect" in command or "problem" in command or "fault" in command or "issue" in command or "why" in command:
            tool_name = "diagnose_root_cause"
        elif any(k in command for k in ["list db", "show db", "databases", "list dataset", "show dataset", "my db"]):
            tool_name = "list_datasets"

    # Emit ReAct Thought message
    thought_str = decision.get("thought") or f"Thought: Evaluated intent using Gemma-4 Orchestrator. Directing to tool '{tool_name or 'general_qa'}'."
    thought_msg = conversation_store.save_message({
        "type": "agent",
        "agentId": "orchestrator",
        "content": thought_str,
    }, session_id=session_id)
    await ws_manager.broadcast({
        "type": "chat.message",
        "data": thought_msg
    })

    # --- AGENTIC TOOL EXECUTION BRANCHES ---
    if tool_name == "list_datasets":
        agent_id = "orchestrator"
        from src.config import get_settings
        settings = get_settings()
        ds_list = settings.list_available_datasets()

        obs_content = f"Observation: Found {len(ds_list)} registered datasets in DataTrust OS repository."
        obs_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": obs_content,
            "metadata": {"datasets": ds_list}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": obs_msg})

        summary_lines = [f"Available Datasets ({len(ds_list)}):"]
        for ds in ds_list:
            status = "Ready" if ds.get("exists") else "Missing"
            summary_lines.append(f"- **{ds.get('name')}** ({ds.get('key')}): {status} — Format: {ds.get('format').upper()} ({ds.get('size_mb', 0)} MB)")

        conclusion_content = "\n".join(summary_lines)
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": conclusion_content,
            "metadata": {"datasets": ds_list}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": agent_msg})
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})

        return ChatResponse(
            response=agent_msg["content"],
            analysis="ReAct Loop Completed: Thought -> Action (List Datasets) -> Observation -> Conclusion",
            state="READY",
            agent_execution={"agent": agent_id, "datasets": ds_list}
        )

    elif tool_name == "profile_dataset":
        agent_id = "profiler"
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "working"})
        from src.services.dataset_engine import load_dataset, profile_rows
        df = load_dataset(dataset_key=target_key)
        profile_data = profile_rows(df.to_dict("records"))

        obs_content = f"Observation: Scanned {len(df)} rows and analyzed {len(df.columns)} columns for '{target_key}'. Health Score: {profile_data.get('data_health_score', 100.0)}%."
        obs_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": obs_content,
            "metadata": {"profile": profile_data}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": obs_msg})

        conclusion_content = f"Scanned {len(df)} rows and analyzed {len(df.columns)} columns for '{target_key}'. Data Health Score: {profile_data.get('data_health_score', 100.0)}%."
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": conclusion_content,
            "metadata": {"profile": profile_data}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": agent_msg})
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})
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
                        "health": "healthy" if df[col].isnull().mean() < 0.05 else "warning"
                    }
                    for col in df.columns
                ]
            }
        })

        return ChatResponse(
            response=agent_msg["content"],
            analysis="ReAct Loop Completed: Thought -> Action (Profile) -> Observation -> Conclusion",
            state="PROFILED",
            agent_execution={"agent": agent_id, "profile": profile_data}
        )

    elif tool_name == "propose_quality_rules":
        agent_id = "ruleProposer"
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "working"})
        from src.services.dataset_engine import load_dataset, generate_rules_for_baseline, profile_rows
        df = load_dataset(dataset_key=target_key)
        profile_data = profile_rows(df.to_dict("records"))
        rules, _ = generate_rules_for_baseline("A1", profile_data)

        proposals = []
        for i, r in enumerate(rules):
            if isinstance(r, dict):
                rf = r.get("rule_type") or r.get("rule_family") or "range_check"
                col = r.get("column") or "dataset"
                expr = r.get("expression") or "val != null"
                desc = r.get("description") or f"Enforce {rf} constraint on {col}"
                sev = str(r.get("severity", "warning")).lower()
                rid = r.get("rule_id") or f"prop_{i+1}"
            else:
                rf = r.rule_family.value if hasattr(r.rule_family, "value") else str(r.rule_family)
                col = r.column or "dataset"
                expr = r.expression
                desc = f"Enforce {rf} constraint on {r.column or 'dataset'}"
                sev = r.severity.value.lower() if hasattr(r.severity, "value") else str(r.severity).lower()
                rid = r.rule_id

            if sev not in ["critical", "warning", "info"]:
                sev = "warning"
            proposals.append({
                "id": rid,
                "type": rf,
                "column": col,
                "expression": expr,
                "description": desc,
                "severity": sev,
                "status": "pending",
                "agentId": agent_id
            })

        proposals.insert(0, {
            "id": "rule_pipeline_declaration_gate",
            "type": "AUTONOMOUS_PIPELINE",
            "column": target_key,
            "expression": "RUN_CLEAN_DB_WORKFLOW",
            "description": f"Autonomous AI Data Governance Declaration: Auto-start next step upon acceptance until cleanDB is created for '{target_key}'.",
            "severity": "critical",
            "status": "pending",
            "agentId": agent_id
        })

        obs_content = f"Observation: Synthesized {len(proposals)} proposed quality constraints for dataset '{target_key}'."
        obs_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": obs_content,
            "metadata": {"proposals": proposals}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": obs_msg})

        conclusion_content = f"Synthesized {len(proposals)} data quality constraints for '{target_key}' governance review."
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": conclusion_content,
            "metadata": {"proposals": proposals}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": agent_msg})
        await ws_manager.broadcast({"type": "agent.proposal", "proposals": proposals})
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})
        await ws_manager.broadcast({"type": "workspace.update", "panel": "rules", "data": {"proposals": proposals}})

        return ChatResponse(
            response=agent_msg["content"],
            analysis="ReAct Loop Completed: Thought -> Action (Propose Rules) -> Observation -> Conclusion",
            state="RULES_PROPOSED",
            agent_execution={"agent": agent_id, "proposals": proposals}
        )

    elif tool_name == "detect_anomalies":
        agent_id = "anomalyDetector"
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "working"})
        from src.services.dataset_engine import load_dataset, profile_rows
        df = load_dataset(dataset_key=target_key)
        profile_data = profile_rows(df.to_dict("records"))

        anomaly_report = react_engine.detect_anomalies(current_profile=profile_data)
        anomaly_scan = anomaly_report.model_dump() if hasattr(anomaly_report, "model_dump") else (anomaly_report if isinstance(anomaly_report, dict) else {})
        
        # Extract statistical anomalies directly from DataFrame
        def detect_df_anomalies(df_in):
            import pandas as pd
            anoms = []
            tot = max(len(df_in), 1)
            for c in df_in.columns:
                nc = int(df_in[c].isnull().sum())
                nr = nc / tot
                if nr > 0.03:
                    anoms.append({
                        "column": str(c),
                        "anomaly_type": "null_pct_high",
                        "metric_name": "null_rate_check",
                        "description": f"Column '{c}' has high null rate of {nr*100:.1f}% ({nc} missing values)",
                        "severity": "critical" if nr > 0.1 else "warning",
                        "observed": f"{nr*100:.1f}% ({nc} nulls)",
                        "expected_bounds": "<= 3.0%",
                        "confidence": 0.95
                    })
                num_s = pd.to_numeric(df_in[c], errors="coerce")
                v_num = num_s.dropna()
                if len(v_num) > 0:
                    negs = v_num[v_num < 0]
                    if len(negs) > 0:
                        anoms.append({
                            "column": str(c),
                            "anomaly_type": "negative_value_check",
                            "metric_name": "min_value_check",
                            "description": f"Column '{c}' contains {len(negs)} negative values (min: {negs.min()})",
                            "severity": "critical",
                            "observed": str(negs.min()),
                            "expected_bounds": ">= 0.0",
                            "confidence": 0.98
                        })
                    if len(v_num) >= 5:
                        q1 = v_num.quantile(0.25)
                        q3 = v_num.quantile(0.75)
                        iqr = q3 - q1
                        if iqr > 0:
                            outs = v_num[(v_num < q1 - 1.5 * iqr) | (v_num > q3 + 3.0 * iqr)]
                            if len(outs) > 0:
                                anoms.append({
                                    "column": str(c),
                                    "anomaly_type": "iqr_outlier_check",
                                    "metric_name": "iqr_outlier_check",
                                    "description": f"Column '{c}' contains {len(outs)} statistical outliers via IQR (max: {outs.max()})",
                                    "severity": "warning",
                                    "observed": str(outs.max()),
                                    "expected_bounds": f"{q1 - 1.5*iqr:.1f} to {q3 + 1.5*iqr:.1f}",
                                    "confidence": 0.90
                                })
            return anoms

        df_anomalies = detect_df_anomalies(df)
        raw_llm = anomaly_scan.get("detected_anomalies") or anomaly_scan.get("anomalies") or []
        anomaly_list = df_anomalies + [a for a in raw_llm if isinstance(a, dict)]
        anomaly_scan["anomalies"] = anomaly_list
        anomaly_scan["detected_anomalies"] = anomaly_list

        obs_content = f"Observation: Scanned dataset '{target_key}' and detected {len(anomaly_list)} statistical anomalies (Z-Score, IQR, Isolation Forest)."
        obs_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": obs_content,
            "metadata": {"anomalies": anomaly_scan}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": obs_msg})

        conclusion_content = f"Detected {len(anomaly_list)} statistical outliers and schema anomalies in '{target_key}'."
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": conclusion_content,
            "metadata": {"anomalies": anomaly_scan}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": agent_msg})
        await ws_manager.broadcast({"type": "workspace.update", "panel": "anomaly", "data": {"anomalies": anomaly_list, "totalCount": len(anomaly_list)}})
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})

        # Check for multi-step workflow continuation (e.g. Detect anomalies AND propose quality rules)
        if any(k in command for k in ["propose", "rule", "pipeline", "accept", "clean", "run governance"]):
            rule_agent_id = "ruleProposer"
            await ws_manager.broadcast({"type": "agent.status", "agent": rule_agent_id, "status": "working"})
            from src.services.dataset_engine import generate_rules_for_baseline
            rules, _ = generate_rules_for_baseline("A1", profile_data)

            proposals = []
            for i, r in enumerate(rules):
                if isinstance(r, dict):
                    rf = r.get("rule_type") or r.get("rule_family") or "range_check"
                    col = r.get("column") or "dataset"
                    expr = r.get("expression") or "val != null"
                    desc = r.get("description") or f"Enforce {rf} constraint on {col}"
                    sev = str(r.get("severity", "warning")).lower()
                    rid = r.get("rule_id") or f"prop_{i+1}"
                else:
                    rf = r.rule_family.value if hasattr(r.rule_family, "value") else str(r.rule_family)
                    col = r.column or "dataset"
                    expr = r.expression
                    desc = f"Enforce {rf} constraint on {r.column or 'dataset'}"
                    sev = r.severity.value.lower() if hasattr(r.severity, "value") else str(r.severity).lower()
                    rid = r.rule_id

                if sev not in ["critical", "warning", "info"]:
                    sev = "warning"
                proposals.append({
                    "id": rid,
                    "type": rf,
                    "column": col,
                    "expression": expr,
                    "description": desc,
                    "severity": sev,
                    "status": "pending",
                    "agentId": rule_agent_id
                })

            obs_msg_rules = conversation_store.save_message({
                "type": "agent",
                "agentId": rule_agent_id,
                "content": f"Observation: Synthesized {len(proposals)} proposed quality constraints for dataset '{target_key}'.",
                "metadata": {"proposals": proposals}
            }, session_id=session_id)
            await ws_manager.broadcast({"type": "chat.message", "data": obs_msg_rules})
            await ws_manager.broadcast({"type": "agent.proposal", "proposals": proposals})
            await ws_manager.broadcast({"type": "agent.status", "agent": rule_agent_id, "status": "done"})
            await ws_manager.broadcast({"type": "workspace.update", "panel": "rules", "data": {"proposals": proposals}})

            return ChatResponse(
                response=f"{conclusion_content}\n\nSynthesized {len(proposals)} quality constraints for '{target_key}' governance review.",
                analysis="ReAct Continuation Completed: Anomaly Detection -> Rule Proposal",
                state="RULES_PROPOSED",
                agent_execution={"agent": rule_agent_id, "anomalies": anomaly_scan, "proposals": proposals}
            )

        return ChatResponse(
            response=agent_msg["content"],
            analysis="ReAct Loop Completed: Thought -> Action (Anomaly Detection) -> Observation -> Conclusion",
            state="ANOMALY_DETECTED",
            agent_execution={"agent": agent_id, "anomalies": anomaly_scan}
        )

    elif tool_name == "diagnose_root_cause":
        agent_id = "diagnosis"
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "working"})
        from src.services.dataset_engine import load_dataset, profile_rows
        df = load_dataset(dataset_key=target_key)
        profile_data = profile_rows(df.to_dict("records"))
        diag_report = react_engine.diagnose(data_profile=profile_data)

        conclusion_content = f"Root-cause diagnosis complete for '{target_key}'. Category: {diag_report.category}. Remediation: {diag_report.recommended_remediation}"
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": conclusion_content,
            "metadata": {"diagnosis": diag_report.model_dump()}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": agent_msg})
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})

        return ChatResponse(
            response=agent_msg["content"],
            analysis="ReAct Loop Completed: Thought -> Action (Diagnose) -> Observation -> Conclusion",
            state="DIAGNOSED",
            agent_execution={"agent": agent_id, "diagnosis": diag_report.model_dump()}
        )

    elif tool_name == "clean_database":
        agent_id = "orchestrator"
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "working"})
        from src.services.dataset_engine import load_dataset, profile_rows, generate_rules_for_baseline, execute_compiled_rules
        df = load_dataset(dataset_key=target_key)
        profile_data = profile_rows(df.to_dict("records"))
        rules, _ = generate_rules_for_baseline("A1", profile_data)

        clean_res = execute_compiled_rules(df.to_dict("records"), rules)
        clean_count = clean_res["clean_count"]
        quarantine_count = clean_res["quarantine_count"]
        manifest_hash = clean_res["manifest_hash"]

        obs_content = f"Observation: Partitioned dataset '{target_key}' into CleanDB ({clean_count:,} rows) and QuarantineTable ({quarantine_count:,} rows). Cryptographic SHA-256 Hash: `{manifest_hash[:16]}...`"
        obs_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": obs_content,
            "metadata": {"clean_res": clean_res}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": obs_msg})

        conclusion_content = (
            f"Autonomous Clean DB Pipeline Execution Complete for '{target_key}'!\n\n"
            f"- Clean DB Row Count: {clean_count:,} rows ({100.0 - clean_res['quarantine_rate']:.1f}% health score)\n"
            f"- Quarantined Rows: {quarantine_count:,} defect rows isolated\n"
            f"- Lineage Cryptographic SHA-256 Hash: `{manifest_hash[:16]}...`"
        )
        agent_msg = conversation_store.save_message({
            "type": "agent",
            "agentId": agent_id,
            "content": conclusion_content,
            "metadata": {"clean_res": clean_res}
        }, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": agent_msg})
        await ws_manager.broadcast({"type": "workspace.update", "panel": "diff", "data": {
            "dataset": target_key,
            "original_rows": len(df),
            "clean_rows": clean_count,
            "quarantined_rows": quarantine_count,
            "manifest_hash": manifest_hash,
            "quarantine_rate": clean_res["quarantine_rate"]
        }})
        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})

        return ChatResponse(
            response=agent_msg["content"],
            analysis="ReAct Loop Completed: Thought -> Action (Clean Database Pipeline) -> Observation -> Conclusion",
            state="CLEAN_DB_CREATED",
            agent_execution={"agent": agent_id, "clean_res": clean_res}
        )

    else:
        # Stream response for general chat / QA
        agent_id = "orchestrator"
        msg_id = f"msg_{int(time.time()*1000)}"

        system_prompt = (
            "You are DataTrust OS Orchestrator Agent powered by Gemma-4. "
            "Respond in clean, professional markdown without using any emojis, icons, or decorative symbols. "
            "Address the user's question directly, explain relevant multi-agent capabilities, and suggest logical next steps."
        )

        full_text = ""
        for item in llm_service.stream_text(prompt=request.message, system_prompt=system_prompt):
            if item.get("type") == "thought":
                await ws_manager.broadcast({"type": "chat.stream_thought", "id": msg_id, "delta": item["text"]})
            else:
                chunk = item.get("text", "")
                full_text += chunk
                await ws_manager.broadcast({"type": "chat.stream_chunk", "id": msg_id, "delta": chunk})

        agent_msg = conversation_store.save_message({
            "id": msg_id,
            "type": "agent",
            "agentId": agent_id,
            "content": full_text,
        }, session_id=session_id)

        await ws_manager.broadcast({"type": "agent.status", "agent": agent_id, "status": "done"})

        return ChatResponse(
            response=full_text,
            analysis="ReAct Loop Streaming Completed",
            state="READY",
            agent_execution={"agent": agent_id, "llm_reasoning": True}
        )


@router.get("/chat/history")
async def get_chat_history(session_id: str = "default"):
    """Retrieve persisted chat messages."""
    return {"messages": conversation_store.get_messages(session_id=session_id)}


@router.get("/chat/sessions")
async def get_chat_sessions():
    """Retrieve all chat sessions."""
    return {"sessions": conversation_store.list_sessions()}


class ClearChatRequest(BaseModel):
    session_id: Optional[str] = None


@router.post("/chat/clear")
async def clear_chat(req: ClearChatRequest):
    """Clear chat messages for a specific session or all sessions."""
    if req.session_id:
        conversation_store.clear_messages(session_id=req.session_id)
    else:
        conversation_store.clear_all()
    return {"status": "cleared", "session_id": req.session_id}


@router.post("/dataset/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload a database or data file (.parquet, .csv, .json, .jsonl, .sqlite, .db)
    and initiate autonomous AI governance declaration pipeline.
    """
    import os
    import shutil

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    clean_name = os.path.splitext(file.filename)[0].replace("-", "_").replace(" ", "_").lower()
    dataset_key = f"uploaded_{clean_name}"
    rel_path = os.path.relpath(file_path, base_dir)

    from src.config import get_settings
    settings = get_settings()
    settings.register_dataset(dataset_key, rel_path)

    # Load and profile uploaded dataset
    from src.tools.datasource import StructuredSource
    src = StructuredSource(file_path)
    df = src.load_data(sample_size=50_000)

    # Broadcast websocket notification & declaration card
    await ws_manager.broadcast({
        "type": "agent.status",
        "agent": "orchestrator",
        "status": "working"
    })

    declaration_content = (
        f"📥 **Uploaded & Registered Dataset**: `{file.filename}` ({file_size_mb} MB)\n\n"
        f"**Dataset Key**: `{dataset_key}` | **Schema**: {len(df.columns)} columns, {len(df):,} sampled rows.\n\n"
        f"⚖️ **Declaration & Permission Gate**:\n"
        f"Orchestrator Agent requests permission to initiate the **Autonomous Governance Pipeline** "
        f"(Profiling ➔ Anomaly Detection ➔ Diagnosis ➔ Rule Synthesis ➔ Clean DB Creation)."
    )

    msg = conversation_store.save_message({
        "type": "proposal",
        "agentId": "orchestrator",
        "content": declaration_content,
        "metadata": {
            "dataset_key": dataset_key,
            "filename": file.filename,
            "columns": list(df.columns),
            "total_rows": len(df),
            "proposals": [{
                "id": f"prop_upload_{dataset_key}",
                "type": "AUTONOMOUS_PIPELINE",
                "column": "dataset_pipeline",
                "expression": f"AUTONOMOUS_GOVERNANCE({dataset_key})",
                "description": f"Execute automated DataTrust OS cleaning pipeline for '{dataset_key}'",
                "severity": "info",
                "status": "pending",
                "agentId": "orchestrator"
            }]
        }
    })

    await ws_manager.broadcast({
        "type": "chat.message",
        "data": msg
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
                    "health": "healthy" if df[col].isnull().mean() < 0.05 else "warning"
                }
                for col in df.columns
            ]
        }
    })

    return {
        "status": "uploaded",
        "dataset_key": dataset_key,
        "filename": file.filename,
        "size_mb": file_size_mb,
        "columns": list(df.columns),
        "total_rows": len(df)
    }



