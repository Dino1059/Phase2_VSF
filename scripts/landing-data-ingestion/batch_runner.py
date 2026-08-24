"""
batch_runner.py — Giai đoạn 3: Day-aware batch orchestration.
Lưu tại: scripts/landing-data-ingestion/batch_runner.py

Responsibilities:
1. Call orchestrator.run_analysis(dataset_key, target_day_idx=day_idx, window_days=10).
2. INSERT/UPDATE pipeline_runs.source_ingestion_run_id.
3. Log to demo_ops.batch_run_log for UI observability.
"""

from __future__ import annotations
import hashlib
import logging
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable

from src.db.connection import get_db
from src.orchestrator.orchestrator import DataTrustOrchestrator
from src.services.llm import GemmaLLMAdapter

logger = logging.getLogger(__name__)


def _notify(progress_callback: Optional[Callable[[str, str, dict], None]], stage: str, message: str, metadata: Optional[dict] = None):
    msg = f"⚡ [BatchRunner] [{stage}] {message}"
    logger.info(msg)
    if progress_callback:
        try:
            progress_callback(stage, message, metadata or {})
        except Exception as exc:
            logger.warning(f"progress_callback error: {exc}")


@dataclass
class BatchRunResult:
    run_id: str
    day_idx: int
    status: str  # "started" | "completed" | "error"
    incident_count: int
    duration_ms: int
    error_msg: str = ""
    run_uuid: str = ""
    ingestion_run_id: str = ""  # link to demo_ops.ingestion_runs


def _ingestion_run_id(day_idx: int, run_kind: str) -> str:
    """Generate deterministic ingestion_run_id."""
    import hashlib
    key = f"{day_idx}:{run_kind}"
    return f"ING-{day_idx:04d}-{hashlib.md5(key.encode()).hexdigest()[:6]}"


