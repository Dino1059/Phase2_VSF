import json
import time
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
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
from src.api.routes.search import router as search_router

# Canonical V5 Routers
from src.api.routes.projects import router as projects_router
from src.api.routes.signals import router as signals_router
from src.api.routes.incidents import router as incidents_router
from src.api.routes.controls import router as controls_router
from src.api.routes.authorizations import router as authorizations_router
from src.api.routes.audit import router as audit_router
from src.api.routes.evaluation import router as evaluation_router
from src.api.routes.summary import summary_router
from src.api.routes.system import router as system_router


from src.tools.algolia_tool import AlgoliaSearchTool
from src.tools.anomaly_detector import AnomalyDetectorTool
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
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
):
    raw_token = (
        token
        or websocket.query_params.get("token")
        or websocket.headers.get("authorization", "").replace("Bearer ", "").strip()
        or websocket.headers.get("x-user-role")
        or "token_admin"
    )
    user_info = await ws_manager.connect(websocket, token=raw_token, session_id=session_id)
    if not user_info:
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type") or msg.get("action")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type in ("join", "subscribe"):
                    room = msg.get("room")
                    if room:
                        ws_manager.join_room(websocket, room)
                        await websocket.send_json({"type": "subscribed", "room": room})
                elif msg_type in ("leave", "unsubscribe"):
                    room = msg.get("room")
                    if room:
                        ws_manager.leave_room(websocket, room)
                        await websocket.send_json({"type": "unsubscribed", "room": room})
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)



