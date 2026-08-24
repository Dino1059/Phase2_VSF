"""Day ingestor - Giai doan 2b
Ingest a specific day_idx from landing parquet into raw.<table>.
Idempotent: skips if data already exists for that day_idx with matching snapshot_id.
"""
import duckdb, os
from datetime import datetime

DB_PATH = r"c:\Users\ngant\P-086\data_new\db\vingroup_pilot.db"
PQ_PATH = r"c:\Users\ngant\P-086\data_new\vingroup_pilot_landing.parquet"

# Column mapping: landing dataset_table -> (raw_table, [columns in landing], snapshot_id injected)
# Derived from actual schema analysis.
TABLE_MAPPINGS = {
    "ev_telemetry": {
        "raw_table": "raw.ev_telemetry",
        "landing_cols": [
            "record_id", "vehicle_vin", "day_idx", "sample_idx", "timestamp",
            "speed_kmh", "motor_rpm", "battery_soc", "battery_voltage",
            "battery_current", "battery_temp_c", "state_at_sample",
            "assigned_day_index", "ved_reference_veh_id", "synthetic_gap_indicator",
            "event_sequence_index", "latitude", "longitude", "accel_z", "telemetry_coverage"
        ],
        "day_filter": "day_idx = :day",
    },
    "ride_trips": {
        "raw_table": "raw.trips",
        "landing_cols": [
            "trip_id", "vehicle_vin", "driver_id", "pickup_datetime", "dropoff_datetime",
            "assigned_day_index", "trip_distance_km", "fare_amount", "currency_unverified",
            "tip_amount", "total_fare", "pickup_latitude", "pickup_longitude",
            "vehicle_type", "event_sequence_index"
        ],
        "day_filter": "assigned_day_index = :day",
        "day_col_landing": "day_idx",  # landing has day_idx
        "day_col_raw": "assigned_day_index",  # raw uses assigned_day_index
    },
    "acn_charging": {
        "raw_table": "raw.charging_sessions",
        "landing_cols": [
            "vehicle_vin", "session_id", "station_id", "charger_id", "start_time",
            "duration_mins", "kwh_consumed", "power_kw", "charging_pattern",
            "assigned_day_index", "station_temp_c", "cost_vnd", "status",
            "soft_overlap_flag", "event_sequence_index"
        ],
        "day_filter": "assigned_day_index = :day",
        "day_col_landing": "day_idx",
        "day_col_raw": "assigned_day_index",
    },
    "fleet_index": {
        "raw_table": "raw.fleet_index",
        "landing_cols": [
            "vehicle_vin", "vehicle_type", "telemetry_equipped"
        ],
        "day_filter": None,  # static reference data - ingest once
        "once": True,       # only ingest once, not per-day
    },
    # nlp_feedback: landing.feedback only has sentiment+topic, raw.nlp_feedback needs sentence.
    # Skip for now - require manual mapping if needed.
}

SNAPSHOT_MAP = {
    0: "SNAP_000", 1: "SNAP_001", 2: "SNAP_002", 3: "SNAP_003", 4: "SNAP_004",
    5: "SNAP_005", 6: "SNAP_006", 7: "SNAP_007", 8: "SNAP_008", 9: "SNAP_009",
    10: "SNAP_010", 11: "SNAP_011", 12: "SNAP_012", 13: "SNAP_013", 14: "SNAP_014",
}


def get_snapshot_id(day_idx: int) -> str:
    return SNAPSHOT_MAP.get(int(day_idx), f"SNAP_{int(day_idx):03d}")


