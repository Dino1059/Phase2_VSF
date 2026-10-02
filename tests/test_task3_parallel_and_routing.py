"""
Comprehensive Automated Test Suite for Task 3:
1. Generic Operation Registry (MASK, HASH, ROUND, GENERALIZE, REMOVE)
2. Lane B Lifecycle (Resolve -> Policy -> Pre-check -> Treatment -> Process -> Post-check -> Verdict)
   with Law 91/2025/QH15 & Decree 356/2025/ND-CP (effective 01/01/2026)
3. Lane A L1-L4 Reliability Suite & Per-Record Changepoint Attribution
4. Lane C Merge Verdicts: A/B Combination Matrix & Precedence (FAIL > WARNING > PASS)
5. Controlled PII Storage in warning.records vs 100% Raw in quarantine.records
6. PostgreSQL Database Persistence
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import uuid

from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig
from backend.engine.operation_registry import OperationRegistry
from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor, LaneBVerdict
from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter
from src.detectors.detector_suite import L1toL4DetectorSuite
from dags.parallel_evaluation_engine import (
    execute_lane_a_detectors,
    execute_lane_b_policy,
    execute_lane_c_merge_and_persist,
    get_db_connection
)


# =============================================================================
# 1. TEST GENERIC OPERATION REGISTRY
# =============================================================================

def test_operation_registry_mask():
    res = OperationRegistry.mask_value("0987654321", prefix_len=3, suffix_len=2)
    assert res == "098*****21"

    # Short string
    res_short = OperationRegistry.mask_value("123", prefix_len=2, suffix_len=2)
    assert res_short == "***"


def test_operation_registry_hash():
    res1 = OperationRegistry.hash_value("DRV_XANH_001", algorithm="sha256", salt_ref="salt_test_2026")
    assert len(res1) == 64
    res2 = OperationRegistry.hash_value("DRV_XANH_001", algorithm="sha256", salt_ref="salt_test_2026")
    assert res1 == res2


def test_operation_registry_round():
    res = OperationRegistry.round_numeric(21.028511, decimals=2)
    assert res == 21.03
    assert OperationRegistry.round_numeric(None) is None


def test_operation_registry_generalize_and_remove():
    assert OperationRegistry.generalize_value(27, level=10) == "20-29"
    assert OperationRegistry.remove_value("sensitive_value") is None


def test_operation_registry_dynamic_execute():
    res_mask = OperationRegistry.execute("MASK", "0912345678", {"prefix_len": 4, "suffix_len": 2})
    assert res_mask == "0912****78"

    res_round = OperationRegistry.execute("ROUND", 105.854444, {"decimals": 2})
    assert res_round == 105.85


# =============================================================================
# 2. TEST LANE B: 7-STEP LIFECYCLE & VIETNAM 2026 LEGAL FRAMEWORK
# =============================================================================

def test_lane_b_vietnam_legal_framework():
    """Verify Lane B uses Law 91/2025/QH15 and Decree 356/2025/ND-CP."""
    processor = HierarchicalPolicyProcessor()
    clean_record = {
        "trip_id": "VN_TRIP_001",
        "subject_zone": "VN",
        "customer_phone": "0987654321",
        "driver_id": "DRV_VN_100",
        "fare_amount": 75000.0,
        "trip_distance_km": 4.5,
        "pickup_latitude": 21.028511,
        "pickup_longitude": 105.854444
    }
    verdict = processor.process_single_record("trips", clean_record)

    assert verdict.status == "PASS"
    assert verdict.treated_record is not None
    # Phone was masked
    assert verdict.treated_record["customer_phone"] == "098*****21"
    # Driver ID was hashed
    assert len(verdict.treated_record["driver_id"]) == 64
    # GPS was rounded
    assert verdict.treated_record["pickup_latitude"] == 21.03
    assert verdict.treated_record["pickup_longitude"] == 105.85

    # Check that Law 91/2025/QH15 and Decree 356/2025 are referenced
    law_refs = [t.get("law_ref", "") for t in verdict.required_treatments]
    assert any("91/2025/QH15" in ref for ref in law_refs)
    assert any("356/2025" in ref for ref in law_refs)


def test_lane_b_precheck_geographic_boundary():
    """Verify Pre-check fails if GPS is outside Vietnam territory for VN zone."""
    processor = HierarchicalPolicyProcessor()
    bad_geo = {
        "trip_id": "VN_BAD_GEO",
        "subject_zone": "VN",
        "customer_phone": "0987654321",
        "fare_amount": 50000.0,
        "trip_distance_km": 3.0,
        "pickup_latitude": 45.123456,  # Outside VN (lat [8.0, 24.0])
        "pickup_longitude": 105.854444
    }
    verdict = processor.process_single_record("trips", bad_geo)
    assert verdict.status == "FAIL"
    assert any("ngoài lãnh thổ cấp phép VN" in r for r in verdict.failure_reasons)


def test_lane_b_postcheck_ifrs15():
    """Verify Post-check fails if fare_amount <= 0 or trip_distance < 0.1."""
    processor = HierarchicalPolicyProcessor()
    bad_fare = {
        "trip_id": "TRIP_BAD_FARE",
        "subject_zone": "VN",
        "customer_phone": "0987654321",
        "fare_amount": -5000.0,
        "trip_distance_km": 3.0,
        "pickup_latitude": 21.02,
        "pickup_longitude": 105.85
    }
    verdict = processor.process_single_record("trips", bad_fare)
    assert verdict.status == "FAIL"
    assert any("IFRS 15" in r for r in verdict.failure_reasons)


# =============================================================================
# 3. TEST LANE A: L1-L4 RELIABILITY & SENSOR ANOMALY SUITE
# =============================================================================

def test_lane_a_l1_sensor_and_ledger():
    """Verify Lane A detects physical sensor bounds and arithmetic ledger violations."""
    suite = L1toL4DetectorSuite()
    df = pd.DataFrame([
        {"trip_id": "T_OK", "vehicle_vin": "V1", "fare_amount": 50000.0, "total_fare": 50000.0, "battery_soc": 80.0},
        {"trip_id": "T_FAIL_SOC", "vehicle_vin": "V2", "fare_amount": 50000.0, "total_fare": 50000.0, "battery_soc": 115.0},
        {"trip_id": "T_FAIL_MATH", "vehicle_vin": "V3", "fare_amount": 50000.0, "total_fare": 90000.0, "battery_soc": 80.0},
    ])
    results = suite.evaluate_records("trips", df)

    assert results["T_OK"]["status"] == "PASS"
    assert results["T_FAIL_SOC"]["status"] == "FAIL"
    assert results["T_FAIL_MATH"]["status"] == "FAIL"


def test_lane_a_l4_changepoint_window_attribution():
    """Verify Lane A detects changepoint and maps WARNING signals to the transition window."""
    suite = L1toL4DetectorSuite()
    # Create 20 time-series points with abrupt jump at t=10
    records = []
    base_time = pd.date_range(start="2026-01-01 08:00:00", periods=20, freq="10min")
    for i, t in enumerate(base_time):
        val = 25.0 if i < 10 else 55.0  # Abrupt jump of 30 degrees
        records.append({
            "record_id": f"TEL_{i:02d}",
            "vehicle_vin": "VF8_PILOT_01",
            "timestamp": t.isoformat(),
            "battery_temp_c": val,
            "battery_soc": 80.0
        })

    df = pd.DataFrame(records)
    results = suite.evaluate_records("telemetry", df)

    # Verify that records in the transition window (around index 10) have WARNING or signals
    window_statuses = [results[f"TEL_{i:02d}"]["status"] for i in range(10, 15)]
    assert any(s == "WARNING" for s in window_statuses), "Expected changepoint window records to be flagged WARNING"


# =============================================================================
# 4. TEST LANE C: A/B COMBINATION MATRIX & PRECEDENCE
# =============================================================================

def test_lane_c_combination_matrix():
    router = VerdictMergerAndRouter()
    dataset_id = "trips"
    run_id = "test_run_matrix"

    records = [
        {"trip_id": "REC_PASS_PASS", "customer_phone": "0987654321", "fare_amount": 50000.0, "trip_distance_km": 3.0, "subject_zone": "VN"},
        {"trip_id": "REC_PASS_FAIL", "customer_phone": "0987654321", "fare_amount": -100.0, "trip_distance_km": 3.0, "subject_zone": "VN"},
        {"trip_id": "REC_FAIL_PASS", "customer_phone": "0987654321", "fare_amount": 50000.0, "trip_distance_km": 3.0, "subject_zone": "VN"},
        {"trip_id": "REC_FAIL_FAIL", "customer_phone": "0987654321", "fare_amount": -100.0, "trip_distance_km": 3.0, "subject_zone": "VN"},
        {"trip_id": "REC_WARN_PASS", "customer_phone": "0987654321", "fare_amount": 50000.0, "trip_distance_km": 3.0, "subject_zone": "VN"},
    ]

    lane_a_results = {
        "REC_PASS_PASS": {"status": "PASS", "evidence": []},
        "REC_PASS_FAIL": {"status": "PASS", "evidence": []},
        "REC_FAIL_PASS": {"status": "FAIL", "evidence": ["battery_soc > 100"]},
        "REC_FAIL_FAIL": {"status": "FAIL", "evidence": ["battery_soc > 100"]},
        "REC_WARN_PASS": {"status": "WARNING", "evidence": ["z-score > 4.5"]},
    }

    lane_b_verdicts = [
        LaneBVerdict("REC_PASS_PASS", "PASS", {"trip_id": "REC_PASS_PASS", "customer_phone": "098*****21", "fare_amount": 50000.0}, records[0]),
        LaneBVerdict("REC_PASS_FAIL", "FAIL", None, records[1], failure_reasons=["fare <= 0"]),
        LaneBVerdict("REC_FAIL_PASS", "PASS", {"trip_id": "REC_FAIL_PASS", "customer_phone": "098*****21", "fare_amount": 50000.0}, records[2]),
        LaneBVerdict("REC_FAIL_FAIL", "FAIL", None, records[3], failure_reasons=["fare <= 0"]),
        LaneBVerdict("REC_WARN_PASS", "PASS", {"trip_id": "REC_WARN_PASS", "customer_phone": "098*****21", "fare_amount": 50000.0}, records[4]),
    ]

    result = router.merge_and_route(dataset_id, records, lane_a_results, lane_b_verdicts, run_id=run_id)

    # Verify counts
    assert result.scanned_count == 5
    assert result.silver_count == 1      # Only A PASS + B PASS
    assert result.quarantine_count == 3  # (A PASS, B FAIL), (A FAIL, B PASS), (A FAIL, B FAIL)
    assert result.warning_count == 1     # A WARN + B PASS

    # Check failure lanes
    quar_map = {q["source_row_pk"]: q for q in result.quarantine_records}
    assert quar_map["REC_PASS_FAIL"]["failure_lane"] == "LANE_B"  # Policy Block
    assert quar_map["REC_FAIL_PASS"]["failure_lane"] == "LANE_A"  # Reliability defect
    assert quar_map["REC_FAIL_FAIL"]["failure_lane"] == "BOTH"    # Quarantine + Finding

    # Check Silver record has treated phone
    assert result.silver_records[0]["customer_phone"] == "098*****21"
    assert "lineage_hash" in result.silver_records[0]


# =============================================================================
# 5. TEST PII REDACTION IN STORAGE
# =============================================================================

def test_storage_pii_redaction():
    router = VerdictMergerAndRouter()
    raw = {
        "trip_id": "T_WARN_1",
        "customer_name": "Nguyễn Quốc Bảo",
        "customer_phone": "0987654321",
        "customer_email": "bao.nguyen@vinfast.vn",
        "fare_amount": 50000.0
    }
    redacted = router.redact_pii_for_warning(raw)

    # Plain text PII must NOT exist in warning payload
    assert redacted["customer_phone"] == "098*****21"
    assert redacted["customer_name"] == "[REDACTED_NAME]"
    assert redacted["customer_email"] == "r***@***.com"
    # Technical metrics preserved
    assert redacted["fare_amount"] == 50000.0
    assert redacted["trip_id"] == "T_WARN_1"


# =============================================================================
# 6. TEST DATABASE PERSISTENCE END-TO-END
# =============================================================================

def test_database_persistence_integration():
    """Verify that execution writes cleanly to PostgreSQL tables."""
    try:
        conn = get_db_connection()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not accessible locally: {exc}")

    try:
        records = [
            {"trip_id": "DB_VAL_01", "vehicle_vin": "VF8_01", "customer_phone": "0987654321", "fare_amount": 50000.0, "trip_distance_km": 3.0, "subject_zone": "VN", "pickup_latitude": 21.028511, "pickup_longitude": 105.854444},
            {"trip_id": "DB_FAIL_01", "vehicle_vin": "VF8_02", "customer_phone": "0912345678", "fare_amount": -100.0, "trip_distance_km": 3.0, "subject_zone": "VN"},
            {"trip_id": "DB_WARN_01", "vehicle_vin": "VF8_03", "customer_phone": "0933333333", "fare_amount": 50000.0, "trip_distance_km": 3.0, "currency_unverified": True, "subject_zone": "VN"},
        ]

        lane_a_data = execute_lane_a_detectors("trips", records)
        lane_b_data = execute_lane_b_policy("trips", records)
        run_id = f"test_db_run_{uuid.uuid4().hex[:6]}"

        metrics = execute_lane_c_merge_and_persist(
            dataset_id="trips",
            records=records,
            lane_a_data=lane_a_data,
            lane_b_data=lane_b_data,
            run_id=run_id,
            conn=conn
        )

        assert metrics["scanned"] == 3
        assert metrics["silver"] >= 1
        assert metrics["quarantine"] >= 1

        # Check in Postgres
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM silver.ride_hailing_xanh_sm_trips WHERE _run_id = %s;", (run_id,))
        silver_count = cur.fetchone()[0]
        assert silver_count == metrics["silver"]

        cur.execute("SELECT count(*) FROM quarantine.records WHERE run_id = %s;", (run_id,))
        quar_count = cur.fetchone()[0]
        assert quar_count == metrics["quarantine"]

    finally:
        conn.close()
