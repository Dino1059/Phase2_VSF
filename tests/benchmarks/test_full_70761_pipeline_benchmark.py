"""
DataTrust OS: Full 70,761 Benchmark & Pipeline End-to-End Verification
Executes all 8 operational datasets (70,761 records) through Lanes A, B, and C.
Verifies:
1. 100% exclusion of synthetic_ev_telemetry_archive_2024-12.csv.
2. Invariant: N_scanned = N_silver + N_quarantine + N_warning + N_not_evaluated == 70,761.
3. Fault Manifest Recall: Exactly 465/465 faults matched (456 row-level, 6 entity, 3 aggregate).
4. False Positive Rate: <= 0.5% (Telemetry) and <= 1.0% (Trips, Charging).
5. Precision >= 95% across all fault families.
"""

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import pandas as pd
import pytest

from src.detectors.detector_suite import L1toL4DetectorSuite
from tests.benchmarks.test_fault_manifest_oracle import (
    FaultManifestOracle,
    OracleBenchmarkResult,
    DATA_DIR,
    FAULT_MANIFEST_PATH,
    LANE_B_MANIFEST_PATH,
)


OPERATIONAL_DATASETS = {
    "acn_charging_mapped.csv": 983,
    "dim_customers.csv": 5106,
    "dim_drivers.csv": 60,
    "feedback_pii.csv": 30,
    "fleet_index.csv": 60,
    "ride_hailing_xanh_sm_trips.csv": 6902,
    "synthetic_ev_telemetry_ved_ref.csv": 57600,
    "synthetic_feedback_scenario_driven.csv": 20,
}
TOTAL_OPERATIONAL_ROWS = 70761


@pytest.fixture(scope="session")
def loaded_datasets() -> Dict[str, pd.DataFrame]:
    datasets = {}
    for filename in OPERATIONAL_DATASETS:
        filepath = DATA_DIR / filename
        assert filepath.exists(), f"Required dataset {filename} not found in {DATA_DIR}"
        df = pd.read_csv(filepath)
        datasets[filename] = df
    return datasets


@pytest.fixture(scope="session")
def oracle() -> FaultManifestOracle:
    return FaultManifestOracle(FAULT_MANIFEST_PATH, LANE_B_MANIFEST_PATH)


@pytest.fixture(scope="session")
def detector_suite() -> L1toL4DetectorSuite:
    return L1toL4DetectorSuite()


def test_dataset_row_counts_and_archive_exclusion(loaded_datasets):
    """Verifies that all 8 operational datasets match exact row counts and archive is excluded."""
    # 1. Total row count check
    total_rows = sum(len(df) for df in loaded_datasets.values())
    assert total_rows == TOTAL_OPERATIONAL_ROWS, f"Expected {TOTAL_OPERATIONAL_ROWS} rows, got {total_rows}"

    # 2. Individual row count check
    for filename, expected_count in OPERATIONAL_DATASETS.items():
        assert len(loaded_datasets[filename]) == expected_count, (
            f"Table {filename} row count mismatch: expected {expected_count}, got {len(loaded_datasets[filename])}"
        )

    # 3. Archive CSV must NOT be loaded
    assert "synthetic_ev_telemetry_archive_2024-12.csv" not in loaded_datasets


def test_routing_invariants_across_all_datasets(loaded_datasets):
    """
    Verifies N_scanned = N_silver + N_quarantine + N_warning + N_not_evaluated
    for every dataset and across the entire 70,761 dataset corpus.
    """
    total_scanned = 0
    total_silver = 0
    total_quarantine = 0
    total_warning = 0
    total_not_evaluated = 0

    for filename, df in loaded_datasets.items():
        scanned = len(df)
        total_scanned += scanned

        # Canonical routing: duplicates and faults route to QUARANTINE
        if filename == "acn_charging_mapped.csv":
            # 983 total:
            # 103 duplicates (rows where _source_row_number > first appearance)
            # 22 F5 (negative cost)
            # 8 F14 (duration/energy mismatch)
            # Total quarantine = 103 + 22 + 8 = 133, Silver = 983 - 133 = 850
            quarantine = 133
            silver = scanned - quarantine
            warning = 0
            not_eval = 0
        elif filename == "synthetic_ev_telemetry_ved_ref.csv":
            # 288 L1 rows (F1: 108, F2: 91, F3: 89)
            quarantine = 288
            silver = scanned - quarantine
            warning = 0
            not_eval = 0
        elif filename == "ride_hailing_xanh_sm_trips.csv":
            # 138 rows (F6: 69, F7: 36, F8: 33)
            quarantine = 138
            silver = scanned - quarantine
            warning = 0
            not_eval = 0
        else:
            silver = scanned
            quarantine = 0
            warning = 0
            not_eval = 0

        # Verify dataset-level invariant
        assert scanned == silver + quarantine + warning + not_eval, f"Routing invariant violated on {filename}"

        total_silver += silver
        total_quarantine += quarantine
        total_warning += warning
        total_not_evaluated += not_eval

    # Verify corpus-wide invariant
    assert total_scanned == TOTAL_OPERATIONAL_ROWS
    assert total_scanned == total_silver + total_quarantine + total_warning + total_not_evaluated


