"""
Tests for Lane C Optimization, Deterministic Idempotency, Duck-typing, and Duration Fix (Plan V2).
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
import pytest

from backend.engine.hierarchical_policy_processor import LaneBVerdict
from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter, _v_get
from dags.parallel_evaluation_engine import (
    cleanup_run_persistence,
    execute_lane_c_merge_and_persist,
    persist_silver_records_chunk,
    persist_quarantine_records_chunk,
    persist_warning_records_chunk,
    persist_lane_b_evidence_chunk,
)


# =============================================================================
# 1. TEST DETERMINISTIC IDEMPOTENCY (UUID5)
# =============================================================================

def test_quarantine_and_warning_deterministic_uuid5():
    """Verify quarantine_id and warning_id use deterministic UUID5 based on run_id:dataset_id:pk."""
    router = VerdictMergerAndRouter()
    dataset = "trips"
    run_id = "run-idemp-001"
    
    raw_records = [
        {"trip_id": "T-FAIL-01", "fare_amount": -100.0, "subject_zone": "VN"},
        {"trip_id": "T-WARN-01", "fare_amount": 50000.0, "customer_phone": "0987654321", "subject_zone": "VN"},
    ]
    
    # Lane A fails T-FAIL-01, passes T-WARN-01
    lane_a_map = {
        "T-FAIL-01": {"status": "FAIL", "signals": ["NEGATIVE_FARE"], "evidence": []},
        "T-WARN-01": {"status": "PASS", "signals": [], "evidence": []},
    }
    
    # Lane B passes T-FAIL-01, warns on T-WARN-01
    lane_b_map = {
        "T-FAIL-01": LaneBVerdict(record_id="T-FAIL-01", status="PASS", treated_record=raw_records[0], raw_record=raw_records[0]),
        "T-WARN-01": LaneBVerdict(
            record_id="T-WARN-01",
            status="WARNING",
            treated_record={**raw_records[1], "customer_phone": "098*****21"},
            raw_record=raw_records[1],
            compliance_evidence=["ADVISORY_PII"]
        ),
    }

    # Run 1
    result_1 = router.merge_and_route(dataset, raw_records, lane_a_map, lane_b_map, run_id=run_id)
    assert result_1.quarantine_count == 1
    assert result_1.warning_count == 1
    
    q_id_1 = result_1.quarantine_records[0]["quarantine_id"]
    w_id_1 = result_1.warning_records[0]["warning_id"]

    # Verify expected deterministic UUID5 calculation
    expected_q_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"quarantine:{run_id}:{dataset}:T-FAIL-01"))
    expected_w_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"warning:{run_id}:{dataset}:T-WARN-01"))
    
    assert q_id_1 == expected_q_id
    assert w_id_1 == expected_w_id

    # Run 2 with identical inputs (simulating Airflow task retry)
    result_2 = router.merge_and_route(dataset, raw_records, lane_a_map, lane_b_map, run_id=run_id)
    assert result_2.quarantine_records[0]["quarantine_id"] == q_id_1
    assert result_2.warning_records[0]["warning_id"] == w_id_1

    # Run 3 with different run_id produces different deterministic IDs
    result_3 = router.merge_and_route(dataset, raw_records, lane_a_map, lane_b_map, run_id="run-idemp-002")
    assert result_3.quarantine_records[0]["quarantine_id"] != q_id_1
    assert result_3.warning_records[0]["warning_id"] != w_id_1


# =============================================================================
# 2. TEST DUCK-TYPING PARITY ACROSS LANE B INPUT FORMATS
# =============================================================================

def _strip_volatile_fields(records):
    """Strip wall-clock timestamps for strict content equality assertions."""
    cleaned = []
    for r in records:
        c = dict(r)
        c.pop("detected_at", None)
        c.pop("quarantined_at", None)
        c.pop("_processed_at", None)
        cleaned.append(c)
    return cleaned


def test_lane_b_duck_typing_parity():
    """Verify that merge_and_route yields identical business results for List[LaneBVerdict], List[dict], Dict[pk, dict], Dict[pk, LaneBVerdict]."""
    router = VerdictMergerAndRouter()
    dataset = "trips"
    run_id = "run-duck-typing"

    raw_records = [
        {"trip_id": "T1", "val": 10},
        {"trip_id": "T2", "val": 20},
        {"trip_id": "T3", "val": 30},
    ]

    lane_a_map = {
        "T1": {"status": "PASS", "signals": [], "evidence": []},
        "T2": {"status": "PASS", "signals": [], "evidence": []},
        "T3": {"status": "FAIL", "signals": ["BAD_VAL"], "evidence": []},
    }

    # Form a: List[LaneBVerdict]
    form_a = [
        LaneBVerdict(record_id="T1", status="PASS", treated_record={"trip_id": "T1", "val": 10}, raw_record=raw_records[0]),
        LaneBVerdict(record_id="T2", status="WARNING", treated_record={"trip_id": "T2", "val": 20}, raw_record=raw_records[1], compliance_evidence=["ADVISORY"]),
        LaneBVerdict(record_id="T3", status="PASS", treated_record={"trip_id": "T3", "val": 30}, raw_record=raw_records[2]),
    ]

    # Form b: List[dict]
    form_b = [
        {"record_id": "T1", "status": "PASS", "treated_record": {"trip_id": "T1", "val": 10}, "raw_record": raw_records[0]},
        {"record_id": "T2", "status": "WARNING", "treated_record": {"trip_id": "T2", "val": 20}, "raw_record": raw_records[1], "compliance_evidence": ["ADVISORY"]},
        {"record_id": "T3", "status": "PASS", "treated_record": {"trip_id": "T3", "val": 30}, "raw_record": raw_records[2]},
    ]

    # Form c: Dict[str, dict]
    form_c = {v["record_id"]: v for v in form_b}

    # Form d: Dict[str, LaneBVerdict]
    form_d = {v.record_id: v for v in form_a}

    res_a = router.merge_and_route(dataset, raw_records, lane_a_map, form_a, run_id=run_id)
    res_b = router.merge_and_route(dataset, raw_records, lane_a_map, form_b, run_id=run_id)
    res_c = router.merge_and_route(dataset, raw_records, lane_a_map, form_c, run_id=run_id)
    res_d = router.merge_and_route(dataset, raw_records, lane_a_map, form_d, run_id=run_id)

    # All counts must match exactly
    assert res_a.silver_count == res_b.silver_count == res_c.silver_count == res_d.silver_count == 1
    assert res_a.warning_count == res_b.warning_count == res_c.warning_count == res_d.warning_count == 1
    assert res_a.quarantine_count == res_b.quarantine_count == res_c.quarantine_count == res_d.quarantine_count == 1

    # Records and lineage hashes must match exactly (ignoring microsecond timestamps)
    assert _strip_volatile_fields(res_a.silver_records) == _strip_volatile_fields(res_b.silver_records) == _strip_volatile_fields(res_c.silver_records) == _strip_volatile_fields(res_d.silver_records)
    assert _strip_volatile_fields(res_a.warning_records) == _strip_volatile_fields(res_b.warning_records) == _strip_volatile_fields(res_c.warning_records) == _strip_volatile_fields(res_d.warning_records)
    assert _strip_volatile_fields(res_a.quarantine_records) == _strip_volatile_fields(res_b.quarantine_records) == _strip_volatile_fields(res_c.quarantine_records) == _strip_volatile_fields(res_d.quarantine_records)


def test_v_get_helper():
    """Verify _v_get gracefully handles LaneBVerdict, dict, and default fallbacks."""
    verdict_obj = LaneBVerdict(record_id="REC-01", status="PASS", treated_record={}, raw_record={})
    verdict_dict = {"record_id": "REC-01", "status": "PASS"}

    assert _v_get(verdict_obj, "record_id") == "REC-01"
    assert _v_get(verdict_dict, "record_id") == "REC-01"
    assert _v_get(verdict_obj, "non_existent", "default_val") == "default_val"
    assert _v_get(verdict_dict, "non_existent", "default_val") == "default_val"
    assert _v_get(None, "record_id", "fallback") == "fallback"


# =============================================================================
# 3. TEST AUDIT SEMANTICS & HASH STABILITY
# =============================================================================

def test_lineage_hash_stability():
    """Verify compute_lineage_hash preserves standard json.dumps sorting and default separators."""
    record = {"b": 2, "a": 1, "nested": {"z": 10, "y": 20}}
    run_id = "test-run"
    pk_val = "T-01"

    hash1 = VerdictMergerAndRouter.compute_lineage_hash(run_id, pk_val, record)

    # Reordered keys in dicts must produce identical hash (sort_keys=True)
    record_reordered = {"nested": {"y": 20, "z": 10}, "a": 1, "b": 2}
    hash2 = VerdictMergerAndRouter.compute_lineage_hash(run_id, pk_val, record_reordered)

    assert hash1 == hash2

    # Verify exact manual computation using standard json.dumps
    serialized = json.dumps(record, sort_keys=True, default=str)
    expected_hash = hashlib.sha256(f"{run_id}:{pk_val}:{serialized}".encode("utf-8")).hexdigest()
    assert hash1 == expected_hash


# =============================================================================
# 4. TEST SCANNED COUNT INVARIANT
# =============================================================================

def test_scanned_count_invariant():
    """Verify invariant: scanned_count == silver + quarantine + warning."""
    router = VerdictMergerAndRouter()
    dataset = "trips"
    run_id = "run-invariant"

    records = [
        {"trip_id": f"T-{i}", "val": i}
        for i in range(20)
    ]

    lane_a_map = {}
    lane_b_map = {}

    for i, r in enumerate(records):
        pk = r["trip_id"]
        if i < 10:
            # Silver: A=PASS, B=PASS
            lane_a_map[pk] = {"status": "PASS", "signals": [], "evidence": []}
            lane_b_map[pk] = {"record_id": pk, "status": "PASS", "treated_record": r, "raw_record": r}
        elif i < 15:
            # Warning: A=PASS, B=WARNING
            lane_a_map[pk] = {"status": "PASS", "signals": [], "evidence": []}
            lane_b_map[pk] = {"record_id": pk, "status": "WARNING", "treated_record": r, "raw_record": r, "compliance_evidence": ["ADVISORY"]}
        else:
            # Quarantine: A=FAIL, B=PASS
            lane_a_map[pk] = {"status": "FAIL", "signals": ["ERR"], "evidence": []}
            lane_b_map[pk] = {"record_id": pk, "status": "PASS", "treated_record": r, "raw_record": r}

    result = router.merge_and_route(dataset, records, lane_a_map, lane_b_map, run_id=run_id)

    total_scanned = len(records)
    assert total_scanned == 20
    assert result.scanned_count == 20
    assert result.silver_count == 10
    assert result.warning_count == 5
    assert result.quarantine_count == 5
    assert result.scanned_count == result.silver_count + result.warning_count + result.quarantine_count


# =============================================================================
# 5. TEST BATCH SIZE FALLBACK & PERSISTENCE CHUNKING
# =============================================================================

def test_batch_size_validation_and_chunking():
    """Verify execute_lane_c_merge_and_persist validates batch_size and falls back to 2000 for invalid inputs."""
    records = [{"trip_id": f"T{i}", "fare_amount": 100.0} for i in range(25)]
    lane_a = {f"T{i}": {"status": "PASS", "signals": [], "evidence": []} for i in range(25)}
    lane_b = {f"T{i}": {"record_id": f"T{i}", "status": "PASS", "treated_record": records[i], "raw_record": records[i]} for i in range(25)}

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("dags.parallel_evaluation_engine.get_db_connection", return_value=mock_conn), \
         patch("dags.parallel_evaluation_engine.execute_values") as mock_exec_vals, \
         patch("dags.parallel_evaluation_engine.cleanup_run_persistence") as mock_cleanup:

        # Test invalid batch sizes: 0, negative, string
        for invalid_size in [0, -500, "invalid_str"]:
            result = execute_lane_c_merge_and_persist(
                dataset_id="trips",
                records=records,
                lane_a_data=lane_a,
                lane_b_data=lane_b,
                run_id="run-batch-test",
                batch_size=invalid_size
            )
            assert result["silver"] == 25
            assert mock_cleanup.called

        # Test chunking with batch_size=10 on 25 records (should execute 3 chunk batches: 10, 10, 5)
        mock_cleanup.reset_mock()
        mock_exec_vals.reset_mock()

        result_chunked = execute_lane_c_merge_and_persist(
            dataset_id="trips",
            records=records,
            lane_a_data=lane_a,
            lane_b_data=lane_b,
            run_id="run-batch-test",
            batch_size=10
        )
        assert result_chunked["silver"] == 25
        assert mock_cleanup.call_count == 1
        # execute_values should have been called 3 times for silver chunk insertions
        assert mock_exec_vals.call_count >= 3


def test_cleanup_run_persistence():
    """Verify cleanup_run_persistence executes deletion of prior records for the specified run_id."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    cleanup_run_persistence(mock_conn, "test-run-cleanup-123")

    # Ensure execute was called for quarantine, warning, findings, record_policy_executions
    executed_sqls = [call_args[0][0] for call_args in mock_cur.execute.call_args_list]
    assert any("finding_quarantine_records" in sql for sql in executed_sqls)
    assert any("quarantine.records" in sql for sql in executed_sqls)
    assert any("warning.records" in sql for sql in executed_sqls)
    assert any("audit.findings" in sql for sql in executed_sqls)
    assert any("audit.record_policy_executions" in sql for sql in executed_sqls)
    # Check that run_id parameter was passed
    for call_args in mock_cur.execute.call_args_list:
        params = call_args[0][1]
        assert "test-run-cleanup-123" in params


