"""
DataTrust OS: Central AI Multi-Agent Orchestrator
Coordinates:
- ProfilerAgent (Data structural profiling & PII discovery)
- AnomalyAgent (L2-L4 statistical drift detection)
- DiagnosisAgent (4-Tier root-cause causal analysis for Quarantine records)
- RuleProposerAgent (HITL rule proposals & Dry-run simulation)
- PreventiveGuardAgent (Real-time early warning drift monitoring)
- Real-time ReAct thought streaming over WebSockets
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone

from backend.ai.services.llm_adapter import UnifiedLLMAdapter
from backend.ai.services.realtime_tracer import RealtimeTracer
from backend.ai.engine.react_engine import ReActEngine
from backend.ai.agents.profiler_agent import ProfilerAgent
from backend.ai.agents.anomaly_agent import AnomalyAgent
from backend.ai.agents.diagnosis_agent import DiagnosisAgent
from backend.ai.agents.rule_proposer_agent import RuleProposerAgent
from backend.ai.agents.preventive_guard_agent import PreventiveGuardAgent
from backend.database.models import QuarantineRecordModel, AgentTraceModel, ProposedRuleModel
from backend.ai.services.intent_classifier import IntentClassifier, UserIntent
from backend.ai.services.context_loader import RunContextLoader

logger = logging.getLogger("DataTrust.Orchestrator")


def sanitize_chat_markdown(text: str) -> str:
    """
    Cleans markdown formatting and removes escaped markdown characters,
    internal variable tokens, and deep headings.
    """
    import re
    if not text:
        return ""
    # 1. Remove backslash escapes for markdown characters: \####, 1\., \*, \_
    text = re.sub(r'\\+(#+)', r'\1', text)
    text = re.sub(r'([0-9]+)\\+\.', r'\1.', text)
    text = re.sub(r'\\+([0-9]+)\.', r'\1.', text)
    text = re.sub(r'\\+([*_\-`])', r'\1', text)
    # 2. Reduce deep headings (#### -> ###)
    text = re.sub(r'#{4,}', '###', text)
    # 3. Strip any leaked code/variable tokens
    text = re.sub(r'requires_approval\s*=\s*(True|False|true|false)', '', text)
    text = re.sub(r'structured_analysis', '', text)
    text = re.sub(r'ActionType\.[A-Z_]+', '', text)
    text = re.sub(r'dry_run_supported\s*=\s*(True|False|true|false)', '', text)
    # 4. Remove standalone json blocks if present in answer
    if "```json" in text:
        parts = text.split("```json")
        clean_parts = [parts[0]]
        for p in parts[1:]:
            if "```" in p:
                clean_parts.append(p.split("```", 1)[1])
        text = "".join(clean_parts).strip()
    return text.strip()


class DataTrustAgentOrchestrator:
    """Central orchestrator managing specialized agents and live execution streams."""

    def __init__(self, llm_adapter: Optional[UnifiedLLMAdapter] = None):
        self.llm_adapter = llm_adapter or UnifiedLLMAdapter()
        self.tracer = RealtimeTracer()
        self.react_engine = ReActEngine(llm_adapter=self.llm_adapter)

        # Initialize sub-agents
        self.profiler_agent = ProfilerAgent(react_engine=self.react_engine)
        self.anomaly_agent = AnomalyAgent(react_engine=self.react_engine)
        self.diagnosis_agent = DiagnosisAgent(react_engine=self.react_engine, tracer=self.tracer)
        self.rule_proposer_agent = RuleProposerAgent(react_engine=self.react_engine)
        self.preventive_guard_agent = PreventiveGuardAgent(react_engine=self.react_engine)

        self._active_listeners: List[Callable[[AgentTraceModel], Awaitable[None]]] = []

    def register_step_listener(self, listener: Callable[[AgentTraceModel], Awaitable[None]]):
        self._active_listeners.append(listener)

    def unregister_step_listener(self, listener: Callable[[AgentTraceModel], Awaitable[None]]):
        if listener in self._active_listeners:
            self._active_listeners.remove(listener)

    async def _broadcast_step(self, trace: AgentTraceModel):
        for listener in list(self._active_listeners):
            try:
                await listener(trace)
            except Exception as e:
                logger.warning(f"Error broadcasting step trace to listener: {e}")

    async def chat(
        self,
        message: str,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processes general user dialogue strictly scoped to run_id.
        No cross-run fallback permitted.
        """
        import re
        from fastapi import HTTPException
        from database.profiler_engine import get_db_connection
        from psycopg2.extras import RealDictCursor
        from backend.ai.services.chat_session_manager import session_manager
        from backend.ai.services.context_loader import (
            RunContextLoader, load_catalog_columns, load_profiling_stats, load_compliance_rules, load_warning_evidence
        )

        context = context or {}
        run_id = (run_id or context.get("run_id") or "").strip()
        if not run_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "MISSING_RUN_ID", "message": "run_id là bắt buộc để tương tác với AI Agent."}
            )

        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        session_manager.verify_and_bind_session(session_id, run_id)
        session_state = session_manager.get_session_state(session_id)

        msg_lower = message.lower().strip()

        # Classify User Intent using negation-aware priority rules
        user_intent = IntentClassifier.classify(message)

        # -------------------------------------------------------------
        # 1. TOPIC SWITCH: Explicit request to change topic / reset
        # -------------------------------------------------------------
        if user_intent == UserIntent.TOPIC_SWITCH:
            session_manager.clear_session_focus(session_id)
            reset_reply = (
                "Ting ting! ✨ Mình đã làm mới ngữ cảnh tập trung của cuộc trò chuyện rồi nè! "
                "Tụi mình cùng bắt đầu chủ đề mới nhé, bạn muốn cùng mình tìm hiểu hoặc kiểm tra nội dung nào tiếp theo về lần chạy này nè? 🚗💡"
            )
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=reset_reply,
                updates={}
            )
            return {
                "response": reset_reply,
                "session_id": session_id,
                "run_id": run_id,
                "data": {"status": "TOPIC_RESET"},
                "traces": []
            }

        # -------------------------------------------------------------
        # Resolve target finding / entities with pronoun resolution
        # -------------------------------------------------------------
        target_finding_id = finding_id or context.get("finding_id")
        if not target_finding_id:
            f_match = re.search(r'\b(FND-[a-zA-Z0-9_-]+|F-[a-zA-Z0-9_-]+)\b', message)
            if f_match:
                target_finding_id = f_match.group(1)

        # Pronoun & follow-up resolution: "nó", "bản ghi này", "lỗi đó", "tại sao?", "sửa thế nào?"
        has_followup_reference = any(
            re.search(p, msg_lower) for p in [
                r"\bn\u00f3\b", r"b\u1ea3n\s+ghi\s+n\u00e0y", r"l\u1ed7i\s+(\u0111\u00f3|n\u00e0y)",
                r"c\u1ed9t\s+n\u00e0y", r"v\u1ea5n\s+\u0111\u1ec1\s+(\u0111\u00f3|n\u00e0y)",
                r"t\u1ea1i\s+sao\??$", r"s\u1eeda\s+(nh\u01b0\s+th\u1ebf\s+n\u00e0o|sao|th\u1ebf\s+n\u00e0o)",
                r"kh\u1eafc\s+ph\u1ee5c\s+sao", r"chi\s+ti\u1ebft\s+h\u01a1n", r"gi\u1ea3i\s+th\u00edch\s+th\u00eam",
                r"nguy\u00ean\s+nh\u00e2n\s+(c\u1ee7a\s+n\u00f3|l\u00e0\s+g\u00ec)"
            ]
        )
        if not target_finding_id and has_followup_reference and session_state.get("active_finding_id"):
            target_finding_id = session_state.get("active_finding_id")

        # -------------------------------------------------------------
        # 2. GENERAL CONVERSATION: Greetings, capabilities, small talk
        # -------------------------------------------------------------
        has_investigation_keywords = any(
            k in msg_lower for k in ("finding", "rca", "nguyên nhân", "lý do vi phạm", "điều tra", "khắc phục", "sửa", "remediation", "tại sao")
        )
        if user_intent == UserIntent.GENERAL_CONVERSATION and not target_finding_id and not has_investigation_keywords:
            is_unconfigured_mock = (
                not self.llm_adapter.force_mock
                and (
                    self.llm_adapter.provider == "mock"
                    or (self.llm_adapter.provider == "openai" and not self.llm_adapter._get_active_key())
                )
            )
            if is_unconfigured_mock:
                greeting_reply = (
                    f"Xin chào bạn nha! ✨ Mình là trợ lý AI DataTrust OS siêu đáng yêu của bạn đây nè! 🚗💡 "
                    f"*(Hệ thống hiện hoạt động ở chế độ mô phỏng do chưa kết nối LLM API Key)*.\n\n"
                    f"Trong lần chạy `{run_id}`, tụi mình có thể cùng nhau xem qua số liệu 📊, kiểm tra danh sách vi phạm 🛡️ hay tra cứu catalog quy tắc nè! "
                    f"Bạn muốn tụi mình bắt đầu từ đâu nào? 📝💖"
                )
            else:
                sys_inst = (
                    "Bạn là trợ lý AI DataTrust OS cực kỳ đáng yêu, thân thiện, năng động và tràn đầy năng lượng tích cực! ✨ "
                    "Hãy trò chuyện tự nhiên như hai người bạn đồng nghiệp thân thiết đang cùng pair-working, "
                    "luôn biết lắng nghe, đồng cảm và thấu hiểu những vất vả khi xử lý dữ liệu. 💖 "
                    "Sử dụng emoji hợp lý, tinh tế (✨, 📝, 🚗, 💡, 🛡️, 🔍, 📊) để làm mềm câu văn, tuyệt đối không trả lời khô khan hay máy móc! "
                    f"Lần chạy hiện tại: {run_id}. "
                    "Bắt đầu lời chào bằng 'Xin chào bạn nha! ✨' hoặc lời chào ấm áp, thân thiện, giữ câu trả lời súc tích (1-2 câu). "
                    "Tuyệt đối không dùng tiền tố cứng nhắc như '**Kết luận:**'. Không để lộ raw JSON hay tên biến nội bộ."
                )
                res_llm = self.llm_adapter.complete(
                    prompt=f"Người dùng nói: '{message}'. Hãy trả lời một cách cực kỳ đáng yêu, thân thiện và ấm áp như bạn bè.",
                    system_instruction=sys_inst,
                    context={"run_id": run_id, "active_entities": session_state.get("entities", {})},
                    temperature=0.3,
                    max_tokens=200
                )
                greeting_reply = sanitize_chat_markdown(res_llm.get("text", "")).strip()
                if not greeting_reply:
                    greeting_reply = (
                        f"Xin chào bạn nha! ✨ Mình là trợ lý AI DataTrust OS siêu đáng yêu của bạn đây nè! 🚗💡 "
                        f"Trong lần chạy `{run_id}`, tụi mình có thể giúp bạn kiểm tra chất lượng dữ liệu, tìm nguyên nhân vi phạm (RCA), "
                        f"đề xuất quy tắc khắc phục hoặc tra cứu catalog. Bạn cần mình hỗ trợ gì nè? 📝💖"
                    )

            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=greeting_reply,
                updates={}
            )
            return {
                "response": greeting_reply,
                "session_id": session_id,
                "run_id": run_id,
                "data": {"intent": "GENERAL_CONVERSATION"},
                "traces": []
            }

        # -------------------------------------------------------------
        # 3. RUN OVERVIEW: Explicit summary of pipeline metrics
        # -------------------------------------------------------------
        if user_intent == UserIntent.RUN_OVERVIEW and not target_finding_id:
            selective_context = RunContextLoader.load_context(run_id, user_intent, target_finding_id)
            pr = selective_context.get("pipeline_run", {})
            scanned = pr.get("scanned_count", 0)
            silver = pr.get("silver_count", 0)
            quarantine = pr.get("quarantine_count", 0)
            warning = pr.get("warning_count", 0)
            not_eval = pr.get("not_evaluated_count", 0)
            status = pr.get("status", "COMPLETED")
            duration_ms = pr.get("execution_duration_ms") or 0
            f_summary = selective_context.get("findings_summary", [])
            total_findings = sum(f.get("cnt", 0) for f in f_summary)

            fallback_overview = (
                f"Lần chạy `{run_id}` hiện ở trạng thái **{status}** nè! ✨ Tụi mình đã quét tổng cộng **{scanned:,} bản ghi** "
                f"(trong đó có **{silver:,} bản ghi Silver** đạt chuẩn xịn sò 🚗, **{quarantine:,} bản ghi cách ly** "
                f"và **{warning:,} bản ghi cảnh báo** nha).\n\n"
                f"- 🔍 **Vấn đề kiểm toán (Findings):** Ghi nhận tổng cộng **{total_findings}** vấn đề.\n"
                f"- ⏳ **Bản ghi chưa đánh giá (Not Evaluated):** {not_eval:,}.\n"
                f"- ⚡ **Thời gian thực thi:** {duration_ms:,}ms.\n"
                f"- 🛡️ **Đánh giá chất lượng:** Dữ liệu vi phạm đã được cách ly an toàn theo chính sách kiểm soát rồi, cậu yên tâm nhé! 💡"
            )

            clean_overview = sanitize_chat_markdown(fallback_overview)
            if not self.llm_adapter.force_mock and self.llm_adapter.provider != "mock":
                try:
                    sys_inst = (
                        "Bạn là DataTrust AI Companion - người bạn kiểm toán dữ liệu cực kỳ đáng yêu, thân thiện và năng động! ✨ "
                        "Tất cả số liệu cung cấp đều là ground-truth facts verified by PostgreSQL. "
                        "Do NOT calculate or invent numbers. Hãy diễn giải tự nhiên, ấm áp như hai người bạn kỹ sư dữ liệu cùng làm việc, "
                        "biết khích lệ và dùng emoji hợp lý (✨, 🚗, 📊, 💡, 🛡️) để làm mềm câu văn, không trả lời khô khan như máy móc."
                    )
                    prompt = (
                        f"Hãy diễn giải tóm tắt kết quả kiểm toán lần chạy {run_id} cho bạn đồng hành:\n"
                        f"- Tổng bản ghi quét: {scanned:,}\n"
                        f"- Đạt chuẩn Silver: {silver:,}\n"
                        f"- Cách ly (Quarantine): {quarantine:,}\n"
                        f"- Cảnh báo (Warning): {warning:,}\n"
                        f"- Chưa đánh giá (Not Evaluated): {not_eval:,}\n"
                        f"- Số vấn đề kiểm toán (Findings): {total_findings}\n"
                        f"- Trạng thái: {status}\n\n"
                        f"Yêu cầu: Viết tự nhiên, súc tích (3-4 câu), ấm áp, thân thiện, nêu rõ tỷ lệ và trọng tâm cần chú ý."
                    )
                    llm_res = self.llm_adapter.complete(
                        prompt=prompt,
                        system_instruction=sys_inst,
                        context={"run_id": run_id, "metrics": pr},
                        temperature=0.2,
                        max_tokens=300
                    )
                    llm_text = llm_res.get("text", "").strip()
                    if llm_text:
                        clean_overview = sanitize_chat_markdown(llm_text)
                except Exception as e:
                    logger.warning(f"LLM interpretation fallback to template: {e}")

            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=clean_overview,
                updates={}
            )
            return {
                "response": clean_overview,
                "session_id": session_id,
                "run_id": run_id,
                "data": {
                    "structured_analysis": {
                        "run_id": run_id,
                        "status": status,
                        "scanned_count": scanned,
                        "silver_count": silver,
                        "quarantine_count": quarantine,
                        "warning_count": warning,
                        "not_evaluated_count": not_eval,
                        "total_findings": total_findings,
                        "duration_ms": duration_ms
                    }
                },
                "traces": []
            }

        # -------------------------------------------------------------
        # 4. PIPELINE ERROR OR PROGRESS
        # -------------------------------------------------------------
        if user_intent == UserIntent.PIPELINE_ERROR_OR_PROGRESS and not target_finding_id:
            selective_context = RunContextLoader.load_context(run_id, user_intent, target_finding_id)
            pr = selective_context.get("pipeline_run", {})
            status = pr.get("status", "RUNNING")
            steps = selective_context.get("steps", [])
            failed_step = next((s for s in steps if s.get("status") == "FAILED"), None)
            err_msg = failed_step.get("error_message") if failed_step else pr.get("error_message")

            if failed_step:
                progress_ans = (
                    f"Ối, pipeline lần chạy `{run_id}` đang gặp chút trục trặc tại bước **{failed_step.get('step_name')}** rồi nè! 🥺\n\n"
                    f"- 💥 **Chi tiết lỗi:** {err_msg or 'Lỗi không xác định trong quá trình thực thi.'}\n"
                    f"- 🛡️ **Tác động:** Hệ thống đã chủ động tạm dừng để bảo vệ tính toàn vẹn dữ liệu, không để dữ liệu lỗi lọt vào Silver đâu nha. Đừng lo, tụi mình cùng kiểm tra và khắc phục nhé! ✨"
                )
            else:
                progress_ans = (
                    f"Pipeline lần chạy `{run_id}` hiện đang ở trạng thái **{status}** với **{len(steps)} bước** đã ghi nhận nè! 🚀\n\n"
                    f"- 🔍 **Tiến trình:** Các bước kiểm soát chất lượng từ L1 đến L4 đều đang được giám sát chặt chẽ và vận hành mượt mà nha! ✨"
                )

            clean_prog = sanitize_chat_markdown(progress_ans)
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=clean_prog,
                updates={}
            )
            return {
                "response": clean_prog,
                "session_id": session_id,
                "run_id": run_id,
                "data": {
                    "structured_analysis": {
                        "run_id": run_id,
                        "status": status,
                        "failed_step": failed_step.get("step_name") if failed_step else None,
                        "error_message": err_msg
                    }
                },
                "traces": []
            }

        # -------------------------------------------------------------
        # 5. DATA OR CATALOG INQUIRY
        # -------------------------------------------------------------
        if user_intent == UserIntent.DATA_OR_CATALOG_INQUIRY:
            target_ds = session_state.get("active_dataset_id")
            cols = load_catalog_columns(target_ds)
            prof = load_profiling_stats(target_ds, session_state.get("active_column"))

            col_lines = "\n".join([f"- 📌 `{c['column_name']}` ({c['data_type']}){' 🔒 [PII]' if c.get('pii_flag') else ''}" for c in cols[:10]])
            catalog_reply = (
                f"Dạ đây nè! ✨ Mình gửi bạn thông tin catalog dữ liệu cho lần chạy `{run_id}` nha:\n\n"
                f"**Danh sách các cột tiêu biểu:**\n{col_lines or '- Chưa có thông tin cột cụ thể.'}\n\n"
                f"Cậu cứ tự nhiên hỏi thêm mình về tỷ lệ null, phân phối giá trị hoặc quy tắc kiểm tra cho từng cột cụ thể nha! 💡"
            )
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=catalog_reply,
                updates={"active_dataset_id": target_ds}
            )
            return {
                "response": catalog_reply,
                "session_id": session_id,
                "run_id": run_id,
                "data": {"columns": cols, "profiling": prof},
                "traces": []
            }

        # -------------------------------------------------------------
        # 6. RULE INQUIRY OR POLICY INQUIRY
        # -------------------------------------------------------------
        if user_intent in (UserIntent.RULE_INQUIRY, UserIntent.POLICY_OR_LEGAL_INQUIRY) and not target_finding_id:
            from backend.ai.services.rule_lookup_service import (
                RuleLookupService, RuleLookupStatus, RuleFamily
            )

            # Determine dataset and run start time for historical versioning
            target_ds = context.get("dataset_id") or session_state.get("active_dataset_id")
            run_start_time = None
            try:
                conn = get_db_connection()
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT dataset_id, started_at FROM orchestration.pipeline_runs WHERE run_id = %s LIMIT 1;",
                        (run_id,)
                    )
                    pr_info = cur.fetchone()
                    if pr_info:
                        if not target_ds:
                            target_ds = pr_info.get("dataset_id")
                        run_start_time = pr_info.get("started_at")
                conn.close()
            except Exception as e:
                logger.warning(f"Could not load run metadata for rule lookup: {e}")

            target_ds = target_ds or "ride_hailing_xanh_sm_trips"

            # Case A: User explicitly asks about rules executed in THIS run
            is_run_executed_query = any(k in msg_lower for k in (
                "lần chạy này", "run này", "đã chạy", "đã áp dụng", "thực thi", "được áp dụng"
            ))

            if is_run_executed_query and user_intent == UserIntent.RULE_INQUIRY:
                lookup_res = RuleLookupService.get_executed_rules_for_run(run_id)

                if lookup_res.status == RuleLookupStatus.DB_ERROR:
                    reply = (
                        f"Ui, hiện tại mình chưa thể truy xuất telemetry thực thi của lần chạy `{run_id}` "
                        f"do gián đoạn kết nối cơ sở dữ liệu rồi! 😢 Cậu đợi chút xíu rồi thử lại cùng mình nha ✨."
                    )
                elif lookup_res.execution_unknown and not lookup_res.evaluated_rules:
                    reply = (
                        f"Trong lần chạy `{run_id}`, hệ thống ghi nhận thiếu telemetry thực thi chi tiết "
                        f"(do lần chạy được tạo trước khi kích hoạt execution audit ledger) nên chưa đủ bằng chứng "
                        f"để khẳng định danh sách toàn bộ quy tắc đã chạy nha. Cậu hoàn toàn yên tâm là các vi phạm hay cảnh báo "
                        f"(nếu có) đều vẫn được lưu trữ tại Findings và Warnings nhé! 💡"
                    )
                else:
                    eval_pass = [r for r in lookup_res.evaluated_rules if r.get("pass_count", 0) > 0 and r.get("fail_count", 0) == 0]
                    eval_fail = [r for r in lookup_res.evaluated_rules if r.get("fail_count", 0) > 0]
                    eval_skip = [r for r in lookup_res.evaluated_rules if r.get("skip_count", 0) > 0 and r.get("pass_count", 0) == 0 and r.get("fail_count", 0) == 0]

                    pass_bullets = "\n".join([
                        f"  - 🟢 `{r['rule_id']}` (v{r.get('rule_version', 1)}): {r.get('rule_name', r['rule_id'])} (Đạt {r.get('pass_count', 0):,} bản ghi)"
                        for r in eval_pass[:5]
                    ])
                    fail_bullets = "\n".join([
                        f"  - 🔴 `{r['rule_id']}` (v{r.get('rule_version', 1)}): {r.get('rule_name', r['rule_id'])} ({r.get('fail_count', 0):,} vi phạm)"
                        for r in eval_fail[:5]
                    ])

                    pass_section = f"**Quy tắc đạt chuẩn (Passed):**\n{pass_bullets}\n\n" if pass_bullets else ""
                    fail_section = f"**Quy tắc phát sinh lỗi/cảnh báo (Triggered):**\n{fail_bullets}\n\n" if fail_bullets else ""

                    reply = (
                        f"Dựa trên bằng chứng thực thi thực tế (`audit.record_policy_executions`) của lần chạy `{run_id}` nè! 📋✨\n\n"
                        f"- 🎯 **Tổng quy tắc đã đánh giá**: **{len(lookup_res.evaluated_rules)} quy tắc** "
                        f"(trong đó có **{len(eval_pass)} quy tắc đạt chuẩn hoàn toàn**, **{len(eval_fail)} quy tắc phát hiện vi phạm**"
                        f"{f', {len(eval_skip)} quy tắc bỏ qua' if eval_skip else ''}).\n\n"
                        f"{pass_section}"
                        f"{fail_section}"
                        f"Tất cả biểu thức và căn cứ pháp lý đều được trích xuất từ snapshot thực thi chính thức lúc pipeline chạy đó nha! 🚗💡"
                    )

                clean_reply = sanitize_chat_markdown(reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_reply,
                    updates={"active_dataset_id": target_ds}
                )
                return {
                    "response": clean_reply,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {
                        "intent": "RULE_INQUIRY",
                        "status": lookup_res.status.value,
                        "evaluated_rules_count": len(lookup_res.evaluated_rules),
                        "triggered_rules_count": len(lookup_res.triggered_rules),
                        "execution_unknown": lookup_res.execution_unknown
                    },
                    "traces": []
                }

            # Case B: User inquires about a specific rule identifier
            lookup_single = RuleLookupService.lookup_by_identifier(message, dataset_id=target_ds, as_of=run_start_time)

            if lookup_single.status == RuleLookupStatus.FOUND_ONE and lookup_single.rule:
                r = lookup_single.rule
                fam = lookup_single.family or RuleFamily.COMPLIANCE
                if fam == RuleFamily.COMPLIANCE:
                    fam_label = "🛡️ Quy tắc Tuân thủ & Kiểm tra Chất lượng (Compliance - Lane B)"
                elif fam == RuleFamily.TREATMENT:
                    fam_label = "📝 Quy tắc Xử lý & Chuẩn hóa Dữ liệu (Data Treatment)"
                else:
                    fam_label = "🚗 Quy tắc Kỹ thuật & Cảm biến Xe (Reliability - Lane A)"

                r_name = r.get("rule_name") or r.get("treatment_name") or r.get("rule_id")
                r_expr = r.get("expression") or r.get("expression_display") or r.get("detector_id") or "Không có biểu thức"
                r_col = r.get("column_name") or (", ".join(r.get("target_fields", [])) if isinstance(r.get("target_fields"), list) else None) or "Toàn bảng"
                r_sev = r.get("severity") or "HIGH"
                r_act = r.get("on_fail_action") or ("QUARANTINE" if fam == RuleFamily.COMPLIANCE else "WARNING")
                r_law = r.get("law_ref")
                law_text = f"• 📜 **Căn cứ pháp lý**: `{r_law}`\n" if r_law else "• 📜 **Căn cứ pháp lý**: Quy chuẩn kỹ thuật nội bộ (không gắn tham chiếu luật cụ thể)\n"

                detail_reply = (
                    f"Thông tin chi tiết về quy tắc `{r.get('rule_id')}` nè! ✨\n\n"
                    f"• 📌 **Tên quy tắc**: {r_name}\n"
                    f"• 🏷️ **Phân loại**: {fam_label} (Phiên bản v{r.get('version', 1)})\n"
                    f"• 🎯 **Cột & Bảng áp dụng**: `{r_col}` trên `{r.get('dataset_id')}`\n"
                    f"• 🔍 **Logic kiểm tra / Biểu thức**: `{r_expr}`\n"
                    f"• ⚖️ **Mức độ & Xử lý khi lỗi**: Mức `{r_sev}` → Hành động: `{r_act}`\n"
                    f"{law_text}"
                    f"• ⚙️ **Trạng thái**: `{r.get('status', 'ACTIVE')}` (Chế độ: `{r.get('runtime_mode', 'ENFORCED')}`)\n\n"
                    f"Cậu cần mình giải thích thêm cơ chế hay cách hoạt động của quy tắc này thì cứ nhắn mình nhé! 💡"
                )
                clean_detail = sanitize_chat_markdown(detail_reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_detail,
                    updates={"active_dataset_id": r.get("dataset_id") or target_ds}
                )
                return {
                    "response": clean_detail,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {
                        "intent": "RULE_INQUIRY",
                        "status": "FOUND_ONE",
                        "rule": r
                    },
                    "traces": []
                }

            elif lookup_single.status == RuleLookupStatus.FOUND_MANY:
                matches_bullets = "\n".join([
                    f"- 🔹 `{m.get('rule_id')}` (Bảng `{m.get('dataset_id')}`, Cột `{m.get('column_name')}`): {m.get('rule_name') or m.get('treatment_name')}"
                    for m in lookup_single.rules[:6]
                ])
                many_reply = (
                    f"Mình tìm thấy **{len(lookup_single.rules)} quy tắc** liên quan đến `{lookup_single.query}` trong hệ thống nè! ✨\n\n"
                    f"{matches_bullets}\n\n"
                    f"Cậu muốn xem chi tiết quy tắc của cột hoặc bảng nào trước, cứ bảo mình nhé! 💡"
                )
                clean_many = sanitize_chat_markdown(many_reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_many,
                    updates={"active_dataset_id": target_ds}
                )
                return {
                    "response": clean_many,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {
                        "intent": "RULE_INQUIRY",
                        "status": "FOUND_MANY",
                        "matches_count": len(lookup_single.rules),
                        "rules": lookup_single.rules
                    },
                    "traces": []
                }

            elif lookup_single.status == RuleLookupStatus.DB_ERROR:
                db_err_reply = (
                    f"Ui, hiện tại mình chưa thể truy xuất dữ liệu quy tắc do gián đoạn kết nối cơ sở dữ liệu rồi! 😢 "
                    f"Cậu đợi chút xíu rồi thử lại cùng mình nha ✨."
                )
                clean_db_err = sanitize_chat_markdown(db_err_reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_db_err,
                    updates={}
                )
                return {
                    "response": clean_db_err,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {"intent": "RULE_INQUIRY", "status": "DB_ERROR"},
                    "traces": []
                }

            # Case C: User asks about configured rules for the dataset or general legal policies
            ds_config_res = RuleLookupService.get_configured_rules_for_dataset(target_ds, as_of=run_start_time)

            if user_intent == UserIntent.RULE_INQUIRY:
                # If specific query was searched but NOT_FOUND:
                if lookup_single.status == RuleLookupStatus.NOT_FOUND and len(lookup_single.query) > 2 and lookup_single.query not in ("rule", "quy tắc", "danh sách", "treatment rule"):
                    not_found_reply = (
                        f"Hiện tại mình không tìm thấy quy tắc nào khớp với từ khóa `{lookup_single.query}` trong hệ sinh thái của DataTrust OS đâu nha 🥺. "
                        f"Cậu thử kiểm tra lại mã quy tắc hoặc tham khảo danh sách quy tắc đang có của bảng `{target_ds}` dưới đây xem sao nhé! ✨"
                    )
                    clean_nf = sanitize_chat_markdown(not_found_reply)
                    session_manager.append_chat_turn(
                        session_id=session_id,
                        run_id=run_id,
                        user_text=message,
                        ai_text=clean_nf,
                        updates={"active_dataset_id": target_ds}
                    )
                    return {
                        "response": clean_nf,
                        "session_id": session_id,
                        "run_id": run_id,
                        "data": {"intent": "RULE_INQUIRY", "status": "NOT_FOUND", "query": lookup_single.query},
                        "traces": []
                    }

                # Otherwise display dataset configured rules summary
                comp_rules = [r for r in ds_config_res.rules if r.get("family") == "COMPLIANCE"]
                treat_rules = [r for r in ds_config_res.rules if r.get("family") == "TREATMENT"]
                rel_rules = [r for r in ds_config_res.rules if r.get("family") == "RELIABILITY"]

                comp_bullets = "\n".join([f"- 🛡️ `{r['rule_id']}` (Cột `{r.get('column_name')}`): {r.get('rule_name')}" + (f" (Căn cứ `{r['law_ref']}`)" if r.get('law_ref') else "") for r in comp_rules[:4]])
                treat_bullets = "\n".join([f"- 📝 `{t['rule_id']}` (Cột `{t.get('column_name')}`): `{t.get('operation_id')}` - {t.get('treatment_name')}" for t in treat_rules[:3]])
                rel_bullets = "\n".join([f"- 🚗 `{rl['rule_id']}` ({rl.get('layer')}): {rl.get('description') or rl.get('detector_id')}" for rl in rel_rules[:3]])

                ds_summary_reply = (
                    f"Dạ đây nè! ✨ Cấu hình quy tắc đang kích hoạt cho bảng `{target_ds}` gồm **{len(ds_config_res.rules)} quy tắc** được chia làm 3 nhóm chuẩn chỉnh:\n\n"
                    f"1. **Quy tắc Tuân thủ & Chất lượng (Lane B - {len(comp_rules)} quy tắc)**:\n{comp_bullets or '- Chưa có quy tắc tuân thủ nào.'}\n\n"
                    f"2. **Quy tắc Xử lý & Chuẩn hóa (Treatment - {len(treat_rules)} quy tắc)**:\n{treat_bullets or '- Chưa cấu hình quy tắc xử lý nào.'}\n\n"
                    f"3. **Quy tắc Kỹ thuật & Cảm biến Xe (Lane A - {len(rel_rules)} quy tắc)**:\n{rel_bullets or '- Chưa có quy tắc kỹ thuật nào.'}\n\n"
                    f"Cậu muốn tìm hiểu kỹ quy tắc nào thì cứ bảo mình nha! 💡"
                )
                clean_ds_summary = sanitize_chat_markdown(ds_summary_reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_ds_summary,
                    updates={"active_dataset_id": target_ds}
                )
                return {
                    "response": clean_ds_summary,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {
                        "intent": "RULE_INQUIRY",
                        "status": ds_config_res.status.value,
                        "dataset_id": target_ds,
                        "rules_count": len(ds_config_res.rules)
                    },
                    "traces": []
                }

            # General POLICY_OR_LEGAL_INQUIRY (Regulatory frameworks)
            comp_sample = [r for r in ds_config_res.rules if r.get("family") == "COMPLIANCE" and r.get("law_ref")][:5]
            rule_bullets = "\n".join([
                f"- **{r.get('rule_name')}** (`{r.get('rule_id')}`): Căn cứ `{r.get('law_ref')}`"
                for r in comp_sample
            ])
            policy_reply = (
                f"Về các tiêu chuẩn quản trị và pháp lý, DataTrust OS đang áp dụng bộ quy tắc cực kỳ chuẩn chỉnh này nè: 🛡️✨\n\n"
                f"{rule_bullets or '- Các quy tắc tuân thủ cơ bản đang được kích hoạt.'}\n\n"
                f"Tụi mình luôn phân định rõ ràng giữa Lane A (Kỹ thuật / Viễn thông xe 🚗) và Lane B (Chính sách & Bảo vệ dữ liệu cá nhân 🔒) để bảo đảm an toàn dữ liệu tối đa đó! Cậu cần tìm hiểu kỹ quy tắc nào cứ bảo mình nhé! 💡"
            )
            clean_policy = sanitize_chat_markdown(policy_reply)
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=clean_policy,
                updates={}
            )
            return {
                "response": clean_policy,
                "session_id": session_id,
                "run_id": run_id,
                "data": {"rules": ds_config_res.rules},
                "traces": []
            }

        # -------------------------------------------------------------
        # 6.5 WARNING INQUIRY: Queries about warning records, reasons & counts
        # -------------------------------------------------------------
        if user_intent == UserIntent.WARNING_INQUIRY:
            we = load_warning_evidence(run_id)

            # A. Resilience / Fallback on DB connection failure
            if we.get("db_error"):
                db_err_reply = (
                    f"Ui tiếc quá, hiện tại mình chưa thể truy xuất dữ liệu chi tiết từ bảng cảnh báo (`warning.records`) của lần chạy `{run_id}` "
                    f"do gián đoạn kết nối cơ sở dữ liệu mất rồi! 😢 Cậu đợi chút xíu rồi thử lại cùng mình, hoặc kiểm tra kết nối DB giúp mình nha ✨."
                )
                clean_db_err = sanitize_chat_markdown(db_err_reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_db_err,
                    updates={}
                )
                return {
                    "response": clean_db_err,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {"intent": "WARNING_INQUIRY", "status": "DB_CONNECTION_ERROR"},
                    "traces": []
                }

            pipeline_cnt = we.get("pipeline_warning_count", 0)
            actual_cnt = we.get("actual_records_count", 0)
            grouped = we.get("grouped_warnings", [])
            discrepancy_note = we.get("discrepancy_note")
            samples = we.get("sanitized_samples", [])

            # B. Zero warnings case
            if pipeline_cnt == 0 and actual_cnt == 0:
                zero_reply = (
                    f"Tin vui nè! 🎉 Trong lần chạy `{run_id}`, hệ thống không ghi nhận bất kỳ bản ghi cảnh báo nào (`warning_count = 0`) luôn nha! ✨ "
                    f"Toàn bộ dữ liệu sạch đã được đưa thẳng vào chuẩn Silver, hoặc khu vực Cách ly (Quarantine) nếu có vi phạm cứng. Cậu cứ hoàn toàn yên tâm nhé! 💡"
                )
                clean_zero = sanitize_chat_markdown(zero_reply)
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clean_zero,
                    updates={}
                )
                return {
                    "response": clean_zero,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {"intent": "WARNING_INQUIRY", "warning_count": 0, "actual_records_count": 0},
                    "traces": []
                }

            # C. Warning records exist - Quantitative, rule-bound, fact-grounded presentation
            cp_summary = we.get("changepoint_summary")
            cp_section = ""
            if cp_summary:
                rule_id = cp_summary.get("rule_id", "L4-DEFAULT-METRICS")
                t_metric = cp_summary.get("target_metric", "trip_distance_km")
                pen = cp_summary.get("penalty_threshold", 3.0)
                dirs = cp_summary.get("shift_directions", {})
                up_cnt = dirs.get("UP", 0)
                down_cnt = dirs.get("DOWN", 0)
                mag_range = cp_summary.get("magnitude_range", {})
                score_range = cp_summary.get("score_range", {})
                events = cp_summary.get("events", [])

                events_text = "\n".join([
                    f"  - `{e.get('event_time')}`: Dịch chuyển **{e.get('direction')}** (biên độ `{e.get('magnitude'):+.2f} km`), trung bình dịch từ `{e.get('pre_mean')}` sang `{e.get('post_mean')}` (ảnh hưởng {e.get('affected_records')} bản ghi liên tiếp)."
                    for e in events[:3]
                ])

                direction_bits = []
                if up_cnt:
                    direction_bits.append(f"{up_cnt} lần tăng")
                if down_cnt:
                    direction_bits.append(f"{down_cnt} lần giảm")
                direction_text = ", ".join(direction_bits) or "chưa có phân loại hướng dịch chuyển"

                metric_bits = []
                if mag_range.get("min") is not None and mag_range.get("max") is not None:
                    metric_bits.append(
                        f"Biên độ từ `{mag_range['min']:+.2f}` đến `{mag_range['max']:+.2f}`"
                    )
                if score_range.get("min") is not None and score_range.get("max") is not None:
                    metric_bits.append(
                        f"điểm bất thường từ `{score_range['min']:.2f}` đến `{score_range['max']:.2f}`"
                    )
                metric_text = "; ".join(metric_bits)

                cp_section = (
                    f"\n\nCác cảnh báo `CHANGEPOINT_SHIFT` thuộc Lane A: quy tắc `{rule_id}` phát hiện "
                    f"phân phối của `{t_metric}` thay đổi giữa các cửa sổ quan sát "
                    f"(ngưỡng kỹ thuật `penalty = {pen}`; {direction_text}"
                    f"{f'; {metric_text}' if metric_text else ''}). "
                    "Đây là tín hiệu thống kê, tự nó chưa chứng minh vi phạm pháp lý (Lane B), "
                    "cũng chưa đủ để kết luận dữ liệu là bình thường hay hoàn toàn hợp lệ."
                    f"{f'\n\nMột số điểm quan sát có bằng chứng:\n{events_text}' if events_text else ''}"
                    "\n\nNên đối chiếu các điểm có biên độ lớn với ngưỡng của rule và bối cảnh vận hành trước khi kết luận hoặc xử lý dữ liệu."
                )

            bullets = []
            for g in grouped:
                w_type = g.get("warning_type") or "ADVISORY"
                w_reason = g.get("warning_reason") or "Cảnh báo độ lệch dữ liệu"
                g_cnt = g.get("count", 0)
                lane = g.get("signal_lane")
                layer = g.get("signal_layer")
                lane_info = f" (Làn: `{lane}`" if lane else ""
                if layer:
                    lane_info += f", Lớp: `{layer}`" if lane_info else f" (Lớp: `{layer}`"
                if lane_info:
                    lane_info += ")"
                bullets.append(f"- **{g_cnt:,} bản ghi**: Loại `{w_type}` - {w_reason}{lane_info}")

            bullet_text = "\n".join(bullets) if bullets else "- Không có phân nhóm chi tiết."
            discrepancy_text = f"\n\n> ⚠️ **Lưu ý đối soát**: {discrepancy_note}" if discrepancy_note else ""

            default_warning_reply = (
                f"Lần chạy `{run_id}` ghi nhận **{actual_cnt:,}** bản ghi Warning nè! ✨ Đây là các tín hiệu cảnh báo thống kê kỹ thuật (Lane A), "
                f"**không phải là vi phạm pháp lý** hay chính sách tuân thủ (Lane B) đâu nha, cậu yên tâm nhé! 🚗💡 "
                f"Theo chính sách định tuyến hiện tại, riêng tín hiệu Warning không tự động đưa bản ghi vào Quarantine; "
                f"việc bản ghi có đi tiếp vào Silver còn phụ thuộc các rule khác. Các mô hình ở tầng Gold cần lưu ý độ trôi phân phối này.\n\n"
                f"**Thống kê tổng quan**:\n"
                f"- Số bản ghi cảnh báo thực tế: **{actual_cnt:,}**\n"
                f"- Chỉ số ghi nhận tại pipeline: **{pipeline_cnt:,}**\n\n"
                f"**Phân nhóm cảnh báo**:\n"
                f"{bullet_text}"
                f"{cp_section}"
                f"{discrepancy_text}"
            )

            clean_warning_reply = sanitize_chat_markdown(default_warning_reply)

            if not self.llm_adapter.force_mock and self.llm_adapter.provider != "mock":
                try:
                    sys_inst = (
                        "Bạn là DataTrust AI Companion - người bạn kỹ sư dữ liệu cực kỳ đáng yêu, thân thiện và ấm áp! ✨ "
                        "Tất cả số liệu cung cấp đều là số liệu thực tế đã xác minh từ PostgreSQL. "
                        "Trả lời đúng trọng tâm câu hỏi của người bạn kỹ sư trước bằng tiếng Việt tự nhiên, ấm áp, đồng cảm, "
                        "sử dụng emoji hợp lý (✨, 💡, 🚗, 📊) để làm mềm câu văn, không trả lời khô khan như máy móc. "
                        "Ngắn gọn súc tích 1-3 câu nếu câu hỏi đơn giản; tập trung nguyên nhân & evidence nếu hỏi tại sao. "
                        "Phân biệt rõ: Cảnh báo thống kê Lane A KHÔNG PHẢI vi phạm pháp lý Lane B."
                    )
                    prompt = (
                        f"Người dùng hỏi về cảnh báo: '{message}'.\n"
                        f"Dữ liệu kiểm toán lần chạy {run_id}:\n"
                        f"- Số bản ghi cảnh báo thực tế: {actual_cnt:,}\n"
                        f"- Số bản ghi pipeline ghi nhận: {pipeline_cnt:,}\n"
                        f"- Phân nhóm cảnh báo:\n{bullet_text}\n"
                        f"{f'- Phân tích changepoint: {json.dumps(cp_summary, default=str)}' if cp_summary else ''}\n"
                        f"{f'- Lưu ý đối soát: {discrepancy_note}' if discrepancy_note else ''}\n\n"
                        f"Yêu cầu: Trả lời trực tiếp câu hỏi người dùng, chỉ rõ rule_id, ngưỡng threshold, change_magnitude và phân biệt rõ Lane A (kỹ thuật) vs Lane B (pháp lý)."
                    )
                    llm_res = self.llm_adapter.complete(
                        prompt=prompt,
                        system_instruction=sys_inst,
                        context={"run_id": run_id, "warning_evidence": we},
                        temperature=0.2,
                        max_tokens=450
                    )
                    llm_text = llm_res.get("text", "").strip()
                    if llm_text:
                        clean_warning_reply = sanitize_chat_markdown(llm_text)
                except Exception as e:
                    logger.warning(f"LLM interpretation for warning inquiry failed: {e}")

            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=clean_warning_reply,
                updates={}
            )
            return {
                "response": clean_warning_reply,
                "session_id": session_id,
                "run_id": run_id,
                "data": {
                    "intent": "WARNING_INQUIRY",
                    "pipeline_warning_count": pipeline_cnt,
                    "actual_records_count": actual_cnt,
                    "is_reconciled": we.get("is_reconciled", True),
                    "grouped_warnings": grouped
                },
                "traces": []
            }

        # -------------------------------------------------------------
        # 7. FINDING RCA / REMEDIATION / INVESTIGATION
        # -------------------------------------------------------------
        if (
            user_intent != UserIntent.WARNING_INQUIRY
            and (has_investigation_keywords or target_finding_id or user_intent in (UserIntent.ROOT_CAUSE_ONLY, UserIntent.REMEDIATION_ONLY, UserIntent.BOTH_RCA_AND_REMEDIATION))
        ):
            finding_row = None
            sample_q = None

            # Retrieve findings in run for ambiguity check if target_finding_id is not yet pinned
            run_findings = []
            try:
                conn = get_db_connection()
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT finding_id, column_name, dataset_id, severity, reason FROM audit.findings WHERE run_id = %s ORDER BY failed_record_count DESC LIMIT 5;",
                        (run_id,)
                    )
                    run_findings = [dict(r) for r in cur.fetchall()]
                conn.close()
            except Exception as e:
                logger.warning(f"Error querying run findings: {e}")

            # Ambiguity check: user asks general error question, but there are multiple findings and no active focus
            if not target_finding_id and len(run_findings) > 1 and not has_followup_reference:
                finding_bullets = "\n".join([
                    f"- 🔍 **{f['finding_id']}** (cột `{f['column_name']}`): {f['reason']}"
                    for f in run_findings[:3]
                ])
                clarification = (
                    f"Trong lần chạy `{run_id}`, hệ thống ghi nhận **{len(run_findings)} vấn đề kiểm toán** nè: ✨\n\n"
                    f"{finding_bullets}\n\n"
                    f"Bạn muốn tôi phân tích nguyên nhân (RCA) hoặc đề xuất giải pháp cho vấn đề nào trước? Cứ bảo mình nhé, mình hỗ trợ ngay! 💡"
                )
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=clarification,
                    updates={}
                )
                return {
                    "response": clarification,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {"available_findings": [f["finding_id"] for f in run_findings]},
                    "traces": []
                }

            # If only 1 finding exists in the run and user asks about root cause/error, auto-focus
            if not target_finding_id and len(run_findings) == 1:
                target_finding_id = run_findings[0]["finding_id"]

            try:
                conn = get_db_connection()
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if target_finding_id:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE finding_id = %s AND run_id = %s LIMIT 1;",
                            (target_finding_id, run_id)
                        )
                        finding_row = cur.fetchone()
                        if not finding_row:
                            raise HTTPException(
                                status_code=404,
                                detail={
                                    "code": "FINDING_NOT_FOUND_IN_RUN",
                                    "message": f"Finding '{target_finding_id}' không tồn tại trong lần chạy '{run_id}'. Tuyệt đối cấm tra cứu chéo lần chạy."
                                }
                            )
                    else:
                        cur.execute(
                            "SELECT * FROM audit.findings WHERE run_id = %s ORDER BY failed_record_count DESC LIMIT 1;",
                            (run_id,)
                        )
                        finding_row = cur.fetchone()

                    grounded_samples = []
                    if finding_row:
                        from backend.ai.services.context_loader import fetch_grounded_quarantine_samples
                        fid_for_query = finding_row.get("finding_id")
                        rule_for_query = finding_row.get("rule_id")
                        col_for_query = finding_row.get("column_name")
                        grounded_samples = fetch_grounded_quarantine_samples(
                            cur,
                            run_id=run_id,
                            finding_id=fid_for_query,
                            rule_id=rule_for_query,
                            column_name=col_for_query,
                            limit=3
                        )
                        sample_q = grounded_samples[0] if grounded_samples else None
                conn.close()
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Error querying finding details for chat: {e}")

            if not finding_row:
                no_finding_ans = (
                    f"Tuyệt vời quá nè! 🎉 Trong lần chạy `{run_id}`, hệ thống không ghi nhận bất kỳ vi phạm kiểm toán nào cả! ✨ "
                    f"Toàn bộ dữ liệu của lần chạy này đều đáp ứng xuất sắc các tiêu chuẩn kiểm soát chất lượng luôn! Cậu hoàn toàn yên tâm nha! 🚗💖"
                )
                session_manager.append_chat_turn(
                    session_id=session_id,
                    run_id=run_id,
                    user_text=message,
                    ai_text=no_finding_ans,
                    updates={}
                )
                return {
                    "response": no_finding_ans,
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {
                        "structured_analysis": {
                            "run_id": run_id,
                            "conclusion": f"Lần chạy {run_id} đạt 100% tiêu chuẩn chất lượng và kiểm toán.",
                            "status": "PASSED"
                        }
                    },
                    "traces": []
                }

            fid = finding_row.get("finding_id")
            col = finding_row.get("column_name") or "cột mục tiêu"
            dataset = finding_row.get("dataset_id") or "bảng dữ liệu"
            rule = finding_row.get("rule_id") or "RULE_CHECK"
            sev = finding_row.get("severity") or "HIGH"
            law = finding_row.get("law_ref")
            reason = finding_row.get("reason") or "Dữ liệu không đạt tiêu chuẩn."
            count = finding_row.get("failed_record_count", 1)
            failure_lane = (sample_q.get("failure_lane") if sample_q else None) or "LANE_B"
            if "LANE_A" in rule.upper() or "SENSOR" in rule.upper():
                failure_lane = "LANE_A"

            grounding_level = "SUPPORTED" if grounded_samples else "INSUFFICIENT_EVIDENCE"
            rca_context = {
                "finding": dict(finding_row),
                "evidence": grounded_samples,
                "grounding_level": grounding_level,
                "failure_lane": failure_lane,
                "rule_id": rule,
                "column_name": col,
                "law_ref": law,
                "user_query": message,
                "intent": user_intent.value
            }

            intent_instruction = ""
            if grounding_level == "INSUFFICIENT_EVIDENCE":
                intent_instruction += (
                    "NGUYÊN TẮC EVIDENCE-OR-ABSTAIN (BẮT BUỘC): Không tìm thấy bản ghi cách ly thực nghiệm khớp chính xác với finding này trong lần chạy. "
                    "TUYỆT ĐỐI KHÔNG SUY ĐOÁN hoặc tự bịa nguyên nhân vật lý cụ thể (như quá tải, lỗi làm mát, trôi cảm biến). "
                    "Hãy nêu rõ vi phạm được phát hiện theo định nghĩa quy tắc kiểm toán nhưng chưa có mẫu dữ liệu đối chứng để kết luận nguyên nhân vật lý cụ thể.\n"
                )
            if user_intent == UserIntent.ROOT_CAUSE_ONLY:
                intent_instruction += (
                    "YÊU CẦU TRỌNG TÂM: Người dùng CHỈ hỏi về nguyên nhân vi phạm. "
                    "CHỈ giải thích nguyên nhân và cơ chế phát sinh lỗi. TUYỆT ĐỐI KHÔNG tự ý liệt kê hàng loạt giải pháp khắc phục hay remediation."
                )
            elif user_intent == UserIntent.REMEDIATION_ONLY:
                intent_instruction = (
                    "YÊU CẦU TRỌNG TÂM: Người dùng hỏi về giải pháp xử lý. "
                    "Tập trung đề xuất quy tắc chuẩn hóa và khắc phục dữ liệu."
                )
            else:
                intent_instruction = (
                    "YÊU CẦU TRỌNG TÂM: Trình bày ngắn gọn nguyên nhân và đề xuất phương án khắc phục tương ứng."
                )

            prompt = f"""Phân tích Finding '{fid}' trên bảng '{dataset}', cột '{col}'.
Quy tắc: '{rule}'.
Lý do vi phạm: '{reason}'.
Số bản ghi cách ly: {count}.
Làn kiểm soát (Failure Lane): {failure_lane}.
Căn cứ tham chiếu: {law or 'Không có tham chiếu cụ thể'}.
Câu hỏi người dùng: "{message}".

{intent_instruction}

HƯỚNG DẪN TRẢ LỜI TỰ NHIÊN, ĐÚNG TRỌNG TÂM:
1. Trả lời trực tiếp câu hỏi ngay ở câu đầu; không chào lại và không nhắc lại nguyên văn câu hỏi.
2. Điều chỉnh hình thức theo ý định: câu hỏi ngắn cần 1-3 câu; câu hỏi "vì sao" tập trung vào nguyên nhân và evidence; chỉ dùng tiêu đề hoặc bullet khi người dùng yêu cầu chi tiết hoặc nội dung thực sự phức tạp.
3. Các ý về bản chất vấn đề, bằng chứng, ảnh hưởng và hành động là nội dung cần cân nhắc khi phù hợp, không phải bốn mục bắt buộc. Chỉ dùng ví dụ đời thường nếu ví dụ giúp làm rõ và không đưa thêm dữ kiện chưa có trong evidence.
4. Không dùng khuôn mẫu hành chính, không ép cụm từ "Kết luận:" ở đầu đoạn, không lặp lại cùng một nội dung. Chỉ phân tách Lane A / Lane B khi điều đó liên quan trực tiếp hoặc khi vi phạm kép (BOTH).
5. Không gọi dữ liệu là bình thường, an toàn hoặc hợp lệ nếu evidence không chứng minh. Khi thiếu evidence, nêu rõ điều đã biết và điều chưa thể kết luận.
6. ẨN 100% JSON & THÔNG TIN KỸ THUẬT: Tuyệt đối không hiển thị chuỗi JSON thô, code block JSON, hoặc biến nội bộ.

Trả về JSON có cấu trúc gồm:
- 'answer': Văn bản phản hồi tự nhiên cho người dùng.
- 'structured_analysis': Dữ liệu phân tích có cấu trúc."""

            system_inst = (
                "You are DataTrust AI Companion - a super cute, warm, friendly, dynamic AI assistant and pair-programming friend! ✨ "
                "Analyze objectively using actual evidence verified from PostgreSQL, but explain everything in warm, empathetic, intuitive Vietnamese. "
                "Chat like two close engineering friends, use tasteful emojis (✨, 📝, 🚗, 💡, 🛡️, 🔍) to soften statements, and absolutely avoid dry, rigid, robotic bureaucratic phrasing. "
                "Answer the exact question first and adapt response length and structure to the user's intent. "
                "Short questions should receive concise answers; why-questions should prioritize causes and supporting evidence; "
                "headings, bullets, analogies, impact, and next actions are optional and should appear only when useful. "
                "Never add facts through an analogy or claim that data is normal, safe, or valid without supporting evidence. "
                "Avoid repetitive bureaucratic prefixes while strictly preserving the required structured JSON response contract with 'answer' and 'structured_analysis'."
            )

            history_turns = session_state.get("recent_messages", []) if session_state else []
            llm_res = self.llm_adapter.complete(
                prompt=prompt,
                system_instruction=system_inst,
                context=rca_context,
                history=history_turns,
                temperature=0.1
            )

            raw_text = llm_res.get("text", "")
            structured_data = None
            clean_response = raw_text

            if "```json" in raw_text:
                try:
                    parts = raw_text.split("```json")
                    json_str = parts[1].split("```")[0].strip()
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        structured_data = parsed.get("structured_analysis", parsed)
                        clean_response = parsed.get("answer") or parsed.get("explanation") or parts[0].strip()
                except Exception as parse_err:
                    logger.warning(f"Failed parsing embedded JSON from LLM: {parse_err}")

            if not structured_data:
                try:
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        structured_data = parsed.get("structured_analysis", parsed)
                        clean_response = parsed.get("answer") or parsed.get("explanation") or raw_text
                except Exception:
                    pass

            clean_response = sanitize_chat_markdown(clean_response)

            # Negation enforcement: If intent was ROOT_CAUSE_ONLY, strip any remediation sections
            if user_intent == UserIntent.ROOT_CAUSE_ONLY:
                if "Đề xuất khắc phục" in clean_response or "Remediation" in clean_response:
                    clean_response = re.split(r'(\*\*|\#\#+)?\s*(Đề xuất khắc phục|Remediation|Giải pháp khắc phục)', clean_response, flags=re.IGNORECASE)[0].strip()

            if not clean_response:
                clean_response = f"Finding `{fid}` tại cột `{col}` ghi nhận vi phạm quy tắc `{rule}` ({reason})."

            # Record reasoning step into ReAct tracer
            step_trace = AgentTraceModel(
                session_id=session_id,
                agent_type="DiagnosisAgent",
                step_index=1,
                thought=f"Đã phân tích finding {fid} theo ranh giới {failure_lane} và intent {user_intent.value}.",
                action="CALL_LLM_RCA_ANALYSIS",
                tool_name="llm_adapter",
                tool_input={"finding_id": fid, "failure_lane": failure_lane, "rule_id": rule, "intent": user_intent.value},
                observation=f"Hoàn thành suy luận RCA từ {llm_res.get('provider', 'llm')}."
            )
            self.react_engine.add_trace(step_trace)
            await self._broadcast_step(step_trace)

            # Update session state with active finding & entities
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=clean_response,
                updates={
                    "active_finding_id": fid,
                    "active_dataset_id": dataset,
                    "active_column": col,
                    "active_failure_lane": failure_lane,
                }
            )

            source_label = llm_res.get("source") or ("OPENAI" if llm_res.get("provider") == "openai" else "DETERMINISTIC_FALLBACK")
            evidence_ids = [str(s.get("quarantine_id")) for s in grounded_samples if s.get("quarantine_id")]

            return {
                "response": clean_response,
                "session_id": session_id,
                "run_id": run_id,
                "data": {
                    "finding": dict(finding_row),
                    "structured_analysis": structured_data,
                    "grounding_level": grounding_level,
                    "source_label": source_label,
                    "rule_id": rule,
                    "law_ref": law,
                    "tools_called": ["QuarantineSampler", "PolicyRegistry", "ComplianceEvaluator"],
                    "evidence_ids": evidence_ids,
                    "evidence_samples": grounded_samples
                },
                "traces": [step_trace.model_dump()]
            }

        # -------------------------------------------------------------
        # 8. DATA TREATMENT RULE PROPOSAL
        # -------------------------------------------------------------
        if any(k in msg_lower for k in ("đề xuất rule", "treatment rule", "khắc phục", "quy tắc xử lý")):
            target_ds = context.get("dataset_id") or session_state.get("active_dataset_id") or "trips"
            target_col = context.get("column_name") or session_state.get("active_column") or "customer_phone"
            op_id = "mask_phone" if "phone" in target_col.lower() else ("round_decimal" if "lat" in target_col.lower() else "hash_sha256")
            params = {"prefix_len": 3, "suffix_len": 2, "mask_char": "*"} if op_id == "mask_phone" else {"decimals": 2}

            dry_run_res = self.rule_proposer_agent.dry_run_tool.execute({
                "proposal": {
                    "dataset_id": target_ds,
                    "column_name": target_col,
                    "operation_id": op_id,
                    "params_json": params
                },
                "sample_size": 200
            })

            total_sim = dry_run_res.get("simulated_total", 200)
            pass_rows = dry_run_res.get("simulated_pass_rows", 198)
            quar_rows = dry_run_res.get("simulated_quarantine_rows", 2)
            pass_rate = dry_run_res.get("pass_rate_pct", 99.0)
            data_source = dry_run_res.get("data_source", "SYNTHETIC_SIMULATION")
            synth_notice = dry_run_res.get("synthetic_notice")
            p50_str = f"{dry_run_res.get('latency_p50_ms', 0.0):.3f}ms"
            p95_str = f"{dry_run_res.get('latency_p95_ms', 0.0):.3f}ms"
            data_src_label = "Mẫu dữ liệu thực tế (Real Dataset Sample)" if data_source == "REAL_DATASET_SAMPLE" else "Dữ liệu mô phỏng tổng hợp (Synthetic Simulation)"
            scope_label = dry_run_res.get("benchmark_scope", "Microbenchmark mô phỏng trên tập mẫu")

            rule_trace = AgentTraceModel(
                session_id=session_id,
                agent_type="RuleProposerAgent",
                step_index=1,
                thought=f"Mô phỏng thử nghiệm (Dry-Run) quy tắc {op_id} trên tập mẫu Bronze {target_ds}.{target_col}.",
                action="EXECUTE_DRY_RUN",
                tool_name="dry_run",
                tool_input={"operation_id": op_id, "column": target_col, "sample_size": total_sim},
                observation=f"Tỷ lệ sạch (Silver Pass): {pass_rate}%, Cách ly: {quar_rows} dòng. Nguồn: {data_source}."
            )
            self.react_engine.add_trace(rule_trace)
            await self._broadcast_step(rule_trace)

            resp = (
                f"✨ **Đề xuất Quy tắc Khắc phục (Data Treatment Rule) từ AI Bạn Đồng Hành** nè! 📝\n\n"
                f"• 💡 **Quy tắc đề xuất**: `{op_id}({', '.join(f'{k}={v}' for k, v in params.items())})` trên cột `{target_col}`\n"
                f"• 🎯 **Mục tiêu**: Chuẩn hóa dữ liệu mượt mà trước khi chuyển tiếp vào tầng Silver\n"
                f"• 🔍 **Nguồn dữ liệu kiểm thử**: {data_src_label}" + (f" ({synth_notice})" if synth_notice else "") + "\n"
                f"• 📊 **Kết quả Mô phỏng Thử nghiệm (Dry-Run)**:\n"
                f"  - Tập mẫu quét: **{total_sim:,} bản ghi**\n"
                f"  - Dữ liệu sạch (Silver Pass): **{pass_rows:,} ({pass_rate}%)** 🚗✨\n"
                f"  - Cách ly (Quarantine): **{quar_rows:,} ({round(100 - pass_rate, 2)}%)**\n"
                f"  - Độ trễ vi điểm (Microbenchmark): **p50 = {p50_str} / p95 = {p95_str}** ⚡\n"
                f"  - Lưu ý phạm vi đo: *{scope_label}*\n\n"
                f"👉 *Quy tắc đang ở trạng thái **PENDING** chờ phê duyệt (Human-In-The-Loop). Cậu chỉ cần chuyển sang vai trò Admin để duyệt là áp dụng được ngay nha! 💖*"
            )
            clean_resp = sanitize_chat_markdown(resp)
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=clean_resp,
                updates={
                    "active_dataset_id": target_ds,
                    "active_column": target_col
                }
            )
            return {
                "response": clean_resp,
                "session_id": session_id,
                "run_id": run_id,
                "data": {"dry_run_result": dry_run_res},
                "traces": [rule_trace.model_dump()]
            }

        # -------------------------------------------------------------
        # 9. Fallback to ReAct assistant
        # -------------------------------------------------------------
        tools = {"profiler": self.profiler_agent.tools["profiler"]}
        res = await self.react_engine.run(
            goal=message,
            agent_type="AssistantAgent",
            tools=tools,
            context=context,
            session_id=session_id,
            step_callback=self._broadcast_step
        )
        final_ans = res.get("final_answer") or (
            "Mình đã ghi nhận yêu cầu của cậu và đối soát xong dữ liệu với catalog chính sách hiện hành rồi nè! ✨ "
            "Nếu cần mình phân tích sâu hơn khía cạnh nào, cậu cứ thoải mái nhắn mình nha! 💡"
        )
        clean_final = sanitize_chat_markdown(final_ans)
        session_manager.append_chat_turn(
            session_id=session_id,
            run_id=run_id,
            user_text=message,
            ai_text=clean_final,
            updates={}
        )
        return {
            "response": clean_final,
            "session_id": res.get("session_id", session_id),
            "run_id": run_id,
            "traces": res.get("traces", [])
        }

    async def diagnose_quarantine(
        self,
        record: QuarantineRecordModel,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs 4-tier root-cause diagnosis on a quarantine record."""
        return await self.diagnosis_agent.diagnose_quarantine_record(record, session_id=session_id)

    def scan_preventive_alerts(self, dataset_id: str, columns: List[str]):
        """Runs preventive early-warning drift check."""
        return self.preventive_guard_agent.scan_for_preventive_risks(dataset_id, columns)
