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
    """Ingest CSV files into DuckDB tables with raw_snapshots metadata tracking and provenance tagging."""
    db_manager = DuckDBManager(db_path=db_path)
    db_manager.init_schema()

    project_root = db_manager.project_root
    
    # Candidates for data directory
    candidates = [
        os.path.join(project_root, "data_new", "vingroup_faulty_pilot_dataset"),
        os.path.join(project_root, "data", "vingroup_faulty_pilot_dataset"),
        os.path.join(project_root, "data_new", "vingroup_pilot_dataset"),
        os.path.join(project_root, "data", "vingroup_real"),
    ]
    data_dir = None
    for c in candidates:
        if os.path.exists(c):
            data_dir = c
            break
    if not data_dir:
        data_dir = os.path.join(project_root, "data_new", "vingroup_faulty_pilot_dataset")

    csv_configs = [
        {
            "file_names": ["synthetic_feedback_scenario_driven.csv", "real_xanh_sm_customer_feedback.csv"],
            "table_name": "xanhsm_feedback",
            "source_name": "xanh_sm_customer_feedback",
            "mapper": map_xanhsm_feedback,
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": BENCHMARK_TAG,
        },
        {
            "file_names": ["acn_charging_mapped.csv", "real_vgreen_charging_stations.csv"],
            "table_name": "vgreen_telemetry",
            "source_name": "vgreen_charging_stations",
            "mapper": map_vgreen_telemetry,
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": BENCHMARK_TAG,
        },
        {
            "file_names": ["synthetic_ev_telemetry_ved_ref.csv", "real_vinfast_ev_telemetry.csv"],
            "table_name": "vinfast_bms",
            "source_name": "vinfast_ev_telemetry",
            "mapper": map_vinfast_bms,
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": BENCHMARK_TAG,
        },
        {
            "file_names": ["ride_hailing_xanh_sm_trips.csv", "real_xanh_sm_trips.csv"],
            "table_name": "xanhsm_trips",
            "source_name": "xanh_sm_trips",
            "mapper": map_xanhsm_trips,
            "provenance": DataProvenance.SEMI_SYNTHETIC,
            "tag": BENCHMARK_TAG,
        },
    ]

    conn = db_manager.get_connection()

    for config in csv_configs:
        file_path = None
        for name in config["file_names"]:
            p = os.path.join(data_dir, name)
            if os.path.exists(p):
                file_path = p
                break
        
        if not file_path:
            print(f"Warning: No matching CSV for {config['table_name']} found in {data_dir}. Skipping.")
            continue

        table_name = config["table_name"]
        source_name = config["source_name"]
        mapper = config["mapper"]
        prov_val = config["provenance"].value if isinstance(config["provenance"], DataProvenance) else config["provenance"]
        tag_val = config.get("tag", BENCHMARK_TAG)

        sha256_hash = compute_sha256(file_path)

        existing = db_manager.execute(
            "SELECT id FROM raw_snapshots WHERE sha256_hash = ?", [sha256_hash]
        )
        if existing:
            # Ensure existing record has provenance metadata updated
            db_manager.execute(
                "UPDATE raw_snapshots SET provenance = ?, tag = ? WHERE sha256_hash = ?",
                [prov_val, tag_val, sha256_hash]
            )
            print(f"Snapshot for {table_name} ({sha256_hash[:8]}...) already exists. Updated provenance metadata.")
            continue

        df = pd.read_csv(file_path)
        snapshot_id = str(uuid.uuid4())

        # Compute next auto-increment ID
        res = db_manager.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
        start_id = (res[0][0] if res else 0) + 1

        # Insert raw_snapshots metadata record with explicit provenance
        db_manager.execute(
            """
            INSERT INTO raw_snapshots (id, source_name, file_path, sha256_hash, row_count, column_count, provenance, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [snapshot_id, source_name, file_path, sha256_hash, len(df), len(df.columns), prov_val, tag_val],
        )

        # Map DataFrame columns to target DuckDB schema
        mapped_df = mapper(df, snapshot_id, start_id=start_id)

        # Insert data rows into target table using DuckDB's INSERT INTO ... SELECT from pandas DataFrame
        cols = ", ".join(mapped_df.columns)
        conn.execute(f"INSERT INTO {table_name} ({cols}) SELECT {cols} FROM mapped_df")
        print(f"Ingested {len(mapped_df)} rows into '{table_name}' (snapshot: {snapshot_id}, provenance: {prov_val}).")

    # Tag integrated benchmark dataset in datasets registry table
    rel_data_dir = os.path.relpath(data_dir, project_root) if os.path.isabs(data_dir) else data_dir
    db_manager.execute(
        """
        INSERT INTO datasets (dataset_key, file_path, provenance, tag)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (dataset_key) DO UPDATE SET file_path = EXCLUDED.file_path, provenance = EXCLUDED.provenance, tag = EXCLUDED.tag
        """,
        ["integrated_benchmark", rel_data_dir, DataProvenance.SEMI_SYNTHETIC.value, BENCHMARK_TAG],
    )

    # Print summary
    print("\n=== Database Seed Summary ===")
    print(f"Integrated Benchmark Tag: '{BENCHMARK_TAG}' ({BENCHMARK_TARGET})")
    for config in csv_configs:
        t_name = config["table_name"]
        prov_val = config["provenance"].value if isinstance(config["provenance"], DataProvenance) else config["provenance"]
        res = db_manager.execute(f"SELECT COUNT(*) FROM {t_name}")
        count = res[0][0] if res else 0
        print(f"Table '{t_name}': {count} records | Provenance: {prov_val}")
    print("=============================\n")


if __name__ == "__main__":
    seed_database()

