import pytest
from pathlib import Path
from eval.eval_failure_analysis import (
    A1FailureAnalyzer,
    FailureMode,
    FailureAnalysisCase,
    classify_a1_failure,
    get_failure_analysis_benchmark_cases,
    generate_markdown_report,
    run_failure_analysis,
    main as cli_main,
)
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis


def test_get_failure_analysis_benchmark_cases():
    cases = get_failure_analysis_benchmark_cases()
    assert len(cases) >= 5
    for case in cases:
        assert isinstance(case, FailureAnalysisCase)
        assert case.case_id.startswith("FA-CASE-")
        assert case.expected_classification in ["OPERATIONAL", "DATA", "UNKNOWN"]


def test_classify_a1_failure_budget_exhaustion():
    c_inc = Incident(incident_id="inc-test", project_id="p", entity_ids=["E1"], signal_ids=["sig-1"], admission_reason="reason")
    case = FailureAnalysisCase(
        case_id="FA-TEST-01",
        name="Test",
        incident=c_inc,
        initial_evidence=[],
        expected_classification="OPERATIONAL",
        ground_truth_evidence_ids=set(),
        description="test",
    )
    hyp = Hypothesis(incident_id="inc-test", claim="test", classification="UNKNOWN")
    meta = {"stop_reason": "max_tool_calls_exceeded", "tool_calls_made": 5, "tokens_spent": 2000}

    mode, expl = classify_a1_failure(case, hyp, meta)
    assert mode == FailureMode.BUDGET_EXHAUSTION
    assert "operational bound exceeded" in expl


def test_classify_a1_failure_false_contradiction():
    c_inc = Incident(incident_id="inc-test", project_id="p", entity_ids=["E1"], signal_ids=["sig-1"], admission_reason="reason")
    case = FailureAnalysisCase(
        case_id="FA-TEST-02",
        name="Test",
        incident=c_inc,
        initial_evidence=[],
        expected_classification="OPERATIONAL",
        ground_truth_evidence_ids=set(),
        description="test",
    )
    hyp = Hypothesis(
        incident_id="inc-test",
        claim="Dynamic A1 abstained: Contradictory evidence detected",
        classification="UNKNOWN",
    )
    meta = {"stop_reason": "completed"}

    mode, expl = classify_a1_failure(case, hyp, meta)
    assert mode == FailureMode.FALSE_CONTRADICTION
    assert "falsely abstained" in expl


def test_classify_a1_failure_unsupported_claim():
    c_inc = Incident(incident_id="inc-test", project_id="p", entity_ids=["E1"], signal_ids=["sig-1"], admission_reason="reason")
    ev = Evidence(evidence_id="ev-real", source_type="t", source_id="s", entity_ids=["E1"], content_hash="hash1", summary="summary")
    case = FailureAnalysisCase(
        case_id="FA-TEST-03",
        name="Test",
        incident=c_inc,
        initial_evidence=[ev],
        expected_classification="OPERATIONAL",
        ground_truth_evidence_ids={"ev-real"},
        description="test",
    )
    # Hypothesis referencing hallucinated evidence
    hyp = Hypothesis(
        incident_id="inc-test",
        claim="Claim",
        classification="SYSTEM_DATA_LOGIC",
        supporting_evidence=["ev-hallucinated-999"],
    )
    meta = {"stop_reason": "completed"}

    mode, expl = classify_a1_failure(case, hyp, meta)
    assert mode == FailureMode.UNSUPPORTED_CLAIM
    assert "invalid/hallucinated evidence" in expl


def test_classify_a1_failure_insufficient_tool_depth():
    c_inc = Incident(incident_id="inc-test", project_id="p", entity_ids=["E1"], signal_ids=["sig-1"], admission_reason="reason")
    ev = Evidence(evidence_id="ev-real", source_type="t", source_id="s", entity_ids=["E1"], content_hash="hash1", summary="summary")
    case = FailureAnalysisCase(
        case_id="FA-TEST-04",
        name="Test",
        incident=c_inc,
        initial_evidence=[ev],
        expected_classification="OPERATIONAL",
        ground_truth_evidence_ids={"ev-real"},
        description="test",
        requires_specialist_tools=True,
    )
    hyp = Hypothesis(
        incident_id="inc-test",
        claim="Claim",
        classification="SYSTEM_DATA_LOGIC",
        supporting_evidence=["ev-real"],
    )
    meta = {"stop_reason": "completed"}

    mode, expl = classify_a1_failure(case, hyp, meta)
    assert mode == FailureMode.INSUFFICIENT_TOOL_DEPTH


def test_run_failure_analysis(tmp_path):
    results_dir = tmp_path / "results"
    report_res = run_failure_analysis(save_artifacts=True, results_dir=results_dir)

    assert "summary" in report_res
    assert "failure_mode_breakdown" in report_res
    assert "a2_justified_per_plan_6_4" in report_res

    assert (results_dir / "eval_failure_analysis_report.md").exists()
    assert (results_dir / "eval_failure_analysis_latest.json").exists()


def test_generate_markdown_report():
    analyzer = A1FailureAnalyzer()
    res = analyzer.run_analysis()
    md = generate_markdown_report(res)

    assert "# DataTrust OS v4.2 — A1 Failure Analysis & A2 Justification Report" in md
    assert "PLAN.md §6.4" in md
    assert "INSUFFICIENT_TOOL_DEPTH" in md
    assert "FALSE_CONTRADICTION" in md
    assert "BUDGET_EXHAUSTION" in md
    assert "UNSUPPORTED_CLAIM" in md
    assert "proposed_specialist_or_verifier:" in md
