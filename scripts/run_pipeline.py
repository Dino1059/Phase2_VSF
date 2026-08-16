#!/usr/bin/env python3
"""
Pipeline Orchestrator for the DataTrust OS data quality pipeline (Task 1).

Runs the 5 pipeline tools in order, streaming each step's output to both
the console and a per-step log file, timing each step, and writing a
manifest (data/pipeline_manifest.json) describing the whole run.

Steps:
  1. build_source_db.py   -> data/source.db
  2. profile_source_db.py -> data/profiling_report.{json,md}
  3. validate_rules.py    -> data/rule_validation_report.{json,md}
  4. compile_rules.py     -> data/compiled_rules.{json,md}
  5. run_tests.py         -> data/test_run_report.{json,md}

validate_rules.py and run_tests.py intentionally exit(1) when they find
invalid rules / failing data-quality checks — that is an expected business
outcome ("ok_with_findings"), not a pipeline crash, so the orchestrator
keeps going. Any other non-zero exit (an actual script error) halts the
pipeline immediately and is recorded as "error".

Usage:
  python scripts/run_pipeline.py
"""
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "data" / "logs"

# steps whose exit code 1 means "ran fine, found real issues" rather than "crashed"
GATED_STEPS = {"validate_rules", "run_tests"}

STEPS = [
    ("build_source_db", "scripts/build_source_db.py"),
    ("profile_source_db", "scripts/profile_source_db.py"),
    ("validate_rules", "scripts/validate_rules.py"),
    ("compile_rules", "scripts/compile_rules.py"),
    ("run_tests", "scripts/run_tests.py"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_step(name: str, script: str) -> dict:
    log_path = LOG_DIR / f"{name}.log"
    print(f"\n===== [{name}] {script} =====")

    started_at = now_iso()
    t0 = time.perf_counter()

    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / script)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    with open(log_path, "w", encoding="utf-8") as log_file:
        for line in proc.stdout:
            print(f"  {line}", end="")
            log_file.write(line)
        proc.wait()

    duration = round(time.perf_counter() - t0, 3)
    finished_at = now_iso()
    exit_code = proc.returncode

    if exit_code == 0:
        status = "ok"
    elif exit_code == 1 and name in GATED_STEPS:
        status = "ok_with_findings"
    else:
        status = "error"

    print(f"----- [{name}] exit={exit_code} status={status} duration={duration}s -----")

    return {
        "name": name,
        "script": script,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "exit_code": exit_code,
        "status": status,
        "log_file": str(log_path.relative_to(REPO_ROOT)),
    }


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    pipeline_started_at = now_iso()
    t0 = time.perf_counter()

    steps_report = []
    overall_status = "ok"
    for name, script in STEPS:
        result = run_step(name, script)
        steps_report.append(result)
        if result["status"] == "error":
            overall_status = "error"
            print(f"\nPipeline halted: step '{name}' failed unexpectedly (exit {result['exit_code']}).")
            break
        if result["status"] == "ok_with_findings" and overall_status == "ok":
            overall_status = "ok_with_findings"

    pipeline_finished_at = now_iso()
    manifest = {
        "pipeline_run_id": run_id,
        "started_at": pipeline_started_at,
        "finished_at": pipeline_finished_at,
        "duration_seconds": round(time.perf_counter() - t0, 3),
        "overall_status": overall_status,
        "steps": steps_report,
    }

    manifest_path = REPO_ROOT / "data" / "pipeline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n===== Pipeline finished: {overall_status} in {manifest['duration_seconds']}s =====")
    print(f"Wrote {manifest_path}")

    if overall_status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
