from datetime import datetime, timezone

import pytest

from backend.engine.compliance_rule_evaluator import (
    ComplianceRuleEvaluator,
    RuleConfigurationError,
)
from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor


def rule(rule_id, condition, *, phase="PRE_CHECK", action="BLOCK", **extra):
    return {
        "rule_id": rule_id,
        "version": extra.pop("version", 1),
        "status": "ACTIVE",
        "dataset_id": "trips",
        "jurisdiction": extra.pop("jurisdiction", "GLOBAL"),
        "evaluation_phase": phase,
        "condition_json": condition,
        "missing_behavior": extra.pop("missing_behavior", "FAIL"),
        "invalid_type_behavior": extra.pop("invalid_type_behavior", "FAIL"),
        "on_fail_action": action,
        "effective_from": "2026-01-01T00:00:00+00:00",
        **extra,
    }


@pytest.mark.parametrize(
    "condition,record,raw",
    [
        ({"operator": "required", "fields": ["fare"]}, {"fare": 1}, {"fare": 1}),
        ({"operator": "range", "field": "fare", "min": 0, "max": 10}, {"fare": 5}, {"fare": 5}),
        ({"operator": "compare", "field": "fare", "op": ">", "value": 0}, {"fare": 1}, {"fare": 1}),
        ({"operator": "enum", "field": "state", "values": ["OK"]}, {"state": "OK"}, {"state": "OK"}),
        ({"operator": "arithmetic", "field": "total", "fields": ["fare", "tip"]}, {"total": 3, "fare": 2, "tip": 1}, {}),
        ({"operator": "relative_delta", "left_field": "meter", "right_field": "bms", "max": .03}, {"meter": 100, "bms": 98}, {}),
        ({"operator": "regex", "field": "code", "pattern": r"[A-Z]{2}"}, {"code": "VN"}, {}),
        ({"operator": "masked", "field": "phone"}, {"phone": "098*****21"}, {"phone": "0987654321"}),
        ({"operator": "hashed", "field": "driver"}, {"driver": "a" * 64}, {"driver": "D1"}),
        ({"operator": "geofence", "latitude_field": "lat", "longitude_field": "lon", "bounds": {"min_lat": 8, "max_lat": 24, "min_lon": 102, "max_lon": 110}}, {"lat": 21, "lon": 105}, {}),
    ],
)
def test_allowlisted_operators_pass(condition, record, raw):
    evaluator = ComplianceRuleEvaluator([rule("R", condition)])
    applicable, _ = evaluator.applicable_rules("trips", ["GLOBAL"], datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert evaluator.evaluate(applicable, record, raw or record, "PRE_CHECK").findings == []


def test_rejects_unknown_operator_and_overlapping_versions():
    with pytest.raises(RuleConfigurationError):
        ComplianceRuleEvaluator([rule("BAD", {"operator": "python", "expression": "open('x')"})])
    with pytest.raises(RuleConfigurationError, match="overlapping"):
        ComplianceRuleEvaluator([
            rule("R", {"operator": "required", "field": "x"}, version=1),
            rule("R", {"operator": "required", "field": "x"}, version=2),
        ])


def test_active_legal_rule_does_not_require_approval_metadata():
    evaluator = ComplianceRuleEvaluator([
        rule("LEGAL", {"operator": "required", "field": "x"}, legal_review_required=True)
    ])
    assert evaluator.rules[0]["rule_id"] == "LEGAL"


def test_invalid_value_is_not_copied_into_evidence():
    evaluator = ComplianceRuleEvaluator([rule("NUMBER", {"operator": "range", "field": "amount", "min": 0})])
    applicable, _ = evaluator.applicable_rules("trips", ["GLOBAL"], datetime(2026, 2, 1, tzinfo=timezone.utc))
    finding = evaluator.evaluate(applicable, {"amount": "secret@example.com"}, {}, "PRE_CHECK").findings[0]
    assert finding.reason == "invalid input type"
    assert "secret@example.com" not in finding.reason


def test_country_scoping_and_overlap_are_independent():
    vn = rule("LOCAL", {"operator": "required", "field": "x"}, jurisdiction="EU", country="DE")
    fr = rule("LOCAL", {"operator": "required", "field": "x"}, jurisdiction="EU", country="FR", version=2)
    evaluator = ComplianceRuleEvaluator([vn, fr])
    applicable, _ = evaluator.applicable_rules("trips", ["GLOBAL", "EU", "DE"], datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert [item["country"] for item in applicable] == ["DE"]


def test_processor_collects_all_findings_and_blocks_missing_zone():
    rules = [
        rule("FARE", {"operator": "range", "field": "fare", "min": 0}),
        rule("DIST", {"operator": "range", "field": "distance", "min": .1}),
        rule("MASK", {"operator": "masked", "field": "phone"}, phase="POST_CHECK"),
    ]
    verdict = HierarchicalPolicyProcessor(active_compliance_rules=rules).process_single_record(
        "trips", {"trip_id": "T1", "fare": -1, "distance": 0, "phone": "0987654321"}
    )
    assert verdict.status == "FAIL"
    assert {v.rule_id for v in verdict.violations} == {"ZONE_MISSING", "FARE", "DIST", "MASK"}
    assert len(verdict.executed_rule_keys) == 3
    assert verdict.rule_snapshot_hash and verdict.rule_snapshot


def test_missing_and_invalid_behaviors_and_finding_only_pack():
    rules = [
        rule("OPTIONAL", {"operator": "range", "field": "optional", "min": 0}, missing_behavior="SKIP"),
        rule("BADTYPE", {"operator": "range", "field": "amount", "min": 0}, action="WARNING", invalid_type_behavior="WARNING"),
    ]
    verdict = HierarchicalPolicyProcessor(active_compliance_rules=rules).process_single_record(
        "trips", {"trip_id": "T2", "subject_zone": "XX", "amount": "not-a-number"}
    )
    assert verdict.status == "FAIL"
    assert verdict.treated_record is None
    assert {v.rule_id for v in verdict.violations} == {"NO_ACTIVE_PACK", "BADTYPE"}


def test_warning_retains_treated_record_and_shadow_does_not_block():
    rules = [rule(
        "FARE", {"operator": "range", "field": "fare", "min": 0}, jurisdiction="VN"
    )]
    treatment = [{
        "column": "phone", "operation_id": "MASK", "params": {"prefix_len": 3, "suffix_len": 2},
        "jurisdiction": "GLOBAL", "policy_id": "P-PRIVACY",
    }]
    processor = HierarchicalPolicyProcessor(
        active_treatments=treatment, active_compliance_rules=rules, shadow_mode=True
    )
    verdict = processor.process_single_record(
        "trips", {"trip_id": "T3", "subject_zone": "VN", "fare": -1, "phone": "0987654321"}
    )
    assert verdict.status == "WARNING"
    assert verdict.treated_record["phone"] == "098*****21"
    assert verdict.violations[0].runtime_state == "shadowed"
    assert verdict.rule_executions[0]["runtime_state"] == "shadowed"


def test_per_rule_shadow_mode_is_not_enforced():
    rules = [rule(
        "FARE", {"operator": "range", "field": "fare", "min": 0},
        runtime_mode="SHADOW", jurisdiction="VN",
    )]
    verdict = HierarchicalPolicyProcessor(
        active_compliance_rules=rules, compliance_mode="ENFORCED"
    ).process_single_record("trips", {"trip_id": "T4", "subject_zone": "VN", "fare": -1})
    assert verdict.status == "WARNING"
    fare = next(item for item in verdict.violations if item.rule_id == "FARE")
    assert fare.runtime_state == "shadowed"
    assert fare.reason not in verdict.failure_reasons


def test_snapshot_hash_covers_returned_snapshot():
    rules = [rule("GLOBAL", {"operator": "required", "field": "x"}),
             rule("EU", {"operator": "required", "field": "x"}, jurisdiction="EU")]
    verdict = HierarchicalPolicyProcessor(active_compliance_rules=rules).process_single_record(
        "trips", {"trip_id": "T5", "subject_zone": "VN", "x": 1}
    )
    assert verdict.rule_snapshot_hash == ComplianceRuleEvaluator.snapshot_hash(verdict.rule_snapshot)
    assert {item["rule_id"] for item in verdict.rule_snapshot} == {"GLOBAL", "EU"}


def test_jurisdiction_and_effective_time_filtering():
    evaluator = ComplianceRuleEvaluator([
        rule("VN", {"operator": "required", "field": "x"}, jurisdiction="VN"),
        rule("EU", {"operator": "required", "field": "x"}, jurisdiction="EU"),
    ])
    applicable, skipped = evaluator.applicable_rules(
        "trips", ["GLOBAL", "VN"], datetime(2026, 2, 1, tzinfo=timezone.utc)
    )
    assert [r["rule_id"] for r in applicable] == ["VN"]
    assert "EU@1" in skipped
