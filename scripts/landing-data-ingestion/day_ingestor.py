"""Day ingestor.

Ingest landing parquet rows into canonical main tables. `main.*` is treated as
append-only; replay of an existing snapshot is skipped instead of deleting truth.
"""

import logging
import os

import duckdb

logger = logging.getLogger(__name__)

try:
    from src.config import get_settings
    from src.db.connection import get_db

    _rel_pq = get_settings().landing_parquet_path
    PQ_PATH = _rel_pq if os.path.isabs(_rel_pq) else os.path.join(get_db().project_root, _rel_pq)
except Exception:
    PQ_PATH = r"c:\Users\ngant\P-086\data_demo\vingroup_pilot_landing_demo.parquet"


TABLE_MAPPINGS = {
    "ev_telemetry": {
        "target_table": "main.ev_telemetry",
        "landing_cols": [
            "record_id", "vehicle_vin", "day_idx", "sample_idx", "timestamp",
            "speed_kmh", "motor_rpm", "battery_soc", "battery_voltage",
            "battery_current", "battery_temp_c", "state_at_sample",
            "assigned_day_index", "ved_reference_veh_id", "synthetic_gap_indicator",
            "event_sequence_index", "latitude", "longitude", "accel_z", "telemetry_coverage",
        ],
        "day_filter": "day_idx = :day",
    },
    "ride_trips": {
        "target_table": "main.trips",
        "landing_cols": [
            "trip_id", "vehicle_vin", "driver_id", "pickup_datetime", "dropoff_datetime",
            "assigned_day_index", "trip_distance_km", "fare_amount", "currency_unverified",
            "tip_amount", "total_fare", "pickup_latitude", "pickup_longitude",
            "vehicle_type", "event_sequence_index",
        ],
        "day_filter": "assigned_day_index = :day",
    },
    "acn_charging": {
        "target_table": "main.charging_sessions",
        "landing_cols": [
            "vehicle_vin", "session_id", "station_id", "charger_id", "start_time",
            "duration_mins", "kwh_consumed", "power_kw", "charging_pattern",
            "assigned_day_index", "station_temp_c", "cost_vnd", "status",
            "soft_overlap_flag", "event_sequence_index",
        ],
        "day_filter": "assigned_day_index = :day",
    },
    "feedback": {
        "target_table": "main.nlp_feedback",
        "landing_cols": [
            "feedback_id", "vehicle_vin", "sentence", "sentiment", "topic",
            "scenario_date", "raw_comment_text",
        ],
        "day_filter": None,
        "once": True,
    },
    "fleet_index": {
        "target_table": "ref.fleet_index_ref",
        "landing_cols": ["vehicle_vin", "vehicle_type", "telemetry_equipped"],
        "day_filter": None,
        "once": True,
    },
}

SNAPSHOT_MAP = {i: f"SNAP_{i:03d}" for i in range(15)}


def get_snapshot_id(day_idx: int) -> str:
    return SNAPSHOT_MAP.get(int(day_idx), f"SNAP_{int(day_idx):03d}")


def _connection(conn: duckdb.DuckDBPyConnection | None = None):
    if conn is not None:
        return conn
    from src.db.connection import get_db

    return get_db().get_connection()


def _insert_from_landing(conn, mapping: dict, snapshot_id: str, where_clause: str) -> int:
    target_table = mapping["target_table"]
    landing_cols = mapping["landing_cols"]
    col_list = ", ".join(landing_cols + ["snapshot_id", "source_ingestion_run_id"])
    select_list = ", ".join(
        landing_cols + [f"'{snapshot_id}' AS snapshot_id", "'DAY_INGESTOR' AS source_ingestion_run_id"]
    )
    sql = f"""
        INSERT INTO {target_table} ({col_list})
        SELECT {select_list}
        FROM read_parquet('{PQ_PATH}')
        {where_clause}
    """
    conn.execute(sql)
    return conn.execute(f"SELECT COUNT(*) FROM {target_table} WHERE snapshot_id = ?", [snapshot_id]).fetchone()[0]


