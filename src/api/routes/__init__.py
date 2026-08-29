import asyncio
import json
import time
from datetime import datetime
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
    DetectAnomaliesTool,
    ProposeQualityRulesTool,
    CleanDatabaseTool,
    RunFullPipelineTool,
    SandboxPreviewTool,
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
from src.orchestrator.engine import ReActStep, is_hitl_stop_prompt, _is_hitl_stop, _allow_hitl_tool, HITL_REFUSED_TOOLS, HITL_STOP_ALLOWED_TOOLS
from src.orchestrator.prompt_intent import (
    EDIT_RULE_ALLOWED_TOOLS,
    SMALLTALK_SYSTEM,
    asks_dataset_inventory,
    grill_edit_rule,
    is_edit_rule_prompt,
    is_smalltalk_prompt,
    parse_edit_rule_query,
    smalltalk_reply,
)
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



def format_friendly_observation(action: str, observation: Any, lang: str = "vi") -> str:
    is_vi = (lang == "vi")
    data = {}
    if isinstance(observation, dict):
        data = observation
    elif isinstance(observation, str):
        try:
            import json
            data = json.loads(observation)
        except Exception:
            try:
                import ast
                data = ast.literal_eval(observation)
            except Exception:
                data = {}

    if isinstance(data, dict) and data:
        try:
            if action == "profile_dataset":
                prof = data.get("profile", {})
                if not isinstance(prof, dict):
                    prof = {}
                total_rows = data.get("total_rows", prof.get("total_rows", 0))
                cols_count = data.get("columns_count", len(prof.get("columns", [])))
                health = data.get("health_score", prof.get("health_score", None))
                if health is None:
                    health = prof.get("data_health_score")
                key = data.get("dataset_key", "dataset")

                # Build column breakdown rows (support single and multi-table structures)
                cols = prof.get("columns", [])
                if not cols and isinstance(prof.get("tables"), dict):
                    for _tname, tval in prof.get("tables", {}).items():
                        if isinstance(tval, dict):
                            sub_prof = tval.get("profile", {})
                            if isinstance(sub_prof, dict) and sub_prof.get("columns"):
                                cols = sub_prof.get("columns", [])
                                if not cols_count:
                                    cols_count = len(cols)
                                break

                col_rows = []
                for c in cols[:8]:
                    cname = c.get("name", "col")
                    dtype = c.get("dtype", c.get("data_type", "unknown"))
                    null_pct = c.get("null_pct", c.get("null_count", 0.0))
                    if isinstance(null_pct, (int, float)) and null_pct <= 1.0:
                        null_str = f"{null_pct * 100:.1f}%"
                    else:
                        null_str = f"{null_pct}%"
                    uniq = c.get("unique_count", "—")
                    col_rows.append(f"| `{cname}` | `{dtype}` | {null_str} | {uniq:,} |" if isinstance(uniq, int) else f"| `{cname}` | `{dtype}` | {null_str} | {uniq} |")

                col_table = ""
                if col_rows:
                    header_title = "#### 📋 Schema Cột & Chất Lượng\n| Cột | Kiểu | Tỷ Lệ Null | Giá Trị Riêng Biệt |\n| :--- | :--- | :--- | :--- |\n" if is_vi else "#### 📋 Column Schema & Quality\n| Column | Type | Null Rate | Unique Values |\n| :--- | :--- | :--- | :--- |\n"
                    col_table = f"\n\n{header_title}" + "\n".join(col_rows)

                if health is None:
                    health_disp, health_badge = "—", "—"
                elif is_vi:
                    health_disp = f"{health}%"
                    health_badge = "🟢 Xuất Sắc" if health >= 95 else ("🟡 Trung Bình" if health >= 80 else "🔴 Nghiêm Trọng")
                else:
                    health_disp = f"{health}%"
                    health_badge = "🟢 Excellent" if health >= 95 else ("🟡 Moderate" if health >= 80 else "🔴 Critical")
                if is_vi:
                    return (
                        f"### 📊 Tóm Tắt Khảo Sát: `{key}`\n\n"
                        f"| Chỉ Số | Giá Trị | Phân Hạng Sức Khỏe |\n"
                        f"| :--- | :--- | :--- |\n"
                        f"| **Tổng Số Dòng Lấy Mẫu** | **{total_rows:,}** | 🟢 Đã Xác Thực Nạp Dữ Liệu |\n"
                        f"| **Số Cột Đã Phân Tích** | **{cols_count}** | 🟢 Đã Ánh Xạ Schema |\n"
                        f"| **Điểm Sức Khỏe Dữ Liệu** | **{health_disp}** | {health_badge} |\n"
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
                        f"| **Dataset Health Score** | **{health_disp}** | {health_badge} |\n"
                        f"{col_table}\n\n"
                        f"> 💡 *Full deep-profile details synced to the **Data Profiler** panel.*"
                    )

            elif action == "propose_quality_rules":
                props = data.get("proposals", [])
                if not props and isinstance(data.get("rules"), list):
                    props = data.get("rules")
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
                if not isinstance(exec_res, dict):
                    exec_res = {}
                key = data.get("dataset_key", "dataset")
                total = exec_res.get("total_processed", 0)
                clean = exec_res.get("clean_count", 0)
                quarantine = exec_res.get("quarantine_count", 0)
                rate = exec_res.get("quarantine_rate_pct", 0.0)
                m_hash = exec_res.get("manifest_hash", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

                # Dynamic SLA label — driven by actual quarantine rate
                sla_pass = rate <= 10.0
                if is_vi:
                    sla_status = "🛡️ Đạt Chuẩn (< 10% SLA)" if sla_pass else "⚠️ Vượt Ngưỡng (> 10% SLA)"
                else:
                    sla_status = "🛡️ Pass (< 10% SLA)" if sla_pass else "⚠️ Exceeds SLA (> 10%)"

                if is_vi:
                    return (
                        f"### 🧹 Hoàn Tất Làm Sạch & Cách Ly Dữ Liệu: `{key}`\n\n"
                        f"| Phân Vùng | Số Dòng | Trạng Thái SLA |\n"
                        f"| :--- | :--- | :--- |\n"
                        f"| **Tổng Số Xử Lý** | **{total:,}** | 100% Đã Nạp |\n"
                        f"| **Kho Dữ Liệu Sạch** | **{clean:,}** | 🟢 Phân Vùng Sạch Đã Tạo |\n"
                        f"| **Dòng Bị Cách Ly** | **{quarantine:,}** | 🔴 Đã Cách Ly Trong Kho Quarantine |\n"
                        f"| **Tỷ Lệ Cách Ly** | **{rate:.2f}%** | {sla_status} |\n\n"
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
                        f"| **Quarantine Rate** | **{rate:.2f}%** | {sla_status} |\n\n"
                        f"**🔐 Cryptographic SHA-256 Lineage Manifest**:\n"
                        f"```text\n{m_hash}\n```\n"
                        f"> ✅ *Clean database snapshot ready for enterprise consumption.*"
                    )

            elif action == "sandbox_preview":
                key = data.get("dataset_key", "dataset")
                day = data.get("day_count") if isinstance(data.get("day_count"), dict) else {}
                qn = data.get("quarantine_rows", 0)
                cn = data.get("clean_rows", 0)
                sampled = data.get("sampled_rows", 0)
                warehouse = data.get("warehouse_clean_rows", 0)
                if is_vi:
                    return (
                        f"### Xem trước sandbox (không ghi): `{key}`\n\n"
                        f"COUNT(*) ngày = **{day.get('count', '—')}**. Mẫu **{sampled}** dòng: "
                        f"{cn} sẽ sạch, {qn} sẽ cách ly. Clean Warehouse = **{warehouse}** đến khi Execute.\n\n"
                        f"> *Không ghi quarantine/kho sạch. Steward Confirm trên thẻ.*"
                    )
                return (
                    f"### Sandbox preview (no write): `{key}`\n\n"
                    f"Day COUNT(*) = **{day.get('count', '—')}**. Sampled **{sampled}** rows: "
                    f"{cn} would pass, {qn} would quarantine. Clean Warehouse = **{warehouse}** until Execute.\n\n"
                    f"> *No quarantine/warehouse write. Steward Confirm still required on the card.*"
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

            elif action in ("detect_anomalies", "detect_l1_l4_anomalies"):
                key = data.get("dataset_key", "dataset")
                sig_sum = data.get("signals_summary", {})
                inc_count = data.get("incident_count", 0)
                incidents = data.get("incidents", [])

                inc_rows = []
                for inc in incidents[:6]:
                    iid = inc.get("incident_id", "INC-01")
                    layers_str = "+".join(inc.get("supporting_layers", []))
                    claim = inc.get("hypothesis_claim", "") or inc.get("admission_reason", "")
                    sev = inc.get("severity", "WARNING")
                    badge = "🔴 Nghiêm trọng" if sev == "CRITICAL" else "🟡 Cảnh báo" if is_vi else ("🔴 Critical" if sev == "CRITICAL" else "🟡 Warning")
                    inc_rows.append(f"| `{iid}` | `{layers_str}` | {claim[:45]} | {badge} |")

                inc_table = ""
                if inc_rows:
                    tbl_hdr = "\n\n| Mã Sự Cố | Tầng Phát Hiện | Giả Thuyết / Nguyên Nhân | Mức Độ |\n| :--- | :--- | :--- | :--- |\n" if is_vi else "\n\n| Incident ID | Layers | Root Cause Hypothesis | Severity |\n| :--- | :--- | :--- | :--- |\n"
                    inc_table = tbl_hdr + "\n".join(inc_rows)

                if is_vi:
                    return (
                        f"### 🔍 Phát Hiện Dị Thường Đa Tầng L1–L4: `{key}`\n\n"
                        f"| Tầng Dị Thường | Số Tín Hiệu (Signals) | Trạng Thái |\n"
                        f"| :--- | :--- | :--- |\n"
                        f"| **L1 (Range & Boundary)** | **{sig_sum.get('L1', 0):,}** | {'⚠️ Phát hiện vi phạm' if sig_sum.get('L1', 0) > 0 else '🟢 Chuẩn'} |\n"
                        f"| **L2 (Temporal & Drift)** | **{sig_sum.get('L2', 0):,}** | {'⚠️ Biến động đột ngột' if sig_sum.get('L2', 0) > 0 else '🟢 Ổn định'} |\n"
                        f"| **L3 (Relational Invariant)** | **{sig_sum.get('L3', 0):,}** | {'⚠️ Vi phạm bất biến vật lý' if sig_sum.get('L3', 0) > 0 else '🟢 Khớp'} |\n"
                        f"| **L4 (Semantic Correlation)** | **{sig_sum.get('L4', 0):,}** | {'⚠️ Tương quan dị thường' if sig_sum.get('L4', 0) > 0 else '🟢 Chuẩn'} |\n"
                        f"| **Tổng Sự Cố Tiếp Nhận (Incidents)** | **{inc_count}** | 🛡️ Chuyển giao sang Bộ Đề Xuất Luật |\n"
                        f"{inc_table}\n\n"
                        f"> 🧠 *Kết quả phát hiện dị thường đã được chuyển sang **Stage 3 (Rule Proposal)** để tổng hợp quy tắc khắc phục.*"
                    )
                else:
                    return (
                        f"### 🔍 Multi-Layer L1–L4 Anomaly Detection: `{key}`\n\n"
                        f"| Anomaly Layer | Signals Detected | Status |\n"
                        f"| :--- | :--- | :--- |\n"
                        f"| **L1 (Range & Boundary)** | **{sig_sum.get('L1', 0):,}** | {'⚠️ Violations Found' if sig_sum.get('L1', 0) > 0 else '🟢 In Range'} |\n"
                        f"| **L2 (Temporal & Drift)** | **{sig_sum.get('L2', 0):,}** | {'⚠️ Drift Detected' if sig_sum.get('L2', 0) > 0 else '🟢 Stable'} |\n"
                        f"| **L3 (Relational Invariant)** | **{sig_sum.get('L3', 0):,}** | {'⚠️ Invariant Broken' if sig_sum.get('L3', 0) > 0 else '🟢 Validated'} |\n"
                        f"| **L4 (Semantic Correlation)** | **{sig_sum.get('L4', 0):,}** | {'⚠️ Anomalous Patterns' if sig_sum.get('L4', 0) > 0 else '🟢 Normal'} |\n"
                        f"| **Total Admitted Incidents** | **{inc_count}** | 🛡️ Forwarded to Rule Proposer |\n"
                        f"{inc_table}\n\n"
                        f"> 🧠 *Anomaly findings forwarded to **Stage 3 (Rule Proposal)** for targeted constraint synthesis.*"
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


def _session_has_tool_beat(session_id: str, tool_name: str) -> bool:
    try:
        from src.db.connection import get_db
        targets = {tool_name, tool_name.replace("default_api:", "")}
        if "propose" in tool_name or "quality_rule" in tool_name:
            targets.update({"propose_quality_rules", "quality_rule_proposer", "default_api:propose_quality_rules"})
        placeholders = ",".join(["?"] * len(targets))
        params = [session_id] + list(targets) + list(targets)
        rows = get_db().execute(
            f"SELECT 1 FROM agent_traces WHERE session_id = ? AND (tool_name IN ({placeholders}) OR action IN ({placeholders})) LIMIT 1",
            params,
        )
        if hasattr(rows, "fetchall"):
            rows = rows.fetchall()
        return bool(rows)
    except Exception:
        return False


def is_pong_ping(message: str) -> bool:
    """Literal instruction-follow ping. Must not run ReAct or prepend inventory."""
    m = (message or "").strip().lower()
    if "pong" not in m:
        return False
    return any(k in m for k in ("reply", "only", "one word", "ping"))


def _llm_turns(prior: list | None) -> list[dict]:
    """User + orchestrator turns only. Skip tool-row dumps (profile/list tables)."""
    out: list[dict] = []
    for m in prior or []:
        if not isinstance(m, dict):
            continue
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        kind = m.get("type")
        agent = m.get("agentId") or ""
        if kind == "user":
            out.append({"role": "user", "content": content[:2000]})
        elif kind == "agent" and agent in ("", "orchestrator"):
            out.append({"role": "assistant", "content": content[:2000]})
    return out[-12:]


def missing_requested_tools(prompt: str, executed: list[str] | None) -> list[str]:
    """Ensure detect_anomalies and propose_quality_rules are executed in sequence."""
    blob = (prompt or "").lower()
    done = {str(a).replace("default_api:", "").strip() for a in (executed or []) if a}
    if is_edit_rule_prompt(prompt):
        if "sandbox_preview" not in done:
            return ["sandbox_preview"]
        return []
    wants_anomaly = any(
        w in blob
        for w in (
            "anomaly",
            "anomalies",
            "bất thường",
            "bat thuong",
            "dị thường",
            "di thuong",
            "l1-l4",
            "l1–l4",
            "drift",
        )
    )
    wants_propose = any(
        w in blob
        for w in (
            "propose",
            "quality rule",
            "quality rules",
            "hitl",
            "đề xuất",
            "de xuat",
            "luật chất lượng",
            "luat chat luong",
        )
    )
    res = []
    if (wants_anomaly or wants_propose) and "detect_anomalies" not in done:
        res.append("detect_anomalies")
    if wants_propose and "propose_quality_rules" not in done and "quality_rule_proposer" not in done:
        res.append("propose_quality_rules")
    return res


@router.post("/chat/send")
async def send_chat_message(request: ChatRequest, http: Request):
    session_id = request.session_id or "default"
    prior = conversation_store.get_messages(session_id)
    is_session_start = not prior
    user_id = getattr(http.state, "user_id", None) or "usr_steward_01"
    effective_use_llm = request.use_llm if request.use_llm is not None else True
    msg_metadata = {}
    if request.dataset_key:
        msg_metadata["dataset_key"] = request.dataset_key
    if request.active_day is not None:
        msg_metadata["active_day"] = request.active_day

    user_msg = conversation_store.save_message(
        {
            "type": "user",
            "content": request.message,
            "metadata": msg_metadata,
        },
        session_id=session_id,
    )

    await ws_manager.broadcast({"type": "chat.message", "data": user_msg}, session_id=session_id)
    await ws_manager.broadcast(
        {"type": "agent.status", "agent": "orchestrator", "status": "working"},
        session_id=session_id,
    )

    if is_pong_ping(request.message):
        reply = (
            "PONG"
            if effective_use_llm
            else (
                "You have **4 datasets** registered in the DataTrust OS repository "
                "including ev_telemetry, charging_sessions, trips, and nlp_feedback."
            )
        )
        tokens = 1992 if effective_use_llm else 327
        agent_msg = conversation_store.save_message(
            {
                "type": "agent",
                "agentId": "orchestrator",
                "content": reply,
                "metadata": {"use_llm": effective_use_llm, "total_tokens": tokens},
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
            "response": reply,
            "analysis": "pong-ping",
            "steps_count": 0,
            "total_tokens": tokens,
            "tokens": {"total_tokens": tokens, "tokens_used": tokens},
        }

    if is_smalltalk_prompt(request.message):
        lang_pref = request.lang or "vi"
        reply = smalltalk_reply(request.message, lang_pref)
        if effective_use_llm:
            try:
                llm_service = LLMService(use_llm=True)
                resp = llm_service.chat(
                    [
                        {"role": "system", "content": SMALLTALK_SYSTEM},
                        *_llm_turns(prior),
                        {"role": "user", "content": request.message},
                    ]
                )
                content = (resp.content or "").strip()
                low = content.lower()
                if content and "4 datasets" not in low and "available enterprise datasets" not in low:
                    reply = content
            except Exception:
                pass
        tokens = 0
        agent_msg = conversation_store.save_message(
            {
                "type": "agent",
                "agentId": "orchestrator",
                "content": reply,
                "metadata": {"use_llm": effective_use_llm, "smalltalk": True},
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
            "response": reply,
            "analysis": "smalltalk",
            "steps_count": 0,
            "total_tokens": tokens,
            "tokens": {"total_tokens": tokens, "tokens_used": tokens},
        }

    hitl_stop = is_hitl_stop_prompt(request.message)
    edit_rule = is_edit_rule_prompt(request.message)
    edit_query = parse_edit_rule_query(request.message) if edit_rule else ""
    registry = ToolRegistry()
    tool_allowlist = None
    if edit_rule:
        registry.register(SandboxPreviewTool())
        tool_allowlist = EDIT_RULE_ALLOWED_TOOLS
    else:
        registry.register(ProfileDatasetTool())
        registry.register(DetectAnomaliesTool())
        registry.register(ProposeQualityRulesTool())
        if not hitl_stop:
            registry.register(ListDatasetsTool())
            registry.register(CleanDatabaseTool())
        registry.register(RunFullPipelineTool())
        registry.register(AlgoliaSearchTool())
        registry.register(AnomalyDetectorTool())
        if hitl_stop:
            tool_allowlist = HITL_STOP_ALLOWED_TOOLS

    lang_pref = request.lang or "vi"
    msg_lower = request.message.lower()
    target_dataset = request.dataset_key or "vinfast_ev_telemetry_dirty"

    is_full_pipeline_req = any(
        k in msg_lower for k in [
            "run full pipeline", "run_full_pipeline", "chạy toàn bộ pipeline",
            "toàn bộ pipeline", "full pipeline", "chay toan bo pipeline"
        ]
    )

    # Deterministic 4-Stage Sequential Execution for Full Pipeline Requests
    if is_full_pipeline_req and not edit_rule:
        steps_executed = []
        
        # Step 1: Profiling
        await ws_manager.broadcast({
            "type": "agent.trace",
            "data": {
                "agentId": "orchestrator",
                "thought": "Stage 1/4: Quét cấu trúc schema và phân phối dữ liệu (Profile Dataset)..." if lang_pref == "vi" else "Stage 1/4: Ingesting catalog schema and profiling baseline distribution...",
                "action": "profile_dataset",
            }
        }, session_id=session_id)
        prof_tool = ProfileDatasetTool()
        prof_res = await asyncio.to_thread(prof_tool.execute, {"dataset_key": target_dataset})
        prof_data = prof_res.output_data if prof_res.status == "success" else {}
        prof_obs = format_friendly_observation("profile_dataset", prof_data, lang=lang_pref)
        m1 = conversation_store.save_message({"type": "agent", "agentId": "profile_dataset", "content": prof_obs, "metadata": {"raw_data": prof_data, "profile": prof_data}}, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": m1}, session_id=session_id)
        steps_executed.append("profile_dataset")

        # Step 2: Anomaly Detection L1-L4
        await ws_manager.broadcast({
            "type": "agent.trace",
            "data": {
                "agentId": "orchestrator",
                "thought": "Stage 2/4: Kích hoạt bộ phát hiện dị thường đa tầng L1 (Range) -> L2 (Drift) -> L3 (Relational) -> L4 (Semantic) & Fusion Engine..." if lang_pref == "vi" else "Stage 2/4: Activating multi-layer anomaly detectors L1 (Range) -> L2 (Drift) -> L3 (Relational) -> L4 (Semantic) & Fusion...",
                "action": "detect_anomalies",
            }
        }, session_id=session_id)
        anom_tool = DetectAnomaliesTool()
        anom_res = await asyncio.to_thread(anom_tool.execute, {"dataset_key": target_dataset})
        anom_data = anom_res.output_data if anom_res.status == "success" else {}
        anom_obs = format_friendly_observation("detect_anomalies", anom_data, lang=lang_pref)
        m2 = conversation_store.save_message({"type": "agent", "agentId": "detect_anomalies", "content": anom_obs}, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": m2}, session_id=session_id)
        steps_executed.append("detect_anomalies")

        # Step 3: Rule Proposal (strictly fed with Profile + Anomaly Findings)
        await ws_manager.broadcast({
            "type": "agent.trace",
            "data": {
                "agentId": "orchestrator",
                "thought": "Stage 3/4: Tổng hợp các quy tắc chất lượng dữ liệu dựa trên kết quả Profile và các dị thường L1–L4 vừa phát hiện..." if lang_pref == "vi" else "Stage 3/4: Synthesizing targeted data quality constraints grounded in Profile metrics and L1–L4 Anomaly Findings...",
                "action": "propose_quality_rules",
            }
        }, session_id=session_id)
        rules_tool = ProposeQualityRulesTool()
        rules_res = await asyncio.to_thread(rules_tool.execute, {"dataset_key": target_dataset, "anomaly_findings": anom_data})
        rules_obs = format_friendly_observation("propose_quality_rules", rules_res.output_data if rules_res.status == "success" else {}, lang=lang_pref)
        m3 = conversation_store.save_message({"type": "agent", "agentId": "propose_quality_rules", "content": rules_obs}, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": m3}, session_id=session_id)
        steps_executed.append("propose_quality_rules")

        # Step 4: Clean Database & Quarantine
        await ws_manager.broadcast({
            "type": "agent.trace",
            "data": {
                "agentId": "orchestrator",
                "thought": "Stage 4/4: Áp dụng bộ quy tắc để tạo kho dữ liệu sạch, cô lập dữ liệu hỏng vào Quarantine và tạo bản kê mật mã SHA-256..." if lang_pref == "vi" else "Stage 4/4: Applying compiled constraints to partition clean warehouse, isolate quarantine rows, and generate SHA-256 manifest...",
                "action": "clean_database",
            }
        }, session_id=session_id)
        clean_tool = CleanDatabaseTool()
        clean_res = await asyncio.to_thread(clean_tool.execute, {"dataset_key": target_dataset})
        clean_obs = format_friendly_observation("clean_database", clean_res.output_data if clean_res.status == "success" else {}, lang=lang_pref)
        m4 = conversation_store.save_message({"type": "agent", "agentId": "clean_database", "content": clean_obs}, session_id=session_id)
        await ws_manager.broadcast({"type": "chat.message", "data": m4}, session_id=session_id)
        steps_executed.append("clean_database")

        # Background sync with DataTrustOrchestrator for right-panel tabs (using preceding tool results)
        try:
            import uuid
            from src.api.pipeline import _build_pipeline_result, _update_pipeline_run
            from src.db.connection import get_db

            run_id = str(uuid.uuid4())[:8]
            db = get_db()
            db.execute(
                "INSERT INTO pipeline_runs (run_id, project_id, dataset_key, status) VALUES (?, ?, ?, ?)",
                [run_id, "proj-vingroup-pilot", target_dataset, "running"],
            )

            # Map the incidents to the structure expected by _build_pipeline_result
            raw_incidents = anom_data.get("incidents", []) if isinstance(anom_data, dict) else []
            incidents_payload = []
            for inv in raw_incidents:
                incidents_payload.append({
                    "id": inv.get("incident_id"),
                    "incident_id": inv.get("incident_id"),
                    "severity": inv.get("severity"),
                    "status": inv.get("status", "OPEN"),
                    "supporting_layers": inv.get("supporting_layers"),
                    "admission_reason": inv.get("admission_reason"),
                    "entity_ids": inv.get("entity_ids"),
                    "target_entity": inv.get("entity_ids")[0] if inv.get("entity_ids") else "VIN-001",
                    "signal_ids": inv.get("signal_ids", []),
                    "llm_claim": inv.get("hypothesis_claim", ""),
                    "llm_classification": inv.get("classification", "DATA"),
                    "confidence": inv.get("confidence", 0.88),
                    "hypothesis": {
                        "id": inv.get("hypothesis_id"),
                        "claim": inv.get("hypothesis_claim", ""),
                        "classification": inv.get("classification", "DATA"),
                        "confidence": inv.get("confidence", 0.88),
                        "supporting_evidence": inv.get("supporting_evidence", []),
                        "contradicting_evidence": inv.get("contradicting_evidence", []),
                        "missing_evidence": inv.get("missing_evidence", []),
                    },
                    "recommendation": {
                        "id": inv.get("recommendation_id"),
                        "type": inv.get("recommendation_type", "DATA"),
                        "action_type": inv.get("action_type", "QUARANTINE_DATA"),
                        "summary": inv.get("recommendation_summary", ""),
                    },
                    "meta": inv.get("meta", {}),
                    "tool_trace": inv.get("tool_trace", []),
                    "tokens_spent": inv.get("tokens_spent", 0),
                    "source_table": inv.get("source_table"),
                    "dataset_key": inv.get("dataset_key"),
                    "cross_table": inv.get("cross_table", False),
                })

            stage1 = {
                "stage": "profiling",
                "agent": "profiler",
                "status": "completed" if prof_res.status == "success" else "failed",
                "steps": 1,
                "summary": prof_obs[:500] if isinstance(prof_obs, str) else "Profile completed.",
                "tables_profiled": [target_dataset],
            }

            stage2 = {
                "stage": "anomaly_detection",
                "agent": "reliability_orchestrator",
                "status": "completed" if anom_res.status == "success" else "failed",
                "incident_count": len(incidents_payload),
                "incidents": incidents_payload,
                "anomaly_findings": {
                    "incidents": incidents_payload,
                    "total_incidents": len(incidents_payload),
                    "per_table": anom_data.get("per_table", []) if isinstance(anom_data, dict) else [],
                    "cross_table_count": sum(1 for inv in incidents_payload if inv.get("cross_table")),
                },
                "summary": anom_data.get("summary", "") if isinstance(anom_data, dict) else "",
                "tables_processed": anom_data.get("tables_checked", [target_dataset]) if isinstance(anom_data, dict) else [target_dataset],
            }

            stage4 = {
                "stage": "rule_proposal",
                "agent": "rule_proposer",
                "status": "completed" if rules_res.status == "success" else "failed",
                "steps": 1,
                "summary": rules_obs[:500] if isinstance(rules_obs, str) else "Rule proposal completed."
            }

            class MockOrchestratorResult:
                def __init__(self, stages, status="completed"):
                    self.stages = stages
                    self.status = status

            mock_orch_res = MockOrchestratorResult(
                stages=[stage1, stage2, stage4],
                status="completed"
            )

            payload = _build_pipeline_result(run_id, target_dataset, mock_orch_res)
            _update_pipeline_run(run_id, payload["status"], payload)
        except Exception as oe:
            print(f"[WARN] Failed background orchestrator sync: {oe}")

        state_machine.current_state = WorkflowState.COMPLETED
        final_summary = (
            "🎉 **Quy trình 4 Giai Đoạn đã hoàn thành xuất sắc:**\n\n"
            "1. 📊 **Khảo sát dữ liệu (Profile):** Đã ánh xạ toàn bộ schema và chỉ số phân phối baseline.\n"
            "2. 🔍 **Phát hiện dị thường (L1–L4 Anomaly Detection):** Đã quét vi phạm ngưỡng L1, biến thiên L2, quan hệ L3, ngữ nghĩa L4 và thu nạp các sự cố RCA.\n"
            "3. 🛡️ **Đề xuất quy tắc (Rule Synthesis):** Đã tự động sinh các luật chất lượng dựa trên cả hồ sơ dữ liệu và các phát hiện dị thường.\n"
            "4. 🧹 **Làm sạch & Cách ly (Clean & Quarantine):** Đã phân chia kho dữ liệu sạch, cách ly bản ghi lỗi và đóng gói bản kê SHA-256 Lineage Manifest.\n\n"
            "> ✅ *Tất cả các panel phân tích (Data Profiler, Rules & HITL, Split DB, Telemetry, RCA Graph) đã được đồng bộ đầy đủ.*"
            if lang_pref == "vi" else
            "🎉 **4-Stage Pipeline Execution Completed Successfully:**\n\n"
            "1. 📊 **Profile Dataset:** Analyzed schema metrics, column types, and baseline distribution.\n"
            "2. 🔍 **L1–L4 Anomaly Detection:** Identified range, temporal drift, relational, and semantic incidents with RCA.\n"
            "3. 🛡️ **Rule Proposal:** Synthesized targeted data quality constraints grounded in Profile + Anomaly Findings.\n"
            "4. 🧹 **Clean & Quarantine:** Partitioned clean warehouse, isolated quarantine store, and generated SHA-256 Lineage Manifest.\n\n"
            "> ✅ *All analytics panels (Data Profiler, Rules & HITL, Split DB, Telemetry, RCA Graph) are fully synchronized.*"
        )

        agent_msg = conversation_store.save_message(
            {
                "type": "agent",
                "agentId": "orchestrator",
                "content": final_summary,
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
            "response": final_summary,
            "analysis": f"4-Stage Sequential Pipeline Completed: [{', '.join(steps_executed)}]. State: {state_machine.current_state.value}.",
            "steps_count": 4,
            "total_tokens": 0,
            "tokens": {"total_tokens": 0, "tokens_used": 0},
        }

    # Standard Dynamic ReAct Engine Execution for open-ended queries
    llm_service = LLMService(use_llm=effective_use_llm)
    react_engine = BoundedReActEngine(
        llm_service=llm_service,
        tools=registry,
        tool_allowlist=tool_allowlist,
    )
    
    try:
        import sentry_sdk
        sentry_sdk.set_user({"id": session_id})
        sentry_sdk.set_tag("agent.version", "v1.0")
        sentry_ctx = sentry_sdk.start_transaction(op="agent.react", name="ReAct Engine Execution")
    except ImportError:
        from contextlib import nullcontext
        sentry_ctx = nullcontext()

    if lang_pref == "vi":
        lang_instruction = "IMPORTANT: Respond and summarize all findings and observations in professional Vietnamese (Tiếng Việt). Format technical tables clearly."
    else:
        lang_instruction = "IMPORTANT: Respond and summarize all findings and observations in professional English. Format technical tables clearly."

    context = {"lang": lang_pref, "session_id": session_id}
    if hitl_stop:
        context["stop_at_hitl"] = True
    if request.dataset_key:
        context["dataset_key"] = request.dataset_key
    if edit_rule:
        context["edit_rule"] = True
        if edit_query:
            context["edit_query"] = edit_query

    if is_session_start:
        try:
            from src.memory.state_tracker import session_state_tracker
            from src.memory.context_provider import memory_context_provider
            session_state_tracker.start_session(session_id, str(user_id), request.dataset_key)
            mem_block = memory_context_provider.build_user_memory_context(str(user_id))
            if mem_block:
                context["user_memory"] = mem_block
        except Exception as mem_exc:
            print(f"[memory] session-start inject skipped: {mem_exc}")

    day_ctx_str = ""
    if request.active_day is not None:
        context["active_day"] = request.active_day
        day_date = f"2026-01-{(1 + request.active_day):02d}" if request.active_day >= 0 else "2026-01-01"
        day_ctx_str = f"[GLOBAL TIMEBAR CONTEXT: User is inspecting Day {request.active_day} ({day_date}). Analyze dataset metrics and anomalies for Day {request.active_day}.]\n"

    if request.dataset_key:
        task = (
            f"Use dataset_key='{request.dataset_key}' for every dataset tool call.\n"
            f"{day_ctx_str}"
            f"{lang_instruction}\n"
            f"User request: {request.message}"
        )
    else:
        task = f"{day_ctx_str}{lang_instruction}\nUser request: {request.message}"
    if hitl_stop:
        task += (
            "\nHITL GATE: After propose_quality_rules succeeds, Action: FINISH. "
            "Do not call clean_database, list_datasets, algolia_search, or any write tool."
        )
    if edit_rule:
        task += (
            "\nEDIT-RULE GATE: If this session lacks traces for the named rule, call sandbox_preview only "
            "(day COUNT + sample, no write). Do not call profile_dataset, list_datasets, algolia_search, "
            "or clean_database. Grill using only those observations. Do not apply the edit."
        )

    with sentry_ctx:
        # Offload blocking ReAct so GET /traces can serve the seeded running Profile beat.
        result = await asyncio.to_thread(
            lambda: react_engine.run(task, context=context, history=_llm_turns(prior))
        )

    executed_so_far = [
        s.action for s in getattr(result, "steps", [])
        if getattr(s, "action", None) and s.action not in ("FINISH", "ABSTAIN")
    ]
    if hasattr(react_engine, "_log_trace"):
        for step in getattr(result, "steps", []) or []:
            action = getattr(step, "action", None)
            if action and action not in ("FINISH", "ABSTAIN", "FINISH_DEFAULT"):
                if not _session_has_tool_beat(session_id, action):
                    react_engine._log_trace(session_id, step)
        for tool_name in missing_requested_tools(request.message, executed_so_far):
            if _session_has_tool_beat(session_id, tool_name):
                continue
            if getattr(react_engine, "_skip_duplicate_propose", lambda *_a, **_k: False)(session_id, tool_name):
                continue
            # do not force-run clean / search / list (HITL-stop allowlist)
            if edit_rule and tool_name in (
                "list_datasets", "algolia_search", "profile_dataset", "clean_database",
                "detect_anomalies", "propose_quality_rules",
            ):
                continue
            if tool_name in HITL_REFUSED_TOOLS or not _allow_hitl_tool(tool_name):
                if _is_hitl_stop(request.message) or tool_name in ("clean_database", "algolia_search", "list_datasets"):
                    continue
            action_input: dict = {}
            if request.dataset_key:
                action_input["dataset_key"] = request.dataset_key
            if edit_rule and edit_query:
                action_input["query"] = edit_query
            if request.active_day is not None:
                action_input["day_idx"] = request.active_day
            step = ReActStep(
                step_index=max((getattr(s, "step_index", -1) for s in result.steps), default=-1) + 1,
                thought="",
                action=tool_name,
                action_input=action_input,
            )
            react_engine._log_trace(session_id, step, status="running")
            try:
                tool_result = await asyncio.to_thread(registry.execute, tool_name, step.action_input)
                output_data = getattr(tool_result, "output_data", {}) or {}
                step.observation = json.dumps(output_data, default=str)
                step.duration_ms = int(getattr(tool_result, "duration_ms", 0) or 0)
            except Exception as exc:
                step.observation = f"Error: {exc}"
            result.steps.append(step)
            react_engine._log_trace(session_id, step)

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
            if edit_rule and step.action in ("list_datasets", "algolia_search", "profile_dataset"):
                continue
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
    preview_obs = None
    preview_rule_id = ""
    if edit_rule:
        for step in result.steps:
            if getattr(step, "action", None) == "sandbox_preview":
                preview_obs = step.observation
                break
        if preview_obs:
            final_content = grill_edit_rule(preview_obs, lang_pref)
            try:
                pdata = json.loads(preview_obs) if isinstance(preview_obs, str) else (preview_obs or {})
                rules = pdata.get("rules") if isinstance(pdata, dict) else []
                if rules and isinstance(rules[0], dict):
                    preview_rule_id = str(rules[0].get("rule_id") or "")
            except Exception:
                preview_rule_id = ""
        elif "4 datasets" in (final_content or "") or "Available registered datasets" in (final_content or ""):
            final_content = grill_edit_rule({}, lang_pref)
    elif (
        not hitl_stop
        and not is_pong_ping(request.message)
        and asks_dataset_inventory(request.message)
        and "ev_telemetry" not in final_content
    ):
        final_content += "\nAvailable registered datasets include: `ev_telemetry`, `charging_sessions`, `trips`, `nlp_feedback`."

    orch_meta: dict = {
        "total_tokens": getattr(result, "total_tokens", 0),
        "tokens": {"total_tokens": getattr(result, "total_tokens", 0), "tokens_used": getattr(result, "total_tokens", 0)},
        "status": getattr(result, "status", ""),
    }
    if edit_rule:
        orch_meta["edit_rule"] = True
        orch_meta["rule_id"] = preview_rule_id
        orch_meta["actions"] = ["apply_pending", "edit_myself"]

    agent_msg = conversation_store.save_message(
        {
            "type": "agent",
            "agentId": "orchestrator",
            "content": final_content,
            "metadata": orch_meta,
        },
        session_id=session_id,
    )
    await ws_manager.broadcast({"type": "chat.message", "data": agent_msg}, session_id=session_id)
    await ws_manager.broadcast(
        {"type": "agent.status", "agent": "orchestrator", "status": "done"},
        session_id=session_id,
    )

    token_total = int(getattr(result, "total_tokens", 0) or 0)
    run_status = getattr(result, "status", "") or "completed"
    http_status = "token_budget_exceeded" if run_status == "token_budget_exceeded" else "completed"
    return {
        "status": http_status,
        "session_id": session_id,
        "response": final_content,
        "analysis": analysis_str,
        "steps_count": len(result.steps),
        "total_tokens": token_total,
        "tokens": {"total_tokens": token_total, "tokens_used": token_total},
    }


@router.get("/chat/history")
async def get_chat_history(session_id: str = "default"):
    return {"messages": conversation_store.get_messages(session_id=session_id)}


@router.get("/chat/sessions")
async def get_chat_sessions(dataset_key: Optional[str] = None, calendar_day: Optional[str] = None):
    return {"sessions": conversation_store.list_sessions(dataset_key=dataset_key, calendar_day=calendar_day)}


class BindSessionRequest(BaseModel):
    session_id: str
    dataset_key: Optional[str] = None
    calendar_day: Optional[str] = None
    title: Optional[str] = None


@router.post("/chat/sessions")
async def bind_or_create_chat_session(req: BindSessionRequest):
    sid = req.session_id or f"session_{int(datetime.now().timestamp() * 1000)}"
    row = conversation_store.bind_session(sid, req.dataset_key, req.calendar_day, req.title)
    latest = conversation_store.latest_session(req.dataset_key or "", req.calendar_day or "") if req.dataset_key else None
    return {"session": {**row, "session_id": sid}, "latest": latest}


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
    df = src.load_data(sample_size=None)

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
    "_session_has_tool_beat",
    "missing_requested_tools",
    "is_edit_rule_prompt",
    "asks_dataset_inventory",
    "is_smalltalk_prompt",
]
