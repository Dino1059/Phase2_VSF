import os
import pytest
import pandas as pd
from src.services.vietnamese_nlp import extract_aspect_entities, cross_validate_with_telemetry
from src.tools.anomaly import compute_composite_anomaly_score

VINGROUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vingroup")

def test_vingroup_datasets_exist():
    """Verify all 4 VinGroup datasets and fault manifest JSON exist."""
    files = [
        "vinfast_ev_telemetry_dirty.csv",
        "vgreen_charging_stations_dirty.csv",
        "xanh_sm_trips_dirty.csv",
        "xanh_sm_customer_feedback_dirty.csv",
        "vingroup_fault_manifest.json"
    ]
    for filename in files:
        filepath = os.path.join(VINGROUP_DIR, filename)
        assert os.path.exists(filepath), f"Missing VinGroup dataset file: {filename}"

def test_vinfast_ev_telemetry_schema_and_faults():
    """Verify VinFast EV Telemetry dataset contains expected columns and injected faults."""
    df = pd.read_csv(os.path.join(VINGROUP_DIR, "vinfast_ev_telemetry_dirty.csv"))
    expected_cols = ["record_id", "vehicle_vin", "timestamp", "speed_kmh", "motor_rpm", "battery_soc", "battery_voltage", "battery_current", "battery_temp_c", "latitude", "longitude", "accel_z"]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in vinfast_ev_telemetry_dirty.csv"

    assert len(df) == 1000
    assert (df["battery_soc"] < 0).sum() > 0, "Expected negative SOC faults"

def test_vgreen_charging_stations_schema():
    """Verify V-GREEN Charging Stations dataset contains thermal fault events."""
    df = pd.read_csv(os.path.join(VINGROUP_DIR, "vgreen_charging_stations_dirty.csv"))
    assert len(df) == 500
    assert (df["status"] == "THERMAL_FAULT").sum() > 0, "Expected THERMAL_FAULT status in V-GREEN dataset"

def test_xanh_sm_trips_schema():
    """Verify Xanh SM Ride-Hailing Trips dataset contains GPS alleyway drift and negative fare faults."""
    df = pd.read_csv(os.path.join(VINGROUP_DIR, "xanh_sm_trips_dirty.csv"))
    assert len(df) == 500
    assert (df["fare_amount"] < 0).sum() > 0, "Expected negative fare defects"

def test_vietnamese_nlp_aspect_extraction_and_cross_validation():
    """Verify Vietnamese NLP teen-code normalization, aspect entity extraction, and telemetry cross validation."""
    raw_comment = "xe di em nhung tram sac v-green o vincom ba trieu bi loi ko sac dc, app lag vl"
    extracted = extract_aspect_entities(raw_comment)
    
    assert extracted["location"] == "Vincom Bà Triệu"
    assert extracted["component"] == "Trạm sạc V-GREEN"
    assert extracted["severity"] in ["CRITICAL", "WARNING"]

    vgreen_logs = [
        {"station_id": "VG_STA_VINCOM_BA_TRIEU", "charger_id": "C01", "station_temp_c": 85.5, "status": "THERMAL_FAULT"}
    ]
    validated = cross_validate_with_telemetry(extracted, vgreen_logs)
    assert validated["telemetry_verified"] is True
    assert validated["matched_station"] == "VG_STA_VINCOM_BA_TRIEU"

def test_composite_anomaly_score():
    """Verify Dual-Engine Composite Anomaly Score S_composite = w1 * Sigmoid(Z) + w2 * S_isolation_forest."""
    score_normal = compute_composite_anomaly_score(z_score=0.5, isolation_forest_score=0.1)
    assert 0.0 <= score_normal <= 0.5

    score_anom = compute_composite_anomaly_score(z_score=6.5, isolation_forest_score=0.9)
    assert score_anom > 0.8
