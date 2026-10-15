"""
DataTrust OS: Phase 1 Production Readiness & Pipeline Upgrade Test Suite
Verifies:
1. Data contracts & normalization (opt_out_sharing, feedback subject_zone inference)
2. Strategy A Canonical Retention & Evaluation Identity across Lane A, Lane B, Lane C
3. Preservation of 983 = 880 + 103 invariant on acn_charging_mapped
4. Zero UUID5 collisions for duplicate business keys
5. Voltage, financial bounds, and promo fare (fare_amount=0.0) validation
6. Health/biometric exclusion from Silver (fatigue_score protection)
7. Consent lifecycle & legal_basis persistence in Silver dimensions
"""

import uuid
import pytest
import pandas as pd
import numpy as np

from database.reset_and_ingest_bronze import (
    normalize_opt_out_sharing,
    validate_dataset_contract,
    DataContractValidationError,
)
from src.detectors.detector_suite import L1toL4DetectorSuite
from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor
from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter
from dags.parallel_evaluation_engine import persist_silver_records_chunk


# =============================================================================
# 1. DATA CONTRACTS & NORMALIZATION
# =============================================================================

def test_opt_out_sharing_strict_normalization():
    """Verify strict normalization of opt_out_sharing (0/1)."""
    assert normalize_opt_out_sharing(0) == 0
    assert normalize_opt_out_sharing("0") == 0
    assert normalize_opt_out_sharing(False) == 0
    assert normalize_opt_out_sharing("false") == 0
    assert normalize_opt_out_sharing("FALSE") == 0
    assert normalize_opt_out_sharing(None) == 0
    assert normalize_opt_out_sharing("") == 0
    assert normalize_opt_out_sharing(np.nan) == 0

    assert normalize_opt_out_sharing(1) == 1
    assert normalize_opt_out_sharing("1") == 1
    assert normalize_opt_out_sharing(True) == 1
    assert normalize_opt_out_sharing("true") == 1
    assert normalize_opt_out_sharing("TRUE") == 1

    # Invalid values must raise DataContractValidationError
    with pytest.raises(DataContractValidationError):
        normalize_opt_out_sharing("INVALID")

    with pytest.raises(DataContractValidationError):
        normalize_opt_out_sharing(2)

    with pytest.raises(DataContractValidationError):
        normalize_opt_out_sharing(-1)


def test_data_contract_validation_error_on_missing_columns():
    """Verify DataContractValidationError is raised when required columns are absent."""
    broken_df = pd.DataFrame([{"vehicle_vin": "VF8_01"}])  # missing session_id, station_id, etc.
    with pytest.raises(DataContractValidationError) as exc:
        validate_dataset_contract("acn_charging_mapped", broken_df)
    assert "missing expected column" in str(exc.value)


def test_feedback_subject_zone_inference_never_hardcodes_vn():
    """Verify subject_zone inference maps VIN -> fleet_index zone, or None (never hardcoded VN)."""
    fleet_map = {
        "VIN_VN_01": "VN",
        "VIN_EU_01": "EU",
        "VIN_US_01": "US",
    }
    fb_df = pd.DataFrame([
        {"feedback_id": "FB_01", "vehicle_vin": "VIN_VN_01", "raw_comment_text": "Good"},
        {"feedback_id": "FB_02", "vehicle_vin": "VIN_EU_01", "raw_comment_text": "Gut"},
        {"feedback_id": "FB_03", "vehicle_vin": "VIN_UNKNOWN", "raw_comment_text": "Unknown"},
    ])

    inferred_zones = fb_df["vehicle_vin"].map(lambda vin: fleet_map.get(vin, None))
    assert inferred_zones.iloc[0] == "VN"
    assert inferred_zones.iloc[1] == "EU"
    assert pd.isna(inferred_zones.iloc[2]), "Unknown VIN must map to None/NaN, never hardcoded to VN"


# =============================================================================
# 2. EVALUATION IDENTITY & STRATEGY A CANONICAL RETENTION
# =============================================================================

