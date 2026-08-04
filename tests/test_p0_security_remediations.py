import io
import pytest
from src.tools.rule_executor import RuleSpec, compile_rule_spec, RuleExecutorTool
from src.services.security import validate_webhook_url


def test_p0_04_rule_spec_ast_compilation():
    # Test valid RuleSpec compilation
    spec = RuleSpec(
        table="vgreen_telemetry",
        column="temperature",
        operator="between",
        arguments=[-10, 85],
        severity="error"
    )
    sql = compile_rule_spec(spec)
    assert sql == "WHERE NOT (temperature BETWEEN ? AND ?)"

    # Test gt operator
    spec_gt = RuleSpec(
        table="xanhsm_trips",
        column="fare_vnd",
        operator="gt",
        arguments=[0]
    )
    assert compile_rule_spec(spec_gt) == "WHERE NOT (fare_vnd > ?)"

    # Test not_null operator
    spec_null = RuleSpec(
        table="vinfast_bms",
        column="battery_soc",
        operator="not_null",
        arguments=[]
    )
    assert compile_rule_spec(spec_null) == "WHERE NOT (battery_soc IS NOT NULL)"


def test_p0_04_sql_injection_rejection():
    # Invalid column identifier containing comment or injection
    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="temp; DROP TABLE users; --",
            operator="gt",
            arguments=[0]
        )
        compile_rule_spec(spec)

    # Disallow SQL comment in argument string
    with pytest.raises(ValueError):
        spec = RuleSpec(
            table="vgreen_telemetry",
            column="status",
            operator="eq",
            arguments=["ACTIVE'; --"]
        )
        compile_rule_spec(spec)

    # Disallow SELECT subquery
    with pytest.raises(ValueError):
        tool = RuleExecutorTool()
        tool._parse_rule_spec("SELECT * FROM users")


def test_p0_05_upload_security_validation():
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app, headers={"X-User-Role": "Admin"})

    # 1. Reject forbidden extension (.exe)
    file_bad_ext = ("test.exe", io.BytesIO(b"binary data"), "application/octet-stream")
    resp = client.post("/api/v1/dataset/upload", files={"file": file_bad_ext})
    assert resp.status_code == 400
    assert "Invalid file extension" in resp.json()["detail"]

    # 2. Directory traversal in filename should be sanitized
    file_traversal = ("../../etc/passwd.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")
    resp_trav = client.post("/api/v1/dataset/upload", files={"file": file_traversal})
    assert resp_trav.status_code == 200
    assert resp_trav.json()["dataset_key"] == "uploaded_passwd"

    # 3. Valid CSV upload
    file_valid = ("valid_data.csv", io.BytesIO(b"x,y\n10,20\n"), "text/csv")
    resp_val = client.post("/api/v1/dataset/upload", files={"file": file_valid})
    assert resp_val.status_code == 200
    assert resp_val.json()["status"] == "uploaded"


def test_p0_06_ssrf_defense():
    # Reject loopback IP / localhost
    assert validate_webhook_url("http://127.0.0.1/webhook") is False
    assert validate_webhook_url("http://localhost:8000/webhook") is False
    assert validate_webhook_url("http://[::1]/webhook") is False

    # Reject private IP ranges (10.x, 172.16.x, 192.168.x)
    assert validate_webhook_url("http://10.0.0.1/notify") is False
    assert validate_webhook_url("http://172.16.0.5/notify") is False
    assert validate_webhook_url("http://192.168.1.100/notify") is False

    # Reject AWS Metadata IP (169.254.169.254)
    assert validate_webhook_url("http://169.254.169.254/latest/meta-data/") is False

    # Reject non-http/https schemes
    assert validate_webhook_url("ftp://example.com/webhook") is False
    assert validate_webhook_url("file:///etc/passwd") is False

    # Accept valid public HTTPS URLs
    assert validate_webhook_url("https://hooks.slack.com/services/test/webhook") is True
