"""Integration tests: chain Profiler -> Validator -> Compiler -> Test Runner
exactly as an agent would, each stage's real output feeding the next."""
import json

from src.tools.dq.common import ErrorCode
from src.tools.dq.compiler_tool import CompilerInput, run_compiler
from src.tools.dq.profiler_tool import ProfilerInput, run_profiler
from src.tools.dq.test_runner_tool import TestRunnerInput, run_test_runner
from src.tools.dq.validator_tool import ValidatorInput, run_validator

RULES = [
    {"rule_id": "R_RANGE", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0},
    {"rule_id": "R_DATE", "table": "trips", "column": "pickup_datetime", "operator": "valid_date"},
    {"rule_id": "R_BAD_TABLE", "table": "no_such_table", "column": "x", "operator": "not_null"},
    {"rule_id": "R_BAD_OP", "table": "trips", "column": "fare_amount", "operator": "delete_everything"},
]


def _write_schema(tmp_path, profiler_result):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps([t.model_dump() for t in profiler_result.tables], ensure_ascii=False), encoding="utf-8"
    )
    return schema_path


def test_happy_path_full_chain_detects_known_violations(temp_db, tmp_path):
    # 1. Profiler
    profiler_result = run_profiler(ProfilerInput(db_path=str(temp_db)))
    assert profiler_result.status == "success"
    schema_path = _write_schema(tmp_path, profiler_result)

    # 2. Validator — only the 2 well-formed rules should be valid
    validator_result = run_validator(ValidatorInput(rules=RULES, schema_path=str(schema_path)))
    assert validator_result.status == "success"
    assert validator_result.valid_count == 2
    assert validator_result.invalid_count == 2

    # 3. Compiler — must only compile what Validator marked valid
    compiler_result = run_compiler(CompilerInput(rules=RULES, schema_path=str(schema_path)))
    assert compiler_result.status == "success"
    assert {c.rule_id for c in compiler_result.compiled} == {"R_RANGE", "R_DATE"}
    assert {s.rule_id for s in compiler_result.skipped} == {"R_BAD_TABLE", "R_BAD_OP"}

    # 4. Test Runner — executes only the compiled checks against real data
    test_result = run_test_runner(
        TestRunnerInput(
            db_path=str(temp_db),
            schema_path=str(schema_path),
            compiled_rules=compiler_result.compiled,
            include_duplicate_checks=True,
        )
    )
    assert test_result.status == "success"

    by_id = {e.check_id: e for e in test_result.evidence}
    assert by_id["R_RANGE"].status == "FAIL"  # T2 has fare_amount = -5.0
    assert by_id["R_RANGE"].violation_count == 1
    assert by_id["R_DATE"].status == "FAIL"  # T3 has pickup_datetime = "BAD_DATE"
    assert by_id["R_DATE"].violation_count == 1
    assert by_id["DUP_trips"].status == "PASS"

    assert test_result.failed == 2
    assert test_result.passed == 1


def test_failure_path_bad_operator_never_reaches_test_runner(temp_db, tmp_path):
    profiler_result = run_profiler(ProfilerInput(db_path=str(temp_db)))
    schema_path = _write_schema(tmp_path, profiler_result)

    compiler_result = run_compiler(CompilerInput(rules=RULES, schema_path=str(schema_path)))
    compiled_ids = {c.rule_id for c in compiler_result.compiled}

    # The two malformed rules must never make it into an executable check.
    assert "R_BAD_TABLE" not in compiled_ids
    assert "R_BAD_OP" not in compiled_ids


def test_failure_path_hand_crafted_bad_check_caught_at_execution(temp_db, tmp_path):
    """Even if a caller bypasses Validator/Compiler and hand-builds a
    CompiledRule referencing a column that doesn't exist, the Test Runner
    must not crash — it isolates the SQL error into that check's evidence."""
    profiler_result = run_profiler(ProfilerInput(db_path=str(temp_db)))
    schema_path = _write_schema(tmp_path, profiler_result)

    forged_check = {
        "rule_id": "FORGED",
        "table": "trips",
        "column": "does_not_exist",
        "operator": "gte",
        "description": "hand-crafted, bypassing Validator/Compiler",
        "satisfies_expr": "does_not_exist >= 0",
        "violation_sql": "WHERE does_not_exist < 0",
    }
    test_result = run_test_runner(
        TestRunnerInput(
            db_path=str(temp_db),
            schema_path=str(schema_path),
            compiled_rules=[forged_check],
            include_duplicate_checks=False,
        )
    )
    assert test_result.status == "success"
    assert test_result.evidence[0].execution_status == "error"


def test_failure_path_missing_db_reported_with_standard_error_code(tmp_path):
    result = run_profiler(ProfilerInput(db_path=str(tmp_path / "missing.db")))
    assert result.status == "error"
    assert result.error_code == ErrorCode.DB_NOT_FOUND
    # every stage should fail the same standardized way given the same bad input
    validator_result = run_validator(
        ValidatorInput(rules=RULES[:1], schema_path=str(tmp_path / "missing_schema.json"))
    )
    assert validator_result.error_code == ErrorCode.SCHEMA_NOT_FOUND
