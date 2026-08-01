import hashlib
import os
import sys
import uuid
from datetime import datetime
import numpy as np
import pandas as pd


def generate_synthetic_dataset():
    """Generates a realistic synthetic Vietnam ride-hailing dataset of 50,000 trips."""
    SEED = 42
    N = 50_000
    rng = np.random.default_rng(SEED)

    print("Generating synthetic dataset (N = 50,000, seed = 42)...")

    # 1. UUID4 generation (reproducible with RNG)
    def gen_uuid4_list(n, rng_inst):
        raw_bytes = rng_inst.bytes(16 * n)
        uuids = []
        for i in range(n):
            b = bytearray(raw_bytes[i * 16 : (i + 1) * 16])
            b[6] = (b[6] & 0x0F) | 0x40  # Version 4
            b[8] = (b[8] & 0x3F) | 0x80  # Variant RFC 4122
            uuids.append(str(uuid.UUID(bytes=bytes(b))))
        return uuids

    trip_ids = gen_uuid4_list(N, rng)
    booking_ids = gen_uuid4_list(N, rng)

    # 2. Passenger & Driver tokens (SHA256 stubs)
    NUM_PAX = 5000
    NUM_DRV = 2000
    pax_pool = [
        f"pax_{hashlib.sha256(f'pax_{i}'.encode()).hexdigest()[:12]}"
        for i in range(NUM_PAX)
    ]
    drv_pool = [
        f"drv_{hashlib.sha256(f'drv_{j}'.encode()).hexdigest()[:12]}"
        for j in range(NUM_DRV)
    ]

    passenger_tokens = rng.choice(pax_pool, size=N)
    driver_tokens = rng.choice(drv_pool, size=N)

    # 3. Vehicle type & Service city distributions
    vehicle_types = rng.choice(
        ["motorbike", "car_4seat", "car_7seat"],
        size=N,
        p=[0.60, 0.30, 0.10],
    )
    service_cities = rng.choice(
        ["Ho Chi Minh City", "Hanoi", "Da Nang"],
        size=N,
        p=[0.70, 0.20, 0.10],
    )

    # 4. Booking status distribution
    booking_statuses = rng.choice(
        [
            "completed",
            "cancelled_by_passenger",
            "cancelled_by_driver",
            "no_driver_found",
        ],
        size=N,
        p=[0.85, 0.08, 0.05, 0.02],
    )

    # Driver token is null if no driver was found
    driver_tokens = np.where(
        booking_statuses == "no_driver_found", None, driver_tokens
    )

    # 5. Pickup & Dropoff coordinates by city
    pickup_lats = np.zeros(N, dtype=np.float64)
    pickup_lons = np.zeros(N, dtype=np.float64)

    hcm_mask = service_cities == "Ho Chi Minh City"
    hn_mask = service_cities == "Hanoi"
    dn_mask = service_cities == "Da Nang"

    pickup_lats[hcm_mask] = rng.uniform(10.75, 10.88, size=np.sum(hcm_mask))
    pickup_lons[hcm_mask] = rng.uniform(106.60, 106.75, size=np.sum(hcm_mask))

    pickup_lats[hn_mask] = rng.uniform(20.98, 21.05, size=np.sum(hn_mask))
    pickup_lons[hn_mask] = rng.uniform(105.78, 105.87, size=np.sum(hn_mask))

    pickup_lats[dn_mask] = rng.uniform(16.04, 16.08, size=np.sum(dn_mask))
    pickup_lons[dn_mask] = rng.uniform(108.17, 108.24, size=np.sum(dn_mask))

    # 6. Distances & Durations
    # LogNormal(mu=1.5, sigma=0.7)
    estimated_distance_km = rng.lognormal(mean=1.5, sigma=0.7, size=N)
    estimated_distance_km = np.round(estimated_distance_km, 2)

    actual_distance_km = estimated_distance_km * rng.uniform(
        0.9, 1.3, size=N
    )
    actual_distance_km = np.round(actual_distance_km, 2)

    # Calculate dropoff lat/lon offset from pickup by actual distance
    theta = rng.uniform(0, 2 * np.pi, size=N)
    delta_lat = (actual_distance_km * np.cos(theta)) / 111.0
    delta_lon = (actual_distance_km * np.sin(theta)) / (
        111.0 * np.cos(np.radians(pickup_lats))
    )
    dropoff_lats = np.round(pickup_lats + delta_lat, 6)
    dropoff_lons = np.round(pickup_lons + delta_lon, 6)
    pickup_lats = np.round(pickup_lats, 6)
    pickup_lons = np.round(pickup_lons, 6)

    # Speed: motorbike 25 km/h, car 30 km/h
    speeds = np.where(vehicle_types == "motorbike", 25.0, 30.0)
    estimated_duration_min = np.round((estimated_distance_km / speeds) * 60.0, 2)
    actual_duration_min = np.round(
        estimated_duration_min * rng.uniform(0.8, 1.5, size=N), 2
    )

    # 7. Timestamps in 2024 (Asia/Ho_Chi_Minh) with bimodal rush-hour peaks
    days_offset = rng.integers(0, 366, size=N)

    # Mixture model for hour of day: 35% morning peak (7-9), 40% evening peak (17-20), 25% off-peak
    peak_type = rng.choice(
        ["morning", "evening", "offpeak"], size=N, p=[0.35, 0.40, 0.25]
    )
    hours = np.zeros(N, dtype=np.float64)

    m_mask = peak_type == "morning"
    e_mask = peak_type == "evening"
    o_mask = peak_type == "offpeak"

    hours[m_mask] = np.clip(rng.normal(8.0, 0.5, size=np.sum(m_mask)), 7.0, 9.0)
    hours[e_mask] = np.clip(rng.normal(18.5, 0.75, size=np.sum(e_mask)), 17.0, 20.0)
    hours[o_mask] = rng.uniform(0.0, 24.0, size=np.sum(o_mask))

    seconds_into_day = (hours * 3600).astype(int)

    base_ts = pd.Timestamp("2024-01-01 00:00:00", tz="Asia/Ho_Chi_Minh")
    requested_at = pd.Series(
        base_ts
        + pd.to_timedelta(days_offset, unit="D")
        + pd.to_timedelta(seconds_into_day, unit="s")
    )

    # Driver assigned: requested_at + 30-180 seconds
    assign_delays_sec = rng.integers(30, 181, size=N)
    driver_assigned_at = requested_at + pd.to_timedelta(assign_delays_sec, unit="s")

    # Pickup at: driver_assigned_at + 60-600 seconds
    pickup_delays_sec = rng.integers(60, 601, size=N)
    pickup_at = driver_assigned_at + pd.to_timedelta(pickup_delays_sec, unit="s")

    # Dropoff at: pickup_at + actual_duration_min
    dropoff_at = pickup_at + pd.to_timedelta(
        (actual_duration_min * 60).astype(int), unit="s"
    )

    # Convert to Series to apply NaT masking based on booking_status
    driver_assigned_at = pd.Series(driver_assigned_at)
    pickup_at = pd.Series(pickup_at)
    dropoff_at = pd.Series(dropoff_at)

    no_drv_mask = booking_statuses == "no_driver_found"
    cancelled_mask = (booking_statuses == "cancelled_by_passenger") | (
        booking_statuses == "cancelled_by_driver"
    )

    driver_assigned_at[no_drv_mask] = pd.NaT
    pickup_at[no_drv_mask | cancelled_mask] = pd.NaT
    dropoff_at[no_drv_mask | cancelled_mask] = pd.NaT

    # 8. Fares (VND)
    base_fare_map = {"motorbike": 12000.0, "car_4seat": 25000.0, "car_7seat": 35000.0}
    dist_rate_map = {"motorbike": 4500.0, "car_4seat": 7500.0, "car_7seat": 9500.0}
    time_rate_map = {"motorbike": 300.0, "car_4seat": 500.0, "car_7seat": 600.0}

    base_fare = np.array([base_fare_map[vt] for vt in vehicle_types])
    dist_rate = np.array([dist_rate_map[vt] for vt in vehicle_types])
    time_rate = np.array([time_rate_map[vt] for vt in vehicle_types])

    distance_fare = np.round(actual_distance_km * dist_rate, 2)
    time_fare = np.round(actual_duration_min * time_rate, 2)

    # Surge multiplier: 1.0-1.5 normally, 1.5-3.0 during rush hours (07:00-09:00 and 17:00-20:00)
    req_hours = requested_at.dt.hour
    is_rush = ((req_hours >= 7) & (req_hours < 9)) | (
        (req_hours >= 17) & (req_hours < 20)
    )

    surge_multiplier = np.where(
        is_rush,
        rng.uniform(1.5, 3.0, size=N),
        rng.uniform(1.0, 1.5, size=N),
    )
    surge_multiplier = np.round(surge_multiplier, 2)

    # Discount: 0, 5000, 10000, 15000, 20000
    discount = rng.choice(
        [0, 5000, 10000, 15000, 20000], size=N, p=[0.50, 0.20, 0.15, 0.10, 0.05]
    )

    # Toll fee: 0 for most, 10000-30000 for airport trips (~5% of trips)
    is_airport = rng.random(size=N) < 0.05
    toll_fee = np.where(
        is_airport,
        rng.choice([10000, 15000, 20000, 25000, 30000], size=N),
        0,
    )

    # Final fare calculation: (base + distance + time) * surge - discount + toll
    raw_final_fare = (
        (base_fare + distance_fare + time_fare) * surge_multiplier
        - discount
        + toll_fee
    )
    final_fare = np.maximum(raw_final_fare, base_fare)
    final_fare = np.round(final_fare, 2)

    # 9. Payment method
    payment_method = rng.choice(
        ["cash", "e_wallet", "card"], size=N, p=[0.40, 0.35, 0.25]
    )

    # 10. Cancellation reason
    cancellation_reasons_pax = [
        "Change of plans",
        "Driver taking too long",
        "Found alternative transport",
        "Wrong pickup location",
        "High surge price",
    ]
    cancellation_reasons_drv = [
        "Vehicle breakdown",
        "Traffic congestion",
        "Passenger unresponsive",
        "Unsafe pickup location",
        "Personal emergency",
    ]
    cancellation_reasons_nodrv = [
        "No driver available in area",
        "System timeout",
    ]

    cancellation_reason = np.full(N, None, dtype=object)
    pax_canc_mask = booking_statuses == "cancelled_by_passenger"
    drv_canc_mask = booking_statuses == "cancelled_by_driver"
    nodrv_canc_mask = booking_statuses == "no_driver_found"

    cancellation_reason[pax_canc_mask] = rng.choice(
        cancellation_reasons_pax, size=np.sum(pax_canc_mask)
    )
    cancellation_reason[drv_canc_mask] = rng.choice(
        cancellation_reasons_drv, size=np.sum(drv_canc_mask)
    )
    cancellation_reason[nodrv_canc_mask] = rng.choice(
        cancellation_reasons_nodrv, size=np.sum(nodrv_canc_mask)
    )

    # 11. Ratings for completed trips
    driver_rating = np.full(N, np.nan, dtype=np.float64)
    passenger_rating = np.full(N, np.nan, dtype=np.float64)

    completed_mask = booking_statuses == "completed"
    num_completed = np.sum(completed_mask)

    driver_rating[completed_mask] = np.round(
        rng.choice(
            [1.0, 2.0, 3.0, 4.0, 5.0],
            size=num_completed,
            p=[0.01, 0.02, 0.05, 0.22, 0.70],
        ),
        1,
    )
    passenger_rating[completed_mask] = np.round(
        rng.choice(
            [1.0, 2.0, 3.0, 4.0, 5.0],
            size=num_completed,
            p=[0.01, 0.02, 0.04, 0.23, 0.70],
        ),
        1,
    )

    # Construct DataFrame
    df = pd.DataFrame(
        {
            "trip_id": trip_ids,
            "booking_id": booking_ids,
            "passenger_token": passenger_tokens,
            "driver_token": driver_tokens,
            "vehicle_type": vehicle_types,
            "service_city": service_cities,
            "pickup_latitude": pickup_lats,
            "pickup_longitude": pickup_lons,
            "dropoff_latitude": dropoff_lats,
            "dropoff_longitude": dropoff_lons,
            "requested_at": requested_at,
            "driver_assigned_at": driver_assigned_at,
            "pickup_at": pickup_at,
            "dropoff_at": dropoff_at,
            "estimated_distance_km": estimated_distance_km,
            "actual_distance_km": actual_distance_km,
            "estimated_duration_min": estimated_duration_min,
            "actual_duration_min": actual_duration_min,
            "base_fare": base_fare,
            "distance_fare": distance_fare,
            "time_fare": time_fare,
            "surge_multiplier": surge_multiplier,
            "discount": discount,
            "toll_fee": toll_fee,
            "final_fare": final_fare,
            "payment_method": payment_method,
            "booking_status": booking_statuses,
            "cancellation_reason": cancellation_reason,
            "driver_rating": driver_rating,
            "passenger_rating": passenger_rating,
        }
    )

    # Ensure output directory exists
    output_dir = "data/synthetic"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "vietnam_trips.parquet")

    # Save to parquet
    df.to_parquet(output_path, index=False)
    print(f"Dataset successfully saved to: {output_path}")

    # Print Schema & Summary
    print("\n" + "=" * 60)
    print("DATASET SCHEMA & INFO")
    print("=" * 60)
    df.info(memory_usage="deep")

    print("\n" + "=" * 60)
    print("NUMERICAL SUMMARY STATISTICS")
    print("=" * 60)
    print(df.describe().T)

    print("\n" + "=" * 60)
    print("CATEGORICAL DISTRIBUTIONS")
    print("=" * 60)
    for col in ["service_city", "vehicle_type", "booking_status", "payment_method"]:
        print(f"\n--- {col} ---")
        print(df[col].value_counts(normalize=True).apply(lambda x: f"{x:.2%}"))

    print("\n" + "=" * 60)
    print("NULL COUNTS")
    print("=" * 60)
    print(df.isnull().sum()[df.isnull().sum() > 0])

    print("\n" + "=" * 60)
    print("FIRST 3 ROWS PREVIEW")
    print("=" * 60)
    print(df.head(3).T)

    return df


if __name__ == "__main__":
    generate_synthetic_dataset()
