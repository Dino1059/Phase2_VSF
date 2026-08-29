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
    sandbox_fn = ui.split("const handleSandboxExecute", 1)[1].split("const handleWarehouseExecute", 1)[0]
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
    assert "hitlApi.sandbox(" not in approve
    assert "hitlApi.executeWarehouse" not in approve
    assert "hitlApi.execute(" not in approve
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
    assert int(body.get("quarantine_rows") or 0) == 1
    assert int(body.get("clean_rows") or 0) == 1
    assert body.get("counts_kind") == "preview"
    assert int(body.get("warehouse_clean_rows") or 0) == 0
    assert body.get("cell_diffs")
    assert "sandbox." not in preview.text


def test_approved_rules_for_clean_never_synthesizes():
    from src.db.connection import get_db
    db = get_db()
    empty = approved_rules_for_clean(db, "no_such_dataset_xyz", ["missing__R1"])
    assert empty == [] or all(str(r.get("decision") or "").lower() in ("approved", "edit", "edited") for r in empty)


def test_execute_off_is_design_not_csrf_or_auth():
    """POST /hitl/execute is Steward-only. Admin/anon/viewer stay 403. Missing JWT is 401."""
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
    assert "steward" in detail or "hitl write" in detail or "execute off" in detail or "not execute" in detail
    assert "csrf" not in detail
    assert "token" not in detail
    assert "viewer" not in detail

    viewer = TestClient(app, headers={"X-User-Role": "Viewer"})
    blocked = viewer.post("/api/v1/hitl/sandbox", json={"dataset_key": "ev_telemetry", "rule_ids": ["x"]})
    assert blocked.status_code == 403, blocked.text
    vdetail = str(blocked.json().get("detail") or "").lower()
    assert "viewer" in vdetail or "read-only" in vdetail


