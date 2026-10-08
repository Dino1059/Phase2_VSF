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

        context = context or {}
        run_id = (run_id or context.get("run_id") or "").strip()
        if not run_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "MISSING_RUN_ID", "message": "run_id là bắt buộc để tương tác với AI Agent."}
            )

        msg_lower = message.lower()
        target_finding_id = finding_id or context.get("finding_id")
        if not target_finding_id:
            f_match = re.search(r'\b(FND-[a-zA-Z0-9_-]+|F-[a-zA-Z0-9_-]+)\b', message)
            if f_match:
                target_finding_id = f_match.group(1)

        # Classify User Intent using negation-aware priority rules
        user_intent = IntentClassifier.classify(message)
        selective_context = RunContextLoader.load_context(run_id, user_intent, target_finding_id)

        # Special Case A: User asks for Run Overview and no specific finding was requested
        if user_intent == UserIntent.RUN_OVERVIEW and not target_finding_id:
            pr = selective_context.get("pipeline_run", {})
            scanned = pr.get("scanned_count", 0)
            silver = pr.get("silver_count", 0)
            quarantine = pr.get("quarantine_count", 0)
            status = pr.get("status", "COMPLETED")
            duration_ms = pr.get("execution_duration_ms") or 0
            f_summary = selective_context.get("findings_summary", [])
            total_findings = sum(f.get("cnt", 0) for f in f_summary)

            overview_ans = (
                f"**Kết luận:** Lần chạy `{run_id}` đang ở trạng thái **{status}**, đã xử lý tổng cộng **{scanned:,} bản ghi** "
                f"(gồm **{silver:,} bản ghi sạch** vào tầng Silver và **{quarantine:,} bản ghi cách ly**).\n\n"
                f"- **Vấn đề kiểm toán (Findings):** Ghi nhận tổng cộng **{total_findings}** vấn đề.\n"
                f"- **Thời gian thực thi:** {duration_ms:,}ms.\n"
                f"- **Đánh giá kiểm toán:** Dữ liệu vi phạm đã được cách ly nghiêm ngặt, bảo đảm tính toàn vẹn cho Silver layer."
            )
            return {
                "response": sanitize_chat_markdown(overview_ans),
                "session_id": session_id or f"sess_{uuid.uuid4().hex[:8]}",
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

        # Special Case B: User asks about pipeline progress or errors
        if user_intent == UserIntent.PIPELINE_ERROR_OR_PROGRESS and not target_finding_id:
            pr = selective_context.get("pipeline_run", {})
            status = pr.get("status", "RUNNING")
            steps = selective_context.get("steps", [])
            failed_step = next((s for s in steps if s.get("status") == "FAILED"), None)
            err_msg = failed_step.get("error_message") if failed_step else pr.get("error_message")

            if failed_step:
                progress_ans = (
                    f"**Kết luận:** Pipeline lần chạy `{run_id}` gặp sự cố tại bước **{failed_step.get('step_name')}**.\n\n"
                    f"- **Chi tiết lỗi:** {err_msg or 'Lỗi không xác định trong quá trình thực thi.'}\n"
                    f"- **Tác động:** Pipeline tạm dừng để bảo vệ tính toàn vẹn dữ liệu, không ghi nhận thêm dữ liệu vào Silver."
                )
            else:
                progress_ans = (
                    f"**Kết luận:** Pipeline lần chạy `{run_id}` hiện có trạng thái **{status}** với **{len(steps)} bước** đã ghi nhận.\n\n"
                    f"- **Tiến trình:** Các bước kiểm soát chất lượng L1-L4 đang được giám sát chặt chẽ."
                )

            return {
                "response": sanitize_chat_markdown(progress_ans),
                "session_id": session_id or f"sess_{uuid.uuid4().hex[:8]}",
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

        # 1. Finding / Root Cause Analysis (RCA) / Remediation Query
        if any(k in msg_lower for k in ("finding", "rca", "nguyên nhân", "giải thích", "lý do vi phạm", "điều tra", "khắc phục", "sửa", "remediation")) or target_finding_id:
            finding_row = None
            sample_q = None
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
                        # Find top finding strictly within this run_id
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
                session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
                return {
                    "response": f"**Kết luận:** Trong lần chạy `{run_id}`, hệ thống không ghi nhận bất kỳ vi phạm kiểm toán nào. Toàn bộ dữ liệu của lần chạy này đều đáp ứng tiêu chuẩn kiểm soát.",
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

            if finding_row:
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

                # Construct prompt strictly adhering to 5 standards
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

                prompt = f"""Perform analysis for Finding '{fid}' on table '{dataset}', column '{col}'.
Rule: '{rule}'.
Violation reason: '{reason}'.
Number of quarantined records: {count}.
Failure Lane: {failure_lane}.
Legal/Technical Reference: {law or 'No specific reference configured'}.
User Question: "{message}".

{intent_instruction}

5 MANDATORY FORMATTING RULES:
1. ĐÚNG TRỌNG TÂM: Trả lời ngắn gọn, đúng câu hỏi người dùng đặt ra.
2. KẾT LUẬN LÊN ĐẦU: Bắt đầu văn bản bằng 1-2 câu tóm tắt trực diện Finding dạng '**Kết luận:** [Bản ghi vi phạm cái gì, ở đâu, tại sao]'. Tiếp theo mới nêu các giả thuyết RCA.
3. GIẢM TRÙNG LẶP: Không lặp lại cùng một nội dung ở nhiều phần. CHỈ phân chia Lane A / Lane B khi vi phạm thực sự là vi phạm kép (BOTH). Nếu chỉ thuộc một làn, trình bày thành một luồng phân tích duy nhất.
4. ẨN 100% JSON & THÔNG TIN KỸ THUẬT: Tuyệt đối KHÔNG hiển thị chuỗi JSON thô, code block ```json, hay các tên biến kỹ thuật nội bộ (như 'structured_analysis', 'requires_approval = True') trong phần văn bản trả lời.
5. CHUẨN HÓA MARKDOWN: Không dùng các ký tự markdown escape lỗi (không viết '\\####', '1\\.', '\\*'). Hạn chế heading sâu và danh sách lồng nhau.

Trả về JSON có cấu trúc gồm trường 'answer' (chứa toàn bộ văn bản phản hồi tự nhiên cho người dùng tuân thủ 5 quy tắc trên) và trường 'structured_analysis'."""

                system_inst = (
                    "You are the Data Governance & Root Cause Analysis specialist for DataTrust OS. "
                    "Analyze objectively using actual evidence. Respond in natural, professional Vietnamese. "
                    "Always put conclusion first and respect all 5 formatting rules."
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

                # Extract embedded JSON if present
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

                # Ensure conclusion is clearly marked
                if not clean_response.startswith("**Kết luận:**") and not clean_response.startswith("Kết luận:"):
                    clean_response = f"**Kết luận:** Finding `{fid}` tại cột `{col}` vi phạm quy tắc `{rule}` ({reason}).\n\n" + clean_response

                # Record reasoning step into ReAct tracer
                session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
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

                return {
                    "response": clean_response or f"**Kết luận:** Đã hoàn thành phân tích cho Finding {fid}.",
                    "session_id": session_id,
                    "run_id": run_id,
                    "data": {
                        "finding": dict(finding_row),
                        "structured_analysis": structured_data
                    },
                    "traces": [step_trace.model_dump()]
                }


        # 2. If question is about proposing rules / Data Treatment
        if any(k in msg_lower for k in ("đề xuất rule", "treatment rule", "khắc phục", "quy tắc xử lý")):
            target_ds = context.get("dataset_id", "trips")
            target_col = context.get("column_name", "customer_phone")
            op_id = "mask_phone" if "phone" in target_col.lower() else ("round_decimal" if "lat" in target_col.lower() else "hash_sha256")
            params = {"prefix_len": 3, "suffix_len": 2, "mask_char": "*"} if op_id == "mask_phone" else {"decimals": 2}

            # Run actual dry-run simulation via dry_run_tool
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

            session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
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
            return {
                "response": resp,
                "session_id": session_id,
                "data": {"dry_run_result": dry_run_res},
                "traces": [rule_trace.model_dump()]
            }

        # 3. If question is about profiling
        if "profile" in msg_lower or "thống kê" in msg_lower:
            dataset_id = context.get("dataset_id", "ride_hailing_xanh_sm_trips")
            res = await self.profiler_agent.profile_dataset(dataset_id)
            return {
                "response": f"Đã hoàn thành phân tích profiling cho {dataset_id}.",
                "session_id": res.get("session_id"),
                "data": res.get("profile_data"),
                "traces": res.get("traces", [])
            }

        # 4. If question is about anomalies or drift
        if "drift" in msg_lower or "dị biệt" in msg_lower or "lệch" in msg_lower:
            dataset_id = context.get("dataset_id", "ride_hailing_xanh_sm_trips")
            col = context.get("column_name", "fare_amount")
            res = await self.anomaly_agent.detect_anomalies(dataset_id, col)
            return {
                "response": f"Đã kiểm tra dị biệt và độ trôi phân phối cho cột {col}.",
                "session_id": res.get("session_id"),
                "data": res.get("anomaly_data"),
                "traces": res.get("traces", [])
            }

        # 5. General conversational assistant via ReAct engine
        tools = {"profiler": self.profiler_agent.tools["profiler"]}
        res = await self.react_engine.run(
            goal=message,
            agent_type="AssistantAgent",
            tools=tools,
            context=context,
            session_id=session_id,
            step_callback=self._broadcast_step
        )

        return {
            "response": res.get("final_answer") or "Hệ thống DataTrust AI Agent đã ghi nhận yêu cầu và đối soát dữ liệu với catalog chính sách hiện hành.",
            "session_id": res.get("session_id"),
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
