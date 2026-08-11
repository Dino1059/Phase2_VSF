import pytest
from eval.eval_rca import (
    run_rca_evaluation,
    get_hidden_rca_ground_truth_cases,
    RCAGroundTruthCase
)
from src.reliability.investigation.c1 import C1FixedInvestigator
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence


def test_get_hidden_rca_ground_truth_cases():
    cases = get_hidden_rca_ground_truth_cases()
    assert len(cases) >= 5
    for case in cases:
        assert isinstance(case, RCAGroundTruthCase)
        assert case.case_id.startswith("RCAC-")
        assert case.expected_classification in ["OPERATIONAL", "DATA", "UNKNOWN", "MIXED"]


def test_run_rca_evaluation_dynamic():
    res = run_rca_evaluation()
    assert "rca_evaluation" in res
    assert "safety_guardrails" in res
    metrics = res["rca_evaluation"]

    required_keys = [
        "top1_cause_accuracy",
        "top3_cause_recall",
        "evidence_precision",
        "evidence_recall",
        "unsupported_claim_rate",
        "abstention_precision"
    ]
    for key in required_keys:
        assert key in metrics
        val = metrics[key]
        assert isinstance(val, float)
        assert 0.0 <= val <= 1.0

    sg = res["safety_guardrails"]
    assert sg["evidence_precision_min_target"] == 0.90
    assert sg["unsupported_claim_rate_max_target"] == 0.05
    assert isinstance(sg["safety_guardrails_passed"], bool)


def test_run_rca_evaluation_custom_cases():
    cases = get_hidden_rca_ground_truth_cases()[:3]
    res = run_rca_evaluation(cases=cases)
    assert "rca_evaluation" in res
    metrics = res["rca_evaluation"]
    assert metrics["top1_cause_accuracy"] >= 0.0


def test_run_rca_evaluation_empty_cases():
    res = run_rca_evaluation(cases=[])
    assert res == {
        "rca_evaluation": {
            "top1_cause_accuracy": 0.0,
            "top3_cause_recall": 0.0,
            "evidence_precision": 0.0,
            "evidence_recall": 0.0,
            "unsupported_claim_rate": 0.0,
            "abstention_precision": 0.0
        },
        "safety_guardrails": {
            "evidence_precision_min_target": 0.90,
            "evidence_precision_passed": False,
            "unsupported_claim_rate_max_target": 0.05,
            "unsupported_claim_rate_passed": True,
            "safety_guardrails_passed": False
        }
    }
