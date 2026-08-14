#!/usr/bin/env python3
"""
Ingest VinGroup Pilot Dataset (Faulty or Clean) into DuckDB.
`scripts/ingest_vingroup_pilot_to_duckdb.py`

Features:
1. Full-fidelity 1:1 schema mapping: Preserves all 20 telemetry columns, 15 charging columns,
   15 trip columns, fleet index, and scenario-driven feedback.
2. Ingests ground truth metadata: Loads `fault_manifest.json` and `provenance_manifest.json`.
3. Populates system metadata: `raw_snapshots` and `datasets` registry.
4. Backwards compatibility: Populates legacy tables/views (`vinfast_bms`, `vgreen_telemetry`, `xanhsm_trips`, `xanhsm_feedback`).
5. Configurable target DB: Default is isolated `data/vingroup_pilot_faulty.duckdb`, or custom `--db`.
6. EDA 2026-08-14: Trip distance uses `trip_distance_km` (Tier RD, scaled from miles at ingestion).

Usage:
  python scripts/ingest_vingroup_pilot_to_duckdb.py [--db data/vingroup_pilot_faulty.duckdb] [--source-dir data_new/vingroup_pilot_dataset]
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB = PROJECT_ROOT / "data" / "vingroup_pilot_faulty.duckdb"
DEFAULT_SOURCE = PROJECT_ROOT / "data_new" / "vingroup_pilot_dataset"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_csv_optional(con: duckdb.DuckDBPyConnection, name: str, path: Path, table: str) -> bool:
    """Load a CSV into DuckDB. Returns True if file exists and loaded."""
    if not path.exists():
        print(f"  [SKIP] {name}: {path} not found")
        return False
    df = pd.read_csv(path, low_memory=False)
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM df")
    print(f"  [OK]   {name}: {len(df)} rows -> {table}")
    return True


# ─── Schema ──────────────────────────────────────────────────────────────────

def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS xanhsm")

    # ── raw snapshot registry ─────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.raw_snapshots (
            snapshot_id       VARCHAR PRIMARY KEY,
            dataset_name     VARCHAR NOT NULL,
            file_hash        VARCHAR NOT NULL,
            ingested_at      TIMESTAMP DEFAULT now(),
            row_count        BIGINT,
            source_path      VARCHAR,
            metadata         JSON
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.datasets (
            dataset_id       VARCHAR PRIMARY KEY,
            dataset_name     VARCHAR NOT NULL,
            version          VARCHAR,
            ingested_at      TIMESTAMP DEFAULT now(),
            record_count     BIGINT,
            fault_injected   BOOLEAN DEFAULT FALSE,
            metadata         JSON
        )
    """)

    # ── telemetry (20 cols) ────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.ev_telemetry (
            telemetry_id     VARCHAR PRIMARY KEY,
            vehicle_vin      VARCHAR,
            timestamp        TIMESTAMP NOT NULL,
            state_at_sample  VARCHAR,
            soc_pct          DOUBLE,
            voltage          DOUBLE,
            current_ma       BIGINT,
            temp_c           DOUBLE,
            speed_kmh        DOUBLE,
            odometer_km      DOUBLE,
            accel_z          DOUBLE,
            rpm              DOUBLE,
            range_km_est     DOUBLE,
            charging_rate_kw DOUBLE,
            regen_kw         DOUBLE,
            driver_id        VARCHAR,
            session_id       VARCHAR,
            fault_code       VARCHAR,
            latitude         DOUBLE,
            longitude        DOUBLE,
            snapshot_id      VARCHAR,
            FOREIGN KEY (snapshot_id) REFERENCES raw.raw_snapshots(snapshot_id)
        )
    """)

    # ── charging (15 cols) ─────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.charging_sessions (
            session_id       VARCHAR PRIMARY KEY,
            vehicle_vin      VARCHAR,
            start_time       TIMESTAMP NOT NULL,
            end_time         TIMESTAMP,
            energy_kwh       DOUBLE,
            power_kw         DOUBLE,
            start_soc_pct    DOUBLE,
            end_soc_pct      DOUBLE,
            station_id       VARCHAR,
            latitude         DOUBLE,
            longitude        DOUBLE,
            duration_min     BIGINT,
            charge_cost_usd  DOUBLE,
            fast_charge      BOOLEAN,
            driver_id        VARCHAR,
            snapshot_id      VARCHAR,
            FOREIGN KEY (snapshot_id) REFERENCES raw.raw_snapshots(snapshot_id)
        )
    """)

    # ── trips (15 cols) ────────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.trips (
            trip_id               VARCHAR PRIMARY KEY,
            vehicle_vin           VARCHAR,
            driver_id             VARCHAR,
            pickup_datetime       TIMESTAMP NOT NULL,
            dropoff_datetime     TIMESTAMP,
            assigned_day_index    INT,
            trip_distance_km      DOUBLE,      -- EDA 2026-08-14: Tier RD, scaled from fact_rides miles
            fare_amount          DOUBLE,
            currency_unverified   BOOLEAN,
            tip_amount           DOUBLE,
            total_fare           DOUBLE,
            pickup_latitude      DOUBLE,
            pickup_longitude     DOUBLE,
            vehicle_type         VARCHAR,
            event_sequence_index INT,
            snapshot_id           VARCHAR,
            FOREIGN KEY (snapshot_id) REFERENCES raw.raw_snapshots(snapshot_id)
        )
    """)

    # ── fleet index ────────────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.fleet_index (
            vehicle_vin   VARCHAR PRIMARY KEY,
            vehicle_type  VARCHAR,
            car_make      VARCHAR,
            car_model     VARCHAR,
            license_plate VARCHAR,
            fleet_id      VARCHAR,
            driver_id     VARCHAR,
            snapshot_id   VARCHAR,
            FOREIGN KEY (snapshot_id) REFERENCES raw.raw_snapshots(snapshot_id)
        )
    """)

    # ── NLP feedback ───────────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.nlp_feedback (
            feedback_id     VARCHAR PRIMARY KEY,
            vehicle_vin     VARCHAR,
            review_text     VARCHAR,
            rating          INT,
            source          VARCHAR,
            submitted_at    TIMESTAMP,
            sentiment_score DOUBLE,
            topic           VARCHAR,
            driver_id       VARCHAR,
            snapshot_id     VARCHAR,
            FOREIGN KEY (snapshot_id) REFERENCES raw.raw_snapshots(snapshot_id)
        )
    """)

    # ── fault manifest (ground truth for eval) ─────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.fault_manifest (
            fault_id      VARCHAR PRIMARY KEY,
            fault_type    VARCHAR NOT NULL,
            injected_at   TIMESTAMP,
            description   VARCHAR,
            affected_rows BIGINT,
            dataset_id    VARCHAR,
            metadata      JSON,
            snapshot_id   VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.provenance_manifest (
            artifact_id    VARCHAR PRIMARY KEY,
            artifact_type  VARCHAR,
            source_file    VARCHAR,
            source_hash    VARCHAR,
            ingested_at    TIMESTAMP DEFAULT now(),
            lineage        JSON,
            snapshot_id    VARCHAR
        )
    """)

    # ── backwards-compat views ─────────────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE VIEW vinfast_bms AS
        SELECT vehicle_vin, timestamp, soc_pct, voltage, temp_c, charging_rate_kw, fault_code
        FROM raw.ev_telemetry
        ORDER BY vehicle_vin, timestamp
    """)

    con.execute("""
        CREATE OR REPLACE VIEW vgreen_telemetry AS
        SELECT e.vehicle_vin, e.timestamp, e.state_at_sample, e.soc_pct, e.speed_kmh,
               e.odometer_km, e.accel_z, e.rpm, e.range_km_est, e.driver_id,
               f.vehicle_type, f.car_make, f.car_model, f.fleet_id
        FROM raw.ev_telemetry e
        LEFT JOIN raw.fleet_index f ON e.vehicle_vin = f.vehicle_vin
        ORDER BY e.vehicle_vin, e.timestamp
    """)

    con.execute("""
        CREATE OR REPLACE VIEW xanhsm_trips AS
        SELECT
            row_number() OVER () AS id,
            t.trip_id,
            t.vehicle_vin,
            t.driver_id,
            CAST(t.pickup_latitude AS VARCHAR) || ',' || CAST(t.pickup_longitude AS VARCHAR) AS pickup_location,
            NULL AS dropoff_location,
            t.trip_distance_km AS distance_km,
            t.total_fare AS fare_vnd,
            datediff('minute', t.pickup_datetime, t.dropoff_datetime) AS duration_minutes,
            NULL AS rating,
            t.pickup_datetime AS timestamp,
            t.fare_amount,
            t.tip_amount,
            t.currency_unverified,
            t.assigned_day_index,
            t.vehicle_type,
            t.event_sequence_index
        FROM raw.trips t
        ORDER BY t.pickup_datetime
    """)

    con.execute("""
        CREATE OR REPLACE VIEW xanhsm_feedback AS
        SELECT feedback_id, vehicle_vin, review_text, rating, source,
               submitted_at, sentiment_score, topic, driver_id
        FROM raw.nlp_feedback
        ORDER BY submitted_at DESC
    """)

    print("[OK] Schema created")


# ─── Ingest ──────────────────────────────────────────────────────────────────

def ingest(source_dir: Path, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    create_tables(con)

    # ── raw snapshots ──────────────────────────────────────────────────────────
    snap_id = f"snap_{uuid.uuid4().hex[:12]}"

    # telemetry
    tel_path = source_dir / "synthetic_ev_telemetry_ved_ref.csv"
    if load_csv_optional(con, "EV Telemetry", tel_path, "raw.ev_telemetry"):
        con.execute(
            "UPDATE raw.ev_telemetry SET snapshot_id = ? WHERE snapshot_id IS NULL",
            [snap_id],
        )

    # charging
    chg_path = source_dir / "acn_charging_mapped.csv"
    if load_csv_optional(con, "Charging Sessions", chg_path, "raw.charging_sessions"):
        con.execute(
            "UPDATE raw.charging_sessions SET snapshot_id = ? WHERE snapshot_id IS NULL",
            [snap_id],
        )

    # trips
    trp_path = source_dir / "ride_hailing_xanh_sm_trips.csv"
    if load_csv_optional(con, "Trips", trp_path, "raw.trips"):
        con.execute(
            "UPDATE raw.trips SET snapshot_id = ? WHERE snapshot_id IS NULL",
            [snap_id],
        )

    # fleet
    fleet_path = source_dir / "fleet_index.csv"
    if load_csv_optional(con, "Fleet Index", fleet_path, "raw.fleet_index"):
        con.execute(
            "UPDATE raw.fleet_index SET snapshot_id = ? WHERE snapshot_id IS NULL",
            [snap_id],
        )

    # NLP feedback
    nlp_path = source_dir / "nlp_benchmark_uit_vsfc.csv"
    load_csv_optional(con, "NLP Feedback", nlp_path, "raw.nlp_feedback")

    # register snapshot
    tel_count = con.execute("SELECT count(*) FROM raw.ev_telemetry").fetchone()[0]
    con.execute("""
        INSERT INTO raw.raw_snapshots (snapshot_id, dataset_name, source_path, row_count)
        VALUES (?, ?, ?, ?)
    """, [snap_id, "vingroup_pilot", str(source_dir), tel_count])

    # ── manifests ─────────────────────────────────────────────────────────────
    fault_path = source_dir / "fault_manifest.json"
    prov_path = source_dir / "provenance_manifest.json"
    fault_injected = fault_path.exists()

    if fault_injected:
        with open(fault_path) as f:
            faults = json.load(f)
        for fault in faults:
            con.execute("""
                INSERT INTO raw.fault_manifest
                    (fault_id, fault_type, injected_at, description, affected_rows, dataset_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                fault.get("fault_id", uuid.uuid4().hex[:12]),
                fault.get("fault_type", "unknown"),
                fault.get("injected_at"),
                fault.get("description", ""),
                fault.get("affected_rows", 0),
                snap_id,
                json.dumps(fault),
            ])
        print(f"  [OK]   Fault manifest: {len(faults)} faults")

    if prov_path.exists():
        with open(prov_path) as f:
            prov = json.load(f)
        for art in prov:
            con.execute("""
                INSERT INTO raw.provenance_manifest
                    (artifact_id, artifact_type, source_file, source_hash, lineage, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                art.get("artifact_id", uuid.uuid4().hex[:12]),
                art.get("artifact_type", "unknown"),
                art.get("source_file", ""),
                art.get("source_hash", ""),
                json.dumps(art.get("lineage", {})),
                snap_id,
            ])
        print(f"  [OK]   Provenance manifest: {len(prov)} artifacts")

    # ── datasets registry ─────────────────────────────────────────────────────
    trip_count = con.execute("SELECT count(*) FROM raw.trips").fetchone()[0]
    chg_count = con.execute("SELECT count(*) FROM raw.charging_sessions").fetchone()[0]
    con.execute("""
        INSERT INTO raw.datasets (dataset_id, dataset_name, version, record_count, fault_injected, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        snap_id,
        "vingroup_pilot",
        "1.0",
        tel_count + trip_count + chg_count,
        fault_injected,
        json.dumps({"source_dir": str(source_dir)}),
    ])

    con.close()
    print(f"\n[OK] Ingest complete: {db_path}")
    print(f"     Snapshot ID: {snap_id}")
    print(f"     Telemetry: {tel_count} rows | Trips: {trip_count} | Charging: {chg_count}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest VinGroup pilot dataset into DuckDB")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"Target DuckDB file (default: {DEFAULT_DB})")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE,
                        help=f"Source dataset directory (default: {DEFAULT_SOURCE})")
    args = parser.parse_args()

    print(f"Target:   {args.db}")
    print(f"Source:   {args.source_dir}")
    ingest(args.source_dir, args.db)
