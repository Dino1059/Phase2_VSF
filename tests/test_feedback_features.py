import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.db.connection import get_db
from src.reliability.incidents.service import IncidentService

client = TestClient(app)

HEADERS = {
    "X-User-Role": "steward",
    "X-Session-ID": "test-session-feedback"
}


def test_rule_reject_feedback_persisted():
    db = get_db()
    rule_id = "test_rule_feedback_01"
    db.execute(
        """
        INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at)
        VALUES (?, ?, ?, ?, ?, 'proposed', 'test_agent', CURRENT_TIMESTAMP)
        """,
        [rule_id, "Test Rule Feedback", "range", "voltage > 0", 0.95]
    )

    reason = "Threshold too tight for test environment"
    resp = client.post(
        f"/api/v1/hitl/reject/{rule_id}",
        json={"rejected_by": "qa_user", "reason": reason},
        headers=HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["reject_reason"] == reason

    # Verify queue returns reject_reason
    q_resp = client.get("/api/v1/hitl/queue?status=rejected", headers=HEADERS)
    assert q_resp.status_code == 200
    proposals = q_resp.json().get("proposals", [])
    target = next((p for p in proposals if p["rule_id"] == rule_id), None)
    assert target is not None
    assert target["reject_reason"] == reason
    assert target["feedback_by"] == "qa_user"


def test_incident_feedback_persisted():
    service = IncidentService()
    inc = service.create_incident(
        project_id="proj-vingroup-pilot",
        entity_ids=["VIN-999"],
        signal_ids=["sig-999"],
        admission_reason="ANOMALY: High temperature spike",
        severity="HIGH"
    )

    # Submit TRUE_POSITIVE feedback
    resp_tp = client.post(
        f"/api/v1/incidents/{inc.incident_id}/feedback",
        json={"feedback_type": "TRUE_POSITIVE", "reason": "Confirmed physical overheat on BMS", "user": "steward_bob"},
        headers=HEADERS
    )
    assert resp_tp.status_code == 200
    tp_data = resp_tp.json()
    assert tp_data["status"] == "ok"
    assert tp_data["feedback_type"] == "TRUE_POSITIVE"
    assert tp_data["feedback_reason"] == "Confirmed physical overheat on BMS"
    assert tp_data["incident_status"] == "RESOLVED"

    # Submit FALSE_POSITIVE feedback update
    resp_fp = client.post(
        f"/api/v1/incidents/{inc.incident_id}/feedback",
        json={"feedback_type": "FALSE_POSITIVE", "reason": "Sensor glitch during calibration", "user": "steward_bob"},
        headers=HEADERS
    )
    assert resp_fp.status_code == 200
    fp_data = resp_fp.json()
    assert fp_data["feedback_type"] == "FALSE_POSITIVE"
    assert fp_data["feedback_reason"] == "Sensor glitch during calibration"
    assert fp_data["incident_status"] == "DISMISSED"

    # Verify get_incident includes feedback
    get_resp = client.get(f"/api/v1/incidents/{inc.incident_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    inc_detail = get_resp.json()
    assert inc_detail["feedback_type"] == "FALSE_POSITIVE"
    assert inc_detail["feedback_reason"] == "Sensor glitch during calibration"
