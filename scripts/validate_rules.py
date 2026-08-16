#!/usr/bin/env python3
"""
Validator Tool for the DataTrust OS pipeline (Step 3).

Checks whether declarative data-quality rules (scripts/rules.json) are
VALID before they are handed to the downstream Rule Engine / Executor:
  - structural validity: required fields present, operator is recognized,
    the "value" shape matches what that operator expects
  - schema validity: the rule's table and column(s) actually exist in the
    schema produced by the Profiler Tool (data/profiling_report.json), and
    the column's declared type is compatible with the operator

This tool does NOT execute rules against real data and does NOT decide
whether records pass/fail a rule — it only decides whether the rule
definition itself is well-formed and applicable to the schema.

Usage:
  python scripts/validate_rules.py [--rules scripts/rules.json]
                                    [--schema data/profiling_report.json]
                                    [--out-prefix data/rule_validation_report]
"""
import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

NUMERIC_TYPES = {"REAL", "INTEGER"}
ALLOWED_OPERATORS = {
    "not_null",
    "gte",
    "lte",
    "gt",
    "lt",
    "eq",
    "ne",
    "between",
    "in",
    "regex",
    "expr_eq",
    "is_numeric",
    "valid_date",
}
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
EXPR_ALLOWED_CHARS_RE = re.compile(r"^[A-Za-z0-9_\.\+\-\*\/\(\)\s]+$")


def load_schema(schema_path: Path) -> dict[str, dict[str, str]]:
    if not schema_path.exists():
        raise SystemExit(
            f"Schema file not found: {schema_path}\n"
            "Run the Profiler Tool first: python scripts/profile_source_db.py"
        )
    tables = json.loads(schema_path.read_text(encoding="utf-8"))
    return {t["table"]: {c["column"]: c["declared_type"] for c in t["columns"]} for t in tables}


def load_rules(rules_path: Path) -> list[dict]:
    if not rules_path.exists():
        raise SystemExit(f"Rules file not found: {rules_path}")
    return json.loads(rules_path.read_text(encoding="utf-8"))


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_rule(rule: dict, schema: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []

    for field in ("rule_id", "table", "column", "operator"):
        if not rule.get(field):
            errors.append(f"missing required field '{field}'")
    if errors:
        return errors  # can't check anything else without these

    operator = rule["operator"]
    if operator not in ALLOWED_OPERATORS:
        errors.append(f"unknown operator '{operator}' (allowed: {sorted(ALLOWED_OPERATORS)})")
        return errors

    table = rule["table"]
    column = rule["column"]
    value = rule.get("value")

    if table not in schema:
        errors.append(f"table '{table}' does not exist in the source schema")
        return errors

    if column not in schema[table]:
        errors.append(f"column '{column}' does not exist in table '{table}'")
        return errors

    col_type = schema[table][column]

    if operator == "not_null":
        pass  # no value needed

    elif operator in ("gte", "lte", "gt", "lt"):
        if col_type not in NUMERIC_TYPES:
            errors.append(f"operator '{operator}' requires a numeric column, but '{column}' is {col_type}")
        if not _is_number(value):
            errors.append(f"operator '{operator}' requires a numeric 'value', got {value!r}")

    elif operator in ("eq", "ne"):
        if col_type in NUMERIC_TYPES and not _is_number(value):
            errors.append(f"column '{column}' is {col_type}, so 'value' must be numeric, got {value!r}")
        elif col_type == "TEXT" and not isinstance(value, str):
            errors.append(f"column '{column}' is TEXT, so 'value' must be a string, got {value!r}")

    elif operator == "between":
        if col_type not in NUMERIC_TYPES:
            errors.append(f"operator 'between' requires a numeric column, but '{column}' is {col_type}")
        if not (isinstance(value, list) and len(value) == 2 and all(_is_number(v) for v in value)):
            errors.append(f"operator 'between' requires 'value' to be a 2-element numeric list, got {value!r}")
        elif value[0] > value[1]:
            errors.append(f"operator 'between' has min > max: {value!r}")

    elif operator == "in":
        if not (isinstance(value, list) and len(value) > 0):
            errors.append(f"operator 'in' requires a non-empty list 'value', got {value!r}")

    elif operator == "regex":
        if col_type != "TEXT":
            errors.append(f"operator 'regex' requires a TEXT column, but '{column}' is {col_type}")
        if not isinstance(value, str):
            errors.append(f"operator 'regex' requires a string 'value', got {value!r}")
        else:
            try:
                re.compile(value)
            except re.error as e:
                errors.append(f"'value' is not a valid regex pattern: {e}")

    elif operator == "is_numeric":
        if col_type not in NUMERIC_TYPES:
            errors.append(
                f"operator 'is_numeric' only makes sense on a numeric-typed column, but '{column}' is {col_type}"
            )

    elif operator == "valid_date":
        if col_type != "TEXT":
            errors.append(f"operator 'valid_date' requires a TEXT column, but '{column}' is {col_type}")

    elif operator == "expr_eq":
        if col_type not in NUMERIC_TYPES:
            errors.append(f"operator 'expr_eq' requires a numeric column, but '{column}' is {col_type}")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"operator 'expr_eq' requires a non-empty string 'value' (an expression), got {value!r}")
        else:
            if not EXPR_ALLOWED_CHARS_RE.match(value):
                errors.append(f"'value' expression contains disallowed characters: {value!r}")
            else:
                for ident in set(IDENTIFIER_RE.findall(value)):
                    if ident not in schema[table]:
                        errors.append(f"expression references unknown column '{ident}' in table '{table}'")
                    elif schema[table][ident] not in NUMERIC_TYPES:
                        errors.append(f"expression references non-numeric column '{ident}'")
        tolerance = rule.get("tolerance", 0)
        if not _is_number(tolerance):
            errors.append(f"'tolerance' must be numeric, got {tolerance!r}")

    return errors


