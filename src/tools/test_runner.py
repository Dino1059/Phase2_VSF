from typing import Any, Dict, List, Optional
import pandas as pd

from src.models.schemas import RuleFamily, RuleSpec, TestResult, TestSuiteResult


class TestRunner:
    """
    TestRunner executes deterministic verification tests against CleanDB output
    to validate data quality compliance post-execution.
    """

    def run_tests(
        self,
        clean_df: pd.DataFrame,
        rules: List[RuleSpec],
        target_schema: Optional[Dict[str, Any]] = None,
    ) -> TestSuiteResult:
        results: List[TestResult] = []

        # 1. Test target schema column presence
        if target_schema and "columns" in target_schema:
            expected_cols = [c["name"] for c in target_schema["columns"] if "name" in c]
            missing = [c for c in expected_cols if c not in clean_df.columns]
            passed = len(missing) == 0
            results.append(
                TestResult(
                    test_name="schema_columns_presence",
                    passed=passed,
                    message=f"Missing columns: {missing}" if missing else "All schema columns present",
                    details={"missing_columns": missing, "expected_columns": expected_cols},
                )
            )

        # 2. Rule verification tests
        for i, rule in enumerate(rules):
            field = rule.target_field
            family_str = rule.family.value if isinstance(rule.family, RuleFamily) else str(rule.family)

            if field not in clean_df.columns and family_str != "cross_field":
                results.append(
                    TestResult(
                        test_name=f"rule_field_exists_{field}_{i}",
                        passed=False,
                        message=f"Field '{field}' does not exist in clean DataFrame",
                    )
                )
                continue

            if family_str == "not_null":
                null_cnt = int(clean_df[field].isna().sum())
                results.append(
                    TestResult(
                        test_name=f"not_null_check_{field}",
                        passed=null_cnt == 0,
                        message=f"Found {null_cnt} nulls in '{field}'" if null_cnt > 0 else f"0 nulls in '{field}'",
                        details={"null_count": null_cnt},
                    )
                )
            elif family_str == "unique":
                dup_cnt = int(clean_df.duplicated(subset=[field]).sum())
                results.append(
                    TestResult(
                        test_name=f"unique_check_{field}",
                        passed=dup_cnt == 0,
                        message=f"Found {dup_cnt} duplicates in '{field}'" if dup_cnt > 0 else f"0 duplicates in '{field}'",
                        details={"duplicate_count": dup_cnt},
                    )
                )
            elif family_str == "range":
                params = rule.parameters or {}
                min_v = params.get("min")
                max_v = params.get("max")
                series = pd.to_numeric(clean_df[field], errors="coerce")

                viol = 0
                if min_v is not None:
                    viol += int((series < min_v).sum())
                if max_v is not None:
                    viol += int((series > max_v).sum())

                results.append(
                    TestResult(
                        test_name=f"range_check_{field}",
                        passed=viol == 0,
                        message=f"Found {viol} range violations in '{field}'" if viol > 0 else f"0 range violations in '{field}'",
                        details={"violations": viol, "min": min_v, "max": max_v},
                    )
                )

        passed_cnt = sum(1 for r in results if r.passed)
        failed_cnt = len(results) - passed_cnt

        return TestSuiteResult(
            total_tests=len(results),
            passed=passed_cnt,
            failed=failed_cnt,
            results=results,
        )
