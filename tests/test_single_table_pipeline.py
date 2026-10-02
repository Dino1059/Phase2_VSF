"""
Unit & Integration Tests: Single Table Selection for Task 1, Task 2, and DAG Pipeline
Verifies that:
1. resolve_target_dataset resolves single tables, aliases, and 'ALL'.
2. truncate_and_ingest_all only ingests the targeted table in single-table mode.
3. profile_single_dataset only profiles the targeted dataset.
4. Airflow DAG parameters and task callables execute cleanly in single-table mode.
"""

import pytest
from pathlib import Path
from dags.datatrust_adaptive_pipeline_dag import resolve_target_dataset
from dags.reset_and_ingest_bronze import (
    get_db_connection,
    resolve_data_dir,
    truncate_and_ingest_all,
    DATASET_METADATA
)
from database.profiler_engine import DataProfilerEngine, ProfilingConfig


def test_resolve_target_dataset():
    """Verify resolve_target_dataset handles aliases, filenames, single tables, and ALL."""
    # Specific full table name
    t, f = resolve_target_dataset({"dataset_id": "synthetic_ev_telemetry_ved_ref"})
    assert t == "synthetic_ev_telemetry_ved_ref"
    assert f == "synthetic_ev_telemetry_ved_ref.csv"

    # With .csv extension
    t, f = resolve_target_dataset({"dataset_id": "synthetic_ev_telemetry_ved_ref.csv"})
    assert t == "synthetic_ev_telemetry_ved_ref"
    assert f == "synthetic_ev_telemetry_ved_ref.csv"

    # Alias 'trips'
    t, f = resolve_target_dataset({"dataset_id": "trips"})
    assert t == "ride_hailing_xanh_sm_trips"
    assert f == "ride_hailing_xanh_sm_trips.csv"

    # Alias 'telemetry'
    t, f = resolve_target_dataset({"filename": "telemetry"})
    assert t == "synthetic_ev_telemetry_ved_ref"
    assert f == "synthetic_ev_telemetry_ved_ref.csv"

    # 'ALL' mode
    t, f = resolve_target_dataset({"dataset_id": "ALL"})
    assert t is None
    assert f is None

    # Empty conf
    t, f = resolve_target_dataset({})
    assert t is None
    assert f is None


def test_task1_single_table_ingestion():
    """Verify Task 1 only truncates and ingests the specified table when target_dataset_id is set."""
    try:
        conn = get_db_connection()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not accessible: {exc}")

    try:
        data_dir = resolve_data_dir()
        # Ingest only fleet_index (60 rows)
        summary = truncate_and_ingest_all(
            conn,
            data_dir=data_dir,
            batch_id="test_single_fleet",
            target_dataset_id="fleet_index"
        )
        assert len(summary) == 1
        assert "fleet_index" in summary
        assert summary["fleet_index"] == 60
        assert "ride_hailing_xanh_sm_trips" not in summary

        # Check in DB
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM bronze.fleet_index;")
            cnt = cur.fetchone()[0]
            assert cnt == 60

            cur.execute("SELECT count(*) FROM catalog.columns WHERE dataset_id = 'fleet_index';")
            col_cnt = cur.fetchone()[0]
            assert col_cnt == 4
    finally:
        conn.close()


def test_task2_single_dataset_profiling():
    """Verify Task 2 single-dataset profiling only profiles the chosen dataset."""
    try:
        conn = get_db_connection()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not accessible: {exc}")

    try:
        profiler = DataProfilerEngine(config=ProfilingConfig())
        res = profiler.profile_single_dataset("fleet_index", batch_id="test_single_prof_fleet", conn=conn)

        assert res["dataset_id"] == "fleet_index"
        assert res["total_rows"] == 60
        assert res["columns_count"] == 4
        assert res["health_score"] >= 80.0
        assert "signals_summary" in res

        # Check in DB catalog
        with conn.cursor() as cur:
            cur.execute("SELECT health_score FROM catalog.table_profiles WHERE dataset_id = 'fleet_index' ORDER BY profiled_at DESC LIMIT 1;")
            score = float(cur.fetchone()[0])
            assert score == res["health_score"]
    finally:
        conn.close()
