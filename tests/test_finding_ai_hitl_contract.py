from fastapi.testclient import TestClient

from backend.ai.services.finding_analysis_store import FindingAnalysisStore
from backend.ai.services.llm_adapter import UnifiedLLMAdapter
from backend.api import main as api_main


def _finding_detail(_finding_id: str):
    return {
        "finding_id": "F-001",
        "run_id": "RUN-001",
        "dataset_id": "trips",
        "rule_id": "RULE-PII-01",
        "policy_id": "POL-UNKNOWN",
        "policy_name": "PII policy",
        "law_ref": "Luật 91/2025/QH15",
        "column_name": "customer_phone",
        "reason": "Clear-text phone 0912345678 was detected",
        "failed_record_count": 3,
        "run_status": "FAILED",
        "sample_records": [
            {
                "quarantine_id": "Q-001",
                "source_row_pk": "TRIP-001",
                "raw_record_json": {"customer_phone": "0912345678"},
                "lineage_hash": "abc123",
            }
        ],
        "rule_definition": {"rule_id": "RULE-PII-01", "operation_id": "mask_phone"},
    }


def test_finding_ai_contract_and_strict_hitl(monkeypatch, tmp_path):
    monkeypatch.setattr(api_main, "get_finding_detail", _finding_detail)
    monkeypatch.setattr(api_main.orchestrator.llm_adapter, "force_mock", True)
    monkeypatch.setattr(
        api_main,
        "finding_analysis_store",
        FindingAnalysisStore(str(tmp_path / "analyses.json")),
    )
    client = TestClient(api_main.app)

    created = client.post("/api/findings/F-001/ai-explanation")
    assert created.status_code == 200
    analysis = created.json()
    assert analysis["finding_id"] == "F-001"
    assert analysis["remediation"]["status"] == "suggested"
    assert analysis["confidence"] < 1
    assert "lineage" in analysis["missing_context"]
    assert "policy" in analysis["missing_context"]
    assert "0912345678" not in str(analysis)

    fetched = client.get("/api/findings/F-001/ai-analysis")
    assert fetched.status_code == 200
    assert fetched.json()["analysis_id"] == analysis["analysis_id"]

    assert client.post("/api/findings/F-001/remediation/approve").status_code == 403
    assert client.post(
        "/api/findings/F-001/remediation/approve",
        headers={"X-User-Role": "AUDITOR", "X-User": "auditor@example.com"},
    ).status_code == 403

    approved = client.post(
        "/api/findings/F-001/remediation/approve",
        headers={"X-User-Role": "ADMIN", "X-User": "admin@example.com"},
        json={"comment": "Reviewed scope"},
    )
    assert approved.status_code == 200
    assert approved.json()["remediation"]["status"] == "pending_execution"
    assert approved.json()["remediation"]["decided_by"] == "admin@example.com"

    retry = client.post(
        "/api/findings/F-001/remediation/approve",
        headers={"X-User-Role": "ADMIN", "X-User": "admin@example.com"},
    )
    assert retry.status_code == 200
    assert retry.json()["audit_events"] == approved.json()["audit_events"]

    conflict = client.post(
        "/api/findings/F-001/remediation/reject",
        headers={"X-User-Role": "ADMIN", "X-User": "admin@example.com"},
    )
    assert conflict.status_code == 409


def test_ai_rule_generation_is_disabled():
    client = TestClient(api_main.app)
    assert client.post("/api/ai/propose?policy_id=P&dataset_id=D").status_code == 410
    assert client.post(
        "/api/rules/proposal-1/approve",
        json={"actor_name": "Admin", "actor_role": "ADMIN"},
    ).status_code == 410


def test_mock_provider_receives_only_sanitized_context(monkeypatch):
    adapter = UnifiedLLMAdapter(force_mock=True)
    captured = {}

    def fake_mock(prompt, system_instruction, context):
        captured["context"] = context
        return "safe", 1

    monkeypatch.setattr(adapter, "_generate_deterministic_mock", fake_mock)
    adapter.complete(
        "Review customer phone",
        context={
            "customer": {"phone": ["0912345678"], "email": "person@example.com"},
            "reason": "Seen at 21.028511, 105.854444",
        },
    )

    serialized = str(captured["context"])
    assert "0912345678" not in serialized
    assert "person@example.com" not in serialized
    assert "21.028511" not in serialized


