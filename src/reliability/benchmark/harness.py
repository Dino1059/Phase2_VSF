"""
Benchmark harness for offline C0/C1/A1 capability comparison.
Runs investigators on ground truth dataset, computes metrics, outputs results.
"""
import time
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.reliability.benchmark.models import (
    BenchmarkCase,
    BenchmarkResults,
    BenchmarkCaseResult,
    InvestigatorResult,
    GroundTruthLabel,
)
from src.reliability.benchmark.metrics import (
    compute_benchmark_results,
    determine_case_winner,
)
from src.reliability.investigation.c0 import C0DeterministicBaseline
from src.reliability.investigation.c1 import C1FixedInvestigator
from src.reliability.investigation.a1 import A1BoundedInvestigator
from src.reliability.governance.recommendations import RecommendationRouter
from src.reliability.models.hypothesis import CauseClassification


class BenchmarkHarness:
    """
    Offline benchmark runner for C0/C1/A1 capability comparison.

    Design V2:
    - C0: Deterministic baseline (no LLM, fixed rule lookups, <10ms SLA)
    - C1: Fixed evidence bundle + 1 LLM call (deterministic context, controlled LLM)
    - A1: Dynamic ReAct loop with bounded tools (production path)

    Benchmark flow:
    1. Load benchmark dataset (list of BenchmarkCase)
    2. Run each investigator (C0/C1/A1) on each case
    3. Compute metrics: Precision/Recall/F1, Keyword Match, Latency, Cost
    4. Output BenchmarkResults for architecture decision-making

    Usage:
        harness = BenchmarkHarness()
        results = harness.run_all(dataset)
        harness.save_results(results, "results.json")
    """

    def __init__(
        self,
        enable_c0: bool = True,
        enable_c1: bool = True,
        enable_a1: bool = True,
        max_a1_tool_calls: int = 5,
        max_a1_tokens: int = 2000,
        max_a1_wallclock_sec: float = 30.0,
    ):
        self.enable_c0 = enable_c0
        self.enable_c1 = enable_c1
        self.enable_a1 = enable_a1

        # Investigators (lazy init)
        self._c0: Optional[C0DeterministicBaseline] = None
        self._c1: Optional[C1FixedInvestigator] = None
        self._a1: Optional[A1BoundedInvestigator] = None

        # A1 bounds
        self.max_a1_tool_calls = max_a1_tool_calls
        self.max_a1_tokens = max_a1_tokens
        self.max_a1_wallclock_sec = max_a1_wallclock_sec

    @property
    def c0(self) -> C0DeterministicBaseline:
        if self._c0 is None:
            self._c0 = C0DeterministicBaseline(router=RecommendationRouter())
        return self._c0

    @property
    def c1(self) -> C1FixedInvestigator:
        if self._c1 is None:
            from src.services.llm import UnifiedLLMAdapter
            self._c1 = C1FixedInvestigator(router=RecommendationRouter(), llm=UnifiedLLMAdapter())
        return self._c1

    @property
    def a1(self) -> A1BoundedInvestigator:
        if self._a1 is None:
            from src.services.llm import UnifiedLLMAdapter
            self._a1 = A1BoundedInvestigator(
                max_tool_calls=self.max_a1_tool_calls,
                max_tokens_budget=self.max_a1_tokens,
                max_wall_clock_sec=self.max_a1_wallclock_sec,
                router=RecommendationRouter(),
                llm=UnifiedLLMAdapter(),
            )
        return self._a1

    def _run_c0(self, case: BenchmarkCase) -> InvestigatorResult:
        """Runs C0 deterministic baseline on a benchmark case."""
        t0 = time.perf_counter()

        try:
            hyp, rec = self.c0.investigate_incident(
                incident=case.incident,
                initial_evidence=case.evidence,
            )

            wall_ms = (time.perf_counter() - t0) * 1000

            if hyp is None:
                return InvestigatorResult(
                    case_id=case.case_id,
                    investigator_id="C0",
                    status="NONE",
                    wall_clock_ms=wall_ms,
                    tokens_used=0,
                    tool_calls_made=0,
                )

            return InvestigatorResult(
                case_id=case.case_id,
                investigator_id="C0",
                hypothesis_claim=hyp.claim,
                hypothesis_classification=hyp.classification,
                hypothesis_confidence=hyp.confidence,
                supporting_evidence_ids=hyp.supporting_evidence,
                contradicting_evidence_ids=hyp.contradicting_evidence,
                missing_evidence=hyp.missing_evidence,
                status="RESOLVED",
                wall_clock_ms=wall_ms,
                tokens_used=0,  # C0 uses no LLM
                tool_calls_made=0,
                stop_reason="deterministic_resolved" if hyp else "no_rule_match",
            )
        except Exception as e:
            wall_ms = (time.perf_counter() - t0) * 1000
            return InvestigatorResult(
                case_id=case.case_id,
                investigator_id="C0",
                status="NONE",
                wall_clock_ms=wall_ms,
                tokens_used=0,
                tool_calls_made=0,
                stop_reason=f"error: {str(e)[:100]}",
            )

    def _run_c1(self, case: BenchmarkCase) -> InvestigatorResult:
        """Runs C1 fixed workflow on a benchmark case."""
        t0 = time.perf_counter()

        try:
            # C1 builds fixed evidence bundle and runs 1 LLM call
            context = self.c1.build_context(case.incident, case.evidence)
            hyp, rec = self.c1.investigate_incident(
                incident=case.incident,
                available_evidence=case.evidence,
            )

            wall_ms = (time.perf_counter() - t0) * 1000

            return InvestigatorResult(
                case_id=case.case_id,
                investigator_id="C1",
                hypothesis_claim=hyp.claim,
                hypothesis_classification=hyp.classification,
                hypothesis_confidence=hyp.confidence,
                supporting_evidence_ids=hyp.supporting_evidence,
                contradicting_evidence_ids=hyp.contradicting_evidence,
                missing_evidence=hyp.missing_evidence,
                status="RESOLVED",
                wall_clock_ms=wall_ms,
                tokens_used=500,  # Estimate: C1 uses 1 fixed LLM call
                tool_calls_made=0,
                stop_reason="fixed_workflow_completed",
            )
        except Exception as e:
            wall_ms = (time.perf_counter() - t0) * 1000
            return InvestigatorResult(
                case_id=case.case_id,
                investigator_id="C1",
                status="NONE",
                wall_clock_ms=wall_ms,
                tokens_used=0,
                tool_calls_made=0,
                stop_reason=f"error: {str(e)[:100]}",
            )

    def _run_a1(self, case: BenchmarkCase) -> InvestigatorResult:
        """Runs A1 dynamic ReAct loop on a benchmark case."""
        t0 = time.perf_counter()

        try:
            hyp, rec, meta = self.a1.investigate_incident_dynamically(
                incident=case.incident,
                initial_evidence=case.evidence,
            )

            wall_ms = (time.perf_counter() - t0) * 1000

            status = "ABSTAINED" if hyp.classification == "UNKNOWN" else "RESOLVED"

            return InvestigatorResult(
                case_id=case.case_id,
                investigator_id="A1",
                hypothesis_claim=hyp.claim,
                hypothesis_classification=hyp.classification,
                hypothesis_confidence=hyp.confidence,
                supporting_evidence_ids=hyp.supporting_evidence,
                contradicting_evidence_ids=hyp.contradicting_evidence,
                missing_evidence=hyp.missing_evidence,
                status=status,
                wall_clock_ms=wall_ms,
                tokens_used=meta.get("tokens_spent", 0),
                tool_calls_made=meta.get("tool_calls_made", 0),
                stop_reason=meta.get("stop_reason"),
            )
        except Exception as e:
            wall_ms = (time.perf_counter() - t0) * 1000
            return InvestigatorResult(
                case_id=case.case_id,
                investigator_id="A1",
                status="NONE",
                wall_clock_ms=wall_ms,
                tokens_used=0,
                tool_calls_made=0,
                stop_reason=f"error: {str(e)[:100]}",
            )

    def run_all(
        self,
        dataset: List[BenchmarkCase],
        use_cache: bool = True,
        cache_path: Optional[str | Path] = "eval/benchmarks/.cache/case_results_cache.json"
    ) -> BenchmarkResults:
        """
        Runs all enabled investigators on all benchmark cases.
        Supports per-case disk caching to avoid repeating LLM/tool computations and save tokens.
        Returns aggregated BenchmarkResults.
        """
        all_case_results: List[BenchmarkCaseResult] = []
        cache_file = Path(cache_path) if cache_path else None
        cached_data: Dict[str, Any] = {}

        if use_cache and cache_file and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
            except Exception as e:
                print(f"[BenchmarkCache] Warning: could not load cache from {cache_file}: {e}")
                cached_data = {}

        for case in dataset:
            # Check if case result is cached
            if use_cache and case.case_id in cached_data:
                try:
                    case_res = BenchmarkCaseResult.model_validate(cached_data[case.case_id])
                    all_case_results.append(case_res)
                    continue
                except Exception:
                    pass

            c0_result: Optional[InvestigatorResult] = None
            c1_result: Optional[InvestigatorResult] = None
            a1_result: Optional[InvestigatorResult] = None

            # Run C0
            if self.enable_c0:
                c0_result = self._run_c0(case)

            # Run C1
            if self.enable_c1:
                c1_result = self._run_c1(case)

            # Run A1
            if self.enable_a1:
                a1_result = self._run_a1(case)

            # Determine winner
            winner, reason = determine_case_winner(c0_result, c1_result, a1_result, case.ground_truth)

            case_result = BenchmarkCaseResult(
                case_id=case.case_id,
                case_name=case.case_name,
                category=case.category,
                difficulty=case.difficulty,
                ground_truth=case.ground_truth,
                c0_result=c0_result,
                c1_result=c1_result,
                a1_result=a1_result,
                winner=winner,
                winner_reason=reason,
            )
            all_case_results.append(case_result)

            # Save to cache immediately (atomic resume support)
            if use_cache and cache_file:
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cached_data[case.case_id] = case_result.model_dump(mode="json")
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cached_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"[BenchmarkCache] Warning: could not write to cache {cache_file}: {e}")

        # Compute aggregated metrics
        return compute_benchmark_results(all_case_results)

    def save_results(self, results: BenchmarkResults, output_path: str) -> None:
        """Saves benchmark results to JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict for JSON serialization
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    def load_results(self, input_path: str) -> BenchmarkResults:
        """Loads benchmark results from JSON file."""
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        return BenchmarkResults.model_validate(data)

    def print_summary(self, results: BenchmarkResults) -> None:
        """Prints a human-readable summary of benchmark results."""
        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS SUMMARY")
        print("=" * 70)
        print(f"Version: {results.benchmark_version}")
        print(f"Total Cases: {results.total_cases}")
        print(f"Categories: {', '.join(results.categories_covered)}")
        print()

        for inv_id, metrics in results.investigator_metrics.items():
            print(f"\n{'-' * 50}")
            print(f"Investigator: {inv_id}")
            print(f"{'-' * 50}")
            print(f"  Precision:     {metrics.precision:.4f}")
            print(f"  Recall:       {metrics.recall:.4f}")
            print(f"  F1 Score:     {metrics.f1_score:.4f}")
            print(f"  Avg Latency:  {metrics.avg_latency_ms:.2f} ms")
            print(f"  Total Cases:  {metrics.total_cases}")
            print(f"  Resolved:     {metrics.cases_resolved}")
            print(f"  Abstention:   {metrics.abstention_rate:.2%}")

        print("\n" + "=" * 70)
        print("PER-CASE WINNERS")
        print("=" * 70)

        winner_counts: Dict[str, int] = {}
        for cr in results.case_results:
            w = cr.winner or "NONE"
            winner_counts[w] = winner_counts.get(w, 0) + 1

        for w, count in sorted(winner_counts.items(), key=lambda x: -x[1]):
            print(f"  {w}: {count} cases")

        print()
