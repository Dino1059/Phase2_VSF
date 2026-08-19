import os
from fastapi.testclient import TestClient
import pytest

_SKIP_LLM = pytest.mark.skipif(
    not os.environ.get("GOOGLE_AI_API_KEY"),
    reason="Requires live LLM (GOOGLE_AI_API_KEY not set)"
)

from src.api.audit_store import AuditStore
from src.api.state_machine import StateMachine, WorkflowState
from src.main import app

client = TestClient(app, headers={"X-User-Role": "Admin"})


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ok"


def test_status_endpoint():
    response = client.get("/api/v1/status")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert "state" in data


def test_profile_endpoint():
    payload = {
        "data": [
            {"hvfhs_license_num": "HV0003", "driver_pay": 10.0, "trip_miles": 5.0},
            {"hvfhs_license_num": "HV0003", "driver_pay": None, "trip_miles": 12.0},
        ]
    }
    response = client.post("/api/v1/profile", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["row_count"] == 2
    assert data["column_count"] == 3


@_SKIP_LLM
def test_propose_rules_endpoint():
    payload = {
        "data": [
            {"hvfhs_license_num": "HV0003", "driver_pay": 10.0},
        ],
        "variant": "A1",
    }
    response = client.post("/api/v1/rules/propose", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["variant"] == "A1"
    assert len(data["rules"]) > 0


def test_execute_transform_endpoint():
    from src.db.connection import get_db
    db = get_db()
    try:
        db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, status) VALUES ('r1', 'Drop dups', 'unique', 'x', 'approved')")
    except Exception:
        pass
    payload = {
        "data": [
            {"hvfhs_license_num": "HV0003", "driver_pay": 10.0, "trip_miles": 5.0},
            {"hvfhs_license_num": "HV0003", "driver_pay": 10.0, "trip_miles": 5.0},
        ],
        "rules": [
            {
                "rule_id": "r1",
                "rule_type": "unique",
                "target_column": None,
                "action": "drop_duplicates",
                "parameters": {},
                "severity": "medium",
                "description": "Drop dups",
            }
        ],
    }
    response = client.post("/api/v1/transform/execute", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["initial_rows"] == 2
    assert data["clean_rows"] == 1
    assert data["quarantine_rows"] == 1


def test_audit_store_endpoint():
    response = client.get("/api/v1/audit/store")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


def test_reset_endpoint():
    response = client.post("/api/v1/reset")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["reset_time_sec"] < 1.0


def test_state_machine():
    sm = StateMachine()
    assert sm.current_state == WorkflowState.INIT

    sm.transition_to(WorkflowState.PROFILED)
    assert sm.current_state == WorkflowState.PROFILED

    sm.transition_to(WorkflowState.RULES_PROPOSED)
    assert sm.current_state == WorkflowState.RULES_PROPOSED

    sm.transition_to(WorkflowState.COMPILED)
    assert sm.current_state == WorkflowState.COMPILED

    sm.transition_to(WorkflowState.TESTED)
    assert sm.current_state == WorkflowState.TESTED

    sm.transition_to(WorkflowState.HITL_REVIEWED)
    assert sm.current_state == WorkflowState.HITL_REVIEWED

    sm.transition_to(WorkflowState.EXECUTED)
    assert sm.current_state == WorkflowState.EXECUTED

    sm.transition_to(WorkflowState.COMPLETED)
    assert sm.current_state == WorkflowState.COMPLETED

    sm.transition_to(WorkflowState.INIT)
    assert sm.current_state == WorkflowState.INIT

    sm.transition_to(WorkflowState.FAILED)
    assert sm.current_state == WorkflowState.FAILED

    sm.reset()
    assert sm.current_state == WorkflowState.INIT


def test_audit_store_class():
    store = AuditStore()
    store.record_event("test_evt", {"foo": "bar"})

    records = store.get_records()
    assert len(records) == 1
    assert records[0].event_type == "test_evt"

    store.clear()
    assert len(store.get_records()) == 0


def test_list_datasets_endpoint():
    response = client.get("/api/v1/datasets")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "datasets" in data
    assert len(data["datasets"]) > 0


def test_profile_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/profile?sample_size=10")
    if response.status_code == 404:
        pytest.skip(response.text)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["dataset"] == "nyc_fhvhv"
    assert "profile" in data


def test_propose_rules_for_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/propose?variant=A1&sample_size=10")
    if response.status_code == 404:
        pytest.skip(response.text)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["dataset"] == "nyc_fhvhv"
    assert data["variant"] == "A1"
    assert "rules" in data


def test_execute_rules_on_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/execute?sample_size=10")
    assert response.status_code in (200, 403, 404), response.text
    if response.status_code == 200:
        data = response.json()
        assert data["dataset"] == "nyc_fhvhv"
        assert "clean_rows" in data
        assert "quarantine_rows" in data


@_SKIP_LLM
def test_benchmark_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/benchmark?sample_size=10")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["dataset"] == "nyc_fhvhv"
    assert "results" in data


def test_dataset_not_found_endpoints():
    endpoints = [
        "/api/v1/datasets/invalid_dataset_key/profile",
        "/api/v1/datasets/invalid_dataset_key/propose",
        "/api/v1/datasets/invalid_dataset_key/execute",
        "/api/v1/datasets/invalid_dataset_key/benchmark",
    ]
    for ep in endpoints:
        resp = client.post(ep)
        assert resp.status_code == 404
        assert "Unknown dataset: invalid_dataset_key" in resp.json()["detail"]


def test_v3_static_and_ui_endpoints():
    # Test /v3 root and client-side subroute
    resp_v3 = client.get("/v3")
    assert resp_v3.status_code == 200
    assert "DataTrust OS" in resp_v3.text

    resp_v3_sub = client.get("/v3/dashboard")
    assert resp_v3_sub.status_code == 200
    assert "DataTrust OS" in resp_v3_sub.text

    # Test /vite.svg endpoint
    resp_vite = client.get("/vite.svg")
    assert resp_vite.status_code == 200

    # Test /favicon.ico endpoint
    resp_fav = client.get("/favicon.ico")
    assert resp_fav.status_code == 200

    # Test /v3/assets endpoint dynamically
    import os
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-v3", "dist", "assets")
    if os.path.exists(assets_dir):
        js_files = [f for f in os.listdir(assets_dir) if f.endswith(".js")]
        if js_files:
            resp_asset = client.get(f"/v3/assets/{js_files[0]}")
            assert resp_asset.status_code == 200


def test_websocket_endpoint_clean_connection():
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "ping"})
        data = websocket.receive_json()
        assert data == {"type": "pong"}


