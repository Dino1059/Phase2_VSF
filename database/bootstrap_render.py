"""Initialize a fresh Render PostgreSQL database without resetting existing data."""

import os
import sys
import hashlib

import psycopg2

from database.init_db import init_postgres
from database.run_migrations import DATABASE_DIR, INCREMENTAL_MIGRATIONS, ensure_migration_table, run_migrations


APP_SCHEMAS = ("bronze", "silver", "quarantine", "catalog", "policy", "engine", "orchestration", "audit")
SOD_MIGRATION = "migration_20261016_phase2_sod_schema.sql"
LEGACY_SOD_MIGRATION_CHECKSUM = "50ad9a6381549ae6e123cb926c4d9d0775a70adf7496f8afd88670d08eb8b3ea"
PHASE3_MIGRATION = "migration_20261016_phase3_cross_system.sql"
LEGACY_PHASE3_MIGRATION_CHECKSUM = "bda7e007f9885c45aeb31bb4fcd67a637cad0c1bd14252395d93554bbdb914b7"


def ensure_production_admin(database_url: str) -> bool:
    """Provision the deployment administrator from environment-managed secrets."""
    if os.environ.get("ENVIRONMENT", "").lower() != "production":
        return True
    username = os.environ.get("DATATRUST_API_USER", "datatrust").strip().lower()
    password = os.environ.get("DATATRUST_API_PASSWORD")
    if not password:
        print("DATATRUST_API_PASSWORD is required in production", file=sys.stderr)
        return False
    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sod.users (username, full_name, email, dept, is_active, password_hash)
                VALUES (%s, 'DataTrust Production Administrator', %s, 'Platform Operations', TRUE,
                        crypt(%s, gen_salt('bf')))
                ON CONFLICT (username) DO UPDATE
                SET is_active = TRUE,
                    session_version = CASE
                        WHEN sod.users.password_hash IS NULL
                          OR sod.users.password_hash <> crypt(%s, sod.users.password_hash)
                        THEN sod.users.session_version + 1
                        ELSE sod.users.session_version
                    END,
                    password_hash = crypt(%s, gen_salt('bf'))
                RETURNING id
                """,
                (username, f"{username}@datatrust.local", password, password, password),
            )
            user_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO sod.user_roles (user_id, role_code)
                VALUES (%s, 'ADMIN')
                ON CONFLICT (user_id, role_code) DO UPDATE
                SET revoked_at = NULL, valid_to = NULL
                """,
                (user_id,),
            )
    return True


def ensure_demo_personas() -> bool:
    """Ensure demo personas are populated for multi-party testing."""
    try:
        from database.seed_sod_demo import seed_demo_data
        seed_demo_data()
        return True
    except Exception as e:
        print(f"Notice: demo persona seed: {e}", file=sys.stderr)
        return False


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ANY(%s)",
                (list(APP_SCHEMAS),),
            )
            existing = sorted(row[0] for row in cursor.fetchall())

    if not existing:
        print("Fresh database detected; applying the canonical bootstrap.")
        if not init_postgres():
            return 1

        with psycopg2.connect(database_url) as connection:
            ensure_migration_table(connection)
            with connection.cursor() as cursor:
                for migration_name in INCREMENTAL_MIGRATIONS:
                    migration_path = DATABASE_DIR / migration_name
                    checksum = hashlib.sha256(migration_path.read_bytes()).hexdigest()
                    cursor.execute(
                        """
                        INSERT INTO orchestration.schema_migrations
                            (migration_name, applied_at, checksum)
                        VALUES (%s, CURRENT_TIMESTAMP, %s)
                        ON CONFLICT (migration_name) DO UPDATE
                        SET checksum = EXCLUDED.checksum
                        """,
                        (migration_name, checksum),
                    )
        ensure_demo_personas()
        return 0 if ensure_production_admin(database_url) else 1

    if "orchestration" not in existing:
        print(
            "Refusing destructive bootstrap: application schemas already exist but the database is incomplete: "
            + ", ".join(existing),
            file=sys.stderr,
        )
        return 1

    # Older installs may contain the legacy login role with a password embedded
    # in the original migration. Disable that credential and accept the audited
    # replacement migration checksum before normal checksum enforcement runs.
    compatible_checksum_updates = (
        (
            SOD_MIGRATION,
            LEGACY_SOD_MIGRATION_CHECKSUM,
            hashlib.sha256((DATABASE_DIR / SOD_MIGRATION).read_bytes()).hexdigest(),
        ),
        (
            PHASE3_MIGRATION,
            LEGACY_PHASE3_MIGRATION_CHECKSUM,
            hashlib.sha256((DATABASE_DIR / PHASE3_MIGRATION).read_bytes()).hexdigest(),
        ),
    )
    with psycopg2.connect(database_url) as connection:
        ensure_migration_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DO $cleanup$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
                        ALTER ROLE sod_app NOLOGIN PASSWORD NULL;
                    END IF;
                END
                $cleanup$;
                """
            )
            for migration_name, legacy_checksum, current_checksum in compatible_checksum_updates:
                cursor.execute(
                    """
                    UPDATE orchestration.schema_migrations
                    SET checksum = %s
                    WHERE migration_name = %s AND checksum = %s
                    """,
                    (current_checksum, migration_name, legacy_checksum),
                )

    print("Existing DataTrust database detected; applying pending non-destructive migrations.")
    if not run_migrations():
        return 1
    ensure_demo_personas()
    return 0 if ensure_production_admin(database_url) else 1


if __name__ == "__main__":
    raise SystemExit(main())
