import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.database.models import (
    ActionType,
    FindingAIAnalysisModel,
    QuarantineRecordModel,
    RuleSeverity
)
from backend.ai.agents.orchestrator import DataTrustAgentOrchestrator
from backend.ai.services.llm_adapter import UnifiedLLMAdapter
from backend.ai.services.realtime_tracer import RealtimeTracer
from backend.api import main as api_main


@pytest.fixture
def mock_orchestrator():
    adapter = UnifiedLLMAdapter(force_mock=True)
    orch = DataTrustAgentOrchestrator(llm_adapter=adapter)
    return orch


@pytest.mark.asyncio
async def test_chat_invokes_llm_adapter_dynamically(mock_orchestrator, monkeypatch):
    """
    Tiêu chuẩn 1 & 6: Chat không dùng template hardcode, thực sự gọi llm_adapter và sinh trace.
    """
    call_tracker = {"called": False, "prompt": "", "context": {}}

    def spy_complete(prompt, system_instruction="", context=None, temperature=0.1, max_tokens=1024):
        call_tracker["called"] = True
        call_tracker["prompt"] = prompt
        call_tracker["context"] = context
        return {
            "text": json.dumps({
                "explanation": "Động cơ LLM đã phân tích dữ liệu động từ finding.",
                "root_cause": "Tải vận hành cao đột xuất trong chu kỳ nạp nhanh.",
                "confidence": 0.90,
                "confidence_method": "EVIDENCE_GROUNDED_VERIFICATION",
                "failure_lane": "LANE_A",
                "rule_id": "CHK-TELEM-TEMP",
                "violation_type": "PHYSICAL_BOUND_BREACH",
                "observation": "battery_temp_c = 92.5°C vượt ngưỡng 85.0°C",
                "hypotheses": [
                    {
                        "hypothesis": "Tải vận hành cao trong môi trường nhiệt độ cao",
                        "likelihood": "HIGH",
                        "supporting_evidence": "Dòng sạc đỉnh đạt 150kW"
                    }
                ],
                "structured_remediation": {
                    "action_type": "MANUAL_INSPECTION",
                    "action_summary": "Kiểm tra hệ thống tản nhiệt và hiệu chuẩn cảm biến",
                    "parameters": {"target": "battery_temp_c"},
                    "expected_outcome": "Đảm bảo pack pin vận hành dưới 85°C",
                    "dry_run_supported": False,
                    "requires_approval": True
                }
            }, ensure_ascii=False),
            "provider": "spy_llm",
            "tokens_used": 180,
            "guardrail_report": {}
        }

    monkeypatch.setattr(mock_orchestrator.llm_adapter, "complete", spy_complete)

    # Giả lập tìm thấy finding trong DB
    fake_finding = {
        "finding_id": "FND-TEST-001",
        "dataset_id": "telemetry",
        "column_name": "battery_temp_c",
        "rule_id": "CHK-TELEM-TEMP",
        "severity": "CRITICAL",
        "reason": "battery_temp_c = 92.5 vượt ngưỡng 85.0",
        "failed_record_count": 5,
        "run_id": "run-test-01"
    }

    class MockCursor:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            pass
        def fetchone(self):
            return fake_finding

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    res = await mock_orchestrator.chat(
        message="Giải thích nguyên nhân vi phạm cho finding FND-TEST-001",
        run_id="run-test-01",
        session_id="test-session-123"
    )

    # Xác nhận llm_adapter thực sự được gọi động
    assert call_tracker["called"] is True
    assert "FND-TEST-001" in call_tracker["prompt"]
    assert res["session_id"] == "test-session-123"
    assert len(res["traces"]) >= 1
    assert res["traces"][0]["action"] == "CALL_LLM_RCA_ANALYSIS"
    assert "Động cơ LLM đã phân tích" in res["response"]
    assert res["data"]["structured_analysis"] is not None
    assert res["data"]["structured_analysis"]["rule_id"] == "CHK-TELEM-TEMP"


def test_lane_a_technical_reliability_no_privacy_hallucination():
    """
    Tiêu chuẩn 7: Lane A (Kỹ thuật/Cảm biến) không được tự tiện viện dẫn Luật 91 PII.
    """
    adapter = UnifiedLLMAdapter(force_mock=True)
    context = {
        "finding": {
            "finding_id": "FND-TEMP-01",
            "rule_id": "CHK-TELEM-TEMP",
            "column_name": "battery_temp_c",
            "reason": "battery_temp_c exceeded 85C",
            "law_ref": None  # Không có luật PII
        },
        "failure_lane": "LANE_A",
        "evidence": [{"quarantine_id": "Q-01", "source_row_pk": "VIN-100"}]
    }

    res = adapter.complete(
        prompt="Chẩn đoán nguyên nhân vi phạm nhiệt độ pin FND-TEMP-01",
        context=context
    )
    payload = json.loads(res["text"])

    # Kiểm tra phân định Lane A
    assert payload["failure_lane"] == "LANE_A"
    assert payload["violation_type"] == "PHYSICAL_BOUND_BREACH"
    assert payload["lane_specific_details"]["lane_a"] is not None
    assert payload["lane_specific_details"]["lane_b"] is None
    # Không viện dẫn Luật 91 hay GDPR
    std_ref = payload["lane_specific_details"]["lane_a"]["standard_or_law_ref"]
    if std_ref:
        assert "91/2025" not in std_ref
        assert "GDPR" not in std_ref


