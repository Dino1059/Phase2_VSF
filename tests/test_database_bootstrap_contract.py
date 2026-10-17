"""Static contracts for the fresh-database bootstrap.

These tests deliberately avoid connecting to PostgreSQL.  Their purpose is to
keep the bootstrap entry point, the current schema migrations, and the seed
file from drifting back toward the retired, short dataset identifiers.
"""

import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
DATABASE = ROOT / "database"
INIT_DB = DATABASE / "init_db.py"
SEED_DATA = DATABASE / "seed_data.sql"

CANONICAL_DATASET_IDS = {
    "acn_charging_mapped",
    "dim_customers",
    "dim_drivers",
    "feedback_pii",
    "fleet_index",
    "ride_hailing_xanh_sm_trips",
    "synthetic_ev_telemetry_ved_ref",
    "synthetic_feedback_scenario_driven",
}

LEGACY_DATASET_IDS = {"trips", "customers", "drivers", "charging", "telemetry"}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bootstrap_references_every_existing_sql_file_in_safe_order():
    init_source = _text(INIT_DB)
    ordered_files = [
        "schema_bronze_and_catalog.sql",
        "schema.sql",
        "schema_audit_and_policy_rules.sql",
        "migration_data_driven_lane_rules.sql",
        "migration_update_l3_relations_v2.sql",
        "schema_silver_quarantine_warning.sql",
        "schema_profiling.sql",
        "schema_step3_step5_hardening.sql",
        "migration_run_lineage_snapshots.sql",
        "schema_jurisdiction_policy_isolation.sql",
        "migration_lane_b_policy_packs.sql",
        "migration_20261014_new_columns_and_injected_faults.sql",
        "migration_20261015_phase2_record_identity.sql",
        "migration_20261015_phase2_policy_rules.sql",
        "migration_20261015_seed_required_parent_policies.sql",
        "seed_data.sql",
    ]
    for name in ordered_files:
        assert (DATABASE / name).is_file(), f"missing bootstrap SQL file: {name}"
        assert name in init_source, f"init_db.py does not reference {name}"

    # Match the executable path declarations exactly. A plain substring search
    # confuses schema.sql with migration_*_schema.sql added later in the list.
    positions = []
    for name in ordered_files:
        declaration = (
            f'database_dir / "{name}"'
            if name != "seed_data.sql"
            else 'Path(__file__).parent / "seed_data.sql"'
        )
        positions.append(init_source.index(declaration))
    assert positions == sorted(positions), "bootstrap SQL files are in an unsafe order"


def test_bootstrap_loads_root_env_and_returns_cli_failure_status():
    init_source = _text(INIT_DB)
    ingest_source = _text(DATABASE / "reset_and_ingest_bronze.py")

    assert 'load_dotenv(database_dir.parent / ".env")' in init_source
    assert 'sys.exit(0 if init_postgres() else 1)' in init_source
    assert 'load_dotenv(Path(__file__).resolve().parents[1] / ".env")' in ingest_source


def test_seed_contains_only_non_rule_bootstrap_data():
    seed = _text(SEED_DATA)

    forbidden_rule_or_policy_targets = {
        "catalog.datasets",
        "catalog.columns",
        "policy.compliance_policies",
        "policy.policy_clauses",
        "policy.compliance_rules",
        "policy.data_treatment_rules",
        "engine.compliance_check_rules",
        "engine.data_treatment_rules",
        "engine.field_process_configs",
        "engine.reliability_rules",
    }
    inserted_tables = {
        match.group(1).lower()
        for match in re.finditer(
            r"\bINSERT\s+INTO\s+([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)",
            seed,
            flags=re.IGNORECASE,
        )
    }
    assert inserted_tables.isdisjoint(forbidden_rule_or_policy_targets), (
        "seed_data.sql must not seed catalogs, policies, or executable rules; "
        "the current schema/migrations own those rows"
    )

    quoted_values = {
        value.lower()
        for value in re.findall(r"'([^']+)'", seed)
    }
    assert quoted_values.isdisjoint(LEGACY_DATASET_IDS)

    legacy_id_prefixes = ("CHK-", "TRT-", "ACT-", "POL-VN-ND13", "CLAUSE-ND13")
    assert not any(
        value.upper().startswith(legacy_id_prefixes) for value in quoted_values
    ), "seed_data.sql still contains legacy rule or policy identifiers"


def test_canonical_dataset_contract_is_shared_by_schema_and_ingest():
    bronze_schema = _text(DATABASE / "schema_bronze_and_catalog.sql")
    ingest = _text(DATABASE / "reset_and_ingest_bronze.py")

    for dataset_id in CANONICAL_DATASET_IDS:
        assert f"bronze.{dataset_id}" in bronze_schema
        assert f'"{dataset_id}"' in ingest


def test_current_lane_a_and_lane_b_rule_sources_remain_canonical():
    lane_a = _text(DATABASE / "migration_data_driven_lane_rules.sql")
    lane_a_l3 = _text(DATABASE / "migration_update_l3_relations_v2.sql")
    lane_b = _text(DATABASE / "migration_lane_b_policy_packs.sql")

    assert "INSERT INTO engine.reliability_rules" in lane_a
    assert "L1-ARITHMETIC-TOTAL-FARE" in lane_a
    assert "L1-CONDITION-ZERO-SPEED-RPM" in lane_a
    assert "L3-DEFAULT-RELATIONS" in lane_a_l3

    assert "INSERT INTO policy.policy_packs" in lane_b
    assert "INSERT INTO policy.compliance_rules" in lane_b
    assert "INSERT INTO policy.data_treatment_rules" in lane_b
    for pack_id in (
        "PACK-GLOBAL-PRIVACY-V1",
        "PACK-VN-PRIVACY-V1",
        "PACK-EU-GDPR-V1",
        "PACK-US-CA-PRIVACY-V1",
    ):
        assert pack_id in lane_b

    # Current executable Lane B rows use full ingest IDs (or the global '*').
    assert "'ride_hailing_xanh_sm_trips'" in lane_b
    assert "'synthetic_ev_telemetry_ved_ref'" in lane_b
    assert not any(
        re.search(rf"\b(?:dataset_id|field\.dataset_id)\b[^\n]*'{legacy}'", lane_b)
        for legacy in LEGACY_DATASET_IDS
    )
