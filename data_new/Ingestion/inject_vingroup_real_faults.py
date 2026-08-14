"""
inject_vingroup_real_faults.py

Layer 3 — Fault Injection cho data_new/vingroup_pilot_dataset.

Hoạt động trên COPY, không chỉnh sửa ground truth trong data_new/vingroup_pilot_dataset.

16 Fault Families theo L1-L4 + NLP (từ .plan/tom-tat-phan-tich-DATA-02.md):

L1 — Point/Rule (5):  baseline rule-level, dbt-style
  F1  Negative_SOC                battery_soc < 0
  F2  Voltage_Overvoltage_Spike   battery_voltage > 1000V
  F5  Negative_Cost               cost_vnd < 0
  F7  Negative_Fare               fare_amount < 0
  F8  Ledger_Mismatch              total_fare != fare + tip (discount = 0)

L2 — Contextual/Univariate (3):  rolling z-score so với baseline 14d của entity
  F10 SOC_Degradation_Drift       SOC discharge rate tăng dần 2 tuần
  F11 BatteryTemp_Drift           battery_temp_c tăng 2σ so với baseline 14d
  F12 TripDuration_Surge          trip_miles của 1 driver tăng đột biến so với baseline 14d

L3 — Relational/Collective (3):  regression residual / IsolationForest
  F3  RPM_Speed_Mismatch          speed=0 + rpm > 12000 (L1-style rule)
  F13 ChargingTrip_Mismatch       sạc nhiều sessions/ngày nhưng trip_count thấp
  F14 DurationEnergy_Mismatch     charging_duration tăng nhưng kwh_consumed flat

L4 — Sequential/Change-point (2):  CUSUM / PELT
  F15 ChargingFrequency_Shift     VIN chuyển từ 'sạc 1 lần/ngày' → 'sạc 3 lần/ngày'
  F16 CostDistribution_Regime     fare_amount của 1 driver shift mean 30% trong 7 ngày (hoặc trip_distance_km +50%)

NLP (1):  tách riêng layer=EXT_NLP
  F9  TeenCode_Text_Corruption     Vietnamese text bị corrupt bằng teen-code

Output:
    data_new/vingroup_faulty_pilot_dataset/*.csv  (copy + injected faults)
    data_new/vingroup_faulty_pilot_dataset/fault_manifest.json  (ground truth)
    data_new/vingroup_faulty_pilot_dataset/synthetic_feedback_scenario_driven.csv
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #

SRC_DIR = Path("../vingroup_pilot_dataset")
DST_DIR = Path("../vingroup_faulty_pilot_dataset")
MANIFEST_PATH = DST_DIR / "fault_manifest.json"

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# Bounding box Hà Nội
HANOI_BBOX = {"lat_min": 20.95, "lat_max": 21.10, "lon_min": 105.75, "lon_max": 105.90}

# Fault injection rates per dataset (giảm để tránh over-inject và dễ eval)
EV_FAULT_RATE = 0.005  # 0.5% -> ~430 rows L1 (vừa đủ test detector)
CHG_FAULT_RATE = 0.025  # dataset nhỏ nên giữ
TRIP_FAULT_RATE = 0.010  # 1% -> ~100 rows L1
NLP_FAULT_RATE = 0.0  # NLP benchmark giữ nguyên (đã có teen-code rồi)

# L2-L4 params (giảm coverage)
L2_N_DRIFTING_ENTITIES = 3  # giảm từ 5
L2_DRIFT_DAYS = 5  # giảm từ 8 (days L4_START_DAY → L4_START_DAY+L2_DRIFT_DAYS-1)

# L4 fault chỉ inject vào nửa sau dataset
L4_START_DAY = 8
L4_END_DAY = 15


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def mark_fault(manifest: list[dict], dataset: str, row_idx, col: str,
               fault_family: str, description: str, **extra):
    entry = {
        "dataset": dataset,
        "original_index": int(row_idx) if not isinstance(row_idx, (list, np.ndarray)) else [int(i) for i in row_idx],
        "column": col,
        "fault_family": fault_family,
        "description": description,
    }
    entry.update(extra)
    manifest.append(entry)


def choose_fault_type(n: int, weights: list[float]) -> np.ndarray:
    """Chọn fault type theo tỷ lệ weights."""
    types = list(range(len(weights)))
    return rng.choice(types, size=n, p=np.array(weights) / sum(weights))


# --------------------------------------------------------------------------- #
# L1 — Point / Rule (5 fault families)
# --------------------------------------------------------------------------- #

def inject_l1_ev_telemetry(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L1 faults trên EV telemetry: F1, F2, F3.

    F1 Negative_SOC:  battery_soc < 0
    F2 Overvoltage:   battery_voltage > 1000V (giả từ 8000V xuống 1000V cho hợp lý)
    F3 RPM_Speed:      speed=0 + rpm > 12000 (L1-style rule)
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * EV_FAULT_RATE)
    if n_fault == 0:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)
    fault_type = choose_fault_type(n_fault, weights=[0.40, 0.30, 0.30])  # F1:F2:F3

    for row_idx, ft in zip(fault_idx, fault_type):
        if ft == 0:
            # F1: Negative SOC
            negative_soc = round(rng.uniform(-15.0, -5.0), 1)
            df.at[row_idx, "battery_soc"] = negative_soc
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "battery_soc",
                "F1_Negative_SOC",
                f"Battery BMS sensor error: negative SOC {negative_soc}%",
                layer="L1", signal_type="RANGE_VIOLATION",
            )
        elif ft == 1:
            # F2: Overvoltage spike
            overvoltage = rng.choice([1500.0, 2000.0, 5000.0])
            df.at[row_idx, "battery_voltage"] = overvoltage
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "battery_voltage",
                "F2_Voltage_Overvoltage_Spike",
                f"CAN-bus spike: unrealistic voltage {overvoltage}V",
                layer="L1", signal_type="RANGE_VIOLATION",
            )
        else:
            # F3: RPM/Speed mismatch (L1-style)
            df.at[row_idx, "speed_kmh"] = 0.0
            rpm_val = int(rng.integers(12000, 15000))
            df.at[row_idx, "motor_rpm"] = rpm_val
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "motor_rpm",
                "F3_RPM_Speed_Mismatch",
                f"Speed=0 km/h but Motor RPM={rpm_val} (L1 rule)",
                layer="L1", signal_type="RANGE_VIOLATION",
            )

    return df, manifest


def inject_l1_charging(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L1 faults trên charging: F5 (negative cost).

    F4 (thermal drop) chuyển sang L3 relational — xem inject_l3_charging().
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * CHG_FAULT_RATE)
    if n_fault == 0:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)

    for row_idx in fault_idx:
        negative_cost = round(rng.uniform(-200000.0, -50000.0), 0)
        df.at[row_idx, "cost_vnd"] = negative_cost
        mark_fault(
            manifest, "acn_charging_mapped", row_idx, "cost_vnd",
            "F5_Negative_Cost",
            f"Billing glitch: negative charging cost {int(negative_cost)} VND",
            layer="L1", signal_type="RANGE_VIOLATION",
        )

    return df, manifest


def inject_l1_trips(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L1 faults trên trips: F7, F8.
    F6 (GPS alleyway drift) chuyển sang L3 spatial bounding — xem inject_l3_trips().
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * TRIP_FAULT_RATE)
    if n_fault == 0:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)
    fault_type = choose_fault_type(n_fault, weights=[0.50, 0.50])  # F7:F8

    for row_idx, ft in zip(fault_idx, fault_type):
        if ft == 0:
            # F7: Negative Fare
            negative_fare = round(rng.uniform(-80000.0, -20000.0), 2)
            df.at[row_idx, "fare_amount"] = negative_fare
            new_total = round(negative_fare + df.at[row_idx, "tip_amount"], 2)
            df.at[row_idx, "total_fare"] = new_total
            mark_fault(
                manifest, "ride_hailing_xanh_sm_trips", row_idx, "fare_amount",
                "F7_Negative_Fare",
                f"Ledger calculation error: negative fare {negative_fare} VND",
                layer="L1", signal_type="RANGE_VIOLATION",
            )
        else:
            # F8: Arithmetic Ledger Mismatch
            adjustment = round(rng.uniform(50000.0, 250000.0), 2)
            current_total = df.at[row_idx, "fare_amount"] + df.at[row_idx, "tip_amount"]
            new_total = round(current_total + adjustment, 2)
            df.at[row_idx, "total_fare"] = new_total
            mark_fault(
                manifest, "ride_hailing_xanh_sm_trips", row_idx, "total_fare",
                "F8_Ledger_Mismatch",
                f"Total fare ({new_total:,.0f}) != fare+tip ({current_total:,.0f}); delta={adjustment:,.0f} VND",
                layer="L1", signal_type="ARITHMETIC_VIOLATION",
            )

    return df, manifest


# --------------------------------------------------------------------------- #
# L2 — Contextual / Univariate (3 fault families)
# --------------------------------------------------------------------------- #

def inject_l2_entity_drift(
    df: pd.DataFrame,
    fault_family: str,
    description_prefix: str,
    metric_col: str,
    entity_col: str,
    time_col: str,
    layer: str,
    n_drifting_entities: int = 5,
    drift_start_day: int = 8,
    end_day: int = 15,
    drift_magnitude_pct: float = 0.30,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Inject L2 contextual drift: chọn N entity, từ drift_start_day trở đi
    tăng/giảm metric theo pct tuyến tính đến drift_magnitude_pct ở end_day.

    Layer=L2 phát hiện được vì robust z-score (median/MAD rolling 14d) của entity
    sẽ vượt ngưỡng khi distribution của entity dịch chuyển.
    """
    manifest = []
    df = df.copy()
    if df.empty or metric_col not in df.columns:
        return df, manifest

    entities = df[entity_col].dropna().unique()
    if len(entities) == 0:
        return df, manifest

    drift_entities = rng.choice(entities, size=min(n_drifting_entities, len(entities)), replace=False)
    drift_direction = rng.choice([-1.0, 1.0])  # giảm hoặc tăng

    for ent in drift_entities:
        ent_mask = df[entity_col] == ent
        ent_df = df[ent_mask]
        if "assigned_day_index" not in ent_df.columns:
            continue

        # baseline = median của entity trong 14 ngày đầu (pre-drift)
        pre = ent_df[ent_df["assigned_day_index"] < drift_start_day]
        if pre.empty:
            continue
        baseline = float(pre[metric_col].median())
        if pd.isna(baseline) or baseline == 0:
            continue

        # Apply drift từ drift_start_day đến end_day
        for day in range(drift_start_day, end_day + 1):
            day_mask = ent_mask & (df["assigned_day_index"] == day)
            if not day_mask.any():
                continue
            # Linear ramp 0 → drift_magnitude_pct
            progress = (day - drift_start_day + 1) / (end_day - drift_start_day + 1)
            drift_pct = drift_direction * drift_magnitude_pct * progress
            multiplier = 1.0 + drift_pct

            affected_idx = df.index[day_mask]
            for idx in affected_idx:
                val = df.at[idx, metric_col]
                if pd.isna(val):
                    continue
                df.at[idx, metric_col] = round(float(val) * multiplier, 4)

        # Record 1 manifest entry per entity (đủ để evaluate)
        sample_idx = ent_df.index[0]
        mark_fault(
            manifest, "synthetic_ev_telemetry_ved_ref", int(sample_idx), metric_col,
            fault_family,
            f"{description_prefix}: entity {ent} drifted {drift_direction*drift_magnitude_pct*100:.1f}% "
            f"from day {drift_start_day} to {end_day} (baseline={baseline:.2f})",
            layer=layer, signal_type="CONTEXTUAL_DRIFT",
            entity_id=str(ent), drift_start_day=drift_start_day,
            drift_end_day=end_day, drift_pct=drift_direction * drift_magnitude_pct,
        )

    return df, manifest


