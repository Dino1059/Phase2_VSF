"""
DataTrust OS: Lane A L3 Relational Calibration Test Suite
Verifies 100% recall and high precision on all 77 L3 row-level faults across 2 datasets:
- ride_hailing_xanh_sm_trips: F6_GPS_Alleyway_Drift (69 faults)
- acn_charging_mapped: F14_DurationEnergy_Mismatch (8 faults)
Total L3 row-level faults = 69 + 8 = 77 faults.
"""

from pathlib import Path
import pandas as pd
import pytest

from src.detectors.detector_suite import L1toL4DetectorSuite
from tests.benchmarks.test_fault_manifest_oracle import FaultManifestOracle

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data" / "vingroup_pii_faulty_testset_3zone"


@pytest.fixture(scope="module")
def oracle():
    return FaultManifestOracle()


@pytest.fixture(scope="module")
def suite():
    # Test L3 relational detectors
    return L1toL4DetectorSuite()


def test_l3_trips_f6_gps_alleyway_drift(oracle, suite):
    """Verifies F6 (69) GPS alleyway drift in ride_hailing_xanh_sm_trips."""
    csv_path = DATA_DIR / "ride_hailing_xanh_sm_trips.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    results = suite.evaluate_records("ride_hailing_xanh_sm_trips", df, pk_col="trip_id")

    detected_by_family = {
        "F6_GPS_Alleyway_Drift": set(),
    }

    for idx, row in df.iterrows():
        eval_id = str(row["trip_id"])
        res = results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.layer == "L3" and sig.metric_or_relationship == "gps_coordinates_bounding_box":
                detected_by_family["F6_GPS_Alleyway_Drift"].add(idx)

    metrics = oracle.match_row_signals("ride_hailing_xanh_sm_trips", detected_by_family, len(df))

    f6_m = metrics["F6_GPS_Alleyway_Drift"]
    assert f6_m.target_count == 69
    assert f6_m.true_positives == 69
    assert f6_m.false_positives == 0
    assert f6_m.false_negatives == 0
    assert f6_m.recall == 1.0
    assert f6_m.precision == 1.0
    assert f6_m.false_positive_rate <= 0.01


def test_l3_charging_f14_duration_energy_mismatch(oracle, suite):
    """Verifies F14 (8) duration-energy mismatch in acn_charging_mapped."""
    csv_path = DATA_DIR / "acn_charging_mapped.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    # Note: df has duplicate session_ids (F13, F15), so _raw_id is evaluation_id
    df["_raw_id"] = [f"rec_{i}" for i in range(len(df))]
    df["_source_row_number"] = df.index + 1
    results = suite.evaluate_records("acn_charging_mapped", df, pk_col="session_id")

    detected_by_family = {
        "F14_DurationEnergy_Mismatch": set(),
    }

    for idx, row in df.iterrows():
        eval_id = str(row["_raw_id"])
        res = results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.layer == "L3" and sig.metric_or_relationship == "duration_mins_vs_kwh_consumed":
                detected_by_family["F14_DurationEnergy_Mismatch"].add(idx)

    metrics = oracle.match_row_signals("acn_charging_mapped", detected_by_family, len(df))

    f14_m = metrics["F14_DurationEnergy_Mismatch"]
    assert f14_m.target_count == 8
    assert f14_m.true_positives == 8
    assert f14_m.false_positives == 0
    assert f14_m.false_negatives == 0
    assert f14_m.recall == 1.0
    assert f14_m.precision == 1.0
    assert f14_m.false_positive_rate <= 0.01
