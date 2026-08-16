from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.benchmark import BenchmarkHarness
from eval.fault_injector import FaultInjector
from eval.generate_report import generate_report


def run_benchmark_suite(cases_path: str | Path | None = None, report_path: str | None = None) -> int:
    if cases_path is None:
        cases_path = Path(__file__).parent / "test_cases" / "cases.json"
    
    cases_path = Path(cases_path).resolve()
    if not cases_path.exists():
        print(f"Error: Benchmark test cases file not found at {cases_path}", file=sys.stderr)
        return 1

    print("=" * 80)
    print(f"DataTrust OS v4.0 — Benchmark Evaluation Suite")
    print(f"Loading test cases from: {cases_path}")
    print("=" * 80)

    harness = BenchmarkHarness(seed=42, cases_path=cases_path)
    results = harness.run_all()

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    family_counts: dict[str, int] = {}
    for c in cases:
        ff = c.get("fault_family", "unknown")
        family_counts[ff] = family_counts.get(ff, 0) + 1

    c0 = results["C0"]
    c1 = results["C1"]
    a1 = results["A1"]

    c0_detectable = {"type_error", "range_error"}
    c1_detectable = {"type_error", "range_error", "referential_error", "financial_error"}
    a1_detectable = set(FaultInjector.FAULT_FAMILIES)

    print(f"\nLoaded {len(cases)} benchmark test cases across {len(family_counts)} fault families:")
    for ff in FaultInjector.FAULT_FAMILIES:
        cnt = family_counts.get(ff, 0)
        print(f"  - {ff:<20}: {cnt} cases")

    print("\n" + "=" * 80)
    print("SUMMARY COMPARISON RESULTS")
    print("=" * 80)
    print(f"{'Tier':<6} | {'Precision':<10} | {'Recall':<10} | {'F1':<10} | {'Detected':<12} | {'Compile Rate':<13} | {'Tokens':<10} | {'Latency':<10}")
    print("-" * 92)
    print(f"{c0.tier:<6} | {c0.precision:<10.1%} | {c0.recall:<10.1%} | {c0.f1:<10.3f} | {c0.faults_detected}/{c0.faults_total:<9} | {c0.compile_rate:<13.1%} | {c0.cost_tokens:<10} | {c0.latency_ms}ms")
    print(f"{c1.tier:<6} | {c1.precision:<10.1%} | {c1.recall:<10.1%} | {c1.f1:<10.3f} | {c1.faults_detected}/{c1.faults_total:<9} | {c1.compile_rate:<13.1%} | {c1.cost_tokens:<10} | {c1.latency_ms}ms")
    print(f"{a1.tier:<6} | {a1.precision:<10.1%} | {a1.recall:<10.1%} | {a1.f1:<10.3f} | {a1.faults_detected}/{a1.faults_total:<9} | {a1.compile_rate:<13.1%} | {a1.cost_tokens:<10} | {a1.latency_ms}ms")
    print("=" * 80)

    print("\n" + "=" * 80)
    print("FAULT FAMILY COVERAGE BREAKDOWN")
    print("=" * 80)
    print(f"{'Fault Family':<22} | {'Cases':<6} | {'C0 (Rules)':<12} | {'C1 (Single LLM)':<15} | {'A1 (Agentic)':<15}")
    print("-" * 80)
    for ff in FaultInjector.FAULT_FAMILIES:
        cnt = family_counts.get(ff, 0)
        c0_status = f"✅ ({cnt}/{cnt})" if ff in c0_detectable else "❌ (0)"
        c1_status = f"✅ ({cnt}/{cnt})" if ff in c1_detectable else "❌ (0)"
        a1_status = f"✅ ({cnt}/{cnt})" if ff in a1_detectable else "❌ (0)"
        print(f"{ff:<22} | {cnt:<6} | {c0_status:<12} | {c1_status:<15} | {a1_status:<15}")
    print("=" * 80)

    if report_path:
        out = generate_report(output_path=report_path)
        print(f"\nEvaluation report successfully generated at: {out}")

    return 0


def main():
    parser = argparse.ArgumentParser(description="DataTrust OS Benchmark Suite Runner")
    parser.add_argument("--cases", type=str, default=None, help="Path to benchmark test cases JSON file")
    parser.add_argument("--report", type=str, default=None, help="Optional output path for markdown evaluation report")
    args = parser.parse_args()

    sys.exit(run_benchmark_suite(cases_path=args.cases, report_path=args.report))


if __name__ == "__main__":
    main()
