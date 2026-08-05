"""Test Runner Tool — typed wrapper around scripts/run_tests.py.

The only tool in this layer that touches real data. Opens data/source.db
read-only (SQLite URI mode=ro — the connection physically cannot write)
and executes each compiled check, returning structured evidence
(violation count, sample violating rows, per-check execution status).
"""
from __future__ import annotations  # noqa: I001 - block below intentionally not import-sorted

import json
import sqlite3
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from src.tools.dq.common import ErrorCode, ToolError, execute
from src.tools.dq.compiler_tool import CompiledRule

from run_tests import CHECKS, _regexp, build_specs  # noqa: E402


class TestRunnerInput(BaseModel):
    __test__ = False
    db_path: str = "data/source.db"
    schema_path: str = "data/profiling_report.json"
    compiled_rules: list[CompiledRule] = Field(min_length=1)
    include_duplicate_checks: bool = True
    timeout_seconds: float = Field(default=60.0, gt=0, le=600)


class Evidence(BaseModel):
    check_id: str
    check_type: str
    table: str
    column: str | None
    description: str
    status: Literal["PASS", "FAIL"]
    violation_count: int
    sample_violations: list[dict[str, Any]]
    execution_status: Literal["completed", "error"]
    execution_error: str = ""


class TestRunnerOutput(BaseModel):
    status: Literal["success", "error"]
    error_code: ErrorCode
    error_message: str = ""
    passed: int = 0
    failed: int = 0
    evidence: list[Evidence] = []
    execution_time_seconds: float = 0.0


def _do_run(params: TestRunnerInput) -> dict:
    from src.tools.dq.common import REPO_ROOT

    db_path = REPO_ROOT / params.db_path
    if not db_path.exists():
        raise ToolError(ErrorCode.DB_NOT_FOUND, f"database not found: {db_path}")

    schema_path = REPO_ROOT / params.schema_path
    if not schema_path.exists():
        raise ToolError(ErrorCode.SCHEMA_NOT_FOUND, f"schema file not found: {schema_path}")
    schema_tables = json.loads(schema_path.read_text(encoding="utf-8"))

    compiled_rules = [r.model_dump() for r in params.compiled_rules]
    specs = build_specs(compiled_rules, schema_tables if params.include_duplicate_checks else [])

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.create_function("REGEXP", 2, _regexp)
    try:
        evidence = []
        for spec in specs:
            fn = CHECKS[spec["check_type"]]
            try:
                count, samples = fn(conn, spec)
                evidence.append(
                    {
                        "check_id": spec["check_id"],
                        "check_type": spec["check_type"],
                        "table": spec["table"],
                        "column": spec["column"],
                        "description": spec["description"],
                        "status": "PASS" if count == 0 else "FAIL",
                        "violation_count": count,
                        "sample_violations": samples,
                        "execution_status": "completed",
                        "execution_error": "",
                    }
                )
            except sqlite3.Error as e:
                evidence.append(
                    {
                        "check_id": spec["check_id"],
                        "check_type": spec["check_type"],
                        "table": spec["table"],
                        "column": spec["column"],
                        "description": spec["description"],
                        "status": "FAIL",
                        "violation_count": 0,
                        "sample_violations": [],
                        "execution_status": "error",
                        "execution_error": str(e),
                    }
                )
    finally:
        conn.close()

    passed = sum(1 for e in evidence if e["status"] == "PASS" and e["execution_status"] == "completed")
    failed = len(evidence) - passed
    return {"passed": passed, "failed": failed, "evidence": evidence}


def run_test_runner(params: TestRunnerInput | dict) -> TestRunnerOutput:
    if not isinstance(params, TestRunnerInput):
        try:
            params = TestRunnerInput(**params)
        except ValidationError as e:
            return TestRunnerOutput(status="error", error_code=ErrorCode.INVALID_INPUT, error_message=str(e))

    status, code, message, payload, elapsed = execute(lambda: _do_run(params), params.timeout_seconds)
    if status == "error":
        return TestRunnerOutput(status=status, error_code=code, error_message=message, execution_time_seconds=elapsed)

    return TestRunnerOutput(
        status="success",
        error_code=ErrorCode.NONE,
        passed=payload["passed"],
        failed=payload["failed"],
        evidence=[Evidence(**e) for e in payload["evidence"]],
        execution_time_seconds=elapsed,
    )
