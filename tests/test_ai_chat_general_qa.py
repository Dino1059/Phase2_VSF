"""
Comprehensive Benchmark & Regression Test Suite for DataTrust OS General Business Q&A Chat.

Verifies:
1. Hybrid intent classification across diverse Vietnamese/English phrasing, diacritics, and compound queries.
2. Distinct routing for RUN_METRICS, DOMAIN_GLOSSARY, RULE_INQUIRY, PIPELINE_ERROR_OR_PROGRESS,
   WARNING_INQUIRY, RCA, REMEDIATION, GENERAL_CONVERSATION, and UNSUPPORTED.
3. Canonical domain glossary definitions (Silver, Bronze, Gold, Lane A/B, L1-L4, Finding, Warning, Quarantine, HITL).
4. Deterministic response builders and grounding status (GROUNDED, PARTIAL, INSUFFICIENT_DATA, UNSUPPORTED).
5. Safe metrics calculation directly from `orchestration.pipeline_runs` (silver_count, silver_rate) without assuming 0.
6. Zero replacement characters (\\ufffd) and strict UTF-8 output quality.
7. Out-of-scope queries transparently rejected without generic greeting loops.
8. Multi-intent synthesis combining definitions and live run metrics.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.ai.services.intent_classifier import IntentClassifier, UserIntent
from backend.ai.domain.glossary import (
    lookup_glossary_term,
    suggest_closest_terms,
    format_term_response,
    GLOSSARY_REGISTRY
)
from backend.ai.services.context_registry import (
    ContextRouterRegistry,
    load_run_metrics_context,
    load_domain_glossary_context,
    build_run_metrics_response,
    build_domain_glossary_response,
    build_unsupported_response
)
from backend.ai.agents.orchestrator import DataTrustAgentOrchestrator, sanitize_chat_markdown
from backend.ai.services.llm_adapter import UnifiedLLMAdapter


# ==============================================================================
# 1. Intent Classifier Benchmark (Phrasing, Diacritics, Accents, Multi-intent)
# ==============================================================================

class TestIntentClassifierBenchmark:
    """Benchmark tests for intent classification accuracy and robustness."""

    @pytest.mark.parametrize("query", [
        "Run này có bao nhiêu dòng đạt chuẩn?",
        "run nay co bao nhieu dong dat chuan",
        "bao nhiêu dòng sạch",
        "bao nhieu dong sach",
        "tỷ lệ dữ liệu sạch của run hiện tại là bao nhiêu",
        "how many silver records in this run?",
        "tỉ lệ pass data đợt chạy này",
        "có bao nhiêu bản ghi bị cách ly quarantine?",
        "tổng số dòng quét được là bao nhiêu",
        "scanned records count",
        "tỉ lệ silver đạt bao nhiêu phần trăm",
    ])
    def test_run_metrics_intent_benchmark(self, query):
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.RUN_METRICS, f"Failed for query: {query}"
        assert res.confidence >= 0.70

    @pytest.mark.parametrize("query", [
        "có mấy record vào silver",
        "có mấy record được đưa vào tầng Silver?",
        "mấy dòng chuyển sang silver rồi",
        "Silver hiện nhận được bao nhiêu records?",
        "record pass được mấy dòng",
    ])
    def test_run_metrics_colloquial_slot_order(self, query):
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.RUN_METRICS, f"Failed for query: {query}"
        assert res.metric_target == "silver_count"

    @pytest.mark.parametrize("query, expected_term", [
        ("Silver là gì?", "silver"),
        ("silver la gi", "silver"),
        ("Định nghĩa chuẩn của Silver trong DataTrust", "silver"),
        ("What is Bronze layer?", "bronze"),
        ("Lane A và Lane B khác nhau như thế nào?", "lane_a"),
        ("Lane A là gì", "lane_a"),
        ("Lane B là gì", "lane_b"),
        ("L1 là gì?", "l1"),
        ("l1 la gi", "l1"),
        ("L2 là gì?", "l2"),
        ("L3 detector kiểm tra cái gì?", "l3"),
        ("L4 hoạt động ra sao?", "l4"),
        ("Finding là gì?", "finding"),
        ("Warning trong DataTrust là gì?", "warning"),
        ("HITL nghĩa là gì?", "hitl"),
        ("Khu vực cách ly quarantine là gì?", "quarantine"),
        ("Data treatment là gì?", "data_treatment"),
        ("SoD nghĩa là gì trong hệ thống?", "sod"),
    ])
    def test_domain_glossary_intent_benchmark(self, query, expected_term):
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.DOMAIN_GLOSSARY, f"Failed for query: {query}"
        assert res.glossary_term is not None
        assert expected_term in res.glossary_term.lower()

    @pytest.mark.parametrize("query", [
        "L1-L4 là gì",
        "L1–L4 là gì?",
        "L1 đến L4 nghĩa là gì",
        "giải thích L1 tới L4",
    ])
    def test_l1_l4_range_is_glossary_not_rule_id(self, query):
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.DOMAIN_GLOSSARY
        assert res.glossary_term == "detector_levels"

    def test_real_rule_id_still_routes_to_rule_inquiry(self):
        res = IntentClassifier.classify_detailed("Rule L1-01 là gì?")
        assert res.intent == UserIntent.RULE_INQUIRY

    def test_compound_multi_intent_query(self):
        """Compound query: 'Silver là gì và run này có bao nhiêu dòng đạt chuẩn?'"""
        query = "Silver là gì và run này có bao nhiêu dòng đạt chuẩn?"
        res = IntentClassifier.classify_detailed(query)
        assert res.is_multi_intent is True
        assert len(res.sub_intents) >= 2
        assert UserIntent.DOMAIN_GLOSSARY in res.sub_intents
        assert UserIntent.RUN_METRICS in res.sub_intents

    def test_compound_query_l1_and_quarantine_count(self):
        query = "Định nghĩa L1 và có bao nhiêu bản ghi bị cách ly?"
        res = IntentClassifier.classify_detailed(query)
        assert res.is_multi_intent is True
        assert UserIntent.DOMAIN_GLOSSARY in res.sub_intents
        assert UserIntent.RUN_METRICS in res.sub_intents

    @pytest.mark.parametrize("query", [
        "Rule L1-01 là gì?",
        "Quy tắc L2-02 kiểm tra gì?",
        "Chi tiết rule POL-VN-PDP-01",
    ])
    def test_rule_inquiry_not_hijacked_by_glossary(self, query):
        """Rule ID inquiries with hyphenated codes must route to RULE_INQUIRY, not DOMAIN_GLOSSARY."""
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.RULE_INQUIRY, f"Rule inquiry hijacked: {query}"

    def test_pipeline_error_intent_precedence(self):
        query = "Tại sao pipeline bị lỗi và dừng lại ở bước L3?"
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.PIPELINE_ERROR_OR_PROGRESS

    def test_remediation_intent_precedence(self):
        query = "Đề xuất treatment rule cho customer_phone"
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.REMEDIATION_ONLY

    def test_negation_suppresses_remediation(self):
        query = "Giải thích nguyên nhân vi phạm của finding FND-001, không cần giải pháp khắc phục"
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.ROOT_CAUSE_ONLY
        assert UserIntent.REMEDIATION_ONLY not in res.sub_intents

    @pytest.mark.parametrize("query", [
        "Hôm nay thời tiết Hà Nội thế nào?",
        "Viết cho tôi một bài thơ về mùa thu",
        "Cách nấu món phở bò ngon tại nhà",
        "Who won the FIFA World Cup in 2022?",
        "Tell me a funny joke about dogs",
        "Giá cổ phiếu VinFast hôm nay bao nhiêu?",
    ])
    def test_unsupported_queries_do_not_fall_into_general_conversation(self, query):
        """Out of scope queries must resolve to UNSUPPORTED, never GENERAL_CONVERSATION."""
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.UNSUPPORTED, f"Query '{query}' classified as {res.intent}"

    @pytest.mark.parametrize("query", [
        "Xin chào bạn",
        "Hello assistant",
        "Cảm ơn bạn nhé",
        "Thanks a lot",
        "Bạn có thể làm được những gì?",
        "Trợ lý có những tính năng gì?",
    ])
    def test_general_conversation_greetings_only(self, query):
        res = IntentClassifier.classify_detailed(query)
        assert res.intent == UserIntent.GENERAL_CONVERSATION


# ==============================================================================
# 2. Canonical Domain Glossary Verification
# ==============================================================================

class TestDomainGlossaryModule:
    """Verifies centralized domain glossary content and matching."""

    def test_canonical_terms_presence(self):
        expected_keys = {
            "silver", "bronze", "gold", "lane_a", "lane_b",
            "l1", "l2", "l3", "l4", "finding", "warning",
            "quarantine", "hitl", "data_treatment", "sod"
        }
        for key in expected_keys:
            term = lookup_glossary_term(key)
            assert term is not None, f"Missing canonical term: {key}"
            assert term.name_vi
            assert term.name_en
            assert term.definition_vi
            assert term.definition_en

    def test_l1_to_l4_detector_suite_definitions(self):
        """L1-L4 must follow detector suite specifications."""
        l1 = lookup_glossary_term("l1")
        assert "schema" in l1.definition_vi.lower()
        assert "bất biến xác định" in l1.definition_vi.lower()

        l2 = lookup_glossary_term("l2")
        assert "trôi dạt thống kê" in l2.definition_vi.lower() or "bất thường" in l2.definition_vi.lower()

        l3 = lookup_glossary_term("l3")
        assert "quan hệ đa biến" in l3.definition_vi.lower() or "liên thực thể" in l3.definition_vi.lower()

        l4 = lookup_glossary_term("l4")
        assert "điểm thay đổi" in l4.definition_vi.lower() or "dịch chuyển" in l4.definition_vi.lower()

    def test_silver_definition(self):
        silver = lookup_glossary_term("silver")
        assert "lane a" in silver.definition_vi.lower()
        assert "lane b" in silver.definition_vi.lower()
        assert "treatment" in silver.definition_vi.lower() or "chữa lành" in silver.definition_vi.lower()

    def test_fuzzy_suggestions_for_unknown_terms(self):
        unknown = "blockchain"
        suggestions = suggest_closest_terms(unknown)
        assert isinstance(suggestions, list)


# ==============================================================================
# 3. Context Loaders & Deterministic Builders
# ==============================================================================

class TestContextLoadersAndBuilders:
    """Verifies factual deterministic builders without LLM dependency."""

    def test_build_run_metrics_response_completed_run(self):
        context = {
            "run_id": "run-001",
            "exists": True,
            "is_ready": True,
            "dataset_id": "ev_telemetry",
            "status": "COMPLETED",
            "scanned_count": 1000000,
            "silver_count": 985000,
            "quarantine_count": 15000,
            "warning_count": 250,
            "not_evaluated_count": 0,
            "silver_rate": 98.50,
            "duration_ms": 1200
        }
        res = build_run_metrics_response(context, "run-001")
        assert res.grounding_status == "GROUNDED"
        assert "985,000" in res.response_text
        assert "98.50%" in res.response_text
        assert "15,000" in res.response_text
        assert res.data_payload["silver_count"] == 985000
        assert res.data_payload["silver_rate"] == 98.5

    def test_build_run_metrics_response_in_progress_no_zero_hallucination(self):
        context = {
            "run_id": "run-002",
            "exists": True,
            "is_ready": False,
            "dataset_id": "ev_telemetry",
            "status": "RUNNING",
            "scanned_count": 500000,
            "silver_count": None,  # Not finalized yet
            "quarantine_count": 12,
            "warning_count": 0,
            "not_evaluated_count": 0,
            "silver_rate": None,
            "duration_ms": 0
        }
        res = build_run_metrics_response(context, "run-002")
        assert res.grounding_status == "INSUFFICIENT_DATA"
        # Must NOT claim 0 or 0.0% silver rate
        assert "chưa được chốt" in res.response_text or "đang được xử lý" in res.response_text
        assert "0.00%" not in res.response_text

    def test_build_run_metrics_missing_run(self):
        context = {
            "run_id": "run-999",
            "exists": False,
            "is_ready": False,
            "dataset_id": None,
            "status": "UNKNOWN",
            "scanned_count": None,
            "silver_count": None,
            "quarantine_count": None,
            "warning_count": None,
            "not_evaluated_count": None,
            "silver_rate": None,
            "duration_ms": 0
        }
        res = build_run_metrics_response(context, "run-999")
        assert res.grounding_status == "INSUFFICIENT_DATA"
        assert "không tìm thấy" in res.response_text.lower()

    def test_build_domain_glossary_response_known_term(self):
        context = {
            "term": lookup_glossary_term("silver"),
            "found": True,
            "query": "silver",
            "suggestions": []
        }
        res = build_domain_glossary_response(context)
        assert res.grounding_status == "GROUNDED"
        assert "Bản ghi Silver" in res.response_text
        assert "Lane A" in res.response_text
        assert "Lane B" in res.response_text

    def test_build_domain_glossary_response_unknown_term(self):
        context = {
            "term": None,
            "found": False,
            "query": "quantum_computing",
            "suggestions": [lookup_glossary_term("l1"), lookup_glossary_term("l2")]
        }
        res = build_domain_glossary_response(context)
        assert res.grounding_status == "PARTIAL"
        assert "chưa có định nghĩa chính thức" in res.response_text

    def test_build_unsupported_response_no_greetings(self):
        res = build_unsupported_response("Hôm nay thời tiết thế nào?")
        assert res.grounding_status == "UNSUPPORTED"
        assert "xin chào" not in res.response_text.lower()
        assert "datatrust" in res.response_text.lower()
        assert res.data_payload["status"] == "OUT_OF_SCOPE"


# ==============================================================================
# 4. Context Router Registry Multi-Intent & Dispatch Execution
# ==============================================================================

class TestContextRouterRegistry:
    """Verifies the unified registry executing multi-intent and grounded synthesis."""

    def test_execute_multi_intent_silver_definition_and_run_metrics(self):
        classification = IntentClassifier.classify_detailed(
            "Silver là gì và run này có bao nhiêu dòng đạt chuẩn?"
        )
        assert classification.is_multi_intent is True

        mock_db_context = {
            "run_id": "test-run-101",
            "exists": True,
            "is_ready": True,
            "dataset_id": "ev_telemetry",
            "status": "COMPLETED",
            "scanned_count": 500000,
            "silver_count": 490000,
            "quarantine_count": 10000,
            "warning_count": 50,
            "not_evaluated_count": 0,
            "silver_rate": 98.00,
            "duration_ms": 1500
        }

        with patch("backend.ai.services.context_registry.load_run_metrics_context", return_value=mock_db_context):
            result = ContextRouterRegistry.execute(classification, run_id="test-run-101")
            assert result is not None
            assert result.grounding_status == "GROUNDED"
            # Both concepts must appear in the combined response
            assert "Bản ghi Silver" in result.response_text
            assert "490,000" in result.response_text
            assert "98.00%" in result.response_text
            assert "domain_glossary" in result.sources
            assert "orchestration.pipeline_runs" in result.sources


# ==============================================================================
# 5. Response Sanitization & Quality (Zero \ufffd, Clean UTF-8)
# ==============================================================================

class TestResponseQualityAndSanitization:
    """Verifies that no corrupted characters or leaked SQL queries escape to the user."""

    def test_sanitize_chat_markdown_removes_replacement_characters(self):
        corrupted = "Dữ liệu chuẩn Silver\ufffd đạt tỷ lệ 98.5% \ufffd và không có lỗi."
        clean = sanitize_chat_markdown(corrupted)
        assert "\ufffd" not in clean
        assert "98.5%" in clean

    def test_sources_do_not_contain_sql_queries(self):
        context = {
            "run_id": "run-001",
            "exists": True,
            "is_ready": True,
            "dataset_id": "ev_telemetry",
            "status": "COMPLETED",
            "scanned_count": 100000,
            "silver_count": 98000,
            "quarantine_count": 2000,
            "warning_count": 10,
            "not_evaluated_count": 0,
            "silver_rate": 98.00,
            "duration_ms": 1000
        }
        res = build_run_metrics_response(context, "run-001")
        for src in res.sources:
            assert "SELECT" not in src.upper()
            assert "FROM" not in src.upper()
            assert "WHERE" not in src.upper()


# ==============================================================================
# 6. End-to-End Orchestrator Routing Without LLM
# ==============================================================================

class TestOrchestratorEndToEnd:
    """Verifies DataTrustAgentOrchestrator handles business queries cleanly even without LLM."""

    @pytest.mark.asyncio
    async def test_orchestrator_handles_glossary_query_offline(self):
        adapter = UnifiedLLMAdapter(force_mock=True)
        orchestrator = DataTrustAgentOrchestrator(llm_adapter=adapter)
        res = await orchestrator.chat(
            message="Silver là gì?",
            run_id="demo-run-001"
        )
        assert res["intent"] == "DOMAIN_GLOSSARY"
        assert res["data"]["grounding_status"] == "GROUNDED"
        assert "Bản ghi Silver" in res["response"]
        assert "\ufffd" not in res["response"]

    @pytest.mark.asyncio
    async def test_orchestrator_handles_unsupported_query_offline(self):
        adapter = UnifiedLLMAdapter(force_mock=True)
        orchestrator = DataTrustAgentOrchestrator(llm_adapter=adapter)
        res = await orchestrator.chat(
            message="Hôm nay thời tiết TP.HCM có mưa không?",
            run_id="demo-run-001"
        )
        assert res["intent"] == "UNSUPPORTED"
        assert res["data"]["grounding_status"] == "UNSUPPORTED"
        assert "xin chào" not in res["response"].lower()
        assert "datatrust" in res["response"].lower()