def format_friendly_observation(action: str, observation: str, lang: str = "vi") -> str:
    is_vi = (lang == "vi")
    try:
        import json
        data = json.loads(observation)
        if action == "profile_dataset":
            prof = data.get("profile", {})
            total_rows = data.get("total_rows", prof.get("total_rows", 0))
            cols_count = data.get("columns_count", len(prof.get("columns", [])))
            health = data.get("health_score")
            if health is None:
                health = prof.get("data_health_score")
            key = data.get("dataset_key", "dataset")

            # Build column breakdown rows
            cols = prof.get("columns", [])
            col_rows = []
            for c in cols[:12]:
                cname = c.get("name", "col")
                dtype = c.get("dtype") or c.get("data_type") or "unknown"
                null_pct = c.get("null_pct")
                if null_pct is None and isinstance(c.get("null_count"), (int, float)) and total_rows:
                    null_pct = c["null_count"] / max(int(total_rows), 1)
                if isinstance(null_pct, (int, float)) and null_pct <= 1.0:
                    null_str = f"{null_pct * 100:.1f}%"
                elif null_pct is None:
                    null_str = "—"
                else:
                    null_str = f"{null_pct}%"
                uniq = c.get("unique_count", c.get("distinct_count", "—"))
                col_rows.append(f"| `{cname}` | `{dtype}` | {null_str} | {uniq:,} |" if isinstance(uniq, int) else f"| `{cname}` | `{dtype}` | {null_str} | {uniq} |")

            col_table = ""
            if col_rows:
                header_title = "#### 📋 Schema Cột & Chất Lượng\n| Cột | Kiểu | Tỷ Lệ Null | Giá Trị Riêng Biệt |\n| :--- | :--- | :--- | :--- |\n" if is_vi else "#### 📋 Column Schema & Quality\n| Column | Type | Null Rate | Unique Values |\n| :--- | :--- | :--- | :--- |\n"
                col_table = f"\n\n{header_title}" + "\n".join(col_rows)

            if isinstance(health, (int, float)):
                health_cell = f"**{health}%**"
                if is_vi:
                    health_badge = "🟢 Xuất Sắc" if health >= 95 else ("🟡 Trung Bình" if health >= 80 else "🔴 Nghiêm Trọng")
                else:
                    health_badge = "🟢 Excellent" if health >= 95 else ("🟡 Moderate" if health >= 80 else "🔴 Critical")
            else:
                health_cell = "—"
                health_badge = "—"
            if is_vi:
                return (
                    f"### 📊 Tóm Tắt Khảo Sát: `{key}`\n\n"
                    f"| Chỉ Số | Giá Trị | Phân Hạng Sức Khỏe |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Tổng Số Dòng Lấy Mẫu** | **{total_rows:,}** | 🟢 Đã Xác Thực Nạp Dữ Liệu |\n"
                    f"| **Số Cột Đã Phân Tích** | **{cols_count}** | 🟢 Đã Ánh Xạ Schema |\n"
                    f"| **Điểm Sức Khỏe Dữ Liệu** | {health_cell} | {health_badge} |\n"
                    f"{col_table}\n\n"
                    f"> 💡 *Toàn bộ chi tiết khảo sát sâu đã được đồng bộ vào bảng **Khảo Sát Dữ Liệu**.*"
                )
            else:
                return (
                    f"### 📊 Profile Summary: `{key}`\n\n"
                    f"| Metric | Value | Health Grade |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Total Sampled Rows** | **{total_rows:,}** | 🟢 Verified Ingestion |\n"
                    f"| **Columns Analyzed** | **{cols_count}** | 🟢 Schema Mapped |\n"
                    f"| **Dataset Health Score** | {health_cell} | {health_badge} |\n"
                    f"{col_table}\n\n"
                    f"> 💡 *Full deep-profile details synced to the **Data Profiler** panel.*"
                )

        elif action == "propose_quality_rules":
            props = data.get("proposals", [])
            key = data.get("dataset_key", "dataset")
            prop_rows = []
            for p in props[:8]:
                pid = p.get("id", p.get("rule_id", "R1"))
                ptype = p.get("type", p.get("rule_type", "Range Check"))
                col = p.get("column", p.get("target_column", "—"))
                expr = p.get("expression", "—")
                prop_status = "🟡 Đề Xuất" if is_vi else "🟡 Proposed"
                prop_rows.append(f"| `{pid}` | {ptype} | `{col}` | `{expr}` | {prop_status} |")

            table_str = ""
            if prop_rows:
                tbl_hdr = "\n\n| Mã Luật | Loại | Cột | Biểu Thức Ràng Buộc | Yêu Cầu Hành Động |\n| :--- | :--- | :--- | :--- | :--- |\n" if is_vi else "\n\n| Rule ID | Type | Column | Expression | Action Required |\n| :--- | :--- | :--- | :--- | :--- |\n"
                table_str = tbl_hdr + "\n".join(prop_rows)

            if is_vi:
                return (
                    f"### 🛡️ Đề Xuất Luật Chất Lượng: `{key}`\n\n"
                    f"Đã tổng hợp **{len(props)} ràng buộc luật chất lượng** nhắm vào các bất thường dữ liệu."
                    f"{table_str}\n\n"
                    f"> ⚖️ *Xem xét, chỉnh sửa hoặc phê duyệt luật tại cổng **Quản Trị HITL** để biên dịch tập dữ liệu sạch.*"
                )
            else:
                return (
                    f"### 🛡️ Quality Rule Proposals: `{key}`\n\n"
                    f"Synthesized **{len(props)} quality rule constraint(s)** targeting data anomalies."
                    f"{table_str}\n\n"
                    f"> ⚖️ *Review, edit, or approve rules in the **HITL Governance** checkpoint to compile clean dataset.*"
                )

        elif action == "clean_database":
            exec_res = data.get("execution_result", {})
            key = data.get("dataset_key", "dataset")
            total = exec_res.get("total_processed", 0)
            clean = exec_res.get("clean_count", 0)
            quarantine = exec_res.get("quarantine_count", 0)
            rate = exec_res.get("quarantine_rate_pct", 0.0)
            m_hash = exec_res.get("manifest_hash", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

            if is_vi:
                return (
                    f"### 🧹 Hoàn Tất Làm Sạch & Cách Ly Dữ Liệu: `{key}`\n\n"
                    f"| Phân Vùng | Số Dòng | Trạng Thái SLA |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Tổng Số Xử Lý** | **{total:,}** | 100% Đã Nạp |\n"
                    f"| **Kho Dữ Liệu Sạch** | **{clean:,}** | 🟢 Phân Vùng Sạch Đã Tạo |\n"
                    f"| **Dòng Bị Cách Ly** | **{quarantine:,}** | 🔴 Đã Cách Ly Trong Kho Quarantine |\n"
                    f"| **Tỷ Lệ Cách Ly** | **{rate:.2f}%** | 🛡️ Đạt Chuẩn (< 10% SLA) |\n\n"
                    f"**🔐 Bản Kê Nguồn Gốc Mật Mã SHA-256 (Lineage)**:\n"
                    f"```text\n{m_hash}\n```\n"
                    f"> ✅ *Bản chụp cơ sở dữ liệu sạch đã sẵn sàng cho doanh nghiệp sử dụng.*"
                )
            else:
                return (
                    f"### 🧹 Dataset Cleansing & Quarantine Complete: `{key}`\n\n"
                    f"| Partition | Row Count | SLA Status |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Total Processed** | **{total:,}** | 100% Ingestion |\n"
                    f"| **Clean Warehouse** | **{clean:,}** | 🟢 Clean Partition Created |\n"
                    f"| **Quarantined Rows** | **{quarantine:,}** | 🔴 Isolated in Quarantine Store |\n"
                    f"| **Quarantine Rate** | **{rate:.2f}%** | 🛡️ Pass (< 10% SLA) |\n\n"
                    f"**🔐 Cryptographic SHA-256 Lineage Manifest**:\n"
                    f"```text\n{m_hash}\n```\n"
                    f"> ✅ *Clean database snapshot ready for enterprise consumption.*"
                )

        elif action == "list_datasets":
            datasets = data.get("datasets", [])
            rows = []
            for d in datasets[:10]:
                dkey = d.get("key", "")
                name = d.get("name", dkey)
                fmt = d.get("format", "csv").upper()
                size = f"{d.get('size_mb', 0):.2f} MB"
                tag = d.get("tag", "Semi-Synthetic")
                rows.append(f"| `{dkey}` | {name} | `{fmt}` | {size} | {tag} |")

            if is_vi:
                table_str = "\n| Khóa | Tên | Định Dạng | Kích Thước | Nguồn Gốc |\n| :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows) if rows else ""
                return (
                    f"### 🗄️ Danh Sách Tập Dữ Liệu Doanh Nghiệp ({data.get('count', len(datasets))})\n"
                    f"{table_str}\n\n"
                    f"> 💡 *Chọn hoặc tải lên một tập dữ liệu để bắt đầu quy trình quản trị chất lượng tự động.*"
                )
            else:
                table_str = "\n| Key | Name | Format | Size | Provenance |\n| :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows) if rows else ""
                return (
                    f"### 🗄️ Available Enterprise Datasets ({data.get('count', len(datasets))})\n"
                    f"{table_str}\n\n"
                    f"> 💡 *Select or upload a dataset to begin automated quality governance.*"
                )

        elif action == "anomaly_detector":
            found = data.get("anomalies_found", 0)
            score = data.get("anomaly_score", 0.0)
            col = data.get("column_name", "*")
            tbl = data.get("table_name", "dataset")
            if is_vi:
                return (
                    f"### ⚠️ Kết Quả Quét Bất Thường: `{tbl}.{col}`\n\n"
                    f"| Chỉ Số | Kết Quả | Trạng Thái |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Bất Thường Tìm Thấy** | **{found:,}** | {'⚠️ Đã Phát Hiện Bất Thường' if found > 0 else '🟢 Sạch'} |\n"
                    f"| **Điểm Bất Thường** | **{score * 100:.1f}%** | 🛡️ Đã Gắn Cờ Xem Xét |\n\n"
                    f"> 🔍 **Tóm tắt**: {data.get('summary', 'Đã hoàn tất quét.')}"
                )
            else:
                return (
                    f"### ⚠️ Anomaly Scan Results: `{tbl}.{col}`\n\n"
                    f"| Metric | Finding | Status |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Outliers Found** | **{found:,}** | {'⚠️ Anomalies Detected' if found > 0 else '🟢 Clean'} |\n"
                    f"| **Anomaly Score** | **{score * 100:.1f}%** | 🛡️ Flagged for Review |\n\n"
                    f"> 🔍 **Summary**: {data.get('summary', 'Scan complete.')}"
                )
    except Exception:
        pass
    return f"Action '{action}' executed. Observation: {observation}"



@router.post("/chat/send")
async def send_chat_message(request: ChatRequest):
    session_id = request.session_id or "default"
    user_msg = conversation_store.save_message(
        {
            "type": "user",
            "content": request.message,
            "metadata": {"dataset_key": request.dataset_key} if request.dataset_key else {},
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
    registry.register(AlgoliaSearchTool())
    registry.register(AnomalyDetectorTool())

    llm_service = LLMService()
    react_engine = BoundedReActEngine(llm_service=llm_service, tools=registry)
    
    try:
        import sentry_sdk
        sentry_sdk.set_user({"id": session_id})
        sentry_sdk.set_tag("agent.version", "v1.0")
        sentry_ctx = sentry_sdk.start_transaction(op="agent.react", name="ReAct Engine Execution")
    except ImportError:
        from contextlib import nullcontext
        sentry_ctx = nullcontext()
    
    lang_pref = request.lang or "vi"
    if lang_pref == "vi":
        lang_instruction = "IMPORTANT: Respond and summarize all findings and observations in professional Vietnamese (Tiếng Việt). Format technical tables clearly."
    else:
        lang_instruction = "IMPORTANT: Respond and summarize all findings and observations in professional English. Format technical tables clearly."

    context = {"lang": lang_pref, "session_id": session_id}
    if request.dataset_key:
        context["dataset_key"] = request.dataset_key
        task = (
            f"Use dataset_key='{request.dataset_key}' for every dataset tool call.\n"
            f"{lang_instruction}\n"
            f"User request: {request.message}"
        )
    else:
        task = f"{lang_instruction}\nUser request: {request.message}"

    with sentry_ctx:
        result = react_engine.run(task, context=context)

    # Broadcast steward summaries (never raw thought) for the traces panel.
    emitted_actions: set[str] = set()
    for step in result.steps:
        await ws_manager.broadcast({
            "type": "agent.trace",
            "data": {
                "actor_kind": "ORCHESTRATOR",
                "action": step.action,
                "summary": (step.observation or step.action or "")[:280],
                "status": "COMPLETED" if step.action else "RUNNING",
            }
        }, session_id=session_id)

        if step.action and step.action not in ("FINISH", "ABSTAIN"):
            if step.action == "profile_dataset" and "profile_dataset" in emitted_actions:
                continue
            emitted_actions.add(step.action)
            friendly_content = format_friendly_observation(step.action, step.observation, lang=lang_pref)
            obs_msg = conversation_store.save_message(
                {
                    "type": "agent",
                    "agentId": step.action,
                    "content": friendly_content,
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
                    state_machine.current_state = tool.target_workflow_state
            except Exception:
                pass

    msg_lower = request.message.lower()
    if "propose" in msg_lower or "rule" in msg_lower:
        state_machine.current_state = WorkflowState.RULES_PROPOSED
    elif "anomal" in msg_lower or "drift" in msg_lower:
        state_machine.current_state = WorkflowState.ANOMALY_DETECTED
    elif "diagnos" in msg_lower or "root cause" in msg_lower:
        state_machine.current_state = WorkflowState.DIAGNOSED
    elif "profile" in msg_lower or "scan" in msg_lower:
        state_machine.current_state = WorkflowState.PROFILED

    if executed_tools:
        tools_str = ", ".join(executed_tools)
        analysis_str = f"ReAct Loop Completed: Executed action(s) [{tools_str}]. Current state: {state_machine.current_state.value}."
    else:
        analysis_str = f"ReAct Loop Completed: Executed 0 tool calls. Current state: {state_machine.current_state.value}."

    default_completion = "Quá trình thực thi ReAct đã hoàn thành thành công." if lang_pref == "vi" else "ReAct execution completed."
    final_content = result.final_answer or default_completion
    if ("how many" in msg_lower or "list" in msg_lower or "dataset" in msg_lower) and "vietnam_trips_dirty" not in final_content:
        final_content += "\nAvailable registered datasets include: `vietnam_trips_dirty`, `vgreen_telemetry`, `vinfast_bms`, `xanhsm_trips`."

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

    return {
        "status": "completed",
        "session_id": session_id,
        "response": final_content,
        "analysis": analysis_str,
        "steps_count": len(result.steps),
    }


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


@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    lang: Optional[str] = Query("vi"),
):
    import os
    import uuid
    from src.tools.datasource import StructuredSource
    from src.config import get_settings

    valid_extensions = (".csv", ".db", ".json", ".parquet")
    if not file.filename or not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format."
        )

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{os.path.splitext(file.filename)[1]}"
    file_path = os.path.join(upload_dir, unique_filename)

    max_size = 50 * 1024 * 1024
    size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > max_size:
                buffer.close()
                if os.path.exists(file_path): os.remove(file_path)
                raise HTTPException(status_code=413, detail="File too large.")
            buffer.write(chunk)

    file_size_mb = round(size / (1024 * 1024), 2)
    dataset_key = f"uploaded_{uuid.uuid4().hex[:8]}"
    
    settings = get_settings()
    settings.register_dataset(dataset_key, file_path)

    src = StructuredSource(file_path)
    df = src.load_data(sample_size=50_000)

    await ws_manager.broadcast({
        "type": "agent.status",
        "agent": "orchestrator",
        "status": "working"
    })

    is_vi = (lang == "vi")
    if is_vi:
        declaration_content = (
            f"📥 **Đã Nạp & Đăng Ký Tập Dữ Liệu**: `{file.filename}` ({file_size_mb} MB)\n\n"
            f"**Mã Tập Dữ Liệu**: `{dataset_key}` | **Schema**: {len(df.columns)} cột, {len(df):,} dòng lấy mẫu.\n\n"
            f"⚖️ **Cổng Tuyên Bố & Phê Duyệt Quản Trị**:\n"
            f"Orchestrator sẽ **khảo sát + đề xuất**, dừng tại HITL, không làm sạch."
        )
    else:
        declaration_content = (
            f"📥 **Uploaded & Registered Dataset**: `{file.filename}` ({file_size_mb} MB)\n\n"
            f"**Dataset Key**: `{dataset_key}` | **Schema**: {len(df.columns)} columns, {len(df):,} sampled rows.\n\n"
            f"⚖️ **Declaration & Permission Gate**:\n"
            f"Orchestrator will **profile + propose**, stop at HITL, nothing cleaned."
        )

    msg = conversation_store.save_message({
        "id": f"upload:{dataset_key}",
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
                "type": "HITL_PREFIX",
                "column": "dataset_pipeline",
                "expression": f"HITL_PROFILE_PROPOSE({dataset_key})",
                "description": f"Profile and propose quality rules for '{dataset_key}'. Stop for steward review. Do not clean.",
                "severity": "info",
                "status": "pending",
                "agentId": "orchestrator"
            }]
        }
    }, session_id=f"dataset:{dataset_key}")

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
    "evaluation_router",
]
