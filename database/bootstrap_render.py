"""Initialize a fresh Render PostgreSQL database without resetting existing data."""

import os
import sys

import psycopg2

from database.init_db import init_postgres


APP_SCHEMAS = ("bronze", "silver", "quarantine", "catalog", "policy", "engine", "orchestration", "audit")


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
        return 0 if init_postgres() else 1

    if "orchestration" not in existing:
        print(
            "Refusing destructive bootstrap: application schemas already exist but the database is incomplete: "
            + ", ".join(existing),
            file=sys.stderr,
        )
        return 1

    print("Existing DataTrust database detected; destructive bootstrap skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
