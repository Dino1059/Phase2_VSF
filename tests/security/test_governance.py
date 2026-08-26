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
        ["unapproved_rule_p002", "unapproved_temp_check", "range", "station_temp_c < 80.0", 0.8, "proposed"]
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
            "data": [{"station_temp_c": 25.0}],
            "rules": [{
                "rule_id": "unapproved_rule_p002",
                "rule_type": "range",
                "target_column": "station_temp_c",
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
            table="charging_sessions",
            column="temperature; DROP TABLE users; --",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="charging_sessions",
            column="status /* comment */",
            operator="eq",
            arguments=[1]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="charging_sessions",
            column="status",
            operator="eq",
            arguments=["ACTIVE'; --"]
        )
        compile_rule_spec(spec)

    # 2. Subqueries in RuleSpec or expression parsing
    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="charging_sessions",
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
            table="charging_sessions",
            column="eval('import os')",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="charging_sessions",
            column="script_exec()",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="charging_sessions",
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
    resp_ext = client.post("/api/v1/datasets/upload", files={"file": file_bad_ext}, headers=headers)
    assert resp_ext.status_code == 400
    assert "Invalid file extension" in resp_ext.json()["detail"]

    # 2. Directory traversal path in CSV filename is sanitized safely
    file_traversal = ("../../etc/passwd.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")
    resp_trav = client.post("/api/v1/datasets/upload", files={"file": file_traversal}, headers=headers)
    assert resp_trav.status_code == 200
    assert resp_trav.json()["dataset_key"] == "uploaded_passwd"

    # 3. File size exceeding 50MB -> HTTP 413 Payload Too Large
    large_content = b"x" * (50 * 1024 * 1024 + 1024)
    file_large = ("large_file.csv", io.BytesIO(large_content), "text/csv")
    resp_large = client.post("/api/v1/datasets/upload", files={"file": file_large}, headers=headers)
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


from src.reliability.governance.preventive_controls import PreventiveControlManager


def test_unified_governance_lifecycle():
    """
    Test Wave 6: Unified proposal, review, compilation, sandbox validation, authorization token generation, and execution.
    """
    mgr = PreventiveControlManager()

    # 1. Proposal
    prop = mgr.propose_control(
        control_id="ctrl-wave6-01",
        rule_type="range",
        rule_expression="battery_soc >= 0 AND battery_soc <= 100",
        target_table="ev_telemetry",
        target_column="battery_soc"
    )
    assert prop.status == "PROPOSED"
    assert prop.version == 1

    # 2. HITL Review
    rev = mgr.review_control("ctrl-wave6-01", reviewer="data_steward_1", approved=True)
    assert rev.status == "REVIEWED"
    assert rev.reviewed_by == "data_steward_1"

    # 3. Compilation
    comp = mgr.compile_control("ctrl-wave6-01")
    assert comp.status == "COMPILED"
    assert "WHERE NOT" in comp.compiled_expression

    # 4. Sandbox Validation
    sandbox = mgr.sandbox_validate_control("ctrl-wave6-01")
    assert sandbox.status == "SANDBOX_VALIDATED"
    assert sandbox.sandbox_passed is True

    # 5. Authorization Token Generation
    auth = mgr.generate_authorization("ctrl-wave6-01", actor="data_steward_1", expires_in_seconds=3600)
    assert auth.status == "VALID"
    assert auth.authorization_id.startswith("auth-")
    assert auth.version == 1

    # 6. Execution with Authorization ID
    res = mgr.execute_control("ctrl-wave6-01", authorization_id=auth.authorization_id, dry_run=False)
    assert res["status"] == "EXECUTED"
    assert res["authorization_id"] == auth.authorization_id


def test_execution_requires_authorization_id_and_rejects_missing():
    """
    Test Wave 6: Execution fails if authorization_id is missing.
    """
    mgr = PreventiveControlManager()
    mgr.propose_control(
        control_id="ctrl-wave6-02",
        rule_type="range",
        rule_expression="station_temp_c < 80.0",
        target_table="charging_sessions",
        target_column="station_temp_c"
    )

    with pytest.raises(PermissionError) as exc_info:
        mgr.execute_control("ctrl-wave6-02", authorization_id=None)
    assert "Authorization ID is required for execution" in str(exc_info.value)


def test_strict_exact_version_matching_and_rule_modification_rejection():
    """
    Test Wave 6: Enforce strict exact-version matching (rejecting modified rules or mismatched versions).
    """
    mgr = PreventiveControlManager()
    mgr.propose_control(
        control_id="ctrl-wave6-03",
        rule_type="range",
        rule_expression="duration_mins <= 1.0",
        target_table="charging_sessions",
        target_column="duration_mins"
    )
    auth = mgr.generate_authorization("ctrl-wave6-03", actor="data_steward_1")

    # Modifying control rule expression increments version to 2
    mgr.update_control_rule("ctrl-wave6-03", new_expression="duration_mins <= 0.9")

    # Attempting to execute updated control (v2) with token issued for v1 fails
    with pytest.raises(PermissionError) as exc_info:
        mgr.execute_control("ctrl-wave6-03", authorization_id=auth.authorization_id)
    assert "Version mismatch" in str(exc_info.value)


def test_expired_and_revoked_tokens_rejected():
    """
    Test Wave 6: Reject execution using expired or revoked authorization tokens.
    """
    mgr = PreventiveControlManager()
    mgr.propose_control(
        control_id="ctrl-wave6-04",
        rule_type="range",
        rule_expression="sentiment >= 1.0",
        target_table="trips",
        target_column="sentiment"
    )
    # Generate expired token
    auth_exp = mgr.generate_authorization("ctrl-wave6-04", actor="data_steward_1", expires_in_seconds=-10)

    with pytest.raises(PermissionError) as exc_info:
        mgr.execute_control("ctrl-wave6-04", authorization_id=auth_exp.authorization_id)
    assert "expired" in str(exc_info.value).lower()

    # Generate valid token and then revoke it
    auth_rev = mgr.generate_authorization("ctrl-wave6-04", actor="data_steward_1", expires_in_seconds=3600)
    mgr.revoke_authorization(auth_rev.authorization_id)

    with pytest.raises(PermissionError) as exc_info2:
        mgr.execute_control("ctrl-wave6-04", authorization_id=auth_rev.authorization_id)
    assert "REVOKED" in str(exc_info2.value) or "not valid" in str(exc_info2.value).lower() or "is revoked" in str(exc_info2.value).lower()


def test_ai_path_direct_mutation_without_hitl_approval_blocked():
    """
    Test Wave 6: Ensure no AI path can directly mutate production state without HITL approval and signed authorization.
    """
    mgr = PreventiveControlManager()
    mgr.propose_control(
        control_id="ctrl-wave6-05",
        rule_type="range",
        rule_expression="fare_amount > 0",
        target_table="trips",
        target_column="fare_amount"
    )

    # Autonomous self-review by AI is rejected
    with pytest.raises(PermissionError) as exc_info:
        mgr.review_control("ctrl-wave6-05", reviewer="autonomous_agent", approved=True)
    assert "HITL human steward review is required" in str(exc_info.value)


def test_authorizations_api_endpoints(client):
    """
    Test Wave 6: API endpoints for authorizations route.
    """
    headers = {"X-User-Role": "Admin"}

    # 1. Pipeline endpoint
    pipeline_payload = {
        "control_id": "ctrl-api-01",
        "rule_type": "range",
        "rule_expression": "power_kw >= 200.0",
        "target_table": "charging_sessions",
        "target_column": "power_kw",
        "reviewer": "data_steward_1",
        "actor": "data_steward_1",
        "dry_run": False
    }
    resp = client.post("/api/v1/authorizations/pipeline", json=pipeline_payload, headers=headers)
    assert resp.status_code == 200
    res_json = resp.json()
    assert "authorization" in res_json
    auth_id = res_json["authorization"]["authorization_id"]
    assert auth_id.startswith("auth-")

    # 2. List authorizations
    resp_list = client.get("/api/v1/authorizations", headers=headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 1

    # 3. Verify authorization
    resp_verify = client.post("/api/v1/authorizations/verify", json={"authorization_id": auth_id, "control_id": "ctrl-api-01"}, headers=headers)
    assert resp_verify.status_code == 200
    assert resp_verify.json()["is_valid"] is True

    # 4. Execute without authorization_id -> 403 Forbidden
    resp_exec_no_auth = client.post("/api/v1/authorizations/execute", json={"control_id": "ctrl-api-01"}, headers=headers)
    assert resp_exec_no_auth.status_code == 403
    assert "Authorization ID is required" in resp_exec_no_auth.json()["detail"]


