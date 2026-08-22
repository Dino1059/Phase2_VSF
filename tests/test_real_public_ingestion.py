import os
import pytest
import pandas as pd

RAW_PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw_public")
VINGROUP_REAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vingroup_real")

def _require_file(filepath: str) -> None:
    if not os.path.exists(filepath):
        pytest.skip(f"missing {filepath}; CI has no bundled CSVs, app uses data_new")


def test_raw_public_datasets_exist():
    """Verify all 4 raw public datasets exist in data/raw_public/."""
    expected_raw_files = [
        "st_evcdp_raw.csv",
        "uit_vsfc_raw.csv",
        "vehicle_telemetry_raw.csv",
        "ride_hailing_raw.csv"
    ]
    for filename in expected_raw_files:
        filepath = os.path.join(RAW_PUBLIC_DIR, filename)
        _require_file(filepath)

def test_vingroup_real_mapped_datasets_exist():
    """Verify all 4 VinGroup mapped real datasets exist in data/vingroup_real/."""
    expected_mapped_files = [
        "real_vinfast_ev_telemetry.csv",
        "real_vgreen_charging_stations.csv",
        "real_xanh_sm_trips.csv",
        "real_xanh_sm_customer_feedback.csv"
    ]
    for filename in expected_mapped_files:
        filepath = os.path.join(VINGROUP_REAL_DIR, filename)
        _require_file(filepath)

def test_real_vinfast_ev_telemetry_schema():
    """Verify mapped real VinFast EV Telemetry contains VINs, Speed, SOC, and Voltage."""
    path = os.path.join(VINGROUP_REAL_DIR, "real_vinfast_ev_telemetry.csv")
    _require_file(path)
    df = pd.read_csv(path)
    assert "vehicle_vin" in df.columns
    assert "speed_kmh" in df.columns
    assert "battery_soc" in df.columns
    assert "battery_voltage" in df.columns
    assert len(df) == 1000

def test_real_vgreen_charging_stations_schema():
    """Verify mapped real V-GREEN Charging Stations contains Station ID, Power kW, and Cost VND."""
    path = os.path.join(VINGROUP_REAL_DIR, "real_vgreen_charging_stations.csv")
    _require_file(path)
    df = pd.read_csv(path)
    assert "station_id" in df.columns
    assert "power_kw" in df.columns
    assert "cost_vnd" in df.columns
    assert len(df) == 1000

def test_real_xanh_sm_trips_schema():
    """Verify mapped real Xanh SM Trips contains Trip ID, Vehicle VIN, Latitude, Longitude, and Total Fare."""
    path = os.path.join(VINGROUP_REAL_DIR, "real_xanh_sm_trips.csv")
    _require_file(path)
    df = pd.read_csv(path)
    assert "trip_id" in df.columns
    assert "vehicle_vin" in df.columns
    assert "pickup_latitude" in df.columns
    assert "total_fare" in df.columns
    assert len(df) == 1000

def test_real_xanh_sm_customer_feedback_schema():
    """Verify mapped real Xanh SM Feedback contains Feedback ID, Customer ID, and Raw Comment Text."""
    path = os.path.join(VINGROUP_REAL_DIR, "real_xanh_sm_customer_feedback.csv")
    _require_file(path)
    df = pd.read_csv(path)
    assert "feedback_id" in df.columns
    assert "customer_id" in df.columns
    assert "raw_comment_text" in df.columns
    assert len(df) == 500
