"""Seed landing parquet - Giai doan 2
Merge all CSVs from vingroup_faulty_pilot_dataset into single Parquet with day_idx + dataset_table.
Uses pandas to handle different column sets per CSV (pad with NULL/NaN).
"""
import duckdb, os, hashlib, json
import pandas as pd
from datetime import datetime

SRC_DIR = r"c:\Users\ngant\P-086\data_new\vingroup_faulty_pilot_dataset"
OUT_PQ = r"c:\Users\ngant\P-086\data_new\vingroup_pilot_landing.parquet"
OUT_DIR = r"c:\Users\ngant\P-086\.ngan_tmp_local"
os.makedirs(OUT_DIR, exist_ok=True)

# CSV files and their logical table names
CSV_MAPPING = {
    "synthetic_ev_telemetry_ved_ref.csv": "ev_telemetry",
    "ride_hailing_xanh_sm_trips.csv": "ride_trips",
    "acn_charging_mapped.csv": "acn_charging",
    "fleet_index.csv": "fleet_index",
    "lp_benchmark_uit_vsfc.csv": "lp_benchmark",
    "synthetic_feedback_scenario_driven.csv": "feedback",
}

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

print("=" * 60)
print("SEED LANDING PARQUET")
print("=" * 60)

# Step 1: Count rows per CSV
print("\n[1] CSV row counts:")
conn = duckdb.connect()
row_counts = {}
for csv_file, table_name in CSV_MAPPING.items():
    csv_path = os.path.join(SRC_DIR, csv_file)
    if not os.path.exists(csv_path):
        print(f"  SKIP {csv_file} - not found")
        continue
    cnt = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{csv_path}')").fetchone()[0]
    row_counts[table_name] = cnt
    print(f"  {table_name}: {cnt:,} rows")
conn.close()

# Step 2: Read all CSVs via pandas (handles varying column sets)
print("\n[2] Reading CSVs via pandas...")
dfs = []
for csv_file, table_name in CSV_MAPPING.items():
    csv_path = os.path.join(SRC_DIR, csv_file)
    if not os.path.exists(csv_path):
        print(f"  SKIP {csv_file} - not found")
        continue
    df = pd.read_csv(csv_path)
    # Add metadata columns
    df["dataset_table"] = table_name
    if "day_idx" in df.columns:
        df["day_idx"] = df["day_idx"].astype("Int64")
    elif "assigned_day_index" in df.columns:
        # Map assigned_day_index -> day_idx (e.g. ride_trips, acn_charging, feedback)
        df["day_idx"] = df["assigned_day_index"].astype("Int64")
    else:
        # Tables without any day index (e.g. fleet_index) -> day_idx = NULL
        df["day_idx"] = pd.array([None] * len(df), dtype=pd.Int64Dtype())
    dfs.append(df)
    print(f"  + {table_name}: {len(df):,} rows x {len(df.columns)} cols")

# Step 3: Concatenate all (pandas auto-pads missing cols with NaN)
print("\n[3] Concatenating all CSVs...")
combined = pd.concat(dfs, ignore_index=True, sort=False)
total_rows = len(combined)
print(f"  Total rows: {total_rows:,}")
print(f"  Total cols: {len(combined.columns)}")

# Step 4: Write parquet
print("\n[4] Writing parquet...")
combined.to_parquet(OUT_PQ, index=False, compression="zstd")
print(f"  Saved to: {OUT_PQ}")
size_mb = os.path.getsize(OUT_PQ) / (1024 * 1024)
print(f"  File size: {size_mb:.2f} MB")

# Step 5: Verify via DuckDB
print("\n[5] Verification:")
conn2 = duckdb.connect()
total = conn2.execute(f"SELECT COUNT(*) FROM read_parquet('{OUT_PQ}')").fetchone()[0]
min_day = conn2.execute(f"SELECT MIN(day_idx) FROM read_parquet('{OUT_PQ}')").fetchone()[0]
max_day = conn2.execute(f"SELECT MAX(day_idx) FROM read_parquet('{OUT_PQ}')").fetchone()[0]
dist_tables = conn2.execute(f"SELECT COUNT(DISTINCT dataset_table) FROM read_parquet('{OUT_PQ}')").fetchone()[0]

print(f"  COUNT(*): {total:,}")
print(f"  MIN(day_idx): {min_day}")
print(f"  MAX(day_idx): {max_day}")
print(f"  COUNT(DISTINCT dataset_table): {dist_tables}")

# Per-table breakdown
print("\n[6] Per-table breakdown:")
breakdown = conn2.execute(f"""
    SELECT dataset_table, COUNT(*) as cnt, MIN(day_idx) as min_day, MAX(day_idx) as max_day
    FROM read_parquet('{OUT_PQ}')
    GROUP BY dataset_table
    ORDER BY cnt DESC
""").fetchall()
for row in breakdown:
    print(f"  {row[0]}: {row[1]:,} rows, day_idx [{row[2]} - {row[3]}]")

# Sample columns
print("\n[7] Columns in landing parquet:")
cols = conn2.execute(f"SELECT * FROM read_parquet('{OUT_PQ}') LIMIT 1").df().columns.tolist()
for i, c in enumerate(cols):
    print(f"  {i+1:2d}. {c}")

conn2.close()

# Step 8: SHA-256
print("\n[8] SHA-256 hash:")
file_hash = compute_sha256(OUT_PQ)
print(f"  {file_hash}")

# Save hash to file
hash_file = os.path.join(OUT_DIR, "landing_parquet_hash.json")
with open(hash_file, "w") as f:
    json.dump({
        "file": OUT_PQ,
        "sha256": file_hash,
        "total_rows": total,
        "min_day_idx": int(min_day) if min_day is not None else None,
        "max_day_idx": int(max_day) if max_day is not None else None,
        "table_count": dist_tables,
        "file_size_mb": round(size_mb, 2),
        "timestamp": datetime.now().isoformat(),
        "per_table": {row[0]: row[1] for row in breakdown}
    }, f, indent=2)
print(f"\n  Hash saved to: {hash_file}")

print("\n" + "=" * 60)
print("DONE - Landing parquet ready for ingestion pipeline")
print("=" * 60)
