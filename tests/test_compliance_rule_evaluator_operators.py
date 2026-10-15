from datetime import datetime, timezone
import pytest

from backend.engine.compliance_rule_evaluator import (
    ComplianceRuleEvaluator,
    RuleConfigurationError,
    MAX_NESTING_DEPTH,
    MAX_CHILD_CONDITIONS,
    MAX_REFERENCED_FIELDS,
    MAX_SERIALIZED_RULE_SIZE,
)


def _make_rule(condition: dict, rule_id: str = "RULE-TEST") -> dict:
    return {
        "rule_id": rule_id,
        "version": 1,
        "dataset_id": "test_dataset",
        "column_name": condition.get("field", "*"),
        "rule_name": "Test Rule",
        "rule_code": "TEST_RULE",
        "expression": "test",
        "description": "test rule",
        "policy_id": "POL-TEST",
        "jurisdiction": "GLOBAL",
        "severity": "CRITICAL",
        "on_fail_action": "BLOCK",
        "status": "ACTIVE",
        "runtime_mode": "ENFORCED",
        "effective_from": "2020-01-01T00:00:00Z",
        "evaluation_phase": "PRE_CHECK",
        "condition_json": condition,
        "missing_behavior": "FAIL",
        "invalid_type_behavior": "FAIL",
        "law_ref": "Internal",
    }


def test_is_null_operator():
    rule = _make_rule({"operator": "is_null", "field": "deleted_at"})
    evaluator = ComplianceRuleEvaluator([rule])
    rules, _ = evaluator.applicable_rules("test_dataset", ["GLOBAL"])

    # Null value
    res = evaluator.evaluate(rules, {"deleted_at": None}, {"deleted_at": None}, "PRE_CHECK")
    assert len(res.findings) == 0

    # Empty string
    res = evaluator.evaluate(rules, {"deleted_at": ""}, {"deleted_at": ""}, "PRE_CHECK")
    assert len(res.findings) == 0

    # Populated string
    res = evaluator.evaluate(rules, {"deleted_at": "2026-01-01"}, {"deleted_at": "2026-01-01"}, "PRE_CHECK")
    assert len(res.findings) == 1
    assert "deleted_at is expected to be null or empty" in res.findings[0].reason


def test_context_equals_operator():
    rule = _make_rule({"operator": "context_equals", "key": "purpose_id", "value": "ops_dispatch"})
    evaluator = ComplianceRuleEvaluator([rule])
    rules, _ = evaluator.applicable_rules("test_dataset", ["GLOBAL"])

    # Matching context
    res = evaluator.evaluate(
        rules, {}, {}, "PRE_CHECK", context={"purpose_id": "ops_dispatch"}
    )
    assert len(res.findings) == 0

    # Non-matching context
    res = evaluator.evaluate(
        rules, {}, {}, "PRE_CHECK", context={"purpose_id": "marketing"}
    )
    assert len(res.findings) == 1
    assert "context key 'purpose_id'" in res.findings[0].reason


def test_date_age_days_operator():
    rule = _make_rule({"operator": "date_age_days", "field": "request_date", "max_days": 20})
    evaluator = ComplianceRuleEvaluator([rule])
    rules, _ = evaluator.applicable_rules("test_dataset", ["GLOBAL"])

    as_of = datetime(2026, 1, 11, 0, 0, 0, tzinfo=timezone.utc)

    # 10 days old (within 20 days)
    res = evaluator.evaluate(
        rules, {"request_date": "2026-01-01"}, {"request_date": "2026-01-01"}, "PRE_CHECK", as_of=as_of
    )
    assert len(res.findings) == 0

    # 41 days old (exceeds 20 days)
    res = evaluator.evaluate(
        rules, {"request_date": "2025-12-01"}, {"request_date": "2025-12-01"}, "PRE_CHECK", as_of=as_of
    )
    assert len(res.findings) == 1
    assert "request_date age (41.0 days) exceeds permitted range" in res.findings[0].reason


def test_all_operator():
    rule = _make_rule({
        "operator": "all",
        "conditions": [
            {"operator": "compare", "field": "score", "comparator": ">=", "value": 50},
            {"operator": "compare", "field": "score", "comparator": "<=", "value": 100},
        ],
    })
    evaluator = ComplianceRuleEvaluator([rule])
    rules, _ = evaluator.applicable_rules("test_dataset", ["GLOBAL"])

    # Both conditions met (75)
    res = evaluator.evaluate(rules, {"score": 75}, {"score": 75}, "PRE_CHECK")
    assert len(res.findings) == 0

    # First condition failed (40)
    res = evaluator.evaluate(rules, {"score": 40}, {"score": 40}, "PRE_CHECK")
    assert len(res.findings) == 1


