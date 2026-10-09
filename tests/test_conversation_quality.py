"""
Test suite for Conversation Quality, Multi-Turn Memory, Ambiguity Clarification,
Topic Switching, and Natural Dialogue in DataTrust OS AI Agent.
"""

import pytest
import json
import uuid
from backend.ai.agents.orchestrator import DataTrustAgentOrchestrator
from backend.ai.services.llm_adapter import UnifiedLLMAdapter
from backend.ai.services.chat_session_manager import session_manager
from backend.ai.services.intent_classifier import IntentClassifier, UserIntent


@pytest.fixture
def mock_orchestrator():
    adapter = UnifiedLLMAdapter(force_mock=True)
    orch = DataTrustAgentOrchestrator(llm_adapter=adapter)
    return orch


@pytest.mark.asyncio
async def test_followup_entity_resolution(mock_orchestrator, monkeypatch):
    """
    Test: Lượt 1 nhắc đến FND-SOC-99, lượt 2 dùng đại từ 'nó' ('tại sao nó bị vậy?').
    Hệ thống phải tự giải quyết đại từ và tiếp tục điều tra FND-SOC-99 từ session memory.
    """
    session_id = f"test-sess-followup-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-conv-01"

    fake_finding = {
        "finding_id": "FND-SOC-99",
        "dataset_id": "telemetry",
        "column_name": "battery_soc",
        "rule_id": "CHK-SOC-BOUNDS",
        "severity": "CRITICAL",
        "reason": "battery_soc = 105% vượt mức tối đa 100%",
        "failed_record_count": 3,
        "run_id": run_id,
        "law_ref": "UN ECE R100"
    }

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            pass
        def fetchone(self):
            return fake_finding
        def fetchall(self):
            return [fake_finding]

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    # Turn 1: User explicitly specifies finding FND-SOC-99
    res1 = await mock_orchestrator.chat(
        message="Hãy phân tích nguyên nhân cho finding FND-SOC-99",
        run_id=run_id,
        session_id=session_id
    )
    assert res1["session_id"] == session_id
    assert "FND-SOC-99" in res1["response"]

    # Verify session state recorded active finding
    state = session_manager.get_session_state(session_id)
    assert state.get("active_finding_id") == "FND-SOC-99"

    # Turn 2: User refers to 'nó' without mentioning finding ID
    res2 = await mock_orchestrator.chat(
        message="Tại sao nó lại xảy ra lỗi đó?",
        run_id=run_id,
        session_id=session_id
    )
    # The orchestrator should retain FND-SOC-99 focus
    assert res2["data"]["finding"]["finding_id"] == "FND-SOC-99"
    assert "FND-SOC-99" in res2["response"]


@pytest.mark.asyncio
async def test_ambiguous_question_clarification(mock_orchestrator, monkeypatch):
    """
    Test: Khi run có nhiều hơn 1 finding (ví dụ: FND-TEMP-01 và FND-PHONE-02),
    người dùng hỏi trống không 'tại sao bị lỗi?' -> AI lịch sự đưa ra các lựa chọn
    thay vì tự đoán bừa 1 finding.
    """
    session_id = f"test-sess-ambig-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-conv-02"

    multi_findings = [
        {
            "finding_id": "FND-TEMP-01",
            "dataset_id": "telemetry",
            "column_name": "battery_temp_c",
            "severity": "CRITICAL",
            "reason": "Nhiệt độ pin vượt ngưỡng 85°C",
            "failed_record_count": 8,
            "run_id": run_id
        },
        {
            "finding_id": "FND-PHONE-02",
            "dataset_id": "trips",
            "column_name": "customer_phone",
            "severity": "HIGH",
            "reason": "Số điện thoại khách hàng lộ bản rõ",
            "failed_record_count": 15,
            "run_id": run_id
        }
    ]

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            pass
        def fetchone(self):
            return None
        def fetchall(self):
            return multi_findings

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    # User asks vague root-cause question
    res = await mock_orchestrator.chat(
        message="Tại sao lại bị lỗi vi phạm?",
        run_id=run_id,
        session_id=session_id
    )

    # Must ask for clarification rather than picking one arbitrarily
    assert "available_findings" in res.get("data", {})
    available = res["data"]["available_findings"]
    assert "FND-TEMP-01" in available
    assert "FND-PHONE-02" in available
    assert "Bạn muốn tôi phân tích nguyên nhân" in res["response"]


