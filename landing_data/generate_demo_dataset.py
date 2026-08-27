"""
data_demo/generate_demo_dataset.py

Isolated script to generate demo dataset and fault manifest for system demonstration.
- Reads clean ground truth CSVs from data_new/vingroup_pilot_dataset/
- Applies exactly 14 controlled fault injections (L1-L4) distributed across Days 0..14.
- Days 0-9: Clean warmup baseline (2 simple L1 faults).
- Days 10-14: 12 targeted L1, L2, L3, L4 faults for daily step demonstration.
- Generates:
    - data_demo/vingroup_pilot_landing_demo.parquet
    - data_demo/fault_manifest.json
- Strictly isolated inside data_demo/ directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import duckdb

# Path setup
BASE_DIR = Path(r"c:\Users\ngant\P-086")
SRC_DIR = BASE_DIR / "data_new" / "vingroup_pilot_dataset"
DATA_DEMO_DIR = BASE_DIR / "data_demo"
OUT_PARQUET = DATA_DEMO_DIR / "vingroup_pilot_landing_demo.parquet"
OUT_MANIFEST = DATA_DEMO_DIR / "fault_manifest.json"

DATA_DEMO_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 2026
rng = np.random.default_rng(RANDOM_SEED)

CSV_MAPPING = {
    "synthetic_ev_telemetry_ved_ref.csv": "ev_telemetry",
    "ride_hailing_xanh_sm_trips.csv": "ride_trips",
    "acn_charging_mapped.csv": "acn_charging",
    "fleet_index.csv": "fleet_index",
    "nlp_benchmark_uit_vsfc.csv": "lp_benchmark",
}

def load_ground_truth_datasets() -> dict[str, pd.DataFrame]:
    """Load clean ground truth datasets from data_new/vingroup_pilot_dataset."""
    dfs = {}
    for csv_file, table_name in CSV_MAPPING.items():
        csv_path = SRC_DIR / csv_file
        if csv_path.exists():
            print(f"Loading ground truth {csv_file} -> table '{table_name}'...")
            dfs[table_name] = pd.read_csv(csv_path)
        else:
            print(f"WARNING: {csv_file} not found in {SRC_DIR}")
    
    # Generate synthetic feedback scenario data if missing
    if "fleet_index" in dfs:
        fleet_vins = dfs["fleet_index"]["vehicle_vin"].dropna().unique().tolist()
        dfs["feedback"] = generate_demo_feedback(fleet_vins)
        
    return dfs

def generate_demo_feedback(fleet_vins: list[str], days: int = 15) -> pd.DataFrame:
    """Generate clean synthetic feedback scenario dataset for demo."""
    rows = []
    base_date = datetime(2026, 1, 1)
    topics = ["vehicle", "charging", "app", "driver"]
    comments = {
        "vehicle": ["Xe chạy êm mượt", "Điều hòa hoạt động tốt", "Màn hình điều khiển nhạy"],
        "charging": ["Sạc nhanh 40 phút đầy", "Trạm sạc sạch sẽ", "Cáp sạc chắc chắn"],
        "app": ["App dễ sử dụng", "Đặt xe nhanh chóng", "Bản đồ định vị chính xác"],
        "driver": ["Tài xế lịch sự", "Lái xe an toàn", "Phục vụ chu đáo"]
    }
    
    for i in range(100):
        vin = rng.choice(fleet_vins)
        day_idx = int(i % days)
        topic = rng.choice(topics)
        text = rng.choice(comments[topic])
        rows.append({
            "feedback_id": f"FB_DEMO_{i+1:04d}",
            "vehicle_vin": vin,
            "scenario_date": (base_date + timedelta(days=day_idx)).strftime("%Y-%m-%d"),
            "assigned_day_index": day_idx,
            "topic": topic,
            "sentiment": 2, # Positive
            "raw_comment_text": text
        })
    return pd.DataFrame(rows)

def inject_demo_incidents(dfs: dict[str, pd.DataFrame]) -> list[dict]:
    """Inject 14 controlled L1-L4 incidents into datasets and return fault manifest."""
    manifest = []
    
    # helper for day index retrieval/normalization
    def get_day_mask(df: pd.DataFrame, day_idx: int) -> pd.Series:
        if "assigned_day_index" in df.columns:
            return df["assigned_day_index"] == day_idx
        elif "day_idx" in df.columns:
            return df["day_idx"] == day_idx
        return pd.Series([False] * len(df))

    # Helper to add manifest item
    def record_fault(incident_id: str, day_idx: int, level: str, fault_family: str,
                     dataset_table: str, row_index: int, column: str, description: str,
                     expected_rule: str, **kwargs):
        entry = {
            "incident_id": incident_id,
            "day_idx": day_idx,
            "layer": level,
            "fault_family": fault_family,
            "dataset_table": dataset_table,
            "row_index": int(row_index),
            "column": column,
            "description": description,
            "expected_rule": expected_rule
        }
        entry.update(kwargs)
        manifest.append(entry)

    # -------------------------------------------------------------------------
    # WARMUP PHASE (Days 0 - 8) - 100% Clean Baseline
    # FAULTS START FROM DAY 9 TO DAY 14
    # -------------------------------------------------------------------------
    
    # Fault 1: Day 9 - L1 Negative SOC in ev_telemetry
    df_ev = dfs["ev_telemetry"]
    mask_day9 = get_day_mask(df_ev, 9)
    if mask_day9.any():
        idx = df_ev.index[mask_day9][10]
        original_val = df_ev.at[idx, "battery_soc"]
        df_ev.at[idx, "battery_soc"] = -12.5
        record_fault(
            "INC_001", 9, "L1", "F1_Negative_SOC", "ev_telemetry", idx, "battery_soc",
            f"BMS sensor glitch: battery_soc set to -12.5% (was {original_val}%)",
            "Rule_L1_Range_SOC_Negative"
        )

    # Fault 2: Day 9 - L1 Negative Cost in acn_charging
    df_chg = dfs["acn_charging"]
    mask_day9_chg = get_day_mask(df_chg, 9)
    if mask_day9_chg.any():
        idx = df_chg.index[mask_day9_chg][5]
        original_val = df_chg.at[idx, "cost_vnd"]
        df_chg.at[idx, "cost_vnd"] = -150000.0
        record_fault(
            "INC_002", 9, "L1", "F5_Negative_Cost", "acn_charging", idx, "cost_vnd",
            f"Billing anomaly: cost_vnd set to -150,000 VND (was {original_val})",
            "Rule_L1_Range_Cost_Negative"
        )

    # -------------------------------------------------------------------------
    # DAILY STEP DEMO PHASE (Days 10 - 14)
    # -------------------------------------------------------------------------

    # --- DAY 10 ---
    # Fault 3: Day 10 - L1 Overvoltage Spike in ev_telemetry
    mask_day10_ev = get_day_mask(df_ev, 10)
    if mask_day10_ev.any():
        idx = df_ev.index[mask_day10_ev][15]
        df_ev.at[idx, "battery_voltage"] = 1850.0
        record_fault(
            "INC_003", 10, "L1", "F2_Voltage_Overvoltage_Spike", "ev_telemetry", idx, "battery_voltage",
            "CAN-bus bus spike: battery_voltage = 1850.0V (threshold: 1000V)",
            "Rule_L1_Range_Voltage_Overvoltage"
        )

    # Fault 4: Day 10 - L1 Negative Fare in ride_trips
    df_trips = dfs["ride_trips"]
    mask_day10_trips = get_day_mask(df_trips, 10)
    if mask_day10_trips.any():
        idx = df_trips.index[mask_day10_trips][8]
        df_trips.at[idx, "fare_amount"] = -55000.0
        df_trips.at[idx, "total_fare"] = -55000.0
        record_fault(
            "INC_004", 10, "L1", "F7_Negative_Fare", "ride_trips", idx, "fare_amount",
            "Ledger calculation error: fare_amount = -55,000 VND",
            "Rule_L1_Range_Fare_Negative"
        )

    # --- DAY 11 ---
    # Fault 5: Day 11 - L1 Ledger Mismatch in ride_trips
    mask_day11_trips = get_day_mask(df_trips, 11)
    if mask_day11_trips.any():
        idx = df_trips.index[mask_day11_trips][12]
        fare = float(df_trips.at[idx, "fare_amount"])
        tip = float(df_trips.at[idx, "tip_amount"])
        df_trips.at[idx, "total_fare"] = fare + tip + 120000.0
        record_fault(
            "INC_005", 11, "L1", "F8_Ledger_Mismatch", "ride_trips", idx, "total_fare",
            f"Arithmetic mismatch: total_fare ({df_trips.at[idx, 'total_fare']}) != fare ({fare}) + tip ({tip})",
            "Rule_L1_Arithmetic_TotalFare_Mismatch"
        )

    # Fault 6: Day 11 - L2 Battery Temp Drift in ev_telemetry
    vins = df_ev["vehicle_vin"].dropna().unique()
    target_vin_temp = vins[0] if len(vins) > 0 else "VIN_VF8_DEMO"
    mask_vin_temp = (df_ev["vehicle_vin"] == target_vin_temp) & (get_day_mask(df_ev, 11))
    if mask_vin_temp.any():
        for idx in df_ev.index[mask_vin_temp]:
            val = float(df_ev.at[idx, "battery_temp_c"])
            df_ev.at[idx, "battery_temp_c"] = round(val + 18.5, 2)
        first_idx = df_ev.index[mask_vin_temp][0]
        record_fault(
            "INC_006", 11, "L2", "F11_BatteryTemp_Drift", "ev_telemetry", first_idx, "battery_temp_c",
            f"Thermal drift: vehicle {target_vin_temp} battery temp elevated by +18.5°C above 10-day baseline",
            "Rule_L2_Contextual_BatteryTemp_Drift", entity_id=target_vin_temp
        )

    # --- DAY 12 ---
    # Fault 7: Day 12 - L2 SOC Degradation Drift in ev_telemetry
    target_vin_soc = vins[1] if len(vins) > 1 else "VIN_VF9_DEMO"
    mask_vin_soc = (df_ev["vehicle_vin"] == target_vin_soc) & (get_day_mask(df_ev, 12))
    if mask_vin_soc.any():
        for idx in df_ev.index[mask_vin_soc]:
            val = float(df_ev.at[idx, "battery_soc"])
            df_ev.at[idx, "battery_soc"] = round(max(0.0, val * 0.45), 2)
        first_idx = df_ev.index[mask_vin_soc][0]
        record_fault(
            "INC_007", 12, "L2", "F10_SOC_Degradation_Drift", "ev_telemetry", first_idx, "battery_soc",
            f"Rapid SOC discharge drift: vehicle {target_vin_soc} SOC dropped 55% faster than baseline",
            "Rule_L2_Contextual_SOC_Degradation", entity_id=target_vin_soc
        )

    # Fault 8: Day 12 - L3 Duration / Energy Mismatch in acn_charging
    mask_day12_chg = get_day_mask(df_chg, 12)
    if mask_day12_chg.any():
        idx = df_chg.index[mask_day12_chg][3]
        df_chg.at[idx, "duration_mins"] = 240.0
        df_chg.at[idx, "kwh_consumed"] = 1.2
        df_chg.at[idx, "power_kw"] = 0.3
        record_fault(
            "INC_008", 12, "L3", "F14_DurationEnergy_Mismatch", "acn_charging", idx, "duration_mins",
            "Relational break: charging duration 240 mins but energy consumed only 1.2 kWh",
            "Rule_L3_Relational_Duration_Energy_Mismatch"
        )

    # Fault 9: Day 12 - L3 GPS Alleyway Drift (NYC coords) in ride_trips
    mask_day12_trips = get_day_mask(df_trips, 12)
    if mask_day12_trips.any():
        idx = df_trips.index[mask_day12_trips][7]
        df_trips.at[idx, "pickup_latitude"] = 40.7128
        df_trips.at[idx, "pickup_longitude"] = -74.0060
        record_fault(
            "INC_009", 12, "L3", "F6_GPS_Alleyway_Drift", "ride_trips", idx, "pickup_latitude",
            "Multivariate spatial anomaly: pickup coordinates (40.7128, -74.0060) outside Hanoi bounding box",
            "Rule_L3_Spatial_Bounding_Box_Violation"
        )

    # --- DAY 13 ---
    # Fault 10: Day 13 - L3 Charging / Trip Mismatch across tables
    target_vin_mismatch = vins[2] if len(vins) > 2 else "VIN_VFE34_DEMO"
    mask_day13_chg = (df_chg["vehicle_vin"] == target_vin_mismatch) & (get_day_mask(df_chg, 13))
    if not mask_day13_chg.any():
        # Duplicate 4 charging sessions for this VIN on day 13
        sample_row = df_chg.iloc[0].copy()
        sample_row["vehicle_vin"] = target_vin_mismatch
        sample_row["assigned_day_index"] = 13
        sample_row["session_id"] = "SESS_DEMO_DUP_01"
        df_chg = pd.concat([df_chg, pd.DataFrame([sample_row]*4)], ignore_index=True)
        dfs["acn_charging"] = df_chg
        first_idx = len(df_chg) - 4
    else:
        first_idx = df_chg.index[mask_day13_chg][0]

    record_fault(
        "INC_010", 13, "L3", "F13_ChargingTrip_Mismatch", "acn_charging", first_idx, "vehicle_vin",
        f"Cross-table mismatch: vehicle {target_vin_mismatch} has 5 charging sessions on Day 13 but 0 completed trips",
        "Rule_L3_CrossTable_Charging_Trip_Anomaly", entity_id=target_vin_mismatch
    )

    # Fault 11: Day 13 - L4 Charging Frequency Shift in acn_charging
    target_vin_shift = vins[3] if len(vins) > 3 else "VIN_VF8_SHIFT"
    # Append extra charging sessions for Day 13 & 14 for this VIN
    shift_rows = []
    base_sess = df_chg.iloc[0].copy()
    for d in [13, 14]:
        for s in range(4):
            r = base_sess.copy()
            r["vehicle_vin"] = target_vin_shift
            r["assigned_day_index"] = d
            r["session_id"] = f"SESS_SHIFT_{d}_{s}"
            shift_rows.append(r)
    df_chg = pd.concat([df_chg, pd.DataFrame(shift_rows)], ignore_index=True)
    dfs["acn_charging"] = df_chg
    shift_idx = len(df_chg) - len(shift_rows)
    record_fault(
        "INC_011", 13, "L4", "F15_ChargingFrequency_Shift", "acn_charging", shift_idx, "session_id",
        f"Sequential changepoint: vehicle {target_vin_shift} charging frequency jumped from 1/day to 4/day starting Day 13",
        "Rule_L4_Changepoint_Charging_Frequency", entity_id=target_vin_shift
    )

    # --- DAY 14 ---
    # Fault 12: Day 14 - L4 Fare / Distance Distribution Regime Shift in ride_trips
    drivers = df_trips["driver_id"].dropna().unique()
    target_driver = drivers[0] if len(drivers) > 0 else "DRV_042"
    mask_driver = (df_trips["driver_id"] == target_driver) & (get_day_mask(df_trips, 14))
    if mask_driver.any():
        for idx in df_trips.index[mask_driver]:
            val = float(df_trips.at[idx, "trip_distance_km"])
            df_trips.at[idx, "trip_distance_km"] = round(val * 1.65, 2)
        first_idx = df_trips.index[mask_driver][0]
        record_fault(
            "INC_012", 14, "L4", "F16_FareDistribution_Regime", "ride_trips", first_idx, "trip_distance_km",
            f"Distribution regime shift: driver {target_driver} mean trip distance shifted +65% on Day 14",
            "Rule_L4_Regime_Shift_Driver_Distance", entity_id=target_driver
        )

    # Fault 13: Day 14 - L1 RPM / Speed Mismatch in ev_telemetry
    mask_day14_ev = get_day_mask(df_ev, 14)
    if mask_day14_ev.any():
        idx = df_ev.index[mask_day14_ev][5]
        df_ev.at[idx, "speed_kmh"] = 0.0
        df_ev.at[idx, "motor_rpm"] = 13500
        record_fault(
            "INC_013", 14, "L1", "F3_RPM_Speed_Mismatch", "ev_telemetry", idx, "motor_rpm",
            "Rule violation: vehicle speed = 0 km/h but motor RPM = 13,500 RPM",
            "Rule_L1_Logic_RPM_Speed_Mismatch"
        )

    # Fault 14: Day 14 - L4 Cross-Table Foreign Key Orphan in acn_charging
    orphan_row = df_chg.iloc[0].copy()
    orphan_row["vehicle_vin"] = "VIN_UNKNOWN_999_ORPHAN"
    orphan_row["assigned_day_index"] = 14
    orphan_row["session_id"] = "SESS_ORPHAN_999"
    df_chg = pd.concat([df_chg, pd.DataFrame([orphan_row])], ignore_index=True)
    dfs["acn_charging"] = df_chg
    orphan_idx = len(df_chg) - 1
    record_fault(
        "INC_014", 14, "L4", "F17_ForeignKey_Orphan", "acn_charging", orphan_idx, "vehicle_vin",
        "Referential integrity failure: VIN 'VIN_UNKNOWN_999_ORPHAN' in charging sessions does not exist in fleet_index",
        "Rule_L4_Relational_FK_Orphan_Check", entity_id="VIN_UNKNOWN_999_ORPHAN"
    )

    return manifest


def combine_and_write_parquet(dfs: dict[str, pd.DataFrame]):
    """Concatenate all table dataframes and write to data_demo/vingroup_pilot_landing_demo.parquet."""
    print("\nConcatenating tables into unified landing parquet...")
    processed_dfs = []
    
    for table_name, df in dfs.items():
        df = df.copy()
        df["dataset_table"] = table_name
        
        # Normalize day_idx
        if "day_idx" in df.columns:
            df["day_idx"] = df["day_idx"].astype("Int64")
        elif "assigned_day_index" in df.columns:
            df["day_idx"] = df["assigned_day_index"].astype("Int64")
        else:
            df["day_idx"] = pd.array([None] * len(df), dtype=pd.Int64Dtype())
            
        processed_dfs.append(df)
        print(f"  + Table '{table_name}': {len(df):,} rows, {len(df.columns)} columns")
        
    combined = pd.concat(processed_dfs, ignore_index=True, sort=False)
    print(f"\nTotal combined rows: {len(combined):,}, columns: {len(combined.columns)}")
    
    print(f"Writing parquet to {OUT_PARQUET} via DuckDB...")
    conn = duckdb.connect()
    conn.execute(f"COPY combined TO '{OUT_PARQUET}' (FORMAT PARQUET, COMPRESSION 'ZSTD');")
    conn.close()
    size_mb = os.path.getsize(OUT_PARQUET) / (1024 * 1024)
    print(f"Parquet generated successfully! Size: {size_mb:.2f} MB")


def main():
    print("=" * 70)
    print("DEMO DATASET GENERATOR - ISOLATED IN data_demo/")
    print("=" * 70)
    
    # 1. Load clean datasets
    dfs = load_ground_truth_datasets()
    
    # 2. Inject controlled demo incidents
    print("\nInjecting 14 controlled L1-L4 demo incidents...")
    manifest_entries = inject_demo_incidents(dfs)
    
    # 3. Save fault manifest
    manifest_data = {
        "generated_at": datetime.now().isoformat(),
        "random_seed": RANDOM_SEED,
        "dataset_name": "vingroup_pilot_landing_demo.parquet",
        "total_days": 15,
        "warmup_days": 10,
        "daily_step_days": 5,
        "total_incidents": len(manifest_entries),
        "fault_summary_by_layer": {
            "L1": len([m for m in manifest_entries if m["layer"] == "L1"]),
            "L2": len([m for m in manifest_entries if m["layer"] == "L2"]),
            "L3": len([m for m in manifest_entries if m["layer"] == "L3"]),
            "L4": len([m for m in manifest_entries if m["layer"] == "L4"]),
        },
        "incidents": manifest_entries
    }
    
    print(f"Saving fault manifest to {OUT_MANIFEST}...")
    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(manifest_entries)} incidents to manifest!")

    # 4. Write final combined Parquet
    combine_and_write_parquet(dfs)
    
    print("\n" + "=" * 70)
    print("DEMO GENERATION COMPLETE!")
    print(f"Parquet:  {OUT_PARQUET}")
    print(f"Manifest: {OUT_MANIFEST}")
    print("=" * 70)


if __name__ == "__main__":
    main()
