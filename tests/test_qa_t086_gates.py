"""QA t086 CRITICAL/HIGH gates: eval UI bind, Analyst HITL 403, HITL queue after propose, RBAC chrome."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import ROLE_PERMISSIONS, UserRole, create_access_token, is_hitl_review_write

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_eval_panel_binds_gt_fetch_and_paints_f1():
    panel = _src("frontend/src/components/workspace/EvalVsGtPanel.tsx")
    api = _src("frontend/src/services/api.ts")
    assert "evaluationApi.getGt" in panel
    assert "function normalizeGtResponse" in panel
    assert "batch.detection?.f1" in panel or "batch.detection" in panel
    assert "data-testid=\"eval-gt-metrics\"" in panel
    assert "Scoring GT pack" in panel
    assert "setErr" in panel
    assert "getGt: (signal?: AbortSignal)" in api


def test_rbac_ui_hides_write_actions_by_role():
    rules = _src("frontend/src/components/workspace/QualityRulesTab.tsx")
    ops = _src("frontend/src/pages/OperationsWorkspace.tsx")
    dash = _src("frontend/src/pages/ExecutiveDashboard.tsx")
    ingest = _src("frontend/src/components/ingestion/ResetDbButton.tsx")
    chat = _src("frontend/src/components/chat/ChatInput.tsx")
    store = _src("frontend/src/stores/authStore.ts")
    assert "canReviewRules" in store
    assert "normalizeUserRole" in store
    assert "roleCan" in store
    assert "hitl-role-gate" in rules
    assert "hitl-approve-all" in rules
    assert "canReviewRules" in rules
    assert "canReviewRules" in ops
    assert "canReviewRules" in dash
    assert "if (!isAdmin) return null" in ingest
    assert "canPropose" in chat
    assert "canExecute" in chat
    assert "Batch approve all now" in ops
    assert "canReviewRules ?" in ops or "canReviewRules &&" in ops


def test_hitl_role_gate_copy_and_role_normalize():
    store = _src("frontend/src/stores/authStore.ts")
    assert "export function normalizeUserRole" in store
    assert "data steward" in store
    assert "export function roleCan" in store
    rules = _src("frontend/src/components/workspace/QualityRulesTab.tsx")
    assert 'roleCan(s.user?.role, \'review_rules\')' in rules or 'roleCan(s.user?.role, "review_rules")' in rules
    assert "Switch persona" in rules
    assert "Steward to approve" in rules or "Steward/Admin to approve" in rules


def test_analyst_lacks_review_rules_permission():
    assert "review_rules" not in ROLE_PERMISSIONS[UserRole.ANALYST]
    assert "review_rules" in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert is_hitl_review_write("/api/v1/hitl/approve/RULE_QA_FAKE", "POST")
    assert not is_hitl_review_write("/api/v1/hitl/queue", "GET")


def test_analyst_hitl_approve_is_403():
    token = create_access_token({
        "sub": "analyst@datatrust.os",
        "user_id": "usr_analyst_01",
        "role": "Analyst",
    })
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/v1/hitl/approve/RULE_QA_FAKE", json={"approved_by": "qa"})
    assert resp.status_code == 403
    assert "approve" in resp.json()["detail"].lower() or "forbidden" in resp.json()["detail"].lower()


def test_analyst_hitl_approve_x_user_role_is_403():
    client = TestClient(app, headers={"X-User-Role": "Analyst"})
    resp = client.post("/api/v1/hitl/approve/RULE_QA_FAKE", json={"approved_by": "qa"})
    assert resp.status_code == 403


def test_admin_hitl_approve_is_403_watch_only():
    token = create_access_token({
        "sub": "admin@datatrust.os",
        "user_id": "usr_admin_01",
        "role": "Admin",
    })
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/v1/hitl/approve/RULE_QA_FAKE", json={"approved_by": "qa"})
    assert resp.status_code == 403


def test_steward_hitl_approve_still_404_for_missing_rule():
    token = create_access_token({
        "sub": "steward@datatrust.os",
        "user_id": "usr_steward_01",
        "role": "Steward",
    })
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/v1/hitl/approve/RULE_QA_FAKE", json={"approved_by": "qa"})
    assert resp.status_code == 404


def test_queue_aliases_vinfast_key_to_ev_telemetry(tmp_path, monkeypatch):
    from src.db.connection import DuckDBManager
    db_path = str(tmp_path / "qa_hitl.duckdb")
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    monkeypatch.setattr("src.api.hitl.get_db", lambda: db)
    try:
        db.execute("ALTER TABLE quality_rules ADD COLUMN dataset_key VARCHAR")
    except Exception:
        pass
    db.execute(
        "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
        "VALUES ('vinfast_ev_telemetry__R1', 'vinfast_ev_telemetry', 'soc', 'range', 'battery_soc BETWEEN 0 AND 100', 0.9, 'proposed', 'agent')"
    )
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    resp = client.get("/api/v1/hitl/queue?dataset_key=ev_telemetry")
    assert resp.status_code == 200
    ids = {p["rule_id"] for p in resp.json()["proposals"]}
    assert "vinfast_ev_telemetry__R1" in ids
    db.close()


def test_queue_hydrates_propose_trace_without_session_id_match(tmp_path, monkeypatch):
    from src.db.connection import DuckDBManager
    db_path = str(tmp_path / "qa_hitl2.duckdb")
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    monkeypatch.setattr("src.api.hitl.get_db", lambda: db)
    try:
        db.execute("ALTER TABLE quality_rules ADD COLUMN dataset_key VARCHAR")
    except Exception:
        pass
    proposals = [
        {"id": "R1_A1", "type": "range", "column": "battery_soc", "expression": "battery_soc >= 0 AND battery_soc <= 100"},
    ]
    payload = json.dumps({"dataset_key": "ev_telemetry", "proposals": proposals, "count": 1})
    db.execute(
        "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, "
        "tool_name, tool_input, tool_output, observation, tokens_used, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            f"tr-{uuid.uuid4().hex[:12]}",
            "chat-session-uuid-not-dataset-key",
            "C1_AI",
            1,
            None,
            "propose_quality_rules",
            "propose_quality_rules",
            '{"dataset_key": "ev_telemetry"}',
            payload,
            payload,
            4,
            12,
        ],
    )
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    resp = client.get("/api/v1/hitl/queue?dataset_key=ev_telemetry")
    assert resp.status_code == 200
    ids = {p["rule_id"] for p in resp.json()["proposals"]}
    assert any("R1_A1" in i for i in ids)
    db.close()


def test_mobile_drawer_and_eval_gt_endpoint_shape():
    layout = _src("frontend/src/components/layout/AppLayout.tsx")
    css = _src("frontend/src/assets/dashboard.css")
    header = _src("frontend/src/components/layout/Header.tsx")
    assert "nav-hamburger" in header
    assert "nav-open" in layout
    assert "nav-backdrop" in layout
    assert "transform: translateX(-110%)" in css
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    res = client.get("/api/v1/evaluation/gt")
    assert res.status_code == 200
    body = res.json()
    assert body["batch"]["detection"]["f1"] >= 0
    assert "precision" in body["batch"]["detection"]


def test_os_compose_sets_production_without_breaking_d086_example():
    compose = _src("docker-compose.yml")
    example = _src("docker-compose.d086.override.example.yml")
    assert "APP_ENV=production" in compose
    assert "APP_ENV=development" in example
    assert "8001:8000" in example
    profiler = _src("frontend/src/components/workspace/DataProfilerTab.tsx")
    assert "Unknown" in profiler
    assert "activeHealthScore == null" in profiler
    assert "setAggregateHealth<number>(100)" not in profiler


def test_pong_ping_llm_on_vs_off_are_distinct():
    from src.api.routes import is_pong_ping
    assert is_pong_ping("Reply PONG only. One word.")
    assert is_pong_ping("QA ping LLM-ON: reply with the word PONG only.")
    assert not is_pong_ping("list datasets")
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    off = client.post("/api/v1/chat/send", json={
        "message": "Reply PONG only. One word.",
        "session_id": f"qa-pong-off-{uuid.uuid4().hex[:8]}",
        "use_llm": False,
        "lang": "en",
    })
    on = client.post("/api/v1/chat/send", json={
        "message": "Reply PONG only. One word.",
        "session_id": f"qa-pong-on-{uuid.uuid4().hex[:8]}",
        "use_llm": True,
        "lang": "en",
    })
    assert off.status_code == 200 and on.status_code == 200
    assert off.json()["response"] != on.json()["response"]
    assert on.json()["response"].strip() == "PONG"
    assert "4 datasets" in off.json()["response"]
    assert "PONG" not in off.json()["response"]


def test_synth_off_uses_rule_det_prefix():
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    res = client.post("/api/v1/hitl/synthesize-llm", json={
        "dataset_key": "vinfast_ev_telemetry",
        "use_llm": False,
    })
    assert res.status_code == 200
    ids = [p["rule_id"] for p in res.json()["proposals"]]
    assert ids and all(i.startswith("RULE_DET_") for i in ids)
    assert not any(i.startswith("RULE_LLM_") for i in ids)


def test_remaining_medium_low_ui_gates():
    auth = _src("frontend/src/components/auth/AuthModal.tsx")
    assert "Not signed in" in auth
    assert 'htmlFor="dt-login-user"' in auth
    assert "#0369a1" in auth
    css = _src("frontend/src/assets/dashboard.css")
    assert "overflow-wrap: anywhere" in css
    assert "@media (max-width: 768px)" in css
    ops = _src("frontend/src/pages/OperationsWorkspace.tsx")
    assert "gt-pack-banner" in ops
    assert "view === 'eval' ? 'eval'" in ops
    assert "mainGroup === 'eval' ? null" in ops
    assert "Ngan GT pack: 14 incidents" in ops
    assert "minWidth: '120px'" in ops
    header = _src("frontend/src/components/layout/Header.tsx")
    assert "hud-reset-db" in header
    api = _src("frontend/src/services/api.ts")
    assert "export function isPongPing" in api
    assert "!ping && datasetKey" in api


def test_workspace_batch_approve_uses_rules_api_not_parallel_hitl():
    tab = _src("frontend/src/components/workspace/QualityRulesTab.tsx")
    start = tab.index("const handleBatchApprove")
    end = tab.index("const handleSaveEdit")
    body = tab[start:end]
    assert "rulesApi.batchApprove" in body
    assert "Promise.all" not in body
    assert "hitlApi.approve" not in body
    poll = tab[tab.index("window.setInterval"):tab.index("handleApprove")]
    assert "8000" in poll
    assert "document.hidden" in poll
    assert ", 2000)" not in poll and ",2000)" not in poll


def test_batch_approve_source_is_status_sql_not_quarantine_loop():
    src = _src("src/api/routes/rules.py")
    start = src.index("async def batch_approve_rules")
    nxt = src.find("@router.post", start + 1)
    body = src[start:nxt if nxt != -1 else None]
    assert "quarantine_violating_data_for_rule" not in body
    assert "load_dataset" not in body
    assert "asyncio.to_thread" in body
    assert "total_quarantined" in body
    assert "execute" in body
    assert "sample_size=None" not in _src("src/api/routes/rules.py").split("def quarantine_violating_data_for_rule", 1)[1][:1200]


def test_analyst_batch_approve_is_403():
    token = create_access_token({
        "sub": "analyst@datatrust.os",
        "user_id": "usr_analyst_01",
        "role": "Analyst",
    })
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/v1/rules/batch-approve", json={"rule_ids": ["RULE_QA_FAKE"]})
    assert resp.status_code == 403


def test_steward_batch_approve_marks_without_full_scan(tmp_path, monkeypatch):
    from src.db.connection import DuckDBManager

    db_path = str(tmp_path / "qa_batch_approve.duckdb")
    db = DuckDBManager(db_path=db_path)
    db.init_schema()
    for col_sql in (
        "ALTER TABLE quality_rules ADD COLUMN approved_by VARCHAR",
        "ALTER TABLE quality_rules ADD COLUMN approved_at TIMESTAMP",
    ):
        try:
            db.execute(col_sql)
        except Exception:
            pass
    monkeypatch.setattr("src.db.connection.get_db", lambda *a, **k: db)

    def _boom(*_a, **_k):
        raise AssertionError("load_dataset must not run on batch-approve")

    monkeypatch.setattr("src.services.dataset_engine.load_dataset", _boom)
    ids = [f"QA_BATCH_{i}" for i in range(3)]
    for rid in ids:
        db.execute(
            "INSERT INTO quality_rules (id, dataset_key, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
            "VALUES (?, 'ev_telemetry', 'r', 'range', 'x > 0', 0.9, 'proposed', 'agent')",
            [rid],
        )
    token = create_access_token({
        "sub": "steward@datatrust.os",
        "user_id": "usr_steward_01",
        "role": "Steward",
    })
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/v1/rules/batch-approve", json={"rule_ids": ids})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["processed_count"] == 3
    assert body["total_quarantined"] == 0
    assert body["execute"] == "off"
    rows = db.execute(
        f"SELECT status FROM quality_rules WHERE id IN ({','.join(['?'] * len(ids))})",
        ids,
    )
    assert all((r[0] or "").lower() == "approved" for r in rows)
    db.close()
