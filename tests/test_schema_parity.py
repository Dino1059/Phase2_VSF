"""
DataTrust OS: Schema Parity & Ingestion Contract Verification Tests
Offline verification that baseline SQL schemas, migration scripts, and ingestion contracts
remain synchronized with zero drift.
"""

import re
from pathlib import Path
import pytest
import pandas as pd

ROOT = Path(__file__).parents[1]
DATABASE_DIR = ROOT / "database"
DATA_DIR = ROOT / "data" / "vingroup_pii_faulty_testset_3zone"


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_migration_and_baseline_schema_parity():
    """Verify that new columns added in migration are also reflected in baseline schemas."""
    bronze_sql = _read_file(DATABASE_DIR / "schema_bronze_and_catalog.sql")
    silver_sql = _read_file(DATABASE_DIR / "schema_silver_quarantine_warning.sql")
    mig_sql = _read_file(DATABASE_DIR / "migration_20261014_new_columns_and_injected_faults.sql")

    # 1. Fatigue score in bronze telemetry
    assert "fatigue_score" in bronze_sql.lower(), "fatigue_score missing from schema_bronze_and_catalog.sql"
    assert "fatigue_score" in mig_sql.lower(), "fatigue_score missing from migration_20261014_new_columns_and_injected_faults.sql"
    # Raw fatigue_score must NOT be in silver telemetry
    silver_telemetry_section = re.search(
        r"CREATE TABLE IF NOT EXISTS silver\.synthetic_ev_telemetry_ved_ref\s*\((.*?)\);",
        silver_sql,
        re.DOTALL | re.IGNORECASE
    )
    assert silver_telemetry_section is not None, "silver.synthetic_ev_telemetry_ved_ref table not found"
    assert "fatigue_score" not in silver_telemetry_section.group(1).lower(), (
        "Medical privacy violation: raw fatigue_score must NOT be in silver.synthetic_ev_telemetry_ved_ref"
    )

    # 2. Consent lifecycle in dim_customers (both bronze and silver)
    consent_cols = ["consent_at", "consent_withdrawn_at", "delete_requested_at", "delete_completed_at", "opt_out_sharing"]
    for col in consent_cols:
        assert col in bronze_sql.lower(), f"{col} missing from schema_bronze_and_catalog.sql"
        assert col in silver_sql.lower(), f"{col} missing from schema_silver_quarantine_warning.sql"
        assert col in mig_sql.lower(), f"{col} missing from migration_20261014_new_columns_and_injected_faults.sql"

    # 3. Legal basis in dim_drivers (both bronze and silver)
    assert "legal_basis" in bronze_sql.lower(), "legal_basis missing from schema_bronze_and_catalog.sql"
    assert "legal_basis" in silver_sql.lower(), "legal_basis missing from schema_silver_quarantine_warning.sql"
    assert "legal_basis" in mig_sql.lower(), "legal_basis missing from migration_20261014_new_columns_and_injected_faults.sql"


def test_silver_charging_pk_remains_session_id():
    """Verify that silver.acn_charging_mapped retains session_id PRIMARY KEY."""
    silver_sql = _read_file(DATABASE_DIR / "schema_silver_quarantine_warning.sql")
    charging_section = re.search(
        r"CREATE TABLE IF NOT EXISTS silver\.acn_charging_mapped\s*\((.*?)\);",
        silver_sql,
        re.DOTALL | re.IGNORECASE
    )
    assert charging_section is not None
    assert "session_id varchar(100) primary key" in charging_section.group(1).lower()


def test_ingestion_contract_matches_dataset_csv_headers():
    """Verify that EXPECTED_SCHEMA_CONTRACT matches the actual CSV columns on disk."""
    from database.reset_and_ingest_bronze import EXPECTED_SCHEMA_CONTRACT, DATASET_METADATA

    assert DATA_DIR.exists(), f"Dataset directory {DATA_DIR} does not exist"

    for tbl_name, expected_cols in EXPECTED_SCHEMA_CONTRACT.items():
        meta = DATASET_METADATA.get(tbl_name)
        assert meta is not None, f"Missing metadata for {tbl_name}"
        csv_file = DATA_DIR / meta["file"]
        assert csv_file.exists(), f"Missing CSV file: {csv_file}"

        df = pd.read_csv(csv_file, nrows=5)
        csv_cols = list(df.columns)

        # For synthetic_feedback_scenario_driven, subject_zone is inferred, so CSV has 7 columns
        if tbl_name == "synthetic_feedback_scenario_driven":
            assert set(expected_cols) == set(csv_cols), (
                f"Mismatch in {tbl_name}: expected {expected_cols}, CSV has {csv_cols}"
            )
        else:
            missing_in_csv = [c for c in expected_cols if c not in csv_cols]
            assert not missing_in_csv, f"Dataset {tbl_name} is missing columns in CSV: {missing_in_csv}"


def test_production_safety_guards_in_migration_and_init():
    """Verify non-destructive runner guards and init_db warning."""
    init_db_text = _read_file(DATABASE_DIR / "init_db.py")
    migration_runner_text = _read_file(DATABASE_DIR / "run_migrations.py")
    migration_sql = _read_file(DATABASE_DIR / "migration_20261014_new_columns_and_injected_faults.sql")

    # init_db.py must warn against running on existing/production DB
    assert "DO NOT run this script" in init_db_text or "run_migrations.py instead" in init_db_text

    # run_migrations.py must enforce zero destructive keywords
    assert "DROP SCHEMA" in migration_runner_text
    assert "DROP DATABASE" in migration_runner_text

    # migration_20261014_new_columns_and_injected_faults.sql must not have DROP TABLE/SCHEMA
    assert "DROP SCHEMA" not in migration_sql.upper()
    assert "DROP TABLE" not in migration_sql.upper()
    assert "DROP DATABASE" not in migration_sql.upper()


def test_source_row_number_parity():
    """Verify that _source_row_number is present in bronze DDL and migration."""
    bronze_sql = _read_file(DATABASE_DIR / "schema_bronze_and_catalog.sql")
    mig_sql = _read_file(DATABASE_DIR / "migration_20261015_phase2_record_identity.sql")

    assert "_source_row_number" in bronze_sql.lower(), "_source_row_number missing from schema_bronze_and_catalog.sql"
    assert "_source_row_number" in mig_sql.lower(), "_source_row_number missing from migration_20261014_new_columns_and_injected_faults.sql"
