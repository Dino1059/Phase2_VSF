import pandas as pd
import pytest

from eval.benchmark import (
    AgenticGateResult,
    BenchmarkHarness,
    BenchmarkMetrics,
    evaluate_agentic_gate,
)
from eval.injector import ErrorInjector, GroundTruthLabel


@pytest.fixture
def sample_clean_df():
    return pd.DataFrame({
        "request_datetime": ["2026-05-01 00:01:00", "2026-05-01 00:05:00", "2026-05-01 00:10:00"] * 10,
        "hvfhs_license_num": ["HV0003", "HV0005", "HV0004"] * 10,
        "driver_pay": [15.5, 22.0, 31.2] * 10,
        "trip_miles": [3.2, 5.8, 12.1] * 10,
        "PULocationID": [10, 20, 30] * 10,
        "DOLocationID": [15, 25, 35] * 10,
    })


def test_error_injector_families_and_rates(sample_clean_df):
    injector = ErrorInjector(seed=42)

    # Inject 10%
    dirty_df, labels = injector.inject_errors(sample_clean_df, error_rate=0.10)

    assert len(dirty_df) >= len(sample_clean_df)
    assert len(labels) > 0

    error_types = set(lbl.error_type for lbl in labels)
    # Check that error families are labeled
    assert len(error_types) > 0

    for label in labels:
        assert isinstance(label.row_idx, int)
        assert label.error_type in ["null", "duplicate", "invalid_format", "outlier_range", "schema_drift", "cross_field"]
        assert label.severity in ["low", "medium", "high"]


def test_error_injector_generate_datasets(sample_clean_df):
    injector = ErrorInjector(seed=123)
    datasets = injector.generate_datasets(sample_clean_df)

    assert "easy" in datasets
    assert "medium" in datasets
    assert "hard" in datasets

    assert datasets["easy"]["error_rate"] == 0.05
    assert datasets["medium"]["error_rate"] == 0.10
    assert datasets["hard"]["error_rate"] == 0.20


def test_benchmark_harness(sample_clean_df):
    injector = ErrorInjector(seed=42)
    datasets = injector.generate_datasets(sample_clean_df)

    harness = BenchmarkHarness()
    summary = harness.run_benchmark(datasets)

    assert "dataset_evaluations" in summary
    assert "agentic_gate" in summary

    gate_res = summary["agentic_gate"]
    assert "passed" in gate_res
    assert "recall_gain_pp" in gate_res
    assert "time_reduction_pct" in gate_res


def test_evaluate_agentic_gate_passing():
    c1_metrics = BenchmarkMetrics(
        variant="C1",
        precision=0.85,
        semantic_recall=0.75,
        correction_time_sec=1.0,
        compile_rate=0.90,
        cost_usd=0.001,
        idempotency_score=0.95,
        abstention_quality=0.80,
    )
    a1_metrics = BenchmarkMetrics(
        variant="A1",
        precision=0.92,
        semantic_recall=0.88,  # +13pp gain >= 10pp
        correction_time_sec=0.70,  # 30% reduction >= 25%
        compile_rate=1.0,
        cost_usd=0.0012,  # 1.2x cost <= 2.0x
        idempotency_score=0.99,
        abstention_quality=0.95,
    )

    gate_res = evaluate_agentic_gate(c1_metrics, a1_metrics)
    assert gate_res.passed
    assert gate_res.recall_gain_pp == 13.0
    assert gate_res.time_reduction_pct == 30.0
    assert gate_res.precision_guardrail_met
    assert gate_res.cost_guardrail_met


def test_evaluate_agentic_gate_failing_guardrail():
    c1_metrics = BenchmarkMetrics(
        variant="C1",
        precision=0.85,
        semantic_recall=0.75,
        correction_time_sec=1.0,
        compile_rate=0.90,
        cost_usd=0.001,
        idempotency_score=0.95,
        abstention_quality=0.80,
    )
    a1_metrics = BenchmarkMetrics(
        variant="A1",
        precision=0.75,  # FAILS guardrail (< 80%)
        semantic_recall=0.88,
        correction_time_sec=0.70,
        compile_rate=1.0,
        cost_usd=0.0012,
        idempotency_score=0.99,
        abstention_quality=0.95,
    )

    gate_res = evaluate_agentic_gate(c1_metrics, a1_metrics)
    assert not gate_res.passed
    assert not gate_res.precision_guardrail_met
