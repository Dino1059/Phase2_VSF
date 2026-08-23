"""
realtime_runner.py — Giai đoạn 4: Asyncio scheduler for real-time rule application.
Lưu tại: src/services/ingestion/realtime_runner.py

Responsibilities:
1. Asyncio scheduler running every 10 seconds
2. Fetch approved rules for current dataset_key
3. Apply SUPPORTED rules (L1, L3 spatial) inline
4. Defer LAZY rules (L2/L4) to batch processor
5. Auto-switch to day+1 after batch completion
6. Broadcast status via WebSocket
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from src.db.connection import get_db
from src.services.ingestion.rule_applier import (
    apply_rules_batch,
    quarantine_violations,
    SUPPORTED_REALTIME_LAYERS,
    LAZY_LAYERS,
)
from src.services.ingestion.rule_registry_filter import get_rules_for_realtime, FilteredRules
from src.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

# Landing parquet path
LANDING_PARQUET = "data_new/vingroup_pilot_landing.parquet"

# Batch size cap for realtime processing
REALTIME_BATCH_SIZE = 5000
# Scheduler interval
REALTIME_INTERVAL_SEC = 10.0


@dataclass
class RealtimeState:
    """Current state of the realtime runner."""
    is_running: bool = False
    dataset_key: str = "vingroup_pilot"
    current_day_idx: int = -1
    window_days: int = 10
    interval_sec: float = REALTIME_INTERVAL_SEC
    batch_size: int = REALTIME_BATCH_SIZE
    last_run_at: Optional[datetime] = None
    last_run_duration_ms: int = 0
    rows_processed_total: int = 0
    quarantined_total: int = 0
    deferred_total: int = 0
    error_msg: str = ""
    tick_count: int = 0


@dataclass
class RealtimeTickResult:
    """Result of a single realtime tick."""
    tick_id: str
    day_idx: int
    rows_processed: int
    quarantined_count: int
    deferred_count: int
    duration_ms: int
    status: str  # "ok" | "idle" | "error"
    error: str = ""


class RealtimeRunner:
    """
    Asyncio-based realtime rule runner.
    
    Workflow:
    1. On each tick (every 10s):
       - Fetch latest approved rules for current dataset_key
       - Read a batch of rows from the landing parquet (current day)
       - Apply SUPPORTED rules (L1, L3) inline
       - Quarantine any violations
       - Defer L2/L4 signals for batch processor
       - Broadcast status via WebSocket
    2. On day completion:
       - Mark day as completed in demo_ops
       - Auto-switch to day+1 if available
    """

    def __init__(
        self,
        dataset_key: str = "vingroup_pilot",
        interval_sec: float = REALTIME_INTERVAL_SEC,
        batch_size: int = REALTIME_BATCH_SIZE,
        window_days: int = 10,
    ):
        self.dataset_key = dataset_key
        self.interval_sec = interval_sec
        self.batch_size = batch_size
        self.window_days = window_days

        self._state = RealtimeState(
            dataset_key=dataset_key,
            interval_sec=interval_sec,
            batch_size=batch_size,
            window_days=window_days,
        )
        self._task: Optional[asyncio.Task] = None
        self._read_cursor: int = 0  # Track position in current day's data
        self._current_rules: Optional[FilteredRules] = None

    @property
    def state(self) -> RealtimeState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state.is_running

    def start(self, day_idx: Optional[int] = None) -> str:
        """Start the realtime runner. Returns the runner_id."""
        if self._state.is_running:
            logger.warning("RealtimeRunner already running")
            return ""

        runner_id = f"RR-{uuid.uuid4().hex[:8]}"
        self._state.is_running = True
        self._state.current_day_idx = day_idx if day_idx is not None else self._get_next_active_day()
        self._read_cursor = 0

        self._task = asyncio.create_task(self._run_loop(runner_id))
        logger.info(f"RealtimeRunner started: {runner_id}, day_idx={self._state.current_day_idx}")

        asyncio.create_task(self._broadcast_state(f"runner_started:{runner_id}"))
        return runner_id

    def stop(self) -> None:
        """Stop the realtime runner."""
        if not self._state.is_running:
            return

        self._state.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("RealtimeRunner stopped")

        asyncio.create_task(self._broadcast_state("runner_stopped"))

    def set_day(self, day_idx: int) -> None:
        """Switch to a specific day_idx."""
        if self._state.current_day_idx != day_idx:
            self._state.current_day_idx = day_idx
            self._read_cursor = 0  # Reset cursor on day switch
            logger.info(f"RealtimeRunner switched to day_idx={day_idx}")

    def _get_next_active_day(self) -> int:
        """Get the next day that should be processed."""
        try:
            db = get_db()
            conn = db._get_master_conn()
            # Find the latest activated day that hasn't been fully processed
            result = conn.execute("""
                SELECT day_idx FROM demo_ops.landing_day_snapshots
                WHERE is_activated = TRUE AND is_ingested = TRUE
                ORDER BY day_idx DESC LIMIT 1
            """).fetchone()
            if result:
                return int(result[0])
        except Exception:
            pass
        return 0

    async def _run_loop(self, runner_id: str) -> None:
        """Main asyncio loop."""
        while self._state.is_running:
            tick_start = time.time()
            self._state.tick_count += 1
            tick_id = f"{runner_id}-tick-{self._state.tick_count}"

            try:
                result = await self._tick(tick_id)

                self._state.rows_processed_total += result.rows_processed
                self._state.quarantined_total += result.quarantined_count
                self._state.deferred_total += result.deferred_count
                self._state.last_run_duration_ms = result.duration_ms
                self._state.last_run_at = datetime.now(timezone.utc)
                self._state.error_msg = ""

                # Broadcast after each tick
                await self._broadcast_status(result)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._state.error_msg = str(exc)
                logger.error(f"RealtimeRunner tick error: {exc}", exc_info=True)

            elapsed = time.time() - tick_start
            sleep_time = max(0, self.interval_sec - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def _tick(self, tick_id: str) -> RealtimeTickResult:
        """
        Single tick: fetch rules, process a batch, quarantine violations.
        """
        start = time.time()

        # 1. Fetch latest rules (with caching)
        self._current_rules = get_rules_for_realtime(self.dataset_key)
        supported_rules = [
            r for r in self._current_rules.all_rules
            if r.get("layer") in SUPPORTED_REALTIME_LAYERS
        ]

        if not supported_rules:
            return RealtimeTickResult(
                tick_id=tick_id,
                day_idx=self._state.current_day_idx,
                rows_processed=0,
                quarantined_count=0,
                deferred_count=0,
                duration_ms=int((time.time() - start) * 1000),
                status="idle",
            )

        # 2. Read a batch from landing parquet
        df = self._read_landing_batch(self._state.current_day_idx)

        if df.empty:
            return RealtimeTickResult(
                tick_id=tick_id,
                day_idx=self._state.current_day_idx,
                rows_processed=0,
                quarantined_count=0,
                deferred_count=0,
                duration_ms=int((time.time() - start) * 1000),
                status="idle",
            )

        # 3. Apply rules
        result = apply_rules_batch(supported_rules, df, snapshot_id=f"realtime:{tick_id}")

        # 4. Quarantine SUPPORTED violations
        if result.supported_violations:
            q_count = quarantine_violations(result.supported_violations, snapshot_id=f"realtime:{tick_id}")
            logger.info(f"Quarantined {q_count} rows on day {self._state.current_day_idx}")

        # 5. Log lazy signals for batch processor
        if result.lazy_signals:
            self._store_lazy_signals(result.lazy_signals, tick_id)

        return RealtimeTickResult(
            tick_id=tick_id,
            day_idx=self._state.current_day_idx,
            rows_processed=result.rows_processed,
            quarantined_count=result.quarantined_count,
            deferred_count=result.deferred_count,
            duration_ms=int((time.time() - start) * 1000),
            status="ok",
        )

    def _read_landing_batch(self, day_idx: int) -> pd.DataFrame:
        """
        Read a batch of rows from the landing parquet for the current day.
        Uses cursor to track position for paginated reads.
        """
        if not os.path.exists(LANDING_PARQUET):
            return pd.DataFrame()

        try:
            import duckdb
            con = duckdb.connect(read_only=True)
            try:
                # Read a slice from current cursor position
                df = con.execute(f"""
                    SELECT *
                    FROM read_parquet('{LANDING_PARQUET}')
                    WHERE day_idx = {day_idx}
                    LIMIT {self.batch_size}
                    OFFSET {self._read_cursor}
                """).df()

                # Advance cursor
                self._read_cursor += len(df)

                # Reset cursor when we've read all rows for this day
                # (This means we've looped back or day switched)
                if len(df) < self.batch_size:
                    pass  # Keep cursor at end

                return df
            finally:
                con.close()
        except Exception as exc:
            logger.warning(f"Failed to read landing batch: {exc}")
            return pd.DataFrame()

    def _store_lazy_signals(self, lazy_signals: list[dict], tick_id: str) -> None:
        """
        Store L2/L4 signals for batch processor to handle later.
        Writes to demo_ops.realtime_lazy_signals table.
        """
        if not lazy_signals:
            return

        try:
            db = get_db()
            conn = db._get_master_conn()

            # Ensure table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS demo_ops.realtime_lazy_signals (
                    signal_id    VARCHAR PRIMARY KEY,
                    tick_id      VARCHAR,
                    day_idx      BIGINT,
                    rule_id      VARCHAR,
                    rule_version_id VARCHAR,
                    source_table VARCHAR,
                    source_row_id VARCHAR,
                    reason       VARCHAR,
                    severity     VARCHAR,
                    layer        VARCHAR,
                    lineage_hash VARCHAR,
                    original_data VARCHAR,
                    event_time   TIMESTAMP,
                    processed    BOOLEAN DEFAULT FALSE,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for sig in lazy_signals:
                sig_id = f"LS-{uuid.uuid4().hex[:8]}"
                try:
                    conn.execute("""
                        INSERT INTO demo_ops.realtime_lazy_signals
                        (signal_id, tick_id, day_idx, rule_id, rule_version_id, source_table,
                         source_row_id, reason, severity, layer, lineage_hash, original_data, event_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        sig_id,
                        tick_id,
                        self._state.current_day_idx,
                        sig["rule_id"],
                        sig.get("rule_version_id", sig["rule_id"]),
                        sig["source_table"],
                        sig["source_row_id"],
                        sig["reason"],
                        sig["severity"],
                        sig["layer"],
                        sig["lineage_hash"],
                        json.dumps(sig.get("original_data", {}), default=str),
                        datetime.now(timezone.utc),
                    ])
                except Exception as exc:
                    logger.debug(f"Failed to store lazy signal: {exc}")

            conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to store lazy signals table: {exc}")

    async def _broadcast_status(self, result: RealtimeTickResult) -> None:
        """Broadcast current status via WebSocket."""
        await ws_manager.broadcast({
            "type": "realtime.status",
            "data": {
                "runner_id": result.tick_id.rsplit("-", 2)[0] if "-" in result.tick_id else result.tick_id,
                "day_idx": result.day_idx,
                "tick_count": self._state.tick_count,
                "rows_processed": result.rows_processed,
                "quarantined_total": self._state.quarantined_total,
                "deferred_total": self._state.deferred_total,
                "last_duration_ms": result.duration_ms,
                "status": result.status,
                "error": result.error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    async def _broadcast_state(self, event: str) -> None:
        """Broadcast state change events."""
        await ws_manager.broadcast({
            "type": "realtime.event",
            "data": {
                "event": event,
                "day_idx": self._state.current_day_idx,
                "is_running": self._state.is_running,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })


# Singleton instance for the demo
_default_runner: Optional[RealtimeRunner] = None


def get_default_runner() -> RealtimeRunner:
    """Get or create the default realtime runner instance."""
    global _default_runner
    if _default_runner is None:
        _default_runner = RealtimeRunner()
    return _default_runner


def start_realtime(dataset_key: str = "vingroup_pilot", day_idx: Optional[int] = None) -> str:
    """Convenience function to start the default realtime runner."""
    runner = get_default_runner()
    runner.dataset_key = dataset_key
    return runner.start(day_idx)


def stop_realtime() -> None:
    """Convenience function to stop the default realtime runner."""
    runner = get_default_runner()
    runner.stop()


def switch_day(day_idx: int) -> None:
    """Convenience function to switch the default runner to a specific day."""
    runner = get_default_runner()
    runner.set_day(day_idx)
