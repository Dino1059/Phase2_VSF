#!/usr/bin/env python3
"""
Test Runner for the DataTrust OS pipeline (Step 5).

Takes executable checks — SQL produced by the Compiler Tool
(data/compiled_rules.json) plus one auto-generated duplicate check per
table — and actually RUNS them read-only against data/source.db. This is
the first tool in the pipeline that touches real data; every prior tool
(Profiler, Validator, Compiler) only inspected schema or text.

Each check is dispatched to a named, executable function:
  check_range, check_null, check_membership, check_equality,
  check_pattern, check_ledger, check_duplicate

A check never just reports PASS/FAIL — it always returns evidence: the
violation count and up to 5 sample offending rows (empty sample when it
passes, since there is nothing to show).

Usage:
  python scripts/run_tests.py [--db data/source.db]
                               [--compiled-rules data/compiled_rules.json]
                               [--schema data/profiling_report.json]
                               [--out-prefix data/test_run_report]

Output (also printed to stdout):
  {"passed": 18, "failed": 2, "evidence": [...]}
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LIMIT = 5

OPERATOR_TO_CHECK_TYPE = {
    "gte": "check_range",
    "lte": "check_range",
    "gt": "check_range",
    "lt": "check_range",
    "between": "check_range",
    "not_null": "check_null",
    "in": "check_membership",
    "eq": "check_equality",
    "ne": "check_equality",
    "regex": "check_pattern",
    "expr_eq": "check_ledger",
    "is_numeric": "check_type",
    "valid_date": "check_date",
}


def _regexp(pattern: str, value) -> bool:
    if value is None:
        return False
    return re.search(pattern, str(value)) is not None


def _run_sql_violation_check(conn: sqlite3.Connection, table: str, violation_sql: str) -> tuple[int, list[dict]]:
    count = conn.execute(f"SELECT COUNT(*) FROM {table} {violation_sql}").fetchone()[0]
    samples: list[dict] = []
    if count:
        cur = conn.execute(f"SELECT * FROM {table} {violation_sql} LIMIT {SAMPLE_LIMIT}")
        cols = [d[0] for d in cur.description]
        samples = [dict(zip(cols, row)) for row in cur.fetchall()]
    return int(count), samples


def check_range(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_null(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_membership(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_equality(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_pattern(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_ledger(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_type(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_date(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    return _run_sql_violation_check(conn, spec["table"], spec["violation_sql"])


def check_duplicate(conn: sqlite3.Connection, spec: dict) -> tuple[int, list[dict]]:
    table = spec["table"]
    pk_cols = spec["primary_key"]
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    compare_cols = [c for c in df.columns if c not in pk_cols] or list(df.columns)
    dup_mask = df.duplicated(subset=compare_cols, keep=False)
    count = int(df.duplicated(subset=compare_cols).sum())
    samples = df.loc[dup_mask].head(SAMPLE_LIMIT).to_dict("records") if count else []
    return count, samples


CHECKS = {
    "check_range": check_range,
    "check_null": check_null,
    "check_membership": check_membership,
    "check_equality": check_equality,
    "check_pattern": check_pattern,
    "check_ledger": check_ledger,
    "check_type": check_type,
    "check_date": check_date,
    "check_duplicate": check_duplicate,
}


def build_specs(compiled_rules: list[dict], schema: list[dict]) -> list[dict]:
    specs = []
    for rule in compiled_rules:
        specs.append(
            {
                "check_id": rule["rule_id"],
                "check_type": OPERATOR_TO_CHECK_TYPE[rule["operator"]],
                "table": rule["table"],
                "column": rule["column"],
                "description": rule.get("description", ""),
                "violation_sql": rule["violation_sql"],
            }
        )
    for table_report in schema:
        specs.append(
            {
                "check_id": f"DUP_{table_report['table']}",
                "check_type": "check_duplicate",
                "table": table_report["table"],
                "column": None,
                "description": f"No duplicate records in {table_report['table']} (excl. primary key)",
                "primary_key": table_report["primary_key"],
            }
        )
    return specs


def run(conn: sqlite3.Connection, specs: list[dict]) -> dict:
    passed = failed = 0
    evidence = []
    for spec in specs:
        fn = CHECKS[spec["check_type"]]
        count, samples = fn(conn, spec)
        status = "PASS" if count == 0 else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        entry = {
            "check_id": spec["check_id"],
            "check_type": spec["check_type"],
            "table": spec["table"],
            "column": spec["column"],
            "description": spec["description"],
            "status": status,
            "violation_count": count,
            "sample_violations": samples,
        }
        evidence.append(entry)
        print(
            f"[{status}] {spec['check_id']:<12} {spec['check_type']:<16} "
            f"{spec['table']}{'.' + spec['column'] if spec['column'] else ''}  violations={count}"
        )

    return {"passed": passed, "failed": failed, "evidence": evidence}


def render_markdown(result: dict) -> str:
    lines = [
        "# Test Run Report",
        "",
        "Generated by `scripts/run_tests.py` — executable checks run read-only against `data/source.db`.",
        "",
        f"**Passed: {result['passed']}  Failed: {result['failed']}**",
        "",
        "| Check ID | Type | Table | Column | Status | Violations |",
        "|---|---|---|---|---|---:|",
    ]
    for e in result["evidence"]:
        lines.append(
            f"| {e['check_id']} | {e['check_type']} | {e['table']} | {e['column'] or '-'} | "
            f"{e['status']} | {e['violation_count']} |"
        )
    lines.append("")

    failures = [e for e in result["evidence"] if e["status"] == "FAIL"]
    if failures:
        lines.append("## Failure Evidence")
        lines.append("")
        for e in failures:
            lines.append(f"### {e['check_id']} — {e['table']}{'.' + e['column'] if e['column'] else ''}")
            lines.append("")
            lines.append(f"{e['description']}")
            lines.append("")
            lines.append(f"Violations: {e['violation_count']}, sample rows:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(e["sample_violations"], indent=2, ensure_ascii=False, default=str))
            lines.append("```")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/source.db")
    parser.add_argument("--compiled-rules", default="data/compiled_rules.json")
    parser.add_argument("--schema", default="data/profiling_report.json")
    parser.add_argument("--out-prefix", default="data/test_run_report")
    args = parser.parse_args()

    compiled_rules = json.loads((REPO_ROOT / args.compiled_rules).read_text(encoding="utf-8"))
    schema = json.loads((REPO_ROOT / args.schema).read_text(encoding="utf-8"))
    specs = build_specs(compiled_rules, schema)

    conn = sqlite3.connect(f"file:{REPO_ROOT / args.db}?mode=ro", uri=True)
    conn.create_function("REGEXP", 2, _regexp)
    try:
        result = run(conn, specs)
    finally:
        conn.close()

    json_path = REPO_ROOT / f"{args.out_prefix}.json"
    md_path = REPO_ROOT / f"{args.out_prefix}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")

    print()
    print(json.dumps({"passed": result["passed"], "failed": result["failed"]}, indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