def ingest_day(
    day_idx: int,
    verbose: bool = True,
    force_replay: bool = False,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> dict:
    """Ingest all day-scoped tables for a given day_idx from landing parquet."""
    snapshot_id = get_snapshot_id(day_idx)
    if not os.path.exists(PQ_PATH):
        return {"error": f"Parquet not found: {PQ_PATH}"}

    conn = _connection(conn)
    results = {}

    for dataset_table, mapping in TABLE_MAPPINGS.items():
        if mapping.get("once"):
            results[dataset_table] = {"status": "skipped", "reason": "static_reference"}
            continue

        target_table = mapping["target_table"]
        day_filter = mapping["day_filter"].replace(":day", str(day_idx))
        existing_count = conn.execute(
            f"SELECT COUNT(*) FROM {target_table} WHERE {day_filter} AND snapshot_id = ?",
            [snapshot_id],
        ).fetchone()[0]
        if existing_count:
            results[dataset_table] = {"status": "skipped", "rows": existing_count, "snapshot_id": snapshot_id}
            continue
        if force_replay:
            logger.info("force_replay ignored for %s; main.* is append-only", target_table)

        try:
            where_clause = f"WHERE dataset_table = '{dataset_table}' AND {day_filter}"
            count = _insert_from_landing(conn, mapping, snapshot_id, where_clause)
            results[dataset_table] = {"status": "inserted", "rows": count, "snapshot_id": snapshot_id}
        except Exception as exc:
            logger.error("[DayIngestor] %s insert error: %s", dataset_table, exc, exc_info=True)
            results[dataset_table] = {"status": "error", "error": str(exc)}

    return results


def verify_day(day_idx: int) -> dict:
    """Show what canonical tables have for a given day_idx."""
    snapshot_id = get_snapshot_id(day_idx)
    conn = _connection()
    stats = {}
    for dataset_table, mapping in TABLE_MAPPINGS.items():
        target_table = mapping["target_table"]
        day_filter = mapping.get("day_filter")
        try:
            if day_filter:
                cond = day_filter.replace(":day", str(day_idx))
                cnt = conn.execute(f"SELECT COUNT(*) FROM {target_table} WHERE {cond}").fetchone()[0]
                snap = conn.execute(f"SELECT MAX(snapshot_id) FROM {target_table} WHERE {cond}").fetchone()[0]
                stats[dataset_table] = f"{cnt} rows (snap={snap})"
            else:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {target_table} WHERE snapshot_id = ?", [snapshot_id]).fetchone()[0]
                stats[dataset_table] = f"{cnt} rows (snap={snapshot_id})"
        except Exception as exc:
            stats[dataset_table] = f"ERR: {exc}"
    return stats


def seed_static_references(snapshot_id: str = "SNAP_000", verbose: bool = True) -> dict:
    """Ingest static reference tables once."""
    if not os.path.exists(PQ_PATH):
        return {"error": f"Parquet not found: {PQ_PATH}"}

    conn = _connection()
    results = {}
    for dataset_table in ("feedback", "fleet_index"):
        mapping = TABLE_MAPPINGS[dataset_table]
        target_table = mapping["target_table"]
        existing = conn.execute(f"SELECT COUNT(*) FROM {target_table}").fetchone()[0]
        if existing:
            results[dataset_table] = {"status": "skipped", "rows": existing}
            continue
        try:
            count = _insert_from_landing(
                conn,
                mapping,
                snapshot_id,
                f"WHERE dataset_table = '{dataset_table}'",
            )
            results[dataset_table] = {"status": "inserted", "rows": count}
        except Exception as exc:
            results[dataset_table] = {"status": "error", "error": str(exc)}
    return results


def seed_fleet_index(snapshot_id: str = "SNAP_000", verbose: bool = True) -> dict:
    """Backward-compatible CLI wrapper for static reference ingest."""
    return seed_static_references(snapshot_id=snapshot_id, verbose=verbose).get("fleet_index", {})


def ingest_warmup(days: int = 10) -> list:
    return [(day, ingest_day(day, verbose=True)) for day in range(days)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Day ingestor")
    parser.add_argument("--day", type=int, help="Ingest single day_idx")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Ingest day range")
    parser.add_argument("--warmup", type=int, default=10, help="Ingest first N days")
    parser.add_argument("--verify", type=int, help="Verify canonical tables for day_idx")
    parser.add_argument("--seed-fleet", action="store_true", help="Ingest static reference tables once")
    args = parser.parse_args()

    if args.seed_fleet:
        print(seed_static_references())
    elif args.verify is not None:
        print(f"Verifying day {args.verify}:")
        for tbl, info in verify_day(args.verify).items():
            print(f"  {tbl}: {info}")
    elif args.day is not None:
        print(ingest_day(args.day))
    elif args.range:
        start, end = args.range
        for day in range(start, end + 1):
            print(day, ingest_day(day))
    else:
        print(ingest_warmup(args.warmup))