def test_finding_analysis_uses_model_generated_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(api_main, "get_finding_detail", _finding_detail)
    monkeypatch.setattr(
        api_main,
        "finding_analysis_store",
        FindingAnalysisStore(str(tmp_path / "analyses.json")),
    )

    def fake_complete(*_args, **_kwargs):
        return {
            "provider": "openai",
            "model": "test-model",
            "text": """{
                "explanation": "Ba bản ghi có dấu hiệu không nhất quán và cần được kiểm tra.",
                "root_cause": "Dữ liệu đầu vào có thể chưa được chuẩn hóa.",
                "confidence": 0.78,
                "issues": [{
                    "field": "customer_phone",
                    "issue": "Số điện thoại đang ở dạng văn bản rõ",
                    "observed_condition": "Giá trị chưa được che",
                    "likely_cause": "Bước masking chưa được áp dụng",
                    "suggested_action": "Áp dụng mask_phone rồi kiểm tra lại",
                    "evidence_reference": "Q-001"
                }],
                "remediation_action": "Kiểm tra và chuẩn hóa dữ liệu bị ảnh hưởng",
                "remediation_rationale": "Hãy đối chiếu với nguồn trước khi gửi sang luồng thực thi."
            }""",
        }

    monkeypatch.setattr(api_main.orchestrator.llm_adapter, "complete", fake_complete)
    response = TestClient(api_main.app).post("/api/findings/F-001/ai-explanation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["explanation"].startswith("Ba bản ghi")
    assert payload["root_cause"] == "Dữ liệu đầu vào có thể chưa được chuẩn hóa."
    assert payload["confidence"] == 0.78
    assert payload["issues"][0]["field"] == "customer_phone"
    assert payload["issues"][0]["suggested_action"].startswith("Áp dụng mask_phone")
    assert payload["remediation"]["action"] == "Kiểm tra và chuẩn hóa dữ liệu bị ảnh hưởng"
    assert payload["remediation"]["rationale"].startswith("Hãy đối chiếu")
    assert payload["remediation"]["scope"]["affected_records"] == 3


def test_openai_failure_is_not_presented_as_ai_analysis(monkeypatch, tmp_path):
    monkeypatch.setattr(api_main, "get_finding_detail", _finding_detail)
    monkeypatch.setattr(
        api_main,
        "finding_analysis_store",
        FindingAnalysisStore(str(tmp_path / "analyses.json")),
    )
    monkeypatch.setattr(
        api_main.orchestrator.llm_adapter,
        "complete",
        lambda *_args, **_kwargs: {
            "provider": "openai_error",
            "text": "",
            "error": "test failure",
        },
    )

    response = TestClient(api_main.app).post("/api/findings/F-001/ai-explanation")
    assert response.status_code == 503
    assert "OpenAI" in response.json()["detail"]


def test_auditor_can_trigger_pipeline_run(monkeypatch):
    """Kiểm tra vai trò AUDITOR được phép kích hoạt lượt chạy kiểm tra qua /api/runs (không bị 403)."""
    from unittest.mock import MagicMock
    import io

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock database connection
    import database.profiler_engine as profiler_engine
    monkeypatch.setattr(profiler_engine, "get_db_connection", lambda: mock_conn)

    # Mock Airflow urlopen
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"execution_date": "2026-10-09T07:30:00Z"}'
    mock_resp.__enter__.return_value = mock_resp
    monkeypatch.setattr(api_main, "urlopen", lambda *_args, **_kwargs: mock_resp)

    client = TestClient(api_main.app)
    response = client.post(
        "/api/runs",
        headers={"X-User-Role": "AUDITOR", "X-User": "DataTrust Auditor"},
        json={"dataset_id": "ride_hailing_xanh_sm_trips", "collect_evidence": True, "generate_lineage": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RUNNING"
    assert "run_id" in data

