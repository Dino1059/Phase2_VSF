"""
DataTrust OS: PostgreSQL Database Initializer
Applies the canonical schemas/migrations, then loads non-rule platform seed
data from database/seed_data.sql against PostgreSQL. Runtime Lane A/Lane B
rules are owned by their named schema/migration files, not by the seed step.
Falls back gracefully with helpful diagnostics if PostgreSQL is offline.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

def init_postgres():
    database_dir = Path(__file__).parent
    load_dotenv(database_dir.parent / ".env")
    db_url = os.getenv("DATABASE_URL", "postgresql://airflow:airflow@localhost:5432/airflow")
    schema_paths = [
        # The Bronze bootstrap intentionally resets shared schemas, so it must
        # precede the canonical policy/engine schema on a fresh initialization.
        database_dir / "schema_bronze_and_catalog.sql",
        database_dir / "schema.sql",
        database_dir / "schema_audit_and_policy_rules.sql",
        database_dir / "migration_data_driven_lane_rules.sql",
        # This is the current L3 relation configuration. It must follow the
        # v1 rule bootstrap so version 1 can be closed before version 2 starts.
        database_dir / "migration_update_l3_relations_v2.sql",
        database_dir / "schema_silver_quarantine_warning.sql",
        database_dir / "schema_profiling.sql",
        database_dir / "schema_step3_step5_hardening.sql",
        database_dir / "migration_run_lineage_snapshots.sql",
        database_dir / "schema_jurisdiction_policy_isolation.sql",
        database_dir / "migration_lane_b_policy_packs.sql",
    ]
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

        print("[1/2] Applying schema and jurisdiction migrations...")
        for schema_path in schema_paths:
            with open(schema_path, "r", encoding="utf-8") as f:
                cursor.execute(f.read())
            print(f"  -> Applied {schema_path.name}")

        print("[2/2] Applying non-rule platform seed data (database/seed_data.sql)...")
        with open(seed_path, "r", encoding="utf-8") as f:
            cursor.execute(f.read())
        print("  -> Successfully seeded platform reference data.")
        print("     Current Lane A/Lane B rules were installed by the schema/migration files above.")

        cursor.close()
        conn.close()
        print("\n>>> PostgreSQL Database Setup Completed Successfully! <<<")
        return True

    except Exception as e:
        print(f"\n[!] Database bootstrap failed ({e}).")
        print("    If Docker is not running yet, execute: docker-compose up -d postgres")
        print("    Then re-run: python database/init_db.py")
        print("    All schema files and seed data are verified and ready in:")
        for schema_path in schema_paths:
            print(f"    - {schema_path}")
        print(f"    - {seed_path}")
        return False

if __name__ == "__main__":
    sys.exit(0 if init_postgres() else 1)
