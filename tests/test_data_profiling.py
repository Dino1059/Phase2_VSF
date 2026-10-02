"""
Automated Tests for Task 2: Data Profiling Engine & Catalog Persistence
Verifies:
1. Schema non-duplication and integrity of catalog.table_profiles, catalog.column_profiles, and view catalog.v_column_profiles.
2. Descriptive statistics and statistical signal detection (negative values, zero variance).
3. PII sensitivity indicators as risk flags (NOT compliance conclusions).
4. Configurable health scoring without hardcoded penalties.
5. FastAPI endpoints /datasets/{dataset_id}/profile and /api/profiling/overview.
"""

import pytest
from fastapi.testclient import TestClient
from database.profiler_engine import (
    DataProfilerEngine,
    ProfilingConfig,
    HealthScoreWeights,
    get_db_connection,
)
from backend.api.main import app

client = TestClient(app)


def test_profiler_engine_single_and_all():
    """Verify DataProfilerEngine profiles bronze tables into catalog schema."""
    profiler = DataProfilerEngine()
    results = profiler.profile_all_datasets()
    assert len(results) == 8, f"Expected 8 datasets, got {len(results)}"

    # Check synthetic_ev_telemetry_ved_ref
    telem = next((r for r in results if r["dataset_id"] == "synthetic_ev_telemetry_ved_ref"), None)
    assert telem is not None
    assert telem["total_rows"] == 57600
    assert telem["columns_count"] == 21
    assert 80.0 <= telem["health_score"] <= 100.0


def test_schema_non_duplication_and_view():
    """Verify that catalog.column_profiles references column_id and v_column_profiles joins seamlessly."""
    conn = get_db_connection()
    try:
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. column_profiles should have column_id foreign key, not column_name
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'catalog' AND table_name = 'column_profiles';
            """)
            col_names = [r["column_name"] for r in cur.fetchall()]
            assert "column_id" in col_names
            assert "profile_id" in col_names
            assert "column_name" not in col_names, "column_name is redundant with catalog.columns"
            assert "data_type" not in col_names, "data_type is redundant with catalog.columns"

            # 2. View catalog.v_column_profiles joins both
            cur.execute("""
                SELECT column_name, data_type, pii_role, null_count, unique_count, signals
                FROM catalog.v_column_profiles
                WHERE dataset_id = 'synthetic_ev_telemetry_ved_ref' AND column_name = 'battery_soc';
            """)
            row = cur.fetchone()
            assert row is not None
            assert row["column_name"] == "battery_soc"
            assert row["null_count"] == 0
            assert row["unique_count"] > 1000

            # 3. Check negative value signal in battery_soc
            signals = row["signals"]
            neg_sig = next((s for s in signals if s.get("signal_type") == "negative_values_observed"), None)
            assert neg_sig is not None, "Expected negative_values_observed signal on battery_soc"
            assert neg_sig["count"] > 0
            assert float(neg_sig["min_val"]) < 0
    finally:
        conn.close()


def test_pii_sensitivity_risk_flag_not_compliance():
    """Verify that personal data is captured as pii_risk_indicator (not compliance pass/fail)."""
    conn = get_db_connection()
    try:
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT column_name, pii_role, signals
                FROM catalog.v_column_profiles
                WHERE dataset_id = 'dim_customers' AND is_personal_data = true;
            """)
            rows = cur.fetchall()
            assert len(rows) >= 4, "Expected personal data columns in dim_customers"
            for r in rows:
                signals = r["signals"]
                pii_sig = next((s for s in signals if s.get("signal_type") == "pii_risk_indicator"), None)
                assert pii_sig is not None
                assert pii_sig["category"] == "sensitivity"
                assert "Contains personal data" in pii_sig["detail"]
                # Must not contain rule compliance pass/fail verdicts
                assert "VIOLATION" not in pii_sig["detail"]
                assert "FAILED" not in pii_sig["detail"]
    finally:
        conn.close()


def test_configurable_health_score():
    """Verify health score changes with custom weights and is not hardcoded."""
    # Strict completeness config: 100% weight on completeness
    strict_comp_config = ProfilingConfig(
        weights=HealthScoreWeights(completeness=1.0, validity=0.0, uniqueness=0.0)
    )
    profiler_comp = DataProfilerEngine(config=strict_comp_config)
    res_comp = profiler_comp._compute_health_score(
        num_cols=10,
        total_null_pct_sum=1.0, # 10% average nulls
        validity_issues_count=0,
        constant_cols_count=0
    )
    assert res_comp == 90.0, f"Expected 90.0% completeness score, got {res_comp}"

    # Strict validity config: 100% weight on validity
    strict_val_config = ProfilingConfig(
        weights=HealthScoreWeights(completeness=0.0, validity=1.0, uniqueness=0.0)
    )
    profiler_val = DataProfilerEngine(config=strict_val_config)
    res_val = profiler_val._compute_health_score(
        num_cols=10,
        total_null_pct_sum=0.0,
        validity_issues_count=2, # 2 columns with irregularities
        constant_cols_count=0
    )
    assert res_val == 80.0, f"Expected 80.0% validity score, got {res_val}"


def test_fastapi_profile_endpoints():
    """Verify FastAPI profiling endpoints return expected structure for UI."""
    # 1. POST /datasets/{dataset_id}/profile
    res = client.post("/datasets/synthetic_ev_telemetry_ved_ref/profile")
    assert res.status_code == 200
    data = res.json()
    assert data["dataset"] == "synthetic_ev_telemetry_ved_ref"
    assert data["total_rows"] == 57600
    assert data["columns_count"] == 21
    assert "health_score" in data
    assert len(data["columns"]) == 21
    assert "tables" in data
    assert len(data["tables"]) >= 8

    # 2. GET /api/profiling/overview
    res_ov = client.get("/api/profiling/overview")
    assert res_ov.status_code == 200
    ov_data = res_ov.json()
    assert len(ov_data) >= 8
    first_tbl = ov_data[0]
    assert "dataset_id" in first_tbl
    assert "health_score" in first_tbl
    assert "signals_summary" in first_tbl
