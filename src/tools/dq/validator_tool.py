"""Validator Tool — typed wrapper around scripts/validate_rules.py.

Checks whether declarative rules are well-formed and schema-compatible.
Every rule's operator is checked against an explicit whitelist before any
other validation runs — an operator outside ALLOWED_OPERATORS is rejected
immediately with OPERATOR_NOT_WHITELISTED, never evaluated as code.
"""
from __future__ import annotations  # noqa: I001 - block below intentionally not import-sorted

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from src.tools.dq.common import ErrorCode, ToolError, execute

from validate_rules import ALLOWED_OPERATORS, load_schema, validate_rule  # noqa: E402


class RuleInput(BaseModel):
    rule_id: str
    table: str
    column: str
    operator: str
    value: Any = None
    tolerance: float | None = None
    description: str = ""


class ValidatorInput(BaseModel):
    rules: list[RuleInput] = Field(min_length=1)
    schema_path: str = "data/profiling_report.json"
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)


class RuleValidationResult(BaseModel):
    rule_id: str
    valid: bool
    errors: list[str]


class ValidatorOutput(BaseModel):
    status: Literal["success", "error"]
    error_code: ErrorCode
    error_message: str = ""
    results: list[RuleValidationResult] = []
    valid_count: int = 0
    invalid_count: int = 0
    execution_time_seconds: float = 0.0


def _do_validate(params: ValidatorInput) -> dict:
    from src.tools.dq.common import REPO_ROOT

    schema_path = REPO_ROOT / params.schema_path
    if not schema_path.exists():
        raise ToolError(ErrorCode.SCHEMA_NOT_FOUND, f"schema file not found: {schema_path}")
    schema = load_schema(schema_path)

    results = []
    for rule in params.rules:
        rule_dict = rule.model_dump(exclude_none=True)

        # Whitelist check first and explicitly: an operator outside this
        # set is rejected before it ever reaches the general validator.
        if rule.operator not in ALLOWED_OPERATORS:
            results.append(
                {
                    "rule_id": rule.rule_id,
                    "valid": False,
                    "errors": [
                        f"operator '{rule.operator}' is not in the whitelist: {sorted(ALLOWED_OPERATORS)}"
                    ],
                }
            )
            continue

        errors = validate_rule(rule_dict, schema)
        results.append({"rule_id": rule.rule_id, "valid": not errors, "errors": errors})

    return {"results": results}


def run_validator(params: ValidatorInput | dict) -> ValidatorOutput:
    if not isinstance(params, ValidatorInput):
        try:
            params = ValidatorInput(**params)
        except ValidationError as e:
            return ValidatorOutput(status="error", error_code=ErrorCode.INVALID_INPUT, error_message=str(e))

    status, code, message, payload, elapsed = execute(lambda: _do_validate(params), params.timeout_seconds)
    if status == "error":
        return ValidatorOutput(status=status, error_code=code, error_message=message, execution_time_seconds=elapsed)

    results = [RuleValidationResult(**r) for r in payload["results"]]
    valid_count = sum(1 for r in results if r.valid)
    return ValidatorOutput(
        status="success",
        error_code=ErrorCode.NONE,
        results=results,
        valid_count=valid_count,
        invalid_count=len(results) - valid_count,
        execution_time_seconds=elapsed,
    )
