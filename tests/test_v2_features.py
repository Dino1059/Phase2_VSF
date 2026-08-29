import json
import os
import tempfile
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.agents.sub_agents import (
    AnomalyDetectorAgent,
    DiagnosisAgent,
    ProfilerAgent,
    RuleProposerAgent,
)
from src.api.middleware import RoleMiddleware, UserRole, check_role_permission
from src.main import app
from src.services.alerting import Alert, AlertService, AlertSeverity, RootCauseDiagnosis
from src.services.scheduler import SchedulerService, scheduler_service
from src.tools.anomaly import (
    AnomalyDetector,
    IQRDetector,
    IsolationForestDetector,
    ZScoreDetector,
)
from src.tools.datasource import (
    ImageSource,
    LogSource,
    PDFSource,
    StructuredSource,
)

client = TestClient(app, headers={"X-User-Role": "Admin"})


# --- 1. DataSource Abstraction & JSON/JSONL Loading Tests ---

def test_datasource_structured_csv_parquet():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("col_a,col_b\n1,foo\n2,bar\n")
        csv_path = f.name

    try:
        source = StructuredSource(csv_path)
        assert source.file_format == "csv"
        df = source.load_data()
        assert len(df) == 2
        assert list(df.columns) == ["col_a", "col_b"]

        meta = source.get_metadata()
        assert meta["source_type"] == "structured"
        assert meta["row_count"] == 2
        assert meta["column_count"] == 2
        assert len(meta["checksum_sha256"]) == 64
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)


def test_datasource_duckdb_db_loading():
    import duckdb

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(db_path)

    conn = duckdb.connect(db_path)
    conn.execute("CREATE TABLE ev_telemetry (id INTEGER, status VARCHAR)")
    conn.execute("INSERT INTO ev_telemetry VALUES (1, 'ok'), (2, 'error')")
    conn.close()

    try:
        source = StructuredSource(db_path)
        assert source.file_format == "duckdb"
        df = source.load_data()
        assert len(df) == 2
        assert list(df.columns) == ["id", "status"]
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_datasource_json_jsonl_loading():
    # Test JSON array loading
    json_records = [{"id": 1, "val": 10.5}, {"id": 2, "val": 20.0}]
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(json_records, f)
        json_path = f.name

    # Test JSONL (NDJSON) loading
    jsonl_records = [{"id": 1, "status": "ok"}, {"id": 2, "status": "error"}]
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
        for rec in jsonl_records:
            f.write(json.dumps(rec) + "\n")
        jsonl_path = f.name

    try:
        # JSON Source
        json_src = StructuredSource(json_path)
        assert json_src.file_format == "json"
        df_json = json_src.load_data()
        assert len(df_json) == 2
        assert "val" in df_json.columns

        # JSONL Source
        jsonl_src = StructuredSource(jsonl_path)
        assert jsonl_src.file_format == "jsonl"
        df_jsonl = jsonl_src.load_data()
        assert len(df_jsonl) == 2
        assert "status" in df_jsonl.columns
    finally:
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(jsonl_path):
            os.remove(jsonl_path)


def test_datasource_unstructured_stubs():
    with tempfile.NamedTemporaryFile(suffix=".pdf", mode="w", delete=False) as f:
        f.write("%PDF-1.4 dummy content")
        pdf_path = f.name

    try:
        pdf_src = PDFSource(pdf_path)
        assert pdf_src.file_format == "pdf"
        assert pdf_src.get_metadata()["source_type"] == "unstructured"
        with pytest.raises(NotImplementedError):
            pdf_src.load_data()

        log_src = LogSource(pdf_path)
        assert log_src.file_format == "log"
        with pytest.raises(NotImplementedError):
            log_src.load_data()

        img_src = ImageSource(pdf_path)
        assert img_src.file_format == "image"
        with pytest.raises(NotImplementedError):
            img_src.load_data()
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


# --- 2. APScheduler Integration Tests ---

def test_apscheduler_service_management():
    svc = SchedulerService()
    svc.start()
    assert svc._is_started

    sched_info = svc.add_schedule(
        name="Hourly Profile Test",
        dataset_name="test_data.csv",
        schedule_type="interval",
        interval_seconds=3600,
        action="profile",
    )
    assert sched_info["status"] == "active"
    assert "sched_" in sched_info["schedule_id"]

    all_scheds = svc.get_schedules()
    assert len(all_scheds) >= 1

    triggered = svc.trigger_now(sched_info["schedule_id"])
    assert triggered["run_count"] == 1

    deleted = svc.delete_schedule(sched_info["schedule_id"])
    assert deleted

    svc.shutdown(wait=False)
    assert not svc._is_started


# --- 3. Z-Score and IQR Anomaly Detection Tests ---

