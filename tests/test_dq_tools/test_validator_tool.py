from src.tools.dq.common import ErrorCode
from src.tools.dq.validator_tool import ValidatorInput, run_validator


def test_happy_path_valid_rule(temp_schema):
    result = run_validator(
        ValidatorInput(
            rules=[{"rule_id": "R1", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0}],
            schema_path=str(temp_schema),
        )
    )
    assert result.status == "success"
    assert result.valid_count == 1
    assert result.invalid_count == 0
    assert result.results[0].valid is True
    assert result.results[0].errors == []


def test_failure_operator_not_whitelisted(temp_schema):
    result = run_validator(
        ValidatorInput(
            rules=[
                {"rule_id": "BAD", "table": "trips", "column": "fare_amount", "operator": "exec", "value": 0}
            ],
            schema_path=str(temp_schema),
        )
    )
    assert result.status == "success"  # the tool ran fine; the *rule* is what's invalid
    assert result.invalid_count == 1
    assert "not in the whitelist" in result.results[0].errors[0]


def test_failure_schema_mismatch_unknown_table(temp_schema):
    result = run_validator(
        ValidatorInput(
            rules=[{"rule_id": "BAD", "table": "no_such_table", "column": "x", "operator": "not_null"}],
            schema_path=str(temp_schema),
        )
    )
    assert result.invalid_count == 1
    assert "does not exist" in result.results[0].errors[0]


def test_failure_invalid_type_operator_on_text_column(temp_schema):
    result = run_validator(
        ValidatorInput(
            rules=[
                {"rule_id": "BAD", "table": "trips", "column": "status", "operator": "between", "value": [0, 1]}
            ],
            schema_path=str(temp_schema),
        )
    )
    assert result.invalid_count == 1
    assert "requires a numeric column" in result.results[0].errors[0]


def test_failure_schema_not_found(tmp_path):
    result = run_validator(
        ValidatorInput(
            rules=[{"rule_id": "R1", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0}],
            schema_path=str(tmp_path / "missing.json"),
        )
    )
    assert result.status == "error"
    assert result.error_code == ErrorCode.SCHEMA_NOT_FOUND


def test_failure_invalid_input_empty_rules():
    result = run_validator({"rules": [], "schema_path": "data/profiling_report.json"})
    assert result.status == "error"
    assert result.error_code == ErrorCode.INVALID_INPUT
