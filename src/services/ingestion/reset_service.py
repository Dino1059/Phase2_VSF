"""
reset_service.py — Giai đoạn 7: Reset & State machine.
Lưu tại: src/services/ingestion/reset_service.py

Responsibilities:
1. Clean quarantine, clean, main canonical data, batch_run_log
2. Reset demo_state to IDLE (day_idx = -1, warmup_completed = FALSE)
3. Stop realtime runner
4. Mark all snapshots as inactive
5. State machine: IDLE -> WARMUP -> DAILY transitions
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.db.connection import get_db

logger = logging.getLogger(__name__)


class DemoPhase(Enum):
    """Demo state machine phases."""
    IDLE = "idle"           # Fresh reset, no day activated
    WARMUP = "warmup"       # Currently running warmup (days 0-9)
    DAILY = "daily"         # Running daily activations (day 10+)


@dataclass
class ResetResult:
    """Result of reset operation."""
    status: str
    message: str
    phase: DemoPhase = DemoPhase.IDLE
    error: Optional[str] = None


def get_current_phase(db=None) -> DemoPhase:
    """Determine current phase from demo_state."""
    if db is None:
        db = get_db()
    
    rows = db.execute(
        "SELECT current_day_idx, warmup_completed FROM demo_ops.demo_state LIMIT 1"
    )
    if not rows:
        return DemoPhase.IDLE
    
    day_idx, warmup_completed = rows[0]
    if day_idx < 0 or warmup_completed is None:
        return DemoPhase.IDLE
    if not warmup_completed:
        return DemoPhase.WARMUP
    return DemoPhase.DAILY


def get_transition_target(current_phase: DemoPhase, target_day_idx: int, warmup_completed: bool = False) -> DemoPhase:
    """
    Determine next phase based on current state and target day.
    
    Rules:
    - IDLE + day <= 9 -> WARMUP
    - IDLE + day >= 10 + warmup_completed=True -> DAILY
    - WARMUP + warmup_completed -> DAILY
    - DAILY -> DAILY (stay in daily for subsequent activations)
    """
    if current_phase == DemoPhase.DAILY:
        return DemoPhase.DAILY
    
    if target_day_idx >= 10 or warmup_completed:
        return DemoPhase.DAILY
    
    return DemoPhase.WARMUP


def reset_demo() -> ResetResult:
    """
    Reset demo state: clear quarantine, clean, batch_run_log.
    Main canonical tables are rebuilt from landing parquet after reset.
    Reset demo_state to IDLE (day_idx = -1).
    Mark all snapshots as inactive.
    Stop realtime runner.
    """
    try:
        db = get_db()
        
        # Stop realtime first
        try:
            from src.services.ingestion.realtime_runner import stop_realtime
            stop_realtime()
            logger.info("Realtime runner stopped")
        except Exception as e:
            logger.warning(f"Could not stop realtime runner: {e}")
        
        # Drop index on quarantine to prevent DuckDB index deletion corruption
        try:
            db.execute("DROP INDEX IF EXISTS idx_quarantine_idempotency")
        except Exception:
            pass

        # Clear quarantine tables (all schemas)
        _clear_schema_tables(db, "quarantine")
        
        # Clear clean tables
        _clear_schema_tables(db, "clean")

        # Clear canonical main data tables to ensure single-path Parquet ingestion.
        for tbl in ["ev_telemetry", "charging_sessions", "trips", "nlp_feedback"]:
            try:
                db.execute(f"TRUNCATE TABLE main.{tbl}")
            except Exception:
                try:
                    db.execute(f"DELETE FROM main.{tbl}")
                except Exception:
                    pass

        # Clear demo_ops batch_run_log
        try:
            db.execute("TRUNCATE TABLE demo_ops.batch_run_log")
        except Exception:
            db.execute("DELETE FROM demo_ops.batch_run_log")
        
        # Clear ingestion_runs
        try:
            db.execute("TRUNCATE TABLE demo_ops.ingestion_runs")
        except Exception:
            db.execute("DELETE FROM demo_ops.ingestion_runs")
        
        # Reset demo_state to IDLE
        db.execute("""
            UPDATE demo_ops.demo_state 
            SET current_day_idx = -1, 
                warmup_completed = FALSE, 
                realtime_active_day = -1, 
                realtime_running = FALSE,
                last_reset_at = CURRENT_TIMESTAMP
        """)
        
        # Mark all snapshots as not activated and zero ingested rows
        db.execute("""
            UPDATE demo_ops.landing_day_snapshots 
            SET is_activated = FALSE, activated_at = NULL
        """)
        
        logger.info("Demo reset complete: quarantine, clean, main data, and batch_run_log cleared.")
        
        return ResetResult(
            status="success",
            message="Demo state reset complete. Canonical main tables reset to 0 rows pending day activation from Parquet.",
            phase=DemoPhase.IDLE,
        )
        
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        return ResetResult(
            status="error",
            message=f"Reset failed: {str(e)}",
            error=str(e),
        )


def _clear_schema_tables(db, schema: str) -> int:
    """Clear all tables in a schema. Returns count of cleared tables. Skips views."""
    try:
        rows = db.execute(
            f"SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = '{schema}'"
        )
        cleared = 0
        for row in rows:
            tbl = row[0]
            table_type = row[1] if len(row) > 1 else "BASE TABLE"
            # Skip views
            if table_type != "BASE TABLE":
                logger.debug(f"Skipping view {schema}.{tbl}")
                continue
            try:
                db.execute(f"TRUNCATE TABLE {schema}.{tbl}")
                cleared += 1
                logger.debug(f"Cleared {schema}.{tbl}")
            except Exception as e:
                try:
                    db.execute(f"DELETE FROM {schema}.{tbl}")
                    cleared += 1
                    logger.debug(f"Cleared {schema}.{tbl} via DELETE")
                except Exception as ex:
                    logger.warning(f"Could not clear {schema}.{tbl}: {ex}")
        return cleared
    except Exception as e:
        logger.warning(f"Could not list tables in {schema}: {e}")
        return 0


def verify_reset_complete() -> dict:
    """Verify reset completed correctly."""
    db = get_db()
    
    # Check demo_state
    state = db.execute(
        "SELECT current_day_idx, warmup_completed FROM demo_ops.demo_state LIMIT 1"
    )[0]
    
    # Check quarantine should be empty
    quarantine_count = db.execute(
        "SELECT COUNT(*) FROM quarantine.ev_telemetry"
    )[0][0] if db.execute("SELECT COUNT(*) FROM quarantine.ev_telemetry") else 0
    
    main_count = db.execute(
        "SELECT COUNT(*) FROM main.ev_telemetry"
    )[0][0] if db.execute("SELECT COUNT(*) FROM main.ev_telemetry") else 0
    
    return {
        "demo_state_day_idx": int(state[0]) if state[0] else -1,
        "warmup_completed": bool(state[1]) if state[1] else False,
        "quarantine_rows": quarantine_count,
        "main_rows": main_count,
        "reset_verified": state[0] == -1 and quarantine_count == 0,
    }
