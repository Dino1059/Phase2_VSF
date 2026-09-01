"""vingroup_pilot: live ingest stays in landing.*; promote into main on Run All / day close."""
from __future__ import annotations

from typing import Optional

LANDING_TABLES = ("ev_telemetry", "charging_sessions", "trips", "nlp_feedback")
TABLE_KEYS = {
    "ev_telemetry": "record_id",
    "charging_sessions": "session_id",
    "trips": "trip_id",
    "nlp_feedback": "feedback_id",
}


def _promote_table(db, table: str, day_idx: Optional[int]) -> int:
    """Insert landing rows not already in main (by natural key); clear staging."""
    key = TABLE_KEYS[table]
    try:
        if day_idx is None:
            pending = db.execute(
                f"SELECT COUNT(*) FROM landing.{table} l "
                f"WHERE NOT EXISTS (SELECT 1 FROM main.{table} m WHERE m.{key} = l.{key})"
            )
            n = int(pending[0][0]) if pending else 0
            if n > 0:
                db.execute(
                    f"INSERT INTO main.{table} SELECT l.* FROM landing.{table} l "
                    f"WHERE NOT EXISTS (SELECT 1 FROM main.{table} m WHERE m.{key} = l.{key})"
                )
            db.execute(f"DELETE FROM landing.{table}")
            return n
        params = [day_idx, day_idx]
        day_clause = "(l.assigned_day_index = ? OR l.day_idx = ?)"
        pending = db.execute(
            f"SELECT COUNT(*) FROM landing.{table} l WHERE {day_clause} "
            f"AND NOT EXISTS (SELECT 1 FROM main.{table} m WHERE m.{key} = l.{key})",
            params,
        )
        n = int(pending[0][0]) if pending else 0
        if n > 0:
            db.execute(
                f"INSERT INTO main.{table} SELECT l.* FROM landing.{table} l WHERE {day_clause} "
                f"AND NOT EXISTS (SELECT 1 FROM main.{table} m WHERE m.{key} = l.{key})",
                params,
            )
        db.execute(
            f"DELETE FROM landing.{table} WHERE assigned_day_index = ? OR day_idx = ?",
            params,
        )
        return n
    except Exception:
        return 0


def ensure_landing_schema(db) -> None:
    try:
        db.execute("CREATE SCHEMA IF NOT EXISTS landing")
    except Exception:
        pass


def ensure_landing_tables(db) -> None:
    """Empty landing.* clones of main.* so live ingest never dual-writes warehouse."""
    ensure_landing_schema(db)
    for table in LANDING_TABLES:
        try:
            db.execute(
                f"CREATE TABLE IF NOT EXISTS landing.{table} AS SELECT * FROM main.{table} WHERE 1=0"
            )
        except Exception:
            try:
                db.execute(
                    f"CREATE TABLE IF NOT EXISTS landing.{table} AS SELECT * FROM {table} WHERE 1=0"
                )
            except Exception:
                pass


def reset_landing_tables(db) -> None:
    """Drop and recreate empty landing.* (seed / canonical reset)."""
    ensure_landing_schema(db)
    for table in LANDING_TABLES:
        try:
            db.execute(f"DROP TABLE IF EXISTS landing.{table}")
        except Exception:
            pass
    ensure_landing_tables(db)


def promote_landing_all(db) -> dict:
    """Copy every landing.* row into main.* (seed / full demo load). Idempotent by natural key."""
    ensure_landing_tables(db)
    promoted: dict[str, int] = {}
    for table in LANDING_TABLES:
        promoted[table] = _promote_table(db, table, None)
    return {"day_idx": None, "promoted": promoted, "status": "ok", "dataset": "vingroup_pilot"}


def live_day_idx(db) -> int:
    try:
        rows = db.execute("SELECT current_day_idx FROM demo_ops.demo_state LIMIT 1")
        if rows and rows[0][0] is not None:
            return int(rows[0][0])
    except Exception:
        pass
    return 10


def promote_landing_day(db, day_idx: Optional[int]) -> dict:
    """Copy landing.* rows for one day into main.*. Idempotent; clears landing staging."""
    ensure_landing_tables(db)
    promoted: dict[str, int] = {}
    if day_idx is None:
        return {"day_idx": None, "promoted": promoted, "status": "skipped", "dataset": "vingroup_pilot"}
    try:
        idx = int(day_idx)
    except (TypeError, ValueError):
        return {"day_idx": day_idx, "promoted": promoted, "status": "skipped", "dataset": "vingroup_pilot"}
    for table in LANDING_TABLES:
        promoted[table] = _promote_table(db, table, idx)
    return {"day_idx": idx, "promoted": promoted, "status": "ok", "dataset": "vingroup_pilot"}
