"""vingroup_pilot: live ingest stays in landing.*; promote into main on Run All / day close."""
from __future__ import annotations

from typing import Optional

LANDING_TABLES = ("ev_telemetry", "charging_sessions", "trips", "nlp_feedback")


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
    """Copy every landing.* row into main.* (seed / full demo load)."""
    ensure_landing_tables(db)
    promoted: dict[str, int] = {}
    for table in LANDING_TABLES:
        n = 0
        try:
            src = db.execute(f"SELECT COUNT(*) FROM landing.{table}")
            available = int(src[0][0]) if src else 0
            if available > 0:
                db.execute(f"INSERT INTO main.{table} SELECT * FROM landing.{table}")
                n = available
        except Exception:
            n = 0
        promoted[table] = n
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
    """Copy landing.* rows for one day into main.*. No-op when landing is empty."""
    ensure_landing_tables(db)
    promoted: dict[str, int] = {}
    if day_idx is None:
        return {"day_idx": None, "promoted": promoted, "status": "skipped", "dataset": "vingroup_pilot"}
    try:
        idx = int(day_idx)
    except (TypeError, ValueError):
        return {"day_idx": day_idx, "promoted": promoted, "status": "skipped", "dataset": "vingroup_pilot"}
    for table in LANDING_TABLES:
        n = 0
        try:
            src = db.execute(
                f"SELECT COUNT(*) FROM landing.{table} WHERE assigned_day_index = ? OR day_idx = ?",
                [idx, idx],
            )
            available = int(src[0][0]) if src else 0
            if available > 0:
                try:
                    db.execute(
                        f"INSERT INTO main.{table} SELECT * FROM landing.{table} "
                        f"WHERE assigned_day_index = ? OR day_idx = ?",
                        [idx, idx],
                    )
                    n = available
                except Exception:
                    n = 0
        except Exception:
            n = 0
        promoted[table] = n
    return {"day_idx": idx, "promoted": promoted, "status": "ok", "dataset": "vingroup_pilot"}
