"""HITL sandbox must run the real clean path and populate Split from DuckDB.

handleSandboxExecute used to only authorize + POST /hitl/execute/{id}, then
setSandboxAuthorized(true). Split stayed 0 because parent splitResult was empty,
GET /quarantine was empty, and no clean_database beat existed.
"""
from __future__ import annotations

from pathlib import Path

from src.services.dataset_engine import execute_compiled_rules
from src.tools.chat_tools import persist_sandbox_split, approved_rules_for_clean

ROOT = Path(__file__).resolve().parents[1]


def _rules() -> str:
    return (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()


def _split() -> str:
    return (ROOT / "frontend/src/components/workspace/SplitDbQuarantineTab.tsx").read_text()


def _api() -> str:
    return (ROOT / "frontend/src/services/api.ts").read_text()


def _hitl() -> str:
    return (ROOT / "src/api/hitl.py").read_text()


def _ws() -> str:
    return (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()


def test_handle_sandbox_execute_calls_clean_and_writes_split_store():
    ui = _rules()
    api = _api()
    hitl = _hitl()
    sandbox_fn = ui.split("const handleSandboxExecute", 1)[1].split("const proposedCount", 1)[0]
    assert "approvalsApi.authorize" in sandbox_fn
    assert "hitlApi.execute" not in sandbox_fn
    assert "hitlApi.sandbox" in sandbox_fn
    assert "hitlApi.getSandbox" in sandbox_fn
    assert "SandboxDiff" in ui
    assert "<SandboxDiff" in ui
    assert "mergeSplitRows" in sandbox_fn
    assert "cleanRan: true" in sandbox_fn
    assert "datatrust:sandbox-split" in sandbox_fn or "datatrust:split-refresh" in sandbox_fn
    approve = ui.split("const handleApprove", 1)[1].split("const handleSandboxExecute", 1)[0]
    assert "hitlApi.sandbox" not in approve
    assert "hitlApi.execute" not in approve
    assert "sandbox:" in api.split("export const hitlApi", 1)[1]
    assert '@hitl_router.post("/sandbox")' in hitl or '@hitl_router.post("/sandbox")' in hitl.replace("'", '"')
    assert "persist_sandbox_split" in hitl
    assert "clean_database" in hitl
    assert "onExecuteClean" not in _ws().split("<QualityRulesTab", 1)[1].split("/>", 1)[0]


def test_split_merges_sandbox_event_and_does_not_clobber_empty_get():
    split = _split()
    assert "datatrust:sandbox-split" in split or "datatrust:split-refresh" in split
    fetch = split.split("const fetchData", 1)[1].split("useEffect", 1)[0]
    assert "incomingQ.length === 0" in fetch
    assert "cleanRan" in fetch
    store = (ROOT / "frontend/src/stores/workspaceStore.ts").read_text()
    assert "Empty GET must never clobber" in store
    assert "mergeSplitRows" in store


def test_persist_sandbox_split_writes_measured_quarantine_only():
    rows = [
        {"vin": "VIN-DIRTY", "battery_soc": -3, "speed_kmh": 10},
        {"vin": "VIN-CLEAN", "battery_soc": 64, "speed_kmh": 12},
    ]
    rules = [{
        "rule_id": "qa_sandbox__R1",
        "id": "qa_sandbox__R1",
        "name": "soc",
        "rule_name": "soc",
        "expression": "battery_soc >= 0",
        "rule_expression": "battery_soc >= 0",
        "decision": "approved",
    }]
    exec_res = execute_compiled_rules(rows, rules)
    assert exec_res["quarantine_count"] == 1
    assert exec_res["clean_count"] == 1
    from src.db.connection import get_db
    db = get_db()
    try:
        db.execute("DELETE FROM quarantine WHERE id LIKE 'q-qa_sandbox%' OR source_table = 'qa_sandbox'")
    except Exception:
        pass
    payload = persist_sandbox_split("qa_sandbox", rows, exec_res, rules, db=db)
    assert payload["sandbox"] is True
    assert payload["this_run"] is True
    assert str(payload.get("snapshot_id") or "").startswith("sandbox:")
    assert payload["quarantine_rows"] == 1
    assert payload["clean_rows"] == 1
    assert payload["quarantine"][0]["source_row_id"] in ("VIN-DIRTY", "1")
    assert "172" not in str(payload)
    stored = db.execute("SELECT count(*) FROM quarantine WHERE source_table = 'qa_sandbox'")
    assert stored and int(stored[0][0]) >= 1
    assert payload.get("execute") == "off"
    assert payload.get("promoted") is False
    diffs = payload.get("cell_diffs") or []
    assert diffs
    assert diffs[0]["field"] == "battery_soc"
    assert diffs[0]["before_value"] == -3
    from fastapi.testclient import TestClient
    from src.main import app
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    preview = client.get(f"/api/v1/hitl/sandbox/{payload['snapshot_id']}")
    assert preview.status_code == 200
    body = preview.json()
    assert body.get("execute") == "off"
    assert body.get("promoted") is False
    assert int(body.get("quarantine_rows") or 0) >= 1
    assert body.get("cell_diffs")
    assert "sandbox." not in preview.text


def test_approved_rules_for_clean_never_synthesizes():
    from src.db.connection import get_db
    db = get_db()
    empty = approved_rules_for_clean(db, "no_such_dataset_xyz", ["missing__R1"])
    assert empty == [] or all(str(r.get("decision") or "").lower() in ("approved", "edit", "edited") for r in empty)


def test_execute_off_is_design_not_csrf_or_auth():
    """POST /hitl/execute 403 is execute-off for Admin too. Missing JWT is 401. Viewer write is role 403."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.middleware.auth import create_access_token

    anon = TestClient(app)
    missing = anon.post("/api/v1/hitl/execute", json={})
    assert missing.status_code == 401, missing.text

    token = create_access_token(
        {"sub": "admin@datatrust.os", "user_id": "usr_admin_01", "role": "Admin"}
    )
    admin = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    off = admin.post("/api/v1/hitl/execute", json={"rule_id": "any"})
    assert off.status_code == 403, off.text
    detail = str(off.json().get("detail") or "").lower()
    assert "execute off" in detail or "not execute" in detail
    assert "csrf" not in detail
    assert "token" not in detail
    assert "viewer" not in detail

    viewer = TestClient(app, headers={"X-User-Role": "Viewer"})
    blocked = viewer.post("/api/v1/hitl/sandbox", json={"dataset_key": "ev_telemetry", "rule_ids": ["x"]})
    assert blocked.status_code == 403, blocked.text
    vdetail = str(blocked.json().get("detail") or "").lower()
    assert "viewer" in vdetail or "read-only" in vdetail


def test_admin_authorize_accepts_edited_then_sandbox_preview():
    """Admin HITL path is authorize + sandbox + GET quarantine preview, never execute."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.db.connection import get_db
    from src.middleware.auth import create_access_token

    rid = "qa_edited_auth__R1"
    db = get_db()
    try:
        db.execute("DELETE FROM quality_rules WHERE id = ?", [rid])
    except Exception:
        pass
    db.execute(
        "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [rid, "soc", "range", "battery_soc >= 0", 0.9, "edited"],
    )
    token = create_access_token(
        {"sub": "admin@datatrust.os", "user_id": "usr_admin_01", "role": "Admin"}
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    auth = client.post(
        "/api/v1/approvals/authorize",
        json={"dataset_key": "qa_edited_auth", "rule_ids": [rid]},
    )
    assert auth.status_code == 200, auth.text
    assert auth.json().get("payload_hash")
    exe = client.post(f"/api/v1/hitl/execute/{rid}")
    assert exe.status_code == 403
    assert "not execute" in str(exe.json().get("detail") or "").lower() or "execute off" in str(exe.json().get("detail") or "").lower()


def test_sandbox_endpoint_exists_and_requires_approved_rule():
    from fastapi.testclient import TestClient
    from src.main import app
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    res = client.post("/api/v1/hitl/sandbox", json={"dataset_key": "no_such_dataset_xyz", "rule_ids": []})
    assert res.status_code in (403, 400, 422)
    missing = client.post("/api/v1/hitl/sandbox", json={"dataset_key": "", "rule_ids": ["x"]})
    assert missing.status_code in (400, 422)

def test_sandbox_handler_is_bounded_not_full_50k_blocking_scan():
    """POST /hitl/sandbox must sample, not scan 50k as the only path (504 >90s)."""
    import re
    hitl = _hitl()
    fn = hitl.split("async def sandbox_clean", 1)[1].split("async def get_history", 1)[0]
    assert "SANDBOX_SAMPLE_CAP" in hitl
    cap = int(re.search(r"SANDBOX_SAMPLE_CAP\s*=\s*(\d+)", hitl).group(1))
    assert cap <= 8000
    assert "sample_size=cap" in fn or "sample_size=cap" in fn.replace(" ", "")
    assert "load_dataset(dataset_key=dataset_key, sample_size=" in fn
    assert "load_dataset(dataset_key=dataset_key)" not in fn
    assert "snapshot_id" in fn
    assert "persist_sandbox_split" in fn


def test_sandbox_504_does_not_keep_leftover_split_as_success():
    """HTTP 504 / empty sandbox must stay 0/0 — leftover 50k is not this run."""
    ui = _rules()
    split = _split()
    store = (ROOT / "frontend/src/stores/workspaceStore.ts").read_text()
    sandbox_fn = ui.split("const handleSandboxExecute", 1)[1].split("const proposedCount", 1)[0]
    assert "datatrust:sandbox-failed" in sandbox_fn
    assert "HTTP 504" in sandbox_fn
    assert "replaceSplitRows" in sandbox_fn
    assert "thisRun: true" in sandbox_fn
    fetch = split.split("const fetchData", 1)[1].split("useEffect", 1)[0]
    assert "incomingQ.length === 0" in fetch
    assert "thisRun" in fetch
    assert "cleanRan" in fetch
    assert "cRes.total_rows" not in fetch
    assert "datasetsApi.sample(" not in split
    assert "datatrust:sandbox-failed" in split
    assert "replaceSplitRows" in split
    assert "thisRun" in store
    assert "replaceSplitRows" in store
    assert "Empty GET must never clobber" in store

def test_alert_dashboard_reads_this_run_quarantine():
    """Alert Dashboard Quarantine/Audit must read this-run DuckDB, not a hardcoded 0."""
    ops = (ROOT / "frontend/src/pages/OperationsWorkspace.tsx").read_text()
    qapi = (ROOT / "src/api/quarantine_api.py").read_text()
    summary = (ROOT / "src/api/routes/summary.py").read_text()
    assert "0 / 0" not in ops
    assert "thisRunSplitTotals" in ops
    assert "quarantineApi" in ops
    assert "this_run" in ops
    assert "datatrust:sandbox-split" in ops
    assert "totalQuarantine" in ops
    assert "splitRowsByDataset" in ops
    assert "50000" in ops
    assert "_this_run_quarantine_count" in qapi
    assert "sandbox:%" in qapi
    assert "this_run" in qapi
    assert "this_run_quarantined" in summary


def test_quarantine_count_this_run_matches_persist():
    """GET /quarantine/count this_run is sandbox rows, not leftover warehouse total."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.db.connection import get_db
    from src.services.dataset_engine import execute_compiled_rules
    from src.tools.chat_tools import persist_sandbox_split

    rows = [
        {"vin": "VIN-DIRTY-DASH", "battery_soc": -3, "speed_kmh": 10},
        {"vin": "VIN-CLEAN-DASH", "battery_soc": 64, "speed_kmh": 12},
    ]
    rules = [{
        "rule_id": "qa_dash__R1",
        "id": "qa_dash__R1",
        "name": "soc",
        "rule_name": "soc",
        "expression": "battery_soc >= 0",
        "rule_expression": "battery_soc >= 0",
        "decision": "approved",
    }]
    exec_res = execute_compiled_rules(rows, rules)
    db = get_db()
    try:
        db.execute("DELETE FROM quarantine WHERE source_table = 'qa_dash' OR id LIKE 'q-qa_dash%'")
    except Exception:
        pass
    payload = persist_sandbox_split("qa_dash", rows, exec_res, rules, db=db)
    assert payload["this_run"] is True
    assert payload["quarantine_rows"] == 1
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    res = client.get("/api/v1/quarantine/count")
    assert res.status_code == 200
    body = res.json()
    assert "this_run" in body
    assert int(body["this_run"]) >= 1
    assert int(body["this_run"]) < 50000
    listed = client.get("/api/v1/quarantine/?limit=100")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert "this_run" in listed_body
    mine = [r for r in listed_body.get("quarantine") or [] if r.get("source_table") == "qa_dash"]
    assert mine
    assert all(r.get("this_run") or str(r.get("snapshot_id") or "").startswith("sandbox:") for r in mine)