@_SKIP_LLM
def test_chat_send_react_loop_profile():
    response = client.post("/api/v1/chat/send", json={"message": "Profile the dataset"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert data["status"] == "completed"
    assert "session_id" in data
    assert "analysis" in data
    assert "ReAct Loop Completed" in data["analysis"]


@_SKIP_LLM
def test_chat_send_react_loop_propose_rules():
    response = client.post("/api/v1/chat/send", json={"message": "Propose data quality rules"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert data["state"] == "RULES_PROPOSED"


@_SKIP_LLM
def test_chat_send_react_loop_anomaly():
    response = client.post("/api/v1/chat/send", json={"message": "Detect anomalies in dataset"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert data["state"] == "ANOMALY_DETECTED"


@_SKIP_LLM
def test_chat_send_react_loop_diagnose():
    response = client.post("/api/v1/chat/send", json={"message": "Diagnose root cause"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert data["state"] == "DIAGNOSED"


@_SKIP_LLM
def test_chat_send_list_datasets():
    response = client.post("/api/v1/chat/send", json={"message": "how many datasets do I have?"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert "vietnam_trips_dirty" in data["response"]


def test_upload_dataset_endpoint():
    import io
    csv_content = b"col1,col2,col3\n1,2,3\n4,5,6\n7,8,9\n"
    file = ("sample_test_upload.csv", io.BytesIO(csv_content), "text/csv")
    response = client.post("/api/v1/dataset/upload", files={"file": file})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "uploaded"
    assert data["dataset_key"] == "uploaded_sample_test_upload"
    assert data["columns"] == ["col1", "col2", "col3"]
    assert data["total_rows"] == 3


def test_p0_03_authentication_deny_by_default():
    unauth_client = TestClient(app)

    # Public routes should pass without auth
    resp_health = unauth_client.get("/health")
    assert resp_health.status_code == 200

    resp_v3 = unauth_client.get("/v3")
    assert resp_v3.status_code == 200

    # Protected route without auth header -> 401
    resp_prot = unauth_client.get("/api/v1/status")
    assert resp_prot.status_code == 401

    # Protected route with invalid role -> 403
    resp_inv = unauth_client.get("/api/v1/status", headers={"X-User-Role": "InvalidRole"})
    assert resp_inv.status_code == 403

    # Protected route with explicit valid roles -> 200
    for role in ["Admin", "Analyst", "Auditor", "Viewer"]:
        resp_role = unauth_client.get("/api/v1/status", headers={"X-User-Role": role})
        assert resp_role.status_code == 200


def test_p0_02_hitl_approval_bypass_prevention():
    from src.db.connection import get_db
    db = get_db()
    try:
        db.execute("INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, status) VALUES ('unapproved_r1', 'bad_rule', 'range', 'x', 'proposed')")
    except Exception:
        pass

    payload = {
        "data": [{"hvfhs_license_num": "HV0003", "driver_pay": 10.0}],
        "rules": [
            {
                "rule_id": "unapproved_r1",
                "rule_type": "range",
                "target_column": "driver_pay",
                "action": "flag",
                "parameters": {},
                "severity": "medium",
                "description": "Unapproved rule execution test",
            }
        ],
    }
    response = client.post("/api/v1/transform/execute", json=payload)
    assert response.status_code == 403
    assert "Rule execution denied: Rule is not approved by HITL" in response.json()["detail"]


def test_p0_03_react_dynamic_tool_state_transitions():
    from src.tools.base import BaseTool
    from src.tools.chat_tools import ProfileDatasetTool, ProposeQualityRulesTool, CleanDatabaseTool
    from src.api.state_machine import WorkflowState

    assert ProfileDatasetTool.target_workflow_state == WorkflowState.PROFILED
    assert ProposeQualityRulesTool.target_workflow_state == WorkflowState.RULES_PROPOSED
    assert CleanDatabaseTool.target_workflow_state == WorkflowState.COMPLETED


def test_chat_send_tool_driven_state_transition_mocked(monkeypatch):
    from src.orchestrator.engine import ReActResult, ReActStep
    from src.api.routes import state_machine
    from src.api.state_machine import WorkflowState

    state_machine.reset()
    mock_result = ReActResult(
        task="Random message without any keyword",
        steps=[
            ReActStep(
                step_index=0,
                thought="I will profile the dataset",
                action="profile_dataset",
                observation="Profile complete",
            )
        ],
        final_answer="Profile done",
        status="completed",
    )

    from src.orchestrator.engine import ReActEngine
    monkeypatch.setattr(ReActEngine, "run", lambda self, task, context=None: mock_result)

    # Note user prompt contains NO keyword like 'profile' or 'scan'
    response = client.post("/api/v1/chat/send", json={"message": "Please do some analysis"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "completed"
    assert "session_id" in data
    assert "analysis" in data
    assert "Executed action(s) [profile_dataset]" in data["analysis"]