def test_steward_execute_uses_token_role_value_not_enum_str():
    """Steward JWT role is UserRole.STEWARD.value ('Steward'), never str(enum)='UserRole.STEWARD'."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.middleware.auth import UserRole, create_access_token, decode_access_token

    assert UserRole.STEWARD.value.lower() == "steward"
    token = create_access_token(
        {"sub": "steward@datatrust.os", "user_id": "usr_steward_01", "role": UserRole.STEWARD.value}
    )
    payload = decode_access_token(token)
    assert payload["role"] == UserRole.STEWARD.value
    assert payload["role"].lower() == "steward"
    assert payload["role"] != "UserRole.STEWARD"

    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.post(
        "/api/v1/hitl/execute",
        json={"dataset_key": "qa_steward_role_gate_missing", "calendar_day": "2026-01-11", "day_idx": 10},
    )
    detail = str((resp.json() or {}).get("detail") or "")
    assert "Execute is Data Steward only" not in detail
    assert "UserRole.STEWARD" not in detail
    assert resp.status_code != 403 or "not approved" in detail.lower()


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
    ed = str(exe.json().get("detail") or "").lower()
    assert "steward" in ed or "hitl write" in ed or "not execute" in ed or "execute off" in ed


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
    fn = hitl.split("async def sandbox_clean", 1)[1].split("async def get_sandbox_run", 1)[0]
    assert "SANDBOX_SAMPLE_CAP" in hitl
    cap = int(re.search(r"SANDBOX_SAMPLE_CAP\s*=\s*(\d+)", hitl).group(1))
    assert cap <= 8000
    assert "load_sandbox_rows" in fn
    assert "sample_size=cap" not in fn or "load_sandbox_rows" in fn
    assert "snapshot_id" in fn
    assert "persist_sandbox_split" in fn
    assert "asyncio.to_thread" in fn


def test_sandbox_504_does_not_keep_leftover_split_as_success():
    """HTTP 504 / empty sandbox must stay 0/0 — leftover 50k is not this run."""
    ui = _rules()
    split = _split()
    store = (ROOT / "frontend/src/stores/workspaceStore.ts").read_text()
    sandbox_fn = ui.split("const handleSandboxExecute", 1)[1].split("const handleWarehouseExecute", 1)[0]
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


def test_between_rule_quarantines_negative_soc():
    from src.services.dataset_engine import execute_compiled_rules, safe_eval_rule

    assert safe_eval_rule("battery_soc BETWEEN 0 AND 100", {"battery_soc": -12.5}) is False
    assert safe_eval_rule("battery_soc BETWEEN 0.0 AND 100.0", {"battery_soc": 64}) is True
    rows = [
        {"vin": "FAULT", "battery_soc": -12.5},
        {"vin": "CLEAN", "battery_soc": 64},
    ]
    rules = [{
        "rule_id": "qa_between__R1",
        "decision": "approved",
        "expression": "battery_soc BETWEEN 0 AND 100",
        "name": "soc",
    }]
    res = execute_compiled_rules(rows, rules)
    assert res["quarantine_count"] == 1
    assert res["clean_count"] == 1


def test_load_sandbox_rows_includes_tail_soc_faults():
    """Head LIMIT 3000 misses tail faults; sandbox must pull violators from main.*."""
    import duckdb
    import threading

    from src.services.dataset_engine import load_sandbox_rows

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR)")
    conn.execute("INSERT INTO ev_telemetry SELECT 64.0, 'c' || i FROM range(4000) t(i)")
    for i in range(12):
        conn.execute("INSERT INTO ev_telemetry VALUES (?, ?)", [-12.5, f"FAULT{i}"])

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def _get_master_conn(self):
            return self._c

        def fetch_df(self, q, p=None):
            with self._conn_lock:
                return self._c.execute(q, p).fetchdf() if p is not None else self._c.execute(q).fetchdf()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [{
        "rule_id": "soc",
        "id": "soc",
        "decision": "approved",
        "expression": "battery_soc BETWEEN 0 AND 100",
        "rule_expression": "battery_soc BETWEEN 0 AND 100",
    }]
    rows = load_sandbox_rows("ev_telemetry", rules, 3000, db=_DB(conn))
    bad = [r for r in rows if float(r.get("battery_soc") or 0) < 0]
    assert len(bad) == 12, f"expected 12 SOC<0 rows, got {len(bad)} of {len(rows)}"
    assert len(rows) <= 3000


def test_load_sandbox_rows_keeps_soc_faults_when_other_violators_fill_cap():
    """WHERE NOT LIMIT 3000 of SOC>100 must not drop the 12 tail SOC<0 faults."""
    import duckdb
    import threading

    from src.services.dataset_engine import load_sandbox_rows

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, record_id VARCHAR)")
    conn.execute(
        "INSERT INTO ev_telemetry SELECT 200.0, 'h' || i, 'H' || i FROM range(4000) t(i)"
    )
    for i in range(12):
        conn.execute("INSERT INTO ev_telemetry VALUES (?, ?, ?)", [-12.5, f"FAULT{i}", f"F{i}"])

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def _get_master_conn(self):
            return self._c

        def fetch_df(self, q, p=None):
            with self._conn_lock:
                return self._c.execute(q, p).fetchdf() if p is not None else self._c.execute(q).fetchdf()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [{
        "rule_id": "soc",
        "id": "soc",
        "decision": "approved",
        "expression": "battery_soc >= 0 AND battery_soc <= 100",
        "rule_expression": "battery_soc >= 0 AND battery_soc <= 100",
    }]
    rows = load_sandbox_rows("ev_telemetry", rules, 3000, db=_DB(conn))
    bad = [r for r in rows if float(r.get("battery_soc") or 0) < 0]
    assert len(bad) == 12, f"expected 12 SOC<0 rows, got {len(bad)} of {len(rows)}"


def test_and_range_rule_quarantines_negative_soc():
    from src.services.dataset_engine import execute_compiled_rules, safe_eval_rule

    expr = "battery_soc >= 0 AND battery_soc <= 100"
    assert safe_eval_rule(expr, {"battery_soc": -12.5}) is False
    assert safe_eval_rule(expr, {"battery_soc": 64}) is True
    res = execute_compiled_rules(
        [{"vin": "FAULT", "battery_soc": -12.5}, {"vin": "CLEAN", "battery_soc": 64}],
        [{"rule_id": "qa_and__R1", "decision": "approved", "expression": expr, "name": "soc"}],
    )
    assert res["quarantine_count"] == 1


def test_profile_and_health_offload_event_loop():
    datasets = (ROOT / "src/api/routes/datasets.py").read_text()
    fn = datasets.split("async def profile_dataset", 1)[1].split("async def sample_dataset", 1)[0]
    assert "asyncio.to_thread" in fn
    assert "sample_size = 3000" in fn
    main = (ROOT / "src/main.py").read_text()
    assert "async def health():" not in main
    assert "\ndef health():" in main
    assert "health_fastpath" in main
    conn = (ROOT / "src/db/connection.py").read_text()
    assert "def fetch_df" in conn
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    pipe = routes.split("is_full_pipeline_req", 1)[1].split("Standard Dynamic ReAct", 1)[0]
    assert "asyncio.to_thread(prof_tool.execute" in pipe


def test_preview_split_counts_sql_not_sample_cap():
    """Headline Q/C is COUNT(*) over table+day, not SANDBOX_SAMPLE_CAP / LIMIT 100."""
    import duckdb
    import threading

    from src.services.dataset_engine import PREVIEW_ROW_CAP, execute_compiled_rules
    from src.services.th_hitl_flow import preview_split_counts
    from src.tools.chat_tools import persist_sandbox_split

    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(7):
        conn.execute(
            "INSERT INTO ev_telemetry VALUES (64, ?, 10, 10, '2026-01-11')", [f"c{i}"]
        )
    for i in range(3):
        conn.execute(
            "INSERT INTO ev_telemetry VALUES (-3, ?, 10, 10, '2026-01-11')", [f"b{i}"]
        )
    for i in range(20):
        conn.execute(
            "INSERT INTO ev_telemetry VALUES (-3, ?, 11, 11, '2026-01-12')", [f"x{i}"]
        )

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def _get_master_conn(self):
            return self._c

        def fetch_df(self, q, p=None):
            with self._conn_lock:
                return self._c.execute(q, p).fetchdf() if p is not None else self._c.execute(q).fetchdf()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [{
        "rule_id": "qa_day__R1",
        "id": "qa_day__R1",
        "decision": "approved",
        "expression": "battery_soc >= 0",
        "rule_expression": "battery_soc >= 0",
        "name": "soc",
    }]
    db = _DB(conn)
    counts = preview_split_counts(db, "ev_telemetry", rules, "2026-01-11", 10)
    assert counts["scoped_rows"] == 10
    assert counts["clean_rows"] == 7
    assert counts["quarantine_rows"] == 3
    assert counts["counts_kind"] == "preview"
    assert counts["warehouse_clean_rows"] == 0
    assert counts["warehouse_quarantine_rows"] == 0

    rows = [{"vin": f"D{i}", "battery_soc": -1} for i in range(60)] + [{"vin": "C", "battery_soc": 50}]
    exec_res = execute_compiled_rules(rows, rules)
    from src.db.connection import get_db
    live = get_db()
    try:
        live.execute("DELETE FROM quarantine WHERE source_table = 'qa_cap' OR id LIKE 'q-qa_cap%'")
    except Exception:
        pass
    payload = persist_sandbox_split(
        "qa_cap", rows, exec_res, rules, db=live,
        preview_counts={"clean_rows": 7, "quarantine_rows": 3, "scoped_rows": 10},
    )
    assert payload["clean_rows"] == 7
    assert payload["quarantine_rows"] == 3
    assert payload["scoped_rows"] == 10
    stored = live.execute("SELECT count(*) FROM quarantine WHERE source_table = 'qa_cap'")
    assert stored and int(stored[0][0]) <= PREVIEW_ROW_CAP
    assert int(stored[0][0]) < 60


def test_split_labels_preview_not_warehouse():
    split = _split()
    assert "Preview quarantine" in split
    assert "Preview clean" in split
    assert "not warehouse after Execute" in split
    assert "Committed warehouse: Clean 0" in split
    sand = (ROOT / "frontend/src/components/workspace/SandboxDiff.tsx").read_text()
    assert "Preview estimate (table + day)" in sand
    assert "Warehouse after Execute" in sand
    get_fn = _hitl().split("async def get_sandbox_run", 1)[1].split("async def get_history", 1)[0]
    assert '"clean_rows": 0' not in get_fn
    assert "load_sandbox_preview_meta" in get_fn
    assert "preview_split_counts" in _hitl()
    assert "commit_warehouse_split" in _hitl() or "commit_warehouse_split" in (
        ROOT / "src/services/th_hitl_flow.py"
    ).read_text()
    assert "Execute warehouse (Steward)" in _rules()


def test_commit_warehouse_split_writes_clean_and_quarantine():
    import threading

    import duckdb

    from src.services.th_hitl_flow import commit_warehouse_split

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(7):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, ?, 10, 10, '2026-01-11')", [f"c{i}"])
    for i in range(3):
        conn.execute("INSERT INTO ev_telemetry VALUES (-3, ?, 10, 10, '2026-01-11')", [f"b{i}"])

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [{
        "rule_id": "qa_wh__R1",
        "id": "qa_wh__R1",
        "decision": "approved",
        "expression": "battery_soc >= 0",
        "rule_expression": "battery_soc >= 0",
    }]
    out = commit_warehouse_split(_DB(conn), "ev_telemetry", rules, "2026-01-11", 10)
    assert out["counts_kind"] == "warehouse"
    assert out["warehouse_clean_rows"] == 7
    assert out["warehouse_quarantine_rows"] == 3
    assert out["execute"] == "on"
    clean_n = conn.execute("SELECT count(*) FROM clean.ev_telemetry").fetchone()[0]
    q_n = conn.execute("SELECT count(*) FROM main.quarantine WHERE rule_version_id = 'execute'").fetchone()[0]
    assert int(clean_n) == 7
    assert int(q_n) == 3


def test_get_sandbox_run_uses_meta_when_quarantine_empty():
    """COUNT-only preview (Q=0) must 200 from sandbox_preview_meta, not 404 on empty quarantine."""
    from src.db.connection import get_db
    from src.services.th_hitl_flow import save_sandbox_preview_meta
    from src.middleware.auth import create_access_token
    from fastapi.testclient import TestClient
    from src.main import app

    db = get_db()
    snap = "sandbox:qa_meta_empty:cut"
    save_sandbox_preview_meta(
        db,
        snapshot_id=snap,
        dataset_key="qa_meta_empty",
        calendar_day="2026-01-11",
        scoped_rows=10,
        clean_rows=10,
        quarantine_rows=0,
        per_rule_counts={"soc": 0},
        sample_cap=50,
        counts_kind="preview",
    )
    token = create_access_token(
        {"sub": "analyst@datatrust.os", "user_id": "usr_analyst_01", "role": "Analyst"}
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    preview = client.get(f"/api/v1/hitl/sandbox/{snap}")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body.get("counts_kind") == "preview"
    assert int(body.get("clean_rows") or 0) == 10
    assert int(body.get("quarantine_rows") or 0) == 0
    assert int(body.get("warehouse_clean_rows") or 0) == 0
    assert body.get("execute") == "off"
    missing = client.get("/api/v1/hitl/sandbox/sandbox:does-not-exist")
    assert missing.status_code == 404


def test_load_sandbox_rows_respects_table_day():
    import duckdb
    import threading

    from src.services.dataset_engine import load_sandbox_rows

    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, record_id VARCHAR, "
        "day_idx INTEGER, assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(5):
        conn.execute(
            "INSERT INTO ev_telemetry VALUES (64, ?, ?, 10, 10, '2026-01-11')",
            [f"c{i}", f"c{i}"],
        )
    for i in range(2):
        conn.execute(
            "INSERT INTO ev_telemetry VALUES (-12.5, ?, ?, 10, 10, '2026-01-11')",
            [f"f10-{i}", f"f10-{i}"],
        )
    for i in range(40):
        conn.execute(
            "INSERT INTO ev_telemetry VALUES (-12.5, ?, ?, 11, 11, '2026-01-12')",
            [f"f11-{i}", f"f11-{i}"],
        )

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def _get_master_conn(self):
            return self._c

        def fetch_df(self, q, p=None):
            with self._conn_lock:
                return self._c.execute(q, p).fetchdf() if p is not None else self._c.execute(q).fetchdf()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [{
        "rule_id": "soc",
        "id": "soc",
        "decision": "approved",
        "expression": "battery_soc BETWEEN 0 AND 100",
        "rule_expression": "battery_soc BETWEEN 0 AND 100",
    }]
    rows = load_sandbox_rows(
        "ev_telemetry", rules, 50, db=_DB(conn), calendar_day="2026-01-11", day_idx=10,
    )
    assert rows
    assert all(int(r.get("day_idx") or -1) == 10 for r in rows)
    bad = [r for r in rows if float(r.get("battery_soc") or 0) < 0]
    assert len(bad) == 2
    assert all(str(r.get("vin") or "").startswith("f10-") for r in bad)


def test_per_rule_counts_are_exclusive():
    import threading

    import duckdb

    from src.services.th_hitl_flow import preview_split_counts

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, speed_kmh DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(7):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, 10, ?, 10, 10, '2026-01-11')", [f"c{i}"])
    for i in range(2):
        conn.execute("INSERT INTO ev_telemetry VALUES (-3, 10, ?, 10, 10, '2026-01-11')", [f"s{i}"])
    conn.execute("INSERT INTO ev_telemetry VALUES (50, 999, 'spd', 10, 10, '2026-01-11')")
    conn.execute("INSERT INTO ev_telemetry VALUES (-3, 999, 'both', 10, 10, '2026-01-11')")

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [
        {"rule_id": "soc", "id": "soc", "decision": "approved", "expression": "battery_soc >= 0", "rule_expression": "battery_soc >= 0"},
        {"rule_id": "speed", "id": "speed", "decision": "approved", "expression": "speed_kmh < 200", "rule_expression": "speed_kmh < 200"},
    ]
    counts = preview_split_counts(_DB(conn), "ev_telemetry", rules, "2026-01-11", 10)
    assert counts["scoped_rows"] == 11
    assert counts["clean_rows"] == 7
    assert counts["quarantine_rows"] == 4
    per = counts["per_rule_counts"]
    assert per.get("soc") == 3
    assert per.get("speed") == 1
    assert sum(per.values()) == counts["quarantine_rows"]


def test_per_rule_counts_treat_null_as_fail():
    import threading

    import duckdb

    from src.services.th_hitl_flow import preview_split_counts

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, battery_current DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(7):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, 1, ?, 10, 10, '2026-01-11')", [f"c{i}"])
    for i in range(2):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, NULL, ?, 10, 10, '2026-01-11')", [f"n{i}"])
    conn.execute("INSERT INTO ev_telemetry VALUES (-3, 1, 'soc', 10, 10, '2026-01-11')")
    conn.execute("INSERT INTO ev_telemetry VALUES (-3, NULL, 'both', 10, 10, '2026-01-11')")

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [
        {"rule_id": "soc", "id": "soc", "decision": "approved", "expression": "battery_soc >= 0", "rule_expression": "battery_soc >= 0"},
        {"rule_id": "current", "id": "current", "decision": "approved", "expression": "battery_current >= 0", "rule_expression": "battery_current >= 0"},
    ]
    counts = preview_split_counts(_DB(conn), "ev_telemetry", rules, "2026-01-11", 10)
    assert counts["scoped_rows"] == 11
    assert counts["clean_rows"] == 7
    assert counts["quarantine_rows"] == 4
    per = counts["per_rule_counts"]
    assert per.get("soc") == 2
    assert per.get("current") == 2
    assert sum(per.values()) == counts["quarantine_rows"]


def test_per_rule_counts_skip_unrunnable_expr():
    import threading

    import duckdb

    from src.services.th_hitl_flow import preview_split_counts

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(7):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, ?, 10, 10, '2026-01-11')", [f"c{i}"])
    for i in range(3):
        conn.execute("INSERT INTO ev_telemetry VALUES (-3, ?, 10, 10, '2026-01-11')", [f"b{i}"])

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    rules = [
        {"rule_id": "missing", "id": "missing", "decision": "approved", "expression": "no_such_col > 0", "rule_expression": "no_such_col > 0"},
        {"rule_id": "soc", "id": "soc", "decision": "approved", "expression": "battery_soc >= 0", "rule_expression": "battery_soc >= 0"},
    ]
    counts = preview_split_counts(_DB(conn), "ev_telemetry", rules, "2026-01-11", 10)
    assert counts["scoped_rows"] == 10
    assert counts["clean_rows"] == 7
    assert counts["quarantine_rows"] == 3
    per = counts["per_rule_counts"]
    assert "missing" not in per
    assert per.get("soc") == 3
    assert sum(per.values()) == counts["quarantine_rows"]


def test_rollback_warehouse_moves_clean_rows():
    import threading

    import duckdb

    from src.services.th_hitl_flow import commit_warehouse_split, persist_decision, rollback_last_clean

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    for i in range(7):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, ?, 10, 10, '2026-01-11')", [f"c{i}"])
    for i in range(3):
        conn.execute("INSERT INTO ev_telemetry VALUES (-3, ?, 10, 10, '2026-01-11')", [f"b{i}"])

    class _DB:
        def __init__(self, c):
            self._c = c
            self._conn_lock = threading.RLock()

        def execute(self, q, p=None):
            with self._conn_lock:
                res = self._c.execute(q, p) if p is not None else self._c.execute(q)
                try:
                    return res.fetchall()
                except Exception:
                    return []

    db = _DB(conn)
    rules = [{
        "rule_id": "qa_wh__R1",
        "id": "qa_wh__R1",
        "decision": "approved",
        "expression": "battery_soc >= 0",
        "rule_expression": "battery_soc >= 0",
    }]
    out = commit_warehouse_split(db, "ev_telemetry", rules, "2026-01-11", 10)
    persist_decision(
        db,
        dataset_key="ev_telemetry",
        calendar_day="2026-01-11",
        rule_id="qa_wh__R1",
        persona="Steward",
        action="warehouse_execute",
        details={"counts_kind": "warehouse", "snapshot_id": out.get("snapshot_id")},
    )
    assert int(conn.execute("SELECT count(*) FROM clean.ev_telemetry").fetchone()[0]) == 7
    rb = rollback_last_clean(db, "ev_telemetry", "2026-01-11", "Steward", "qa_wh__R1")
    assert rb["status"] == "superseded"
    assert rb["moved"] == 7
    assert int(conn.execute("SELECT count(*) FROM clean.ev_telemetry").fetchone()[0]) == 0

