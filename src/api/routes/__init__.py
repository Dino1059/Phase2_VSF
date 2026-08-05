import json
import time
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
import pandas as pd
from pydantic import BaseModel
from pydantic import BaseModel


from src.api.audit_store import AuditStore
from src.api.middleware import check_user_role, UserRole
from src.api.state_machine import StateMachine, WorkflowState

from src.tools.profiler import Profiler
from src.tools.compiler import Compiler
from src.tools.executor import Executor
from src.tools.base import ToolRegistry
from src.tools.chat_tools import (
    ListDatasetsTool,
    ProfileDatasetTool,
    ProposeQualityRulesTool,
    CleanDatabaseTool,
)

# Global shared in-memory state objects for API
router = APIRouter(dependencies=[Depends(check_user_role)])
state_machine = StateMachine()
audit_store = AuditStore()
profiler = Profiler()
compiler = Compiler()
executor = Executor()


# Domain routers imported after shared state is initialized
from src.api.routes.approvals import router as approvals_router
from src.api.routes.auth import router as auth_router
from src.api.routes.benchmarks import router as benchmarks_router
from src.api.routes.datasets import router as datasets_router
from src.api.routes.executions import router as executions_router
from src.api.routes.profiling import router as profiling_router
from src.api.routes.rules import router as rules_router
from src.api.routes.schedules import router as schedules_router

from src.agents.baselines import A1Agent, C0Baseline, C1Baseline
from src.agents.react import BoundedReActEngine
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
from src.tools.validator import RuleSpec


@router.post("/transform/execute", response_model=ExecuteTransformResponse)
async def execute_transform_endpoint(request: ExecuteTransformRequest) -> ExecuteTransformResponse:
    from src.api.routes.executions import execute_transform_endpoint as exec_tr
    return await exec_tr(request)


@router.post("/execute")
async def execute_endpoint(request: Request, payload: Optional[dict] = None):
    from src.api.routes.executions import execute_endpoint as exec_ep
    return await exec_ep(request=request, payload=payload)


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


@router.post("/dataset/upload")
@router.post("/datasets/upload")
async def upload_dataset_legacy_endpoint(file: UploadFile = File(...)):
    from src.api.routes.datasets import upload_dataset_endpoint
    return await upload_dataset_endpoint(file=file)



# Anomaly & Alerting endpoints
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


@router.get("/alerts")
async def get_alerts_endpoint(
    severity: Optional[str] = None, status: Optional[str] = None
):
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


# WebSocket router
ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: Optional[str] = None):
    await ws_manager.connect(websocket, session_id=session_id)
    try:
        while True:
            data = await websocket.receive_text()
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
    session_id = request.session_id or "default"
    user_msg = conversation_store.save_message(
        {
            "type": "user",
            "content": request.message,
        },
        session_id=session_id,
    )

    await ws_manager.broadcast({"type": "chat.message", "data": user_msg}, session_id=session_id)
    await ws_manager.broadcast(
        {"type": "agent.status", "agent": "orchestrator", "status": "working"},
        session_id=session_id,
    )

    registry = ToolRegistry()
    registry.register(ListDatasetsTool())
    registry.register(ProfileDatasetTool())
    registry.register(ProposeQualityRulesTool())
    registry.register(CleanDatabaseTool())

    llm_service = LLMService()
    react_engine = BoundedReActEngine(llm_service=llm_service, tools=registry)
    
    result = react_engine.run(request.message)

    # Save and broadcast step thoughts/actions
    for step in result.steps:
        if step.thought:
            thought_msg = conversation_store.save_message(
                {
                    "type": "agent",
                    "agentId": "orchestrator",
                    "content": f"Thought: {step.thought}",
                },
                session_id=session_id,
            )
            await ws_manager.broadcast({"type": "chat.message", "data": thought_msg}, session_id=session_id)

        if step.action and step.action not in ("FINISH", "ABSTAIN"):
            obs_msg = conversation_store.save_message(
                {
                    "type": "agent",
                    "agentId": step.action,
                    "content": f"Action '{step.action}' executed. Observation: {step.observation[:300]}",
                },
                session_id=session_id,
            )
            await ws_manager.broadcast({"type": "chat.message", "data": obs_msg}, session_id=session_id)

    executed_tools = []
    for step in result.steps:
        if step.action and step.action not in ("FINISH", "ABSTAIN"):
            executed_tools.append(step.action)
            try:
                tool = registry.get_tool(step.action)
                if tool and getattr(tool, "target_workflow_state", None):
                    state_machine.transition_to(tool.target_workflow_state)
            except Exception:
                pass

    if executed_tools:
        tools_str = ", ".join(executed_tools)
        analysis_str = f"ReAct Loop Completed: Executed action(s) [{tools_str}]. Current state: {state_machine.current_state.value}."
    else:
        analysis_str = f"Canonical ReAct Engine executed {len(result.steps)} step(s). Status: {result.status}."

    final_content = result.final_answer or "ReAct execution completed."
    agent_msg = conversation_store.save_message(
        {
            "type": "agent",
            "agentId": "orchestrator",
            "content": final_content,
        },
        session_id=session_id,
    )
    await ws_manager.broadcast({"type": "chat.message", "data": agent_msg}, session_id=session_id)
    await ws_manager.broadcast(
        {"type": "agent.status", "agent": "orchestrator", "status": "done"},
        session_id=session_id,
    )

    return ChatResponse(
        response=final_content,
        analysis=analysis_str,
        state=state_machine.current_state.value,
        agent_execution={"steps": len(result.steps), "status": result.status},
    )


@router.get("/chat/history")
async def get_chat_history(session_id: str = "default"):
    return {"messages": conversation_store.get_messages(session_id=session_id)}


@router.get("/chat/sessions")
async def get_chat_sessions():
    return {"sessions": conversation_store.list_sessions()}


class ClearChatRequest(BaseModel):
    session_id: Optional[str] = None


@router.post("/chat/clear")
async def clear_chat(req: ClearChatRequest):
    if req.session_id:
        conversation_store.clear_messages(session_id=req.session_id)
    else:
        conversation_store.clear_all()
    return {"status": "cleared", "session_id": req.session_id}


@router.post("/dataset/upload")
@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    import os
    import shutil
    import uuid
    from src.tools.datasource import StructuredSource
    from src.config import get_settings

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS = {".csv", ".parquet", ".json"}

    raw_filename = file.filename or "uploaded_data.csv"
    filename_base = os.path.basename(raw_filename.replace("\\", "/"))
    filename_base = filename_base.replace("..", "")

    base_name, ext = os.path.splitext(filename_base)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_filename)

    size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                buffer.close()
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=413,
                    detail="File size exceeds maximum allowed limit of 50 MB."
                )
            buffer.write(chunk)

    file_size_mb = round(size / (1024 * 1024), 2)
    clean_name = base_name.replace("-", "_").replace(" ", "_").lower()
    dataset_key = f"uploaded_{clean_name}"
    rel_path = os.path.relpath(file_path, base_dir)

    settings = get_settings()
    settings.register_dataset(dataset_key, rel_path)

    src = StructuredSource(file_path)
    df = src.load_data(sample_size=50_000)

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


__all__ = [
    "router",
    "ws_router",
    "state_machine",
    "audit_store",
    "profiler",
    "compiler",
    "executor",
    "auth_router",
    "datasets_router",
    "profiling_router",
    "rules_router",
    "approvals_router",
    "executions_router",
    "benchmarks_router",
    "schedules_router",
]
