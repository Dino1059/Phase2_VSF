"""Compiler Tool — typed wrapper around scripts/compile_rules.py.

Turns validated rules into text: a Python "satisfies" expression and a SQL
"violation" WHERE clause. This module deliberately never imports sqlite3
or opens any file other than the schema JSON — it cannot execute anything
against real data by construction, only produce text.
"""
from __future__ import annotations  # noqa: I001 - block below intentionally not import-sorted

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from src.tools.dq.common import ErrorCode, ToolError, execute
from src.tools.dq.validator_tool import RuleInput

from compile_rules import compile_rule  # noqa: E402
from validate_rules import load_schema, validate_rule  # noqa: E402


class CompilerInput(BaseModel):
    rules: list[RuleInput] = Field(min_length=1)
    schema_path: str = "data/profiling_report.json"
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)


class CompiledRule(BaseModel):
    rule_id: str
    table: str
    column: str
    operator: str
    description: str = ""
    satisfies_expr: str
    violation_sql: str


class SkippedRule(BaseModel):
    rule_id: str
    errors: list[str]


class CompilerOutput(BaseModel):
    status: Literal["success", "error"]
    error_code: ErrorCode
    error_message: str = ""
    compiled: list[CompiledRule] = []
    skipped: list[SkippedRule] = []
    execution_time_seconds: float = 0.0


def _do_compile(params: CompilerInput) -> dict:
    from src.tools.dq.common import REPO_ROOT

    schema_path = REPO_ROOT / params.schema_path
    if not schema_path.exists():
        raise ToolError(ErrorCode.SCHEMA_NOT_FOUND, f"schema file not found: {schema_path}")
    schema = load_schema(schema_path)

    compiled, skipped = [], []
    for rule in params.rules:
        rule_dict = rule.model_dump(exclude_none=True)
        errors = validate_rule(rule_dict, schema)
        if errors:
            skipped.append({"rule_id": rule.rule_id, "errors": errors})
            continue
        compiled.append(compile_rule(rule_dict))

    return {"compiled": compiled, "skipped": skipped}


def run_compiler(params: CompilerInput | dict) -> CompilerOutput:
    if not isinstance(params, CompilerInput):
        try:
            params = CompilerInput(**params)
        except ValidationError as e:
            return CompilerOutput(status="error", error_code=ErrorCode.INVALID_INPUT, error_message=str(e))

    status, code, message, payload, elapsed = execute(lambda: _do_compile(params), params.timeout_seconds)
    if status == "error":
        return CompilerOutput(status=status, error_code=code, error_message=message, execution_time_seconds=elapsed)

    return CompilerOutput(
        status="success",
        error_code=ErrorCode.NONE,
        compiled=[CompiledRule(**c) for c in payload["compiled"]],
        skipped=[SkippedRule(**s) for s in payload["skipped"]],
        execution_time_seconds=elapsed,
    )
