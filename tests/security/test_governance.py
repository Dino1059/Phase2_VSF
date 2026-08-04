import io
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.db.connection import get_db
from src.tools.rule_executor import RuleSpec, compile_rule_spec, RuleExecutorTool
from src.services.security import validate_webhook_url


@pytest.fixture
def client():
    return TestClient(app)


def test_p0_02_executing_unapproved_rules_denied(client):
    """Test P0-02: Executing unapproved rules returns HTTP 403 Forbidden with 'Rule execution denied: Rule is not approved by HITL'."""
    db = get_db()
    # Ensure clean state for unapproved_rule_p002
    db.execute("DELETE FROM quality_rules WHERE id = 'unapproved_rule_p002'")
    # Insert an unapproved rule with status 'proposed'
    db.execute(
        "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES (?, ?, ?, ?, ?, ?)",
        ["unapproved_rule_p002", "unapproved_temp_check", "range", "temperature_celsius < 80.0", 0.8, "proposed"]
    )

    # 1. Test execution endpoint /api/v1/executions
    resp = client.post(
        "/api/v1/executions",
        json={"rule_id": "unapproved_rule_p002"},
        headers={"X-User-Role": "Admin"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Rule execution denied: Rule is not approved by HITL"

    # 2. Test HITL execution endpoint /api/v1/hitl/execute/unapproved_rule_p002
    resp_hitl = client.post(
        "/api/v1/hitl/execute/unapproved_rule_p002",
        headers={"X-User-Role": "Admin"}
    )
    assert resp_hitl.status_code == 403
    assert resp_hitl.json()["detail"] == "Rule execution denied: Rule is not approved by HITL"

    # 3. Test HITL execution endpoint /api/v1/hitl/execute with JSON payload
    resp_hitl_json = client.post(
        "/api/v1/hitl/execute",
        json={"rule_id": "unapproved_rule_p002"},
        headers={"X-User-Role": "Admin"}
    )
    assert resp_hitl_json.status_code == 403
    assert resp_hitl_json.json()["detail"] == "Rule execution denied: Rule is not approved by HITL"

    # 4. Test transform execution endpoint /api/v1/executions/transform with unapproved rule
    resp_trans = client.post(
        "/api/v1/executions/transform",
        json={
            "data": [{"temperature_celsius": 25.0}],
            "rules": [{
                "rule_id": "unapproved_rule_p002",
                "rule_type": "range",
                "target_column": "temperature_celsius",
                "action": "QUARANTINE"
            }]
        },
        headers={"X-User-Role": "Admin"}
    )
    assert resp_trans.status_code == 403
    assert resp_trans.json()["detail"] == "Rule execution denied: Rule is not approved by HITL"


def test_p0_03_auth_header_and_role_validation(client):
    """Test P0-03: Accessing protected endpoints without auth header returns HTTP 401 Unauthorized; invalid role header returns HTTP 403 Forbidden."""
    protected_endpoints = [
        ("POST", "/api/v1/dataset/upload"),
        ("POST", "/api/v1/schedules"),
        ("POST", "/api/v1/rules/propose"),
        ("POST", "/api/v1/anomalies/detect"),
    ]

    # 1. Missing auth/role header -> HTTP 401 Unauthorized
    for method, endpoint in protected_endpoints:
        if method == "POST":
            resp = client.post(endpoint)
        else:
            resp = client.get(endpoint)
        assert resp.status_code == 401, f"Expected 401 for {method} {endpoint} without auth headers"
        assert "Unauthorized" in resp.json()["detail"]

    # 2. Invalid role header -> HTTP 403 Forbidden
    invalid_headers = [
        {"X-User-Role": "InvalidRole"},
        {"X-User-Role": "SuperUser"},
        {"Authorization": "Bearer UnknownRole"},
    ]
    for headers in invalid_headers:
        resp = client.post("/api/v1/rules/propose", json={"dataset_name": "test"}, headers=headers)
        assert resp.status_code == 403, f"Expected 403 for headers {headers}"
        assert "Forbidden" in resp.json()["detail"] or "invalid" in resp.json()["detail"].lower()


def test_p0_04_sql_injection_compiler_rejection():
    """Test P0-04: Submitting raw SQL comments (-- , /*), subqueries, or injected function strings into RuleSpec compiler raises validation error."""
    # 1. SQL Comments (-- and /* */)
    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="temperature; DROP TABLE users; --",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="status /* comment */",
            operator="eq",
            arguments=[1]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="status",
            operator="eq",
            arguments=["ACTIVE'; --"]
        )
        compile_rule_spec(spec)

    # 2. Subqueries in RuleSpec or expression parsing
    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="(SELECT id FROM users)",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        tool = RuleExecutorTool()
        tool._parse_rule_spec("SELECT * FROM users")

    with pytest.raises(ValueError):
        tool = RuleExecutorTool()
        tool._parse_rule_spec("UNION SELECT 1, 2, 3")

    # 3. Injected function strings
    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="eval('import os')",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="script_exec()",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="exec(rm_rf)",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)


def test_p0_05_file_upload_security_validation(client):
    """Test P0-05: Uploading files with directory traversal paths (../malicious.csv) or exceeding 50MB returns HTTP 400 / 413."""
    headers = {"X-User-Role": "Admin"}

    # 1. Reject forbidden extension (.exe, .sh) -> HTTP 400
    file_bad_ext = ("../malicious.exe", io.BytesIO(b"binary payload"), "application/octet-stream")
    resp_ext = client.post("/api/v1/dataset/upload", files={"file": file_bad_ext}, headers=headers)
    assert resp_ext.status_code == 400
    assert "Invalid file extension" in resp_ext.json()["detail"]

    # 2. Directory traversal path in CSV filename is sanitized safely
    file_traversal = ("../../etc/passwd.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")
    resp_trav = client.post("/api/v1/dataset/upload", files={"file": file_traversal}, headers=headers)
    assert resp_trav.status_code == 200
    assert resp_trav.json()["dataset_key"] == "uploaded_passwd"

    # 3. File size exceeding 50MB -> HTTP 413 Payload Too Large
    large_content = b"x" * (50 * 1024 * 1024 + 1024)
    file_large = ("large_file.csv", io.BytesIO(large_content), "text/csv")
    resp_large = client.post("/api/v1/dataset/upload", files={"file": file_large}, headers=headers)
    assert resp_large.status_code == 413
    assert "File size exceeds maximum allowed limit of 50 MB." in resp_large.json()["detail"]


def test_p0_06_ssrf_private_ip_webhook_validation():
    """Test P0-06: Dispatching webhooks to private IP ranges (10.0.0.1, 127.0.0.1, 169.254.169.254) returns False from validate_webhook_url."""
    # Private IP ranges explicitly specified in P0-06
    assert validate_webhook_url("http://10.0.0.1/notify") is False
    assert validate_webhook_url("http://127.0.0.1/webhook") is False
    assert validate_webhook_url("http://169.254.169.254/latest/meta-data/") is False

    # Additional private / loopback addresses
    assert validate_webhook_url("http://localhost:8000/webhook") is False
    assert validate_webhook_url("http://192.168.1.1/webhook") is False
    assert validate_webhook_url("http://172.16.0.1/webhook") is False
    assert validate_webhook_url("http://[::1]/webhook") is False

    # Non-http schemes
    assert validate_webhook_url("ftp://example.com/webhook") is False
    assert validate_webhook_url("file:///etc/passwd") is False

    # Valid public HTTPS URL
    assert validate_webhook_url("https://hooks.slack.com/services/test/webhook") is True