def inject_l2_fleet(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L2 — 2 fault families trên EV telemetry:
      F10 SOC_Degradation_Drift   battery_soc tăng discharge rate
      F11 BatteryTemp_Drift       battery_temp_c tăng
    """
    df_all = df.copy()
    all_manifest = []

    drift_end_day = L4_START_DAY + L2_DRIFT_DAYS - 1  # day 8 → 12

    # F10 SOC drift
    df_all, m1 = inject_l2_entity_drift(
        df_all, fault_family="F10_SOC_Degradation_Drift",
        description_prefix="SOC discharge rate degradation",
        metric_col="battery_soc", entity_col="vehicle_vin",
        time_col="assigned_day_index", layer="L2",
        n_drifting_entities=L2_N_DRIFTING_ENTITIES, drift_start_day=L4_START_DAY,
        end_day=drift_end_day, drift_magnitude_pct=0.30,
    )
    all_manifest.extend(m1)

    # F11 BatteryTemp drift
    df_all, m2 = inject_l2_entity_drift(
        df_all, fault_family="F11_BatteryTemp_Drift",
        description_prefix="Battery temp drift",
        metric_col="battery_temp_c", entity_col="vehicle_vin",
        time_col="assigned_day_index", layer="L2",
        n_drifting_entities=L2_N_DRIFTING_ENTITIES, drift_start_day=L4_START_DAY,
        end_day=drift_end_day, drift_magnitude_pct=0.25,
    )
    all_manifest.extend(m2)

    return df_all, all_manifest


# --------------------------------------------------------------------------- #
# L3 — Relational / Collective (3 fault families)
# --------------------------------------------------------------------------- #

def inject_l3_ev_telemetry(df: pd.DataFrame, l3_fault_rate: float = 0.005) -> tuple[pd.DataFrame, list[dict]]:
    """
    L3 EV: F14 DurationEnergy_Mismatch.

    Inject trên charging: kéo dài duration_mins nhưng giữ kwh_consumed flat
    → power_kw phải giảm (vì kwh = power × time). Nhưng power_kw = kwh / (duration/60)
    nên ta sẽ set kwh_consumed thấp + duration_mins cao → ratio bất thường.
    """
    return df, []  # L3 EV handled in charging


def inject_l3_charging(df: pd.DataFrame, l3_fault_rate: float = 0.01) -> tuple[pd.DataFrame, list[dict]]:
    """
    L3 charging: F14 DurationEnergy_Mismatch.

    Charging duration tăng 2-3× nhưng kwh_consumed flat → power_kw tự tính phải giảm
    → relationship kwh_consumed ~ duration_mins bị break. L3 regression sẽ flag.
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * 0.01)  # 1% rows
    if n_fault == 0:
        return df, manifest

    if "duration_mins" not in df.columns or "kwh_consumed" not in df.columns:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)

    for row_idx in fault_idx:
        original_duration = df.at[row_idx, "duration_mins"]
        original_kwh = df.at[row_idx, "kwh_consumed"]
        if pd.isna(original_duration) or pd.isna(original_kwh) or original_duration <= 0:
            continue

        # Tăng duration 3× nhưng giữ kwh consumption
        new_duration = original_duration * 3.0
        new_kwh = original_kwh * 0.5  # giảm một nửa để tạo mismatch thực sự

        df.at[row_idx, "duration_mins"] = round(new_duration, 2)
        df.at[row_idx, "kwh_consumed"] = round(new_kwh, 2)
        # Recalc power_kw nếu có
        if "power_kw" in df.columns:
            df.at[row_idx, "power_kw"] = round(new_kwh / (new_duration / 60.0), 2)

        mark_fault(
            manifest, "acn_charging_mapped", row_idx, "duration_mins",
            "F14_DurationEnergy_Mismatch",
            f"Duration {original_duration:.1f}→{new_duration:.1f}min but kwh {original_kwh:.1f}→{new_kwh:.1f} "
            f"(expected kwh ratio should follow duration)",
            layer="L3", signal_type="RELATIONAL_BREAK",
        )

    return df, manifest


