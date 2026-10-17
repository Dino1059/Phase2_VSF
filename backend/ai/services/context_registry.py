"""
DataTrust OS: Centralized Context & Response Router Registry
Maps user intents to dedicated context loaders and deterministic response builders.
Enforces Run Isolation, grounded factual answers, and transparent fallbacks.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from backend.ai.services.intent_classifier import UserIntent, ClassificationResult
from backend.ai.domain.glossary import (
    lookup_glossary_term,
    suggest_closest_terms,
    format_term_response,
    GlossaryTerm
)
from database.profiler_engine import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("DataTrust.ContextRegistry")


@dataclass
class RegistryExecutionResult:
    response_text: str
    grounding_status: str  # "GROUNDED", "PARTIAL", "INSUFFICIENT_DATA", "UNSUPPORTED"
    sources: List[str] = field(default_factory=list)
    data_payload: Dict[str, Any] = field(default_factory=dict)
    structured_analysis: Optional[Dict[str, Any]] = None


# -----------------------------------------------------------------------------
# 1. SPECIALIZED CONTEXT LOADERS
# -----------------------------------------------------------------------------

def load_run_metrics_context(run_id: str) -> Dict[str, Any]:
    """
    Directly queries orchestration.pipeline_runs.
    silver_count is the official source of truth for clean records (never derived by subtraction).
    """
    context: Dict[str, Any] = {
        "run_id": run_id,
        "exists": False,
        "is_ready": False,
        "status": "UNKNOWN",
        "scanned_count": None,
        "silver_count": None,
        "quarantine_count": None,
        "warning_count": None,
        "not_evaluated_count": None,
        "silver_rate": None,
        "duration_ms": 0,
        "dataset_id": None
    }

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT run_id, dataset_id, status, started_at, ended_at,
                       scanned_count, silver_count, quarantine_count, warning_count,
                       not_evaluated_count, execution_duration_ms, error_message
                FROM orchestration.pipeline_runs
                WHERE run_id = %s LIMIT 1;
                """,
                (run_id,)
            )
            row = cur.fetchone()
        conn.close()

        if not row:
            return context

        context["exists"] = True
        context["status"] = row.get("status") or "UNKNOWN"
        context["dataset_id"] = row.get("dataset_id")
        context["duration_ms"] = row.get("execution_duration_ms") or 0

        scanned = row.get("scanned_count")
        silver = row.get("silver_count")
        quarantine = row.get("quarantine_count")
        warning = row.get("warning_count")
        not_eval = row.get("not_evaluated_count")

        context["scanned_count"] = scanned
        context["silver_count"] = silver
        context["quarantine_count"] = quarantine
        context["warning_count"] = warning
        context["not_evaluated_count"] = not_eval

        # Determine readiness: Completed runs have final counts
        if context["status"] in ("COMPLETED", "SUCCESS", "FAILED", "STOPPED"):
            context["is_ready"] = True
            if scanned is not None and scanned > 0 and silver is not None:
                context["silver_rate"] = round((silver / scanned) * 100, 2)
            elif scanned == 0:
                context["silver_rate"] = 0.0

    except Exception as e:
        logger.warning(f"Error loading run metrics for {run_id}: {e}")

    return context


