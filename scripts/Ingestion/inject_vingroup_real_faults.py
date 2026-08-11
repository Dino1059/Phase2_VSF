"""
inject_vingroup_real_faults.py

Layer 3 — Fault Injection cho data\vingroup_real.

Hoạt động trên COPY, không chỉnh sửa ground truth trong data\vingroup_real.

9 Fault Families (từ data/README.md Section 5):
  1. GSM Basement Blackout    -> GPS loss (lat/lon NaN)
  2. Battery BMS Negative SOC  -> battery_soc < 0
  3. CAN-Bus Overvoltage      -> battery_voltage outlier extreme
  4. Motor RPM Mismatch       -> speed=0 nhưng rpm cao bất thường
  5. V-GREEN Thermal Drop     -> power_kw=0 khi station_temp_c cao
  6. Negative Cost/Billing    -> cost_vnd < 0 hoặc fare_amount < 0
  7. GPS Alleyway Drift       -> pickup_lat/lon nhảy ra ngoài bbox Hà Nội
  8. Arithmetic Mismatch      -> total_fare != fare + tip - discount
  9. Teen-Code Noise          -> text bị corrupt bằng teen-code viết tắt

Hướng 2 — Synthetic Feedback Scenario-Driven (2026-08-08 quyết định):
  - UIT-VSFC sai domain (sinh viên đánh giá giảng viên ≠ taxi feedback)
  - Thay bằng synthetic feedback theo kịch bản có kiểm soát
  - Mỗi scenario: VIN + ngày fault → ảnh hưởng telemetry/trips/charging/feedback

Output:
    data/vingroup_real_faulty/*.csv  (copy + injected faults)
    data/vingroup_real_faulty/fault_manifest.json  (ground truth)
    data/vingroup_real_faulty/synthetic_feedback_scenario_driven.csv  (scenario-driven feedback)
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

# Đổi folder output theo quyết định 2026-08-08 (thêm hậu tố _timeseries)
# Source: pilot dataset (syntheic telemetry + real ref data)
SRC_DIR = Path("data/vingroup_pilot_dataset")
# Output: faulty version with injected anomalies
DST_DIR = Path("data/vingroup_faulty_pilot_dataset")
MANIFEST_PATH = DST_DIR / "fault_manifest.json"

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# Bounding box Hà Nội (Hanoi bbox từ ingest_vingroup_real_data.py)
HANOI_BBOX = {"lat_min": 20.95, "lat_max": 21.10, "lon_min": 105.75, "lon_max": 105.90}

# Fault injection rates per dataset
EV_FAULT_RATE = 0.025       # 2.5% rows in EV telemetry get faults
CHG_FAULT_RATE = 0.025      # 2.5% in charging sessions
TRIP_FAULT_RATE = 0.020    # 2.0% in trips
NLP_FAULT_RATE = 0.0       # NLP benchmark giữ nguyên (đã có teen-code rồi)

rng = np.random.default_rng(RANDOM_SEED)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def mark_fault(manifest: list[dict], dataset: str, row_idx: int, col: str,
               fault_family: str, description: str):
    manifest.append({
        "dataset": dataset,
        "original_index": int(row_idx),
        "column": col,
        "fault_family": fault_family,
        "description": description,
    })


def choose_fault_type(n: int, weights: list[float]) -> np.ndarray:
    """Chọn fault type theo tỷ lệ weights."""
    types = list(range(len(weights)))
    return rng.choice(types, size=n, p=np.array(weights) / sum(weights))


# --------------------------------------------------------------------------- #
# Fault Injectors
# --------------------------------------------------------------------------- #

def inject_ev_telemetry_faults(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Inject faults vào synthetic_ev_telemetry_ved_ref.

    Schema: record_id, timestamp, speed_kmh, motor_rpm, battery_soc, battery_voltage,
            battery_current, battery_temp_c, latitude, longitude, accel_z,
            vehicle_vin, assigned_day_index, trip_origin_key, telemetry_coverage,
            synthetic_gap_indicator

    Fault families:
      F0: GSM Basement Blackout (GPS loss: lat/lon = NaN)
      F1: Negative Battery SOC (< 0)
      F2: Overvoltage Spike (> 9000V)
      F3: Motor RPM Mismatch (speed=0 but rpm > 10000)
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * EV_FAULT_RATE)

    # Chọn rows để inject (tránh trùng index)
    fault_idx = rng.choice(n, size=n_fault, replace=False)
    fault_type = choose_fault_type(
        n_fault,
        weights=[0.30, 0.25, 0.25, 0.20]  # F0:F1:F2:F3 weights
    )

    for i, (row_idx, ft) in enumerate(zip(fault_idx, fault_type)):
        row = df.iloc[row_idx]

        if ft == 0:
            # F0: GSM Basement Blackout — GPS loss
            # Timestamp THẬT giữ nguyên, chỉ mất GPS
            df.at[df.index[row_idx], "latitude"] = np.nan
            df.at[df.index[row_idx], "longitude"] = np.nan
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "latitude",
                "GSM_Underground_Blackout",
                f"Vehicle {row['vehicle_vin']} entered basement: GPS lost, lat/lon = NaN"
            )

        elif ft == 1:
            # F1: Negative Battery SOC — BMS sensor defect
            negative_soc = round(rng.uniform(-15.0, -5.0), 1)
            df.at[df.index[row_idx], "battery_soc"] = negative_soc
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "battery_soc",
                "Negative_Sensor_Value",
                f"Battery BMS sensor error: negative SOC {negative_soc}%"
            )

        elif ft == 2:
            # F2: CAN-Bus Overvoltage Spike — extreme outlier
            overvoltage = rng.choice([9999.0, 8888.0, 7500.0])
            df.at[df.index[row_idx], "battery_voltage"] = overvoltage
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "battery_voltage",
                "Voltage_Overvoltage_Outlier",
                f"CAN-bus spike: unrealistic voltage {overvoltage}V"
            )

        else:
            # F3: Motor RPM Mismatch — speed=0 but rpm high
            df.at[df.index[row_idx], "speed_kmh"] = 0.0
            rpm_val = int(rng.integers(12000, 15000))
            df.at[df.index[row_idx], "motor_rpm"] = rpm_val
            mark_fault(
                manifest, "synthetic_ev_telemetry_ved_ref", row_idx, "motor_rpm",
                "Motor_RPM_Mismatch",
                f"Speed is 0 km/h but Motor RPM is {rpm_val} — impossible for EV"
            )

    return df, manifest


def inject_charging_faults(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Inject faults vào acn_charging_mapped.

    Schema: session_id, station_id, charger_id, start_time, duration_mins,
            kwh_consumed, power_kw, charging_pattern, assigned_day_index,
            station_temp_c, cost_vnd, status, vehicle_vin

    Fault families:
      F4: Thermal Power Drop (power_kw=0, station_temp_c > 80°C, status=THERMAL_FAULT)
      F5: Negative Charging Cost (cost_vnd < 0)
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * CHG_FAULT_RATE)

    fault_idx = rng.choice(n, size=n_fault, replace=False)
    fault_type = choose_fault_type(
        n_fault,
        weights=[0.55, 0.45]  # F4:F5 weights
    )

    for row_idx, ft in zip(fault_idx, fault_type):
        row = df.iloc[row_idx]

        if ft == 0:
            # F4: Thermal Power Drop
            # Cần station_temp_c cao (> 80°C) để scenario hợp lý
            df.at[df.index[row_idx], "power_kw"] = 0.0
            df.at[df.index[row_idx], "kwh_consumed"] = 0.0
            df.at[df.index[row_idx], "station_temp_c"] = round(
                rng.uniform(82.0, 92.0), 1
            )
            df.at[df.index[row_idx], "status"] = "THERMAL_FAULT"
            mark_fault(
                manifest, "acn_charging_mapped", row_idx, "power_kw",
                "VGREEN_Thermal_Power_Drop",
                f"Charger {row['charger_id']} at {row['station_id']} overheated: "
                f"Power dropped to 0kW, station_temp={df.at[df.index[row_idx], 'station_temp_c']}°C"
            )

        else:
            # F5: Negative Charging Cost
            negative_cost = round(rng.uniform(-200000.0, -50000.0), 0)
            df.at[df.index[row_idx], "cost_vnd"] = negative_cost
            mark_fault(
                manifest, "acn_charging_mapped", row_idx, "cost_vnd",
                "Negative_Cost_Anomaly",
                f"Billing glitch: negative charging cost {int(negative_cost)} VND"
            )

    return df, manifest


def inject_trip_faults(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Inject faults vào ride_hailing_xanh_sm_trips.

    Schema: trip_id, vehicle_vin, driver_id, pickup_datetime, assigned_day_index,
            trip_miles, fare_amount, currency_unverified, tip_amount,
            discount_amount, total_fare, pickup_latitude, pickup_longitude, vehicle_type

    Fault families:
      F6: GPS Alleyway Drift (coords ra khỏi Hanoi bbox)
      F7: Negative Fare (fare_amount < 0)
      F8: Arithmetic Ledger Mismatch (total_fare != fare + tip - discount)
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * TRIP_FAULT_RATE)

    fault_idx = rng.choice(n, size=n_fault, replace=False)
    fault_type = choose_fault_type(
        n_fault,
        weights=[0.35, 0.30, 0.35]  # F6:F7:F8 weights
    )

    for row_idx, ft in zip(fault_idx, fault_type):
        row = df.iloc[row_idx]

        if ft == 0:
            # F6: GPS Alleyway Drift — coords ra ngoài bbox Hà Nội
            # Inject NYC coordinates (đặc trưng của kịch bản alleyway GPS drift)
            new_lat = rng.uniform(40.70, 40.75)  # NYC latitude
            new_lon = rng.uniform(-74.02, -73.98)  # NYC longitude
            df.at[df.index[row_idx], "pickup_latitude"] = round(new_lat, 6)
            df.at[df.index[row_idx], "pickup_longitude"] = round(new_lon, 6)
            mark_fault(
                manifest, "ride_hailing_xanh_sm_trips", row_idx, "pickup_latitude",
                "GPS_Alleyway_Drift",
                f"GPS drift in narrow alleyway: coords jumped from Hanoi bbox to "
                f"NYC ({new_lat:.4f}, {new_lon:.4f})"
            )

        elif ft == 1:
            # F7: Negative Fare
            negative_fare = round(rng.uniform(-80000.0, -20000.0), 2)
            df.at[df.index[row_idx], "fare_amount"] = negative_fare
            # Recalculate total_fare with negative fare (no discount since vouchers removed 2026-08-08)
            new_total = round(
                negative_fare
                + row["tip_amount"],
                2
            )
            df.at[df.index[row_idx], "total_fare"] = new_total
            mark_fault(
                manifest, "ride_hailing_xanh_sm_trips", row_idx, "fare_amount",
                "Negative_Fare_Defect",
                f"Ledger calculation error: negative fare {negative_fare} VND"
            )

        else:
            # F8: Arithmetic Ledger Mismatch
            # Tang total_fare len de tao mismatch voi fare+tip-discount
            # (discount = 0 sau khi vouchers bi loai bo 2026-08-08)
            adjustment = round(rng.uniform(50000.0, 250000.0), 2)
            current_total = row["fare_amount"] + row["tip_amount"]
            new_total = round(current_total + adjustment, 2)
            df.at[df.index[row_idx], "total_fare"] = new_total
            mark_fault(
                manifest, "ride_hailing_xanh_sm_trips", row_idx, "total_fare",
                "Arithmetic_Ledger_Mismatch",
                f"Total fare ({new_total:,.0f}) does not equal "
                f"fare + tip - discount ({current_total:,.0f}); "
                f"difference = {adjustment:,.0f} VND"
            )

    return df, manifest


def inject_nlp_teencode_corruption(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Inject teen-code corruption vào nlp_benchmark_uit_vsfc.

    Schema: sentence, sentiment, topic

    Fault families:
      F9: Teen-Code Text Corruption — thay thế từ bằng teen-code viết tắt
          (Chỉ áp dụng cho câu dài > 20 ký tự, giữ nguyên sentiment/topic)
    """
    manifest = []
    df = df.copy()
    n = len(df)
    n_fault = int(n * NLP_FAULT_RATE)

    if n_fault == 0:
        return df, manifest

    fault_idx = rng.choice(n, size=n_fault, replace=False)

    # Teen-code mapping cho tiếng Việt (common substitutions)
    teencode_map = [
        ("không", "ko"),
        ("không thể", "k dc"),
        ("được", "dc"),
        ("đi", "đi"),
        ("rất", "rất"),
        ("tốt", "tot"),
        ("lỗi", "loi"),
        ("bị", "bị"),
        ("xe", "xe"),
        ("tram", "tram"),
        ("sạc", "sac"),
        ("vì", "vi"),
        ("nhưng", "nhung"),
        ("thì", "thi"),
        ("phải", "phai"),
        ("khó", "kho"),
        ("lắm", "lam"),
        ("quá", "qua"),
        ("ấy", "ay"),
        ("người", "nguoi"),
        ("đường", "duong"),
        ("nào", "nao"),
        ("thế", "the"),
        ("hết", "het"),
        ("cho", "cho"),
        ("với", "voi"),
        ("của", "cua"),
        ("đã", "da"),
        ("đang", "dang"),
    ]

    for row_idx in fault_idx:
        original = str(df.at[df.index[row_idx], "sentence"])
        if len(original) < 20:
            continue

        corrupted = original
        for formal, teen in teencode_map:
            # Thay thế ngẫu nhiên ~30% từ để không thay hết
            if rng.random() < 0.30 and formal in corrupted:
                corrupted = corrupted.replace(formal, teen, 1)

        df.at[df.index[row_idx], "sentence"] = corrupted
        mark_fault(
            manifest, "nlp_benchmark_uit_vsfc", row_idx, "sentence",
            "TeenCode_Text_Corruption",
            f"Original: '{original[:50]}...' -> Corrupted: '{corrupted[:50]}...'"
        )

    return df, manifest