def inject_l3_trips(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L3 trips: F6 GPS_Alleyway_Drift (relational — coords ngoài bbox).

    Rename: F6 giờ là L3 (multivariate: pickup_lat, pickup_lon cùng lúc drift)
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * TRIP_FAULT_RATE)
    if n_fault == 0:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)

    for row_idx in fault_idx:
        new_lat = round(rng.uniform(40.70, 40.75), 6)  # NYC
        new_lon = round(rng.uniform(-74.02, -73.98), 6)
        df.at[row_idx, "pickup_latitude"] = new_lat
        df.at[row_idx, "pickup_longitude"] = new_lon
        mark_fault(
            manifest, "ride_hailing_xanh_sm_trips", row_idx, "pickup_latitude",
            "F6_GPS_Alleyway_Drift",
            f"GPS drift to NYC ({new_lat:.4f}, {new_lon:.4f}) outside Hanoi bbox",
            layer="L3", signal_type="RELATIONAL_BREAK",
        )

    return df, manifest


def inject_l3_charging_trip_mismatch(
    df_ev: pd.DataFrame, df_chg: pd.DataFrame, df_trip: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict]]:
    """
    L3 cross-table: F13 ChargingTrip_Mismatch.

    Chọn N VIN trong nửa sau dataset. Trong nửa sau này:
      - Tăng số charging sessions của VIN đó 3× so với baseline
      - Nhưng giữ nguyên trip count (hoặc giảm)

    L3 relational detector (regression của trip_count ~ charging_count) sẽ flag
    residual lớn.
    """
    manifest = []
    df_ev = df_ev.copy()
    df_chg = df_chg.copy()
    df_trip = df_trip.copy()

    if "vehicle_vin" not in df_chg.columns or "assigned_day_index" not in df_chg.columns:
        return df_ev, df_chg, df_trip, manifest

    entities = df_ev["vehicle_vin"].dropna().unique() if "vehicle_vin" in df_ev.columns else []
    if len(entities) == 0:
        return df_ev, df_chg, df_trip, manifest

    n_target = min(5, len(entities))
    target_vins = rng.choice(entities, size=n_target, replace=False)

    # Để đơn giản: duplicate các charging sessions trong nửa sau dataset
    duplicated_rows = []
    for vin in target_vins:
        vin_chg = df_chg[df_chg["vehicle_vin"] == vin]
        if vin_chg.empty:
            continue
        second_half = vin_chg[vin_chg["assigned_day_index"] >= L4_START_DAY]
        if second_half.empty:
            continue
        # Duplicate
        duplicated_rows.append(second_half)

    if not duplicated_rows:
        return df_ev, df_chg, df_trip, manifest

    dup = pd.concat(duplicated_rows, ignore_index=True)
    df_chg = pd.concat([df_chg, dup], ignore_index=True)

    sample_idx = int(dup.index[0])
    mark_fault(
        manifest, "acn_charging_mapped", sample_idx, "session_id",
        "F13_ChargingTrip_Mismatch",
        f"Charging sessions duplicated 2× for {n_target} VINs in day {L4_START_DAY}-{L4_END_DAY} "
        f"but trips count unchanged (L3 relational break)",
        layer="L3", signal_type="RELATIONAL_BREAK",
        target_vins=[str(v) for v in target_vins],
        affected_rows=len(dup),
    )

    return df_ev, df_chg, df_trip, manifest


