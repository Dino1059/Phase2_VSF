"""
data_demo/verify_demo_parquet.py

Verification script to audit data_demo/vingroup_pilot_landing_demo.parquet and data_demo/fault_manifest.json
"""

import json
from pathlib import Path
import duckdb

BASE_DIR = Path(r"c:\Users\ngant\P-086")
PARQUET_PATH = BASE_DIR / "data_demo" / "vingroup_pilot_landing_demo.parquet"
MANIFEST_PATH = BASE_DIR / "data_demo" / "fault_manifest.json"

def main():
    print("=" * 70)
    print("VERIFYING DEMO PARQUET & FAULT MANIFEST")
    print("=" * 70)

    # 1. Audit Manifest
    assert MANIFEST_PATH.exists(), f"Manifest file missing: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"\n[1] Manifest Audit:")
    print(f"  Dataset Name:            {manifest.get('dataset_name')}")
    print(f"  Total Days:              {manifest.get('total_days')}")
    print(f"  Total Incidents:         {manifest.get('total_incidents')}")
    print(f"  Layer Breakdown:         {manifest.get('fault_summary_by_layer')}")

    incidents = manifest.get("incidents", [])
    print(f"\n  Detailed Incident Schedule:")
    for inc in incidents:
        print(f"    - Day {inc['day_idx']:2d} | [{inc['layer']}] {inc['incident_id']} ({inc['fault_family']}) -> {inc['dataset_table']}.{inc['column']}: {inc['description'][:60]}...")

    # 2. Audit Parquet File
    assert PARQUET_PATH.exists(), f"Parquet file missing: {PARQUET_PATH}"
    conn = duckdb.connect()
    total_rows = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{PARQUET_PATH}')").fetchone()[0]
    min_day = conn.execute(f"SELECT MIN(day_idx) FROM read_parquet('{PARQUET_PATH}')").fetchone()[0]
    max_day = conn.execute(f"SELECT MAX(day_idx) FROM read_parquet('{PARQUET_PATH}')").fetchone()[0]
    
    print(f"\n[2] Parquet File Audit:")
    print(f"  File Path:      {PARQUET_PATH}")
    print(f"  Total Rows:     {total_rows:,}")
    print(f"  Day Index Range: [{min_day} .. {max_day}]")

    print(f"\n  Breakdown by Table:")
    breakdown = conn.execute(f"""
        SELECT dataset_table, COUNT(*) as cnt, MIN(day_idx) as min_d, MAX(day_idx) as max_d
        FROM read_parquet('{PARQUET_PATH}')
        GROUP BY dataset_table
        ORDER BY cnt DESC
    """).fetchall()
    for row in breakdown:
        print(f"    + {row[0]}: {row[1]:,} rows (Days {row[2]}..{row[3]})")

    conn.close()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE: ALL CHECKS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
