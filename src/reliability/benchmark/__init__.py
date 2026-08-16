"""
Reliability Benchmark Module.
Offline benchmark harness for C0/C1/A1 capability comparison.
"""

# Core models (no duckdb dependency)
from src.reliability.benchmark.models import (
    GroundTruthLabel,
    BenchmarkCase,
    InvestigatorResult,
    BenchmarkResults,
    BenchmarkCaseResult,
    InvestigatorMetrics,
    CategoryMetrics,
)
from src.reliability.benchmark.metrics import (
    compute_keyword_match_score,
    compute_precision_recall_f1,
    compute_investigator_metrics,
    compute_benchmark_results,
    determine_case_winner,
)

__all__ = [
    # Models
    "GroundTruthLabel",
    "BenchmarkCase",
    "InvestigatorResult",
    "BenchmarkResults",
    "BenchmarkCaseResult",
    "InvestigatorMetrics",
    "CategoryMetrics",
    # Metrics
    "compute_keyword_match_score",
    "compute_precision_recall_f1",
    "compute_investigator_metrics",
    "compute_benchmark_results",
    "determine_case_winner",
]


def __getattr__(name: str):
    """Lazy import BenchmarkHarness to avoid duckdb dependency at import time."""
    if name == "BenchmarkHarness":
        from src.reliability.benchmark.harness import BenchmarkHarness
        return BenchmarkHarness
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
