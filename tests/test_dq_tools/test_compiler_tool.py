from src.tools.dq import compiler_tool
from src.tools.dq.common import ErrorCode
from src.tools.dq.compiler_tool import CompilerInput, run_compiler


def test_compiler_module_never_imports_sqlite3():
    """Structural guarantee: the Compiler cannot touch a database — it never
    even imports sqlite3, so it is impossible for it to open a connection."""
    assert not hasattr(compiler_tool, "sqlite3")


def test_happy_path_compiles_valid_rule(temp_schema):
    result = run_compiler(
        CompilerInput(
            rules=[{"rule_id": "R1", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0}],
            schema_path=str(temp_schema),
        )
    )
    assert result.status == "success"
    assert len(result.compiled) == 1
    assert result.skipped == []

    compiled = result.compiled[0]
    assert compiled.satisfies_expr == "fare_amount >= 0"
    assert compiled.violation_sql == "WHERE fare_amount < 0"


def test_failure_invalid_rule_is_skipped_not_erroring(temp_schema):
    result = run_compiler(
        CompilerInput(
            rules=[
                {"rule_id": "OK", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0},
                {"rule_id": "BAD", "table": "trips", "column": "status", "operator": "between", "value": [0, 1]},
            ],
            schema_path=str(temp_schema),
        )
    )
    # The tool call itself succeeds; the bad rule is reported as skipped, never compiled.
    assert result.status == "success"
    assert [c.rule_id for c in result.compiled] == ["OK"]
    assert [s.rule_id for s in result.skipped] == ["BAD"]
    assert "requires a numeric column" in result.skipped[0].errors[0]


def test_failure_schema_not_found(tmp_path):
    result = run_compiler(
        CompilerInput(
            rules=[{"rule_id": "R1", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0}],
            schema_path=str(tmp_path / "missing.json"),
        )
    )
    assert result.status == "error"
    assert result.error_code == ErrorCode.SCHEMA_NOT_FOUND


def test_failure_invalid_input_missing_rules():
    result = run_compiler({"schema_path": "data/profiling_report.json"})
    assert result.status == "error"
    assert result.error_code == ErrorCode.INVALID_INPUT
