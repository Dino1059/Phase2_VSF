from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.database.models import (
    ComplianceCheckRuleModel,
    ComplianceEvaluationPhase,
    ComplianceRuleStatus,
    InvalidTypeBehavior,
    MissingBehavior,
    RuleRuntimeMode,
)


def legacy_payload():
    return {
        "rule_id": "COMP-TEST-01", "dataset_id": "trips",
        "column_name": "fare_amount", "rule_name": "Positive fare",
        "rule_code": "POSITIVE", "expression": "fare_amount > 0",
        "description": "Legacy payload", "law_ref": "Internal control",
    }


def test_legacy_payload_gets_versioned_defaults():
    rule = ComplianceCheckRuleModel(**legacy_payload())
    assert rule.target_column == "fare_amount"
    assert (rule.version, rule.status) == (1, ComplianceRuleStatus.ACTIVE)
    assert rule.evaluation_phase is ComplianceEvaluationPhase.PRE_CHECK
    assert rule.condition_json == {}
    assert rule.missing_behavior is MissingBehavior.FAIL
    assert rule.invalid_type_behavior is InvalidTypeBehavior.FAIL
    assert rule.runtime_mode is RuleRuntimeMode.ENFORCED
    assert rule.legal_review_required is False


def test_versioned_shadow_rule_metadata():
    rule = ComplianceCheckRuleModel(**(legacy_payload() | {
        "version": 2, "status": "PENDING_APPROVAL", "runtime_mode": "SHADOW",
        "evaluation_phase": "POST_CHECK",
        "condition_json": {"operator": "masked", "field": "fare_amount"},
        "missing_behavior": "SKIP", "invalid_type_behavior": "WARNING",
        "legal_review_required": True,
    }))
    assert rule.status is ComplianceRuleStatus.PENDING_APPROVAL
    assert rule.condition_json["operator"] == "masked"


def test_invalid_effective_window_is_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="effective_to must be later"):
        ComplianceCheckRuleModel(**legacy_payload(), effective_from=now,
                                 effective_to=now - timedelta(seconds=1))


def test_active_legal_rule_is_valid_without_approval_metadata():
    rule = ComplianceCheckRuleModel(**legacy_payload(), legal_review_required=True)
    assert rule.status is ComplianceRuleStatus.ACTIVE
    assert rule.approved_by is None


def test_sql_has_composite_key_and_overlap_guards():
    root = Path(__file__).parents[1]
    schema = (root / "database/schema_audit_and_policy_rules.sql").read_text(encoding="utf-8")
    migration = (root / "database/migration_versioned_compliance_rules.sql").read_text(encoding="utf-8")
    for sql in (schema, migration):
        assert "PRIMARY KEY (rule_id, version)" in sql
        assert "compliance_rules_no_overlapping_active_versions" in sql
        assert "EXCLUDE USING gist" in sql
        assert "legal_review_required" in sql
        assert "condition_json" in sql
