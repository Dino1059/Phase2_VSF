from fastapi.testclient import TestClient
import pytest
from src.main import app

client = TestClient(app, headers={"X-User-Role": "Admin"})


# 1. Auth Router Tests
def test_auth_status_endpoint():
    response = client.get("/api/v1/auth")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "auth"


def test_auth_login_endpoint():
    payload = {"username": "admin@datatrust.os", "password": "securepassword123"}
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"] == "admin@datatrust.os"
    assert data["role"] == "Admin"


def test_auth_me_endpoint():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin@datatrust.os"
    assert "permissions" in data


def test_auth_logout_endpoint():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


# 2. Datasets Router Tests
def test_datasets_list_endpoint():
    response = client.get("/api/v1/datasets")
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert isinstance(data["datasets"], list)
    assert len(data["datasets"]) > 0


def test_dataset_metadata_endpoint():
    response = client.get("/api/v1/datasets/ev_telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "ev_telemetry"
    assert "exists" in data


# 3. Profiling Router Tests (Sync & Async HTTP 202 Accepted)
def test_profiling_sync_endpoint():
    payload = {
        "data": [
            {"license_num": "HV0003", "driver_pay": 25.0, "trip_miles": 4.2},
            {"license_num": "HV0003", "driver_pay": 30.0, "trip_miles": 5.1},
        ]
    }
    response = client.post("/api/v1/profile", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 2
    assert data["column_count"] == 3


def test_profiling_async_endpoint():
    payload = {
        "data": [
            {"license_num": "HV0003", "driver_pay": 25.0, "trip_miles": 4.2},
        ]
    }
    response = client.post("/api/v1/profile/async", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert "job_id" in data
    job_id = data["job_id"]

    # Retrieve job status
    job_resp = client.get(f"/api/v1/profile/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["job_id"] == job_id


# 4. Rules Router Tests
def test_rules_list_endpoint():
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_rules_create_endpoint():
    payload = {
        "rule_type": "null_check",
        "target_column": "driver_pay",
        "action": "quarantine",
        "severity": "critical",
        "description": "Ensure driver_pay is not null",
    }
    response = client.post("/api/v1/rules", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert "rule_id" in data


# 5. Approvals Router Tests
def test_approvals_list_endpoint():
    response = client.get("/api/v1/approvals")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_approvals_batch_endpoint():
    payload = {"rule_ids": ["mock_rule_1"], "action": "approve"}
    response = client.post("/api/v1/approvals/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


# 6. Executions Router Tests
def test_executions_list_endpoint():
    response = client.get("/api/v1/executions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 7. Benchmarks Router Tests
def test_benchmarks_info_endpoint():
    response = client.get("/api/v1/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "C0" in data["available_baselines"]


def test_benchmarks_cases_endpoint():
    response = client.get("/api/v1/benchmarks/cases")
    assert response.status_code == 200
    data = response.json()
    assert "cases" in data
    assert len(data["cases"]) > 0


# 8. Schedules Router Tests
def test_schedules_crud_endpoints():
    # 1. List initial schedules
    list_resp = client.get("/api/v1/schedules")
    assert list_resp.status_code == 200
    initial_count = len(list_resp.json())

    # 2. Create schedule
    create_payload = {
        "name": "Daily Quality Scan",
        "dataset_name": "vietnam_trips",
        "schedule_type": "interval",
        "interval_seconds": 3600,
        "action": "profile",
    }
    create_resp = client.post("/api/v1/schedules", json=create_payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["name"] == "Daily Quality Scan"
    sched_id = created["id"]

    # 3. Get single schedule
    get_resp = client.get(f"/api/v1/schedules/{sched_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == sched_id

    # 4. Delete schedule
    del_resp = client.delete(f"/api/v1/schedules/{sched_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"


# 9. CORS Policy Test
def test_cors_policy():
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") in [
        "http://localhost:3000",
        "*",
    ]