def ingest_day(day_idx: int, verbose: bool = True, force_replay: bool = False, conn: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Ingest all tables for a given day_idx from landing parquet."""
    snapshot_id = get_snapshot_id(day_idx)
    if verbose:
        print(f"\n{'='*60}")
        print(f"INGEST DAY {day_idx} (snapshot={snapshot_id})")
        print(f"{'='*60}")

    if not os.path.exists(PQ_PATH):
        return {"error": f"Parquet not found: {PQ_PATH}"}

    should_close = False
    if conn is None:
        try:
            from src.db.connection import get_db
            conn = get_db().get_connection()
        except Exception:
            conn = duckdb.connect(DB_PATH)
            should_close = True
    results = {}

    for dataset_table, mapping in TABLE_MAPPINGS.items():
        raw_table = mapping["raw_table"]
        landing_cols = mapping["landing_cols"]
        day_filter = mapping.get("day_filter")
        day_col_raw = mapping.get("day_col_raw", "day_idx")

        # Skip "once" tables (static reference data) in per-day ingest
        if mapping.get("once"):
            if verbose:
                print(f"\n  [{dataset_table}] -> {raw_table}")
                print(f"    SKIP - static reference (use --seed-fleet to ingest once)")
            results[dataset_table] = {"status": "skipped", "reason": "static_reference"}
            continue

        if verbose:
            print(f"\n  [{dataset_table}] -> {raw_table}")

        # Check idempotency: use SUM of snapshot_id matches (NULL-safe)
        if day_filter:
            day_cond = day_filter.replace(":day", str(day_idx))
            existing_snapshot = conn.execute(
                f"SELECT MAX(snapshot_id) FROM {raw_table} WHERE {day_cond}"
            ).fetchone()[0]
            snapshot_match_count = conn.execute(
                f"SELECT COUNT(*) FROM {raw_table} WHERE {day_cond} AND snapshot_id = ?",
                [snapshot_id]
            ).fetchone()[0]
            existing_count = conn.execute(
                f"SELECT COUNT(*) FROM {raw_table} WHERE {day_cond}"
            ).fetchone()[0]
        else:
            # fleet_index: check by snapshot_id
            existing_count, existing_snapshot = conn.execute(
                f"SELECT COUNT(*), MAX(snapshot_id) FROM {raw_table} WHERE snapshot_id = ?",
                [snapshot_id]
            ).fetchone()
            snapshot_match_count = existing_count

        if force_replay and day_filter:
            day_cond = day_filter.replace(":day", str(day_idx))
            conn.execute(f"DELETE FROM {raw_table} WHERE {day_cond}")
            if verbose:
                print(f"    FORCE REPLAY - deleted existing rows for {day_cond}")
        elif existing_count > 0 and snapshot_match_count > 0:
            # Already ingested with our snapshot_id
            if verbose:
                print(f"    SKIP - already ingested (snapshot={snapshot_id})")
            results[dataset_table] = {"status": "skipped", "rows": existing_count}
            continue
        elif existing_count > 0 and existing_snapshot is None:
            # Data exists but no snapshot_id - old seed data. Skip to be safe.
            if verbose:
                print(f"    SKIP - has {existing_count} rows but no snapshot_id (old seed)")
            results[dataset_table] = {"status": "skipped_old_seed", "rows": existing_count}
            continue

        # Build INSERT
        # Add snapshot_id to columns
        all_cols = landing_cols + ["snapshot_id"]
        col_list = ", ".join(all_cols)
        select_parts = []
        for col in landing_cols:
            select_parts.append(col)
        select_parts.append(f"'{snapshot_id}' AS snapshot_id")
        select_list = ", ".join(select_parts)

        # Build WHERE clause
        if day_filter:
            where_clause = f"WHERE dataset_table = '{dataset_table}' AND {day_filter.replace(':day', str(day_idx))}"
        else:
            where_clause = f"WHERE dataset_table = '{dataset_table}'"

        sql = f"""
            INSERT INTO {raw_table} ({col_list})
            SELECT {select_list}
            FROM read_parquet('{PQ_PATH}')
            {where_clause}
        """

        try:
            conn.execute(sql)
            # Verify - count rows with our snapshot_id
            if day_filter:
                day_cond = day_filter.replace(":day", str(day_idx))
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {raw_table} WHERE {day_cond} AND snapshot_id = ?",
                    [snapshot_id]
                ).fetchone()[0]
            else:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {raw_table} WHERE snapshot_id = ?",
                    [snapshot_id]
                ).fetchone()[0]
            if verbose:
                print(f"    OK   +{count} rows (snapshot={snapshot_id})")
            results[dataset_table] = {"status": "inserted", "rows": count, "snapshot_id": snapshot_id}
        except Exception as e:
            if verbose:
                print(f"    ERR  {e}")
            results[dataset_table] = {"status": "error", "error": str(e)}

    if should_close:
        try:
            conn.close()
        except Exception:
            pass
    return results


def verify_day(day_idx: int) -> dict:
    """Show what raw tables have for a given day_idx."""
    conn = duckdb.connect(DB_PATH, read_only=True)
    snapshot_id = get_snapshot_id(day_idx)
    stats = {}
    for dataset_table, mapping in TABLE_MAPPINGS.items():
        raw_table = mapping["raw_table"]
        day_filter = mapping.get("day_filter")
        if day_filter:
            cond = day_filter.replace(":day", str(day_idx))
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {raw_table} WHERE {cond}").fetchone()[0]
                snap = conn.execute(f"SELECT MAX(snapshot_id) FROM {raw_table} WHERE {cond}").fetchone()[0]
                stats[dataset_table] = f"{cnt} rows (snap={snap})"
            except Exception as e:
                stats[dataset_table] = f"ERR: {e}"
        else:
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {raw_table} WHERE snapshot_id = ?", [snapshot_id]).fetchone()[0]
                stats[dataset_table] = f"{cnt} rows (snap={snapshot_id})"
            except:
                stats[dataset_table] = "ERR"
    conn.close()
    return stats


def seed_fleet_index(snapshot_id: str = "SNAP_000", verbose: bool = True) -> dict:
    """Ingest fleet_index (static reference data) once."""
    if verbose:
        print(f"\n{'='*60}")
        print(f"SEED FLEET INDEX (snapshot={snapshot_id})")
        print(f"{'='*60}")

    if not os.path.exists(PQ_PATH):
        return {"error": f"Parquet not found: {PQ_PATH}"}

    conn = duckdb.connect(DB_PATH)
    mapping = TABLE_MAPPINGS["fleet_index"]
    raw_table = mapping["raw_table"]
    landing_cols = mapping["landing_cols"]

    # Check if already ingested
    existing = conn.execute(
        f"SELECT COUNT(*) FROM {raw_table} WHERE snapshot_id = ?",
        [snapshot_id]
    ).fetchone()[0]
    if existing > 0:
        if verbose:
            print(f"  SKIP - fleet_index already seeded (snapshot={snapshot_id})")
        conn.close()
        return {"status": "skipped", "rows": existing}

    # Insert
    all_cols = landing_cols + ["snapshot_id"]
    sql = f"""
        INSERT INTO {raw_table} ({', '.join(all_cols)})
        SELECT {', '.join(landing_cols)}, '{snapshot_id}' AS snapshot_id
        FROM read_parquet('{PQ_PATH}')
        WHERE dataset_table = 'fleet_index'
    """
    try:
        conn.execute(sql)
        count = conn.execute(
            f"SELECT COUNT(*) FROM {raw_table} WHERE snapshot_id = ?",
            [snapshot_id]
        ).fetchone()[0]
        if verbose:
            print(f"  OK   +{count} rows (snapshot={snapshot_id})")
        result = {"status": "inserted", "rows": count}
    except Exception as e:
        if verbose:
            print(f"  ERR  {e}")
        result = {"status": "error", "error": str(e)}

    conn.close()
    return result


def ingest_warmup(days: int = 10) -> list:
    """Ingest first N days (warmup phase)."""
    results = []
    for day in range(days):
        r = ingest_day(day, verbose=True)
        results.append((day, r))
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Day ingestor")
    parser.add_argument("--day", type=int, help="Ingest single day_idx")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Ingest day range")
    parser.add_argument("--warmup", type=int, default=10, help="Ingest first N days (warmup)")
    parser.add_argument("--verify", type=int, help="Verify raw tables for day_idx")
    parser.add_argument("--seed-fleet", action="store_true", help="Ingest fleet_index (static reference data) once")
    args = parser.parse_args()

    if args.seed_fleet:
        seed_fleet_index()
    elif args.verify is not None:
        print(f"Verifying day {args.verify}:")
        for tbl, info in verify_day(args.verify).items():
            print(f"  {tbl}: {info}")
    elif args.day is not None:
        ingest_day(args.day)
    elif args.range:
        start, end = args.range
        for day in range(start, end + 1):
            ingest_day(day)
    else:
        print(f"Ingesting warmup days 0-{args.warmup-1}...")
        results = ingest_warmup(args.warmup)
        print(f"\n{'='*60}")
        print("WARMUP SUMMARY")
        total = 0
        for day, r in results:
            for tbl, info in r.items():
                if info.get("status") == "inserted":
                    total += info["rows"]
                    print(f"  day {day:2d} {tbl}: +{info['rows']} rows")
        print(f"\nTotal rows inserted: {total:,}")