def test_detection_vs_root_cause_hypotheses_separation():
    """
    Tiêu chuẩn 1: Phân biệt Observation (phát hiện) vs Hypotheses (nguyên nhân có căn cứ).
    """
    adapter = UnifiedLLMAdapter(force_mock=True)
    context = {
        "finding": {
            "finding_id": "FND-SOC-01",
            "rule_id": "CHK-TELEM-SOC",
            "column_name": "battery_soc",
            "reason": "battery_soc is 105.0% (> 100%)"
        },
        "failure_lane": "LANE_A",
        "evidence": [{"quarantine_id": "Q-02", "source_row_pk": "VIN-102"}]
    }

    res = adapter.complete(prompt="Phân tích RCA finding FND-SOC-01", context=context)
    payload = json.loads(res["text"])

    # Observation phải là phát hiện khách quan
    assert "battery_soc" in payload["observation"]
    # Phải có ít nhất 2 giả thuyết nguyên nhân (không kết luận 1 chiều hỏng cảm biến)
    hyps = payload["hypotheses"]
    assert len(hyps) >= 2
    for h in hyps:
        assert "hypothesis" in h
        assert "likelihood" in h
        assert "supporting_evidence" in h


def test_both_lanes_separate_remediation():
    """
    Tiêu chuẩn 2 & 5: Khi vi phạm BOTH, tách bạch lane_a và lane_b cả về phân tích lẫn đề xuất.
    """
    adapter = UnifiedLLMAdapter(force_mock=True)
    context = {
        "finding": {
            "finding_id": "FND-BOTH-01",
            "rule_id": "CHK-MULTI-GATE",
            "column_name": "customer_phone_and_speed",
            "reason": "Cleartext phone and speed arithmetic mismatch"
        },
        "failure_lane": "BOTH",
        "evidence": [{"quarantine_id": "Q-03", "source_row_pk": "TRIP-999"}]
    }

    res = adapter.complete(prompt="Chẩn đoán nguyên nhân vi phạm BOTH FND-BOTH-01", context=context)
    payload = json.loads(res["text"])

    assert payload["failure_lane"] == "BOTH"
    lane_details = payload["lane_specific_details"]
    assert lane_details["lane_a"] is not None
    assert lane_details["lane_b"] is not None
    # Lane A có remediation kỹ thuật
    assert lane_details["lane_a"]["remediation_action"]["action_type"] in [
        ActionType.MANUAL_INSPECTION.value, ActionType.REPROCESS_PAYLOAD.value, ActionType.RECALIBRATE_BASELINE.value
    ]
    # Lane B có remediation chính sách PII
    assert lane_details["lane_b"]["remediation_action"]["action_type"] == ActionType.DATA_TREATMENT_PROPOSAL.value


def test_strict_hitl_and_confidence_evaluation():
    """
    Tiêu chuẩn 3 & 4: Mọi remediation đều requires_approval = True, confidence có method hoặc null khi thiếu context.
    """
    adapter = UnifiedLLMAdapter(force_mock=True)

    # Trường hợp 1: Đủ bằng chứng
    ctx_full = {
        "finding": {"finding_id": "F-FULL", "rule_id": "CHK-01", "column_name": "phone"},
        "failure_lane": "LANE_B",
        "evidence": [{"quarantine_id": "Q-1"}]
    }
    res_full = adapter.complete("Chẩn đoán F-FULL", context=ctx_full)
    p_full = json.loads(res_full["text"])
    assert p_full["confidence_method"] is not None
    assert p_full["structured_remediation"]["requires_approval"] is True

    # Trường hợp 2: Thiếu context -> confidence = None hoặc confidence_method = INSUFFICIENT_EVIDENCE
    ctx_missing = {
        "finding": {"finding_id": "F-MISSING", "rule_id": "CHK-02", "column_name": "unknown"},
        "failure_lane": "LANE_B",
        "missing_context": ["lineage", "policy"],
        "evidence": []
    }
    res_missing = adapter.complete("Chẩn đoán F-MISSING", context=ctx_missing)
    p_missing = json.loads(res_missing["text"])
    assert p_missing["confidence_method"] == "INSUFFICIENT_EVIDENCE"


def test_realtime_tracer_lane_awareness():
    """
    Tiêu chuẩn 1 & 7: 4-Tier Realtime Tracer thể hiện đúng Cổng kiểm định theo failure_lane.
    """
    tracer = RealtimeTracer()

    # Record Lane A
    rec_a = QuarantineRecordModel(
        quarantine_id="q-lane-a-01",
        run_id="run-01",
        dataset_id="telemetry",
        source_table="bronze.telemetry",
        failure_lane="LANE_A",
        violation_column="battery_temp_c",
        violation_rule_id="CHK-TELEM-TEMP",
        violation_reason="battery_temp_c > 85.0",
        raw_record_json={"battery_temp_c": 95.0},
        lineage_hash="hash_a_123"
    )
    report_a = tracer.trace_quarantine_record(rec_a)
    assert report_a["tier_2"]["failure_lane"] == "LANE_A"
    assert "Lane A" in report_a["tier_2"]["title"]
    assert "Luật 91/2025" not in str(report_a["tier_4"]["compliance_standards"])

    # Record Lane B
    rec_b = QuarantineRecordModel(
        quarantine_id="q-lane-b-01",
        run_id="run-02",
        dataset_id="trips",
        source_table="bronze.trips",
        failure_lane="LANE_B",
        violation_column="customer_phone",
        violation_rule_id="RULE-PII-01",
        violation_reason="Cleartext phone exposed",
        raw_record_json={"customer_phone": "0987654321"},
        lineage_hash="hash_b_456"
    )
    report_b = tracer.trace_quarantine_record(rec_b)
    assert report_b["tier_2"]["failure_lane"] == "LANE_B"
    assert "Lane B" in report_b["tier_2"]["title"]
    assert "Luật 91/2025" in str(report_b["tier_4"]["compliance_standards"])