def load_domain_glossary_context(query: str, term_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Looks up official definition from backend.ai.domain.glossary.
    Provides closest fuzzy suggestions when term is not found.
    """
    lookup_target = term_id or query
    term = lookup_glossary_term(lookup_target)
    suggestions: List[GlossaryTerm] = []

    if not term:
        suggestions = suggest_closest_terms(query, limit=3)

    return {
        "term": term,
        "found": term is not None,
        "query": query,
        "suggestions": suggestions
    }


# -----------------------------------------------------------------------------
# 2. DETERMINISTIC RESPONSE BUILDERS
# -----------------------------------------------------------------------------

def build_run_metrics_response(ctx: Dict[str, Any], run_id: str, metric_target: Optional[str] = None) -> RegistryExecutionResult:
    """
    Constructs an authoritative response for run metrics without hallucinating counts or subtracting.
    Does NOT output generic greetings.
    """
    if not ctx.get("exists"):
        return RegistryExecutionResult(
            response_text=f"Không tìm thấy lần chạy `{run_id}` trong hệ thống điều phối kiểm toán DataTrust.",
            grounding_status="INSUFFICIENT_DATA",
            sources=["orchestration.pipeline_runs"],
            data_payload={"run_id": run_id, "status": "NOT_FOUND"}
        )

    status = ctx.get("status")
    if not ctx.get("is_ready"):
        return RegistryExecutionResult(
            response_text=(
                f"Lần chạy `{run_id}` hiện đang ở trạng thái **{status}**.\n\n"
                f"Các chỉ số kiểm toán (dữ liệu sạch Silver, bản ghi cách ly, cảnh báo) đang trong quá trình thực thi (đang được xử lý) "
                f"và chưa được chốt tính toán. Số liệu chính thức sẽ sẵn sàng ngay khi pipeline hoàn thành."
            ),
            grounding_status="INSUFFICIENT_DATA",
            sources=["orchestration.pipeline_runs"],
            data_payload={"run_id": run_id, "status": status, "is_ready": False}
        )

    scanned = ctx.get("scanned_count")
    silver = ctx.get("silver_count")
    quarantine = ctx.get("quarantine_count")
    warning = ctx.get("warning_count")
    not_eval = ctx.get("not_evaluated_count")
    silver_rate = ctx.get("silver_rate")

    # If user specifically asked about silver count / rate
    if metric_target == "silver_count":
        if silver is not None and scanned is not None:
            rate_str = f" ({silver_rate:.2f}%)" if silver_rate is not None else ""
            resp = (
                f"Trong lần chạy `{run_id}` (Trạng thái: **{status}**):\n\n"
                f"• **Số lượng bản ghi Silver (dữ liệu sạch đạt chuẩn)**: **{silver:,}** dòng{rate_str}\n"
                f"• **Tổng số bản ghi đã quét (`scanned_count`)**: **{scanned:,}** dòng\n"
                f"• **Bản ghi cách ly vi phạm (`quarantine_count`)**: **{quarantine or 0:,}** dòng\n"
                f"• **Bản ghi cảnh báo (`warning_count`)**: **{warning or 0:,}** dòng\n\n"
                f"📌 *Nguồn dữ liệu: Chỉ số `silver_count` đọc trực tiếp từ bảng điều phối `orchestration.pipeline_runs`.*"
            )
        else:
            resp = f"Lần chạy `{run_id}` chưa ghi nhận đủ dữ liệu về số dòng Silver đạt chuẩn (chỉ số hiện là NULL)."
    elif metric_target == "quarantine_count":
        quar_rate = round((quarantine / scanned) * 100, 2) if (scanned and quarantine is not None and scanned > 0) else 0.0
        resp = (
            f"Trong lần chạy `{run_id}` (Trạng thái: **{status}**):\n\n"
            f"• **Số bản ghi bị cách ly (`quarantine_count`)**: **{quarantine or 0:,}** dòng ({quar_rate:.2f}%)\n"
            f"• **Tổng số bản ghi quét**: **{scanned or 0:,}** dòng\n"
            f"• **Bản ghi Silver đạt chuẩn**: **{silver or 0:,}** dòng\n\n"
            f"Các bản ghi cách ly do vi phạm quy tắc kỹ thuật Lane A hoặc chính sách tuân thủ Lane B."
        )
    elif metric_target == "warning_count":
        resp = (
            f"Trong lần chạy `{run_id}` (Trạng thái: **{status}**):\n\n"
            f"• **Số lượng bản ghi cảnh báo (`warning_count`)**: **{warning or 0:,}** dòng\n"
            f"• **Tổng số bản ghi quét**: **{scanned or 0:,}** dòng\n\n"
            f"Cảnh báo là các dấu hiệu bất thường thống kê hoặc trôi dạt số liệu (L2–L4) để kiểm toán viên giám sát, không chặn luồng bản ghi."
        )
    else:
        rate_str = f" ({silver_rate:.2f}%)" if silver_rate is not None else ""
        resp = (
            f"Báo cáo số liệu kiểm toán lần chạy `{run_id}` (Trạng thái: **{status}**):\n\n"
            f"• **Tổng số bản ghi quét (`scanned_count`)**: **{scanned or 0:,}** dòng\n"
            f"• **Dữ liệu sạch đạt chuẩn (`silver_count`)**: **{silver or 0:,}** dòng{rate_str}\n"
            f"• **Bản ghi cách ly vi phạm (`quarantine_count`)**: **{quarantine or 0:,}** dòng\n"
            f"• **Bản ghi cảnh báo (`warning_count`)**: **{warning or 0:,}** dòng\n"
            f"• **Bản ghi chưa đánh giá (`not_evaluated_count`)**: **{not_eval or 0:,}** dòng\n\n"
            f"📌 *Nguồn dữ liệu: Bảng `orchestration.pipeline_runs` (không suy diễn bằng phép trừ).* "
        )

    data_payload = {
        "run_id": run_id,
        "status": status,
        "scanned_count": scanned,
        "silver_count": silver,
        "silver_rate": silver_rate,
        "quarantine_count": quarantine,
        "warning_count": warning,
        "not_evaluated_count": not_eval,
    }

    return RegistryExecutionResult(
        response_text=resp,
        grounding_status="GROUNDED",
        sources=["orchestration.pipeline_runs"],
        data_payload=data_payload
    )


def build_domain_glossary_response(ctx: Dict[str, Any]) -> RegistryExecutionResult:
    """
    Constructs canonical glossary response. If term is missing, suggests closest candidates.
    Does NOT output generic greetings.
    """
    term: Optional[GlossaryTerm] = ctx.get("term")
    if term:
        return RegistryExecutionResult(
            response_text=format_term_response(term),
            grounding_status="GROUNDED",
            sources=["domain_glossary"],
            data_payload={
                "term_id": term.term_id,
                "name_vi": term.name_vi,
                "name_en": term.name_en,
                "category": term.category
            }
        )

    # Term not found in glossary
    query = ctx.get("query", "")
    suggestions = ctx.get("suggestions", [])
    if suggestions:
        sugg_lines = "\n".join([f"• **{s.name_vi}** (`{s.term_id}`): {s.definition_vi[:90]}..." for s in suggestions])
        resp = (
            f"Hệ thống DataTrust hiện chưa có định nghĩa chính thức cho thuật ngữ '{query}'.\n\n"
            f"Bạn có thể tham khảo các thuật ngữ quản trị kiểm toán gần nhất trong hệ thống:\n{sugg_lines}\n\n"
            f"*(Bạn có thể hỏi 'Silver là gì?', 'L1 là gì?', hoặc 'Lane A là gì?')*"
        )
    else:
        resp = (
            f"Hệ thống DataTrust hiện chưa có định nghĩa chính thức cho thuật ngữ '{query}'.\n\n"
            f"DataTrust hỗ trợ tra cứu các thuật ngữ chuẩn: **Silver**, **Bronze**, **Gold**, **Lane A**, **Lane B**, "
            f"**L1–L4**, **Finding**, **Warning**, **Quarantine**, **HITL**, **Data Treatment**, và **SoD**."
        )

    return RegistryExecutionResult(
        response_text=resp,
        grounding_status="PARTIAL",
        sources=["domain_glossary"],
        data_payload={"query": query, "found": False}
    )


def build_unsupported_response(raw_query: str) -> RegistryExecutionResult:
    """
    Transparent fallback for out-of-scope questions.
    Explains scope clearly and lists supported categories without greeting.
    """
    resp = (
        "Trợ lý AI DataTrust OS được thiết kế chuyên biệt để hỗ trợ kiểm toán chất lượng dữ liệu, "
        "tuân thủ chính sách và phân tách trách nhiệm (SoD).\n\n"
        "Câu hỏi của bạn hiện nằm ngoài phạm vi nghiệp vụ được hỗ trợ. Bạn có thể hỏi về các nhóm chủ đề sau:\n"
        "1. 📊 **Số liệu lần chạy (`run_id`)**: Số lượng và tỷ lệ dữ liệu sạch (Silver), số bản ghi cách ly, cảnh báo, tổng số bản ghi quét.\n"
        "2. 📖 **Thuật ngữ & Khái niệm**: Định nghĩa Silver, Bronze, L1–L4 (ràng buộc schema, trôi dạt thống kê, quan hệ liên thực thể, điểm thay đổi chuỗi thời gian), Lane A/B, Finding, Warning, HITL, SoD.\n"
        "3. 🔍 **Điều tra Vi phạm & Khắc phục**: Phân tích nguyên nhân gốc rễ (RCA), kiểm tra bằng chứng vi phạm, đề xuất quy tắc chuẩn hóa (Data Treatment Rule).\n"
        "4. 🛡️ **Quy tắc & Khung pháp lý**: Kiểm tra tuân thủ Luật 91, Nghị định 13, GDPR, CCPA, SOX-404, tra cứu catalog dữ liệu và tiến độ pipeline."
    )
    return RegistryExecutionResult(
        response_text=resp,
        grounding_status="UNSUPPORTED",
        sources=[],
        data_payload={"raw_query": raw_query, "status": "OUT_OF_SCOPE"}
    )


# -----------------------------------------------------------------------------
# 3. ROUTER REGISTRY DISPATCHER
# -----------------------------------------------------------------------------

class ContextRouterRegistry:
    """
    Central dispatcher routing intents to loaders and response builders.
    Supports single intent and composite multi-intent execution.
    """

    @classmethod
    def execute(cls, classification: ClassificationResult, run_id: str) -> RegistryExecutionResult:
        """
        Executes routing based on classification result.
        """
        intent = classification.intent
        sub_intents = classification.sub_intents
        is_multi = classification.is_multi_intent and len(sub_intents) > 1

        # 1. Multi-Intent Handling (e.g. Glossary + Run Metrics)
        if is_multi:
            return cls._execute_multi_intent(classification, run_id)

        # 2. Single Intent Dispatch
        if intent == UserIntent.RUN_METRICS:
            ctx = load_run_metrics_context(run_id)
            return build_run_metrics_response(ctx, run_id, classification.metric_target)

        elif intent == UserIntent.DOMAIN_GLOSSARY:
            ctx = load_domain_glossary_context(classification.raw_query, classification.glossary_term)
            return build_domain_glossary_response(ctx)

        elif intent == UserIntent.UNSUPPORTED:
            return build_unsupported_response(classification.raw_query)

        # For intents handled by existing specialized orchestrator agents (RCA, Rule, Overview, Warning):
        # returns None to delegate to orchestrator's specialized sub-agents
        return None

    @classmethod
    def _execute_multi_intent(cls, classification: ClassificationResult, run_id: str) -> RegistryExecutionResult:
        """
        Executes each sub-intent and joins responses harmoniously.
        """
        responses: List[str] = []
        sources: List[str] = []
        combined_payload: Dict[str, Any] = {}
        statuses: List[str] = []

        for sub in classification.sub_intents:
            if sub == UserIntent.DOMAIN_GLOSSARY:
                term_target = classification.glossary_term or classification.raw_query
                ctx = load_domain_glossary_context(term_target, classification.glossary_term)
                res = build_domain_glossary_response(ctx)
                responses.append(res.response_text)
                sources.extend(res.sources)
                statuses.append(res.grounding_status)
                combined_payload.update(res.data_payload)

            elif sub == UserIntent.RUN_METRICS:
                ctx = load_run_metrics_context(run_id)
                res = build_run_metrics_response(ctx, run_id, classification.metric_target)
                responses.append(res.response_text)
                sources.extend(res.sources)
                statuses.append(res.grounding_status)
                combined_payload.update(res.data_payload)

        if not responses:
            return build_unsupported_response(classification.raw_query)

        # Merge responses cleanly
        merged_text = "\n\n---\n\n".join(responses)
        unique_sources = list(dict.fromkeys(sources))

        overall_status = "GROUNDED" if all(s == "GROUNDED" for s in statuses) else "PARTIAL"

        return RegistryExecutionResult(
            response_text=merged_text,
            grounding_status=overall_status,
            sources=unique_sources,
            data_payload=combined_payload
        )
