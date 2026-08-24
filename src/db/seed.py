import hashlib
import json
import os
import uuid
import pandas as pd
from src.db.connection import DuckDBManager
from src.reliability.models.provenance import DataProvenance


BENCHMARK_TAG = "Semi-Synthetic Causal Digital Twin"
BENCHMARK_TARGET = "60-day horizon, 30 VIN, 4 stations target"


def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def map_xanhsm_feedback(df: pd.DataFrame, snapshot_id: str, start_id: int = 1) -> pd.DataFrame:
    """Map customer feedback to xanhsm_feedback table schema."""
    review_col = "raw_comment_text" if "raw_comment_text" in df.columns else ("review_text" if "review_text" in df.columns else df.columns[0])
    rating_col = "sentiment" if "sentiment" in df.columns else ("sentiment_label" if "sentiment_label" in df.columns else "rating")
    aspects_json = None
    if "topic" in df.columns:
        aspects_json = df["topic"].apply(lambda t: json.dumps([t]) if pd.notna(t) else None)

    return pd.DataFrame({
        "id": range(start_id, start_id + len(df)),
        "review_text": df[review_col],
        "normalized_text": None,
        "rating": df[rating_col].astype(float) if rating_col in df.columns else 0.0,
        "location": None,
        "timestamp": df["scenario_date"] if "scenario_date" in df.columns else None,
        "source": "xanh_sm",
        "aspects": aspects_json,
        "snapshot_id": snapshot_id,
    })


def map_vgreen_telemetry(df: pd.DataFrame, snapshot_id: str, start_id: int = 1) -> pd.DataFrame:
    """Map charging telemetry to vgreen_telemetry table schema."""
    st_id = "station_id" if "station_id" in df.columns else df.columns[0]
    st_name = "charger_id" if "charger_id" in df.columns else ("station_name" if "station_name" in df.columns else st_id)
    temp_c = "station_temp_c" if "station_temp_c" in df.columns else "temperature_celsius"
    volts = "voltage" if "voltage" in df.columns else None
    power_kw = "power_kw" if "power_kw" in df.columns else None
    status = "status" if "status" in df.columns else None
    ts = "start_time" if "start_time" in df.columns else "timestamp"
    
    return pd.DataFrame({
        "id": range(start_id, start_id + len(df)),
        "station_id": df[st_id],
        "station_name": df[st_name] if st_name in df.columns else df[st_id],
        "temperature_celsius": df[temp_c].astype(float) if temp_c in df.columns else None,
        "voltage": df[volts].astype(float) if volts and volts in df.columns else None,
        "current_amps": None,
        "duty_cycle": df[power_kw].astype(float) if power_kw and power_kw in df.columns else None,
        "status": df[status] if status in df.columns else "ACTIVE",
        "fault_code": None,
        "timestamp": df[ts] if ts in df.columns else None,
        "snapshot_id": snapshot_id,
    })


def map_vinfast_bms(df: pd.DataFrame, snapshot_id: str, start_id: int = 1) -> pd.DataFrame:
    """Map EV telemetry to vinfast_bms table schema."""
    v_id = "vehicle_vin" if "vehicle_vin" in df.columns else "vehicle_id"
    soc = "battery_soc" if "battery_soc" in df.columns else "battery_soc"
    volts = "battery_voltage" if "battery_voltage" in df.columns else "battery_voltage"
    temp = "battery_temp_c" if "battery_temp_c" in df.columns else "cell_temp_max"
    ts = "timestamp" if "timestamp" in df.columns else "timestamp"
    
    return pd.DataFrame({
        "id": range(start_id, start_id + len(df)),
        "vehicle_id": df[v_id],
        "battery_soc": df[soc].astype(float),
        "battery_voltage": df[volts].astype(float),
        "cell_temp_max": df[temp].astype(float) if temp in df.columns else None,
        "cell_temp_min": None,
        "bms_fault_code": None,
        "charging_station_id": None,
        "timestamp": df[ts] if ts in df.columns else None,
        "snapshot_id": snapshot_id,
    })


