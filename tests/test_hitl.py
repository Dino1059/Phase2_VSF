import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.db.connection import DuckDBManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.duckdb")
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    monkeypatch.setattr('src.api.hitl.get_db', lambda: db)
    monkeypatch.setattr('src.services.audit.get_db', lambda: db)
    yield TestClient(app, headers={"X-User-Role": "Admin"}), db
    db.close()


def test_get_empty_queue(client):
    c, db = client
    resp = c.get("/api/v1/hitl/queue")
    assert resp.status_code == 200
    assert resp.json()["proposals"] == []


def test_get_queue_with_proposals(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed', 'agent')")
    resp = c.get("/api/v1/hitl/queue")
    assert resp.status_code == 200
    assert len(resp.json()["proposals"]) == 1


def test_get_queue_filters_dataset_key(client):
    c, db = client
    try:
        db.execute("ALTER TABLE quality_rules ADD COLUMN dataset_key VARCHAR")
    except Exception:
        pass
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('r-pilot', 'vingroup_pilot', 'soc', 'range', 'soc BETWEEN 0 AND 100', 0.9, 'proposed', 'agent')"
    )
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('r-other', 'other_ds', 'fare', 'range', 'fare >= 0', 0.9, 'proposed', 'agent')"
    )
    resp = c.get("/api/v1/hitl/queue?dataset_key=vingroup_pilot")
    assert resp.status_code == 200
    ids = {p["rule_id"] for p in resp.json()["proposals"]}
    assert ids == {"r-pilot"}


def test_approve_rule(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    resp = c.post("/api/v1/hitl/approve/r1", json={"approved_by": "tester"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_approve_not_found(client):
    c, db = client
    resp = c.post("/api/v1/hitl/approve/nonexistent", json={})
    assert resp.status_code == 404


def test_approve_already_approved(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'approved')")
    resp = c.post("/api/v1/hitl/approve/r1", json={})
    assert resp.status_code == 400


def test_reject_rule(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    resp = c.post("/api/v1/hitl/reject/r1", json={"reason": "not useful"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_reject_not_found(client):
    c, db = client
    resp = c.post("/api/v1/hitl/reject/nonexistent", json={})
    assert resp.status_code == 404


def test_edit_rule(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    resp = c.post("/api/v1/hitl/edit/r1", json={"rule_expression": "x > 10", "edited_by": "tester"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "edited"


def test_edit_not_found(client):
    c, db = client
    resp = c.post("/api/v1/hitl/edit/nonexistent", json={"rule_expression": "x > 0"})
    assert resp.status_code == 404


def test_get_history_empty(client):
    c, db = client
    resp = c.get("/api/v1/hitl/history")
    assert resp.status_code == 200
    assert resp.json()["history"] == []


def test_approve_creates_audit(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    c.post("/api/v1/hitl/approve/r1", json={"approved_by": "admin"})
    audit = db.execute("SELECT action, actor FROM audit_log")
    assert any('APPROVE' in str(a) for a in audit)


def test_reject_creates_audit(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    c.post("/api/v1/hitl/reject/r1", json={"reason": "bad"})
    audit = db.execute("SELECT action FROM audit_log")
    assert any('REJECT' in str(a) for a in audit)


def test_edit_creates_audit(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    c.post("/api/v1/hitl/edit/r1", json={"rule_expression": "x > 5", "edited_by": "editor"})
    audit = db.execute("SELECT action, actor FROM audit_log")
    assert any('EDIT' in str(a) for a in audit)


def test_get_history_populated(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'test', 'range', 'x > 0', 0.9, 'proposed')")
    c.post("/api/v1/hitl/approve/r1", json={"approved_by": "admin"})
    resp = c.get("/api/v1/hitl/history")
    assert resp.status_code == 200
    assert len(resp.json()["history"]) == 1
    assert resp.json()["history"][0]["action"] == "APPROVE_RULE"


def test_full_workflow(client):
    c, db = client
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r1', 'a', 'range', 'x > 0', 0.9, 'proposed')")
    db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) VALUES ('r2', 'b', 'range', 'y > 0', 0.8, 'proposed')")
    # Edit r1, then approve
    c.post("/api/v1/hitl/edit/r1", json={"rule_expression": "x > 5"})
    c.post("/api/v1/hitl/approve/r1", json={"approved_by": "tester"})
    # Reject r2
    c.post("/api/v1/hitl/reject/r2", json={"reason": "not needed"})
    # Check queue is empty
    queue = c.get("/api/v1/hitl/queue").json()
    assert len(queue["proposals"]) == 0
    # Check history has entries
    history = c.get("/api/v1/hitl/history").json()
    assert len(history["history"]) >= 2


def test_audit_state_hash(client):
    c, db = client
    from src.services.audit import AuditService
    h = AuditService.compute_state_hash("r1", "x > 0", "approved")
    assert len(h) == 16
    assert isinstance(h, str)


def test_queue_include_active_keeps_approved_after_approve(client):
    """After one Approve, include_active queue still returns the approved row (DuckDB wins)."""
    c, db = client
    db.execute(
        "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('r1', 'soc', 'range', 'x > 0', 0.9, 'proposed', 'agent')"
    )
    db.execute(
        "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('r2', 'vin', 'not_null', 'y IS NOT NULL', 0.9, 'proposed', 'agent')"
    )
    resp = c.post("/api/v1/hitl/approve/r1", json={"approved_by": "tester"})
    assert resp.status_code == 200
    default_q = c.get("/api/v1/hitl/queue").json()["proposals"]
    assert {p["rule_id"] for p in default_q} == {"r2"}
    active = c.get("/api/v1/hitl/queue?include_active=true").json()["proposals"]
    by_id = {p["rule_id"]: p for p in active}
    assert by_id["r1"]["status"] == "approved"
    assert by_id["r2"]["status"] in ("proposed", "pending")
