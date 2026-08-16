from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)
HEADERS = {"X-User-Role": "admin"}


def test_projects_endpoint():
    res = client.get("/api/v1/projects", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["project_id"] == "proj-vingroup-pilot"


def test_signals_endpoint():
    res = client.get("/api/v1/signals", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1


def test_incidents_endpoint():
    res = client.get("/api/v1/incidents", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    inc_id = data[0]["incident_id"]

    res_inv = client.post(f"/api/v1/incidents/{inc_id}/investigate?mode=C1", headers=HEADERS)
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert inv_data["mode"] == "C1"


def test_controls_and_authorizations_endpoint():
    payload = {
        "control_id": "ctrl-test-1",
        "rule_type": "range",
        "rule_expression": "battery_soc >= 0",
        "target_table": "vinfast_bms",
        "target_column": "battery_soc"
    }
    res_prop = client.post("/api/v1/controls/propose", json=payload, headers=HEADERS)
    assert res_prop.status_code == 200

    res_auth = client.get("/api/v1/authorizations", headers=HEADERS)
    assert res_auth.status_code == 200


def test_audit_endpoint():
    res = client.get("/api/v1/audit", headers=HEADERS)
    assert res.status_code == 200


def test_summary_endpoint():
    res = client.get("/api/v1/summary", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "projects_count" in data
    assert "provenance" in data
    assert data["active_project_id"] == "proj-vingroup-pilot"


def test_incident_chat_endpoint():
    payload = {"message": "Summarize the root cause of this anomaly."}
    res = client.post("/api/v1/incidents/inc-01/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "incident_id" in data
    assert data["incident_id"] == "inc-01"