# --------------------------------------------------------------------------- #
# L4 — Sequential / Change-point (2 fault families)
# --------------------------------------------------------------------------- #

def inject_l4_charging_frequency_shift(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L4 F15 ChargingFrequency_Shift.

    Chọn N VIN, từ day L4_START_DAY: tăng số charging sessions/ngày 3× so với baseline.

    Layer=L4 CUSUM/PELT sẽ detect shift mean của daily_count_per_vin.
    """
    manifest = []
    df = df.copy()
    if "vehicle_vin" not in df.columns or "assigned_day_index" not in df.columns:
        return df, manifest

    entities = df["vehicle_vin"].dropna().unique()
    if len(entities) == 0:
        return df, manifest

    target_vins = rng.choice(entities, size=min(5, len(entities)), replace=False)

    # Baseline: median sessions/day per VIN trong 7 ngày đầu
    new_rows = []
    for vin in target_vins:
        vin_df = df[df["vehicle_vin"] == vin]
        first_week = vin_df[vin_df["assigned_day_index"] < L4_START_DAY]
        if first_week.empty:
            continue
        avg_per_day = len(first_week) / max(1, L4_START_DAY)

        # Trong nửa sau: duplicate sessions để tăng frequency 3×
        second_half = vin_df[vin_df["assigned_day_index"] >= L4_START_DAY]
        if second_half.empty:
            continue
        # Duplicate 2× (tổng 3×)
        extra = pd.concat([second_half, second_half], ignore_index=True)
        new_rows.append(extra)

    if not new_rows:
        return df, manifest

    extra_df = pd.concat(new_rows, ignore_index=True)
    df = pd.concat([df, extra_df], ignore_index=True)

    sample_idx = int(extra_df.index[0])
    mark_fault(
        manifest, "acn_charging_mapped", sample_idx, "session_id",
        "F15_ChargingFrequency_Shift",
        f"Charging frequency shift: {len(target_vins)} VINs jumped from ~1/day to ~3/day "
        f"from day {L4_START_DAY} onward (L4 changepoint)",
        layer="L4", signal_type="CHANGEPOINT_SHIFT",
        target_vins=[str(v) for v in target_vins],
        affected_rows=len(extra_df),
    )

    return df, manifest


def inject_l4_fare_distribution_regime(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    L4 F16 CostDistribution_Regime.

    Chọn N driver, từ day L4_START_DAY: trip_distance_km của mỗi trip tăng 50%.

    L4 sẽ detect shift mean trip_distance_km của driver đó.
    """
    manifest = []
    df = df.copy()
    if "driver_id" not in df.columns or "assigned_day_index" not in df.columns:
        return df, manifest

    drivers = df["driver_id"].dropna().unique()
    if len(drivers) == 0:
        return df, manifest

    target_drivers = rng.choice(drivers, size=min(5, len(drivers)), replace=False)

    for driver in target_drivers:
        mask = (df["driver_id"] == driver) & (df["assigned_day_index"] >= L4_START_DAY)
        if not mask.any():
            continue
        affected_idx = df.index[mask]
        for idx in affected_idx:
            val = df.at[idx, "trip_distance_km"]
            if pd.isna(val):
                continue
            df.at[idx, "trip_distance_km"] = round(float(val) * 1.5, 2)

    sample_idx = int(df.index[mask].min()) if mask.any() else -1
    if sample_idx >= 0:
        mark_fault(
            manifest, "ride_hailing_xanh_sm_trips", sample_idx, "trip_distance_km",
            "F16_FareDistribution_Regime",
            f"Trip distance +50% for {len(target_drivers)} drivers from day {L4_START_DAY} "
            f"(L4 changepoint in mean trip_distance_km)",
            layer="L4", signal_type="CHANGEPOINT_SHIFT",
            target_drivers=[str(d) for d in target_drivers],
        )

    return df, manifest


# --------------------------------------------------------------------------- #
# NLP — TeenCode (1 fault family, tách khỏi L1-L4)
# --------------------------------------------------------------------------- #

def inject_nlp_teencode_corruption(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Giữ nguyên logic từ version cũ."""
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * NLP_FAULT_RATE)
    if n_fault == 0:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)

    teencode_map = [
        ("không", "ko"), ("không thể", "k dc"), ("được", "dc"),
        ("tốt", "tot"), ("lỗi", "loi"), ("tram", "tram"),
        ("sạc", "sac"), ("vì", "vi"), ("nhưng", "nhung"),
        ("thì", "thi"), ("phải", "phai"), ("khó", "kho"),
        ("lắm", "lam"), ("quá", "qua"), ("người", "nguoi"),
        ("đường", "duong"), ("nào", "nao"), ("thế", "the"),
        ("hết", "het"), ("với", "voi"), ("của", "cua"),
        ("đã", "da"), ("đang", "dang"),
    ]

    for row_idx in fault_idx:
        original = str(df.at[row_idx, "sentence"])
        if len(original) < 20:
            continue
        corrupted = original
        for formal, teen in teencode_map:
            if rng.random() < 0.30 and formal in corrupted:
                corrupted = corrupted.replace(formal, teen, 1)
        df.at[row_idx, "sentence"] = corrupted
        mark_fault(
            manifest, "nlp_benchmark_uit_vsfc", row_idx, "sentence",
            "F9_TeenCode_Corruption",
            f"Original: '{original[:50]}...' -> Corrupted: '{corrupted[:50]}...'",
            layer="EXT_NLP", signal_type="TEXT_CORRUPTION",
        )

    return df, manifest


# --------------------------------------------------------------------------- #
# Hướng 2: Synthetic Feedback Scenario-Driven (2026-08-08)
# --------------------------------------------------------------------------- #

def generate_synthetic_feedback_scenario_driven(
    fleet: pd.DataFrame,
    n_scenarios: int = 20,
    days: int = 15,
) -> pd.DataFrame:
    """Giữ nguyên từ version cũ."""
    TEMPLATES = {
        ("vehicle", 0): [
            "xe lỗi pin giữa đường, gọi cứu hộ 1 tiếng mới có xe thay thế",
            "ô tô hết điện đột ngột không báo trước, khách phải xuống đi bộ",
            "màn hình taplo tắt đột ngột khi đang chạy, không biết tốc độ bao nhiêu",
            "điều hòa không hoạt động giữa trưa nắng 40 độ, khách than phiền liên tục",
            "phanh có tiếng kêu lạ khi dừng đèn đỏ, cảm thấy không an toàn",
        ],
        ("vehicle", 1): [
            "xe chạy bình thường nhưng có tiếng ồn nhỏ từ cốp",
            "gương chiếu hậu bị rung nhẹ khi chạy tốc độ cao trên cao tốc",
        ],
        ("vehicle", 2): [
            "xe mới chạy rất mượt, không có vấn đề gì từ khi nhận xe",
            "pin trâu, đi cả ngày không cần sạc thêm",
        ],
        ("charging", 0): [
            "trạm sạc bị hỏng không báo trước, phải tìm trạm khác cách 5km",
            "cáp sạc bị lỗi kết nối, sạc mãi không lên pin",
            "trạm sạc đầy khách, đợi 45 phút mới có chỗ sạc",
        ],
        ("charging", 1): [
            "sạc chậm hơn bình thường, có thể do trời nóng nên giảm công suất",
        ],
        ("charging", 2): [
            "sạc nhanh, đầy pin trong 40 phút, tiện lợi",
        ],
        ("app", 0): [
            "app bị crash liên tục khi đặt xe giờ cao điểm, mất khách",
            "thanh toán bị lỗi 3 lần liên tiếp, khách hàng không hài lòng",
            "map dẫn đường sai lệch, đưa khách đến địa chỉ không đúng",
        ],
        ("app", 1): [
            "notification hơi chậm so với thực tế vị trí xe",
        ],
        ("app", 2): [
            "app dễ sử dụng, đặt xe nhanh chỉ 2 phút",
        ],
        ("driver", 0): [
            "tài xế lái ẩu, phanh gấp nhiều lần khiến khách khó chịu",
            "tài xế hút thuốc trong xe dù khách phản đối",
        ],
        ("driver", 1): [
            "tài xế lái ổn định, không có gì đặc biệt để phàn nàn",
        ],
        ("driver", 2): [
            "tài xế lịch sự, nhắc khách cài dây an toàn",
        ],
    }

    rows = []
    base_date = datetime(2026, 1, 1)
    fleet_vins = list(fleet["vehicle_vin"].values)

    for i in range(n_scenarios):
        vin = rng.choice(fleet_vins)
        day_idx = int(rng.integers(0, days))
        scenario_date = base_date + timedelta(days=day_idx)

        topic_weights = {"vehicle": 0.35, "charging": 0.30, "app": 0.20, "driver": 0.15}
        topics = list(topic_weights.keys())
        weights = list(topic_weights.values())
        topic = rng.choice(topics, p=np.array(weights) / sum(weights))

        if i < n_scenarios * 0.6:
            sentiment = 0
        elif i < n_scenarios * 0.85:
            sentiment = 1
        else:
            sentiment = 2

        templates = TEMPLATES.get((topic, sentiment), TEMPLATES[("app", 1)])
        text = rng.choice(templates)

        rows.append({
            "feedback_id": f"FB_SCENARIO_{i+1:04d}",
            "vehicle_vin": vin,
            "scenario_date": scenario_date.strftime("%Y-%m-%d"),
            "assigned_day_index": day_idx,
            "topic": topic,
            "sentiment": sentiment,
            "raw_comment_text": text,
        })

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    print("=" * 70)
    print("Layer 3: VinGroup Pilot — Fault Injection (L1-L4 + NLP)")
    print("=" * 70)

    if not SRC_DIR.exists():
        raise FileNotFoundError(f"Source directory not found: {SRC_DIR}")

    if DST_DIR.exists():
        print(f"[WARN] {DST_DIR} already exists — overwriting")
        shutil.rmtree(DST_DIR)
    DST_DIR.mkdir(parents=True, exist_ok=True)

    all_manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "random_seed": RANDOM_SEED,
        "source_dir": str(SRC_DIR),
        "schema_version": "v2_l1_l4_nlp",
        "fault_families": {
            "L1": {
                "F1_Negative_SOC": "battery_soc < 0",
                "F2_Voltage_Overvoltage_Spike": "battery_voltage > 1000V",
                "F3_RPM_Speed_Mismatch": "speed=0 but motor_rpm > 12000",
                "F5_Negative_Cost": "cost_vnd < 0",
                "F7_Negative_Fare": "fare_amount < 0",
                "F8_Ledger_Mismatch": "total_fare != fare + tip",
            },
            "L2": {
                "F10_SOC_Degradation_Drift": "SOC discharge rate tăng dần 2 tuần so với baseline 14d",
                "F11_BatteryTemp_Drift": "battery_temp_c tăng đột biến so với baseline 14d",
            },
            "L3": {
                "F6_GPS_Alleyway_Drift": "pickup coords ngoài Hanoi bbox (multivariate)",
                "F13_ChargingTrip_Mismatch": "sạc nhiều sessions nhưng trip thấp — regression residual",
                "F14_DurationEnergy_Mismatch": "duration tăng nhưng kwh flat — relational break",
            },
            "L4": {
                "F15_ChargingFrequency_Shift": "VIN sạc 1→3 lần/ngày từ day X (CUSUM/PELT)",
                "F16_FareDistribution_Regime": "trip_miles shift mean 50% từ day X (CUSUM)",
            },
            "EXT_NLP": {
                "F9_TeenCode_Corruption": "Vietnamese text corrupted with teen-code",
            },
        },
        "injection_summary": {},
        "faults": [],
    }

    total_faults = 0

    # --- (1) Load EV telemetry, apply L1 + L2 ---
    ev_src = SRC_DIR / "synthetic_ev_telemetry_ved_ref.csv"
    if ev_src.exists():
        print(f"\n[*] Processing EV telemetry: {ev_src}")
        df_ev = pd.read_csv(ev_src)
        print(f"    Loaded {len(df_ev)} rows")

        # L1 EV (F1, F2, F3)
        df_ev, l1_ev_m = inject_l1_ev_telemetry(df_ev)
        print(f"    + L1 injected: {len(l1_ev_m)} faults")
        all_manifest["faults"].extend(l1_ev_m)

        # L2 EV (F10, F11)
        df_ev, l2_ev_m = inject_l2_fleet(df_ev)
        print(f"    + L2 injected: {len(l2_ev_m)} faults")
        all_manifest["faults"].extend(l2_ev_m)

        df_ev.to_csv(DST_DIR / "synthetic_ev_telemetry_ved_ref.csv", index=False)
        all_manifest["injection_summary"]["synthetic_ev_telemetry_ved_ref"] = {
            "source_rows": len(pd.read_csv(ev_src)),
            "faults_injected": len(l1_ev_m) + len(l2_ev_m),
            "by_layer": {"L1": len(l1_ev_m), "L2": len(l2_ev_m)},
        }
        total_faults += len(l1_ev_m) + len(l2_ev_m)

    # --- (2) Load charging, apply L1 + L3 + L4 ---
    chg_src = SRC_DIR / "acn_charging_mapped.csv"
    if chg_src.exists():
        print(f"\n[*] Processing charging: {chg_src}")
        df_chg = pd.read_csv(chg_src)
        print(f"    Loaded {len(df_chg)} rows")

        # L1 charging (F5)
        df_chg, l1_chg_m = inject_l1_charging(df_chg)
        print(f"    + L1 injected: {len(l1_chg_m)} faults")
        all_manifest["faults"].extend(l1_chg_m)

        # L3 charging (F14)
        df_chg, l3_chg_m = inject_l3_charging(df_chg)
        print(f"    + L3 injected: {len(l3_chg_m)} faults")
        all_manifest["faults"].extend(l3_chg_m)

        # L4 charging frequency shift (F15)
        df_chg, l4_chg_m = inject_l4_charging_frequency_shift(df_chg)
        print(f"    + L4 injected: {len(l4_chg_m)} faults")
        all_manifest["faults"].extend(l4_chg_m)

        df_chg.to_csv(DST_DIR / "acn_charging_mapped.csv", index=False)
        all_manifest["injection_summary"]["acn_charging_mapped"] = {
            "source_rows": len(pd.read_csv(chg_src)),
            "faults_injected": len(l1_chg_m) + len(l3_chg_m) + len(l4_chg_m),
            "by_layer": {"L1": len(l1_chg_m), "L3": len(l3_chg_m), "L4": len(l4_chg_m)},
        }
        total_faults += len(l1_chg_m) + len(l3_chg_m) + len(l4_chg_m)

    # --- (3) Load trips, apply L1 + L3 + L4 ---
    trip_src = SRC_DIR / "ride_hailing_xanh_sm_trips.csv"
    if trip_src.exists():
        print(f"\n[*] Processing trips: {trip_src}")
        df_trip = pd.read_csv(trip_src)
        print(f"    Loaded {len(df_trip)} rows")

        # L1 trips (F7, F8)
        df_trip, l1_trip_m = inject_l1_trips(df_trip)
        print(f"    + L1 injected: {len(l1_trip_m)} faults")
        all_manifest["faults"].extend(l1_trip_m)

        # L3 trips (F6 GPS alleyway)
        df_trip, l3_trip_m = inject_l3_trips(df_trip)
        print(f"    + L3 injected: {len(l3_trip_m)} faults")
        all_manifest["faults"].extend(l3_trip_m)

        # L4 trips fare regime (F16)
        df_trip, l4_trip_m = inject_l4_fare_distribution_regime(df_trip)
        print(f"    + L4 injected: {len(l4_trip_m)} faults")
        all_manifest["faults"].extend(l4_trip_m)

        df_trip.to_csv(DST_DIR / "ride_hailing_xanh_sm_trips.csv", index=False)
        all_manifest["injection_summary"]["ride_hailing_xanh_sm_trips"] = {
            "source_rows": len(pd.read_csv(trip_src)),
            "faults_injected": len(l1_trip_m) + len(l3_trip_m) + len(l4_trip_m),
            "by_layer": {"L1": len(l1_trip_m), "L3": len(l3_trip_m), "L4": len(l4_trip_m)},
        }
        total_faults += len(l1_trip_m) + len(l3_trip_m) + len(l4_trip_m)

    # --- (4) L3 cross-table: F13 ChargingTrip_Mismatch ---
    if all(src.exists() for src in [ev_src, chg_src, trip_src]):
        print(f"\n[*] L3 cross-table: F13 ChargingTrip_Mismatch")
        df_ev = pd.read_csv(DST_DIR / "synthetic_ev_telemetry_ved_ref.csv")
        df_chg = pd.read_csv(DST_DIR / "acn_charging_mapped.csv")
        df_trip = pd.read_csv(DST_DIR / "ride_hailing_xanh_sm_trips.csv")
        _, df_chg, _, l3_cross_m = inject_l3_charging_trip_mismatch(df_ev, df_chg, df_trip)
        if l3_cross_m:
            print(f"    + L3 cross-table injected: {len(l3_cross_m)} faults")
            all_manifest["faults"].extend(l3_cross_m)
            df_chg.to_csv(DST_DIR / "acn_charging_mapped.csv", index=False)
            total_faults += len(l3_cross_m)

    # --- (5) NLP benchmark (giữ nguyên) ---
    nlp_src = SRC_DIR / "nlp_benchmark_uit_vsfc.csv"
    if nlp_src.exists():
        print(f"\n[*] Processing NLP benchmark: {nlp_src}")
        df_nlp = pd.read_csv(nlp_src)
        df_nlp_faulty, nlp_manifest = inject_nlp_teencode_corruption(df_nlp)
        df_nlp_faulty.to_csv(DST_DIR / "nlp_benchmark_uit_vsfc.csv", index=False)
        all_manifest["faults"].extend(nlp_manifest)
        all_manifest["injection_summary"]["nlp_benchmark_uit_vsfc"] = {
            "source_rows": len(df_nlp),
            "faults_injected": len(nlp_manifest),
            "note": "NLP benchmark kept clean by default (teen-code already present)",
        }
        total_faults += len(nlp_manifest)

    # --- (6) Copy fleet_index, provenance ---
    for fname in ["fleet_index.csv", "provenance_manifest.json", "fleet_index.json", "ved_calibration.json"]:
        src = SRC_DIR / fname
        if src.exists():
            shutil.copy2(src, DST_DIR / fname)
            print(f"[*] Copied {fname}")

    # --- (7) Synthetic feedback scenario-driven ---
    fleet_src = SRC_DIR / "fleet_index.csv"
    if fleet_src.exists():
        fleet_df = pd.read_csv(fleet_src)
        feedback_df = generate_synthetic_feedback_scenario_driven(fleet_df, n_scenarios=20)
        feedback_df.to_csv(DST_DIR / "synthetic_feedback_scenario_driven.csv", index=False)
        print(f"[*] Generated {len(feedback_df)} scenario-driven feedback rows")
        all_manifest["injection_summary"]["synthetic_feedback_scenario_driven"] = {
            "rows": len(feedback_df),
            "note": "Hướng 2: synthetic feedback có kịch bản (2026-08-08)",
        }

    # --- (8) Save manifest ---
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(all_manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"DONE: {total_faults} total faults injected")
    print(f"Output: {DST_DIR}")
    print(f"Fault manifest: {MANIFEST_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
