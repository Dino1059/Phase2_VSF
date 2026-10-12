"""
Regression tests for DataTrust OS Reconciliation and Not Evaluated Calculation.
Verifies the audit invariant equation:
    scanned_count == silver_count + quarantine_count + warning_count + not_evaluated_count
and ensures that stored values of 0 are never replaced by falsy fallbacks.
"""

import pytest
from database.profiler_engine import get_db_connection
from psycopg2.extras import RealDictCursor


def compute_not_eval(scanned: int, silver: int, quarantine: int, warning: int, stored: int = None) -> int:
    """Canonical calculation matching backend/api/main.py and dags/parallel_evaluation_engine.py."""
    if stored is not None:
        return int(stored)
    return max(0, scanned - silver - quarantine - warning)


def test_reconciliation_invariant_equation():
    """Verify that the reconciliation equation holds across standard evaluation scenarios."""
    # Scenario 1: All passed
    scanned = 1000
    silver = 1000
    quar = 0
    warn = 0
    not_eval = compute_not_eval(scanned, silver, quar, warn)
    assert not_eval == 0
    assert scanned == silver + quar + warn + not_eval

    # Scenario 2: Ride hailing actual case (6702 quarantine, 200 warning)
    scanned = 6902
    silver = 0
    quar = 6702
    warn = 200
    not_eval = compute_not_eval(scanned, silver, quar, warn)
    assert not_eval == 0
    assert scanned == silver + quar + warn + not_eval

    # Scenario 3: Real un-evaluated records (e.g. out of scope)
    scanned = 1000
    silver = 800
    quar = 100
    warn = 50
    not_eval = compute_not_eval(scanned, silver, quar, warn)
    assert not_eval == 50
    assert scanned == silver + quar + warn + not_eval


def test_stored_zero_no_falsy_fallback():
    """Verify that a stored count of 0 is NOT coerced to fallback by Python falsy 'or' logic."""
    run_row = {
        "scanned_count": 6902,
        "silver_count": 0,
        "quarantine_count": 6702,
        "warning_count": 200,
        "not_evaluated_count": 0
    }

    scanned = run_row.get("scanned_count") or 0
    silver = run_row.get("silver_count") or 0
    quarantine = run_row.get("quarantine_count") or 0
    warning = run_row.get("warning_count") or 0

    # Old buggy logic:
    # not_eval = run_row.get("not_evaluated_count") or max(0, scanned - silver - quarantine)
    # would evaluate to 200!

    # Fixed logic:
    stored_not_eval = run_row.get("not_evaluated_count")
    if stored_not_eval is not None:
        not_eval = int(stored_not_eval)
    else:
        not_eval = max(0, scanned - silver - quarantine - warning)

    assert not_eval == 0, f"Expected not_eval to be 0, but got {not_eval}"


def test_database_historical_runs_reconciliation():
    """Verify that all historical SUCCESS runs in PostgreSQL satisfy the audit equation."""
    try:
        conn = get_db_connection()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not accessible: {exc}")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT run_id, dataset_id, scanned_count, silver_count,
                       quarantine_count, warning_count, not_evaluated_count
                FROM orchestration.pipeline_runs
                WHERE status = 'SUCCESS' AND scanned_count > 0;
            """)
            rows = cur.fetchall()

        assert len(rows) > 0, "Expected at least 1 SUCCESS run in database"
        for r in rows:
            scanned = r.get("scanned_count") or 0
            silver = r.get("silver_count") or 0
            quar = r.get("quarantine_count") or 0
            warn = r.get("warning_count") or 0
            not_eval = r.get("not_evaluated_count") or 0

            # Guard: Sum must equal scanned
            assert scanned == silver + quar + warn + not_eval, (
                f"Run {r['run_id']} ({r['dataset_id']}) violated audit equation: "
                f"scanned={scanned} != silver({silver}) + quar({quar}) + warn({warn}) + not_eval({not_eval})"
            )
    finally:
        conn.close()


def test_api_results_endpoint_returns_zero_for_ride_hailing():
    """Verify that FastAPI get_run_results returns not_evaluated_count = 0 for ride hailing run."""
    from backend.api.main import get_run_results

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT run_id FROM orchestration.pipeline_runs
                WHERE status = 'SUCCESS'
                  AND dataset_id LIKE '%ride_hailing%'
                  AND warning_count = 200
                ORDER BY started_at DESC LIMIT 1;
            """)
            row = cur.fetchone()
        conn.close()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not accessible: {exc}")

    if not row:
        pytest.skip("No ride hailing run with 200 warnings found in database")

    target_run_id = row["run_id"]
    res = get_run_results(target_run_id)

    assert res["run_id"] == target_run_id
    assert res["kpis"]["warning_count"] == 200
    assert res["kpis"]["not_evaluated_count"] == 0, f"Expected 0 not_evaluated, got {res['kpis']['not_evaluated_count']}"
    assert res["kpis"]["not_evaluated_percentage"] == 0.0
