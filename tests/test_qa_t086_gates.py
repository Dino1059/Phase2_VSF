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
    assert "canReviewRules" in rules
    assert "canReviewRules" in ops
    assert "canReviewRules" in dash
    assert "if (!isAdmin) return null" in ingest
    assert "canPropose" in chat
    assert "canExecute" in chat
    assert "Batch approve all now" in ops
    assert "canReviewRules ?" in ops or "canReviewRules &&" in ops


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


def test_admin_hitl_approve_still_404_for_missing_rule():
    token = create_access_token({
        "sub": "admin@datatrust.os",
        "user_id": "usr_admin_01",
        "role": "Admin",
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
