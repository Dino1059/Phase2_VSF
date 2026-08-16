import os
import json
import requests
import pandas as pd

API_URL = "https://archive-api.open-meteo.com/v1/archive"
LATITUDE = 10.8231
LONGITUDE = 106.6297
HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "weather_code",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
]

JSON_OUT = "data/weather/hcmc_weather_2024.json"
PARQUET_OUT = "data/weather/hcmc_weather_2024.parquet"

def fetch_weather():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "hourly": ",".join(HOURLY_VARS),
    }

    try:
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "hourly" in data and "time" in data["hourly"]:
            print(f"Successfully fetched full year data in single request ({len(data['hourly']['time'])} rows).")
            return data
    except Exception as e:
        print(f"Full year fetch failed ({e}). Falling back to quarterly requests...")

    # Fallback to quarterly fetches if date range exceeds API limits
    quarters = [
        ("2024-01-01", "2024-03-31"),
        ("2024-04-01", "2024-06-30"),
        ("2024-07-01", "2024-09-30"),
        ("2024-10-01", "2024-12-31"),
    ]
    all_hourly = {}
    merged_response = None

    for start_date, end_date in quarters:
        q_params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(HOURLY_VARS),
        }
        resp = requests.get(API_URL, params=q_params, timeout=30)
        resp.raise_for_status()
        q_data = resp.json()

        if merged_response is None:
            merged_response = q_data
            all_hourly = {k: list(v) for k, v in q_data["hourly"].items()}
        else:
            for k, v in q_data["hourly"].items():
                if k in all_hourly:
                    all_hourly[k].extend(v)

    merged_response["hourly"] = all_hourly
    print(f"Successfully fetched and merged quarterly data ({len(all_hourly['time'])} rows).")
    return merged_response

def main():
    os.makedirs("data/weather", exist_ok=True)

    data = fetch_weather()

    # Save raw JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved raw JSON to {JSON_OUT}")

    # Convert to DataFrame
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])

    # Save Parquet
    df.to_parquet(PARQUET_OUT, index=False)
    print(f"Saved Parquet to {PARQUET_OUT}")

    # Summary stats
    print("\n--- Summary Statistics ---")
    print(f"Total Rows: {len(df)}")
    print(f"Date Range: {df['time'].min()} to {df['time'].max()}")
    print("\nNumeric Columns Summary:")
    print(df.describe().T[["count", "mean", "std", "min", "50%", "max"]])

if __name__ == "__main__":
    main()
