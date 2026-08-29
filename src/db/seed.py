import hashlib
import os
import uuid

from src.db.connection import DuckDBManager
from src.reliability.models.provenance import DataProvenance


BENCHMARK_TAG = "Semi-Synthetic Causal Digital Twin"
BENCHMARK_TARGET = "60-day horizon, 30 VIN, 4 stations target"


def compute_sha256(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def apply_canonical_reset(conn, project_root: str) -> None:
    migration_path = os.path.join(
        project_root, "src", "db", "migrations", "0003_main_canonical_truth.sql"
    )
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()

    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        try:
            conn.execute(stmt)
        except Exception as exc:
            print(f"Warning: migration 0003 statement skipped: {exc}")


def seed_database(db_path: str = None) -> None:
    """Load parquet into landing.*, then promote into main.* (same path as live ingest)."""
    db_manager = DuckDBManager(db_path=db_path)
    db_manager.init_schema()

    project_root = db_manager.project_root
    from src.config import get_settings

    parquet_rel_path = get_settings().landing_parquet_path
    candidates = [
        parquet_rel_path if os.path.isabs(parquet_rel_path) else os.path.join(project_root, parquet_rel_path),
        os.path.join(project_root, "landing_data", "vingroup_pilot_landing_demo.parquet"),
        os.path.join(project_root, "data_demo", "vingroup_pilot_landing_demo.parquet"),
        os.path.join(project_root, "data_new", "vingroup_pilot_landing.parquet"),
    ]
    pq_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

    if not os.path.exists(pq_path):
        print(f"Warning: Landing parquet not found at {pq_path}. Skipping database seed.")
        return

    clean_pq_path = pq_path.replace("\\", "/")
    sha256_hash = compute_sha256(pq_path)
    conn = db_manager.get_connection()
    apply_canonical_reset(conn, project_root)
    from src.services.landing_promote import LANDING_TABLES, promote_landing_all, reset_landing_tables
    reset_landing_tables(db_manager)

    table_configs = [
        {
            "dataset_table": "ev_telemetry",
            "table_name": "ev_telemetry",
            "source_name": "ev_telemetry",
            "sql": f"""
                INSERT INTO landing.ev_telemetry (
                    record_id, vehicle_vin, day_idx, sample_idx, timestamp, speed_kmh,
                    motor_rpm, battery_soc, battery_voltage, battery_current,
                    battery_temp_c, state_at_sample, assigned_day_index,
                    ved_reference_veh_id, synthetic_gap_indicator,
                    event_sequence_index, latitude, longitude, accel_z,
                    telemetry_coverage, snapshot_id, source_ingestion_run_id
                )
                SELECT
                    record_id,
                    vehicle_vin,
                    day_idx,
                    sample_idx,
                    CAST(timestamp AS VARCHAR) AS timestamp,
                    speed_kmh,
                    motor_rpm,
                    battery_soc,
                    battery_voltage,
                    battery_current,
                    battery_temp_c,
                    state_at_sample,
                    assigned_day_index,
                    ved_reference_veh_id,
                    synthetic_gap_indicator,
                    event_sequence_index,
                    latitude,
                    longitude,
                    accel_z,
                    telemetry_coverage,
                    'SNAP_LANDING' AS snapshot_id,
                    'SEED_LANDING' AS source_ingestion_run_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'ev_telemetry'
            """,
        },
        {
            "dataset_table": "acn_charging",
            "table_name": "charging_sessions",
            "source_name": "charging_sessions",
            "sql": f"""
                INSERT INTO landing.charging_sessions (
                    vehicle_vin, session_id, station_id, charger_id, start_time,
                    duration_mins, kwh_consumed, power_kw, charging_pattern,
                    assigned_day_index, station_temp_c, cost_vnd, status,
                    soft_overlap_flag, event_sequence_index, snapshot_id,
                    source_ingestion_run_id
                )
                SELECT
                    vehicle_vin,
                    session_id,
                    station_id,
                    charger_id,
                    CAST(start_time AS VARCHAR) AS start_time,
                    duration_mins,
                    kwh_consumed,
                    power_kw,
                    charging_pattern,
                    assigned_day_index,
                    station_temp_c,
                    cost_vnd,
                    status,
                    soft_overlap_flag,
                    event_sequence_index,
                    'SNAP_LANDING' AS snapshot_id,
                    'SEED_LANDING' AS source_ingestion_run_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'acn_charging'
            """,
        },
        {
            "dataset_table": "ride_trips",
            "table_name": "trips",
            "source_name": "trips",
            "sql": f"""
                INSERT INTO landing.trips (
                    trip_id, vehicle_vin, driver_id, pickup_datetime,
                    dropoff_datetime, assigned_day_index, trip_distance_km,
                    fare_amount, currency_unverified, tip_amount, total_fare,
                    pickup_latitude, pickup_longitude, vehicle_type,
                    event_sequence_index, snapshot_id, source_ingestion_run_id
                )
                SELECT
                    trip_id,
                    vehicle_vin,
                    driver_id,
                    CAST(pickup_datetime AS VARCHAR) AS pickup_datetime,
                    CAST(dropoff_datetime AS VARCHAR) AS dropoff_datetime,
                    assigned_day_index,
                    trip_distance_km,
                    fare_amount,
                    currency_unverified,
                    tip_amount,
                    total_fare,
                    pickup_latitude,
                    pickup_longitude,
                    vehicle_type,
                    event_sequence_index,
                    'SNAP_LANDING' AS snapshot_id,
                    'SEED_LANDING' AS source_ingestion_run_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'ride_trips'
            """,
        },
        {
            "dataset_table": "feedback",
            "table_name": "nlp_feedback",
            "source_name": "nlp_feedback",
            "sql": f"""
                INSERT INTO landing.nlp_feedback (
                    feedback_id, vehicle_vin, sentence, sentiment, topic,
                    scenario_date, raw_comment_text, snapshot_id, source_ingestion_run_id
                )
                SELECT
                    feedback_id,
                    vehicle_vin,
                    sentence,
                    TRY_CAST(sentiment AS BIGINT) AS sentiment,
                    TRY_CAST(topic AS BIGINT) AS topic,
                    CAST(scenario_date AS VARCHAR) AS scenario_date,
                    raw_comment_text,
                    'SNAP_LANDING' AS snapshot_id,
                    'SEED_LANDING' AS source_ingestion_run_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'feedback'
            """,
        },
        {
            "dataset_table": "fleet_index",
            "table_name": "ref.fleet_index_ref",
            "source_name": "fleet_index_ref",
            "sql": f"""
                INSERT INTO ref.fleet_index_ref (
                    vehicle_vin, vehicle_type, telemetry_equipped,
                    snapshot_id, source_ingestion_run_id
                )
                SELECT
                    vehicle_vin,
                    vehicle_type,
                    telemetry_equipped,
                    'SNAP_LANDING' AS snapshot_id,
                    'SEED_LANDING' AS source_ingestion_run_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'fleet_index'
            """,
        },
    ]

    prov_val = DataProvenance.SEMI_SYNTHETIC.value
    tag_val = BENCHMARK_TAG

    for config in table_configs:
        conn.execute(config["sql"])
        count_from = (
            f"landing.{config['table_name']}"
            if config["table_name"] in LANDING_TABLES
            else config["table_name"]
        )
        row_cnt = conn.execute(f"SELECT COUNT(*) FROM {count_from}").fetchone()[0]
        db_manager.execute(
            """
            INSERT INTO raw_snapshots (id, source_name, file_path, sha256_hash, row_count, column_count, provenance, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                config["source_name"],
                pq_path,
                sha256_hash,
                row_cnt,
                0,
                prov_val,
                tag_val,
            ],
        )
        print(f"Seeded {row_cnt} rows into landing/ref '{config['table_name']}'.")

    promote_landing_all(db_manager)

    rel_data_dir = os.path.relpath(pq_path, project_root) if os.path.isabs(pq_path) else pq_path
    db_manager.execute(
        """
        INSERT INTO datasets (dataset_key, file_path, provenance, tag)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (dataset_key) DO UPDATE SET file_path = EXCLUDED.file_path, provenance = EXCLUDED.provenance, tag = EXCLUDED.tag
        """,
        ["integrated_benchmark", rel_data_dir, DataProvenance.SEMI_SYNTHETIC.value, BENCHMARK_TAG],
    )

    print("\n=== Canonical Database Seed Summary ===")
    print(f"Landing Parquet Path: '{pq_path}'")
    print(f"Integrated Benchmark Tag: '{BENCHMARK_TAG}' ({BENCHMARK_TARGET})")
    for table_name in ("ev_telemetry", "charging_sessions", "trips", "nlp_feedback"):
        count = conn.execute(f"SELECT COUNT(*) FROM main.{table_name}").fetchone()[0]
        print(f"main.{table_name}: {count} records | Provenance: {prov_val}")
    ref_count = conn.execute("SELECT COUNT(*) FROM ref.fleet_index_ref").fetchone()[0]
    print(f"ref.fleet_index_ref: {ref_count} records")
    print("=======================================\n")


if __name__ == "__main__":
    seed_database()
