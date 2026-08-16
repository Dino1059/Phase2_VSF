import pytest
from eval.eval_agentic import run_unbiased_agentic_evaluation


def test_run_unbiased_agentic_evaluation():
    res = run_unbiased_agentic_evaluation(save_artifact=False)
    assert "agentic_comparison" in res
    assert "safety_guardrails" in res

    comp = res["agentic_comparison"]
    for model_key in ["R0_Deterministic", "C1_Fixed_Workflow", "A1_Bounded_Dynamic"]:
        assert model_key in comp
        model_metrics = comp[model_key]
        assert "evidence_precision" in model_metrics
        assert "unsupported_claim_rate" in model_metrics
        assert "evidence_recall" in model_metrics
        assert "top1_accuracy" in model_metrics

        assert 0.0 <= model_metrics["evidence_precision"] <= 1.0
        assert 0.0 <= model_metrics["unsupported_claim_rate"] <= 1.0

    sg = res["safety_guardrails"]
    assert sg["A1_evidence_precision_min_target"] == 0.90
    assert sg["A1_unsupported_claim_rate_max_target"] == 0.05
    assert isinstance(sg["A1_safety_guardrails_passed"], bool)
