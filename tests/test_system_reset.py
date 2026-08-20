import os
import pytest

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["DUCKDB_PATH"] = os.path.join(_project_root, "data", "datatrust_test.duckdb")

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_quick_switch_admin():
    res = client.post("/api/v1/auth/quick-switch", json={"role": "admin"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "Admin"


def test_quick_switch_steward():
    res = client.post("/api/v1/auth/quick-switch", json={"role": "steward"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "Steward"


def test_quick_switch_viewer():
    res = client.post("/api/v1/auth/quick-switch", json={"role": "viewer"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "Viewer"


def test_system_reset_admin_success():
    # 1. Login as admin to get token
    login_res = client.post("/api/v1/auth/login", json={"username": "admin@datatrust.os", "role": "Admin"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create a dummy incident in IncidentService first
    from src.reliability.incidents.service import IncidentService
    service = IncidentService()
    service.create_incident(
        project_id="proj-vingroup-pilot",
        entity_ids=["VG_STA_0001_JPL"],
        signal_ids=["sig-test-01"],
        admission_reason="Test admission reason before reset",
        severity="HIGH",
    )
    # Verify incident exists
    inc_res = client.get("/api/v1/incidents", headers=headers)
    assert inc_res.status_code == 200
    assert len(inc_res.json()) > 0

    # 3. Call system reset
    reset_res = client.post("/api/v1/system/reset-all", headers=headers)
    assert reset_res.status_code == 200
    data = reset_res.json()
    assert data["status"] == "success"
    assert "quality_rules" in data["cleared_tables"]
    assert "quarantine" in data["cleared_tables"]
    assert "audit_log" in data["cleared_tables"]
    assert "incidents" in data["cleared_tables"]

    # 4. Verify incidents list is now empty after reset
    inc_res_after = client.get("/api/v1/incidents", headers=headers)
    assert inc_res_after.status_code == 200
    assert inc_res_after.json() == []

    # 5. Verify pending HITL rules queue is clean (0 pending proposals)
    queue_res = client.get("/api/v1/hitl/queue", headers=headers)
    assert queue_res.status_code == 200
    assert queue_res.json()["proposals"] == []


