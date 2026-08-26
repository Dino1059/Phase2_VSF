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
    from src.db.connection import get_db
    db = get_db()
    db.execute("DELETE FROM quarantine WHERE id = 'quar-v5-1'")
    db.execute(
        """
        INSERT INTO quarantine (id, rule_id, reason, original_data, quarantined_at)
        VALUES ('quar-v5-1', 'rule-v5-sig', 'drift anomaly in battery_soc', '{"soc": -5}', CURRENT_TIMESTAMP)
        """
    )
    res = client.get("/api/v1/signals", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1


def test_incidents_endpoint():
    from src.reliability.incidents.service import IncidentService
    service = IncidentService()
    if not service.list_incidents():
        service.create_incident(
            project_id="proj-vingroup-pilot",
            entity_ids=["VG_STA_0001_JPL"],
            signal_ids=["sig-01"],
            admission_reason="High temperature drift",
            severity="HIGH"
        )
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
        "target_table": "ev_telemetry",
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


def test_hitl_synthesize_llm_endpoint():
    payload = {"dataset_key": "charging_sessions"}
    res = client.post("/api/v1/hitl/synthesize-llm", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "proposals" in data
    assert len(data["proposals"]) >= 1
    p = data["proposals"][0]
    assert "rule_expression" in p
    assert "problem_discovered" in p
    assert "why_proposed" in p


def test_incident_investigate_endpoint():
    from src.reliability.incidents.service import IncidentService
    service = IncidentService()
    inc = service.create_incident(
        project_id="proj-vingroup-pilot",
        entity_ids=["VG_STA_0001_JPL"],
        signal_ids=["sig-99"],
        admission_reason="Voltage overpower_kw spike test",
        severity="HIGH"
    )
    res = client.post(f"/api/v1/incidents/{inc.incident_id}/investigate?mode=A1&use_llm=false", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["incident_id"] == inc.incident_id
    assert "hypothesis" in data



