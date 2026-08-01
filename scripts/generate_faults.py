#!/usr/bin/env python3
"""
Generate Dirty Vietnam Trips Dataset with Controlled Fault Injection.

This script reads the clean synthetic dataset from data/synthetic/vietnam_trips.parquet,
injects controlled faults of various types at specified rates, and saves both the dirty dataset
to data/synthetic/vietnam_trips_dirty.parquet and the fault manifest to data/synthetic/fault_manifest.json.
"""

import json
import os
import sys
import numpy as np
import pandas as pd

# Define paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "synthetic")
INPUT_FILE = os.path.join(DATA_DIR, "vietnam_trips.parquet")
OUTPUT_FILE = os.path.join(DATA_DIR, "vietnam_trips_dirty.parquet")
MANIFEST_FILE = os.path.join(DATA_DIR, "fault_manifest.json")


def main():
    # 1. Check if input synthetic data exists
    if not os.path.exists(INPUT_FILE):
        print(
            f"Error: Clean synthetic dataset file '{INPUT_FILE}' does not exist.\n"
            "Please generate the clean synthetic dataset 'data/synthetic/vietnam_trips.parquet' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading clean synthetic dataset from: {INPUT_FILE}")
    df = pd.read_parquet(INPUT_FILE)
    n_rows = len(df)
    print(f"Loaded dataset with {n_rows} rows.")

    # 2. Initialize dirty copy and RNG seed
    np.random.seed(42)
    df_dirty = df.copy()
    manifest = []

    # Helper function to sample row indices
    def sample_indices(rate: float, population_size: int = n_rows) -> list:
        count = max(1, int(np.round(population_size * rate)))
        indices = np.random.choice(population_size, size=count, replace=False)
        return sorted([int(x) for x in indices])

    # Helper for column lookup with fallback
    def get_col(preferred: str, fallbacks: list) -> str:
        if preferred in df_dirty.columns:
            return preferred
        for fb in fallbacks:
            if fb in df_dirty.columns:
                return fb
        return preferred

    # Identify column names
    col_final_fare = get_col("final_fare", ["fare_amount", "fare"])
    col_surge = get_col("surge_multiplier", ["surge", "multiplier"])
    col_driver = get_col("driver_token", ["driver_id", "driver_uuid"])
    col_pickup_at = get_col("pickup_at", ["pickup_datetime", "pickup_time"])
    col_requested_at = get_col("requested_at", ["request_datetime", "request_time"])
    col_pickup_lat = get_col("pickup_latitude", ["pickup_lat", "lat_pickup"])
    col_pickup_lon = get_col("pickup_longitude", ["pickup_lon", "lng_pickup"])
    col_city = get_col("service_city", ["city", "location_city"])
    col_status = get_col("booking_status", ["status", "trip_status"])
    col_dropoff_at = get_col("dropoff_at", ["dropoff_datetime", "dropoff_time"])
    col_privacy = get_col(
        "cancellation_reason", ["pickup_address", "dropoff_address", "notes", "customer_notes"]
    )
    col_vehicle = get_col("vehicle_type", ["car_type", "vehicle_category"])

    print("\nInjecting controlled faults into dataset...")

    # --- 1. type_error (5%) ---
    indices_type = sample_indices(0.05)
    string_fares = ["150k", "250k đ", "180k", "300k đ", "500k đ"]
    # Convert final_fare to object dtype for dirty dataframe
    df_dirty["final_fare"] = df_dirty["final_fare"].astype(object)
    for i, idx in enumerate(indices_type):
        df_dirty.at[idx, "final_fare"] = string_fares[i % len(string_fares)]
    manifest.append({
        "fault_type": "type_error",
        "row_indices": indices_type,
        "column": "final_fare",
        "description": "String value in numeric column"
    })

    # --- 2. range_error (3%) ---
    indices_range = sample_indices(0.03)
    neg_surges = [-2.0, -1.5, -2.5]
    for i, idx in enumerate(indices_range):
        df_dirty.at[idx, "surge_multiplier"] = neg_surges[i % len(neg_surges)]
    manifest.append({
        "fault_type": "range_error",
        "row_indices": indices_range,
        "column": "surge_multiplier",
        "description": "Set surge_multiplier to negative (-2, -1.5)"
    })

    # --- 3. referential_error (2%) ---
    indices_ref = sample_indices(0.02)
    invalid_drivers = ["DRV_NONEXISTENT_9999", "DRV_INVALID_8888", "UNKNOWN_DRIVER_X"]
    for i, idx in enumerate(indices_ref):
        df_dirty.at[idx, "driver_token"] = invalid_drivers[i % len(invalid_drivers)]
    manifest.append({
        "fault_type": "referential_error",
        "row_indices": indices_ref,
        "column": "driver_token",
        "description": "Set driver_token to non-existent values"
    })

    # --- 4. temporal_error (5%) ---
    indices_temp = sample_indices(0.05)
    for idx in indices_temp:
        p_val = df_dirty.at[idx, "pickup_at"]
        r_val = df_dirty.at[idx, "requested_at"]
        df_dirty.at[idx, "pickup_at"] = r_val
        df_dirty.at[idx, "requested_at"] = p_val
    manifest.append({
        "fault_type": "temporal_error",
        "row_indices": indices_temp,
        "column": "pickup_at",
        "description": "Swap pickup_at and requested_at so pickup < request"
    })

    # --- 5. geographic_error (3%) ---
    indices_geo = sample_indices(0.03)
    for idx in indices_geo:
        df_dirty.at[idx, "pickup_latitude"] = float(21.0285 + np.random.uniform(-0.01, 0.01))
        df_dirty.at[idx, "pickup_longitude"] = float(105.8542 + np.random.uniform(-0.01, 0.01))
        df_dirty.at[idx, "service_city"] = "Ho Chi Minh City"
    manifest.append({
        "fault_type": "geographic_error",
        "row_indices": indices_geo,
        "column": "pickup_latitude",
        "description": "Set pickup coords to Hanoi but keep service_city as 'Ho Chi Minh City'"
    })

    # --- 6. financial_error (5%) ---
    indices_fin = sample_indices(0.05)
    for idx in indices_fin:
        df_dirty.at[idx, "final_fare"] = 999999.0
    manifest.append({
        "fault_type": "financial_error",
        "row_indices": indices_fin,
        "column": "final_fare",
        "description": "Corrupt final_fare so it doesn't match base+distance+time formula"
    })

    # --- 7. business_error (3%) ---
    indices_biz = sample_indices(0.03)
    for idx in indices_biz:
        df_dirty.at[idx, "booking_status"] = "completed"
        df_dirty.at[idx, "dropoff_at"] = pd.NaT
    manifest.append({
        "fault_type": "business_error",
        "row_indices": indices_biz,
        "column": "dropoff_at",
        "description": "Set booking_status to 'completed' but null out dropoff_at"
    })

    # --- 8. privacy_error (1%) ---
    indices_priv = sample_indices(0.01)
    df_dirty["cancellation_reason"] = df_dirty["cancellation_reason"].astype(object)
    for idx in indices_priv:
        df_dirty.at[idx, "cancellation_reason"] = "Customer phone number: 0901234567"
    manifest.append({
        "fault_type": "privacy_error",
        "row_indices": indices_priv,
        "column": "cancellation_reason",
        "description": "Inject phone number '0901234567' into address-like fields or cancellation_reason"
    })

    # --- 9. distribution_shift (1 batch) ---
    num_last = min(1000, n_rows)
    start_idx = n_rows - num_last
    last_indices = list(range(start_idx, n_rows))
    count_shift = int(np.round(num_last * 0.95))
    indices_shift = sorted([int(x) for x in np.random.choice(last_indices, size=count_shift, replace=False)])
    
    for idx in indices_shift:
        df_dirty.at[idx, "vehicle_type"] = "car_7seat"
    manifest.append({
        "fault_type": "distribution_shift",
        "row_indices": indices_shift,
        "column": "vehicle_type",
        "description": "In last 1000 rows, change 95% of vehicle_type to 'car_7seat'"
    })

    # Convert final_fare column to string type so pyarrow can serialize the dirty dataset cleanly
    df_dirty["final_fare"] = df_dirty["final_fare"].astype(str)

    # 4. Save dirty dataset
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df_dirty.to_parquet(OUTPUT_FILE, index=False)
    print(f"\nSaved dirty dataset to: {OUTPUT_FILE}")

    # 5. Save fault manifest
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved fault manifest to: {MANIFEST_FILE}")

    # 6. Print summary of injected faults
    print("\n=================== FAULT INJECTION SUMMARY ===================")
    for entry in manifest:
        f_type = entry["fault_type"]
        col = entry["column"]
        count = len(entry["row_indices"])
        pct = (count / n_rows) * 100
        print(f" - {f_type:<20} | Column: {col:<20} | Injected: {count:>5} rows ({pct:.2f}%)")
    print("===============================================================")


if __name__ == "__main__":
    main()
