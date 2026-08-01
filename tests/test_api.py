from fastapi.testclient import TestClient
import pytest

from src.api.audit_store import AuditStore
from src.api.state_machine import StateMachine, WorkflowState
from src.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_status_endpoint():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
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
    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 2
    assert data["column_count"] == 3


def test_propose_rules_endpoint():
    payload = {
        "data": [
            {"hvfhs_license_num": "HV0003", "driver_pay": 10.0},
        ],
        "variant": "A1",
    }
    response = client.post("/api/v1/rules/propose", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["variant"] == "A1"
    assert len(data["rules"]) > 0


def test_execute_transform_endpoint():
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
    assert response.status_code == 200
    data = response.json()
    assert data["initial_rows"] == 2
    assert data["clean_rows"] == 1
    assert data["quarantine_rows"] == 1


def test_audit_store_endpoint():
    response = client.get("/api/v1/audit/store")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_reset_endpoint():
    response = client.post("/api/v1/reset")
    assert response.status_code == 200
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
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert len(data["datasets"]) > 0


def test_profile_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/profile?sample_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset"] == "nyc_fhvhv"
    assert "profile" in data


def test_propose_rules_for_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/propose?variant=A1&sample_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset"] == "nyc_fhvhv"
    assert data["variant"] == "A1"
    assert "rules" in data


def test_execute_rules_on_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/execute?sample_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset"] == "nyc_fhvhv"
    assert "clean_rows" in data
    assert "quarantine_rows" in data


def test_benchmark_dataset_endpoint():
    response = client.post("/api/v1/datasets/nyc_fhvhv/benchmark?sample_size=10")
    assert response.status_code == 200
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


