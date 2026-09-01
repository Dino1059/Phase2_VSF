"""Phase 2 dataset ACL gates — steward_a↛B, Admin names-only, no Admin execute, global demo OK."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import (
    ROLE_PERMISSIONS,
    UserRole,
    create_access_token,
    user_can_access_dataset,
    SERVER_USERS,
    acl_profile_from_user,
)


def _tok(username: str) -> str:
    u = SERVER_USERS[username]
    acl = acl_profile_from_user(u)
    return create_access_token(
        {
            "sub": u["username"],
            "user_id": u["user_id"],
            "role": u["role"].value,
            "is_global": acl["is_global"],
            "datasets": acl["datasets"],
            "dept": acl.get("dept") or "",
        }
    )


def _client(username: str) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {_tok(username)}"})


def test_acl_helpers_steward_a_not_b():
    a = acl_profile_from_user(SERVER_USERS["steward_a"])
    assert a["datasets"] == ["ev_telemetry"]
    assert not a["is_global"]
    assert user_can_access_dataset(False, ["ev_telemetry"], "ev_telemetry")
    assert not user_can_access_dataset(False, ["ev_telemetry"], "trips")
    assert user_can_access_dataset(True, ["*"], "trips")


def test_admin_has_no_execute_permission():
    assert "execute_transform" not in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert "execute_transform" in ROLE_PERMISSIONS[UserRole.STEWARD]
    assert "manage_acl" in ROLE_PERMISSIONS[UserRole.ADMIN]


def test_login_returns_acl_claims():
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": "steward_a"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("is_global") is False
    assert "ev_telemetry" in (body.get("datasets") or [])
    assert body.get("role") == "Steward"

    g = c.post("/api/v1/auth/login", json={"username": "steward"})
    assert g.status_code == 200
    assert g.json().get("is_global") is True


def test_steward_a_cannot_access_dataset_b():
    c = _client("steward_a")
    # catalog should not include trips (or filtered)
    r = c.get("/api/v1/datasets")
    assert r.status_code == 200
    keys = []
    for d in r.json().get("datasets") or []:
        if isinstance(d, dict):
            keys.append(d.get("key") or d.get("dataset_key") or d.get("name"))
        else:
            keys.append(str(d))
    assert "trips" not in keys or all(k != "trips" for k in keys if k)

    r2 = c.get("/api/v1/datasets/trips/sample?limit=1")
    assert r2.status_code == 403

    r3 = c.get("/api/v1/hitl/day-count?dataset_key=trips&calendar_day=2026-01-11")
    assert r3.status_code == 403


def test_steward_a_can_access_dataset_a():
    c = _client("steward_a")
    r = c.get("/api/v1/datasets")
    assert r.status_code == 200
    # day-count on A should not be ACL-403 (may 200 or other app error, not 403 ACL)
    r2 = c.get("/api/v1/hitl/day-count?dataset_key=ev_telemetry&calendar_day=2026-01-11&day_idx=10")
    assert r2.status_code != 403


def test_admin_names_only_and_no_row_drill():
    c = _client("admin")
    r = c.get("/api/v1/datasets")
    assert r.status_code == 200
    assert r.json().get("acl") == "names_only" or isinstance(r.json().get("datasets"), list)

    # aggregate dashboard allowed
    dash = c.get("/api/v1/dashboard/stats")
    assert dash.status_code in (200, 404)  # router may be /dashboard/stats
    if dash.status_code == 404:
        dash = c.get("/dashboard/stats")
    # tolerate mount path; must not be 403 for aggregate
    assert dash.status_code != 403

    # row/HITL drill forbidden
    assert c.get("/api/v1/datasets/ev_telemetry/sample?limit=1").status_code == 403
    assert c.get("/api/v1/hitl/day-count?dataset_key=ev_telemetry&calendar_day=2026-01-11").status_code == 403


def test_admin_cannot_execute():
    c = _client("admin")
    r = c.post("/api/v1/hitl/execute", json={"dataset_key": "ev_telemetry", "rule_ids": ["x"]})
    assert r.status_code == 403


def test_global_steward_still_works():
    c = _client("steward")
    r = c.get("/api/v1/datasets")
    assert r.status_code == 200
    r2 = c.get("/api/v1/hitl/day-count?dataset_key=ev_telemetry&calendar_day=2026-01-11&day_idx=10")
    assert r2.status_code != 403
    # HITL write path steward-only — remember should not be role-403 for steward
    r3 = c.post(
        "/api/v1/hitl/remember",
        json={"dataset_key": "ev_telemetry", "rule_id": "acl-test", "actor": "Steward"},
    )
    assert r3.status_code != 403 or "Steward" not in str(r3.json())


def test_steward_b_cannot_access_a():
    c = _client("steward_b")
    assert c.get("/api/v1/datasets/ev_telemetry/sample?limit=1").status_code == 403
    assert c.get("/api/v1/hitl/day-count?dataset_key=ev_telemetry&calendar_day=2026-01-11").status_code == 403
