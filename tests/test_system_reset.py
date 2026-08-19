from fastapi.testclient import TestClient
import pytest
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
    # Login as admin to get token
    login_res = client.post("/api/v1/auth/login", json={"username": "admin@datatrust.os", "role": "Admin"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    reset_res = client.post(
        "/api/v1/system/reset-all?reload_warehouse=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reset_res.status_code == 200
    data = reset_res.json()
    assert data["status"] == "success"
    assert "quality_rules" in data["cleared_tables"]
    assert "quarantine" in data["cleared_tables"]
    assert "audit_log" in data["cleared_tables"]
    assert "algolia" in data
    assert "cleared" in data["algolia"]
    assert "seeded" in data["algolia"]
    assert "uploads_cleared" in data

