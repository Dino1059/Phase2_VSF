#!/usr/bin/env python3
"""
Build the Source Database (data/source.db) for the DataTrust OS pipeline.

Step 1 — Chuan bi du lieu nguon:
Imports every CSV dataset currently checked into data/raw_public,
data/vingroup, and data/vingroup_real into one SQLite database,
one table per CSV file, with an explicit schema per data/README.md.

Usage:
  python scripts/build_source_db.py [--db data/source.db]
"""
import argparse
import sqlite3
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# (csv path relative to repo root, table name, CREATE TABLE column defs, primary key)
# Column types follow the field contracts documented in data/README.md.
# No CHECK/range constraints on the "dirty" tables: their out-of-range values
# are intentionally injected faults consumed by later pipeline stages.
TABLES = [
    (
        "data/raw_public/st_evcdp_raw.csv",
        "st_evcdp_raw",
        """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id TEXT NOT NULL,
        charger_id TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        max_power_kw REAL,
        charging_duration_mins REAL,
        kwh_consumed REAL,
        price_rate_cny REAL,
        status TEXT
        """,
    ),
    (
        "data/raw_public/uit_vsfc_raw.csv",
        "uit_vsfc_raw",
        """
        sentence_id TEXT PRIMARY KEY,
        sentence TEXT,
        sentiment_label INTEGER,
        topic_label INTEGER
        """,
    ),
    (
        "data/raw_public/vehicle_telemetry_raw.csv",
        "vehicle_telemetry_raw",
        """
        record_id TEXT PRIMARY KEY,
        speed_kmh REAL,
        motor_rpm INTEGER,
        soc_pct REAL,
        battery_voltage_v REAL,
        battery_current_a REAL,
        pack_temp_c REAL,
        accel_x REAL,
        accel_y REAL,
        accel_z REAL
        """,
    ),
    (
        "data/raw_public/ride_hailing_raw.csv",
        "ride_hailing_raw",
        """
        transaction_id TEXT PRIMARY KEY,
        driver_id TEXT,
        distance_km REAL,
        fare_vnd REAL,
        tip_vnd REAL,
        discount_vnd REAL,
        lat REAL,
        lon REAL,
        ride_type TEXT
        """,
    ),
    (
        "data/vingroup/vinfast_ev_telemetry_dirty.csv",
        "vinfast_ev_telemetry_dirty",
        """
        record_id TEXT PRIMARY KEY,
        vehicle_vin TEXT,
        timestamp TEXT,
        speed_kmh REAL,
        motor_rpm INTEGER,
        battery_soc REAL,
        battery_voltage REAL,
        battery_current REAL,
        battery_temp_c REAL,
        latitude REAL,
        longitude REAL,
        accel_z REAL
        """,
    ),
    (
        "data/vingroup/vgreen_charging_stations_dirty.csv",
        "vgreen_charging_stations_dirty",
        """
        session_id TEXT PRIMARY KEY,
        station_id TEXT,
        charger_id TEXT,
        vehicle_vin TEXT,
        start_time TEXT,
        duration_mins REAL,
        power_kw REAL,
        kwh_consumed REAL,
        station_temp_c REAL,
        cost_vnd REAL,
        status TEXT
        """,
    ),
    (
        "data/vingroup/xanh_sm_trips_dirty.csv",
        "xanh_sm_trips_dirty",
        """
        trip_id TEXT PRIMARY KEY,
        vehicle_vin TEXT,
        driver_id TEXT,
        pickup_datetime TEXT,
        trip_miles REAL,
        fare_amount REAL,
        tip_amount REAL,
        discount_amount REAL,
        total_fare REAL,
        pickup_latitude REAL,
        pickup_longitude REAL,
        vehicle_type TEXT
        """,
    ),
    (
        "data/vingroup/xanh_sm_customer_feedback_dirty.csv",
        "xanh_sm_customer_feedback_dirty",
        """
        feedback_id TEXT PRIMARY KEY,
        customer_id TEXT,
        timestamp TEXT,
        raw_comment_text TEXT,
        extracted_location TEXT,
        extracted_component TEXT,
        extracted_error_type TEXT,
        severity_level TEXT
        """,
    ),
    (
        "data/vingroup_real/real_vinfast_ev_telemetry.csv",
        "real_vinfast_ev_telemetry",
        """
        record_id TEXT PRIMARY KEY,
        speed_kmh REAL,
        motor_rpm INTEGER,
        battery_soc REAL,
        battery_voltage REAL,
        battery_current REAL,
        battery_temp_c REAL,
        accel_x REAL,
        accel_y REAL,
        accel_z REAL,
        vehicle_vin TEXT
        """,
    ),
    (
        "data/vingroup_real/real_vgreen_charging_stations.csv",
        "real_vgreen_charging_stations",
        """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id TEXT NOT NULL,
        charger_id TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        power_kw REAL,
        duration_mins REAL,
        kwh_consumed REAL,
        cost_rate_vnd REAL,
        status TEXT,
        vehicle_vin TEXT,
        cost_vnd REAL
        """,
    ),
    (
        "data/vingroup_real/real_xanh_sm_trips.csv",
        "real_xanh_sm_trips",
        """
        trip_id TEXT PRIMARY KEY,
        driver_id TEXT,
        trip_miles REAL,
        fare_amount REAL,
        tip_amount REAL,
        discount_amount REAL,
        pickup_latitude REAL,
        pickup_longitude REAL,
        ride_type TEXT,
        vehicle_vin TEXT,
        total_fare REAL
        """,
    ),
    (
        "data/vingroup_real/real_xanh_sm_customer_feedback.csv",
        "real_xanh_sm_customer_feedback",
        """
        feedback_id TEXT PRIMARY KEY,
        raw_comment_text TEXT,
        sentiment_label INTEGER,
        topic_label INTEGER,
        customer_id TEXT
        """,
    ),
]


def build(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        print(f"Building source database at {db_path}")
        for csv_rel, table, columns_sql in TABLES:
            csv_path = REPO_ROOT / csv_rel
            df = pd.read_csv(csv_path)

            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"CREATE TABLE {table} ({columns_sql.strip()})")
            df.to_sql(table, conn, if_exists="append", index=False)

            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<35} {count:>6} rows  <- {csv_rel}")
        conn.commit()
    finally:
        conn.close()
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default="data/source.db",
        help="Output SQLite database path relative to repo root (default: data/source.db)",
    )
    args = parser.parse_args()
    build(REPO_ROOT / args.db)


if __name__ == "__main__":
    main()
