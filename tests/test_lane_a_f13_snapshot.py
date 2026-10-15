"""
DataTrust OS: Lane A L3 Cross-Dataset F13 Snapshot Test Suite
Verifies:
- F13 aggregate fault detection across acn_charging_mapped and ride_hailing_xanh_sm_trips
- Exact match on target VINs: VF8VNF_0059, 0044, 0027, 0019, 0016
- Hard invariant: charging_batch_id == trips_batch_id enforcement (fail-closed NOT_EVALUATED)
- Forensic audit evidence: batch IDs, baseline window 0-4, evaluation window 5-9
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
    return L1toL4DetectorSuite()


@pytest.fixture(scope="module")
def datasets():
    df_charging = pd.read_csv(DATA_DIR / "acn_charging_mapped.csv")
    df_trips = pd.read_csv(DATA_DIR / "ride_hailing_xanh_sm_trips.csv")
    df_charging["_raw_id"] = [f"rec_{i}" for i in range(len(df_charging))]
    df_charging["_source_row_number"] = df_charging.index + 1
    return df_charging, df_trips


def test_f13_cross_dataset_matching_and_oracle(oracle, suite, datasets):
    df_charging, df_trips = datasets
    batch_id = "batch_20261015_pilot_run"

    context = {
        "trips_daily_counts": df_trips.groupby(["vehicle_vin", "assigned_day_index"]).size().to_dict(),
        "trips_batch_id": batch_id,
        "charging_batch_id": batch_id,
    }

    detected_vins = suite.detect_f13_aggregate_vins(df_charging, context)
    expected_vins = {"VF8VNF_0059", "VF8VNF_0044", "VF8VNF_0027", "VF8VNF_0019", "VF8VNF_0016"}

    assert detected_vins == expected_vins, f"F13 target VINs mismatch: got {detected_vins}, expected {expected_vins}"

    # Verify against oracle match_aggregate_scenarios
    scenarios = {"F13_ChargingTrip_Mismatch": detected_vins}
    matched, target = oracle.match_aggregate_scenarios(scenarios)
    assert matched >= 1, "Oracle failed to match F13 aggregate scenario"


def test_f13_audit_evidence_and_signals(suite, datasets):
    df_charging, df_trips = datasets
    batch_id = "batch_20261015_audit_test"

    context = {
        "trips_daily_counts": df_trips.groupby(["vehicle_vin", "assigned_day_index"]).size().to_dict(),
        "trips_batch_id": batch_id,
        "charging_batch_id": batch_id,
    }

    results = suite.evaluate_records(
        "acn_charging_mapped",
        df_charging,
        pk_col="session_id",
        cross_dataset_context=context
    )

    # Check evidence for affected records of detected VINs
    f13_signals = []
    for eval_id, res in results.items():
        for sig in res.get("signals", []):
            if sig.metric_or_relationship == "cross_dataset_charging_vs_trips":
                f13_signals.append(sig)

    assert len(f13_signals) > 0, "No F13 cross-dataset signals emitted"

    # Verify audit evidence contains all required fields
    sample_sig = f13_signals[0]
    refs = " ".join(sample_sig.evidence_refs)
    assert f"charging_batch_id={batch_id}" in refs
    assert f"trips_batch_id={batch_id}" in refs
    assert "baseline_window=0-4" in refs
    assert "evaluation_window=5-9" in refs


def test_f13_batch_mismatch_fails_closed_not_evaluated(suite, datasets):
    df_charging, df_trips = datasets

    # Provide mismatched batch IDs
    mismatched_context = {
        "trips_daily_counts": df_trips.groupby(["vehicle_vin", "assigned_day_index"]).size().to_dict(),
        "trips_batch_id": "batch_trips_001",
        "charging_batch_id": "batch_charging_002",
    }

    # 1. detect_f13_aggregate_vins must refuse to evaluate and return empty set
    vins = suite.detect_f13_aggregate_vins(df_charging, mismatched_context)
    assert vins == set(), "Must return empty set on batch mismatch"

    # 2. evaluate_records must fail-closed with status NOT_EVALUATED, never PASS
    results = suite.evaluate_records(
        "acn_charging_mapped",
        df_charging,
        pk_col="session_id",
        cross_dataset_context=mismatched_context
    )

    assert len(results) == len(df_charging)
    first_res = next(iter(results.values()))
    assert first_res["status"] == "NOT_EVALUATED"
    assert "BATCH_MISMATCH" in first_res["evidence"][0]
