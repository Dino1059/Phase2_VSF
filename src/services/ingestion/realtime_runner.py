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
)
from src.services.ingestion.rule_registry_filter import get_rules_for_realtime, FilteredRules
from src.services.ws_manager import ws_manager

from src.config import get_settings

logger = logging.getLogger(__name__)

def get_landing_parquet_path() -> str:
    path = get_settings().landing_parquet_path
    if not os.path.isabs(path):
        from src.db.connection import get_db
        try:
            root = get_db().project_root
            path = os.path.join(root, path)
        except Exception:
            pass
    return path.replace("\\", "/")

# Batch size cap for realtime processing (50 rows per batch to run for ~2 minutes per day)
REALTIME_BATCH_SIZE = 50
# Scheduler interval (1.0 second per tick for live demo flow)
REALTIME_INTERVAL_SEC = 1.0


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
    total_day_rows: int = 0
    clean_total: int = 0
    quarantined_total: int = 0
    l1_total: int = 0
    l2_total: int = 0
    l3_total: int = 0
    l4_total: int = 0
    error_msg: str = ""
    tick_count: int = 0
    status: str = "idle"
    message: str = ""
    last_tick_at: Optional[datetime] = None


@dataclass
class RealtimeTickResult:
    """Result of a single realtime tick."""
    tick_id: str
    day_idx: int
    rows_processed: int
    quarantined_count: int
    duration_ms: int
    status: str  # "ok" | "idle" | "error"
    deferred_count: int = 0
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
            if day_idx is not None and self._state.current_day_idx != day_idx:
                self.set_day(day_idx)
            return ""

        runner_id = f"RR-{uuid.uuid4().hex[:8]}"
        self._state.is_running = True
        target_day = day_idx if day_idx is not None else self._get_next_active_day()
        self.reset_day_state(target_day)

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

    def reset_day_state(self, day_idx: int) -> None:
        """Reset all per-day counters for a fresh day stream."""
        self._state.current_day_idx = day_idx
        self._read_cursor = 0
        self._state.rows_processed_total = 0
        self._state.clean_total = 0
        self._state.quarantined_total = 0
        self._state.l1_total = 0
        self._state.l2_total = 0
        self._state.l3_total = 0
        self._state.l4_total = 0
        self._state.total_day_rows = self._get_total_day_rows(day_idx)

    def set_day(self, day_idx: int) -> None:
        """Switch to a specific day_idx."""
        if self._state.current_day_idx != day_idx:
            self.reset_day_state(day_idx)
            logger.info(f"RealtimeRunner switched to day_idx={day_idx}, total_rows={self._state.total_day_rows}")

    def _get_total_day_rows(self, day_idx: int) -> int:
        """Get total rows in landing parquet for day_idx."""
        pq_path = get_landing_parquet_path()
        if not os.path.exists(pq_path):
            return 0
        try:
            import duckdb
            con = duckdb.connect()
            try:
                res = con.execute(f"SELECT COUNT(*) FROM read_parquet('{pq_path}') WHERE day_idx = {day_idx}").fetchone()
                return int(res[0]) if res and res[0] is not None else 0
            finally:
                con.close()
        except Exception:
            return 0

    def _get_next_active_day(self) -> int:
        """Get the next day that should be processed (Day N + 1 where N is latest activated day)."""
        try:
            db = get_db()
            conn = db._get_master_conn()
            result = conn.execute("""
                SELECT day_idx FROM demo_ops.landing_day_snapshots
                WHERE is_activated = TRUE
                ORDER BY day_idx DESC LIMIT 1
            """).fetchone()
            if result and result[0] is not None:
                return int(result[0]) + 1
        except Exception:
            pass
        return 0

    def _has_landing_day(self, day_idx: int) -> bool:
        pq_path = get_landing_parquet_path()
        if not os.path.exists(pq_path):
            return False
        try:
            import duckdb
            con = duckdb.connect()
            try:
                res = con.execute(f"SELECT COUNT(*) FROM read_parquet('{pq_path}') WHERE day_idx = {day_idx}").fetchone()
                return bool(res and res[0] > 0)
            finally:
                con.close()
        except Exception:
            return False

    async def _run_loop(self, runner_id: str) -> None:
        """Main asyncio loop."""
        if self._state.total_day_rows == 0:
            self._state.total_day_rows = self._get_total_day_rows(self._state.current_day_idx)

        while self._state.is_running:
            tick_start = time.time()
            self._state.tick_count += 1
            tick_id = f"{runner_id}-tick-{self._state.tick_count}"

            try:
                result, samples = await self._tick(tick_id)

                self._state.rows_processed_total += result.rows_processed
                self._state.quarantined_total += result.quarantined_count
                self._state.clean_total += (result.rows_processed - result.quarantined_count)
                self._state.last_run_duration_ms = result.duration_ms
                self._state.last_run_at = datetime.now(timezone.utc)
                self._state.last_tick_at = datetime.now(timezone.utc)
                self._state.status = result.status
                self._state.error_msg = result.error

                # Broadcast after each tick
                await self._broadcast_status(result, samples)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._state.error_msg = str(exc)
                logger.error(f"RealtimeRunner tick error: {exc}", exc_info=True)

            elapsed = time.time() - tick_start
            sleep_time = max(0, self.interval_sec - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def _tick(self, tick_id: str) -> tuple[RealtimeTickResult, list[dict]]:
        """
        Single tick: fetch rules, process a batch, quarantine violations.
        """
        start = time.time()

        # 1. Fetch latest rules (with caching)
        self._current_rules = get_rules_for_realtime(self.dataset_key)
        supported_rules = [
            r for r in self._current_rules.all_rules
            if r.get("layer") in SUPPORTED_REALTIME_LAYERS
        ] if self._current_rules else []

        # 2. Read a batch from landing parquet
        df = self._read_landing_batch(self._state.current_day_idx)

        if df.empty:
            # Realtime stream for current day reached 100% completion. Hold position until batch execution for day completes.
            return RealtimeTickResult(
                tick_id=tick_id,
                day_idx=self._state.current_day_idx,
                rows_processed=0,
                quarantined_count=0,
                deferred_count=0,
                duration_ms=int((time.time() - start) * 1000),
                status="completed",
            ), []

        # 3. Apply rules (single-row stateless evaluation)
        sample_records = []
        if not supported_rules:
            rows_processed = len(df)
            quarantined_count = 0
        else:
            result = apply_rules_batch(supported_rules, df, snapshot_id=f"realtime:{tick_id}")
            rows_processed = result.rows_processed
            quarantined_count = result.quarantined_count

            if result.supported_violations:
                q_count = quarantine_violations(result.supported_violations, snapshot_id=f"realtime:{tick_id}")
                logger.info(f"Quarantined {q_count} rows on day {self._state.current_day_idx}")

        # Extract 2-3 sample records for live feed visualization
        try:
            for _, row in df.head(3).iterrows():
                vin = str(row.get('vehicle_vin', row.get('vin', f'VIN-EV-{_ % 9000 + 1000}')))
                temp = float(row.get('battery_temp_c', 32.5))
                soc = float(row.get('soc_pct', 78.0))
                sample_records.append({
                    "vin": vin,
                    "battery_temp": temp,
                    "soc": soc,
                    "status": "clean" if quarantined_count == 0 else "flagged"
                })
        except Exception:
            pass

        return RealtimeTickResult(
            tick_id=tick_id,
            day_idx=self._state.current_day_idx,
            rows_processed=rows_processed,
            quarantined_count=quarantined_count,
            duration_ms=max(1, int((time.time() - start) * 1000)),
            status="ok",
        ), sample_records

    def _read_landing_batch(self, day_idx: int) -> pd.DataFrame:
        """
        Read a batch of rows from the landing parquet for the current day.
        Uses cursor to track position for paginated reads.
        """
        pq_path = get_landing_parquet_path()
        if not os.path.exists(pq_path):
            return pd.DataFrame()

        try:
            import duckdb
            con = duckdb.connect()
            try:
                df = con.execute(f"""
                    SELECT *
                    FROM read_parquet('{pq_path}')
                    WHERE day_idx = {day_idx}
                    LIMIT {self.batch_size}
                    OFFSET {self._read_cursor}
                """).df()

                self._read_cursor += len(df)
                return df
            finally:
                con.close()
        except Exception as exc:
            logger.warning(f"Failed to read landing batch: {exc}")
            return pd.DataFrame()

    async def _broadcast_status(self, result: RealtimeTickResult, recent_samples: list[dict] = None) -> None:
        """Broadcast current status via WebSocket."""
        payload = {
            "runner_id": result.tick_id.rsplit("-", 2)[0] if "-" in result.tick_id else result.tick_id,
            "day_idx": result.day_idx,
            "tick_count": self._state.tick_count,
            "rows_processed": result.rows_processed,
            "read_cursor": self._read_cursor,
            "total_day_rows": self._state.total_day_rows,
            "clean_total": self._state.clean_total,
            "quarantined_total": self._state.quarantined_total,
            "l1_total": self._state.l1_total,
            "l2_total": self._state.l2_total,
            "l3_total": self._state.l3_total,
            "l4_total": self._state.l4_total,
            "last_duration_ms": result.duration_ms,
            "throughput_eps": int(result.rows_processed / (result.duration_ms / 1000.0)) if result.duration_ms > 0 else 0,
            "status": result.status,
            "error": result.error,
            "recent_samples": recent_samples or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Broadcast both legacy and standard event types for full compatibility
        await ws_manager.broadcast({
            "type": "realtime.status",
            "data": payload
        })
        await ws_manager.broadcast({
            "type": "datatrust:realtime-tick",
            "data": payload
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


def get_realtime_state() -> RealtimeState:
    """Get current state of the default realtime runner."""
    runner = get_default_runner()
    return runner.state


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

