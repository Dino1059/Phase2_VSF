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


@pytest.mark.asyncio
async def test_warning_inquiry_avoids_finding_ambiguity_clarification(mock_orchestrator, monkeypatch):
    """
    Test: Người dùng hỏi 'tôi không biết 200 warning vi phạm gì' trong lần chạy có 5 Finding.
    AI phải trả lời về warning records, KHÔNG được rơi vào mẫu câu Ambiguity của Finding.
    Đồng thời kiểm tra COUNT(*) độc lập hoạt động đúng khi có nhiều hơn 10 nhóm cảnh báo.
    """
    session_id = f"test-sess-warn-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-warn-01"

    # Mock 12 groups to verify independent COUNT(*) is not truncated by LIMIT 10
    mock_groups = [
        {"warning_type": f"DRIFT_L{i}", "signal_lane": "LANE_A", "signal_layer": "L2", "warning_reason": f"Drift {i}", "count": 15}
        for i in range(12)
    ]
    # 12 * 15 = 180 + 20 = 200

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            self.last_query = query
        def fetchone(self):
            if "pipeline_runs" in self.last_query:
                return {"warning_count": 200}
            if "COUNT(*)" in self.last_query:
                return {"total_records": 200}
            return None
        def fetchall(self):
            if "GROUP BY" in self.last_query:
                return mock_groups[:10]  # LIMIT 10
            if "LIMIT 3" in self.last_query:
                return [
                    {
                        "warning_id": "w-01",
                        "source_row_pk": "pk-1",
                        "signal_lane": "LANE_A",
                        "signal_layer": "L2",
                        "warning_type": "DRIFT_L0",
                        "warning_reason": "Drift 0",
                        "score_or_zvalue": 2.5,
                        "redacted_record_json": {"trip_id": "pk-1", "trip_distance_km": 10.5}
                    }
                ]
            return []

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    res = await mock_orchestrator.chat(
        message="tôi không biết 200 warning vi phạm gì",
        run_id=run_id,
        session_id=session_id
    )

    # 1. Must NOT trigger ambiguity question for audit.findings
    assert "Bạn muốn tôi phân tích nguyên nhân" not in res["response"]
    assert "vấn đề kiểm toán" not in res["response"]

    # 2. Must respond about Warning records
    assert res["data"]["intent"] == "WARNING_INQUIRY"
    assert res["data"]["actual_records_count"] == 200
    assert res["data"]["pipeline_warning_count"] == 200
    assert res["data"]["is_reconciled"] is True
    assert "200" in res["response"]
    assert "cảnh báo" in res["response"].lower() or "warning" in res["response"].lower()

    # The response must adapt to the question instead of reusing the former
    # four-section, run-specific template.
    assert "58 Warning" not in res["response"]
    assert "### 1." not in res["response"]
    assert "### 2." not in res["response"]
    assert "hoàn toàn hợp lệ" not in res["response"].lower()


@pytest.mark.asyncio
async def test_warning_inquiry_with_discrepancy(mock_orchestrator, monkeypatch):
    """
    Test: Khi pipeline_runs báo 200 warning nhưng warning.records chỉ có 50 bản ghi,
    AI phát hiện độ lệch và thông báo minh bạch trong phản hồi.
    """
    session_id = f"test-sess-warn-discrep-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-warn-02"

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            self.last_query = query
        def fetchone(self):
            if "pipeline_runs" in self.last_query:
                return {"warning_count": 200}
            if "COUNT(*)" in self.last_query:
                return {"total_records": 50}
            return None
        def fetchall(self):
            return []

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    res = await mock_orchestrator.chat(
        message="tại sao có 200 warning?",
        run_id=run_id,
        session_id=session_id
    )

    assert res["data"]["intent"] == "WARNING_INQUIRY"
    assert res["data"]["is_reconciled"] is False
    assert res["data"]["pipeline_warning_count"] == 200
    assert res["data"]["actual_records_count"] == 50
    assert "đối soát" in res["response"].lower() or "độ lệch" in res["response"].lower()


@pytest.mark.asyncio
async def test_warning_inquiry_db_resilience(mock_orchestrator, monkeypatch):
    """
    Test: Khi kết nối DB gặp sự cố, hệ thống không bị crash 500
    mà trả về thông báo lỗi kết nối an toàn.
    """
    session_id = f"test-sess-warn-err-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-warn-03"

    def faulty_conn():
        raise ConnectionError("PostgreSQL cluster unavailable")

    monkeypatch.setattr("database.profiler_engine.get_db_connection", faulty_conn)

    res = await mock_orchestrator.chat(
        message="giải thích các bản ghi warning",
        run_id=run_id,
        session_id=session_id
    )

    assert res["data"]["status"] == "DB_CONNECTION_ERROR"
    assert "gián đoạn kết nối" in res["response"] or "chưa thể truy xuất" in res["response"]


@pytest.mark.asyncio
async def test_warning_inquiry_zero_warnings(mock_orchestrator, monkeypatch):
    """
    Test: Khi lần chạy có 0 warning, AI trả lời xác nhận không có cảnh báo nào.
    """
    session_id = f"test-sess-warn-zero-{uuid.uuid4().hex[:6]}"
    run_id = "run-test-warn-04"

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            self.last_query = query
        def fetchone(self):
            if "pipeline_runs" in self.last_query:
                return {"warning_count": 0}
            if "COUNT(*)" in self.last_query:
                return {"total_records": 0}
            return None
        def fetchall(self):
            return []

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    res = await mock_orchestrator.chat(
        message="lần chạy này có cảnh báo gì không?",
        run_id=run_id,
        session_id=session_id
    )

    assert res["data"]["warning_count"] == 0
    assert "không ghi nhận bất kỳ bản ghi cảnh báo nào" in res["response"]