@pytest.mark.asyncio
async def test_topic_switch_clears_focus(mock_orchestrator):
    """
    Test: Sau khi hỏi về finding, người dùng yêu cầu 'bỏ qua chuyện này đi, sang vấn đề khác'
    -> AI giải phóng active focus và xác nhận chuyển chủ đề.
    """
    session_id = f"test-sess-switch-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-conv-03"

    # Seed session state with an active finding
    session_manager.update_session_state(
        session_id=session_id,
        run_id=run_id,
        updates={
            "active_finding_id": "FND-OLD-01",
            "active_dataset_id": "telemetry",
            "active_column": "battery_temp_c"
        }
    )

    # Verify seed
    state_before = session_manager.get_session_state(session_id)
    assert state_before.get("active_finding_id") == "FND-OLD-01"

    # User triggers topic switch
    res = await mock_orchestrator.chat(
        message="Bỏ qua chuyện này đi, chuyển sang vấn đề khác",
        run_id=run_id,
        session_id=session_id
    )

    assert res["data"].get("status") == "TOPIC_RESET"
    assert "làm mới ngữ cảnh" in res["response"]

    # Verify session focus cleared
    state_after = session_manager.get_session_state(session_id)
    assert state_after.get("active_finding_id") is None
    assert state_after.get("active_column") is None


@pytest.mark.asyncio
async def test_response_length_proportionality(mock_orchestrator):
    """
    Test: Chào hỏi ngắn ('xin chào') nhận được phản hồi ngắn gọn 1-2 câu,
    không dài dòng, không tràn lan số liệu hay bảng biểu.
    """
    session_id = f"test-sess-greeting-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-conv-04"

    res = await mock_orchestrator.chat(
        message="Xin chào bạn!",
        run_id=run_id,
        session_id=session_id
    )

    # Greeting response should be concise
    reply = res["response"]
    assert len(reply) < 350
    assert "Xin chào" in reply
    assert not reply.startswith("**Kết luận:**")


@pytest.mark.asyncio
async def test_no_repetitive_ket_luan_prefix(mock_orchestrator, monkeypatch):
    """
    Test: Các câu hỏi tổng quan và giao tiếp không bị bắt buộc chèn cụm từ '**Kết luận:**'
    ở đầu phản hồi như khuôn mẫu hành chính rập khuôn.
    """
    session_id = f"test-sess-natural-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-conv-05"

    fake_pipeline_run = {
        "run_id": run_id,
        "status": "COMPLETED",
        "scanned_count": 10000,
        "silver_count": 9850,
        "quarantine_count": 150,
        "execution_duration_ms": 1250,
        "started_at": "2026-10-08T10:00:00Z"
    }

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            pass
        def fetchone(self):
            return fake_pipeline_run
        def fetchall(self):
            return []

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    # Overview question
    res_overview = await mock_orchestrator.chat(
        message="Tổng quan lần chạy này thế nào?",
        run_id=run_id,
        session_id=session_id
    )
    # Natural summary, not robotic prefix
    assert not res_overview["response"].startswith("**Kết luận:**")
    assert "Lần chạy `run-test-conv-05`" in res_overview["response"]


def test_insufficient_evidence_handling():
    """
    Test: Khi thiếu bằng chứng hoặc không có quarantine samples,
    confidence_method chuyển thành INSUFFICIENT_EVIDENCE khách quan.
    """
    adapter = UnifiedLLMAdapter(force_mock=True)
    ctx_missing = {
        "finding": {"finding_id": "F-LACKING", "rule_id": "CHK-NULL", "column_name": "temp"},
        "missing_context": ["quarantine_sample", "lineage"],
        "evidence": []
    }

    res = adapter.complete("Chẩn đoán vi phạm F-LACKING", context=ctx_missing)
    payload = json.loads(res["text"])

    assert payload["confidence_method"] == "INSUFFICIENT_EVIDENCE"
