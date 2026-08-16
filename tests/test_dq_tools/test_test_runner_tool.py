from src.tools.dq.common import ErrorCode
from src.tools.dq.test_runner_tool import TestRunnerInput, run_test_runner

VALID_CHECK = {
    "rule_id": "R1",
    "table": "trips",
    "column": "fare_amount",
    "operator": "gte",
    "description": "fare must be non-negative",
    "satisfies_expr": "fare_amount >= 0",
    "violation_sql": "WHERE fare_amount < 0",
}


def test_happy_path_detects_real_violation_with_evidence(temp_db, temp_schema):
    result = run_test_runner(
        TestRunnerInput(
            db_path=str(temp_db),
            schema_path=str(temp_schema),
            compiled_rules=[VALID_CHECK],
            include_duplicate_checks=False,
        )
    )
    assert result.status == "success"
    assert result.failed == 1
    assert result.passed == 0

    ev = result.evidence[0]
    assert ev.check_id == "R1"
    assert ev.status == "FAIL"
    assert ev.violation_count == 1
    assert ev.execution_status == "completed"
    assert ev.sample_violations[0]["trip_id"] == "T2"


def test_happy_path_auto_generates_duplicate_check(temp_db, temp_schema):
    result = run_test_runner(
        TestRunnerInput(
            db_path=str(temp_db),
            schema_path=str(temp_schema),
            compiled_rules=[VALID_CHECK],
            include_duplicate_checks=True,
        )
    )
    assert result.status == "success"
    dup_checks = [e for e in result.evidence if e.check_type == "check_duplicate"]
    assert len(dup_checks) == 1
    assert dup_checks[0].check_id == "DUP_trips"
    assert dup_checks[0].status == "PASS"  # no duplicate rows in the fixture


def test_failure_db_not_found(tmp_path, temp_schema):
    result = run_test_runner(
        TestRunnerInput(
            db_path=str(tmp_path / "missing.db"),
            schema_path=str(temp_schema),
            compiled_rules=[VALID_CHECK],
        )
    )
    assert result.status == "error"
    assert result.error_code == ErrorCode.DB_NOT_FOUND


def test_failure_schema_not_found(temp_db, tmp_path):
    result = run_test_runner(
        TestRunnerInput(
            db_path=str(temp_db),
            schema_path=str(tmp_path / "missing.json"),
            compiled_rules=[VALID_CHECK],
        )
    )
    assert result.status == "error"
    assert result.error_code == ErrorCode.SCHEMA_NOT_FOUND


def test_failure_invalid_input_empty_compiled_rules():
    result = run_test_runner({"compiled_rules": []})
    assert result.status == "error"
    assert result.error_code == ErrorCode.INVALID_INPUT


def test_per_check_execution_error_is_isolated_not_fatal(temp_db, temp_schema):
    """A malformed check's SQL error must not crash the whole tool call —
    it should surface as one evidence entry with execution_status='error'."""
    broken_check = dict(VALID_CHECK, rule_id="BROKEN", violation_sql="WHERE this is not valid sql (((")
    result = run_test_runner(
        TestRunnerInput(
            db_path=str(temp_db),
            schema_path=str(temp_schema),
            compiled_rules=[VALID_CHECK, broken_check],
            include_duplicate_checks=False,
        )
    )
    assert result.status == "success"
    broken_evidence = next(e for e in result.evidence if e.check_id == "BROKEN")
    assert broken_evidence.execution_status == "error"
    assert broken_evidence.execution_error != ""

    ok_evidence = next(e for e in result.evidence if e.check_id == "R1")
    assert ok_evidence.execution_status == "completed"
