import pytest
from fastapi.testclient import TestClient
from src.tools.rule_executor import RuleExecutorTool, RuleSpec
from src.services.security import validate_webhook_url
from src.agents.baselines import BaselineA1, BaselineA2, BenchmarkCase
from src.middleware.auth import create_access_token, JWT_SECRET, JWT_ALGORITHM
from src.services.websocket import websocket_manager
from src.main import app


def test_red_team_prompt_injection_in_rule_spec():
    executor = RuleExecutorTool()
    malicious_spec = RuleSpec(
        table="vgreen_telemetry",
        column="temperature; DROP TABLE vgreen_telemetry; --",
        operator="gt",
        arguments=[100],
    )
    # Compiler must reject multiple statements / SQL injection
    with pytest.raises(Exception):
        executor.compile_rule(malicious_spec)


def test_red_team_ssrf_webhook_blocked():
    assert validate_webhook_url("http://127.0.0.1:8000/internal") is False
    assert validate_webhook_url("http://169.254.169.254/latest/meta-data") is False
    assert validate_webhook_url("http://10.0.0.1/admin") is False
    assert validate_webhook_url("https://8.8.8.8/webhook") is True


@pytest.mark.asyncio
async def test_red_team_missing_data_context():
    a1 = BaselineA1()
    # Non-existent table and missing context
    case = BenchmarkCase(case_id="case_missing", dataset_key="non_existent_table_123")
    result = await a1.run(case)

    assert result.tier == "A1"
    # Agent must handle non-existent table gracefully without crashing
    assert isinstance(result.predictions, set)
    assert isinstance(result.evidence_refs, list)


@pytest.mark.asyncio
async def test_red_team_a2_verifier_filters_unsupported():
    a2 = BaselineA2()
    case = BenchmarkCase(case_id="case_redteam", dataset_key="vgreen_telemetry")
    result = await a2.run(case)

    assert result.tier == "A2"
    assert any(t.get("step") == "a2_verifier_audit" for t in result.tool_trace)
    assert result.cost_tokens > 0


def test_red_team_jwt_authentication_and_header_tampering():
    client = TestClient(app)

    # 1. Access protected route without token must be rejected with HTTP 401
    resp_no_token = client.get("/api/v1/me")
    assert resp_no_token.status_code == 401

    # 2. Forged JWT token signed with wrong key must be rejected with HTTP 401
    import jwt as pyjwt
    forged_token = pyjwt.encode({"sub": "attacker", "role": "Admin"}, "wrong_secret_key", algorithm=JWT_ALGORITHM)
    resp_forged = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp_forged.status_code == 401

    # 3. Client header X-User-Role: Admin with Viewer JWT token must NOT grant Admin authority
    viewer_token = create_access_token({"sub": "viewer@datatrust.os", "user_id": "usr_viewer_01", "role": "Viewer"})
    resp_tampered = client.post(
        "/api/v1/reset",
        headers={"Authorization": f"Bearer {viewer_token}", "X-User-Role": "Admin"},
    )
    assert resp_tampered.status_code == 403
    assert "Forbidden" in resp_tampered.json()["detail"]


def test_red_team_unauthenticated_websocket_connection():
    client = TestClient(app)

    # 1. Connection without token fails / rejected
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid_forged_token_999") as websocket:
            websocket.receive_text()

    # 2. Connection with valid token succeeds and joins scoped rooms
    token = create_access_token({"sub": "admin@datatrust.os", "user_id": "usr_admin_01", "role": "Admin"})
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json({"type": "subscribe", "room": "project:proj_redteam_01"})
        data = websocket.receive_json()
        assert data["type"] == "subscribed"
        assert data["room"] == "project:proj_redteam_01"

        websocket.send_json({"type": "subscribe", "room": "incident:inc_redteam_01"})
        data_inc = websocket.receive_json()
        assert data_inc["type"] == "subscribed"
        assert data_inc["room"] == "incident:inc_redteam_01"
