"""
Unit tests for Intent Classification, Response Schemas, and PII Masking in DataTrust OS.
Verifies:
1. Intent classification with negation handling ('không cần giải pháp' -> ROOT_CAUSE_ONLY)
2. Dual request classification ('nguyên nhân và cách khắc phục' -> BOTH_RCA_AND_REMEDIATION)
3. Pipeline error/progress request classification -> PIPELINE_ERROR_OR_PROGRESS
4. PII masking and field allowlisting
5. Pydantic response schemas validation
6. Text Sanitizer cleans escaped markdown and leaked variables
"""

import pytest
from backend.ai.services.intent_classifier import IntentClassifier, UserIntent
from backend.ai.services.context_loader import mask_pii_value, sanitize_sample_record
from backend.ai.services.response_schema import (
    FindingRCAResponse,
    RunOverviewResponse,
    CleanRunResponse,
    PipelineErrorResponse
)
from backend.ai.agents.orchestrator import sanitize_chat_markdown


def test_intent_classification_root_cause_with_negation():
    """
    Test: User asks for root cause and explicitly states NO remediation.
    Should resolve strictly to ROOT_CAUSE_ONLY.
    """
    msg1 = "Giải thích nguyên nhân vi phạm của finding FND-001, không cần giải pháp khắc phục"
    assert IntentClassifier.classify(msg1) == UserIntent.ROOT_CAUSE_ONLY

    msg2 = "Tại sao bản ghi này bị cách ly? Chưa cần khắc phục hay đề xuất rule."
    assert IntentClassifier.classify(msg2) == UserIntent.ROOT_CAUSE_ONLY

    msg3 = "Chỉ giải thích nguyên nhân và lý do vi phạm, đừng nêu remediation"
    assert IntentClassifier.classify(msg3) == UserIntent.ROOT_CAUSE_ONLY


def test_intent_classification_both_rca_and_remediation():
    """
    Test: User asks for both cause and remediation.
    """
    msg = "Giải thích nguyên nhân vi phạm và đề xuất giải pháp khắc phục cho finding này"
    assert IntentClassifier.classify(msg) == UserIntent.BOTH_RCA_AND_REMEDIATION


def test_intent_classification_remediation_only():
    """
    Test: User only asks for remedy/treatment rule.
    """
    msg = "Đề xuất quy tắc khắc phục (treatment rule) cho cột customer_phone"
    assert IntentClassifier.classify(msg) == UserIntent.REMEDIATION_ONLY


def test_intent_classification_pipeline_error_or_progress():
    """
    Test: User asks about step progress or pipeline errors.
    """
    msg1 = "Bước này đang làm gì? Hãy giải thích chi tiết."
    assert IntentClassifier.classify(msg1) == UserIntent.PIPELINE_ERROR_OR_PROGRESS

    msg2 = "Tại sao pipeline bị lỗi và dừng lại ở bước L3?"
    assert IntentClassifier.classify(msg2) == UserIntent.PIPELINE_ERROR_OR_PROGRESS


def test_intent_classification_run_overview():
    """
    Test: User asks about general run status and counts.
    """
    msg = "Tổng quan lần chạy này thế nào? Có bao nhiêu lỗi?"
    assert IntentClassifier.classify(msg) == UserIntent.RUN_OVERVIEW


def test_pii_masking_and_allowlist():
    """
    Test: PII fields are masked and unwhitelisted fields are removed.
    """
    raw_sample = {
        "customer_phone": "0987654321",
        "driver_name": "Nguyễn Văn A",
        "trip_distance_km": 15.2,
        "fare_amount": 120000.0,
        "internal_secret_token": "secret_abc123",
        "system_debug_dump": {"nested": "value"}
    }

    sanitized = sanitize_sample_record(raw_sample)

    # Whitelisted business fields preserved
    assert sanitized["trip_distance_km"] == 15.2
    assert sanitized["fare_amount"] == 120000.0

    # PII fields masked
    assert "0987654321" not in sanitized["customer_phone"]
    assert "***" in sanitized["customer_phone"]
    assert "Nguyễn Văn A" not in sanitized["driver_name"]
    assert "***" in sanitized["driver_name"]

    # Non-whitelisted internal fields dropped
    assert "internal_secret_token" not in sanitized
    assert "system_debug_dump" not in sanitized


def test_response_schemas_validation():
    """
    Test: Discriminated response schemas instantiate and validate correctly.
    """
    rca = FindingRCAResponse(
        answer="**Kết luận:** Bản ghi có tọa độ GPS nằm ngoài EU.\n\n- Giả thuyết 1: Lỗi sensor.",
        finding_id="F-01",
        run_id="RUN-01",
        conclusion="Bản ghi vi phạm vùng địa lý",
        root_cause="Lỗi truyền phát GPS",
        hypotheses=[{"hypothesis": "Lỗi sensor", "likelihood": "HIGH", "supporting_evidence": "lat=21.0"}]
    )
    assert rca.response_type == "FINDING_RCA"

    overview = RunOverviewResponse(
        answer="**Kết luận:** Lần chạy hoàn thành tốt.",
        run_id="RUN-01",
        status="COMPLETED",
        dataset_id="trips",
        scanned_count=1000,
        quarantine_count=5,
        critical_findings_count=1
    )
    assert overview.response_type == "RUN_OVERVIEW"


def test_sanitize_chat_markdown_removes_escapes_and_leaks():
    """
    Test: Sanitizer strips escapes like \\####, 1\\., \\* and leaked variables like requires_approval = True.
    """
    bad_text = (
        "\\#### Tiêu đề lỗi\n"
        "1\\. Bước một vi phạm \\*\\*rất nặng\\*\\*.\n"
        "requires_approval = True\n"
        "structured_analysis: {}\n"
        "```json\n{\"leak\": true}\n```\n"
        "Kết luận bình thường."
    )
    clean = sanitize_chat_markdown(bad_text)

    assert "\\####" not in clean
    assert "1\\." not in clean
    assert "\\*" not in clean
    assert "requires_approval" not in clean
    assert "structured_analysis" not in clean
    assert "```json" not in clean
    assert "Kết luận bình thường" in clean
