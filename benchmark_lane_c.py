"""
Lane C Benchmark Script:
Profiles memory and execution time across 57,600 records of synthetic_ev_telemetry_ved_ref.csv
for batch sizes: Unbatched (57,600), 5,000, 2,000 (Default), 1,000, 500.
"""

import csv
import time
import tracemalloc
import gc
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter
from dags.parallel_evaluation_engine import execute_lane_c_merge_and_persist


CSV_PATH = "data/vingroup_pii_faulty_testset_3zone/synthetic_ev_telemetry_ved_ref.csv"


def load_dataset(filepath: str, limit: int = 57600) -> List[Dict[str, Any]]:
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            records.append(row)
    return records


def generate_mock_verdicts(records: List[Dict[str, Any]]):
    """
    Generate realistic Lane A and Lane B verdicts:
    ~90% PASS, ~6% WARNING (Lane B advisory), ~4% FAIL (Quarantine)
    """
    lane_a = {}
    lane_b = {}

    for i, r in enumerate(records):
        pk = r["record_id"]
        mod = i % 100
        if mod < 4:
            # Quarantine via Lane A
            lane_a[pk] = {"status": "FAIL", "signals": [{"metric_or_relationship": "battery_soc", "rule_id": "L1_PHYSICAL_RANGE_BATTERY_SOC"}], "evidence": ["battery_soc out of physical range"]}
            lane_b[pk] = {"record_id": pk, "status": "PASS", "treated_record": r, "raw_record": r}
        elif mod < 10:
            # Warning via Lane B
            lane_a[pk] = {"status": "PASS", "signals": [], "evidence": []}
            lane_b[pk] = {
                "record_id": pk,
                "status": "WARNING",
                "treated_record": r,
                "raw_record": r,
                "compliance_evidence": ["Law 91/2025 Advisory warning"],
                "violations": []
            }
        else:
            # Silver PASS
            lane_a[pk] = {"status": "PASS", "signals": [], "evidence": []}
            lane_b[pk] = {"record_id": pk, "status": "PASS", "treated_record": r, "raw_record": r}

    return lane_a, lane_b


def run_benchmark_for_batch_size(records, lane_a, lane_b, batch_size: int, label: str):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()

    with patch("dags.parallel_evaluation_engine.get_db_connection", return_value=mock_conn), \
         patch("dags.parallel_evaluation_engine.execute_values") as mock_exec_vals, \
         patch("dags.parallel_evaluation_engine.cleanup_run_persistence"):

        result = execute_lane_c_merge_and_persist(
            dataset_id="telemetry",
            records=records,
            lane_a_data=lane_a,
            lane_b_data=lane_b,
            run_id=f"bench-{batch_size}",
            batch_size=batch_size
        )

    t1 = time.perf_counter()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    exec_vals_calls = mock_exec_vals.call_count
    elapsed_sec = t1 - t0
    peak_mb = peak_mem / (1024 * 1024)

    return {
        "label": label,
        "batch_size": batch_size,
        "elapsed_sec": round(elapsed_sec, 3),
        "peak_mb": round(peak_mb, 2),
        "records_per_sec": round(len(records) / elapsed_sec, 1),
        "execute_values_calls": exec_vals_calls,
        "silver": result["silver"],
        "quarantine": result["quarantine"],
        "warning": result["warning"],
    }


def main():
    print(f"Loading {CSV_PATH}...")
    records = load_dataset(CSV_PATH)
    total_records = len(records)
    print(f"Loaded {total_records} records.")

    print("Generating simulated Lane A and Lane B verdicts...")
    lane_a, lane_b = generate_mock_verdicts(records)
    print("Verdicts generated. Running benchmark matrix...\n")

    test_configs = [
        (57600, "Unbatched (57,600)"),
        (5000,  "Batch 5,000"),
        (2000,  "Batch 2,000 (Default)"),
        (1000,  "Batch 1,000"),
        (500,   "Batch 500"),
    ]

    results = []
    print(f"{'Configuration':<25} | {'Time (s)':<10} | {'Peak RAM (MB)':<14} | {'Throughput (rec/s)':<20} | {'DB Calls':<10}")
    print("-" * 88)

    for bsize, label in test_configs:
        res = run_benchmark_for_batch_size(records, lane_a, lane_b, bsize, label)
        results.append(res)
        print(f"{res['label']:<25} | {res['elapsed_sec']:<10.3f} | {res['peak_mb']:<14.2f} | {res['records_per_sec']:<20.1f} | {res['execute_values_calls']:<10}")

    print("-" * 88)
    print(f"Sample breakdown: Silver={results[0]['silver']}, Quarantine={results[0]['quarantine']}, Warning={results[0]['warning']}")


if __name__ == "__main__":
    main()
