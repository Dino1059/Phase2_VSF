#!/usr/bin/env python3
"""
Frozen RCA Benchmark Runner with Clean Prompts and Structured Output Evaluation.

Executes End-to-End RCA Evaluation directly against frozen gold test cases:
1. Loads frozen test cases from eval/rca_benchmark/frozen_testset_v3.json.
2. Executes A1 Bounded ReAct Investigator (Live LLM or Safe Deterministic Fallback).
3. Evaluates with 3-tier deterministic RCABenchmarkEvaluator.
4. Exports comprehensive Markdown Benchmark Report and full JSON execution traces
   to eval/fault_RCA_benchamark/v3_new_GT_cutprompt_formatoutput.

Usage:
  python scripts/optimized_anomaly/run_rca_benchmark_frozen.py [--use-llm] [--output-dir <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.a1 import A1BoundedInvestigator
from src.reliability.benchmark.rca_evaluator import RCABenchmarkEvaluator
from src.services.llm import UnifiedLLMAdapter


def parse_args():
    parser = argparse.ArgumentParser(description="Run Frozen RCA Benchmark Suite")
    parser.add_argument(
        "--testset",
        type=str,
        default="eval/rca_benchmark/frozen_testset_v3.json",
        help="Path to frozen test suite JSON"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="eval/fault_RCA_benchamark/v3_new_GT_cutprompt_formatoutput",
        help="Directory to save evaluation reports and traces"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable live LLM ReAct agent (Gemini/OpenAI/Groq/Ollama)"
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=1.5,
        help="Cooldown in seconds between test cases to prevent rate limits"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of test cases to run"
    )
    return parser.parse_args()


class FrozenRCABenchmarkRunner:
    def __init__(
        self,
        testset_path: str,
        output_dir: str,
        use_llm: bool = False,
        cooldown: float = 1.5,
        limit: Optional[int] = None
    ):
        self.testset_path = Path(testset_path) if Path(testset_path).is_absolute() else (REPO_ROOT / testset_path)
        self.output_dir = Path(output_dir) if Path(output_dir).is_absolute() else (REPO_ROOT / output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir = self.output_dir / "traces"
        self.traces_dir.mkdir(parents=True, exist_ok=True)

        self.use_llm = use_llm
        self.cooldown = cooldown
        self.limit = limit

        self.llm_adapter = None
        if self.use_llm:
            try:
                self.llm_adapter = UnifiedLLMAdapter()
                print("  [OK] UnifiedLLMAdapter initialized successfully.")
            except Exception as e:
                print(f"  [!] Could not init UnifiedLLMAdapter ({e}). Running in deterministic mode.")

        self.a1 = A1BoundedInvestigator(
            llm=self.llm_adapter,
            max_tool_calls=5,
            max_tokens_budget=12000,
            max_wall_clock_sec=60.0
        )
        self.evaluator = RCABenchmarkEvaluator()

    def run(self):
        print("=" * 70)
        print(f"  DATA TRUST OS — ROOT CAUSE ANALYSIS (RCA) BENCHMARK v3")
        print(f"  Target Test Suite: {self.testset_path}")
        print(f"  Output Directory:  {self.output_dir}")
        print(f"  Execution Mode:    {'Live LLM (Clean Prompt)' if self.use_llm else 'Deterministic Baseline'}")
        print("=" * 70)

        # 1. Load test suite
        if not self.testset_path.exists():
            print(f"  [!] Test suite not found at {self.testset_path}. Generating now...")
            from scripts.optimized_anomaly.curate_frozen_testset import build_frozen_testset
            testset = build_frozen_testset()
            self.testset_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.testset_path, "w", encoding="utf-8") as f:
                json.dump(testset, f, indent=2, ensure_ascii=False)
            print(f"  [OK] Test suite curated and saved: {self.testset_path}")
        else:
            with open(self.testset_path, "r", encoding="utf-8") as f:
                testset = json.load(f)

        if self.limit:
            testset = testset[:self.limit]

        print(f"\nLoaded {len(testset)} Gold Test Cases across L1-L4.\n")

        case_results = []

        for idx, case in enumerate(testset, start=1):
            case_id = case["case_id"]
            fam = case["fault_family"]
            layer = case["layer"]
            entity_id = case["entity_id"]

            print(f"[{idx:02d}/{len(testset):02d}] Executing {case_id} ({layer} | {fam} | {entity_id})...")

            # Convert to Incident & Evidence objects
            incident = Incident(
                incident_id=f"INC-{case_id}",
                project_id="vingroup_pilot",
                entity_ids=[entity_id],
                signal_ids=[f"SIG-{case_id}"],
                admission_reason=case["admission_observation"],
                supporting_layers=[layer]
            )

            init_ev_list = []
            for ev_dict in case.get("initial_evidence", []):
                ev = Evidence(
                    evidence_id=ev_dict["evidence_id"],
                    source_type=ev_dict.get("source_type", "detector"),
                    source_id=ev_dict.get("source_id", "det"),
                    entity_ids=[entity_id],
                    content_hash=f"hash-{ev_dict['evidence_id']}",
                    summary=ev_dict.get("summary", "")
                )
                init_ev_list.append(ev)

            # Execute A1 Bounded ReAct Investigation
            t0 = time.perf_counter()
            hyp, rec, meta = self.a1.investigate_incident_dynamically(incident, init_ev_list)
            dur = time.perf_counter() - t0

            # Evaluate with Deterministic Structured Rubric
            eval_res = self.evaluator.evaluate_case(case, hyp, meta)
            case_results.append(eval_res)

            # Save full execution trace
            trace_payload = {
                "case_id": case_id,
                "case_definition": case,
                "hypothesis": hyp.model_dump(),
                "recommendation": rec.model_dump() if rec else None,
                "execution_meta": meta,
                "evaluation": eval_res
            }
            trace_path = self.traces_dir / f"{case_id}.json"
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(trace_payload, f, indent=2, ensure_ascii=False)

            # Console status
            verdict = eval_res["verdict"]
            score = eval_res["overall_score"]
            c_score = eval_res["classification_score"]
            d_score = eval_res["diagnosis_score"]
            g_score = eval_res["grounding_score"]
            print(f"       Verdict: [{verdict}] Score: {score*100:.1f}% (Cls: {c_score*100:.0f}%, Diag: {d_score*100:.0f}%, Grnd: {g_score*100:.0f}%) | Latency: {dur:.2f}s")

            if self.use_llm and self.cooldown > 0:
                time.sleep(self.cooldown)

        # Generate final reports
        print("\n" + "=" * 70)
        print("  GENERATING COMPREHENSIVE BENCHMARK ARTIFACTS...")
        print("=" * 70)

        report_md_path = self.output_dir / "rca_benchmark_report.md"
        report_content = self.evaluator.generate_markdown_report(case_results, output_file=report_md_path)

        summary_json_path = self.output_dir / "benchmark_summary.json"
        summary_payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_cases": len(case_results),
            "passes": sum(1 for r in case_results if r["verdict"] == "PASS"),
            "partials": sum(1 for r in case_results if r["verdict"] == "PARTIAL"),
            "fails": sum(1 for r in case_results if r["verdict"] == "FAIL"),
            "mean_overall_score": round(sum(r["overall_score"] for r in case_results) / max(1, len(case_results)), 3),
            "results": case_results
        }
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Benchmark Complete!")
        print(f"     Markdown Report: {report_md_path}")
        print(f"     Summary JSON:    {summary_json_path}")
        print(f"     Traces Folder:   {self.traces_dir}")
        print("\n" + report_content)


def main():
    args = parse_args()
    runner = FrozenRCABenchmarkRunner(
        testset_path=args.testset,
        output_dir=args.output_dir,
        use_llm=args.use_llm,
        cooldown=args.cooldown,
        limit=args.limit
    )
    runner.run()


if __name__ == "__main__":
    main()