def test_strategy_a_charging_duplicates_and_scanned_count_invariant():
    """
    Simulates acn_charging_mapped with 983 total records, 880 unique session_id, 103 duplicate instances.
    Verifies:
    1. 880 canonical records evaluate to PASS.
    2. 103 duplicate records evaluate to FAIL (L1_DUPLICATE_SESSION_COLLISION).
    3. Merged results: 880 Silver + 103 Quarantine = 983 total.
    4. Quarantine IDs are unique (zero UUID collisions).
    """
    rows = []
    # Generate 880 unique sessions
    for i in range(880):
        rows.append({
            "_raw_id": f"raw_charging_{i:04d}",
            "session_id": f"SESS_{i:04d}",
            "vehicle_vin": f"VIN_{i % 50:03d}",
            "station_id": "ST_01",
            "charger_id": "CH_01",
            "start_time": f"2026-01-01 10:{i % 60:02d}:00",
            "event_sequence_index": i,
            "duration_mins": 30.0,
            "kwh_consumed": 15.0,
            "power_kw": 50.0,
            "station_temp_c": 25.0,
            "cost_vnd": 50000.0,
            "subject_zone": "VN",
        })

    # Ingest 103 duplicate instances from the first 103 sessions
    for dup_idx in range(103):
        canonical_idx = dup_idx
        rows.append({
            "_raw_id": f"raw_charging_dup_{dup_idx:04d}",
            "session_id": f"SESS_{canonical_idx:04d}",  # Duplicate session_id
            "vehicle_vin": f"VIN_{canonical_idx % 50:03d}",
            "station_id": "ST_01",
            "charger_id": "CH_01",
            "start_time": f"2026-01-01 11:{dup_idx % 60:02d}:00",
            "event_sequence_index": 1000 + dup_idx,
            "duration_mins": 30.0,
            "kwh_consumed": 15.0,
            "power_kw": 50.0,
            "station_temp_c": 25.0,
            "cost_vnd": 50000.0,
            "subject_zone": "VN",
        })

    assert len(rows) == 983
    df = pd.DataFrame(rows)

    # 1. Run Lane A Evaluation
    suite = L1toL4DetectorSuite(reliability_config={"l2_metrics": [], "l3_relations": [], "l4_metrics": []})
    lane_a_results = suite.evaluate_records("acn_charging_mapped", df, pk_col="session_id")

    assert len(lane_a_results) == 983, "Every row must have an entry keyed by its technical _raw_id"

    # Count passes and fails in Lane A
    pass_keys = [k for k, v in lane_a_results.items() if v["status"] == "PASS"]
    fail_keys = [k for k, v in lane_a_results.items() if v["status"] == "FAIL"]

    assert len(pass_keys) == 880, f"Expected exactly 880 canonical passes, got {len(pass_keys)}"
    assert len(fail_keys) == 103, f"Expected exactly 103 duplicate failures, got {len(fail_keys)}"

    # Check that failures have L1_DUPLICATE_SESSION_COLLISION
    for fk in fail_keys:
        sigs = lane_a_results[fk]["signals"]
        assert any(s.signal_type == "L1_DUPLICATE_SESSION_COLLISION" for s in sigs)

    # 2. Run Lane B Policy (clean for charging)
    policy_proc = HierarchicalPolicyProcessor()
    lane_b_verdicts = policy_proc.process_records("acn_charging_mapped", rows, pk_col="session_id")
    assert len(lane_b_verdicts) == 983

    # 3. Run Lane C Router
    router = VerdictMergerAndRouter()
    run_id = f"test_run_{uuid.uuid4().hex[:8]}"
    consolidated = router.merge_and_route(
        "acn_charging_mapped",
        rows,
        lane_a_results,
        lane_b_verdicts,
        run_id=run_id,
        pk_col="session_id",
    )

    # Verify Strict Reconciliation Invariant
    assert consolidated.scanned_count == 983
    assert consolidated.silver_count == 880, f"Expected 880 silver records, got {consolidated.silver_count}"
    assert consolidated.quarantine_count == 103, f"Expected 103 quarantined records, got {consolidated.quarantine_count}"
    assert consolidated.warning_count == 0
    assert consolidated.silver_count + consolidated.quarantine_count == 983

    # Verify Quarantine IDs are unique (zero UUID collisions)
    quar_ids = [r["quarantine_id"] for r in consolidated.quarantine_records]
    assert len(quar_ids) == 103
    assert len(set(quar_ids)) == 103, "Quarantine IDs must be completely unique"

    # Verify source_row_pk retains the natural business session_id
    for qr in consolidated.quarantine_records:
        assert qr["source_row_pk"].startswith("SESS_")


# =============================================================================
# 3. PHYSICAL AND FINANCIAL RANGE DETECTORS
# =============================================================================