def test_anomaly_detectors_zscore_and_iqr():
    hist_profiles = [
        {"total_rows": 100, "total_anomalies": 5, "data_health_score": 95.0},
        {"total_rows": 102, "total_anomalies": 4, "data_health_score": 96.0},
        {"total_rows": 98, "total_anomalies": 6, "data_health_score": 94.0},
        {"total_rows": 101, "total_anomalies": 5, "data_health_score": 95.0},
    ]

    # Normal current profile
    normal_prof = {"total_rows": 100, "total_anomalies": 5, "data_health_score": 95.0}

    # Anomalous current profile
    anom_prof = {"total_rows": 500, "total_anomalies": 80, "data_health_score": 20.0}

    z_det = ZScoreDetector(threshold=3.0)
    iqr_det = IQRDetector(factor=1.5)
    unified = AnomalyDetector()

    # Test Z-score
    res_z_normal = z_det.detect(normal_prof, hist_profiles)
    assert not res_z_normal.is_anomaly

    res_z_anom = z_det.detect(anom_prof, hist_profiles)
    assert res_z_anom.is_anomaly
    assert len(res_z_anom.anomalies_detected) > 0

    # Test IQR
    res_iqr_anom = iqr_det.detect(anom_prof, hist_profiles)
    assert res_iqr_anom.is_anomaly

    # Test Unified Detector
    res_all = unified.detect_all(anom_prof, hist_profiles)
    assert res_all["is_anomaly"]
    assert res_all["aggregate_anomaly_score"] > 0.5


def test_isolation_forest_detector_fallback():
    detector = IsolationForestDetector(min_historical_runs=5)
    res = detector.detect({"total_rows": 100}, [{"total_rows": 100}] * 3)
    assert not res.is_anomaly
    assert "requires > 5" in res.message or "inactive" in res.message


# --- 4. AlertService & Root Cause Diagnosis Tests ---

def test_alert_service():
    svc = AlertService()

    rc_dict = svc.create_root_cause_diagnosis(
        summary="Negative fare anomaly in ride-hailing data",
        affected_component="fare_amount",
        suspected_cause="Upstream taximeter integer overflow",
        suggested_action="Quarantine rows where fare_amount <= 0",
        category="DATA_QUALITY",
        confidence_score=0.98,
    )
    assert rc_dict["category"] == "DATA_QUALITY"
    assert rc_dict["confidence_score"] == 0.98

    alert = svc.create_alert(
        title="High Anomaly Rate Detected",
        message="15% of records violated fare_amount boundaries.",
        severity=AlertSeverity.HIGH,
        root_cause=rc_dict,
        auto_dispatch=False,
    )
    assert alert.severity == "HIGH"
    assert alert.status == "ACTIVE"

    active_alerts = svc.get_alerts(severity="HIGH", status="ACTIVE")
    assert len(active_alerts) == 1

    svc.acknowledge_alert(alert.alert_id)
    assert svc.get_alert(alert.alert_id).status == "ACKNOWLEDGED"

    svc.resolve_alert(alert.alert_id)
    assert svc.get_alert(alert.alert_id).status == "RESOLVED"


# --- 5. Role Middleware (Admin, Steward, Viewer) Tests ---

def test_role_permissions():
    assert check_role_permission(UserRole.ADMIN, "reset")
    assert check_role_permission(UserRole.STEWARD, "execute_transform")
    assert not check_role_permission(UserRole.STEWARD, "reset")
    assert check_role_permission(UserRole.VIEWER, "read")
    assert not check_role_permission(UserRole.VIEWER, "execute_transform")


def test_role_middleware_endpoints():
    # Viewer role header -> should receive 403 on reset endpoint
    res_viewer_reset = client.post("/api/v1/reset", headers={"X-User-Role": "viewer"})
    assert res_viewer_reset.status_code == 403

    # Steward role header -> should receive 403 on reset endpoint
    res_steward_reset = client.post("/api/v1/reset", headers={"X-User-Role": "steward"})
    assert res_steward_reset.status_code == 403

    # Admin role header -> allowed to reset
    res_admin_reset = client.post("/api/v1/reset", headers={"X-User-Role": "admin"})
    assert res_admin_reset.status_code == 200


# --- 6. Specialized 4 Sub-Agents Tests ---

def test_profiler_agent():
    agent = ProfilerAgent()
    profile = agent.run(dataset_source="taxi_trips")
    assert profile.table_name == "taxi_trips"
    assert len(profile.columns) > 0


def test_rule_proposer_agent():
    agent = RuleProposerAgent()
    assert agent.name == "RuleProposerAgent"
    assert "validate" in agent.tools_whitelist
    assert agent.is_action_whitelisted("profile")


def test_anomaly_detector_agent():
    agent = AnomalyDetectorAgent()
    assert agent.name == "AnomalyDetectorAgent"
    current_p = {"table_name": "trips", "total_rows": 100, "columns": {"fare": {"null_pct": 5.0, "min_val": 0.0, "max_val": 100.0}}}
    ctx = agent.format_context(current_p)
    assert "ANOMALY DETECTOR AGENT CONTEXT" in ctx
    assert "trips" in ctx


def test_diagnosis_agent():
    agent = DiagnosisAgent()
    assert agent.name == "DiagnosisAgent"
    violations = [{"rule_id": "r1", "column": "fare_amount", "reason": "fare_amount <= 0"}]
    ctx = agent.format_context(violations=violations)
    assert "DIAGNOSIS AGENT CONTEXT" in ctx
    assert "r1" in ctx
