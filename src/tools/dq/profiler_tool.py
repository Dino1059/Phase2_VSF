"""Profiler Tool — typed wrapper around scripts/profile_source_db.py.

Returns schema + aggregate metadata ONLY (row/column counts, column types,
null rate, distinct count, duplicate count). It never inspects individual
row values and never flags anomalies/violations — that is the Test
Runner's job downstream.
"""
from __future__ import annotations  # noqa: I001 - block below intentionally not import-sorted

import sqlite3
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from src.tools.dq.common import ErrorCode, ToolError, execute

from profile_source_db import get_tables, profile_table  # noqa: E402  (path set up by common)


class ProfilerInput(BaseModel):
    db_path: str = "data/source.db"
    tables: list[str] | None = Field(default=None, description="Subset of tables to profile; None = all tables")
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)


class ColumnMetadata(BaseModel):
    column: str
    declared_type: str
    observed_dtype: str
    null_count: int
    null_rate: float
    distinct_count: int


class TableProfile(BaseModel):
    table: str
    row_count: int
    column_count: int
    primary_key: list[str]
    duplicate_count: int
    columns: list[ColumnMetadata]


class ProfilerOutput(BaseModel):
    status: Literal["success", "error"]
    error_code: ErrorCode
    error_message: str = ""
    tables: list[TableProfile] = []
    execution_time_seconds: float = 0.0


def _do_profile(params: ProfilerInput) -> dict:
    from src.tools.dq.common import REPO_ROOT

    db_path = REPO_ROOT / params.db_path
    if not db_path.exists():
        raise ToolError(ErrorCode.DB_NOT_FOUND, f"database not found: {db_path}")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        all_tables = get_tables(conn)
        if params.tables:
            missing = sorted(set(params.tables) - set(all_tables))
            if missing:
                raise ToolError(ErrorCode.TABLE_NOT_FOUND, f"tables not found in schema: {missing}")
            target_tables = params.tables
        else:
            target_tables = all_tables
        tables = [profile_table(conn, t) for t in target_tables]
    finally:
        conn.close()
    return {"tables": tables}


def run_profiler(params: ProfilerInput | dict) -> ProfilerOutput:
    if not isinstance(params, ProfilerInput):
        try:
            params = ProfilerInput(**params)
        except ValidationError as e:
            return ProfilerOutput(status="error", error_code=ErrorCode.INVALID_INPUT, error_message=str(e))

    status, code, message, payload, elapsed = execute(lambda: _do_profile(params), params.timeout_seconds)
    if status == "error":
        return ProfilerOutput(status=status, error_code=code, error_message=message, execution_time_seconds=elapsed)
    return ProfilerOutput(
        status="success",
        error_code=ErrorCode.NONE,
        tables=[TableProfile(**t) for t in payload["tables"]],
        execution_time_seconds=elapsed,
    )
