import io
import pytest
from fastapi.testclient import TestClient
from src.tools.rule_executor import RuleSpec, compile_rule_spec, RuleExecutorTool
from src.services.security import validate_webhook_url
from src.middleware.auth import create_access_token, decode_access_token
from src.services.websocket import websocket_manager
from src.main import app


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
    token = create_access_token({"sub": "admin@datatrust.os", "user_id": "usr_admin_01", "role": "Admin"})
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

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

    # Accept valid public HTTPS URLs (mock DNS so CI/offline is deterministic)
    import socket
    from unittest.mock import patch
    fake = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0))]
    with patch("src.services.security.socket.getaddrinfo", return_value=fake):
        assert validate_webhook_url("https://hooks.slack.com/services/test/webhook") is True


def test_p0_signed_jwt_authentication_and_server_role_resolution():
    client = TestClient(app)

    # 1. Login with credentials returns signed JWT token with server-resolved role
    resp_login = client.post("/api/v1/auth/login", json={"username": "steward", "password": "password123"})
    assert resp_login.status_code == 200
    login_data = resp_login.json()
    assert "access_token" in login_data
    assert login_data["role"] == "Steward"
    assert login_data["user"] == "steward@datatrust.os"

    # Decode and verify token
    payload = decode_access_token(login_data["access_token"])
    assert payload is not None
    assert payload["role"] == "Steward"
    assert payload["sub"] == "steward@datatrust.os"

    # 2. Call /auth/me with valid Bearer token returns server-resolved user info and permissions
    token = login_data["access_token"]
    resp_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["role"] == "Steward"
    assert me_data["username"] == "steward@datatrust.os"
    assert "execute_transform" in me_data["permissions"]

    # 3. Call /auth/me without token returns HTTP 401
    resp_unauth = client.get("/api/v1/auth/me")
    assert resp_unauth.status_code == 401


def test_p0_websocket_token_authenticated_scoped_rooms():
    client = TestClient(app)

    # Generate token for user
    token = create_access_token({"sub": "steward@datatrust.os", "user_id": "usr_steward_01", "role": "Steward"})

    # Connect to WebSocket with token
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        # Join project, incident, user rooms
        rooms_to_test = ["project:proj_99", "incident:inc_88", "user:usr_steward_01"]
        for room in rooms_to_test:
            websocket.send_json({"type": "subscribe", "room": room})
            res = websocket.receive_json()
            assert res["type"] == "subscribed"
            assert res["room"] == room

        # Unsubscribe test
        websocket.send_json({"type": "unsubscribe", "room": "project:proj_99"})
        res_unsub = websocket.receive_json()
        assert res_unsub["type"] == "unsubscribed"
        assert res_unsub["room"] == "project:proj_99"
