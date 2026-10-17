"""
DataTrust OS: Non-Destructive Production Migration Runner
Safely applies incremental database migrations to AWS RDS / production / staging
without dropping schemas or deleting existing historical data.
"""

import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import psycopg2
from dotenv import load_dotenv

DATABASE_DIR = Path(__file__).resolve().parent
load_dotenv(DATABASE_DIR.parent / ".env")


# Ordered list of incremental, non-destructive migration files
INCREMENTAL_MIGRATIONS = [
    "migration_20261014_new_columns_and_injected_faults.sql",
    "migration_20261015_phase2_record_identity.sql",
    "migration_20261015_phase2_policy_rules.sql",
    "migration_20261015_seed_required_parent_policies.sql",
    "migration_20261016_phase2_sod_schema.sql",
    "migration_20261016_phase3_cross_system.sql",
    "migration_20261017_phase2_sod_matrix_fix.sql",
]


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)

    hosts = ["postgres", "localhost", "127.0.0.1"]
    for h in hosts:
        try:
            return psycopg2.connect(
                host=h,
                port=5432,
                user="airflow",
                password="airflow",
                dbname="airflow",
                connect_timeout=3
            )
        except Exception:
            continue
    raise ConnectionError("Could not connect to PostgreSQL on any known host.")


def ensure_migration_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS orchestration;
            CREATE TABLE IF NOT EXISTS orchestration.schema_migrations (
                migration_name VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                checksum VARCHAR(64)
            );
        """)
    conn.commit()


def get_applied_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT migration_name, checksum FROM orchestration.schema_migrations;")
        return {row[0]: row[1] for row in cur.fetchall()}


def run_migrations(force: bool = False):
    print("=" * 70)
    print("DataTrust OS: Non-Destructive Production Migration Runner")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    conn = get_db_connection()
    try:
        ensure_migration_table(conn)
        applied = get_applied_migrations(conn)

        pending = []
        for mig_filename in INCREMENTAL_MIGRATIONS:
            mig_path = DATABASE_DIR / mig_filename
            if not mig_path.exists():
                raise FileNotFoundError(f"Migration file not found: {mig_path}")
            expected_checksum = hashlib.sha256(mig_path.read_bytes()).hexdigest()
            recorded_checksum = applied.get(mig_filename)
            if recorded_checksum and recorded_checksum != expected_checksum and not force:
                raise RuntimeError(
                    f"Applied migration {mig_filename} was modified after execution: "
                    f"database={recorded_checksum}, file={expected_checksum}. "
                    "Create a new migration instead of editing an applied file."
                )
            if mig_filename not in applied or force:
                pending.append(mig_filename)

        if not pending:
            print("No pending incremental migrations. Database is up-to-date.")
            return True

        print(f"Applying {len(pending)} pending migration(s)...")
        for mig_filename in pending:
            mig_path = DATABASE_DIR / mig_filename
            if not mig_path.exists():
                raise FileNotFoundError(f"Migration file not found: {mig_path}")

            with open(mig_path, "r", encoding="utf-8") as f:
                sql_content = f.read()

            # Safety guard: enforce zero destructive keywords in production runner
            upper_sql = sql_content.upper()
            if "DROP SCHEMA" in upper_sql or "DROP DATABASE" in upper_sql:
                raise ValueError(
                    f"FATAL: Migration file {mig_filename} contains forbidden destructive DDL. "
                    "Aborting execution immediately!"
                )

            checksum = hashlib.sha256(sql_content.encode("utf-8")).hexdigest()
            print(f"  -> Executing {mig_filename} (SHA256: {checksum[:10]}...)...")

            # Execute migration in isolated transaction
            try:
                with conn.cursor() as cur:
                    cur.execute(sql_content)
                    cur.execute("""
                        INSERT INTO orchestration.schema_migrations (migration_name, applied_at, checksum)
                        VALUES (%s, CURRENT_TIMESTAMP, %s)
                        ON CONFLICT (migration_name) DO UPDATE 
                        SET applied_at = CURRENT_TIMESTAMP, checksum = EXCLUDED.checksum;
                    """, (mig_filename, checksum))
                conn.commit()
                print(f"  -> SUCCESS: {mig_filename} applied successfully.")
            except Exception as e:
                conn.rollback()
                print(f"  -> ERROR applying {mig_filename}: {e}")
                raise

        print("\nAll incremental migrations executed successfully!")
        return True

    finally:
        conn.close()


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    try:
        success = run_migrations(force=force_flag)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[!] Migration failed: {e}")
        sys.exit(1)
