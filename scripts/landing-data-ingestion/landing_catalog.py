"""Landing catalog scanner - Giai doan 2b
Scan the single landing parquet and populate landing_day_snapshots (one row per day_idx).
"""
import duckdb, os, hashlib, json
from datetime import datetime

try:
    from src.config import get_settings
    from src.db.connection import get_db
    _rel_pq = get_settings().landing_parquet_path
    PQ_PATH = _rel_pq if os.path.isabs(_rel_pq) else os.path.join(get_db().project_root, _rel_pq)
except Exception:
    PQ_PATH = r"c:\Users\ngant\P-086\data_demo\vingroup_pilot_landing_demo.parquet"
OUT_DIR = r"c:\Users\ngant\P-086\.ngan_tmp_local"

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

print("=" * 60)
print("LANDING CATALOG SCANNER")
print("=" * 60)

# Check parquet exists
if not os.path.exists(PQ_PATH):
    print(f"ERROR: {PQ_PATH} not found!")
    print("Run seed_landing_parquet.py first.")
    exit(1)

file_hash = compute_sha256(PQ_PATH)
file_size = os.path.getsize(PQ_PATH) / (1024 * 1024)
print(f"\nParquet: {PQ_PATH}")
print(f"SHA-256: {file_hash}")
print(f"Size:    {file_size:.2f} MB")

# Scan parquet for per-day, per-table stats
conn = duckdb.connect()
print("\n[1] Scanning landing parquet for day/table stats...")

# Total stats
total = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{PQ_PATH}')").fetchone()[0]
print(f"    Total rows: {total:,}")

# Per-day + per-table breakdown
scan_results = conn.execute(f"""
    SELECT 
        day_idx,
        dataset_table,
        COUNT(*) as row_count
    FROM read_parquet('{PQ_PATH}')
    WHERE day_idx IS NOT NULL
    GROUP BY day_idx, dataset_table
    ORDER BY day_idx, dataset_table
""").fetchall()

# Pivot to per-day
from collections import defaultdict
day_stats = defaultdict(lambda: {"tables": {}, "total": 0})
for day_idx, tbl, cnt in scan_results:
    day_stats[day_idx]["tables"][tbl] = cnt
    day_stats[day_idx]["total"] += cnt

print(f"    Days found: {len(day_stats)}")
for day in sorted(day_stats.keys()):
    tables = day_stats[day]["tables"]
    print(f"    day_idx={day}: {day_stats[day]['total']:,} rows across {[t for t in tables]}")

conn.close()

# Populate landing_day_snapshots (idempotent)
print("\n[2] Populating landing_day_snapshots...")
conn2 = duckdb.connect(DB_PATH)

# Build snapshot_id = f"SNAP_{day_idx:03d}"
# Idempotent: DELETE then INSERT
inserted = 0
skipped = 0
for day_idx in sorted(day_stats.keys()):
    snapshot_id = f"SNAP_{int(day_idx):03d}"
    row_count = day_stats[day_idx]["total"]
    
    # Check if already exists
    existing = conn2.execute(
        "SELECT snapshot_id FROM demo_ops.landing_day_snapshots WHERE snapshot_id = ?",
        [snapshot_id]
    ).fetchone()
    
    if existing:
        # Update if hash changed or row_count differs
        conn2.execute("""
            UPDATE demo_ops.landing_day_snapshots
            SET file_sha256 = ?, row_count = ?, source_file = ?
            WHERE snapshot_id = ?
        """, [file_hash, row_count, PQ_PATH, snapshot_id])
        print(f"  UPDATED {snapshot_id}: {row_count:,} rows (SHA256 updated)")
    else:
        conn2.execute("""
            INSERT INTO demo_ops.landing_day_snapshots 
                (snapshot_id, source_file, day_idx, file_sha256, row_count, fault_injected, is_activated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [snapshot_id, PQ_PATH, int(day_idx), file_hash, row_count, False, False])
        print(f"  INSERTED {snapshot_id}: {row_count:,} rows")
    inserted += 1

conn2.close()

# Final verify
print("\n[3] Final verification...")
conn3 = duckdb.connect(DB_PATH, read_only=True)
final = conn3.execute("""
    SELECT snapshot_id, day_idx, row_count, file_sha256, 
           fault_injected, is_activated, activated_at
    FROM demo_ops.landing_day_snapshots
    ORDER BY day_idx
""").fetchall()
print(f"  Total snapshots in DB: {len(final)}")
for row in final:
    print(f"  {row[0]} | day={row[1]} | rows={row[2]:,} | activated={row[5]}")

conn3.close()

# Save summary
summary = {
    "timestamp": datetime.now().isoformat(),
    "parquet_sha256": file_hash,
    "parquet_size_mb": round(file_size, 2),
    "total_rows": total,
    "days_scanned": len(day_stats),
    "day_range": [int(min(day_stats.keys())), int(max(day_stats.keys()))],
    "per_day": {
        int(d): {"total": day_stats[d]["total"], "tables": day_stats[d]["tables"]}
        for d in day_stats
    }
}
with open(os.path.join(OUT_DIR, "landing_catalog_summary.json"), "w") as f:
    json.dump(summary, f, indent=2)
print(f"\n  Summary saved to: {OUT_DIR}/landing_catalog_summary.json")

print("\n" + "=" * 60)
print("DONE - Landing catalog populated")
print("=" * 60)
