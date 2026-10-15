"""Static safety contract for required parent policy production migration."""

import re
from pathlib import Path

from database.run_migrations import INCREMENTAL_MIGRATIONS


ROOT = Path(__file__).parents[1]
MIGRATION_NAME = "migration_20261015_seed_required_parent_policies.sql"
MIGRATION_PATH = ROOT / "database" / MIGRATION_NAME


def _migration_sql():
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_required_parent_policy_migration_is_registered_last():
    assert MIGRATION_PATH.is_file()
    assert MIGRATION_NAME in INCREMENTAL_MIGRATIONS
    assert INCREMENTAL_MIGRATIONS[-1] == MIGRATION_NAME


def test_required_parent_policy_migration_seeds_ifrs_parent_idempotently():
    sql = _migration_sql()
    normalized = re.sub(r"\s+", " ", sql).upper()

    assert "INSERT INTO POLICY.COMPLIANCE_POLICIES" in normalized
    assert "'POL-IFRS-15'" in normalized
    for required_column in (
        "POLICY_ID",
        "TITLE",
        "JURISDICTION",
        "LEGAL_FRAMEWORK",
        "RAW_POLICY_TEXT",
        "EFFECTIVE_DATE",
    ):
        assert required_column in normalized
    assert "ON CONFLICT (POLICY_ID) DO NOTHING" in normalized
    assert "ON CONFLICT (CLAUSE_ID) DO NOTHING" in normalized
    assert "DO UPDATE" not in normalized


def test_required_parent_policy_migration_is_non_destructive():
    sql = _migration_sql().upper()
    for forbidden in (
        "DROP TABLE",
        "DROP SCHEMA",
        "DROP DATABASE",
        "TRUNCATE ",
        "DELETE FROM",
    ):
        assert forbidden not in sql
