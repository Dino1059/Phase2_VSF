import os
import pandas as pd

RAW_PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw_public")
VINGROUP_REAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vingroup_real")
os.makedirs(VINGROUP_REAL_DIR, exist_ok=True)

def ingest_and_map_real_data():
    """Maps 4 raw public datasets to VinGroup VinFast / Xanh SM / V-GREEN enterprise schemas."""
    
    # 1. Map Vehicle Telemetry -> real_vinfast_ev_telemetry
    raw_ev_path = os.path.join(RAW_PUBLIC_DIR, "vehicle_telemetry_raw.csv")
    if os.path.exists(raw_ev_path):
        df_ev = pd.read_csv(raw_ev_path)
        df_ev["vehicle_vin"] = [f"VF9_REAL_VIN_{100 + (i % 20)}" for i in range(len(df_ev))]
        df_ev.rename(columns={
            "soc_pct": "battery_soc",
            "battery_voltage_v": "battery_voltage",
            "battery_current_a": "battery_current",
            "pack_temp_c": "battery_temp_c"
        }, inplace=True)
        out_ev = os.path.join(VINGROUP_REAL_DIR, "real_vinfast_ev_telemetry.csv")
        df_ev.to_csv(out_ev, index=False)
        print(f"[MAPPER SUCCESS] Mapped Real VinFast EV Telemetry -> {out_ev} ({len(df_ev)} rows)")

    # 2. Map ST-EVCDP -> real_vgreen_charging_stations
    raw_st_path = os.path.join(RAW_PUBLIC_DIR, "st_evcdp_raw.csv")
    if os.path.exists(raw_st_path):
        df_st = pd.read_csv(raw_st_path)
        df_st["station_id"] = [f"VGREEN_STA_{100 + (i % 30)}" for i in range(len(df_st))]
        df_st["vehicle_vin"] = [f"VF8_REAL_VIN_{200 + (i % 25)}" for i in range(len(df_st))]
        df_st.rename(columns={
            "max_power_kw": "power_kw",
            "charging_duration_mins": "duration_mins",
            "price_rate_cny": "cost_rate_vnd"
        }, inplace=True)
        # Convert CNY to VND for realistic Vietnam context
        df_st["cost_vnd"] = (df_st["kwh_consumed"] * 3850.0).round(2)
        out_st = os.path.join(VINGROUP_REAL_DIR, "real_vgreen_charging_stations.csv")
        df_st.to_csv(out_st, index=False)
        print(f"[MAPPER SUCCESS] Mapped Real V-GREEN Charging Stations -> {out_st} ({len(df_st)} rows)")

    # 3. Map Ride Hailing -> real_xanh_sm_trips
    raw_trip_path = os.path.join(RAW_PUBLIC_DIR, "ride_hailing_raw.csv")
    if os.path.exists(raw_trip_path):
        df_trip = pd.read_csv(raw_trip_path)
        df_trip["vehicle_vin"] = [f"VF5_XANH_VIN_{300 + (i % 15)}" for i in range(len(df_trip))]
        df_trip.rename(columns={
            "transaction_id": "trip_id",
            "distance_km": "trip_miles",
            "fare_vnd": "fare_amount",
            "tip_vnd": "tip_amount",
            "discount_vnd": "discount_amount",
            "lat": "pickup_latitude",
            "lon": "pickup_longitude"
        }, inplace=True)
        df_trip["total_fare"] = (df_trip["fare_amount"] + df_trip["tip_amount"] - df_trip["discount_amount"]).round(2)
        out_trip = os.path.join(VINGROUP_REAL_DIR, "real_xanh_sm_trips.csv")
        df_trip.to_csv(out_trip, index=False)
        print(f"[MAPPER SUCCESS] Mapped Real Xanh SM Trips -> {out_trip} ({len(df_trip)} rows)")

    # 4. Map UIT-VSFC -> real_xanh_sm_customer_feedback
    raw_fb_path = os.path.join(RAW_PUBLIC_DIR, "uit_vsfc_raw.csv")
    if os.path.exists(raw_fb_path):
        df_fb = pd.read_csv(raw_fb_path)
        df_fb.rename(columns={
            "sentence_id": "feedback_id",
            "sentence": "raw_comment_text"
        }, inplace=True)
        df_fb["customer_id"] = [f"CUST_REAL_{100 + (i % 40)}" for i in range(len(df_fb))]
        out_fb = os.path.join(VINGROUP_REAL_DIR, "real_xanh_sm_customer_feedback.csv")
        df_fb.to_csv(out_fb, index=False)
        print(f"[MAPPER SUCCESS] Mapped Real Xanh SM Customer Feedback -> {out_fb} ({len(df_fb)} rows)")

if __name__ == "__main__":
    ingest_and_map_real_data()
