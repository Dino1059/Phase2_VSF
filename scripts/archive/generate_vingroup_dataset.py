import json
import math
import os
import random
import datetime
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
VINGROUP_DIR = os.path.join(DATA_DIR, "vingroup")
os.makedirs(VINGROUP_DIR, exist_ok=True)

def generate_vingroup_datasets():
    """Generates 4 synthetic enterprise datasets for VinGroup / VinFast / Xanh SM / V-GREEN ecosystem

    Data Domains:
    1. vinfast_ev_telemetry_dirty.csv (Telemetry IoT: SOC %, Voltage, Temp °C, Speed, Motor RPM, GPS, Basement Blackout)
    2. vgreen_charging_stations_dirty.csv (V-GREEN Charging Sessions: Station ID, Charger ID, Power kW, Temp, Power drop faults)
    3. xanh_sm_trips_dirty.csv (Xanh SM Taxi/Bike: Trip ID, Vehicle VIN, Driver ID, GPS Lat/Lon, Trip Miles, Fare, Tip, Alleyway drift)
    4. xanh_sm_customer_feedback_dirty.csv (Unstructured Vietnamese text feedback: Teen-code, Aspect entities)
    5. vingroup_fault_manifest.json (Ground truth fault injection record for precision/recall evaluation)
    """
    random.seed(42)
    np.random.seed(42)
    start_dt = datetime.datetime(2026, 8, 1, 8, 0, 0)
    fault_manifest = []

    # ==========================================
    # DOMAIN 1: VinFast EV Telemetry (1,000 rows)
    # ==========================================
    ev_rows = []
    vin_list = [f"VF8VNF888{1000 + i}" for i in range(20)]

    for i in range(1, 1001):
        vin = random.choice(vin_list)
        p_dt = start_dt + datetime.timedelta(seconds=i * 10)
        ts_str = p_dt.isoformat()

        speed = round(random.uniform(0.0, 95.0), 1)
        rpm = int(speed * 45 + random.randint(-50, 50))
        soc = round(max(5.0, 100.0 - (i * 0.08) % 95.0), 1)
        voltage = round(380.0 + random.uniform(-10.0, 15.0), 1)
        current = round(random.uniform(0.0, 120.0), 1)
        temp = round(28.0 + random.uniform(0.0, 14.0), 1)
        lat = round(21.0285 + random.uniform(-0.05, 0.05), 5)  # Hanoi lat
        lon = round(105.8542 + random.uniform(-0.05, 0.05), 5)  # Hanoi lon
        acc_z = round(9.81 + random.uniform(-0.5, 0.5), 2)

        fault_type = None
        if i % 25 == 0:
            fault_type = i % 4

        if fault_type == 0:
            # GSM Basement Blackout
            lat, lon = None, None
            ts_str = "INVALID_TIMESTAMP"
            fault_manifest.append({
                "dataset": "vinfast_ev_telemetry_dirty",
                "row_id": i,
                "column": "timestamp",
                "fault_family": "GSM_Underground_Blackout",
                "description": f"Vehicle {vin} entered Vincom basement: GPS loss and invalid timestamp"
            })
        elif fault_type == 1:
            # Negative Battery SOC / Sensor Defect
            soc = -12.5
            fault_manifest.append({
                "dataset": "vinfast_ev_telemetry_dirty",
                "row_id": i,
                "column": "battery_soc",
                "fault_family": "Negative_Sensor_Value",
                "description": f"Battery BMS sensor error: negative SOC {soc}%"
            })
        elif fault_type == 2:
            # Overvoltage Extreme Outlier
            voltage = 9999.0
            fault_manifest.append({
                "dataset": "vinfast_ev_telemetry_dirty",
                "row_id": i,
                "column": "battery_voltage",
                "fault_family": "Voltage_Overvoltage_Outlier",
                "description": f"CAN-bus spike: unrealistic voltage {voltage}V"
            })
        elif fault_type == 3:
            # Motor RPM Mismatch
            speed = 0.0
            rpm = 14500
            fault_manifest.append({
                "dataset": "vinfast_ev_telemetry_dirty",
                "row_id": i,
                "column": "motor_rpm",
                "fault_family": "Motor_RPM_Mismatch",
                "description": f"Speed is 0 km/h but Motor RPM is {rpm}"
            })

        ev_rows.append({
            "record_id": f"EV_REC_{i:04d}",
            "vehicle_vin": vin,
            "timestamp": ts_str,
            "speed_kmh": speed,
            "motor_rpm": rpm,
            "battery_soc": soc,
            "battery_voltage": voltage,
            "battery_current": current,
            "battery_temp_c": temp,
            "latitude": lat,
            "longitude": lon,
            "accel_z": acc_z
        })

    df_ev = pd.DataFrame(ev_rows)
    df_ev.to_csv(os.path.join(VINGROUP_DIR, "vinfast_ev_telemetry_dirty.csv"), index=False)
    df_ev.to_parquet(os.path.join(VINGROUP_DIR, "vinfast_ev_telemetry_dirty.parquet"), index=False)

    # ===================================================
    # DOMAIN 2: V-GREEN Charging Station Sessions (500 rows)
    # ===================================================
    vg_rows = []
    stations = ["VG_STA_VINCOM_BA_TRIEU", "VG_STA_ROYAL_CITY", "VG_STA_OCEAN_PARK", "VG_STA_LANDMARK81"]

    for i in range(1, 501):
        sta = random.choice(stations)
        charger_id = f"{sta}_C0{random.randint(1, 8)}"
        vin = random.choice(vin_list)
        session_id = f"CHG_SESS_{i:04d}"

        p_dt = start_dt + datetime.timedelta(minutes=i * 5)
        duration_mins = random.randint(15, 60)
        power_kw = round(random.uniform(30.0, 150.0), 1)
        kwh_consumed = round(power_kw * (duration_mins / 60.0), 2)
        station_temp = round(32.0 + random.uniform(0.0, 12.0), 1)
        cost_vnd = round(kwh_consumed * 3850.0, 2)
        status = "COMPLETED"

        if i % 20 == 0:
            # Sudden Power Drop / Thermal Trip
            power_kw = 0.0
            kwh_consumed = 0.0
            station_temp = 85.5
            status = "THERMAL_FAULT"
            fault_manifest.append({
                "dataset": "vgreen_charging_stations_dirty",
                "row_id": i,
                "column": "power_kw",
                "fault_family": "VGREEN_Thermal_Power_Drop",
                "description": f"V-GREEN Charger {charger_id} at {sta} overheated ({station_temp}°C): Power dropped to 0kW"
            })
        elif i % 35 == 0:
            # Negative Charging Cost
            cost_vnd = -150000.0
            fault_manifest.append({
                "dataset": "vgreen_charging_stations_dirty",
                "row_id": i,
                "column": "cost_vnd",
                "fault_family": "Negative_Cost_Anomaly",
                "description": f"Billing glitch: negative charging cost {cost_vnd} VND"
            })

        vg_rows.append({
            "session_id": session_id,
            "station_id": sta,
            "charger_id": charger_id,
            "vehicle_vin": vin,
            "start_time": p_dt.isoformat(),
            "duration_mins": duration_mins,
            "power_kw": power_kw,
            "kwh_consumed": kwh_consumed,
            "station_temp_c": station_temp,
            "cost_vnd": cost_vnd,
            "status": status
        })

    df_vg = pd.DataFrame(vg_rows)
    df_vg.to_csv(os.path.join(VINGROUP_DIR, "vgreen_charging_stations_dirty.csv"), index=False)
    df_vg.to_parquet(os.path.join(VINGROUP_DIR, "vgreen_charging_stations_dirty.parquet"), index=False)

    # =============================================
    # DOMAIN 3: Xanh SM Ride-Hailing Trips (500 rows)
    # =============================================
    xanh_rows = []
    drivers = [f"DRV_XANH_{100 + i}" for i in range(15)]

    for i in range(1, 501):
        trip_id = f"XANH_TRIP_{1000 + i}"
        vin = random.choice(vin_list)
        driver_id = random.choice(drivers)

        dist_km = round(random.uniform(1.2, 28.5), 2)
        fare = round(20000.0 + dist_km * 14000.0 + random.uniform(0, 5000), 2)
        tip = round(random.choice([0.0, 10000.0, 20000.0]), 2)
        discount = round(random.choice([0.0, 5000.0, 10000.0]), 2)
        total_fare = round(fare + tip - discount, 2)
        lat = round(21.0285 + random.uniform(-0.04, 0.04), 5)
        lon = round(105.8542 + random.uniform(-0.04, 0.04), 5)

        if i % 18 == 0:
            # GPS Drift in Alleyways
            lat = 40.7128  # New York latitude injected into Hanoi!
            lon = -74.0060
            fault_manifest.append({
                "dataset": "xanh_sm_trips_dirty",
                "row_id": i,
                "column": "latitude",
                "fault_family": "GPS_Alleyway_Drift",
                "description": f"GPS Drift in narrow alleyway: coordinates jumped to NYC ({lat}, {lon})"
            })
        elif i % 28 == 0:
            # Negative Fare / Tip
            fare = -50000.0
            total_fare = round(fare + tip - discount, 2)
            fault_manifest.append({
                "dataset": "xanh_sm_trips_dirty",
                "row_id": i,
                "column": "fare_amount",
                "fault_family": "Negative_Fare_Defect",
                "description": f"Ledger calculation error: negative fare {fare} VND"
            })
        elif i % 42 == 0:
            # Arithmetic Mismatch
            total_fare = round(total_fare + 150000.0, 2)
            fault_manifest.append({
                "dataset": "xanh_sm_trips_dirty",
                "row_id": i,
                "column": "total_fare",
                "fault_family": "Arithmetic_Ledger_Mismatch",
                "description": f"Total fare ({total_fare}) does not equal fare + tip - discount"
            })

        xanh_rows.append({
            "trip_id": trip_id,
            "vehicle_vin": vin,
            "driver_id": driver_id,
            "pickup_datetime": (start_dt + datetime.timedelta(minutes=i * 3)).isoformat(),
            "trip_miles": dist_km,
            "fare_amount": fare,
            "tip_amount": tip,
            "discount_amount": discount,
            "total_fare": total_fare,
            "pickup_latitude": lat,
            "pickup_longitude": lon,
            "vehicle_type": random.choice(["VF_5_TAXI", "VF_e34_TAXI", "FELIZ_S_BIKE"])
        })

    df_xanh = pd.DataFrame(xanh_rows)
    df_xanh.to_csv(os.path.join(VINGROUP_DIR, "xanh_sm_trips_dirty.csv"), index=False)
    df_xanh.to_parquet(os.path.join(VINGROUP_DIR, "xanh_sm_trips_dirty.parquet"), index=False)

    # ===============================================================
    # DOMAIN 4: Unstructured Vietnamese Customer Feedback (100 rows)
    # ===============================================================
    feedback_samples = [
        ("FB_001", "xe di em nhung tram sac v-green o vincom ba trieu bi loi ko sac dc, app lag vl", "Vincom Bà Triệu", "Trạm sạc V-GREEN", "Lỗi kết nối sạc", "CRITICAL"),
        ("FB_002", "tai xe xanh sm nhiet tinh phuc vu rat tot, xe vf8 thom tho sach se", "Hà Nội", "Dịch vụ tài xế", "Khen ngợi dịch vụ", "INFO"),
        ("FB_003", "tram sac royal city full cho ko co cho do, app hien linh tinh", "Royal City", "Ứng dụng di động", "Sai lệch trạng thái trạm sạc", "WARNING"),
        ("FB_004", "xe vf e34 bao loi pin ko chay dc o nguyen trai, goi cuu ho lau vl", "Nguyễn Trãi", "Pin xe VinFast", "Cảnh báo lỗi pin", "CRITICAL"),
        ("FB_005", "gia cước xanh sm taxi rat hop ly, se ung ho lau dai", "TPHCM", "Giá cước", "Khen ngợi cước phí", "INFO"),
        ("FB_006", "tram sac landmark 81 bi ngat dien dot ngot luc dang sac 80%", "Landmark 81", "Trạm sạc V-GREEN", "Ngắt điện đột ngột", "CRITICAL"),
        ("FB_007", "app xanh sm lag ko dat dc xe o ngap nuoc quan 7", "Quận 7", "Ứng dụng di động", "Lỗi đặt xe trên app", "WARNING"),
        ("FB_008", "xe vf5 sach se em a, tai xe chay an toan 10 diem", "Đà Nẵng", "Xe VinFast VF5", "Khen ngợi trải nghiệm", "INFO"),
    ]

    fb_rows = []
    for i in range(1, 101):
        sample = feedback_samples[(i - 1) % len(feedback_samples)]
        fb_rows.append({
            "feedback_id": f"FB_RAW_{i:04d}",
            "customer_id": f"CUST_VN_{100 + (i % 30)}",
            "timestamp": (start_dt + datetime.timedelta(hours=i)).isoformat(),
            "raw_comment_text": sample[1],
            "extracted_location": sample[2],
            "extracted_component": sample[3],
            "extracted_error_type": sample[4],
            "severity_level": sample[5]
        })

    df_fb = pd.DataFrame(fb_rows)
    df_fb.to_csv(os.path.join(VINGROUP_DIR, "xanh_sm_customer_feedback_dirty.csv"), index=False)
    df_fb.to_parquet(os.path.join(VINGROUP_DIR, "xanh_sm_customer_feedback_dirty.parquet"), index=False)

    # Save Ground Truth Fault Manifest JSON
    manifest_path = os.path.join(VINGROUP_DIR, "vingroup_fault_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(fault_manifest, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated VinGroup Multi-Domain Ecosystem Datasets in {VINGROUP_DIR}:")
    print(f" - vinfast_ev_telemetry_dirty ({len(df_ev)} rows)")
    print(f" - vgreen_charging_stations_dirty ({len(df_vg)} rows)")
    print(f" - xanh_sm_trips_dirty ({len(df_xanh)} rows)")
    print(f" - xanh_sm_customer_feedback_dirty ({len(df_fb)} rows)")
    print(f" - vingroup_fault_manifest.json ({len(fault_manifest)} ground-truth faults)")

if __name__ == "__main__":
    generate_vingroup_datasets()
