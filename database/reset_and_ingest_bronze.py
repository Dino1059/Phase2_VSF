"""
DataTrust OS: Reset & Ingest Bronze Data + Data Catalog Metadata Initializer
Truncates and ingests 8 CSV files from data/vingroup_pii_faulty_testset_3zone into schema bronze,
and populates schema catalog (catalog.datasets and catalog.columns).
"""

import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Add fallback path for airflow environment
if os.path.exists("/home/airflow/.local/lib/python3.7/site-packages"):
    sys.path.insert(0, "/home/airflow/.local/lib/python3.7/site-packages")

import psycopg2
from psycopg2.extras import execute_values


DATASET_METADATA = {
    "acn_charging_mapped": {
        "file": "acn_charging_mapped.csv",
        "domain": "charging",
        "title": "ACN Charging Sessions Mapped",
        "pk": "session_id",
        "tags": {
            "session_id": ("identifier", "NON_PERSONAL_REFERENCE", "identifier"),
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "station_id": ("station_id", "NON_PERSONAL_REFERENCE", "identifier"),
            "charger_id": ("charger_id", "NON_PERSONAL_REFERENCE", "identifier"),
            "start_time": ("timestamp", "TECHNICAL_METADATA", "technical_metadata"),
            "duration_mins": ("duration_mins", "NON_PERSONAL_REFERENCE", "technical_metadata"),
            "kwh_consumed": ("kwh_consumed", "NON_PERSONAL_REFERENCE", "energy_metric"),
            "power_kw": ("power_kw", "TECHNICAL_METADATA", "energy_metric"),
            "charging_pattern": ("charging_pattern", "TECHNICAL_METADATA", "technical_metadata"),
            "assigned_day_index": ("day_index", "TECHNICAL_METADATA", "technical_metadata"),
            "station_temp_c": ("temperature_celsius", "TECHNICAL_METADATA", "technical_metadata"),
            "cost_vnd": ("cost_amount", "NON_PERSONAL_REFERENCE", "financial"),
            "status": ("status", "TECHNICAL_METADATA", "technical_metadata"),
            "soft_overlap_flag": ("flag", "TECHNICAL_METADATA", "technical_metadata"),
            "event_sequence_index": ("sequence_index", "TECHNICAL_METADATA", "technical_metadata"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
        }
    },
    "dim_customers": {
        "file": "dim_customers.csv",
        "domain": "customers",
        "title": "Customer Profiles Dimension",
        "pk": "customer_id",
        "tags": {
            "customer_id": ("customer_ref", "LINKABLE_IDENTIFIER", "identifier"),
            "first_name": ("person_name", "DIRECT_IDENTIFIER", "name"),
            "last_name": ("person_name", "DIRECT_IDENTIFIER", "name"),
            "email": ("email_address", "DIRECT_IDENTIFIER", "contact"),
            "phone_number": ("phone_number", "DIRECT_IDENTIFIER", "contact"),
            "created_at": ("timestamp", "TECHNICAL_METADATA", "technical_metadata"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
        }
    },
    "dim_drivers": {
        "file": "dim_drivers.csv",
        "domain": "drivers",
        "title": "GSM Driver Registry Dimension",
        "pk": "driver_id",
        "tags": {
            "driver_id": ("driver_ref", "LINKABLE_IDENTIFIER", "identifier"),
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "first_name": ("person_name", "DIRECT_IDENTIFIER", "name"),
            "last_name": ("person_name", "DIRECT_IDENTIFIER", "name"),
            "email": ("email_address", "DIRECT_IDENTIFIER", "contact"),
            "phone_number": ("phone_number", "DIRECT_IDENTIFIER", "contact"),
            "created_at": ("timestamp", "TECHNICAL_METADATA", "technical_metadata"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
        }
    },
    "feedback_pii": {
        "file": "feedback_pii.csv",
        "domain": "feedback",
        "title": "Customer Free-Text Feedback & PII Injection",
        "pk": "feedback_id",
        "tags": {
            "feedback_id": ("identifier", "NON_PERSONAL_REFERENCE", "identifier"),
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "scenario_date": ("date", "TECHNICAL_METADATA", "technical_metadata"),
            "assigned_day_index": ("day_index", "TECHNICAL_METADATA", "technical_metadata"),
            "topic": ("feedback_topic", "NON_PERSONAL_REFERENCE", "content_feedback"),
            "sentiment": ("feedback_sentiment", "NON_PERSONAL_REFERENCE", "content_feedback"),
            "raw_comment_text": ("free_text_comment", "AMBIGUOUS_UNSTRUCTURED_DATA", "content_feedback"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
            "trip_id": ("trip_ref", "LINKABLE_IDENTIFIER", "identifier"),
            "customer_id": ("customer_ref", "LINKABLE_IDENTIFIER", "identifier"),
        }
    },
    "fleet_index": {
        "file": "fleet_index.csv",
        "domain": "fleet",
        "title": "VinFast 3-Zone Fleet Index",
        "pk": "vehicle_vin",
        "tags": {
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "vehicle_type": ("vehicle_category", "NON_PERSONAL_REFERENCE", "vehicle_technical"),
            "telemetry_equipped": ("flag", "TECHNICAL_METADATA", "technical_metadata"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
        }
    },
    "ride_hailing_xanh_sm_trips": {
        "file": "ride_hailing_xanh_sm_trips.csv",
        "domain": "trips",
        "title": "GSM Xanh SM Ride Hailing Trips Global",
        "pk": "trip_id",
        "tags": {
            "trip_id": ("identifier", "NON_PERSONAL_REFERENCE", "identifier"),
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "driver_id": ("driver_ref", "LINKABLE_IDENTIFIER", "identifier"),
            "pickup_datetime": ("timestamp", "TECHNICAL_METADATA", "technical_metadata"),
            "dropoff_datetime": ("timestamp", "TECHNICAL_METADATA", "technical_metadata"),
            "assigned_day_index": ("day_index", "TECHNICAL_METADATA", "technical_metadata"),
            "trip_distance_km": ("distance_metric", "NON_PERSONAL_REFERENCE", "distance_metric"),
            "fare_amount": ("fare_amount", "NON_PERSONAL_REFERENCE", "financial"),
            "currency_unverified": ("flag", "TECHNICAL_METADATA", "financial"),
            "tip_amount": ("tip_amount", "NON_PERSONAL_REFERENCE", "financial"),
            "total_fare": ("total_fare", "NON_PERSONAL_REFERENCE", "financial"),
            "pickup_latitude": ("gps_latitude", "CONTEXTUAL_PERSONAL_DATA", "location"),
            "pickup_longitude": ("gps_longitude", "CONTEXTUAL_PERSONAL_DATA", "location"),
            "vehicle_type": ("vehicle_category", "NON_PERSONAL_REFERENCE", "vehicle_technical"),
            "event_sequence_index": ("sequence_index", "TECHNICAL_METADATA", "technical_metadata"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
            "customer_id": ("customer_ref", "LINKABLE_IDENTIFIER", "identifier"),
            "customer_contact": ("phone_number", "DIRECT_IDENTIFIER", "contact"),
        }
    },
    "synthetic_ev_telemetry_ved_ref": {
        "file": "synthetic_ev_telemetry_ved_ref.csv",
        "domain": "telemetry",
        "title": "VinFast EV Battery & Motor Telematics VED",
        "pk": "record_id",
        "tags": {
            "record_id": ("identifier", "NON_PERSONAL_REFERENCE", "identifier"),
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "day_idx": ("day_index", "TECHNICAL_METADATA", "technical_metadata"),
            "sample_idx": ("sample_index", "TECHNICAL_METADATA", "technical_metadata"),
            "timestamp": ("timestamp", "TECHNICAL_METADATA", "technical_metadata"),
            "speed_kmh": ("vehicle_speed", "TECHNICAL_METADATA", "vehicle_technical"),
            "motor_rpm": ("motor_rpm", "TECHNICAL_METADATA", "vehicle_technical"),
            "battery_soc": ("battery_soc", "TECHNICAL_METADATA", "vehicle_technical"),
            "battery_voltage": ("battery_voltage", "TECHNICAL_METADATA", "vehicle_technical"),
            "battery_current": ("battery_current", "TECHNICAL_METADATA", "vehicle_technical"),
            "battery_temp_c": ("battery_temp_c", "TECHNICAL_METADATA", "vehicle_technical"),
            "state_at_sample": ("vehicle_state", "TECHNICAL_METADATA", "vehicle_technical"),
            "assigned_day_index": ("day_index", "TECHNICAL_METADATA", "technical_metadata"),
            "ved_reference_veh_id": ("reference_id", "TECHNICAL_METADATA", "technical_metadata"),
            "synthetic_gap_indicator": ("flag", "TECHNICAL_METADATA", "technical_metadata"),
            "event_sequence_index": ("sequence_index", "TECHNICAL_METADATA", "technical_metadata"),
            "latitude": ("gps_latitude", "CONTEXTUAL_PERSONAL_DATA", "location"),
            "longitude": ("gps_longitude", "CONTEXTUAL_PERSONAL_DATA", "location"),
            "accel_z": ("acceleration_z", "TECHNICAL_METADATA", "vehicle_technical"),
            "telemetry_coverage": ("coverage_status", "TECHNICAL_METADATA", "technical_metadata"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
        }
    },
    "synthetic_feedback_scenario_driven": {
        "file": "synthetic_feedback_scenario_driven.csv",
        "domain": "feedback",
        "title": "Scenario-Driven Synthetic User Feedback",
        "pk": "feedback_id",
        "tags": {
            "feedback_id": ("identifier", "NON_PERSONAL_REFERENCE", "identifier"),
            "vehicle_vin": ("vehicle_vin", "LINKABLE_IDENTIFIER", "identifier"),
            "scenario_date": ("date", "TECHNICAL_METADATA", "technical_metadata"),
            "assigned_day_index": ("day_index", "TECHNICAL_METADATA", "technical_metadata"),
            "topic": ("feedback_topic", "NON_PERSONAL_REFERENCE", "content_feedback"),
            "sentiment": ("feedback_sentiment", "NON_PERSONAL_REFERENCE", "content_feedback"),
            "raw_comment_text": ("free_text_comment", "AMBIGUOUS_UNSTRUCTURED_DATA", "content_feedback"),
            "subject_zone": ("regulatory_jurisdiction", "NON_PERSONAL_REFERENCE", "location"),
        }
    }
}


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    
    # Try container internal host first, then localhost fallback
    hosts = ["postgres", "localhost", "127.0.0.1"]
    for h in hosts:
        try:
            return psycopg2.connect(
                host=h,
                port=5432,
                user="airflow",
                password="airflow",
                dbname="airflow",
                connect_timeout=3
            )
        except Exception:
            continue
    raise ConnectionError("Could not connect to PostgreSQL on any known host.")


def resolve_data_dir() -> Path:
    candidates = [
        Path("/opt/airflow/data/vingroup_pii_faulty_testset_3zone"),
        Path("data/vingroup_pii_faulty_testset_3zone"),
        Path("../data/vingroup_pii_faulty_testset_3zone"),
        Path("E:/Phase2_VSF/data/vingroup_pii_faulty_testset_3zone"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Could not find data/vingroup_pii_faulty_testset_3zone directory.")


def execute_schema_ddl(conn):
    """Executes schema_bronze_and_catalog.sql if tables are missing."""
    ddl_candidates = [
        Path("/opt/airflow/database/schema_bronze_and_catalog.sql"),
        Path("database/schema_bronze_and_catalog.sql"),
        Path("../database/schema_bronze_and_catalog.sql"),
        Path("E:/Phase2_VSF/database/schema_bronze_and_catalog.sql"),
    ]
    ddl_path = next((p for p in ddl_candidates if p.exists()), None)
    if not ddl_path:
        print("[!] Warning: DDL file not found, assuming tables exist.")
        return

    print(f"Applying Schema DDL from {ddl_path}...")
    with open(ddl_path, "r", encoding="utf-8") as f:
        ddl_sql = f.read()
    
    with conn.cursor() as cur:
        cur.execute(ddl_sql)
    conn.commit()
    print("Schema DDL applied successfully.")


def truncate_and_ingest_all(conn, data_dir: Path, batch_id: str = None) -> dict:
    batch_id = batch_id or f"batch_{uuid.uuid4().hex[:8]}"
    summary = {}

    with conn.cursor() as cur:
        for tbl_name, meta in DATASET_METADATA.items():
            csv_path = data_dir / meta["file"]
            if not csv_path.exists():
                print(f"[!] Warning: File {csv_path} not found, skipping.")
                continue

            # 1. Truncate target bronze table
            full_table = f"bronze.{tbl_name}"
            cur.execute(f"TRUNCATE TABLE {full_table};")

            # 2. Read CSV & prepare records
            df = pd.read_csv(csv_path)
            # Replace NaN with None for clean SQL NULLs
            df = df.where(pd.notnull(df), None)

            cols = list(df.columns)
            # Insert technical audit columns
            insert_cols = ["_batch_id"] + cols
            col_names_str = ", ".join(insert_cols)
            placeholders = ", ".join(["%s"] * len(insert_cols))
            insert_sql = f"INSERT INTO {full_table} ({col_names_str}) VALUES ({placeholders});"

            rows_to_insert = []
            for _, r in df.iterrows():
                vals = [batch_id] + [r[c] for c in cols]
                rows_to_insert.append(vals)

            # Bulk insert in batches of 5000
            batch_size = 5000
            for i in range(0, len(rows_to_insert), batch_size):
                chunk = rows_to_insert[i:i + batch_size]
                cur.executemany(insert_sql, chunk)

            row_count = len(rows_to_insert)
            col_count = len(cols)
            summary[tbl_name] = row_count
            print(f"  [+] Ingested {row_count:>5} rows -> {full_table}")

            # 3. Update catalog.datasets
            cur.execute("""
                INSERT INTO catalog.datasets (dataset_id, table_name, source_file, domain, row_count, column_count, description, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id) DO UPDATE SET
                    row_count = EXCLUDED.row_count,
                    column_count = EXCLUDED.column_count,
                    updated_at = EXCLUDED.updated_at;
            """, (
                tbl_name,
                full_table,
                meta["file"],
                meta["domain"],
                row_count,
                col_count,
                meta["title"],
                datetime.now(timezone.utc)
            ))

            # 4. Update catalog.columns
            # Clear old column entries for this dataset
            cur.execute("DELETE FROM catalog.columns WHERE dataset_id = %s;", (tbl_name,))
            col_inserts = []
            for idx, col_name in enumerate(cols, start=1):
                col_tag_info = meta["tags"].get(col_name, ("unspecified", "NON_PERSONAL_REFERENCE", "general"))
                semantic_tag, pii_role, data_cat = col_tag_info
                is_pk = (col_name == meta.get("pk"))
                is_personal = (pii_role in ("DIRECT_IDENTIFIER", "LINKABLE_IDENTIFIER", "CONTEXTUAL_PERSONAL_DATA", "AMBIGUOUS_UNSTRUCTURED_DATA"))
                inferred_type = str(df[col_name].dtype)
                
                col_inserts.append((
                    str(uuid.uuid4()),
                    tbl_name,
                    col_name,
                    inferred_type,
                    idx,
                    is_pk,
                    True, # is_nullable
                    is_personal,
                    pii_role,
                    semantic_tag,
                    data_cat
                ))

            if col_inserts:
                execute_values(cur, """
                    INSERT INTO catalog.columns (
                        column_id, dataset_id, column_name, data_type, ordinal_position,
                        is_primary_key, is_nullable, is_personal_data, pii_role,
                        semantic_tag, data_category
                    ) VALUES %s;
                """, col_inserts)

        conn.commit()
    return summary


def run_task_1():
    print("=" * 70)
    print("DataTrust OS: Airflow Task 1 - Truncate & Ingest Bronze + Catalog")
    print("=" * 70)
    data_dir = resolve_data_dir()
    print(f"Data Source Directory: {data_dir}")

    conn = get_db_connection()
    try:
        summary = truncate_and_ingest_all(conn, data_dir)
        total_rows = sum(summary.values())
        print("=" * 70)
        print(f"Task 1 Complete: Ingested {len(summary)} datasets, Total {total_rows:,} records into schema bronze.")
        print("Data Catalog successfully updated with all dataset & column metadata.")
        print("=" * 70)
        return summary
    finally:
        conn.close()


if __name__ == "__main__":
    run_task_1()
