"""
DataTrust OS: Lane A L1 Constraint Calibration Test Suite
Verifies 100% recall and exact match on all 379 L1 faults across 3 datasets:
- synthetic_ev_telemetry_ved_ref: F1 (108), F2 (91), F3 (89) = 288 faults
- acn_charging_mapped: F5 (22) = 22 faults
- ride_hailing_xanh_sm_trips: F7 (36), F8 (33) = 69 faults
Total L1 = 288 + 22 + 69 = 379 faults.
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
    # Only test L1 rules in this suite
    return L1toL4DetectorSuite(reliability_config={
        "l2_metrics": [],
        "l3_relations": [],
        "l4_metrics": []
    })


def test_l1_telemetry_faults_f1_f2_f3(oracle, suite):
    """Verifies F1 (108), F2 (91), F3 (89) in synthetic_ev_telemetry_ved_ref."""
    csv_path = DATA_DIR / "synthetic_ev_telemetry_ved_ref.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    results = suite.evaluate_records("synthetic_ev_telemetry_ved_ref", df, pk_col="record_id")

    # Map signals by evaluation_id
    detected_by_family = {
        "F1_Negative_SOC": set(),
        "F2_Voltage_Overvoltage_Spike": set(),
        "F3_RPM_Speed_Mismatch": set(),
    }

    for idx, row in df.iterrows():
        eval_id = str(row["record_id"])
        res = results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.metric_or_relationship == "battery_soc" and sig.layer == "L1":
                detected_by_family["F1_Negative_SOC"].add(idx)
            elif sig.metric_or_relationship == "battery_voltage" and sig.layer == "L1":
                detected_by_family["F2_Voltage_Overvoltage_Spike"].add(idx)
            elif "speed_kmh_vs_motor_rpm" in sig.metric_or_relationship and sig.layer == "L1":
                detected_by_family["F3_RPM_Speed_Mismatch"].add(idx)

    metrics = oracle.match_row_signals("synthetic_ev_telemetry_ved_ref", detected_by_family, len(df))

    f1_m = metrics["F1_Negative_SOC"]
    assert f1_m.target_count == 108
    assert f1_m.true_positives == 108
    assert f1_m.false_positives == 0
    assert f1_m.false_negatives == 0
    assert f1_m.recall == 1.0
    assert f1_m.precision == 1.0

    f2_m = metrics["F2_Voltage_Overvoltage_Spike"]
    assert f2_m.target_count == 91
    assert f2_m.true_positives == 91
    assert f2_m.false_positives == 0
    assert f2_m.false_negatives == 0
    assert f2_m.recall == 1.0
    assert f2_m.precision == 1.0

    f3_m = metrics["F3_RPM_Speed_Mismatch"]
    assert f3_m.target_count == 89
    assert f3_m.true_positives == 89
    assert f3_m.false_positives == 0
    assert f3_m.false_negatives == 0
    assert f3_m.recall == 1.0
    assert f3_m.precision == 1.0


def test_l1_charging_faults_f5(oracle, suite):
    """Verifies F5 (22) negative cost in acn_charging_mapped."""
    csv_path = DATA_DIR / "acn_charging_mapped.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    # Note: df has duplicate session_ids (F13, F15), so _raw_id or row index is evaluation_id
    df["_raw_id"] = [f"rec_{i}" for i in range(len(df))]
    df["_source_row_number"] = df.index + 1
    results = suite.evaluate_records("acn_charging_mapped", df, pk_col="session_id")

    detected_by_family = {
        "F5_Negative_Cost": set(),
    }

    for idx, row in df.iterrows():
        eval_id = str(row["_raw_id"])
        res = results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.metric_or_relationship == "cost_vnd" and sig.layer == "L1":
                detected_by_family["F5_Negative_Cost"].add(idx)

    metrics = oracle.match_row_signals("acn_charging_mapped", detected_by_family, len(df))

    f5_m = metrics["F5_Negative_Cost"]
    assert f5_m.target_count == 22
    assert f5_m.true_positives == 22
    assert f5_m.false_positives == 0
    assert f5_m.false_negatives == 0
    assert f5_m.recall == 1.0
    assert f5_m.precision == 1.0


def test_l1_trips_faults_f7_f8(oracle, suite):
    """Verifies F7 (36) negative fare and F8 (33) ledger mismatch in ride_hailing_xanh_sm_trips."""
    csv_path = DATA_DIR / "ride_hailing_xanh_sm_trips.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    results = suite.evaluate_records("ride_hailing_xanh_sm_trips", df, pk_col="trip_id")

    detected_by_family = {
        "F7_Negative_Fare": set(),
        "F8_Ledger_Mismatch": set(),
    }

    for idx, row in df.iterrows():
        eval_id = str(row["trip_id"])
        res = results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.metric_or_relationship == "fare_amount" and sig.layer == "L1" and sig.signal_type == "RANGE_VIOLATION":
                detected_by_family["F7_Negative_Fare"].add(idx)
            elif sig.signal_type == "ARITHMETIC_VIOLATION":
                detected_by_family["F8_Ledger_Mismatch"].add(idx)

    metrics = oracle.match_row_signals("ride_hailing_xanh_sm_trips", detected_by_family, len(df))

    f7_m = metrics["F7_Negative_Fare"]
    assert f7_m.target_count == 36
    assert f7_m.true_positives == 36
    assert f7_m.false_positives == 0
    assert f7_m.false_negatives == 0
    assert f7_m.recall == 1.0
    assert f7_m.precision == 1.0

    f8_m = metrics["F8_Ledger_Mismatch"]
    assert f8_m.target_count == 33
    assert f8_m.true_positives == 33
    assert f8_m.false_positives == 0
    assert f8_m.false_negatives == 0
    assert f8_m.recall == 1.0
    assert f8_m.precision == 1.0
