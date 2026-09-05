#!/usr/bin/env python3
"""Rule-validity stress (Wave 3 Task 3.3).

Wrap validate_proposed_rule for always-true, always-false, missing column, duplicate.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.validator import validate_proposed_rule


def run() -> int:
    columns = ["battery_soc"]
    sample_rows = [{"battery_soc": 0}, {"battery_soc": 50}, {"battery_soc": 100}]
    failures: list[str] = []

    cases = [
        (
            "always_true",
            {"rule_expression": "battery_soc > -9999", "rule_name": "always"},
            {"approved": []},
            lambda v: v.status == "NEEDS_REVIEW" and v.always_true is True,
        ),
        (
            "always_false",
            {"rule_expression": "battery_soc > 9999", "rule_name": "never"},
            {"approved": []},
            lambda v: v.status == "NEEDS_REVIEW" and v.always_false is True,
        ),
        (
            "missing_column",
            {"rule_expression": "not_a_col > 0", "rule_name": "ghost"},
            {"approved": []},
            lambda v: v.status == "NEEDS_REVIEW" and v.column_exists is False,
        ),
        (
            "duplicate",
            {"rule_expression": "battery_soc BETWEEN 0 AND 100", "rule_name": "dup"},
            {
                "approved": [
                    {"id": "r1", "rule_expression": "battery_soc BETWEEN 0 AND 100"}
                ],
                "sample_rows": [{"battery_soc": 50}, {"battery_soc": -1}],
            },
            lambda v: v.status == "NEEDS_REVIEW" and v.duplicate_of == "r1",
        ),
    ]

    for name, rule, extra, check in cases:
        rows = extra.get("sample_rows", sample_rows)
        approved = extra.get("approved", [])
        try:
            v = validate_proposed_rule(
                rule,
                columns=columns,
                sample_rows=rows,
                approved=approved,
            )
            if not check(v):
                raise AssertionError(
                    f"unexpected validation: status={v.status} "
                    f"always_true={v.always_true} always_false={v.always_false} "
                    f"column_exists={v.column_exists} duplicate_of={v.duplicate_of} "
                    f"reasons={v.reasons}"
                )
            print(
                f"PASS {name}: status={v.status} always_true={v.always_true} "
                f"always_false={v.always_false} column_exists={v.column_exists} "
                f"duplicate_of={v.duplicate_of}"
            )
        except Exception as e:
            failures.append(f"{name}: {e}")
            print(f"FAIL {name}: {e}")

    if failures:
        print("---")
        for f in failures:
            print("FAIL:", f)
        return 1
    print("All rule-validity stress cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
