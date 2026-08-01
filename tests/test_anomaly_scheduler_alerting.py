import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services.scheduler import scheduler_service
from src.services.alerting import alert_service, AlertSeverity, RootCauseDiagnosis
from src.tools.anomaly import ZScoreDetector, IQRDetector, IsolationForestDetector, AnomalyDetector

client = TestClient(app)


# --- 1. Scheduler Tests ---
def test_scheduler_service_crud():
    scheduler_service.start()

    # Add schedule
    sched = scheduler_service.add_schedule(
        name="Hourly Profile Job",
        dataset_name="raw_taxi_trips.csv",
        schedule_type="interval",
        interval_seconds=600,
        action="profile",
    )
    assert sched["name"] == "Hourly Profile Job"
    assert sched["schedule_type"] == "interval"
    assert "schedule_id" in sched

    # Get schedules
    schedules = scheduler_service.get_schedules()
    assert len(schedules) >= 1
    sched_ids = [s["schedule_id"] for s in schedules]
    assert sched["schedule_id"] in sched_ids

    # Delete schedule
    deleted = scheduler_service.delete_schedule(sched["schedule_id"])
    assert deleted is True

    schedules_after = scheduler_service.get_schedules()
    assert sched["schedule_id"] not in [s["schedule_id"] for s in schedules_after]