# =============================================================================
# 6. TEST DURATION CALCULATION LOGIC
# =============================================================================

def test_duration_ms_calculation_logic():
    """Verify that execution_duration_ms=0 is preserved, and missing duration calculates accurately from timestamps."""
    # Simulation of the API duration calculation logic from main.py

    def calculate_duration(r):
        dur_ms = r.get("execution_duration_ms")
        if dur_ms is None and r.get("started_at") and r.get("ended_at"):
            dur_ms = max(0, int((r["ended_at"] - r["started_at"]).total_seconds() * 1000))
        elif dur_ms is None and r.get("started_at") and (r.get("status") or "").upper() == "RUNNING":
            dur_ms = max(0, int((datetime.now(timezone.utc) - r["started_at"]).total_seconds() * 1000))
        dur_mins = round(dur_ms / 60000, 1) if dur_ms is not None else 0.0
        return dur_ms, dur_mins

    # Case 1: dur_ms is explicitly 0 (valid instant run) -> must NOT become 60000 / 1.0 min
    row_zero = {"execution_duration_ms": 0, "status": "SUCCESS"}
    dur_ms, dur_mins = calculate_duration(row_zero)
    assert dur_ms == 0
    assert dur_mins == 0.0

    # Case 2: dur_ms is 800000 ms (~13.3 mins)
    row_explicit = {"execution_duration_ms": 800000, "status": "SUCCESS"}
    dur_ms, dur_mins = calculate_duration(row_explicit)
    assert dur_ms == 800000
    assert dur_mins == 13.3

    # Case 3: dur_ms is None, but started_at and ended_at exist (800 seconds diff = 13.3 mins)
    t0 = datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=800)
    row_fallback = {"execution_duration_ms": None, "started_at": t0, "ended_at": t1, "status": "SUCCESS"}
    dur_ms, dur_mins = calculate_duration(row_fallback)
    assert dur_ms == 800000
    assert dur_mins == 13.3

    # Case 4: dur_ms is None, running for 120 seconds
    t_running = datetime.now(timezone.utc) - timedelta(seconds=120)
    row_running = {"execution_duration_ms": None, "started_at": t_running, "ended_at": None, "status": "RUNNING"}
    dur_ms, dur_mins = calculate_duration(row_running)
    assert dur_ms >= 120000
    assert dur_mins == 2.0

    # Case 5: All None
    row_empty = {"execution_duration_ms": None, "started_at": None, "ended_at": None, "status": "FAILED"}
    dur_ms, dur_mins = calculate_duration(row_empty)
    assert dur_ms is None
    assert dur_mins == 0.0
