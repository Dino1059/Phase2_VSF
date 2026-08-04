#!/usr/bin/env python3
"""
Unified Feedback Ingestion Pipeline.
Phase 2 Data Ingestion - DataTrust OS v4.0

Ingests scraped feedback CSVs from data/scraped/*.csv into DuckDB.
Deduplicates records by hash(review_text + source + timestamp).
Records immutable raw lineage in raw_snapshots table.
"""

import glob
import hashlib
import os
import sys
import uuid
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db.connection import get_db


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def ingest_scraped_data():
    """Ingest all CSVs from data/scraped/*.csv into DuckDB xanhsm_feedback table."""
    db = get_db()
    db.init_schema()

    scraped_dir = os.path.join(PROJECT_ROOT, "data", "scraped")
    csv_files = glob.glob(os.path.join(scraped_dir, "*.csv"))

    if not csv_files:
        print(f"[INGEST WARNING] No CSV files found in {scraped_dir}")
        return

    print(f"[INGEST] Found {len(csv_files)} scraped CSV file(s) in {scraped_dir}")

    # Fetch existing records to prevent re-ingesting duplicates if run multiple times
    existing_records = db.execute("SELECT review_text, source, timestamp FROM xanhsm_feedback")
    seen_hashes = set()
    for r_text, r_src, r_ts in existing_records:
        h = hashlib.sha256(f"{str(r_text)}{str(r_src)}{str(r_ts)}".encode("utf-8")).hexdigest()
        seen_hashes.add(h)

    # Get max current ID in xanhsm_feedback table
    max_id_res = db.execute("SELECT COALESCE(MAX(id), 0) FROM xanhsm_feedback")
    current_id = max_id_res[0][0] if max_id_res else 0

    total_ingested = 0
    total_deduped = 0
    records_per_source = {}

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        source_name = os.path.splitext(filename)[0]

        df = pd.read_csv(file_path)
        if df.empty:
            print(f"[INGEST SKIP] {filename} is empty")
            continue

        file_hash = compute_file_sha256(file_path)
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"

        # Insert record into raw_snapshots table
        db.execute(
            """
            INSERT INTO raw_snapshots (id, source_name, file_path, sha256_hash, row_count, column_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [snapshot_id, source_name, file_path, file_hash, len(df), len(df.columns)],
        )

        rows_to_insert = []
        source_ingested_count = 0

        for _, row in df.iterrows():
            review_text = str(row.get("review_text", "")).strip()
            source = str(row.get("source", source_name)).strip()
            timestamp = str(row.get("timestamp", "")).strip()

            if not review_text:
                continue

            # Compute hash for deduplication
            dedup_hash = hashlib.sha256(
                f"{review_text}{source}{timestamp}".encode("utf-8")
            ).hexdigest()

            if dedup_hash in seen_hashes:
                total_deduped += 1
                continue

            seen_hashes.add(dedup_hash)
            current_id += 1

            rating = float(row["rating"]) if ("rating" in row and pd.notnull(row["rating"])) else None
            location = str(row.get("location", row.get("category", ""))) or None
            normalized_text = str(row.get("normalized_text", review_text))

            rows_to_insert.append((
                current_id,
                review_text,
                normalized_text,
                rating,
                location,
                timestamp,
                source,
                None,  # aspects JSON
                snapshot_id,
            ))
            source_ingested_count += 1

        if rows_to_insert:
            db.execute_many(
                """
                INSERT INTO xanhsm_feedback 
                (id, review_text, normalized_text, rating, location, timestamp, source, aspects, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows_to_insert,
            )

        records_per_source[source_name] = source_ingested_count
        total_ingested += source_ingested_count
        print(f"[INGEST SUCCESS] File '{filename}': snapshot '{snapshot_id}', ingested {source_ingested_count} unique rows.")

    print("\n==================================================")
    print("📊 UNIFIED SCRAPED FEEDBACK INGESTION SUMMARY")
    print("==================================================")
    for src, count in records_per_source.items():
        print(f"  • Source '{src}': {count} new unique records")
    print(f"  • Total new unique records ingested: {total_ingested}")
    print(f"  • Total duplicate records skipped: {total_deduped}")
    print("==================================================\n")


if __name__ == "__main__":
    ingest_scraped_data()
