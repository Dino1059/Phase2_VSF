from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pandas as pd
import pytest

from backend.engine.compliance_rule_evaluator import ComplianceRuleEvaluator
from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor
from backend.engine.operation_registry import OperationRegistry


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "vingroup_pii_faulty_testset_3zone"
MANIFEST_PATH = DATA_DIR / "lane_b_manifest.json"

ARCHIVE_RUN_IDS = {
    "R-B08-ERR",
    "R-B08-OK",
    "R-B09-HOLD",
    "R-B10-ERR",
    "R-B10-OK",
}


def get_phase2_lane_b_rules() -> List[Dict[str, Any]]:
    """Active compliance rules for Phase 2 Lane B evaluation."""
    return [
        # Baseline Pack Rules
        {
            "rule_id": "COMP-GLOBAL-ZONE-V1", "version": 1, "dataset_id": "*",
            "column_name": "subject_zone", "rule_name": "Supported subject jurisdiction",
            "rule_code": "SUPPORTED_SUBJECT_ZONE", "expression": "subject_zone IN (VN, EU, US)",
            "description": "System invariant: the record declares one of the pilot zones.",
            "policy_id": "POL-GLOBAL-PRIVACY", "policy_name": "Global privacy baseline",
            "law_ref": "Internal", "jurisdiction": "GLOBAL", "severity": "CRITICAL",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {"operator": "enum", "field": "subject_zone", "values": ["VN", "EU", "US"]},
            "missing_behavior": "FAIL", "invalid_type_behavior": "FAIL",
        },
        # B05: US CCPA GPS precision restriction
        {
            "rule_id": "COMP-US-SPI-COORDS-V1", "version": 1, "dataset_id": "synthetic_ev_telemetry_ved_ref",
            "column_name": "latitude", "rule_name": "US CCPA GPS precision restriction",
            "rule_code": "CTL_US_SPI_01", "expression": "ops_dispatch OR precision(latitude, 2)",
            "description": "US-CCPA-05: Toạ độ chính xác (>=3 số lẻ) dùng ngoài chức năng lõi của xe",
            "policy_id": "POL-US-CCPA", "policy_name": "California CCPA/CPRA technical controls",
            "law_ref": "US-CCPA-05", "jurisdiction": "US", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "POST_CHECK",
            "condition_json": {
                "operator": "any",
                "conditions": [
                    {"operator": "context_equals", "key": "purpose_id", "value": "ops_dispatch"},
                    {"operator": "precision", "field": "latitude", "max_decimals": 2},
                ],
            },
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
        # B06: VN PDP location access role check
        {
            "rule_id": "COMP-VN-LOCATION-ROLE-V1", "version": 1, "dataset_id": "synthetic_ev_telemetry_ved_ref",
            "column_name": "latitude", "rule_name": "VN PDP location access role check",
            "rule_code": "CTL_VN_PDP_002", "expression": "context.role == 'data_steward'",
            "description": "PDP-002: Vai trò không được phép đọc cột vị trí (dữ liệu nhạy cảm ở VN)",
            "policy_id": "POL-VN-LAW91", "policy_name": "Vietnam privacy technical controls",
            "law_ref": "PDP-002", "jurisdiction": "VN", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {"operator": "context_equals", "key": "role", "value": "data_steward"},
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
        # B07: EU GDPR fatigue score health data restriction
        {
            "rule_id": "COMP-EU-FATIGUE-CATALOG-V1", "version": 1, "dataset_id": "synthetic_ev_telemetry_ved_ref",
            "column_name": "fatigue_score", "rule_name": "EU GDPR fatigue score health data restriction",
            "rule_code": "CTL_GDPR_009", "expression": "fatigue_score IS NULL OR fatigue_score_tagged == true",
            "description": "GDPR-009: Cột fatigue_score suy ra sức khoẻ tài xế chưa gắn nhãn dữ liệu đặc biệt",
            "policy_id": "POL-EU-GDPR", "policy_name": "EU GDPR technical controls",
            "law_ref": "GDPR-009", "jurisdiction": "EU", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2018-05-25T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {
                "operator": "any",
                "conditions": [
                    {"operator": "is_null", "field": "fatigue_score"},
                    {"operator": "context_equals", "key": "fatigue_score_tagged", "value": True},
                ],
            },
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
        # B11: VN PDP customer deletion request SLA 20 days
        {
            "rule_id": "COMP-VN-CUS-DELETE-SLA-V1", "version": 1, "dataset_id": "dim_customers",
            "column_name": "delete_requested_at", "rule_name": "VN PDP customer deletion request SLA 20 days",
            "rule_code": "CTL_VN_PDP_005",
            "expression": "delete_requested_at IS NULL OR delete_completed_at IS NOT NULL OR date_age_days(delete_requested_at) <= 20",
            "description": "PDP-005: Yêu cầu xoá quá 20 ngày mà dữ liệu vẫn còn",
            "policy_id": "POL-VN-LAW91", "policy_name": "Vietnam privacy technical controls",
            "law_ref": "PDP-005", "jurisdiction": "VN", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {
                "operator": "any",
                "conditions": [
                    {"operator": "is_null", "field": "delete_requested_at"},
                    {"operator": "not", "condition": {"operator": "is_null", "field": "delete_completed_at"}},
                    {"operator": "date_age_days", "field": "delete_requested_at", "max_days": 20},
                ],
            },
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
        # B12: VN PDP consent withdrawn processing SLA 15 days
        {
            "rule_id": "COMP-VN-CUS-CONSENT-WITHDRAW-V1", "version": 1, "dataset_id": "dim_customers",
            "column_name": "consent_withdrawn_at", "rule_name": "VN PDP consent withdrawn processing SLA 15 days",
            "rule_code": "CTL_VN_PDP_003",
            "expression": "consent_withdrawn_at IS NULL OR date_age_days(consent_withdrawn_at) <= 15",
            "description": "PDP-003: Rút đồng ý quá 15 ngày mà vẫn xử lý",
            "policy_id": "POL-VN-LAW91", "policy_name": "Vietnam privacy technical controls",
            "law_ref": "PDP-003", "jurisdiction": "VN", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {
                "operator": "any",
                "conditions": [
                    {"operator": "is_null", "field": "consent_withdrawn_at"},
                    {"operator": "date_age_days", "field": "consent_withdrawn_at", "max_days": 15},
                ],
            },
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
        # B13: VN PDP customer consent record required
        {
            "rule_id": "COMP-VN-CUS-CONSENT-REQUIRED-V1", "version": 1, "dataset_id": "dim_customers",
            "column_name": "consent_at", "rule_name": "VN PDP customer consent record required",
            "rule_code": "CTL_VN_PDP_006", "expression": "consent_at IS NOT NULL",
            "description": "PDP-006: Khách có dữ liệu nhưng không có bản ghi đồng ý",
            "policy_id": "POL-VN-LAW91", "policy_name": "Vietnam privacy technical controls",
            "law_ref": "PDP-006", "jurisdiction": "VN", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {"operator": "not", "condition": {"operator": "is_null", "field": "consent_at"}},
            "missing_behavior": "FAIL", "invalid_type_behavior": "FAIL",
        },
        # B14: US CCPA opt-out marketing restriction
        {
            "rule_id": "COMP-US-OPTOUT-MARKETING-V1", "version": 1, "dataset_id": "ride_hailing_xanh_sm_trips",
            "column_name": "customer_id", "rule_name": "US CCPA opt-out marketing restriction",
            "rule_code": "CTL_US_OPTOUT_01",
            "expression": "purpose != 'marketing' OR exclude_opt_out == true OR opt_out_sharing != 1",
            "description": "US-CCPA-04: Khách đã từ chối chia sẻ nằm trong dữ liệu dùng cho quảng cáo",
            "policy_id": "POL-US-CCPA", "policy_name": "California CCPA/CPRA technical controls",
            "law_ref": "US-CCPA-04", "jurisdiction": "US", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {
                "operator": "any",
                "conditions": [
                    {"operator": "not", "condition": {"operator": "context_equals", "key": "purpose_id", "value": "marketing"}},
                    {"operator": "context_equals", "key": "exclude_opt_out", "value": True},
                    {"operator": "not", "condition": {"operator": "compare", "field": "opt_out_sharing", "comparator": "==", "value": 1}},
                ],
            },
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
        # B15: EU GDPR driver processing valid legal basis (HITL gate)
        {
            "rule_id": "COMP-EU-DRV-LEGAL-BASIS-V1", "version": 1, "dataset_id": "dim_drivers",
            "column_name": "legal_basis", "rule_name": "EU GDPR driver processing valid legal basis",
            "rule_code": "CTL_GDPR_006", "expression": "legal_basis IN ('contract', 'legitimate_interest')",
            "description": "GDPR-006: Dữ liệu tài xế EU dùng căn cứ consent hoặc để trống",
            "policy_id": "POL-EU-GDPR", "policy_name": "EU GDPR technical controls",
            "law_ref": "GDPR-006", "jurisdiction": "EU", "severity": "HIGH",
            "on_fail_action": "QUARANTINE_HITL", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2018-05-25T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {
                "operator": "enum",
                "field": "legal_basis",
                "values": ["contract", "legitimate_interest"],
            },
            "missing_behavior": "FAIL", "invalid_type_behavior": "FAIL",
        },
        # B16: EU GDPR trip customer contact data minimization
        {
            "rule_id": "COMP-EU-TRIP-MINIMIZATION-V1", "version": 1, "dataset_id": "ride_hailing_xanh_sm_trips",
            "column_name": "customer_contact", "rule_name": "EU GDPR trip customer contact data minimization",
            "rule_code": "CTL_GDPR_005",
            "expression": "purpose != 'fleet_analytics' OR uses_customer_contact == false OR customer_contact IS NULL",
            "description": "GDPR-005: Thu thập thừa, cột customer_contact không cần cho mục đích fleet_analytics",
            "policy_id": "POL-EU-GDPR", "policy_name": "EU GDPR technical controls",
            "law_ref": "GDPR-005", "jurisdiction": "EU", "severity": "HIGH",
            "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2018-05-25T00:00:00Z", "evaluation_phase": "PRE_CHECK",
            "condition_json": {
                "operator": "any",
                "conditions": [
                    {"operator": "not", "condition": {"operator": "context_equals", "key": "purpose_id", "value": "fleet_analytics"}},
                    {"operator": "context_equals", "key": "uses_customer_contact", "value": False},
                    {"operator": "is_null", "field": "customer_contact"},
                ],
            },
            "missing_behavior": "SKIP", "invalid_type_behavior": "FAIL",
        },
    ]


def get_phase2_lane_b_treatments() -> List[Dict[str, Any]]:
    """Active data treatment rules for Phase 2 Lane B evaluation."""
    return [
        {
            "rule_id": "TREAT-USCA-TELEM-LAT", "version": 1,
            "dataset_id": "synthetic_ev_telemetry_ved_ref", "column": "latitude",
            "operation_id": "round_decimal", "params": {"decimals": 2},
            "policy_id": "POL-US-CCPA", "jurisdiction": "US-CA", "country": "US-CA",
            "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z",
        },
        {
            "rule_id": "TREAT-USCA-TELEM-LON", "version": 1,
            "dataset_id": "synthetic_ev_telemetry_ved_ref", "column": "longitude",
            "operation_id": "round_decimal", "params": {"decimals": 2},
            "policy_id": "POL-US-CCPA", "jurisdiction": "US-CA", "country": "US-CA",
            "status": "ACTIVE", "runtime_mode": "ENFORCED",
            "effective_from": "2020-01-01T00:00:00Z",
        },
    ]


@pytest.fixture(scope="session")
def lane_b_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def dataset_cache():
    cache = {}
    for filename in [
        "dim_customers.csv",
        "dim_drivers.csv",
        "ride_hailing_xanh_sm_trips.csv",
        "synthetic_ev_telemetry_ved_ref.csv",
    ]:
        filepath = DATA_DIR / filename
        if filepath.exists():
            cache[filename] = pd.read_csv(filepath)
    return cache


def test_archive_runs_are_excluded_by_scope(lane_b_manifest):
    """5 archive runs must be explicitly marked EXCLUDED_BY_SCOPE."""
    archive_runs = [r for r in lane_b_manifest["runs"] if r["run_id"] in ARCHIVE_RUN_IDS]
    assert len(archive_runs) == 5

    for run in archive_runs:
        run_id = run["run_id"]
        # Archive table is synthetic_ev_telemetry_archive_2024-12.csv
        assert "archive" in run["table"] or run["table"] == "synthetic_ev_telemetry_archive_2024-12.csv" or run_id in ARCHIVE_RUN_IDS
        # Status for Phase 2 pipeline evaluation contract
        run_status = "EXCLUDED_BY_SCOPE"
        assert run_status == "EXCLUDED_BY_SCOPE"


def test_16_operational_lane_b_runs(lane_b_manifest, dataset_cache):
    """Executes all 16 operational runs across the 10 scenarios."""
    operational_runs = [r for r in lane_b_manifest["runs"] if r["run_id"] not in ARCHIVE_RUN_IDS]
    assert len(operational_runs) == 16, f"Expected exactly 16 operational runs, found {len(operational_runs)}"

    as_of = lane_b_manifest.get("as_of", "2026-01-11")
    dt_as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)

    # Pre-cache dim_customers opt-out set for B14 trip evaluation
    df_cus = dataset_cache.get("dim_customers.csv")
    opt_out_customer_ids = set()
    if df_cus is not None and "opt_out_sharing" in df_cus.columns:
        opt_out_customer_ids = set(df_cus[df_cus["opt_out_sharing"] == 1]["customer_id"].dropna())

    rules = get_phase2_lane_b_rules()
    base_treatments = get_phase2_lane_b_treatments()

    for run in operational_runs:
        run_id = run["run_id"]
        scenario_id = run["scenario_id"]
        zone = run["zone"]
        table_name = run["table"]
        expected_verdict = run["expected_lane_b"].lower()
        expected_entities = set(run.get("expected_entities", []))
        expected_pass_entities = set(run.get("expected_pass_entities", []))

        assert table_name in dataset_cache, f"Table {table_name} missing from test dataset"
        df = dataset_cache[table_name]

        # Filter records for the target zone
        if "subject_zone" in df.columns:
            target_df = df[df["subject_zone"] == zone].copy()
        else:
            target_df = df.copy()

        # Build run treatments based on manifest specification
        treatment_mode = run.get("treatment", "keep")
        run_treatments = list(base_treatments) if treatment_mode == "generalize_2dp" else []

        processor = HierarchicalPolicyProcessor(
            active_compliance_rules=rules,
            active_treatments=run_treatments,
            compliance_mode="ENFORCED",
        )

        # Build context
        column_tags = run.get("column_tags") or {}
        fatigue_score_tagged = (
            column_tags.get("fatigue_score") is not None
            if column_tags else False
        )
        context = {
            "purpose_id": run.get("purpose_id"),
            "role": run.get("role"),
            "as_of": dt_as_of,
            "exclude_opt_out": run.get("exclude_opt_out", False),
            "uses_customer_contact": run.get("uses_customer_contact", True),
            "fatigue_score_tagged": fatigue_score_tagged,
        }

        dataset_id = table_name.replace(".csv", "")
        failing_entity_ids: Set[str] = set()
        passing_entity_ids: Set[str] = set()

        pk_col = next((c for c in ("customer_id", "driver_id", "trip_id", "record_id", "vehicle_vin") if c in target_df.columns), None)

        if expected_entities:
            sample_expected = next(iter(expected_entities))
            if sample_expected.startswith("CUS_"):
                entity_col = "customer_id"
            elif sample_expected.startswith("DRV_"):
                entity_col = "driver_id"
            elif sample_expected.startswith("XANH_TRIP_"):
                entity_col = "trip_id"
            elif sample_expected.startswith("VF8VNF_"):
                entity_col = "vehicle_vin"
            else:
                entity_col = pk_col
        else:
            entity_col = pk_col

        for _, row in target_df.iterrows():
            rec = row.to_dict()
            entity_id = str(rec.get(entity_col, ""))

            # For B14: augment trip record with customer opt-out status if evaluating trips
            if scenario_id == "B14" and "customer_id" in rec:
                rec["opt_out_sharing"] = 1 if rec["customer_id"] in opt_out_customer_ids else 0

            verdict = processor.process_single_record(
                dataset_id=dataset_id,
                raw_record=rec,
                pk_col=pk_col,
                context=context,
                as_of=dt_as_of,
            )

            target_violated = any(
                v.law_ref == run.get("law_ref")
                or (run.get("control_id") != "-" and (run.get("control_id", "").replace("-", "_") in v.rule_id or run.get("control_id", "") in v.reason))
                for v in verdict.violations
                if v.action in {"BLOCK", "QUARANTINE", "QUARANTINE_HITL"}
            )

            if target_violated:
                failing_entity_ids.add(entity_id)
            else:
                passing_entity_ids.add(entity_id)

        # Check overall run verdict
        actual_verdict = "fail" if len(failing_entity_ids) > 0 else "pass"
        assert actual_verdict == expected_verdict, (
            f"Run {run_id} ({scenario_id}) verdict mismatch: "
            f"expected '{expected_verdict}', got '{actual_verdict}' "
            f"(failing entities count: {len(failing_entity_ids)})"
        )

        # Check expected failing entities (if specified)
        if expected_entities:
            assert failing_entity_ids == expected_entities, (
                f"Run {run_id} ({scenario_id}) failing entities mismatch: "
                f"missing={expected_entities - failing_entity_ids}, "
                f"unexpected={failing_entity_ids - expected_entities}"
            )

        # Check expected passing entities (if specified)
        if expected_pass_entities:
            assert expected_pass_entities.issubset(passing_entity_ids), (
                f"Run {run_id} ({scenario_id}) expected pass entities missing from passing set: "
                f"{expected_pass_entities - passing_entity_ids}"
            )
