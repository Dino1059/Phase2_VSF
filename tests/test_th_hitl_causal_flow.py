"""Must 1–5: day-scoped count, remember, rollback, persist, Steward-only HITL write."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import ROLE_PERMISSIONS, UserRole, create_access_token, is_hitl_review_write
from src.services.th_hitl_flow import day_idx_to_calendar_day, calendar_day_to_day_idx


def _steward():
    token = create_access_token({"sub": "steward@datatrust.os", "user_id": "usr_steward_01", "role": "Steward"})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def _role(role: str):
    token = create_access_token({"sub": f"{role.lower()}@datatrust.os", "user_id": f"usr_{role.lower()}_01", "role": role})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_calendar_day_is_run_id():
    assert day_idx_to_calendar_day(0) == "2026-01-01"
    assert day_idx_to_calendar_day(10) == "2026-01-11"
    assert calendar_day_to_day_idx("2026-01-11") == 10


def test_steward_only_has_hitl_write():
    assert "hitl_write" in ROLE_PERMISSIONS[UserRole.STEWARD]
    assert "hitl_write" not in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert "hitl_write" not in ROLE_PERMISSIONS[UserRole.ANALYST]
    assert "hitl_write" not in ROLE_PERMISSIONS[UserRole.AUDITOR]
    assert is_hitl_review_write("/api/v1/hitl/remember", "POST")
    assert is_hitl_review_write("/api/v1/hitl/rollback", "POST")
    assert is_hitl_review_write("/api/v1/hitl/confirm-patch/R1", "POST")
    assert not is_hitl_review_write("/api/v1/hitl/incidents", "GET")
    assert not is_hitl_review_write("/api/v1/hitl/day-count", "GET")


def test_analyst_remember_is_403():
    resp = _role("Analyst").post("/api/v1/hitl/remember", json={"dataset_key": "ev_telemetry", "rule_id": "R1", "remember": True})
    assert resp.status_code == 403


def test_analyst_warehouse_execute_is_403():
    resp = _role("Analyst").post(
        "/api/v1/hitl/execute",
        json={"dataset_key": "ev_telemetry", "calendar_day": "2026-01-11", "rule_ids": ["any"]},
    )
    assert resp.status_code == 403
    assert "Steward" in (resp.json().get("detail") or "")


def test_admin_approve_is_403_watch_only():
    resp = _role("Admin").post("/api/v1/hitl/approve/RULE_MISSING", json={"approved_by": "qa"})
    assert resp.status_code == 403


def test_steward_approve_missing_is_404():
    resp = _steward().post("/api/v1/hitl/approve/RULE_QA_MISSING_TH", json={"approved_by": "Steward"})
    assert resp.status_code == 404


def test_day_count_never_loads_full_table():
    resp = _role("Analyst").get("/api/v1/hitl/day-count?dataset_key=ev_telemetry&calendar_day=2026-01-11&day_idx=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "count" in body
    assert body.get("sample_cap", 3000) <= 3000
    assert len(body.get("preview") or []) <= 8
    assert body.get("run_id") == "2026-01-11" or body.get("calendar_day") in (None, "2026-01-11")


def test_remember_request_defaults_on():
    from src.api.hitl import RememberRequest

    assert RememberRequest(dataset_key="ev_telemetry", rule_id="R1").remember is True


def test_remember_and_expire_memory_only(tmp_path, monkeypatch):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_mem.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    out = flow.remember_rule(db, "ev_telemetry", "soc_range", "Steward", True)
    assert out["remembered"] is True
    inherited = flow.inherited_memories(db, "ev_telemetry")
    assert any(m["rule_id"] == "soc_range" for m in inherited)
    expired = flow.expire_memory(db, "ev_telemetry", "soc_range", "Steward")
    assert expired["expired"] is True
    assert flow.inherited_memories(db, "ev_telemetry") == []
    payload = flow.memory_payload(db, "ev_telemetry")
    assert payload["default_on"] is True
    assert any(m["rule_id"] == "soc_range" for m in payload["opted_out"])
    db.close()


def test_memory_default_on_without_row(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_mem_on.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    assert flow.memory_is_on(db, "ev_telemetry", "never-touched") is True
    db.close()


def test_inherit_reuses_last_hitl_next_day_unless_opted_out(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_inherit.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('R_Q5', 'ev_telemetry', 'soc', 'range', 'soc BETWEEN 0 AND 100', 0.9, 'proposed', 'agent')"
    )
    flow.persist_decision(
        db,
        dataset_key="ev_telemetry",
        calendar_day="2026-01-11",
        rule_id="R_Q5",
        persona="Steward",
        action="accept",
    )
    db.execute("UPDATE quality_rules SET status = 'proposed' WHERE id = 'R_Q5'")
    applied = flow.apply_inherited_hitl(db, "ev_telemetry", "2026-01-12")
    assert applied and applied[0]["rule_id"] == "R_Q5" and applied[0]["status"] == "approved"
    st = db.execute("SELECT status FROM quality_rules WHERE id = 'R_Q5'")[0][0]
    assert str(st).lower() == "approved"

    flow.expire_memory(db, "ev_telemetry", "R_Q5", "Steward")
    db.execute("UPDATE quality_rules SET status = 'proposed' WHERE id = 'R_Q5'")
    skipped = flow.apply_inherited_hitl(db, "ev_telemetry", "2026-01-13")
    assert skipped == []
    st2 = db.execute("SELECT status FROM quality_rules WHERE id = 'R_Q5'")[0][0]
    assert str(st2).lower() == "proposed"
    db.close()


def test_forget_does_not_undo_today(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_forget_today.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('R_TODAY', 'ev_telemetry', 'soc', 'range', 'soc >= 0', 0.9, 'approved', 'agent')"
    )
    flow.persist_decision(
        db,
        dataset_key="ev_telemetry",
        calendar_day="2026-01-11",
        rule_id="R_TODAY",
        persona="Steward",
        action="accept",
    )
    flow.expire_memory(db, "ev_telemetry", "R_TODAY", "Steward")
    st = db.execute("SELECT status FROM quality_rules WHERE id = 'R_TODAY'")[0][0]
    assert str(st).lower() == "approved"
    db.close()


def test_remember_replays_warehouse_execute_next_day(tmp_path):
    import threading

    import duckdb

    from src.services import th_hitl_flow as flow

    conn = duckdb.connect(str(tmp_path / "th_wh_replay.duckdb"))
    conn.execute("CREATE SCHEMA IF NOT EXISTS main")
    conn.execute(
        "CREATE TABLE ev_telemetry (battery_soc DOUBLE, vin VARCHAR, day_idx INTEGER, "
        "assigned_day_index INTEGER, source_ingestion_run_id VARCHAR)"
    )
    conn.execute(
        "CREATE TABLE quality_rules (id VARCHAR PRIMARY KEY, dataset_key VARCHAR, rule_name VARCHAR, "
        "rule_type VARCHAR, rule_expression VARCHAR, confidence DOUBLE, status VARCHAR, proposed_by VARCHAR)"
    )
    for i in range(7):
        conn.execute("INSERT INTO ev_telemetry VALUES (64, ?, 10, 10, '2026-01-11')", [f"c{i}"])
        conn.execute("INSERT INTO ev_telemetry VALUES (64, ?, 11, 11, '2026-01-12')", [f"d{i}"])
    for i in range(3):
        conn.execute("INSERT INTO ev_telemetry VALUES (-3, ?, 10, 10, '2026-01-11')", [f"b{i}"])
        conn.execute("INSERT INTO ev_telemetry VALUES (-3, ?, 11, 11, '2026-01-12')", [f"e{i}"])
    conn.execute(
        "INSERT INTO quality_rules VALUES ('R_WH', 'ev_telemetry', 'soc', 'range', 'battery_soc >= 0', 0.9, 'approved', 'agent')"
    )

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
    flow.ensure_th_flow_tables(db)
    day1 = flow.commit_warehouse_split(
        db,
        "ev_telemetry",
        [{"rule_id": "R_WH", "id": "R_WH", "decision": "approved", "expression": "battery_soc >= 0", "rule_expression": "battery_soc >= 0"}],
        "2026-01-11",
        10,
    )
    assert day1["warehouse_clean_rows"] == 7
    flow.persist_decision(
        db, dataset_key="ev_telemetry", calendar_day="2026-01-11", rule_id="R_WH",
        persona="Steward", action="warehouse_execute",
        details={"counts_kind": "warehouse"},
    )
    assert flow.memory_is_on(db, "ev_telemetry", "R_WH") is True
    replay = flow.apply_inherited_hitl(db, "ev_telemetry", "2026-01-12")
    assert any(a.get("status") == "warehouse" for a in replay)
    clean12 = conn.execute(
        "SELECT count(*) FROM clean.ev_telemetry WHERE assigned_day_index = 11 OR source_ingestion_run_id = '2026-01-12'"
    ).fetchone()[0]
    assert int(clean12) == 7
    flow.expire_memory(db, "ev_telemetry", "R_WH", "Steward")
    assert flow.memory_is_on(db, "ev_telemetry", "R_WH") is False
    skipped = flow.apply_inherited_hitl(db, "ev_telemetry", "2026-01-13")
    assert not any(a.get("status") == "warehouse" for a in skipped)


def test_rollback_does_not_disable_remember(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_rb_mem.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    flow.persist_decision(
        db, dataset_key="ev_telemetry", calendar_day="2026-01-11", rule_id="R_RB",
        persona="Steward", action="warehouse_execute",
        details={"counts_kind": "warehouse"},
    )
    assert flow.memory_is_on(db, "ev_telemetry", "R_RB") is True
    flow.rollback_last_clean(db, "ev_telemetry", "2026-01-11", "Steward", "R_RB")
    assert flow.memory_is_on(db, "ev_telemetry", "R_RB") is True
    db.close()


def test_rollback_supersedes_clean_decision(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_rb.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    flow.persist_decision(
        db,
        dataset_key="ev_telemetry",
        calendar_day="2026-01-11",
        rule_id="soc_range",
        persona="Steward",
        action="sandbox_clean",
        row_ids=[101, 102],
    )
    out = flow.rollback_last_clean(db, "ev_telemetry", "2026-01-11", "Steward", "soc_range")
    assert out["status"] == "superseded"
    assert out["moved"] >= 1
    left = flow.last_clean_decision(db, "ev_telemetry", "2026-01-11", "soc_range")
    assert left is None
    db.close()


def test_accept_persists_calendar_day():
    from src.db.connection import get_db
    from src.services.th_hitl_flow import ensure_th_flow_tables

    db = get_db()
    ensure_th_flow_tables(db)
    rid = "ev_telemetry__RTH_ACCEPT"
    try:
        db.execute("DELETE FROM quality_rules WHERE id = ?", [rid])
    except Exception:
        pass
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES (?, 'ev_telemetry', 'soc', 'range', 'battery_soc BETWEEN 0 AND 100', 0.9, 'proposed', 'agent')",
        [rid],
    )
    resp = _steward().post(
        f"/api/v1/hitl/approve/{rid}",
        json={"approved_by": "Steward", "dataset_key": "ev_telemetry", "calendar_day": "2026-01-11", "persona": "Steward"},
    )
    assert resp.status_code == 200
    rows = db.execute("SELECT source_ingestion_run_id, calendar_day, status FROM quality_rules WHERE id = ?", [rid])
    assert rows
    assert rows[0][0] == "2026-01-11"
    assert rows[0][1] == "2026-01-11"
    assert rows[0][2] == "approved"
    db.execute("DELETE FROM quality_rules WHERE id LIKE 'ev_telemetry__RTH%'")


def test_chat_sessions_api_filters_pair():
    sid = "th_pair_api"
    c = _steward()
    bind = c.post("/api/v1/chat/sessions", json={"session_id": sid, "dataset_key": "ev_telemetry", "calendar_day": "2026-01-11", "title": "pair"})
    assert bind.status_code == 200
    listed = c.get("/api/v1/chat/sessions?dataset_key=ev_telemetry&calendar_day=2026-01-11")
    assert listed.status_code == 200
    ids = [s.get("session_id") for s in listed.json().get("sessions") or []]
    assert sid in ids
    other = c.get("/api/v1/chat/sessions?dataset_key=trips&calendar_day=2026-01-11")
    assert sid not in [s.get("session_id") for s in other.json().get("sessions") or []]


def test_chat_sessions_filter_by_pair(tmp_path, monkeypatch):
    from src.db.connection import DuckDBManager
    from src.services.conversation_store import ConversationStore

    db = DuckDBManager(db_path=str(tmp_path / "th_chat.duckdb"))
    db.init_schema()
    store = ConversationStore(db=db)
    store.bind_session("s1", "ev_telemetry", "2026-01-11", "Day 11 EV")
    store.bind_session("s2", "trips", "2026-01-11", "Day 11 trips")
    only = store.list_sessions("ev_telemetry", "2026-01-11")
    assert [s["session_id"] for s in only] == ["s1"]
    db.close()


def test_then7_live_ingest_writes_landing_only(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services.landing_promote import ensure_landing_tables, promote_landing_day

    db = DuckDBManager(db_path=str(tmp_path / "th_landing.duckdb"))
    db.init_schema()
    ensure_landing_tables(db)
    db.execute(
        "INSERT INTO landing.ev_telemetry (record_id, vehicle_vin, day_idx, assigned_day_index, battery_soc, source_ingestion_run_id) "
        "VALUES ('LIVE_THEN7', 'VF8_THEN7', 10, 10, 77.0, 'STREAMING_WORKER')"
    )
    before = db.execute("SELECT COUNT(*) FROM main.ev_telemetry WHERE record_id = 'LIVE_THEN7'")
    assert int(before[0][0]) == 0
    land = db.execute("SELECT COUNT(*) FROM landing.ev_telemetry WHERE record_id = 'LIVE_THEN7'")
    assert int(land[0][0]) == 1
    out = promote_landing_day(db, 10)
    assert out["dataset"] == "vingroup_pilot"
    assert out["promoted"].get("ev_telemetry", 0) >= 1
    after = db.execute("SELECT COUNT(*) FROM main.ev_telemetry WHERE record_id = 'LIVE_THEN7'")
    assert int(after[0][0]) == 1
    db.close()


def test_then7_live_paths_do_not_insert_main():
    from pathlib import Path

    worker = Path("src/services/ingestion/streaming_worker.py").read_text()
    telem = Path("src/api/routes/telemetry.py").read_text()
    assert "INSERT INTO landing.ev_telemetry" in worker
    assert "INSERT INTO landing.charging_sessions" in worker
    assert "INSERT INTO main.ev_telemetry" not in worker
    assert "INSERT INTO main.charging_sessions" not in worker
    assert "INSERT INTO landing.ev_telemetry" in telem
    assert "INSERT INTO landing.charging_sessions" in telem
    assert "INSERT INTO main.ev_telemetry" not in telem
    assert "INSERT INTO main.charging_sessions" not in telem
    assert "vtaxi" not in worker.lower() and "vtaxi" not in telem.lower()


def test_leftover_init_schema_creates_landing(tmp_path):
    from src.db.connection import DuckDBManager

    db = DuckDBManager(db_path=str(tmp_path / "th_landing_schema.duckdb"))
    db.init_schema()
    schemas = db.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'landing'"
    )
    assert schemas and schemas[0][0] == "landing"
    n = db.execute("SELECT COUNT(*) FROM landing.ev_telemetry")
    assert int(n[0][0]) == 0
    db.close()


def test_leftover_seed_is_landing_then_promote():
    from pathlib import Path

    seed = Path("src/db/seed.py").read_text()
    assert "INSERT INTO landing.ev_telemetry" in seed
    assert "INSERT INTO landing.charging_sessions" in seed
    assert "INSERT INTO landing.trips" in seed
    assert "INSERT INTO landing.nlp_feedback" in seed
    assert "promote_landing_all" in seed
    assert "reset_landing_tables" in seed
    assert "INSERT INTO main.ev_telemetry" not in seed
    assert "INSERT INTO main.charging_sessions" not in seed
    assert "INSERT INTO ref.fleet_index_ref" in seed
    conn = Path("src/db/connection.py").read_text()
    assert "ensure_landing_tables" in conn


def test_leftover_vin_search_unions_landing(tmp_path, monkeypatch):
    from src.db.connection import DuckDBManager
    from src.services.algolia_search import AlgoliaSearchService

    db = DuckDBManager(db_path=str(tmp_path / "th_vin_search.duckdb"))
    db.init_schema()
    db.execute(
        "INSERT INTO landing.ev_telemetry (record_id, vehicle_vin, day_idx, assigned_day_index, battery_soc) "
        "VALUES ('LIVE_VIN_SEARCH', 'VF8-LAND-ONLY-SEARCH', 11, 11, 55.0)"
    )
    monkeypatch.setattr("src.services.algolia_search.get_db", lambda: db)
    hits = AlgoliaSearchService()._fallback_search("vf8-land-only-search", entity_type="vehicle", limit=5)
    assert any(h.get("entity_id") == "VF8-LAND-ONLY-SEARCH" for h in hits)
    db.close()


def test_promote_landing_is_noop_without_landing():
    from src.db.connection import get_db
    from src.services.landing_promote import promote_landing_day

    out = promote_landing_day(get_db(), 10)
    assert out["dataset"] == "vingroup_pilot"
    assert out["status"] in ("ok", "skipped")
    assert isinstance(out["promoted"], dict)


def test_then6_search_and_then8_hide_are_wired():
    from pathlib import Path

    header = Path("frontend/src/components/layout/Header.tsx").read_text()
    assert "searchHitWorkspacePath" in header
    assert "ws-rules" in header
    assert "/operations/alerts" in header  # ops routes kept
    empty = header.split("if (!q)", 1)[1].split("const matchedOps", 1)[0]
    assert "bindWs" in empty and "workspaceHref" in header
    assert "path: op.path" not in empty
    assert "def axisFromSearch" in header or "function axisFromSearch" in header
    assert "location.search" in header and "axisFromLocation" in header
    cal = Path("frontend/src/lib/calendarDay.ts").read_text()
    assert "tab-rules" in cal and "tab-split" in cal
    assert "queryFromWindow" in cal and "axisFromLocation" in cal
    ws = Path("frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "tabParam" in ws
    assert "chat-hitl-hidden" in ws
    assert "ingestionApi.promote" in ws
    chat = Path("frontend/src/components/chat/ChatInput.tsx").read_text()
    assert "canHitlWrite" in chat
    assert "chat-clean-chip-steward" in chat
    chip_gate = chat.split("chat-clean-chip-steward", 1)[0][-500:]
    assert "canHitlWrite" in chip_gate
    chip = chat.split("chat-clean-chip-steward", 1)[1].split("</button>", 1)[0]
    assert "handleWarehouseExecute" in chat
    assert "hitlApi.executeWarehouse" in chat
    assert "executePrompt" not in chip
    assert "clean database" not in chip
    assert "Làm sạch dữ liệu" not in chip
    ops = Path("frontend/src/pages/OperationsWorkspace.tsx").read_text()
    assert "incidentStories(storyDataset" in ops
    assert "axisFromLocation" in ops
    ing = Path("src/api/ingestion.py").read_text()
    assert ing.count("promote_landing_day") >= 3


def test_watch_roles_cannot_hitl_write():
    body = {"dataset_key": "ev_telemetry", "calendar_day": "2026-01-11", "rule_id": "soc_range", "actor": "qa"}
    for role in ("Admin", "Auditor", "Analyst"):
        rb = _role(role).post("/api/v1/hitl/rollback", json=body)
        assert rb.status_code == 403, role
        assert "Steward" in (rb.json().get("detail") or "")
        rem = _role(role).post("/api/v1/hitl/remember", json={"dataset_key": "ev_telemetry", "rule_id": "R1", "remember": True})
        assert rem.status_code == 403, role
        patch = _role(role).post("/api/v1/hitl/confirm-patch/R1", json={"rule_id": "R1", "rule_expression": "x > 0"})
        assert patch.status_code == 403, role


def test_expire_memory_does_not_undo_today(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_expire.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    did = flow.persist_decision(
        db,
        dataset_key="ev_telemetry",
        calendar_day="2026-01-11",
        rule_id="soc_range",
        persona="Steward",
        action="approve",
        row_ids=[1],
    )
    flow.remember_rule(db, "ev_telemetry", "soc_range", "Steward", True)
    flow.expire_memory(db, "ev_telemetry", "soc_range", "Steward")
    left = db.execute("SELECT id, status FROM hitl_decisions WHERE id = ?", [did])
    assert left and left[0][1] == "active"
    db.close()


def test_latest_session_follows_table_day_pair(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services.conversation_store import ConversationStore

    db = DuckDBManager(db_path=str(tmp_path / "th_latest.duckdb"))
    db.init_schema()
    store = ConversationStore(db=db)
    store.bind_session("old", "ev_telemetry", "2026-01-11", "old")
    store.bind_session("new", "ev_telemetry", "2026-01-11", "new")
    store.bind_session("other", "trips", "2026-01-11", "trips")
    latest = store.latest_session("ev_telemetry", "2026-01-11")
    assert latest and latest["session_id"] == "new"
    assert store.latest_session("trips", "2026-01-12") is None
    db.close()


def test_incident_stories_are_causal_not_signal_dump():
    resp = _role("Analyst").get("/api/v1/hitl/incidents?dataset_key=ev_telemetry&calendar_day=2026-01-11")
    assert resp.status_code == 200
    body = resp.json()
    assert "incidents" in body
    for story in body["incidents"][:5]:
        assert "entity_id" in story
        assert "copy" in story
        assert "suspected" in story["copy"]
        assert "because" in story["copy"]
        assert "recommend" in story["copy"]
        blob = " ".join(str(v) for v in story["copy"].values()).lower()
        assert "nghi" in blob
        assert "vì" in blob or "vi " in blob
        assert "kiểm tra" in blob
        assert "sentence" in story["copy"]
        assert "(table, day)" not in blob
        assert "tab-rules" in (story.get("rule_href") or "")
        assert "tab-split" in (story.get("quarantine_href") or "")


def test_story_record_omits_placeholder_without_day():
    from src.services.th_hitl_flow import _story_record

    empty = _story_record("ev_telemetry", "", "VIN-A", "soc")
    assert "(table, day)" not in empty["copy"]["recommend"]
    assert empty["calendar_day"] == ""
    filled = _story_record("ev_telemetry", "2026-01-11", "VIN-A", "soc")
    assert "2026-01-11" in filled["copy"]["recommend"]
    assert filled["calendar_day"] == "2026-01-11"


def test_workspace_binding_reads_json_after_colon_in_label():
    from src.orchestrator.prompt_intent import workspace_binding

    msgs = [
        {"role": "system", "content": "You are DataTrust OS Agent"},
        {"role": "user", "content": "why is VF8VNF_0001 quarantined?"},
        {
            "role": "system",
            "content": 'Workspace binding (not a user request): {"dataset_key": "ev_telemetry", "active_day": 10, "calendar_day": "2026-01-11"}',
        },
    ]
    ctx = workspace_binding(msgs)
    assert ctx.get("dataset_key") == "ev_telemetry"
    assert ctx.get("calendar_day") == "2026-01-11"
    assert ctx.get("active_day") == 10


def test_day_count_sql_is_count_star_not_full_scan():
    from pathlib import Path

    src = Path("src/services/th_hitl_flow.py").read_text()
    assert "SELECT COUNT(*)" in src
    assert "Never SELECT * the warehouse" in src
    assert "SANDBOX_SAMPLE_CAP" in src


def test_promote_endpoint_noop_ok():
    resp = _role("Analyst").post("/api/v1/ingestion/promote", json={"day_idx": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("dataset") == "vingroup_pilot"
    assert body.get("status") in ("ok", "skipped")


def test_steward_remember_and_empty_rollback():
    rem = _steward().post("/api/v1/hitl/remember", json={"dataset_key": "ev_telemetry", "rule_id": "RTH_HARDEN", "actor": "Steward"})
    assert rem.status_code == 200
    assert rem.json().get("remembered") is True
    rb = _steward().post("/api/v1/hitl/rollback", json={"dataset_key": "no_such_ds", "calendar_day": "2026-01-11", "actor": "Steward"})
    assert rb.status_code == 200
    assert rb.json().get("status") in ("empty", "superseded")


def test_approved_rules_do_not_leak_null_dataset(tmp_path):
    from src.db.connection import DuckDBManager
    from src.tools.chat_tools import approved_rules_for_clean

    db = DuckDBManager(db_path=str(tmp_path / "th_null.duckdb"))
    db.init_schema()
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('orphan_rule', NULL, 'orphan', 'range', 'x > 0', 0.9, 'approved', 'agent')"
    )
    assert approved_rules_for_clean(db, "unknown_ds") == []
    db.close()


def test_must_ui_still_binds_axis():
    from pathlib import Path

    ws = Path("frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "bindAxis" in ws
    assert "|| calendarDay" in ws
    store = Path("frontend/src/stores/pipelineStore.ts").read_text()
    reset = store.split("resetPipeline", 1)[1].split("}));", 1)[0]
    assert "sourceIngestionRunId: state.sourceIngestionRunId" in reset
    assert "selectedDayIdx: state.selectedDayIdx" in reset
    assert "run-id-chip" in Path("frontend/src/components/chat/SourceIngestionRunFilter.tsx").read_text()
    bar = Path("frontend/src/components/ingestion/DayTimelineBar.tsx").read_text()
    assert "workspaceHref" in bar and "ING-" not in bar
    store = Path("frontend/src/stores/authStore.ts").read_text()
    assert "hitl_write" in store
    assert "canHitlWrite" in store
    rules = Path("frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    assert "canHitlWrite" in rules
    assert "Remember" in rules or "remember" in rules
    assert "Forget" in rules
    assert "optedOut" in rules
    assert "data-remembered" in rules
    assert "rollback" in rules.lower()
    assert 'data-testid="hitl-preview-before-approve"' in rules
    assert 'data-testid="hitl-sandbox-preview"' in rules
    assert 'data-testid="btn-rule-preview"' in rules
    chat = Path("frontend/src/components/chat/ChatInput.tsx").read_text()
    assert "hitlApi.executeWarehouse" in chat
    assert "handleWarehouseExecute" in chat
    msg = Path("frontend/src/components/chat/AgentMessage.tsx").read_text()
    assert 'data-testid="chat-edit-rule-apply"' in msg
    assert 'data-testid="chat-edit-rule-edit-myself"' in msg
    ops = Path("frontend/src/pages/OperationsWorkspace.tsx").read_text()
    assert "alert-causal-sentence" in ops
    assert "alert-link-rule" in ops
    assert "alert-link-quarantine" in ops
    assert "btn-rule-link-alerts" in rules
    assert "btn-rule-link-quarantine" in rules
    split = Path("frontend/src/components/workspace/SplitDbQuarantineTab.tsx").read_text()
    assert "quarantine-row-story" in split
    assert "quarantine-link-rule" in split


def test_edit_rule_heuristic_ignores_context_dataset_json():
    import json

    from src.orchestrator.prompt_intent import CANNED_INVENTORY, asks_dataset_inventory, heuristic_user_task
    from src.services.llm import LLMService

    ctx = 'Context: {"dataset_key": "ev_telemetry", "lang": "en", "session_id": "x"}'
    task = (
        "Task: Use dataset_key='ev_telemetry' for every dataset tool call.\n"
        "User request: can you edit rule: longitude range for me?"
    )
    messages = [
        {"role": "system", "content": "You are ReAct."},
        {"role": "user", "content": task},
        {"role": "user", "content": ctx},
    ]
    joined = heuristic_user_task(messages)
    assert "longitude" in joined
    assert "dataset_key" not in joined
    assert not asks_dataset_inventory(joined)
    assert not asks_dataset_inventory(ctx)
    assert not asks_dataset_inventory("can you edit rule: longitude range for me?")
    assert asks_dataset_inventory("how many datasets do I have?")

    resp = LLMService(use_llm=False)._heuristic_fallback(messages)
    blob = (resp.content or "") + json.dumps(resp.tool_calls or [])
    assert CANNED_INVENTORY not in blob
    assert "4 datasets" not in blob
    assert "sandbox_preview" in blob


def test_edit_rule_chat_send_does_not_list_datasets(monkeypatch):
    import uuid as _uuid

    from src.orchestrator.prompt_intent import CANNED_INVENTORY

    fake = {
        "preview": True,
        "write": False,
        "execute": "off",
        "promoted": False,
        "dataset_key": "ev_telemetry",
        "query": "longitude range",
        "rules": [{
            "rule_id": "ev_telemetry__longitude_range",
            "rule_name": "longitude range",
            "rule_expression": "longitude BETWEEN -180 AND 180",
        }],
        "day_count": {"count": 12, "table": "ev_telemetry", "calendar_day": "2026-01-11"},
        "sampled_rows": 8,
        "clean_rows": 3,
        "quarantine_rows": 5,
        "warehouse_clean_rows": 0,
        "note": "preview only, no write",
    }
    monkeypatch.setattr("src.tools.chat_tools.run_sandbox_preview", lambda *a, **k: fake)
    resp = _steward().post(
        "/api/v1/chat/send",
        json={
            "message": "can you edit rule: longitude range for me?",
            "session_id": f"th-edit-rule-{_uuid.uuid4().hex[:8]}",
            "dataset_key": "ev_telemetry",
            "use_llm": False,
            "lang": "en",
            "active_day": 10,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    text = body.get("response") or ""
    analysis = (body.get("analysis") or "").lower()
    assert "4 datasets" not in text
    assert CANNED_INVENTORY not in text
    assert "list_datasets" not in analysis
    assert "algolia" not in analysis
    assert "profile_dataset" not in analysis
    assert "sandbox_preview" in analysis
    assert "Sandbox preview" in text or "preview only" in text.lower()
    assert "Clean Warehouse = 0" in text
    assert "Apply pending" in text


def _react_shaped(user_request: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are DataTrust OS Agent.\n"
                "- profile_dataset: Scans dataset schema.\n"
                "- list_datasets: Lists all available registered datasets in DataTrust OS repository.\n"
            ),
        },
        {
            "role": "user",
            "content": (
                "Task: Use dataset_key='ev_telemetry' for every dataset tool call.\n"
                "Auto Profile + Anomaly L1–L4 + Propose (stop at HITL).\n"
                f"User request: {user_request}"
            ),
        },
        {"role": "user", "content": 'Context: {"dataset_key": "ev_telemetry", "lang": "en", "session_id": "x"}'},
    ]


def _assert_no_inventory_tools(text: str, analysis: str, blob: str = "") -> None:
    hay = f"{text}\n{analysis}\n{blob}".lower()
    assert "list_datasets" not in hay
    assert "profile_dataset" not in hay
    assert "4 datasets" not in hay
    assert "you have **" not in hay
    assert "datasets** registered" not in hay
    assert "available enterprise datasets" not in hay
    assert "select or upload" not in hay


def test_smalltalk_classifier_does_not_swallow_real_tasks():
    from src.orchestrator.prompt_intent import is_capabilities_prompt, is_smalltalk_prompt

    assert is_smalltalk_prompt("hi can you reply me?")
    assert is_capabilities_prompt("what can you do?")
    assert not is_smalltalk_prompt("hi, profile the dataset")
    assert not is_smalltalk_prompt("how many datasets do I have?")
    assert not is_smalltalk_prompt("can you edit rule: longitude range for me?")


def test_greeting_heuristic_ignores_tool_catalog_and_context():
    import json

    from src.orchestrator.prompt_intent import (
        CANNED_INVENTORY,
        asks_dataset_inventory,
        heuristic_user_task,
        is_smalltalk_prompt,
    )
    from src.services.llm import LLMService

    user = "hi can you reply me?"
    messages = _react_shaped(user)
    joined = heuristic_user_task(messages)
    assert "hi can you reply" in joined
    assert "profile_dataset" not in joined
    assert "dataset_key" not in joined
    assert is_smalltalk_prompt(user)
    assert not asks_dataset_inventory(joined)
    resp = LLMService(use_llm=False)._heuristic_fallback(messages)
    blob = (resp.content or "") + json.dumps(resp.tool_calls or [])
    assert CANNED_INVENTORY not in blob
    _assert_no_inventory_tools(resp.content or "", "", blob)
    assert not (resp.tool_calls or [])


def test_capabilities_heuristic_no_inventory():
    import json

    from src.orchestrator.prompt_intent import CANNED_INVENTORY, is_capabilities_prompt, is_smalltalk_prompt
    from src.services.llm import LLMService

    user = "what can you do?"
    assert is_capabilities_prompt(user)
    assert is_smalltalk_prompt(user)
    resp = LLMService(use_llm=False)._heuristic_fallback(_react_shaped(user))
    blob = (resp.content or "") + json.dumps(resp.tool_calls or [])
    text = (resp.content or "").lower()
    assert CANNED_INVENTORY not in blob
    _assert_no_inventory_tools(resp.content or "", "", blob)
    assert not (resp.tool_calls or [])
    assert any(k in text for k in ("hitl", "preview", "rule", "steward", "execute"))


def test_greeting_chat_send_does_not_run_dataset_tools(monkeypatch):
    import uuid as _uuid

    from src.orchestrator.prompt_intent import CANNED_INVENTORY

    def boom(self, *a, **k):
        raise AssertionError(f"{self.name} must not run for greeting")

    monkeypatch.setattr("src.tools.chat_tools.ProfileDatasetTool.execute", boom)
    monkeypatch.setattr("src.tools.chat_tools.ListDatasetsTool.execute", boom)
    sid = f"th-hi-{_uuid.uuid4().hex[:8]}"
    resp = _steward().post(
        "/api/v1/chat/send",
        json={
            "message": "hi can you reply me?",
            "session_id": sid,
            "dataset_key": "ev_telemetry",
            "use_llm": False,
            "lang": "en",
            "active_day": 10,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    text = body.get("response") or ""
    analysis = (body.get("analysis") or "").lower()
    assert CANNED_INVENTORY not in text
    _assert_no_inventory_tools(text, analysis)
    assert "auto profile" not in text.lower()
    assert text.strip()


def test_capabilities_chat_send_does_not_run_dataset_tools(monkeypatch):
    import uuid as _uuid

    from src.orchestrator.prompt_intent import CANNED_INVENTORY

    def boom(self, *a, **k):
        raise AssertionError(f"{self.name} must not run for capabilities")

    monkeypatch.setattr("src.tools.chat_tools.ProfileDatasetTool.execute", boom)
    monkeypatch.setattr("src.tools.chat_tools.ListDatasetsTool.execute", boom)
    sid = f"th-why-{_uuid.uuid4().hex[:8]}"
    resp = _steward().post(
        "/api/v1/chat/send",
        json={
            "message": "what can you do?",
            "session_id": sid,
            "dataset_key": "ev_telemetry",
            "use_llm": False,
            "lang": "en",
            "active_day": 10,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    text = body.get("response") or ""
    analysis = (body.get("analysis") or "").lower()
    assert CANNED_INVENTORY not in text
    _assert_no_inventory_tools(text, analysis)
    assert "auto profile" not in text.lower()
    assert any(k in text.lower() for k in ("hitl", "preview", "rule", "steward", "execute"))


def test_chat_task_is_user_utterance_not_auto_profile():
    from pathlib import Path

    send = Path("src/api/routes/__init__.py").read_text().split("async def send_chat_message", 1)[1]
    assert "task = request.message" in send
    assert "Auto Profile" not in send.split("@router.get", 1)[0]
    assert "Use dataset_key=" not in send.split("with sentry_ctx", 1)[0]
    engine = Path("src/orchestrator/engine.py").read_text()
    assert '{"role": "user", "content": task}' in engine
    assert "Workspace binding (not a user request)" in engine
    assert "history=_llm_turns(prior)" in send


def test_why_question_heuristic_uses_user_text_not_catalog():
    import json

    from src.orchestrator.prompt_intent import CANNED_INVENTORY
    from src.services.llm import LLMService

    resp = LLMService(use_llm=False)._heuristic_fallback(_react_shaped("why is VF8VNF_0001 quarantined?"))
    blob = (resp.content or "") + json.dumps(resp.tool_calls or [])
    assert CANNED_INVENTORY not in blob
    assert "4 datasets" not in blob
    assert "vf8vnf_0001" in (resp.content or "").lower()
    assert not (resp.tool_calls or [])


def test_explicit_list_datasets_still_canned():
    from src.orchestrator.prompt_intent import CANNED_INVENTORY
    from src.services.llm import LLMService

    resp = LLMService(use_llm=False)._heuristic_fallback(_react_shaped("how many datasets do I have?"))
    assert CANNED_INVENTORY in (resp.content or "")


def test_assistant_profile_mention_does_not_force_profile_tool():
    import json

    from src.orchestrator.prompt_intent import CANNED_INVENTORY, last_user_utterance
    from src.services.llm import LLMService

    messages = [
        {"role": "system", "content": "- profile_dataset: Scans dataset schema.\n- list_datasets: Lists datasets."},
        {"role": "user", "content": "hi can you reply me?"},
        {"role": "assistant", "content": "I can profile a dataset, scan L1–L4 anomalies, propose quality rules."},
        {"role": "user", "content": "why is VF8VNF_0001 quarantined today?"},
        {"role": "system", "content": 'Workspace binding (not a user request): {"dataset_key": "ev_telemetry"}'},
    ]
    assert "vf8vnf_0001" in last_user_utterance(messages)
    assert "profile" not in last_user_utterance(messages)
    resp = LLMService(use_llm=False)._heuristic_fallback(messages)
    blob = (resp.content or "") + json.dumps(resp.tool_calls or [])
    assert CANNED_INVENTORY not in blob
    assert not (resp.tool_calls or [])
    assert "vf8vnf_0001" in (resp.content or "").lower()


def test_chat_send_why_does_not_run_dataset_tools(monkeypatch):
    import uuid as _uuid

    from src.orchestrator.prompt_intent import CANNED_INVENTORY

    def boom(self, *a, **k):
        raise AssertionError(f"{self.name} must not run for a why-question")

    monkeypatch.setattr("src.tools.chat_tools.ProfileDatasetTool.execute", boom)
    monkeypatch.setattr("src.tools.chat_tools.ListDatasetsTool.execute", boom)
    resp = _steward().post(
        "/api/v1/chat/send",
        json={
            "message": "why is VF8VNF_0001 quarantined today?",
            "session_id": f"th-whyq-{_uuid.uuid4().hex[:8]}",
            "dataset_key": "ev_telemetry",
            "use_llm": False,
            "lang": "en",
            "active_day": 10,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    text = (body.get("response") or "").lower()
    analysis = (body.get("analysis") or "").lower()
    assert CANNED_INVENTORY not in (body.get("response") or "")
    _assert_no_inventory_tools(body.get("response") or "", analysis)
    assert "vf8vnf_0001" in text
    assert "list_datasets" not in analysis
    assert "profile_dataset" not in analysis


def test_chat_send_why_after_hi_does_not_profile(monkeypatch):
    import uuid as _uuid

    def boom(self, *a, **k):
        raise AssertionError(f"{self.name} must not run after greeting history")

    monkeypatch.setattr("src.tools.chat_tools.ProfileDatasetTool.execute", boom)
    monkeypatch.setattr("src.tools.chat_tools.ListDatasetsTool.execute", boom)
    sid = f"th-hist-{_uuid.uuid4().hex[:8]}"
    payload = {"session_id": sid, "dataset_key": "ev_telemetry", "use_llm": False, "lang": "en", "active_day": 10}
    hi = _steward().post("/api/v1/chat/send", json={**payload, "message": "hi can you reply me?"})
    assert hi.status_code == 200
    why = _steward().post("/api/v1/chat/send", json={**payload, "message": "why is VF8VNF_0001 quarantined today?"})
    assert why.status_code == 200, why.text
    body = why.json()
    analysis = (body.get("analysis") or "").lower()
    text = (body.get("response") or "").lower()
    assert "profile_dataset" not in analysis
    assert "list_datasets" not in analysis
    assert "4 datasets" not in text
    assert "vf8vnf_0001" in text


def test_preview_before_approve_does_not_write_warehouse():
    from pathlib import Path

    src = Path("src/api/hitl.py").read_text()
    approve = src.split("async def approve_rule", 1)[1].split("async def reject_rule", 1)[0]
    assert '"quarantined_count": 0' in approve
    assert '"execute": "off"' in approve
    preview = src.split("async def sandbox_preview_endpoint", 1)[1].split("async def sandbox_clean", 1)[0]
    assert "run_sandbox_preview" in preview
    get_fn = src.split("async def get_sandbox_run", 1)[1].split("async def get_history", 1)[0]
    assert "load_sandbox_preview_meta" in get_fn
    assert "if not q_rows and not meta" in get_fn
    assert 'kind == "warehouse"' in get_fn
    assert "else 0" in get_fn
    assert "calendar_day=day" in src.split("async def sandbox_clean", 1)[1].split("async def get_sandbox_run", 1)[0]
    tools = Path("src/tools/chat_tools.py").read_text()
    run = tools.split("def run_sandbox_preview", 1)[1].split("class SandboxPreviewInput", 1)[0]
    assert '"warehouse_clean_rows": 0' in run
    assert '"write": False' in run


def test_incident_stories_exclusive_entity_and_primary_rule(tmp_path):
    import json

    from src.api.quarantine_api import _ensure_main_quarantine_table
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_inc.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    _ensure_main_quarantine_table(db)
    day = {"assigned_day_index": 10, "day_idx": 10, "source_ingestion_run_id": "2026-01-11"}
    rows = [
        ("q1", "soc", {**day, "vehicle_vin": "VIN-A"}),
        ("q2", "soc", {**day, "vehicle_vin": "VIN-B"}),
        ("q3", "speed", {**day, "vehicle_vin": "VIN-A"}),
        ("q4", "soc", {**day, "vehicle_vin": "VIN-A"}),
    ]
    for i, (qid, rid, orig) in enumerate(rows, start=1):
        db.execute(
            "INSERT INTO main.quarantine (id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data) "
            "VALUES (?, 'execute:ev_telemetry:2026-01-11', 'ev_telemetry', ?, ?, 'execute', 'FAILED_PRIMARY_RULE', ?)",
            [qid, i, rid, json.dumps(orig)],
        )
    stories = flow.incident_stories(db, "ev_telemetry", "2026-01-11", 10)
    keys = {(s["entity_id"], s["primary_rule_id"]) for s in stories}
    assert ("VIN-A", "soc") in keys
    assert ("VIN-B", "soc") in keys
    assert ("VIN-A", "speed") in keys
    tuples = [(s["dataset_key"], s["calendar_day"], s["entity_id"], s["primary_rule_id"]) for s in stories]
    assert len(tuples) == len(set(tuples))
    reply = flow.causal_reply_for_ask(db, "ev_telemetry", "2026-01-11", "VIN-A")
    assert "nghi" in reply.lower()
    assert "vin-a" in reply.lower()
    assert "tab-rules" in reply
    miss = flow.causal_reply_for_ask(db, "ev_telemetry", "2026-01-11", "VF8VNF_0001")
    assert "không khớp" in miss.lower()
    assert "VF8VNF_0001" in miss
    assert "Xe VF8VNF_0001 nghi" not in miss
    assert "VIN-A/" in miss
    db.close()


def test_incident_stories_use_cluster_when_rule_missing(tmp_path):
    from src.db.connection import DuckDBManager
    from src.services import th_hitl_flow as flow

    db = DuckDBManager(db_path=str(tmp_path / "th_inc_cluster.duckdb"))
    db.init_schema()
    flow.ensure_th_flow_tables(db)
    db.execute(
        "INSERT INTO incidents (incident_id, project_id, status, entity_ids, admission_reason, severity, created_at) "
        "VALUES ('INC-CLU', 'proj', 'OPEN', '[\"VIN-C\"]', 'quality violation', 'HIGH', CURRENT_TIMESTAMP)"
    )
    stories = flow.incident_stories(db, "ev_telemetry", "2026-01-11", 10)
    assert stories
    assert stories[0]["entity_id"] == "VIN-C"
    assert stories[0]["primary_rule_id"] == "cluster"
    assert "suspected" in stories[0]["copy"]
    db.close()


def test_leftover_gates_empty_state_count_overlay():
    from pathlib import Path

    flow_src = Path("src/services/th_hitl_flow.py").read_text()
    assert "_causal_empty_state" in flow_src
    ingest = Path("src/api/ingestion.py").read_text()
    assert "1250 if is_act" not in ingest
    assert "_warehouse_counts_by_day" in ingest
    tab = Path("frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    assert "includeActive: true" in tab
    assert "hitl-missing-incident-rule" in tab
    css = Path("frontend/src/assets/styles.css").read_text()
    assert "width: var(--right-panel-width" in css
    assert "z-index: 40" in css
    hud = Path("frontend/src/components/chat/SourceIngestionRunFilter.tsx").read_text()
    assert "1,250 rows" not in hud
    ops = Path("frontend/src/pages/OperationsWorkspace.tsx").read_text()
    assert "Ngan GT pack" not in ops
