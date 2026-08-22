#!/usr/bin/env python3
"""
Ingest VinGroup Pilot Dataset (Faulty or Clean) into DuckDB.
`scripts/ingest_vingroup_pilot_to_duckdb.py`

Features:
1. Full-fidelity 1:1 schema mapping: Preserves all columns from CSV source files.
2. Ingests ground truth metadata: Loads `fault_manifest.json` and `provenance_manifest.json`.
3. Populates system metadata: `raw_snapshots` and `datasets` registry.
4. Backwards compatibility: Populates legacy tables/views.
5. Configurable target DB: Default is `data_new/db/vingroup_pilot.db`.

Usage:
  python scripts/ingest_vingroup_pilot_to_duckdb.py [--db data_new/db/vingroup_pilot.db] [--source-dir data_new/vingroup_faulty_pilot_dataset]
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

DEFAULT_DB = PROJECT_ROOT / "data_new" / "db" / "vingroup_pilot.db"
DEFAULT_SOURCE = PROJECT_ROOT / "data_new" / "vingroup_faulty_pilot_dataset"


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
    # Ensure snapshot_id column exists (may not be in source CSV)
    try:
        con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS snapshot_id VARCHAR")
    except Exception:
        pass  # Column may already exist or not needed
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

    # ── EV telemetry (actual CSV schema) ──────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.ev_telemetry (
            record_id                VARCHAR PRIMARY KEY,
            vehicle_vin             VARCHAR,
            day_idx                 INT,
            sample_idx              INT,
            timestamp               TIMESTAMP NOT NULL,
            speed_kmh               DOUBLE,
            motor_rpm               DOUBLE,
            battery_soc             DOUBLE,
            battery_voltage         DOUBLE,
            battery_current         DOUBLE,
            battery_temp_c          DOUBLE,
            state_at_sample         VARCHAR,
            assigned_day_index      INT,
            ved_reference_veh_id     VARCHAR,
            synthetic_gap_indicator INT,
            event_sequence_index    INT,
            latitude                DOUBLE,
            longitude               DOUBLE,
            accel_z                 DOUBLE,
            telemetry_coverage      DOUBLE,
            snapshot_id             VARCHAR
        )
    """)

    # ── charging sessions (actual CSV schema) ──────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.charging_sessions (
            vehicle_vin            VARCHAR,
            session_id             VARCHAR PRIMARY KEY,
            station_id             VARCHAR,
            charger_id             VARCHAR,
            start_time             TIMESTAMP NOT NULL,
            duration_mins          DOUBLE,
            kwh_consumed           DOUBLE,
            power_kw               DOUBLE,
            charging_pattern       VARCHAR,
            assigned_day_index     INT,
            station_temp_c         DOUBLE,
            cost_vnd              DOUBLE,
            status                 VARCHAR,
            soft_overlap_flag      BOOLEAN,
            event_sequence_index   INT,
            snapshot_id            VARCHAR
        )
    """)

    # ── trips (actual CSV schema) ──────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.trips (
            trip_id               VARCHAR PRIMARY KEY,
            vehicle_vin           VARCHAR,
            driver_id             VARCHAR,
            pickup_datetime       TIMESTAMP NOT NULL,
            dropoff_datetime     TIMESTAMP,
            assigned_day_index    INT,
            trip_distance_km      DOUBLE,
            fare_amount          DOUBLE,
            currency_unverified   BOOLEAN,
            tip_amount           DOUBLE,
            total_fare           DOUBLE,
            pickup_latitude      DOUBLE,
            pickup_longitude     DOUBLE,
            vehicle_type         VARCHAR,
            event_sequence_index INT,
            snapshot_id           VARCHAR
        )
    """)

    # ── fleet index ───────────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.fleet_index (
            vehicle_vin          VARCHAR PRIMARY KEY,
            vehicle_type         VARCHAR,
            telemetry_equipped   BOOLEAN,
            snapshot_id          VARCHAR
        )
    """)

    # ── NLP benchmark (UIT-VSFC) ──────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.nlp_benchmark (
            sentence      VARCHAR,
            sentiment     INT,
            topic        VARCHAR,
            snapshot_id  VARCHAR
        )
    """)

    # ── Synthetic feedback scenario-driven ──────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.synthetic_feedback (
            feedback_id         VARCHAR PRIMARY KEY,
            vehicle_vin         VARCHAR,
            scenario_date       VARCHAR,
            assigned_day_index  INT,
            topic               VARCHAR,
            sentiment           INT,
            raw_comment_text    VARCHAR,
            snapshot_id         VARCHAR
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
        SELECT vehicle_vin, timestamp, battery_soc AS soc_pct, battery_voltage AS voltage,
               battery_temp_c AS temp_c
        FROM raw.ev_telemetry
        ORDER BY vehicle_vin, timestamp
    """)

    con.execute("""
        CREATE OR REPLACE VIEW vgreen_telemetry AS
        SELECT e.vehicle_vin, e.timestamp, e.state_at_sample, e.battery_soc AS soc_pct,
               e.speed_kmh, e.accel_z, e.motor_rpm AS rpm, e.assigned_day_index,
               f.vehicle_type, e.telemetry_coverage
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
            NULL AS duration_minutes,
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
        SELECT feedback_id, vehicle_vin, raw_comment_text AS review_text, sentiment AS rating,
               scenario_date AS submitted_at, topic
        FROM raw.synthetic_feedback
        ORDER BY scenario_date DESC
    """)

    con.execute("""
        CREATE OR REPLACE VIEW vgreen_charging_sessions AS
        SELECT vehicle_vin, session_id, station_id, charger_id, start_time,
               duration_mins, kwh_consumed, power_kw, charging_pattern,
               assigned_day_index, station_temp_c, cost_vnd, status,
               soft_overlap_flag, event_sequence_index, snapshot_id
        FROM raw.charging_sessions
        ORDER BY vehicle_vin, start_time
    """)

    print("[OK] Schema created")


# ─── Ingest ──────────────────────────────────────────────────────────────────

def ingest(source_dir: Path, db_path: Path, con=None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    close_after = con is None
    if con is None:
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

    # NLP benchmark
    nlp_path = source_dir / "nlp_benchmark_uit_vsfc.csv"
    load_csv_optional(con, "NLP Benchmark", nlp_path, "raw.nlp_benchmark")

    # Synthetic feedback scenario-driven
    fb_path = source_dir / "synthetic_feedback_scenario_driven.csv"
    if fb_path.exists():
        load_csv_optional(con, "Synthetic Feedback", fb_path, "raw.synthetic_feedback")

    # register snapshot
    tel_count = con.execute("SELECT count(*) FROM raw.ev_telemetry").fetchone()[0]
    con.execute("""
        INSERT INTO raw.raw_snapshots (snapshot_id, dataset_name, file_hash, source_path, row_count)
        VALUES (?, ?, ?, ?, ?)
    """, [snap_id, "vingroup_pilot", "manual_" + snap_id, str(source_dir), tel_count])

    # ── manifests ─────────────────────────────────────────────────────────────
    fault_path = source_dir / "fault_manifest.json"
    prov_path = source_dir / "provenance_manifest.json"
    fault_injected = fault_path.exists()

    if fault_injected:
        try:
            con.execute("DELETE FROM raw.fault_manifest")
        except Exception:
            pass
        with open(fault_path, encoding="utf-8") as f:
            faults = json.load(f)
        faults_data = faults.get("faults", faults) if isinstance(faults, dict) else faults
        for fault in faults_data:
            con.execute("""
                INSERT INTO raw.fault_manifest
                    (fault_id, fault_type, injected_at, description, affected_rows, dataset_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                fault.get("fault_id", uuid.uuid4().hex[:12]),
                fault.get("fault_family", "unknown"),
                fault.get("injected_at"),
                fault.get("description", ""),
                fault.get("affected_rows", 0),
                snap_id,
                json.dumps(fault),
            ])
        print(f"  [OK]   Fault manifest: {len(faults_data)} faults")

    if prov_path.exists():
        try:
            con.execute("DELETE FROM raw.provenance_manifest")
        except Exception:
            pass
        with open(prov_path, encoding="utf-8") as f:
            prov = json.load(f)
        # provenance_manifest.json is a dict, not a list
        if isinstance(prov, dict):
            con.execute("""
                INSERT INTO raw.provenance_manifest
                    (artifact_id, artifact_type, source_file, source_hash, lineage, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                "prov_" + snap_id,
                "provenance_manifest",
                str(prov_path),
                prov.get("random_seed", ""),
                json.dumps(prov),
                snap_id,
            ])
            print(f"  [OK]   Provenance manifest: 1 artifact")
        elif isinstance(prov, list):
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

    if close_after:
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
    parser.add_argument("--verify", action="store_true", help="Print DB summary after ingest")
    args = parser.parse_args()

    print(f"Target:   {args.db}")
    print(f"Source:   {args.source_dir}")
    ingest(args.source_dir, args.db)

    if args.verify:
        print("\n" + "=" * 60)
        print("DB Summary:")
        print("=" * 60)
        con = duckdb.connect(str(args.db), read_only=True)
        tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'").fetchall()
        for t in tables:
            count = con.execute(f"SELECT count(*) FROM raw.{t[0]}").fetchone()[0]
            print(f"  raw.{t[0]}: {count} rows")
        print("\nSample EV telemetry:")
        df = con.execute("SELECT vehicle_vin, battery_soc, battery_voltage FROM raw.ev_telemetry LIMIT 3").df()
        print(df.to_string())
        con.close()
