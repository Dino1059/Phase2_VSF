"""GET /api/v1/memory is mounted and auth-gated."""
from fastapi.testclient import TestClient

from src.main import app


def test_memory_unauth_is_401():
    r = TestClient(app).get("/api/v1/memory")
    assert r.status_code == 401


def test_memory_admin_is_200():
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    r = client.get("/api/v1/memory")
    assert r.status_code == 200
    body = r.json()
    assert body["module"] == "memory"
    assert body["user_id"]
    stats = client.get("/api/v1/memory/stats")
    assert stats.status_code == 200
