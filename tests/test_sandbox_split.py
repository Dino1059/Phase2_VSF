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
    assert "hitlApi.execute" in sandbox_fn
    assert "hitlApi.sandbox" in sandbox_fn
    assert "mergeSplitRows" in sandbox_fn
    assert "cleanRan: true" in sandbox_fn
    assert "datatrust:sandbox-split" in sandbox_fn or "datatrust:split-refresh" in sandbox_fn
    approve = ui.split("const handleApprove", 1)[1].split("const handleReject", 1)[0]
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
    assert payload["quarantine_rows"] == 1
    assert payload["clean_rows"] == 1
    assert payload["quarantine"][0]["source_row_id"] in ("VIN-DIRTY", "1")
    assert "172" not in str(payload)
    stored = db.execute("SELECT count(*) FROM quarantine WHERE source_table = 'qa_sandbox'")
    assert stored and int(stored[0][0]) >= 1


def test_approved_rules_for_clean_never_synthesizes():
    from src.db.connection import get_db
    db = get_db()
    empty = approved_rules_for_clean(db, "no_such_dataset_xyz", ["missing__R1"])
    assert empty == [] or all(str(r.get("decision") or "").lower() in ("approved", "edit", "edited") for r in empty)


def test_sandbox_endpoint_exists_and_requires_approved_rule():
    from fastapi.testclient import TestClient
    from src.main import app
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    res = client.post("/api/v1/hitl/sandbox", json={"dataset_key": "vingroup_pilot", "rule_ids": []})
    assert res.status_code in (403, 400, 422)
    missing = client.post("/api/v1/hitl/sandbox", json={"dataset_key": "", "rule_ids": ["x"]})
    assert missing.status_code in (400, 422)
