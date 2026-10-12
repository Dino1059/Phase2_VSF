"""
DataTrust OS: Safe Historical Pipeline Runs Migration
Corrects erroneous not_evaluated_count values for historical SUCCESS runs.
Ensures mathematical invariant: scanned = silver + quarantine + warning + not_evaluated.

Usage:
    python scripts/fix_historical_not_evaluated_runs.py --dry-run
    python scripts/fix_historical_not_evaluated_runs.py --commit
"""

import os
import sys
import argparse
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.profiler_engine import get_db_connection
from psycopg2.extras import RealDictCursor


def inspect_and_fix_runs(commit: bool = False) -> int:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query candidate SUCCESS runs
            cur.execute("""
                SELECT run_id, dataset_id, status, scanned_count, silver_count,
                       quarantine_count, warning_count, not_evaluated_count, started_at
                FROM orchestration.pipeline_runs
                WHERE status = 'SUCCESS'
                  AND scanned_count > 0
                ORDER BY started_at DESC;
            """)
            runs: List[Dict[str, Any]] = cur.fetchall()

        candidates = []
        for r in runs:
            scanned = r.get("scanned_count") or 0
            silver = r.get("silver_count") or 0
            quar = r.get("quarantine_count") or 0
            warn = r.get("warning_count") or 0
            current_not_eval = r.get("not_evaluated_count") or 0

            # Guard condition: classified counts must not exceed scanned_count
            if (silver + quar + warn) > scanned:
                print(f"[SKIP] Run {r['run_id']} has inconsistent data: silver({silver}) + quar({quar}) + warn({warn}) > scanned({scanned})")
                continue

            expected_not_eval = max(0, scanned - silver - quar - warn)

            if current_not_eval != expected_not_eval:
                candidates.append({
                    "run_id": r["run_id"],
                    "dataset_id": r["dataset_id"],
                    "scanned": scanned,
                    "silver": silver,
                    "quarantine": quar,
                    "warning": warn,
                    "old_not_eval": current_not_eval,
                    "new_not_eval": expected_not_eval,
                })

        print(f"--- Evaluated {len(runs)} SUCCESS runs. Found {len(candidates)} candidate runs requiring correction. ---")
        if not candidates:
            print("All runs are already consistent. No updates required.")
            return 0

        print(f"{'Run ID':<22} | {'Dataset':<32} | {'Scanned':<8} | {'Silver':<7} | {'Quar':<7} | {'Warn':<7} | {'Old NotEval':<12} -> {'New NotEval':<12}")
        print("-" * 125)
        for c in candidates:
            print(f"{c['run_id']:<22} | {c['dataset_id']:<32} | {c['scanned']:<8} | {c['silver']:<7} | {c['quarantine']:<7} | {c['warning']:<7} | {c['old_not_eval']:<12} -> {c['new_not_eval']:<12}")

        if not commit:
            print("\n[DRY RUN MODE] No changes written to database. Run with --commit to apply fixes.")
            return len(candidates)

        print("\nApplying updates with transaction commit...")
        with conn.cursor() as cur:
            for c in candidates:
                cur.execute("""
                    UPDATE orchestration.pipeline_runs
                    SET not_evaluated_count = %s
                    WHERE run_id = %s;
                """, (c["new_not_eval"], c["run_id"]))
            conn.commit()

        print(f"Successfully updated {len(candidates)} runs in orchestration.pipeline_runs.")
        return len(candidates)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix historical not_evaluated_count values.")
    parser.add_argument("--commit", action="store_true", help="Commit changes to database (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run only")
    args = parser.parse_args()

    commit_mode = args.commit and not args.dry_run
    inspect_and_fix_runs(commit=commit_mode)
