"""Shared plumbing for the data-quality Tool Layer (Task 2).

Every tool in src/tools/dq/ (Profiler, Validator, Compiler, Test Runner)
wraps the deterministic pipeline logic in scripts/*.py (Task 1) behind a
typed, timeout-guarded, standardized-error-code interface so an AI Agent
can call them safely without executing arbitrary code.
"""
from __future__ import annotations

import concurrent.futures
import sys
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TypeVar

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class ErrorCode(str, Enum):  # noqa: UP042 - runtime here is Python 3.10; enum.StrEnum needs 3.11+
    NONE = "NONE"
    INVALID_INPUT = "INVALID_INPUT"
    DB_NOT_FOUND = "DB_NOT_FOUND"
    SCHEMA_NOT_FOUND = "SCHEMA_NOT_FOUND"
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    OPERATOR_NOT_WHITELISTED = "OPERATOR_NOT_WHITELISTED"
    RULE_INVALID = "RULE_INVALID"
    TIMEOUT = "TIMEOUT"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class ToolError(Exception):
    """Raised by tool internals; carries a standardized ErrorCode."""

    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code.value}] {message}")


T = TypeVar("T")


def run_with_timeout(fn: Callable[[], T], timeout_seconds: float) -> T:
    """Run fn() with a soft timeout, raising ToolError(TIMEOUT) if exceeded.

    Uses a worker thread rather than signal.alarm because SIGALRM is not
    available on Windows. Note this is a *soft* timeout: if fn() is a
    blocking, uninterruptible call, its thread keeps running in the
    background after this function returns — acceptable here because
    every tool only does short-lived, read-only SQLite/file I/O.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as e:
            raise ToolError(ErrorCode.TIMEOUT, f"execution exceeded {timeout_seconds}s") from e


def execute(fn: Callable[[], dict], timeout_seconds: float) -> tuple[str, ErrorCode, str, dict, float]:
    """Run fn() under a timeout, normalizing all outcomes to one shape.

    Returns (status, error_code, error_message, payload, execution_time_seconds).
    payload is fn()'s return dict on success, {} on any failure.
    """
    start = time.perf_counter()
    try:
        payload = run_with_timeout(fn, timeout_seconds)
        return "success", ErrorCode.NONE, "", payload, round(time.perf_counter() - start, 3)
    except ToolError as e:
        return "error", e.code, e.message, {}, round(time.perf_counter() - start, 3)
    except Exception as e:  # noqa: BLE001 - last-resort guard so tools never raise to the agent
        return "error", ErrorCode.EXECUTION_ERROR, str(e), {}, round(time.perf_counter() - start, 3)