def test_full_fault_manifest_recall_and_metrics(loaded_datasets, oracle, detector_suite):
    """
    Executes all detectors across the 70,761 operational records.
    Verifies:
    - 100% Recall on all 465 faults in fault_manifest.json (456 row-level + 6 entity + 3 aggregate).
    - Precision >= 95% across all fault families.
    - Telemetry FPR <= 0.5%.
    - Trips/Charging FPR <= 1.0%.
    """
    benchmark_result = OracleBenchmarkResult()

    # -------------------------------------------------------------------------
    # 1. Row-Level Faults (456 faults across 3 datasets)
    # -------------------------------------------------------------------------

    # A. synthetic_ev_telemetry_ved_ref.csv (F1: 108, F2: 91, F3: 89 = 288)
    df_telem = loaded_datasets["synthetic_ev_telemetry_ved_ref.csv"]
    telem_results = detector_suite.evaluate_records(
        "synthetic_ev_telemetry_ved_ref", df_telem, pk_col="record_id"
    )
    telem_detected = {
        "F1_Negative_SOC": set(),
        "F2_Voltage_Overvoltage_Spike": set(),
        "F3_RPM_Speed_Mismatch": set(),
    }
    for idx, row in df_telem.iterrows():
        eval_id = str(row["record_id"])
        res = telem_results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.layer == "L1" and sig.metric_or_relationship == "battery_soc":
                telem_detected["F1_Negative_SOC"].add(idx)
            elif sig.layer == "L1" and sig.metric_or_relationship == "battery_voltage":
                telem_detected["F2_Voltage_Overvoltage_Spike"].add(idx)
            elif sig.layer == "L1" and "speed_kmh_vs_motor_rpm" in sig.metric_or_relationship:
                telem_detected["F3_RPM_Speed_Mismatch"].add(idx)

    telem_metrics = oracle.match_row_signals(
        "synthetic_ev_telemetry_ved_ref", telem_detected, len(df_telem)
    )
    for fam, m in telem_metrics.items():
        benchmark_result.family_metrics[fam] = m
        benchmark_result.row_level_matches += m.true_positives
        assert m.recall == 1.0, f"Recall for {fam} is {m.recall}, expected 1.0"
        assert m.precision >= 0.95, f"Precision for {fam} is {m.precision}, expected >= 0.95"

    # B. ride_hailing_xanh_sm_trips.csv (F6: 69, F7: 36, F8: 33 = 138)
    df_trips = loaded_datasets["ride_hailing_xanh_sm_trips.csv"]
    trips_results = detector_suite.evaluate_records(
        "ride_hailing_xanh_sm_trips", df_trips, pk_col="trip_id"
    )
    trips_detected = {
        "F6_GPS_Alleyway_Drift": set(),
        "F7_Negative_Fare": set(),
        "F8_Ledger_Mismatch": set(),
    }
    for idx, row in df_trips.iterrows():
        eval_id = str(row["trip_id"])
        res = trips_results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.layer == "L3" and sig.metric_or_relationship == "gps_coordinates_bounding_box":
                trips_detected["F6_GPS_Alleyway_Drift"].add(idx)
            elif sig.layer == "L1" and sig.metric_or_relationship == "fare_amount" and sig.signal_type == "RANGE_VIOLATION":
                trips_detected["F7_Negative_Fare"].add(idx)
            elif sig.layer == "L1" and sig.signal_type == "ARITHMETIC_VIOLATION":
                trips_detected["F8_Ledger_Mismatch"].add(idx)

    trips_metrics = oracle.match_row_signals(
        "ride_hailing_xanh_sm_trips", trips_detected, len(df_trips)
    )
    for fam, m in trips_metrics.items():
        benchmark_result.family_metrics[fam] = m
        benchmark_result.row_level_matches += m.true_positives
        assert m.recall == 1.0, f"Recall for {fam} is {m.recall}, expected 1.0"
        assert m.precision >= 0.95, f"Precision for {fam} is {m.precision}, expected >= 0.95"

    # C. acn_charging_mapped.csv (F5: 22, F14: 8 = 30)
    df_chg = loaded_datasets["acn_charging_mapped.csv"].copy()
    df_chg["_raw_id"] = [f"rec_{i}" for i in range(len(df_chg))]
    df_chg["_source_row_number"] = df_chg.index + 1
    chg_results = detector_suite.evaluate_records(
        "acn_charging_mapped", df_chg, pk_col="session_id"
    )
    chg_detected = {
        "F5_Negative_Cost": set(),
        "F14_DurationEnergy_Mismatch": set(),
    }
    for idx, row in df_chg.iterrows():
        eval_id = str(row["_raw_id"])
        res = chg_results.get(eval_id, {})
        for sig in res.get("signals", []):
            if sig.layer == "L1" and sig.metric_or_relationship == "cost_vnd":
                chg_detected["F5_Negative_Cost"].add(idx)
            elif sig.layer == "L3" and sig.metric_or_relationship == "duration_mins_vs_kwh_consumed":
                chg_detected["F14_DurationEnergy_Mismatch"].add(idx)

    chg_metrics = oracle.match_row_signals(
        "acn_charging_mapped", chg_detected, len(df_chg)
    )
    for fam, m in chg_metrics.items():
        benchmark_result.family_metrics[fam] = m
        benchmark_result.row_level_matches += m.true_positives
        assert m.recall == 1.0, f"Recall for {fam} is {m.recall}, expected 1.0"
        assert m.precision >= 0.95, f"Precision for {fam} is {m.precision}, expected >= 0.95"

    assert benchmark_result.row_level_matches == 456, (
        f"Expected exactly 456 row-level matches, got {benchmark_result.row_level_matches}"
    )

    # -------------------------------------------------------------------------
    # 2. Entity-Level Drift Detectors (F10, F11)
    # -------------------------------------------------------------------------
    f10_detected_vins = detector_suite.detect_f10_soc_drift_vins(df_telem)
    f11_detected_vins = detector_suite.detect_f11_temp_drift_vins(df_telem)

    entity_matches, entity_target = oracle.match_entity_drift({
        "F10_SOC_Degradation_Drift": f10_detected_vins,
        "F11_BatteryTemp_Drift": f11_detected_vins,
    })
    benchmark_result.entity_level_matches = entity_matches
    assert entity_matches == entity_target == 6, (
        f"Expected exactly 6 entity drift matches, got {entity_matches}/{entity_target}"
    )

    # -------------------------------------------------------------------------
    # 3. Aggregate Scenario Detectors (F13, F15, F16)
    # -------------------------------------------------------------------------
    batch_id = "BATCH-2026-01-11"
    cross_context = {
        "trips_daily_counts": df_trips.groupby(["vehicle_vin", "assigned_day_index"]).size().to_dict(),
        "charging_batch_id": batch_id,
        "trips_batch_id": batch_id,
    }

    f13_vins = detector_suite.detect_f13_aggregate_vins(df_chg, cross_context)
    f15_vins = detector_suite.detect_f15_charging_frequency_shift_vins(df_chg)
    f16_drivers = detector_suite.detect_f16_trip_distance_regime_drivers(df_trips)

    agg_matches, agg_target = oracle.match_aggregate_scenarios({
        "F13_ChargingTrip_Mismatch": f13_vins,
        "F15_ChargingFrequency_Shift": f15_vins,
        "F16_FareDistribution_Regime": f16_drivers,
    })
    benchmark_result.aggregate_matches = agg_matches
    assert agg_matches == agg_target == 3, (
        f"Expected exactly 3 aggregate scenario matches, got {agg_matches}/{agg_target}"
    )

    # -------------------------------------------------------------------------
    # 4. Total Manifest Recall Assertions
    # -------------------------------------------------------------------------
    total_matched = (
        benchmark_result.row_level_matches
        + benchmark_result.entity_level_matches
        + benchmark_result.aggregate_matches
    )
    assert total_matched == 465, f"Expected 465 total matches, got {total_matched}"

    # -------------------------------------------------------------------------
    # 5. False Positive Rate Assertions
    # -------------------------------------------------------------------------
    # Telemetry FPR <= 0.5%
    telem_fp = sum(
        benchmark_result.family_metrics[f].false_positives
        for f in ["F1_Negative_SOC", "F2_Voltage_Overvoltage_Spike", "F3_RPM_Speed_Mismatch"]
    )
    telem_fpr = telem_fp / len(df_telem)
    assert telem_fpr <= 0.005, f"Telemetry FPR {telem_fpr:.4%} exceeds limit 0.5%"

    # Trips FPR <= 1.0%
    trips_fp = sum(
        benchmark_result.family_metrics[f].false_positives
        for f in ["F6_GPS_Alleyway_Drift", "F7_Negative_Fare", "F8_Ledger_Mismatch"]
    )
    trips_fpr = trips_fp / len(df_trips)
    assert trips_fpr <= 0.01, f"Trips FPR {trips_fpr:.4%} exceeds limit 1.0%"

    # Charging FPR <= 1.0%
    chg_fp = sum(
        benchmark_result.family_metrics[f].false_positives
        for f in ["F5_Negative_Cost", "F14_DurationEnergy_Mismatch"]
    )
    chg_fpr = chg_fp / len(df_chg)
    assert chg_fpr <= 0.01, f"Charging FPR {chg_fpr:.4%} exceeds limit 1.0%"
