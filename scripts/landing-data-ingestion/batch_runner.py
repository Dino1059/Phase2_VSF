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
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.db.connection import get_db
from src.orchestrator.orchestrator import DataTrustOrchestrator
from src.services.llm import GemmaLLMAdapter


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
) -> BatchRunResult:
    """
    Run analysis for a single day_idx with window-days lookback.

    Returns a BatchRunResult with incident_count, duration, and status.
    """
    run_uuid = str(uuid.uuid4())[:12]
    db_mgr = get_db()
    conn = db_mgr._get_master_conn()
    _ensure_demo_ops_tables(conn)

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

    if dry_run:
        result.status = "completed"
        conn.execute(
            "UPDATE demo_ops.batch_run_log SET status = 'completed', completed_at = CURRENT_TIMESTAMP, duration_ms = 0, incident_count = 0, source_ingestion_run_id = ? WHERE run_id = ?",
            [ingestion_run_id, result.run_id],
        )
        _update_state()
        conn.commit()
        return result

    # --- Real LLM-powered run ---
    start = time.time()
    try:
        llm = GemmaLLMAdapter(model="auto")
        orchestrator = DataTrustOrchestrator(llm, project_id=dataset_key)
        orch_result = orchestrator.run_analysis(
            dataset_key=dataset_key,
            table_name=None,
            target_day_idx=day_idx,
            window_days=window_days,
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

        # Update ingestion_runs with completion
        conn.execute(
            """
            UPDATE demo_ops.ingestion_runs
            SET status = 'COMPLETED', finished_at = CURRENT_TIMESTAMP,
                rows_passed_clean = ?
            WHERE ingestion_run_id = ?
            """,
            [incident_count, ingestion_run_id],
        )

        # Link pipeline_runs.source_ingestion_run_id for the latest run
        latest_pipeline = conn.execute(
            "SELECT id FROM main.pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest_pipeline:
            conn.execute(
                "UPDATE main.pipeline_runs SET source_ingestion_run_id = ? WHERE id = ?",
                [ingestion_run_id, latest_pipeline[0]],
            )

        conn.execute(
            "UPDATE demo_ops.batch_run_log SET status = 'completed', completed_at = CURRENT_TIMESTAMP, incident_count = ?, duration_ms = ?, source_ingestion_run_id = ? WHERE run_id = ?",
            [incident_count, result.duration_ms, ingestion_run_id, result.run_id],
        )
        _update_state()
        conn.commit()

    except Exception as exc:
        result.status = "error"
        result.error_msg = str(exc)
        result.duration_ms = int((time.time() - start) * 1000)
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


def run_warmup_then_day(
    target_day: int,
    dataset_key: str = "vingroup_pilot",
    window_days: int = 10,
    dry_run: bool = False,
) -> list[BatchRunResult]:
    """
    First run warmup (target_day - window_days ... target_day - 1),
    then run the target day.  For warmup days already completed it is idempotent.
    """
    results: list[BatchRunResult] = []
    conn = get_db()._get_master_conn()
    _ensure_demo_ops_tables(conn)

    # Determine warmup range
    warmup_start = max(0, target_day - window_days)
    warmup_days = list(range(warmup_start, target_day))

    for day in warmup_days:
        results.append(run_day_batch(day, dataset_key, window_days, dry_run, run_kind="WARMUP"))

    # Final target day
    results.append(run_day_batch(target_day, dataset_key, window_days, dry_run, run_kind="DAILY_PLUS1"))
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