# --------------------------------------------------------------------------- #
# Hướng 2: Synthetic Feedback Scenario-Driven (2026-08-08)
# --------------------------------------------------------------------------- #

def generate_synthetic_feedback_scenario_driven(
    fleet: pd.DataFrame,
    n_scenarios: int = 5,
    days: int = 15,
) -> pd.DataFrame:
    """
    Tạo synthetic feedback theo kịch bản có kiểm soát.

    Mỗi scenario:
      - VIN + ngày fault
      - Topic: vehicle | charging | app | driver
      - Sentiment: 0 (negative) | 1 (neutral) | 2 (positive)
      - Text: mẫu phù hợp với topic và sentiment

    Cho phép test cross-domain corroboration:
      detector thấy fault → corroborate với negative feedback cùng VIN/ngày.
    """
    # Templates theo topic và sentiment
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
            "cần lau camera lùi vì bị mờ do nước mưa",
        ],
        ("vehicle", 2): [
            "xe mới chạy rất mượt, không có vấn đề gì từ khi nhận xe",
            "pin trâu, đi cả ngày không cần sạc thêm",
            "nội thất rộng rãi, khách ngồi thoải mái",
        ],
        ("charging", 0): [
            "trạm sạc bị hỏng không báo trước, phải tìm trạm khác cách 5km",
            "cáp sạc bị lỗi kết nối, sạc mãi không lên pin",
            "trạm sạc đầy khách, đợi 45 phút mới có chỗ sạc",
            "app báo trạm trống nhưng thực tế đang có xe chiếm chỗ",
        ],
        ("charging", 1): [
            "sạc chậm hơn bình thường, có thể do trời nóng nên giảm công suất",
            "trạm sạc đông nhưng di chuyển hợp lý, chờ khoảng 20 phút",
        ],
        ("charging", 2): [
            "sạc nhanh, đầy pin trong 40 phút, tiện lợi",
            "trạm sạc mới sạch sẽ, nhân viên hỗ trợ nhiệt tình",
        ],
        ("app", 0): [
            "app bị crash liên tục khi đặt xe giờ cao điểm, mất khách",
            "thanh toán bị lỗi 3 lần liên tiếp, khách hàng không hài lòng",
            "map dẫn đường sai lệch, đưa khách đến địa chỉ không đúng",
        ],
        ("app", 1): [
            "notification hơi chậm so với thực tế vị trí xe",
            "giao diện ổn nhưng đôi khi loading lâu",
        ],
        ("app", 2): [
            "app dễ sử dụng, đặt xe nhanh chỉ 2 phút",
            "giao diện đẹp, thông báo chính xác thời gian đến",
        ],
        ("driver", 0): [
            "tài xế lái ẩu, phanh gấp nhiều lần khiến khách khó chịu",
            "tài xế hút thuốc trong xe dù khách phản đối",
            "tài xế nói chuyện điện thoại suốt chuyến đi",
        ],
        ("driver", 1): [
            "tài xế lái ổn định, không có gì đặc biệt để phàn nàn",
            "chuyến đi bình thường, đến đúng giờ",
        ],
        ("driver", 2): [
            "tài xế lịch sự, nhắc khách cài dây an toàn",
            "tài xế lái xe an toàn, không phanh gấp, rất chuyên nghiệp",
        ],
    }

    rows = []
    base_date = datetime(2026, 1, 1)
    fleet_vins = list(fleet["vehicle_vin"].values)

    # Chọn ngẫu nhiên VIN và ngày cho mỗi scenario
    for i in range(n_scenarios):
        vin = rng.choice(fleet_vins)
        day_idx = int(rng.integers(0, days))
        scenario_date = base_date + timedelta(days=day_idx)

        # Chọn topic ngẫu nhiên có trọng số (vehicle và charging nhiều hơn)
        topic_weights = {"vehicle": 0.35, "charging": 0.30, "app": 0.20, "driver": 0.15}
        topics = list(topic_weights.keys())
        weights = list(topic_weights.values())
        topic = rng.choice(topics, p=np.array(weights) / sum(weights))

        # Sentiment: 0=negative, 1=neutral, 2=positive
        # Nhiều fault scenario → negative feedback
        if i < n_scenarios * 0.6:
            sentiment = 0  # negative
        elif i < n_scenarios * 0.85:
            sentiment = 1  # neutral
        else:
            sentiment = 2  # positive

        # Chọn text template
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
    print("=" * 60)
    print("Layer 3: VinGroup Real Data — Fault Injection")
    print("=" * 60)

    # Verify source exists
    if not SRC_DIR.exists():
        raise FileNotFoundError(
            f"Source directory not found: {SRC_DIR}\n"
            "Run ingest_vingroup_real_data.py first."
        )

    # Create output directory (work on COPY)
    if DST_DIR.exists():
        print(f"[WARN] {DST_DIR} already exists — overwriting")
        shutil.rmtree(DST_DIR)
    DST_DIR.mkdir(parents=True, exist_ok=True)

    all_manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "random_seed": RANDOM_SEED,
        "source_dir": str(SRC_DIR),
        "fault_families": {
            "F0_GSM_Underground_Blackout": "Vehicle entered basement: GPS lost (lat/lon=NaN)",
            "F1_Negative_Sensor_Value": "Battery BMS sensor error: negative SOC < 0%",
            "F2_Voltage_Overvoltage_Outlier": "CAN-bus spike: battery_voltage > 7000V",
            "F3_Motor_RPM_Mismatch": "Speed=0 km/h but Motor RPM > 12000",
            "F4_VGREEN_Thermal_Power_Drop": "Charger overheated (>80°C): power_kw=0, status=THERMAL_FAULT",
            "F5_Negative_Cost_Anomaly": "Billing glitch: negative cost_vnd < 0",
            "F6_GPS_Alleyway_Drift": "GPS coords jumped to NYC coords outside Hanoi bbox",
            "F7_Negative_Fare_Defect": "Ledger error: fare_amount < 0",
            "F8_Arithmetic_Ledger_Mismatch": "total_fare != fare + tip - discount",
            "F9_TeenCode_Text_Corruption": "Vietnamese text corrupted with teen-code abbreviations",
        },
        "injection_summary": {},
        "faults": [],
    }

    total_faults = 0

    # --- EV Telemetry ---
    ev_src = SRC_DIR / "synthetic_ev_telemetry_ved_ref.csv"
    if ev_src.exists():
        print(f"\n[*] Processing EV telemetry: {ev_src}")
        df_ev = pd.read_csv(ev_src)
        df_ev_faulty, ev_manifest = inject_ev_telemetry_faults(df_ev)
        df_ev_faulty.to_csv(DST_DIR / "synthetic_ev_telemetry_ved_ref.csv", index=False)
        all_manifest["faults"].extend(ev_manifest)
        all_manifest["injection_summary"]["synthetic_ev_telemetry_ved_ref"] = {
            "source_rows": len(df_ev),
            "faults_injected": len(ev_manifest),
            "fault_rate": f"{len(ev_manifest)/len(df_ev)*100:.2f}%",
            "by_family": {
                "GSM_Underground_Blackout": sum(1 for f in ev_manifest if f["fault_family"] == "GSM_Underground_Blackout"),
                "Negative_Sensor_Value": sum(1 for f in ev_manifest if f["fault_family"] == "Negative_Sensor_Value"),
                "Voltage_Overvoltage_Outlier": sum(1 for f in ev_manifest if f["fault_family"] == "Voltage_Overvoltage_Outlier"),
                "Motor_RPM_Mismatch": sum(1 for f in ev_manifest if f["fault_family"] == "Motor_RPM_Mismatch"),
            }
        }
        total_faults += len(ev_manifest)
        print(f"    + Injected {len(ev_manifest)} faults -> {DST_DIR / 'synthetic_ev_telemetry_ved_ref.csv'}")
    else:
        print(f"[SKIP] {ev_src} not found")

    # --- Charging Sessions ---
    chg_src = SRC_DIR / "acn_charging_mapped.csv"
    if chg_src.exists():
        print(f"\n[*] Processing charging stations: {chg_src}")
        df_chg = pd.read_csv(chg_src)
        df_chg_faulty, chg_manifest = inject_charging_faults(df_chg)
        df_chg_faulty.to_csv(DST_DIR / "acn_charging_mapped.csv", index=False)
        all_manifest["faults"].extend(chg_manifest)
        all_manifest["injection_summary"]["acn_charging_mapped"] = {
            "source_rows": len(df_chg),
            "faults_injected": len(chg_manifest),
            "fault_rate": f"{len(chg_manifest)/len(df_chg)*100:.2f}%",
            "by_family": {
                "VGREEN_Thermal_Power_Drop": sum(1 for f in chg_manifest if f["fault_family"] == "VGREEN_Thermal_Power_Drop"),
                "Negative_Cost_Anomaly": sum(1 for f in chg_manifest if f["fault_family"] == "Negative_Cost_Anomaly"),
            }
        }
        total_faults += len(chg_manifest)
        print(f"    + Injected {len(chg_manifest)} faults -> {DST_DIR / 'acn_charging_mapped.csv'}")
    else:
        print(f"[SKIP] {chg_src} not found")

    # --- Trips ---
    trip_src = SRC_DIR / "ride_hailing_xanh_sm_trips.csv"
    if trip_src.exists():
        print(f"\n[*] Processing trips: {trip_src}")
        df_trip = pd.read_csv(trip_src)
        df_trip_faulty, trip_manifest = inject_trip_faults(df_trip)
        df_trip_faulty.to_csv(DST_DIR / "ride_hailing_xanh_sm_trips.csv", index=False)
        all_manifest["faults"].extend(trip_manifest)
        all_manifest["injection_summary"]["ride_hailing_xanh_sm_trips"] = {
            "source_rows": len(df_trip),
            "faults_injected": len(trip_manifest),
            "fault_rate": f"{len(trip_manifest)/len(df_trip)*100:.3f}%",
            "by_family": {
                "GPS_Alleyway_Drift": sum(1 for f in trip_manifest if f["fault_family"] == "GPS_Alleyway_Drift"),
                "Negative_Fare_Defect": sum(1 for f in trip_manifest if f["fault_family"] == "Negative_Fare_Defect"),
                "Arithmetic_Ledger_Mismatch": sum(1 for f in trip_manifest if f["fault_family"] == "Arithmetic_Ledger_Mismatch"),
            }
        }
        total_faults += len(trip_manifest)
        print(f"    + Injected {len(trip_manifest)} faults -> {DST_DIR / 'ride_hailing_xanh_sm_trips.csv'}")
    else:
        print(f"[SKIP] {trip_src} not found")

    # --- NLP Benchmark (UIT-VSFC) ---
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
            "note": "NLP benchmark kept clean by default (teen-code already present in sentences)"
        }
        total_faults += len(nlp_manifest)
        print(f"    + Injected {len(nlp_manifest)} faults -> {DST_DIR / 'nlp_benchmark_uit_vsfc.csv'}")
    else:
        print(f"[SKIP] {nlp_src} not found")

    # --- Copy fleet_index (no fault injection) ---
    fleet_src = SRC_DIR / "fleet_index.csv"
    if fleet_src.exists():
        shutil.copy2(fleet_src, DST_DIR / "fleet_index.csv")
        print(f"\n[*] Copied fleet_index.csv (no faults)")

    # --- Copy provenance manifest from Layer 2 ---
    prov_src = SRC_DIR / "provenance_manifest.json"
    if prov_src.exists():
        shutil.copy2(prov_src, DST_DIR / "provenance_manifest.json")
        print(f"[*] Copied provenance_manifest.json")

    # --- Hướng 2: Synthetic Feedback Scenario-Driven ---
    # Đọc fleet để lấy VIN pool
    fleet_src = SRC_DIR / "fleet_index.csv"
    if fleet_src.exists():
        fleet_df = pd.read_csv(fleet_src)
        feedback_df = generate_synthetic_feedback_scenario_driven(fleet_df, n_scenarios=20)
        feedback_df.to_csv(DST_DIR / "synthetic_feedback_scenario_driven.csv", index=False)
        print(f"[*] Generated {len(feedback_df)} scenario-driven feedback -> synthetic_feedback_scenario_driven.csv")
        # Ghi manifest entry
        all_manifest["injection_summary"]["synthetic_feedback_scenario_driven"] = {
            "rows": len(feedback_df),
            "note": "Hướng 2: synthetic feedback có kịch bản (2026-08-08)",
        }

    # --- Save fault manifest ---
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(all_manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"DONE: {total_faults} total faults injected across 4 datasets")
    print(f"Output: {DST_DIR}")
    print(f"Fault manifest: {MANIFEST_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