def map_xanhsm_trips(df: pd.DataFrame, snapshot_id: str, start_id: int = 1) -> pd.DataFrame:
    """Map ride hailing trips to xanhsm_trips table schema."""
    t_id = "trip_id" if "trip_id" in df.columns else df.columns[0]
    d_id = "driver_id" if "driver_id" in df.columns else "driver_id"
    # EDA 2026-08-14: dataset da rename + scale sang km => distance_km (Tier R du lieu goc, khong can mult)
    if "trip_distance_km" in df.columns:
        dist = "trip_distance_km"; mult = 1.0
    elif "trip_miles" in df.columns:        # backward-compat cho data cu
        dist = "trip_miles"; mult = 1.60934
    else:
        dist = "distance_km"; mult = 1.0
    fare = "total_fare" if "total_fare" in df.columns else "fare_vnd"
    ts = "pickup_datetime" if "pickup_datetime" in df.columns else "timestamp"

    pickup_loc = None
    if "pickup_latitude" in df.columns and "pickup_longitude" in df.columns:
        pickup_loc = df["pickup_latitude"].astype(str) + "," + df["pickup_longitude"].astype(str)
    elif "pickup_location" in df.columns:
        pickup_loc = df["pickup_location"]

    return pd.DataFrame({
        "id": range(start_id, start_id + len(df)),
        "trip_id": df[t_id],
        "driver_id": df[d_id],
        "pickup_location": pickup_loc,
        "dropoff_location": None,
        "distance_km": df[dist] * mult,
        "fare_vnd": df[fare].astype(float),
        "duration_minutes": None,
        "rating": None,
        "timestamp": df[ts] if ts in df.columns else None,
        "snapshot_id": snapshot_id,
    })