def render_markdown(results: list[dict]) -> str:
    valid_count = sum(1 for r in results if r["valid"])
    lines = [
        "# Rule Validation Report",
        "",
        "Generated by `scripts/validate_rules.py` against `scripts/rules.json`.",
        "",
        f"**{valid_count}/{len(results)} rules valid.**",
        "",
        "| Rule ID | Table | Column | Operator | Status | Errors |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        status = "VALID" if r["valid"] else "INVALID"
        errors = "<br>".join(r["errors"]) if r["errors"] else "-"
        lines.append(
            f"| {r['rule_id']} | {r['table']} | {r['column']} | {r['operator']} | {status} | {errors} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", default="scripts/rules.json")
    parser.add_argument("--schema", default="data/profiling_report.json")
    parser.add_argument("--out-prefix", default="data/rule_validation_report")
    args = parser.parse_args()

    schema = load_schema(REPO_ROOT / args.schema)
    rules = load_rules(REPO_ROOT / args.rules)

    results = []
    for rule in rules:
        errors = validate_rule(rule, schema)
        valid = not errors
        results.append(
            {
                "rule_id": rule.get("rule_id", "?"),
                "table": rule.get("table", "?"),
                "column": rule.get("column", "?"),
                "operator": rule.get("operator", "?"),
                "valid": valid,
                "errors": errors,
            }
        )
        status = "VALID  " if valid else "INVALID"
        print(f"[{status}] {rule.get('rule_id', '?'):<10} {rule.get('table', '?')}.{rule.get('column', '?')}")
        for err in errors:
            print(f"           - {err}")

    json_path = REPO_ROOT / f"{args.out_prefix}.json"
    md_path = REPO_ROOT / f"{args.out_prefix}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(results), encoding="utf-8")

    valid_count = sum(1 for r in results if r["valid"])
    print(f"\n{valid_count}/{len(results)} rules valid.")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    if valid_count != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
