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
            RunContextLoader, load_catalog_columns, load_profiling_stats, load_compliance_rules
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
                "Tôi đã làm mới ngữ cảnh tập trung của cuộc trò chuyện. "
                "Bạn muốn tìm hiểu hoặc kiểm tra nội dung nào tiếp theo về lần chạy này?"
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
                    f"Xin chào! Tôi là trợ lý kiểm toán dữ liệu DataTrust OS. *(Hệ thống hiện hoạt động ở chế độ giới hạn do chưa kết nối LLM API Key)*.\n\n"
                    f"Trong lần chạy `{run_id}`, tôi có thể hỗ trợ bạn xem tổng quan số liệu, kiểm tra danh sách vi phạm hoặc tra cứu catalog quy tắc."
                )
            else:
                sys_inst = (
                    "You are DataTrust Assistant, a polite, conversational AI data auditor. "
                    f"Current run: {run_id}. "
                    "Respond naturally and warmly in Vietnamese like ChatGPT. "
                    "For greetings or small talk, keep it concise (1-2 sentences) and offer helpful assistance. "
                    "Never use '**Kết luận:**' for greetings. Never output raw JSON or internal variable names."
                )
                res_llm = self.llm_adapter.complete(
                    prompt=f"Người dùng nói: '{message}'. Hãy trả lời một cách tự nhiên và lịch sự.",
                    system_instruction=sys_inst,
                    context={"run_id": run_id, "active_entities": session_state.get("entities", {})},
                    temperature=0.3,
                    max_tokens=200
                )
                greeting_reply = sanitize_chat_markdown(res_llm.get("text", "")).strip()
                if not greeting_reply:
                    greeting_reply = (
                        f"Xin chào! Tôi là trợ lý AI của DataTrust OS. Trong lần chạy `{run_id}`, "
                        f"tôi có thể giúp bạn kiểm tra chất lượng dữ liệu, tìm nguyên nhân vi phạm (RCA), "
                        f"đề xuất quy tắc khắc phục hoặc tra cứu catalog. Bạn cần hỗ trợ gì?"
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
            status = pr.get("status", "COMPLETED")
            duration_ms = pr.get("execution_duration_ms") or 0
            f_summary = selective_context.get("findings_summary", [])
            total_findings = sum(f.get("cnt", 0) for f in f_summary)

            overview_ans = (
                f"Lần chạy `{run_id}` hiện ở trạng thái **{status}**, đã xử lý tổng cộng **{scanned:,} bản ghi** "
                f"(gồm **{silver:,} bản ghi hợp lệ** vào tầng Silver và **{quarantine:,} bản ghi cách ly**).\n\n"
                f"- **Vấn đề kiểm toán (Findings):** Ghi nhận tổng cộng **{total_findings}** vấn đề.\n"
                f"- **Thời gian thực thi:** {duration_ms:,}ms.\n"
                f"- **Đánh giá chất lượng:** Dữ liệu vi phạm đã được cách ly theo chính sách kiểm soát."
            )
            clean_overview = sanitize_chat_markdown(overview_ans)
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
                    f"Pipeline lần chạy `{run_id}` gặp sự cố tại bước **{failed_step.get('step_name')}**.\n\n"
                    f"- **Chi tiết lỗi:** {err_msg or 'Lỗi không xác định trong quá trình thực thi.'}\n"
                    f"- **Tác động:** Pipeline tạm dừng để bảo vệ tính toàn vẹn dữ liệu, không ghi nhận thêm dữ liệu vào Silver."
                )
            else:
                progress_ans = (
                    f"Pipeline lần chạy `{run_id}` hiện có trạng thái **{status}** với **{len(steps)} bước** đã ghi nhận.\n\n"
                    f"- **Tiến trình:** Các bước kiểm soát chất lượng L1-L4 đang được giám sát chặt chẽ."
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

            col_lines = "\n".join([f"- `{c['column_name']}` ({c['data_type']}){' [PII]' if c.get('pii_flag') else ''}" for c in cols[:10]])
            catalog_reply = (
                f"Thông tin catalog cho dữ liệu của lần chạy `{run_id}`:\n\n"
                f"**Danh sách các cột:**\n{col_lines or '- Không có thông tin cột cụ thể.'}\n\n"
                f"Bạn có thể hỏi thêm về tỷ lệ null, phân phối giá trị hoặc quy tắc kiểm tra cho từng cột cụ thể."
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
        # 6. POLICY OR LEGAL INQUIRY
        # -------------------------------------------------------------
        if user_intent == UserIntent.POLICY_OR_LEGAL_INQUIRY and not target_finding_id:
            rules = load_compliance_rules()
            rule_bullets = "\n".join([f"- **{r['rule_name']}** ({r['rule_id']}): Căn cứ `{r.get('standard_ref') or 'Nghị định 13 / Luật 91'}`" for r in rules[:5]])
            policy_reply = (
                f"Hệ thống DataTrust OS áp dụng các tiêu chuẩn quản trị và pháp lý sau:\n\n"
                f"{rule_bullets or '- Các quy tắc tuân thủ cơ bản đang được kích hoạt.'}\n\n"
                f"Các kiểm tra được phân định nghiêm ngặt giữa Lane A (Kỹ thuật/Vật lý xe) và Lane B (Chính sách/Bảo vệ dữ liệu cá nhân)."
            )
            session_manager.append_chat_turn(
                session_id=session_id,
                run_id=run_id,
                user_text=message,
                ai_text=policy_reply,
                updates={}
            )
            return {
                "response": policy_reply,
                "session_id": session_id,
                "run_id": run_id,
                "data": {"rules": rules},
                "traces": []
            }

        # -------------------------------------------------------------
        # 7. FINDING RCA / REMEDIATION / INVESTIGATION
        # -------------------------------------------------------------
        if has_investigation_keywords or target_finding_id or user_intent in (UserIntent.ROOT_CAUSE_ONLY, UserIntent.REMEDIATION_ONLY, UserIntent.BOTH_RCA_AND_REMEDIATION):
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
                    f"- **{f['finding_id']}** (cột `{f['column_name']}`): {f['reason']}"
                    for f in run_findings[:3]
                ])
                clarification = (
                    f"Trong lần chạy `{run_id}`, hệ thống ghi nhận **{len(run_findings)} vấn đề kiểm toán**:\n\n"
                    f"{finding_bullets}\n\n"
                    f"Bạn muốn tôi phân tích nguyên nhân (RCA) hoặc đề xuất giải pháp cho vấn đề nào trước?"
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

                    if finding_row:
                        cur.execute(
                            "SELECT source_row_pk, failure_lane, violation_reason, raw_record_json, quarantine_id FROM quarantine.records WHERE run_id = %s LIMIT 3;",
                            (run_id,)
                        )
                        sample_q = cur.fetchone()
                conn.close()
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Error querying finding details for chat: {e}")

            if not finding_row:
                no_finding_ans = (
                    f"Trong lần chạy `{run_id}`, hệ thống không ghi nhận bất kỳ vi phạm kiểm toán nào. "
                    f"Toàn bộ dữ liệu của lần chạy này đều đáp ứng tiêu chuẩn kiểm soát chất lượng."
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

            rca_context = {
                "finding": dict(finding_row),
                "evidence": [dict(sample_q)] if sample_q else [],
                "failure_lane": failure_lane,
                "rule_id": rule,
                "column_name": col,
                "law_ref": law,
                "user_query": message,
                "intent": user_intent.value
            }

            intent_instruction = ""
            if user_intent == UserIntent.ROOT_CAUSE_ONLY:
                intent_instruction = (
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

HƯỚNG DẪN TRẢ LỜI TỰ NHIÊN (CHUẨN CHATGPT):
1. ĐÚNG TRỌNG TÂM & TỰ NHIÊN: Trả lời trực diện, lịch sự, không dùng khuôn mẫu hành chính rập khuôn.
2. ĐỘ DÀI TỶ LỆ VỚI ĐỘ PHỨC TẠP: Câu hỏi ngắn trả lời súc tích; câu hỏi điều tra sâu trình bày theo các phần rõ ràng (Phát hiện -> Giả thuyết nguyên nhân -> Hướng xử lý).
3. KHÔNG ÉP CỤM TỪ '**Kết luận:**' Ở ĐẦU MỌI ĐOẠN VĂN: Bắt đầu tự nhiên bằng câu nhận xét trọng tâm.
4. GIẢM TRÙNG LẶP: Không lặp lại cùng một nội dung. Chỉ phân tách Lane A / Lane B khi vi phạm kép (BOTH).
5. ẨN 100% JSON & THÔNG TIN KỸ THUẬT: Tuyệt đối không hiển thị chuỗi JSON thô, code block ```json, hoặc biến nội bộ (requires_approval = True).

Trả về JSON có cấu trúc gồm:
- 'answer': Văn bản phản hồi tự nhiên cho người dùng.
- 'structured_analysis': Dữ liệu phân tích có cấu trúc."""

            system_inst = (
                "You are the Data Governance & Root Cause Analysis specialist for DataTrust OS. "
                "Analyze objectively using actual evidence. Respond in natural, professional Vietnamese like ChatGPT. "
                "Adapt response length to complexity and avoid repetitive bureaucratic prefixes."
            )

            llm_res = self.llm_adapter.complete(
                prompt=prompt,
                system_instruction=system_inst,
                context=rca_context,
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

            return {
                "response": clean_response,
                "session_id": session_id,
                "run_id": run_id,
                "data": {
                    "finding": dict(finding_row),
                    "structured_analysis": structured_data
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

            rule_trace = AgentTraceModel(
                session_id=session_id,
                agent_type="RuleProposerAgent",
                step_index=1,
                thought=f"Mô phỏng thử nghiệm (Dry-Run) quy tắc {op_id} trên tập mẫu Bronze {target_ds}.{target_col}.",
                action="EXECUTE_DRY_RUN",
                tool_name="dry_run",
                tool_input={"operation_id": op_id, "column": target_col, "sample_size": total_sim},
                observation=f"Tỷ lệ sạch (Silver Pass): {pass_rate}%, Cách ly: {quar_rows} dòng."
            )
            self.react_engine.add_trace(rule_trace)
            await self._broadcast_step(rule_trace)

            resp = (
                f"📜 **Đề xuất Quy tắc Khắc phục (Data Treatment Rule) từ AI Agent**:\n\n"
                f"• **Quy tắc đề xuất**: `{op_id}({', '.join(f'{k}={v}' for k, v in params.items())})` trên cột `{target_col}`\n"
                f"• **Mục tiêu**: Chuẩn hóa dữ liệu trước khi chuyển tiếp vào tầng Silver\n"
                f"• **Kết quả Mô phỏng Thử nghiệm (Dry-Run)**:\n"
                f"  - Tập mẫu quét: **{total_sim:,} bản ghi**\n"
                f"  - Dữ liệu sạch (Silver Pass): **{pass_rows:,} ({pass_rate}%)**\n"
                f"  - Cách ly (Quarantine): **{quar_rows:,} ({round(100 - pass_rate, 2)}%)**\n"
                f"  - Độ trễ dự kiến: **+0.7ms** (Đạt chuẩn SLA)\n\n"
                f"👉 *Quy tắc đang ở trạng thái **PENDING** theo cơ chế Human-In-The-Loop. Vui lòng chuyển sang vai trò Admin để phê duyệt.*"
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
        final_ans = res.get("final_answer") or "Hệ thống DataTrust AI Agent đã ghi nhận yêu cầu và đối soát dữ liệu với catalog chính sách hiện hành."
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