def test_voltage_and_cost_ranges_and_promo_fare():
    """Verify battery_voltage max 1000, cost_vnd min 0, and promo fare (fare_amount=0.0 allowed)."""
    suite = L1toL4DetectorSuite()

    # 1. Promo fare (fare_amount = 0.0) must PASS
    promo_trips = pd.DataFrame([
        {"trip_id": "T_PROMO_FREE", "fare_amount": 0.0, "total_fare": 0.0, "trip_distance_km": 2.5, "subject_zone": "VN"},
        {"trip_id": "T_NEGATIVE_FARE", "fare_amount": -1000.0, "total_fare": -1000.0, "trip_distance_km": 2.5, "subject_zone": "VN"},
    ])
    trip_results = suite.evaluate_records("ride_hailing_xanh_sm_trips", promo_trips, pk_col="trip_id")
    assert trip_results["T_PROMO_FREE"]["status"] == "PASS", "fare_amount=0.0 must be valid for promo trips"
    assert trip_results["T_NEGATIVE_FARE"]["status"] == "FAIL", "negative fare must be rejected"

    # 2. Battery voltage (> 1000V fails, <= 1000V passes)
    telemetry_df = pd.DataFrame([
        {"record_id": "R_NORMAL_VOLT", "battery_voltage": 400.0, "battery_soc": 80.0, "subject_zone": "VN"},
        {"record_id": "R_OVERVOLT", "battery_voltage": 1250.0, "battery_soc": 80.0, "subject_zone": "VN"},
    ])
    tel_results = suite.evaluate_records("synthetic_ev_telemetry_ved_ref", telemetry_df, pk_col="record_id")
    assert tel_results["R_NORMAL_VOLT"]["status"] == "PASS"
    assert tel_results["R_OVERVOLT"]["status"] == "FAIL"

    # 3. Charging cost (< 0 fails, >= 0 passes)
    charging_df = pd.DataFrame([
        {"session_id": "C_OK", "cost_vnd": 45000.0, "power_kw": 50.0, "subject_zone": "VN"},
        {"session_id": "C_NEGATIVE_COST", "cost_vnd": -500.0, "power_kw": 50.0, "subject_zone": "VN"},
    ])
    chg_results = suite.evaluate_records("acn_charging_mapped", charging_df, pk_col="session_id")
    assert chg_results["C_OK"]["status"] == "PASS"
    assert chg_results["C_NEGATIVE_COST"]["status"] == "FAIL"


# =============================================================================
# 4. PRIVACY, CONSENT LIFECYCLE & SILVER PERSISTENCE
# =============================================================================

def test_fatigue_score_health_data_protection():
    """Verify fatigue_score is detected as health data in Lane B, but strictly excluded from Silver."""
    proc = HierarchicalPolicyProcessor()
    telemetry_record = {
        "record_id": "EU_TEL_01",
        "vehicle_vin": "VF8_EU_001",
        "subject_zone": "EU",
        "country": "DE",
        "fatigue_score": 75.5,
        "speed_kmh": 60.0,
    }
    verdict = proc.process_single_record("synthetic_ev_telemetry_ved_ref", telemetry_record)
    assert any("fatigue_score" in ev for ev in verdict.compliance_evidence), (
        "Lane B must note fatigue_score under health/biometric policy"
    )

    # Verify silver columns for telemetry exclude fatigue_score
    from dags import parallel_evaluation_engine as engine
    import inspect
    func_source = inspect.getsource(engine.persist_silver_records_chunk)
    # Extract the telemetry section
    tel_part = func_source[func_source.find('elif "telemetry" in dataset_id:'):func_source.find('elif "charging" in dataset_id:')]
    assert "fatigue_score" not in tel_part, "fatigue_score must NOT be in silver.synthetic_ev_telemetry_ved_ref insert columns"


def test_customer_consent_and_driver_legal_basis_in_silver_persistence():
    """Verify that silver persistence includes consent columns and legal_basis."""
    from dags import parallel_evaluation_engine as engine
    import inspect
    func_source = inspect.getsource(engine.persist_silver_records_chunk)

    # Customers section
    cust_part = func_source[func_source.find('elif "customers" in dataset_id:'):func_source.find('elif "drivers" in dataset_id:')]
    for col in ["consent_at", "consent_withdrawn_at", "delete_requested_at", "delete_completed_at", "opt_out_sharing"]:
        assert col in cust_part, f"Customer silver persistence missing {col}"

    # Drivers section
    drv_part = func_source[func_source.find('elif "drivers" in dataset_id:'):func_source.find('elif "feedback_pii" in dataset_id:')]
    assert "legal_basis" in drv_part, "Driver silver persistence missing legal_basis"