def test_any_operator():
    rule = _make_rule({
        "operator": "any",
        "conditions": [
            {"operator": "is_null", "field": "delete_requested_at"},
            {"operator": "date_age_days", "field": "delete_requested_at", "max_days": 20},
        ],
    })
    evaluator = ComplianceRuleEvaluator([rule])
    rules, _ = evaluator.applicable_rules("test_dataset", ["GLOBAL"])

    as_of = datetime(2026, 1, 11, 0, 0, 0, tzinfo=timezone.utc)

    # Alternative 1: delete_requested_at is null -> PASS
    res = evaluator.evaluate(rules, {"delete_requested_at": None}, {"delete_requested_at": None}, "PRE_CHECK", as_of=as_of)
    assert len(res.findings) == 0

    # Alternative 2: delete_requested_at is recent (6 days) -> PASS
    res = evaluator.evaluate(rules, {"delete_requested_at": "2026-01-05"}, {"delete_requested_at": "2026-01-05"}, "PRE_CHECK", as_of=as_of)
    assert len(res.findings) == 0

    # Neither: delete_requested_at is 41 days old -> FAIL
    res = evaluator.evaluate(rules, {"delete_requested_at": "2025-12-01"}, {"delete_requested_at": "2025-12-01"}, "PRE_CHECK", as_of=as_of)
    assert len(res.findings) == 1


def test_not_operator():
    rule = _make_rule({
        "operator": "not",
        "condition": {"operator": "compare", "field": "opt_out_sharing", "comparator": "==", "value": 1},
    })
    evaluator = ComplianceRuleEvaluator([rule])
    rules, _ = evaluator.applicable_rules("test_dataset", ["GLOBAL"])

    # opt_out_sharing == 0 -> child is False -> negated is True (PASS)
    res = evaluator.evaluate(rules, {"opt_out_sharing": 0}, {"opt_out_sharing": 0}, "PRE_CHECK")
    assert len(res.findings) == 0

    # opt_out_sharing == 1 -> child is True -> negated is False (FAIL)
    res = evaluator.evaluate(rules, {"opt_out_sharing": 1}, {"opt_out_sharing": 1}, "PRE_CHECK")
    assert len(res.findings) == 1


def test_ast_complexity_limits():
    # 1. Nesting depth limit
    deep_cond = {"operator": "is_null", "field": "f"}
    for _ in range(MAX_NESTING_DEPTH + 1):
        deep_cond = {"operator": "not", "condition": deep_cond}

    with pytest.raises(RuleConfigurationError, match="condition nesting depth.*exceeds maximum"):
        ComplianceRuleEvaluator([_make_rule(deep_cond)])

    # 2. Max child conditions
    wide_cond = {
        "operator": "any",
        "conditions": [{"operator": "is_null", "field": f"col_{i}"} for i in range(MAX_CHILD_CONDITIONS + 1)],
    }
    with pytest.raises(RuleConfigurationError, match="child conditions; must be between 1 and"):
        ComplianceRuleEvaluator([_make_rule(wide_cond)])

    # 3. Max referenced fields
    fields_cond = {
        "operator": "all",
        "conditions": [{"operator": "is_null", "field": f"f_{i}"} for i in range(MAX_CHILD_CONDITIONS)],
    }
    # To exceed MAX_REFERENCED_FIELDS (20), we can have 2 levels of all/any
    two_level_cond = {
        "operator": "all",
        "conditions": [
            {"operator": "all", "conditions": [{"operator": "is_null", "field": f"f_{i}"} for i in range(10)]},
            {"operator": "all", "conditions": [{"operator": "is_null", "field": f"f_{i+10}"} for i in range(10)]},
            {"operator": "all", "conditions": [{"operator": "is_null", "field": "f_extra"}]},
        ],
    }
    with pytest.raises(RuleConfigurationError, match="referenced fields count.*exceeds maximum"):
        ComplianceRuleEvaluator([_make_rule(two_level_cond)])

    # 4. Max serialized rule size
    huge_cond = {
        "operator": "enum",
        "field": "test_col",
        "values": ["x" * 100 for _ in range(100)],  # > 10,000 bytes
    }
    with pytest.raises(RuleConfigurationError, match="condition serialized size.*exceeds maximum"):
        ComplianceRuleEvaluator([_make_rule(huge_cond)])

    # 5. Not operator requires exactly one child
    bad_not = {"operator": "not", "conditions": [{"operator": "is_null", "field": "a"}, {"operator": "is_null", "field": "b"}]}
    with pytest.raises(RuleConfigurationError, match="operator 'not' requires exactly one child condition"):
        ComplianceRuleEvaluator([_make_rule(bad_not)])
