"""Wave 2 Task 2.1 — rule validation gate before HITL queue."""
from __future__ import annotations

from src.tools.validator import validate_proposed_rule


def test_missing_column_needs_review():
    v = validate_proposed_rule(
        {"rule_expression": "not_a_col > 0", "rule_name": "x"},
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 50}],
        approved=[],
    )
    assert v.status == "NEEDS_REVIEW"
    assert v.column_exists is False


def test_valid_soc_range_validated():
    v = validate_proposed_rule(
        {
            "rule_expression": "battery_soc BETWEEN 0 AND 100",
            "rule_name": "soc_range",
            "remediation_action": "CLIP",
            "remediation_sql_expr": (
                "CASE WHEN battery_soc < 0 THEN 0.0 "
                "WHEN battery_soc > 100 THEN 100.0 ELSE battery_soc END"
            ),
            "why_proposed": "SOC physical bounds",
        },
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 50}, {"battery_soc": -1}],
        approved=[],
    )
    assert v.sql_compiles is True
    assert v.column_exists is True
    assert v.status == "VALIDATED"


def test_compile_fail_needs_review():
    v = validate_proposed_rule(
        {"rule_expression": "DROP TABLE students; --", "rule_name": "bad"},
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 1}],
        approved=[],
    )
    assert v.status == "NEEDS_REVIEW"
    assert v.sql_compiles is False


def test_always_true_needs_review():
    v = validate_proposed_rule(
        {"rule_expression": "battery_soc > -9999", "rule_name": "always"},
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 0}, {"battery_soc": 50}, {"battery_soc": 100}],
        approved=[],
    )
    assert v.status == "NEEDS_REVIEW"
    assert v.always_true is True


def test_always_false_needs_review():
    v = validate_proposed_rule(
        {"rule_expression": "battery_soc > 9999", "rule_name": "never"},
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 0}, {"battery_soc": 50}],
        approved=[],
    )
    assert v.status == "NEEDS_REVIEW"
    assert v.always_false is True


def test_duplicate_approved_needs_review():
    v = validate_proposed_rule(
        {"rule_expression": "battery_soc BETWEEN 0 AND 100", "rule_name": "dup"},
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 50}, {"battery_soc": -1}],
        approved=[{"id": "r1", "rule_expression": "battery_soc BETWEEN 0 AND 100"}],
    )
    assert v.status == "NEEDS_REVIEW"
    assert v.duplicate_of == "r1"


def test_high_quarantine_without_rationale():
    v = validate_proposed_rule(
        {
            "rule_expression": "battery_soc BETWEEN 0 AND 100",
            "rule_name": "harsh",
            "quarantine_rate_preview": 0.5,
        },
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 50}, {"battery_soc": -1}],
        approved=[],
    )
    assert v.status == "NEEDS_REVIEW"
    assert any("quarantine_rate_preview" in r for r in v.reasons)


def test_remediation_column_missing():
    v = validate_proposed_rule(
        {
            "rule_expression": "battery_soc BETWEEN 0 AND 100",
            "rule_name": "bad_remed",
            "remediation_action": "CLIP",
            "remediation_sql_expr": "CASE WHEN ghost_col < 0 THEN 0 ELSE ghost_col END",
            "why_proposed": "clip",
        },
        columns=["battery_soc"],
        sample_rows=[{"battery_soc": 50}, {"battery_soc": -1}],
        approved=[],
    )
    assert v.status == "NEEDS_REVIEW"
    assert any("remediation column missing" in r for r in v.reasons)
