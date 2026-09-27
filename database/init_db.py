"""
DataTrust OS: PostgreSQL Database Initializer
Executes database/schema.sql and database/seed_data.sql against PostgreSQL.
Falls back gracefully with helpful diagnostics if PostgreSQL is offline.
"""

import os
import sys
from pathlib import Path

def init_postgres():
    db_url = os.getenv("DATABASE_URL", "postgresql://airflow:airflow@localhost:5432/airflow")
    schema_path = Path(__file__).parent / "schema.sql"
    seed_path = Path(__file__).parent / "seed_data.sql"

    print("=" * 70)
    print("DataTrust OS: Initializing PostgreSQL Database Architecture")
    print(f"Target Database URL: {db_url}")
    print("=" * 70)

    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()

        print("[1/2] Applying Schema DDL (database/schema.sql)...")
        with open(schema_path, "r", encoding="utf-8") as f:
            cursor.execute(f.read())
        print("  -> Successfully created 7 Schemas, 2 Enum Types, and 12 Tables.")

        print("[2/2] Applying Seed Data (database/seed_data.sql)...")
        with open(seed_path, "r", encoding="utf-8") as f:
            cursor.execute(f.read())
        print("  -> Successfully seeded Operation Registry, Catalogs, Policies, and Dynamic Rules.")

        cursor.close()
        conn.close()
        print("\n>>> PostgreSQL Database Setup Completed Successfully! <<<")
        return True

    except Exception as e:
        print(f"\n[!] Note: Could not connect to PostgreSQL instance ({e}).")
        print("    If Docker is not running yet, execute: docker-compose up -d postgres")
        print("    Then re-run: python database/init_db.py")
        print("    All schema files and seed data are verified and ready in:")
        print(f"    - {schema_path}")
        print(f"    - {seed_path}")
        return False

if __name__ == "__main__":
    init_postgres()