def test_scheduler_api_routes():
    # POST /api/schedules
    payload = {
        "name": "Daily Cron Check",
        "dataset_name": "raw_taxi_trips.csv",
        "schedule_type": "cron",
        "cron_expression": "0 0 * * *",
        "action": "quality_check",
    }
    res = client.post("/api/v1/schedules", json=payload, headers={"X-User-Role": "Admin"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Daily Cron Check"
    assert data["schedule_type"] == "cron"
    sched_id = data["schedule_id"]

    # GET /api/schedules
    res_get = client.get("/api/v1/schedules", headers={"X-User-Role": "Viewer"})
    assert res_get.status_code == 200
    schedules_list = res_get.json()
    assert any(s["schedule_id"] == sched_id for s in schedules_list)

    # DELETE /api/schedules/{id}
    res_del = client.delete(f"/api/v1/schedules/{sched_id}", headers={"X-User-Role": "Admin"})
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"


# --- 2. Anomaly Detector Tests ---
def test_zscore_detector():
    hist = [
        {"row_count": 100, "columns": [{"name": "fare_amount", "null_cnt": 0, "mean_val": 15.0}]},
        {"row_count": 102, "columns": [{"name": "fare_amount", "null_cnt": 0, "mean_val": 15.2}]},
        {"row_count": 98, "columns": [{"name": "fare_amount", "null_cnt": 0, "mean_val": 14.9}]},
    ]
    curr_normal = {"row_count": 101, "columns": [{"name": "fare_amount", "null_cnt": 0, "mean_val": 15.1}]}
    curr_anom = {"row_count": 500, "columns": [{"name": "fare_amount", "null_cnt": 0, "mean_val": 150.0}]}

    detector = ZScoreDetector(threshold=2.5)

    res_norm = detector.detect(curr_normal, hist)
    assert res_norm.is_anomaly is False

    res_anom = detector.detect(curr_anom, hist)
    assert res_anom.is_anomaly is True
    assert len(res_anom.anomalies_detected) > 0


def test_iqr_detector():
    hist = [
        {"row_count": 100, "duplicate_count": 2},
        {"row_count": 105, "duplicate_count": 3},
        {"row_count": 95, "duplicate_count": 1},
        {"row_count": 102, "duplicate_count": 2},
        {"row_count": 99, "duplicate_count": 2},
    ]
    curr_anom = {"row_count": 350, "duplicate_count": 50}

    detector = IQRDetector(factor=1.5)
    res = detector.detect(curr_anom, hist)
    assert res.is_anomaly is True
    assert res.detector == "IQRDetector"


def test_isolation_forest_detector_historical_threshold():
    detector = IsolationForestDetector(min_historical_runs=5)

    # <= 5 runs -> upgrade inactive message
    hist_small = [{"row_count": 100 + i, "duplicate_count": i} for i in range(4)]
    curr = {"row_count": 200, "duplicate_count": 20}

    res_small = detector.detect(curr, hist_small)
    assert res_small.is_anomaly is False
    assert "requires > 5" in res_small.message

    # > 5 runs -> active IsolationForest
    hist_large = [{"row_count": 100 + (i % 3), "duplicate_count": i % 2, "total_anomalies": i % 4} for i in range(10)]
    curr_anom = {"row_count": 500, "duplicate_count": 100, "total_anomalies": 99}

    res_large = detector.detect(curr_anom, hist_large)
    assert "executed on 10 historical runs" in res_large.message


def test_unified_anomaly_detector():
    detector = AnomalyDetector()
    hist = [{"row_count": 100, "total_anomalies": 2} for _ in range(6)]
    curr = {"row_count": 450, "total_anomalies": 80}

    res = detector.detect_all(curr, hist)
    assert "is_anomaly" in res
    assert "detectors" in res
    assert "z_score" in res["detectors"]
    assert "iqr" in res["detectors"]
    assert "isolation_forest" in res["detectors"]


# --- 3. Alerting Service Tests ---
def test_alert_service_and_root_cause():
    alert_service.clear()

    # Create root-cause diagnosis
    rc = alert_service.create_root_cause_diagnosis(
        summary="Spike in negative fare amounts",
        affected_component="fare_amount",
        suspected_cause="Upstream taximeter integer overflow",
        suggested_action="Quarantine rows where fare_amount <= 0",
        category="ARITHMETIC_MISMATCH",
        triggering_metric="min_val",
        current_value=-15.5,
        expected_baseline=2.5,
    )
    assert rc["category"] == "ARITHMETIC_MISMATCH"
    assert rc["affected_component"] == "fare_amount"

    # Create alert with CRITICAL severity and structured root-cause JSON
    alert = alert_service.create_alert(
        title="Negative Fare Integrity Failure",
        message="Critical revenue calculation error",
        severity=AlertSeverity.CRITICAL,
        source="profiler",
        root_cause=rc,
    )

    assert alert.severity == "CRITICAL"
    assert alert.status == "ACTIVE"
    assert alert.root_cause["category"] == "ARITHMETIC_MISMATCH"

    # Filter alerts
    critical_alerts = alert_service.get_alerts(severity="CRITICAL")
    assert len(critical_alerts) == 1

    # Acknowledge alert
    ack = alert_service.acknowledge_alert(alert.alert_id)
    assert ack.status == "ACKNOWLEDGED"

    # Resolve alert
    res = alert_service.resolve_alert(alert.alert_id)
    assert res.status == "RESOLVED"


def test_webhook_dispatch():
    alert = alert_service.create_alert(
        title="Test Webhook Dispatch",
        message="Testing HTTP webhook dispatch function",
        severity=AlertSeverity.HIGH,
        auto_dispatch=False,
    )

    # Dispatches to invalid local endpoint gracefully returning False without crashing
    success = alert_service.dispatch_webhook(alert, webhook_url="http://127.0.0.1:9999/nonexistent-webhook")
    assert success is False


# --- 4. X-User-Role Middleware Tests ---
def test_x_user_role_admin_permissions():
    # Admin can perform GET, POST, DELETE
    res_get = client.get("/api/v1/status", headers={"X-User-Role": "Admin"})
    assert res_get.status_code == 200

    res_post = client.post("/api/v1/reset", headers={"X-User-Role": "Admin"})
    assert res_post.status_code == 200


def test_x_user_role_steward_permissions():
    # Steward can perform GET and POST
    res_get = client.get("/api/v1/status", headers={"X-User-Role": "Steward"})
    assert res_get.status_code == 200

    res_post = client.post("/api/v1/profile", json={"data": [{"fare_amount": 10.0}]}, headers={"X-User-Role": "Steward"})
    assert res_post.status_code == 200

    # Steward cannot perform DELETE or reset
    res_reset = client.post("/api/v1/reset", headers={"X-User-Role": "Steward"})
    assert res_reset.status_code == 403

    sched_res = client.post(
        "/api/v1/schedules",
        json={"name": "Temp", "dataset_name": "raw.csv"},
        headers={"X-User-Role": "Admin"},
    )
    sched_id = sched_res.json()["schedule_id"]

    res_del = client.delete(f"/api/v1/schedules/{sched_id}", headers={"X-User-Role": "Steward"})
    assert res_del.status_code == 403

    # Cleanup with Admin
    client.delete(f"/api/v1/schedules/{sched_id}", headers={"X-User-Role": "Admin"})


def test_x_user_role_viewer_permissions():
    # Viewer can perform GET
    res_get = client.get("/api/v1/status", headers={"X-User-Role": "Viewer"})
    assert res_get.status_code == 200

    # Viewer CANNOT perform POST or DELETE
    res_post = client.post("/api/v1/profile", json={"data": []}, headers={"X-User-Role": "Viewer"})
    assert res_post.status_code == 403
    assert "read-only access" in res_post.json()["detail"]
