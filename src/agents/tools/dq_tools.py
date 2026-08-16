"""Agent-facing data-quality tools.

These are the ONLY data-quality operations the LangGraph agent may invoke.
Each one is a thin @tool wrapper around a typed function in src/tools/dq/ —
the agent never gets a raw SQL/shell/eval tool, so it cannot execute
arbitrary code; it can only call these four fixed operations with
structured, validated input.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from src.tools.dq.compiler_tool import CompilerInput, run_compiler
from src.tools.dq.profiler_tool import ProfilerInput, run_profiler
from src.tools.dq.test_runner_tool import TestRunnerInput, run_test_runner
from src.tools.dq.validator_tool import ValidatorInput, run_validator


@tool
def profiler_tool(db_path: str = "data/source.db", tables: list[str] | None = None) -> str:
    """Sinh schema va aggregate metadata (row/column count, null rate, distinct count,
    duplicate count) cho cac bang trong Source DB. KHONG phat hien anomaly/vi pham.

    Args:
        db_path: Duong dan toi SQLite source database.
        tables: Danh sach bang can profile; None = tat ca bang.

    Returns:
        JSON string cua ProfilerOutput (status, error_code, tables, execution_time_seconds).
    """
    result = run_profiler(ProfilerInput(db_path=db_path, tables=tables))
    return result.model_dump_json()


@tool
def validator_tool(rules: list[dict[str, Any]], schema_path: str = "data/profiling_report.json") -> str:
    """Kiem tra rule co hop le hay khong: operator phai nam trong whitelist, table/column
    phai ton tai trong schema, kieu du lieu phai tuong thich voi operator. KHONG chay
    rule tren du lieu that.

    Args:
        rules: Danh sach rule dang dict (rule_id, table, column, operator, value, ...).
        schema_path: Duong dan toi profiling report (output cua profiler_tool).

    Returns:
        JSON string cua ValidatorOutput (status, error_code, results, valid_count, invalid_count).
    """
    result = run_validator(ValidatorInput(rules=rules, schema_path=schema_path))
    return result.model_dump_json()


@tool
def compiler_tool(rules: list[dict[str, Any]], schema_path: str = "data/profiling_report.json") -> str:
    """Bien dich cac rule hop le thanh executable checks (Python expression + SQL WHERE).
    CHI sinh van ban, khong mo ket noi toi database, khong thuc thi gi tren du lieu.

    Args:
        rules: Danh sach rule dang dict, giong input cua validator_tool.
        schema_path: Duong dan toi profiling report.

    Returns:
        JSON string cua CompilerOutput (status, error_code, compiled, skipped).
    """
    result = run_compiler(CompilerInput(rules=rules, schema_path=schema_path))
    return result.model_dump_json()


@tool
def test_runner_tool(
    compiled_rules: list[dict[str, Any]],
    db_path: str = "data/source.db",
    schema_path: str = "data/profiling_report.json",
    include_duplicate_checks: bool = True,
) -> str:
    """Thuc thi cac executable check (tu compiler_tool) tren Source DB o che do READ-ONLY,
    tra ve evidence co cau truc cho tung check (violation_count, sample_violations,
    execution_status). Khong bao gio sua/ghi du lieu.

    Args:
        compiled_rules: Danh sach check da compile (tu output "compiled" cua compiler_tool).
        db_path: Duong dan toi SQLite source database.
        schema_path: Duong dan toi profiling report (dung de sinh check_duplicate).
        include_duplicate_checks: Co tu sinh them 1 check_duplicate cho moi bang hay khong.

    Returns:
        JSON string cua TestRunnerOutput (status, error_code, passed, failed, evidence).
    """
    result = run_test_runner(
        TestRunnerInput(
            compiled_rules=compiled_rules,
            db_path=db_path,
            schema_path=schema_path,
            include_duplicate_checks=include_duplicate_checks,
        )
    )
    return result.model_dump_json()


DQ_TOOLS = [profiler_tool, validator_tool, compiler_tool, test_runner_tool]