def _ensure_demo_ops_tables(conn) -> None:
    """Create additive demo_ops tables if they don't exist."""
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS batch_run_id_seq
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demo_ops.batch_run_log (
            run_id          VARCHAR PRIMARY KEY,
            run_uuid        VARCHAR NOT NULL,
            day_idx         BIGINT NOT NULL,
            status          VARCHAR NOT NULL DEFAULT 'started',
            started_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at    TIMESTAMP,
            incident_count  BIGINT NOT NULL DEFAULT 0,
            duration_ms     BIGINT NOT NULL DEFAULT 0,
            error_msg       VARCHAR,
            source_ingestion_run_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demo_ops.batch_orchestrator_state (
            last_run_day_idx BIGINT NOT NULL DEFAULT -1,
            last_run_at      TIMESTAMP
        )
    """)


def _get_or_create_state(conn) -> dict:
    try:
        row = conn.execute(
            "SELECT last_run_day_idx, last_run_at FROM demo_ops.batch_orchestrator_state LIMIT 1"
        ).fetchone()
        if row:
            return {"last_run_day_idx": row[0], "last_run_at": row[1]}
    except Exception:
        pass
    conn.execute("INSERT INTO demo_ops.batch_orchestrator_state DEFAULT VALUES")
    return {"last_run_day_idx": -1, "last_run_at": None}


def run_day_batch(
    day_idx: int,
    dataset_key: str = "vingroup_pilot",
    window_days: int = 10,
    dry_run: bool = False,
    run_kind: str = "WARMUP",
    progress_callback: Optional[Callable[[str, str, dict], None]] = None,
) -> BatchRunResult:
    """
    Run analysis for a single day_idx with window-days lookback.

    Returns a BatchRunResult with incident_count, duration, and status.
    """
    run_uuid = str(uuid.uuid4())[:12]
    db_mgr = get_db()
    conn = db_mgr.get_connection()
    _ensure_demo_ops_tables(conn)

    _notify(progress_callback, "Batch Start", f"Starting Day {day_idx} batch run (dataset='{dataset_key}', kind='{run_kind}', window={window_days}d)...", {"day_idx": day_idx, "run_kind": run_kind})

    result = BatchRunResult(
        run_id=f"BR-{day_idx:04d}",
        day_idx=day_idx,
        status="started",
        incident_count=0,
        duration_ms=0,
        run_uuid=run_uuid,
        ingestion_run_id="",
    )

    # --- Batch run log (idempotent upsert) ---
    existing_row = conn.execute(
        "SELECT 1 FROM demo_ops.batch_run_log WHERE run_id = ?",
        [result.run_id],
    ).fetchone()
    if existing_row:
        conn.execute(
            "UPDATE demo_ops.batch_run_log SET status = 'started' WHERE run_id = ?",
            [result.run_id],
        )
    else:
        conn.execute(
            """
            INSERT INTO demo_ops.batch_run_log (run_id, run_uuid, day_idx, status, source_ingestion_run_id)
            VALUES (?, ?, ?, 'started', NULL)
            """,
            [result.run_id, run_uuid, day_idx],
        )
    conn.commit()

    # --- Ingestion run tracking ---
    snapshot_id = f"SNAP_{day_idx:03d}"
    ingestion_run_id = _ingestion_run_id(day_idx, run_kind)

    existing_ing = conn.execute(
        "SELECT ingestion_run_id FROM demo_ops.ingestion_runs WHERE ingestion_run_id = ?",
        [ingestion_run_id],
    ).fetchone()
    if not existing_ing:
        conn.execute(
            """
            INSERT INTO demo_ops.ingestion_runs
                (ingestion_run_id, snapshot_id, day_idx, run_kind, status, window_start_day, window_end_day)
            VALUES (?, ?, ?, ?, 'RUNNING', ?, ?)
            """,
            [ingestion_run_id, snapshot_id, day_idx, run_kind,
             max(0, day_idx - window_days), day_idx],
        )
        conn.commit()
    result.ingestion_run_id = ingestion_run_id

    # --- State update helper ---
    def _update_state():
        existing_st = conn.execute(
            "SELECT last_run_day_idx FROM demo_ops.batch_orchestrator_state LIMIT 1"
        ).fetchone()
        if existing_st is None:
            conn.execute(
                "INSERT INTO demo_ops.batch_orchestrator_state (last_run_day_idx, last_run_at) VALUES (?, CURRENT_TIMESTAMP)",
                [day_idx],
            )
        else:
            conn.execute(
                "UPDATE demo_ops.batch_orchestrator_state SET last_run_day_idx = ?, last_run_at = CURRENT_TIMESTAMP",
                [day_idx],
            )

    # Step 0: Ensure day data is ingested from landing Parquet into raw.*
    # We do this EVEN in dry_run mode to ensure data is accumulated.
    try:
        _notify(progress_callback, "Day Ingest", f"Ingesting Day {day_idx} data from parquet into raw warehouse...", {"day_idx": day_idx})
        import importlib.util, os
        ingest_script = os.path.join(os.path.dirname(__file__), "day_ingestor.py")
        spec = importlib.util.spec_from_file_location("day_ingestor", ingest_script)
        day_ingestor_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(day_ingestor_mod)
        day_ingestor_mod.ingest_day(day_idx, verbose=False, conn=conn)
    except Exception as ing_err:
        logger.warning(f"day_ingestor failed for day {day_idx}: {ing_err}")

    if dry_run:
        result.status = "completed"
        row_cnt_res = conn.execute(
            "SELECT COALESCE(row_count, 0) FROM demo_ops.landing_day_snapshots WHERE day_idx = ?",
            [day_idx],
        ).fetchone()
        row_cnt = row_cnt_res[0] if row_cnt_res else 0

        conn.execute(
            """
            UPDATE demo_ops.ingestion_runs
            SET status = 'COMPLETED', finished_at = CURRENT_TIMESTAMP, rows_copied_to_raw = ?
            WHERE ingestion_run_id = ?
            """,
            [row_cnt, ingestion_run_id],
        )
        conn.execute(
            "UPDATE demo_ops.batch_run_log SET status = 'completed', completed_at = CURRENT_TIMESTAMP, duration_ms = 0, incident_count = 0, source_ingestion_run_id = ? WHERE run_id = ?",
            [ingestion_run_id, result.run_id],
        )
        _update_state()
        conn.commit()
        _notify(progress_callback, "Batch End", f"Dry run completed for Day {day_idx}.", {"day_idx": day_idx})
        return result

    # --- Real LLM-powered run ---
    start = time.time()
    try:
        _notify(progress_callback, "Orchestrator Run", f"Initializing DataTrustOrchestrator for Day {day_idx} analysis...", {"day_idx": day_idx})
        llm = GemmaLLMAdapter(model="auto")
        orchestrator = DataTrustOrchestrator(llm, project_id=dataset_key)
        orch_result = orchestrator.run_analysis(
            dataset_key=dataset_key,
            table_name=None,
            target_day_idx=day_idx,
            window_days=window_days,
            progress_callback=progress_callback,
        )

        # Count incidents from anomaly stage
        incident_count = 0
        for stage in orch_result.stages:
            if stage.get("stage") == "anomaly_detection":
                incident_count = stage.get("incident_count", 0)
                break

        result.incident_count = incident_count
        result.status = "completed"
        result.duration_ms = int((time.time() - start) * 1000)

        _notify(progress_callback, "Batch End", f"Day {day_idx} batch run COMPLETED: {incident_count} incidents in {result.duration_ms}ms.", {"day_idx": day_idx, "incidents": incident_count, "duration_ms": result.duration_ms})

        # Update ingestion_runs with completion
        row_cnt_res = conn.execute(
            "SELECT COALESCE(row_count, 0) FROM demo_ops.landing_day_snapshots WHERE day_idx = ?",
            [day_idx],
        ).fetchone()
        row_cnt = row_cnt_res[0] if row_cnt_res else 0

        conn.execute(
            """
            UPDATE demo_ops.ingestion_runs
            SET status = 'COMPLETED', finished_at = CURRENT_TIMESTAMP,
                rows_copied_to_raw = ?,
                rows_passed_clean = ?
            WHERE ingestion_run_id = ?
            """,
            [row_cnt, incident_count, ingestion_run_id],
        )

        # Link pipeline_runs.source_ingestion_run_id for the latest run
        try:
            latest_pipeline = conn.execute(
                "SELECT run_id FROM main.pipeline_runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if latest_pipeline:
                conn.execute(
                    "UPDATE main.pipeline_runs SET source_ingestion_run_id = ? WHERE run_id = ?",
                    [ingestion_run_id, latest_pipeline[0]],
                )
        except Exception:
            pass

        conn.execute(
            "UPDATE demo_ops.batch_run_log SET status = 'completed', completed_at = CURRENT_TIMESTAMP, incident_count = ?, duration_ms = ?, source_ingestion_run_id = ? WHERE run_id = ?",
            [incident_count, result.duration_ms, ingestion_run_id, result.run_id],
        )
        _update_state()
        conn.commit()

    except Exception as exc:
        logger.error(f"[BatchRunner] Exception during run_day_batch for day {day_idx}: {exc}", exc_info=True)
        result.status = "error"
        result.error_msg = str(exc)
        result.duration_ms = int((time.time() - start) * 1000)
        _notify(progress_callback, "Batch Error", f"Day {day_idx} batch run FAILED: {exc}", {"day_idx": day_idx, "error": str(exc)})
        conn.execute(
            "UPDATE demo_ops.ingestion_runs SET status = 'FAILED', finished_at = CURRENT_TIMESTAMP, error_message = ? WHERE ingestion_run_id = ?",
            [str(exc), ingestion_run_id],
        )
        conn.execute(
            "UPDATE demo_ops.batch_run_log SET status = 'error', completed_at = CURRENT_TIMESTAMP, error_msg = ?, duration_ms = ?, source_ingestion_run_id = ? WHERE run_id = ?",
            [str(exc), result.duration_ms, ingestion_run_id, result.run_id],
        )
        conn.commit()

    return result


def _ingest_day_only(day_idx: int, dataset_key: str, conn, progress_callback: Optional[Callable[[str, str, dict], None]] = None) -> BatchRunResult:
    """Ingest landing parquet data for a single day WITHOUT running analysis.

    Used during warmup Phase A to accumulate timeseries context before
    running L2-L4 detectors which require sufficient historical data.
    """
    run_uuid = str(uuid.uuid4())[:12]
    ingestion_run_id = _ingestion_run_id(day_idx, "WARMUP_INGEST")
    start = time.time()

    _notify(progress_callback, "Phase A Ingest", f"Warmup Phase A: Ingesting baseline Day {day_idx}...", {"day_idx": day_idx})

    result = BatchRunResult(
        run_id=f"BR-{day_idx:04d}",
        day_idx=day_idx,
        status="started",
        incident_count=0,
        duration_ms=0,
        run_uuid=run_uuid,
        ingestion_run_id=ingestion_run_id,
    )

    try:
        # Ingest day data from landing parquet into raw.*
        import importlib.util, os
        ingest_script = os.path.join(os.path.dirname(__file__), "day_ingestor.py")
        spec = importlib.util.spec_from_file_location("day_ingestor", ingest_script)
        day_ingestor_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(day_ingestor_mod)
        day_ingestor_mod.ingest_day(day_idx, verbose=False, conn=conn)

        result.status = "completed"
        result.duration_ms = int((time.time() - start) * 1000)

        # Track in ingestion_runs
        row_cnt_res = conn.execute(
            "SELECT COALESCE(row_count, 0) FROM demo_ops.landing_day_snapshots WHERE day_idx = ?",
            [day_idx],
        ).fetchone()
        row_cnt = row_cnt_res[0] if row_cnt_res else 0

        existing_ing = conn.execute(
            "SELECT ingestion_run_id FROM demo_ops.ingestion_runs WHERE ingestion_run_id = ?",
            [ingestion_run_id],
        ).fetchone()
        if not existing_ing:
            conn.execute(
                """INSERT INTO demo_ops.ingestion_runs
                    (ingestion_run_id, snapshot_id, day_idx, run_kind, status, window_start_day, window_end_day, finished_at, rows_copied_to_raw)
                VALUES (?, ?, ?, 'WARMUP_INGEST', 'COMPLETED', ?, ?, CURRENT_TIMESTAMP, ?)""",
                [ingestion_run_id, f"SNAP_{day_idx:03d}", day_idx, day_idx, day_idx, row_cnt],
            )
        else:
            conn.execute(
                """UPDATE demo_ops.ingestion_runs
                    SET status = 'COMPLETED', finished_at = CURRENT_TIMESTAMP, rows_copied_to_raw = ?
                    WHERE ingestion_run_id = ?""",
                [row_cnt, ingestion_run_id],
            )

        # Track in batch_run_log
        existing_row = conn.execute(
            "SELECT 1 FROM demo_ops.batch_run_log WHERE run_id = ?", [result.run_id]
        ).fetchone()
        if existing_row:
            conn.execute(
                "UPDATE demo_ops.batch_run_log SET status = 'completed', completed_at = CURRENT_TIMESTAMP, duration_ms = ?, source_ingestion_run_id = ? WHERE run_id = ?",
                [result.duration_ms, ingestion_run_id, result.run_id],
            )
        else:
            conn.execute(
                """INSERT INTO demo_ops.batch_run_log (run_id, run_uuid, day_idx, status, completed_at, duration_ms, incident_count, source_ingestion_run_id)
                VALUES (?, ?, ?, 'completed', CURRENT_TIMESTAMP, ?, 0, ?)""",
                [result.run_id, run_uuid, day_idx, result.duration_ms, ingestion_run_id],
            )
        conn.commit()
        _notify(progress_callback, "Phase A Ingest", f"Day {day_idx} ingestion finished (+{row_cnt} rows).", {"day_idx": day_idx, "rows": row_cnt})

    except Exception as exc:
        logger.error(f"[BatchRunner] Exception during _ingest_day_only for day {day_idx}: {exc}", exc_info=True)
        result.status = "error"
        result.error_msg = str(exc)
        result.duration_ms = int((time.time() - start) * 1000)

    return result


def run_warmup_then_day(
    target_day: int,
    dataset_key: str = "vingroup_pilot",
    window_days: int = 10,
    dry_run: bool = False,
    progress_callback: Optional[Callable[[str, str, dict], None]] = None,
) -> list[BatchRunResult]:
    """Two-phase warmup: ingest days 0..target-1 (data accumulation only),
    then run a single full analysis pass on target_day with the complete
    timeseries window so L2-L4 detectors have sufficient historical context.
    """
    results: list[BatchRunResult] = []
    conn = get_db().get_connection()
    _ensure_demo_ops_tables(conn)

    warmup_start = max(0, target_day - window_days)
    _notify(progress_callback, "Warmup Sequence", f"Starting two-phase batch execution for target Day {target_day} (baseline days {warmup_start}..{target_day-1})...", {"target_day": target_day, "warmup_start": warmup_start})

    # ── Phase A: Ingest-only (accumulate timeseries context for missing baseline days) ──
    for day in range(warmup_start, target_day):
        results.append(_ingest_day_only(day, dataset_key, conn, progress_callback=progress_callback))

    # ── Phase B: Single full analysis on target day with complete window ──
    _notify(progress_callback, "Phase B Analysis", f"Warmup Phase B: Running full DataTrust analysis on target Day {target_day}...", {"target_day": target_day})
    results.append(run_day_batch(target_day, dataset_key, window_days, dry_run, run_kind="WARMUP_BASELINE", progress_callback=progress_callback))
    return results


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Day-aware batch runner for landing ingestion")
    parser.add_argument("--day", type=int, required=True, help="Target day_idx to run")
    parser.add_argument("--dataset", default="vingroup_pilot", help="Dataset key")
    parser.add_argument("--window", type=int, default=10, help="Lookback window days")
    parser.add_argument("--dry", action="store_true", help="Dry run (skip LLM calls)")
    parser.add_argument("--warmup", action="store_true", help="Run warmup before target day")
    args = parser.parse_args()

    if args.warmup:
        results = run_warmup_then_day(args.day, args.dataset, args.window, args.dry)
    else:
        results = [run_day_batch(args.day, args.dataset, args.window, args.dry)]

    for r in results:
        print(
            f"[{r.run_id}] day={r.day_idx} status={r.status} "
            f"incidents={r.incident_count} duration={r.duration_ms}ms"
        )
