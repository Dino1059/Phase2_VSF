"""Admin Reset DB must wipe steward state so a fresh VIN upload starts at 0/0."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.db.connection import get_db

ROOT = Path(__file__).resolve().parents[1]


def test_reset_ui_wipes_workspace_hitl_and_storage():
    header = (ROOT / "frontend/src/components/layout/Header.tsx").read_text()
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    store = (ROOT / "frontend/src/stores/workspaceStore.ts").read_text()
    system = (ROOT / "src/api/routes/system.py").read_text()
    hitl = (ROOT / "src/api/hitl.py").read_text()

    assert "resetStewardState" in header
    assert "wipeStewardBrowserKeys" in header
    assert "dt-hitl" in header
    assert "systemApi.resetAll" in header
    assert "datatrust:db-reset" in header
    assert "datatrust:db-reset" in rules
    assert "setProposals([])" in rules
    assert "emptyBootRef.current = false" in rules
    assert "resetStewardState" in store
    assert "wipeStewardBrowserKeys" in store
    assert "dt-hitl" in store
    assert "dt-warehouse" in store
    assert "def wipe_steward_runtime" in system
    assert '"quality_rules"' in system.split("STEWARD_WIPE_TABLES", 1)[1].split("def wipe_steward_runtime", 1)[0]
    assert '"agent_traces"' in system.split("STEWARD_WIPE_TABLES", 1)[1]
    assert '"quarantine"' in system.split("STEWARD_WIPE_TABLES", 1)[1]
    assert "agent_traces" in hitl.split("async def reset_hitl_and_rules", 1)[1]


def test_reset_all_wipes_approved_rules_and_hitl_queue():
    login = TestClient(app).post("/api/v1/auth/login", json={"username": "admin@datatrust.os", "role": "Admin"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    db = get_db()
    rid = "qa_reset_wipe__R1"
    try:
        db.execute(
            "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'approved', 'qa', CURRENT_TIMESTAMP)",
            [rid, "uploaded_vin_reset", "soc", "range", "battery_soc >= 0", 0.9],
        )
    except Exception:
        try:
            db.execute(
                "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'approved', 'qa', CURRENT_TIMESTAMP)",
                [rid, "soc", "range", "battery_soc >= 0", 0.9],
            )
        except Exception:
            db.execute("UPDATE quality_rules SET status = 'approved' WHERE id = ?", [rid])
    leftover = db.execute("SELECT count(*) FROM quality_rules WHERE id = ?", [rid])
    assert leftover and int(leftover[0][0]) >= 1

    res = TestClient(app).post(
        "/api/v1/system/reset-all?reload_warehouse=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert "quality_rules" in body["cleared_tables"]
    gone = db.execute("SELECT count(*) FROM quality_rules")
    assert gone is not None and int(gone[0][0]) == 0
    traces = db.execute("SELECT count(*) FROM agent_traces")
    assert traces is not None and int(traces[0][0]) == 0
    q = db.execute("SELECT count(*) FROM quarantine")
    assert q is not None and int(q[0][0]) == 0
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    queue = client.get("/api/v1/hitl/queue?include_active=true&dataset_key=uploaded_vin_reset")
    assert queue.status_code == 200
    assert queue.json().get("proposals") == []
