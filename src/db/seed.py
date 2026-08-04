import hashlib
import os
import uuid
import pandas as pd
from src.db.connection import DuckDBManager


def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def map_xanhsm_feedback(df: pd.DataFrame, snapshot_id: str) -> pd.DataFrame:
    """Map real_xanh_sm_customer_feedback.csv to xanhsm_feedback table schema."""
    return pd.DataFrame({
        "id": range(1, len(df) + 1),
        "review_text": df["raw_comment_text"],
        "normalized_text": None,
        "rating": df["sentiment_label"].astype(float),
        "location": None,
        "timestamp": None,
        "source": "xanh_sm",
        "aspects": None,
        "snapshot_id": snapshot_id,
    })


def map_vgreen_telemetry(df: pd.DataFrame, snapshot_id: str) -> pd.DataFrame:
    """Map real_vgreen_charging_stations.csv to vgreen_telemetry table schema."""
    return pd.DataFrame({
        "id": range(1, len(df) + 1),
        "station_id": df["station_id"],
        "station_name": df["charger_id"],
        "temperature_celsius": None,
        "voltage": None,
        "current_amps": None,
        "duty_cycle": None,
        "status": df["status"],
        "fault_code": None,
        "timestamp": None,
        "snapshot_id": snapshot_id,
    })


def map_vinfast_bms(df: pd.DataFrame, snapshot_id: str) -> pd.DataFrame:
    """Map real_vinfast_ev_telemetry.csv to vinfast_bms table schema."""
    return pd.DataFrame({
        "id": range(1, len(df) + 1),
        "vehicle_id": df["vehicle_vin"],
        "battery_soc": df["battery_soc"].astype(float),
        "battery_voltage": df["battery_voltage"].astype(float),
        "cell_temp_max": df["battery_temp_c"].astype(float),
        "cell_temp_min": None,
        "bms_fault_code": None,
        "charging_station_id": None,
        "timestamp": None,
        "snapshot_id": snapshot_id,
    })


def map_xanhsm_trips(df: pd.DataFrame, snapshot_id: str) -> pd.DataFrame:
    """Map real_xanh_sm_trips.csv to xanhsm_trips table schema."""
    pickup_loc = (
        df["pickup_latitude"].astype(str) + "," + df["pickup_longitude"].astype(str)
    )
    return pd.DataFrame({
        "id": range(1, len(df) + 1),
        "trip_id": df["trip_id"],
        "driver_id": df["driver_id"],
        "pickup_location": pickup_loc,
        "dropoff_location": None,
        "distance_km": df["trip_miles"] * 1.60934,
        "fare_vnd": df["total_fare"].astype(float),
        "duration_minutes": None,
        "rating": None,
        "timestamp": None,
        "snapshot_id": snapshot_id,
    })


def seed_database(db_path: str = None) -> None:
    """Ingest CSV files into DuckDB tables with raw_snapshots metadata tracking."""
    db_manager = DuckDBManager(db_path=db_path)
    db_manager.init_schema()

    project_root = db_manager.project_root
    data_dir = os.path.join(project_root, "data", "vingroup_real")

    csv_configs = [
        {
            "file_path": os.path.join(data_dir, "real_xanh_sm_customer_feedback.csv"),
            "table_name": "xanhsm_feedback",
            "source_name": "real_xanh_sm_customer_feedback",
            "mapper": map_xanhsm_feedback,
        },
        {
            "file_path": os.path.join(data_dir, "real_vgreen_charging_stations.csv"),
            "table_name": "vgreen_telemetry",
            "source_name": "real_vgreen_charging_stations",
            "mapper": map_vgreen_telemetry,
        },
        {
            "file_path": os.path.join(data_dir, "real_vinfast_ev_telemetry.csv"),
            "table_name": "vinfast_bms",
            "source_name": "real_vinfast_ev_telemetry",
            "mapper": map_vinfast_bms,
        },
        {
            "file_path": os.path.join(data_dir, "real_xanh_sm_trips.csv"),
            "table_name": "xanhsm_trips",
            "source_name": "real_xanh_sm_trips",
            "mapper": map_xanhsm_trips,
        },
    ]

    conn = db_manager.get_connection()

    for config in csv_configs:
        file_path = config["file_path"]
        table_name = config["table_name"]
        source_name = config["source_name"]
        mapper = config["mapper"]

        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} not found. Skipping.")
            continue

        sha256_hash = compute_sha256(file_path)

        existing = db_manager.execute(
            "SELECT id FROM raw_snapshots WHERE sha256_hash = ?", [sha256_hash]
        )
        if existing:
            print(f"Snapshot for {table_name} ({sha256_hash[:8]}...) already exists. Skipping ingestion.")
            continue

        df = pd.read_csv(file_path)
        snapshot_id = str(uuid.uuid4())

        # Insert raw_snapshots metadata record
        db_manager.execute(
            """
            INSERT INTO raw_snapshots (id, source_name, file_path, sha256_hash, row_count, column_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [snapshot_id, source_name, file_path, sha256_hash, len(df), len(df.columns)],
        )

        # Map DataFrame columns to target DuckDB schema
        mapped_df = mapper(df, snapshot_id)

        # Insert data rows into target table using DuckDB's INSERT INTO ... SELECT from pandas DataFrame
        cols = ", ".join(mapped_df.columns)
        conn.execute(f"INSERT INTO {table_name} ({cols}) SELECT {cols} FROM mapped_df")
        print(f"Ingested {len(mapped_df)} rows into '{table_name}' (snapshot: {snapshot_id}).")

    # Print summary
    print("\n=== Database Seed Summary ===")
    for config in csv_configs:
        t_name = config["table_name"]
        res = db_manager.execute(f"SELECT COUNT(*) FROM {t_name}")
        count = res[0][0] if res else 0
        print(f"Table '{t_name}': {count} records")
    print("=============================\n")


if __name__ == "__main__":
    seed_database()