def seed_database(db_path: str = None) -> None:
    """Ingest landing parquet dataset into DuckDB tables with raw_snapshots metadata tracking and provenance tagging."""
    db_manager = DuckDBManager(db_path=db_path)
    db_manager.init_schema()

    project_root = db_manager.project_root
    from src.config import get_settings
    
    parquet_rel_path = get_settings().landing_parquet_path
    if os.path.isabs(parquet_rel_path):
        pq_path = parquet_rel_path
    else:
        pq_path = os.path.join(project_root, parquet_rel_path)

    if not os.path.exists(pq_path):
        pq_path = os.path.join(project_root, "data_demo", "vingroup_pilot_landing_demo.parquet")
    
    if not os.path.exists(pq_path):
        print(f"Warning: Landing parquet not found at {pq_path}. Skipping database seed.")
        return

    clean_pq_path = pq_path.replace("\\", "/")
    sha256_hash = compute_sha256(pq_path)
    conn = db_manager.get_connection()

    table_configs = [
        {
            "dataset_table": "feedback",
            "table_name": "xanhsm_feedback",
            "source_name": "xanh_sm_customer_feedback",
            "sql": f"""
                INSERT INTO xanhsm_feedback (id, review_text, normalized_text, rating, location, timestamp, source, aspects, snapshot_id)
                SELECT 
                    row_number() OVER () AS id,
                    COALESCE(raw_comment_text, '') AS review_text,
                    NULL AS normalized_text,
                    CAST(COALESCE(sentiment, 0.0) AS FLOAT) AS rating,
                    NULL AS location,
                    CAST(scenario_date AS TIMESTAMP) AS timestamp,
                    'xanh_sm' AS source,
                    CASE WHEN topic IS NOT NULL THEN json_array(topic) ELSE NULL END AS aspects,
                    'SNAP_LANDING' AS snapshot_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'feedback'
            """
        },
        {
            "dataset_table": "acn_charging",
            "table_name": "vgreen_telemetry",
            "source_name": "vgreen_charging_stations",
            "sql": f"""
                INSERT INTO vgreen_telemetry (id, station_id, station_name, temperature_celsius, voltage, current_amps, duty_cycle, status, fault_code, timestamp, snapshot_id)
                SELECT
                    row_number() OVER () AS id,
                    station_id,
                    COALESCE(charger_id, station_id) AS station_name,
                    CAST(station_temp_c AS FLOAT) AS temperature_celsius,
                    NULL AS voltage,
                    NULL AS current_amps,
                    CAST(power_kw AS FLOAT) AS duty_cycle,
                    COALESCE(status, 'ACTIVE') AS status,
                    NULL AS fault_code,
                    CAST(start_time AS TIMESTAMP) AS timestamp,
                    'SNAP_LANDING' AS snapshot_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'acn_charging'
            """
        },
        {
            "dataset_table": "ev_telemetry",
            "table_name": "vinfast_bms",
            "source_name": "vinfast_ev_telemetry",
            "sql": f"""
                INSERT INTO vinfast_bms (id, vehicle_id, battery_soc, battery_voltage, cell_temp_max, cell_temp_min, bms_fault_code, charging_station_id, timestamp, snapshot_id)
                SELECT
                    row_number() OVER () AS id,
                    vehicle_vin AS vehicle_id,
                    CAST(battery_soc AS FLOAT) AS battery_soc,
                    CAST(battery_voltage AS FLOAT) AS battery_voltage,
                    CAST(battery_temp_c AS FLOAT) AS cell_temp_max,
                    NULL AS cell_temp_min,
                    NULL AS bms_fault_code,
                    NULL AS charging_station_id,
                    CAST(timestamp AS TIMESTAMP) AS timestamp,
                    'SNAP_LANDING' AS snapshot_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'ev_telemetry'
            """
        },
        {
            "dataset_table": "ride_trips",
            "table_name": "xanhsm_trips",
            "source_name": "xanh_sm_trips",
            "sql": f"""
                INSERT INTO xanhsm_trips (id, trip_id, driver_id, pickup_location, dropoff_location, distance_km, fare_vnd, duration_minutes, rating, timestamp, snapshot_id)
                SELECT
                    row_number() OVER () AS id,
                    trip_id,
                    driver_id,
                    CASE WHEN pickup_latitude IS NOT NULL THEN CONCAT(CAST(pickup_latitude AS VARCHAR), ',', CAST(pickup_longitude AS VARCHAR)) ELSE NULL END AS pickup_location,
                    NULL AS dropoff_location,
                    CAST(trip_distance_km AS FLOAT) AS distance_km,
                    CAST(COALESCE(total_fare, fare_amount, 0.0) AS FLOAT) AS fare_vnd,
                    NULL AS duration_minutes,
                    NULL AS rating,
                    CAST(pickup_datetime AS TIMESTAMP) AS timestamp,
                    'SNAP_LANDING' AS snapshot_id
                FROM read_parquet('{clean_pq_path}')
                WHERE dataset_table = 'ride_trips'
            """
        },
    ]

    prov_val = DataProvenance.SEMI_SYNTHETIC.value
    tag_val = BENCHMARK_TAG

    for config in table_configs:
        table_name = config["table_name"]
        source_name = config["source_name"]

        existing_cnt = db_manager.execute(f"SELECT COUNT(*) FROM {table_name}")
        if existing_cnt and existing_cnt[0][0] > 0:
            print(f"Table '{table_name}' already seeded ({existing_cnt[0][0]} rows). Skipping.")
            continue

        snapshot_id = str(uuid.uuid4())
        conn.execute(config["sql"])
        
        row_cnt = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        db_manager.execute(
            """
            INSERT INTO raw_snapshots (id, source_name, file_path, sha256_hash, row_count, column_count, provenance, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [snapshot_id, source_name, pq_path, sha256_hash, row_cnt, 0, prov_val, tag_val],
        )
        print(f"Ingested {row_cnt} rows into '{table_name}' from Parquet (snapshot: {snapshot_id}).")

    rel_data_dir = os.path.relpath(pq_path, project_root) if os.path.isabs(pq_path) else pq_path
    db_manager.execute(
        """
        INSERT INTO datasets (dataset_key, file_path, provenance, tag)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (dataset_key) DO UPDATE SET file_path = EXCLUDED.file_path, provenance = EXCLUDED.provenance, tag = EXCLUDED.tag
        """,
        ["integrated_benchmark", rel_data_dir, DataProvenance.SEMI_SYNTHETIC.value, BENCHMARK_TAG],
    )

    print("\n=== Database Seed Summary ===")
    print(f"Landing Parquet Path: '{pq_path}'")
    print(f"Integrated Benchmark Tag: '{BENCHMARK_TAG}' ({BENCHMARK_TARGET})")
    for config in table_configs:
        t_name = config["table_name"]
        res = db_manager.execute(f"SELECT COUNT(*) FROM {t_name}")
        count = res[0][0] if res else 0
        print(f"Table '{t_name}': {count} records | Provenance: {prov_val}")
    print("=============================\n")



if __name__ == "__main__":
    seed_database()

