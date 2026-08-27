import pytest
from unittest.mock import MagicMock

from src.agents.baselines import (
    BenchmarkCase,
    BaselineResult,
    Baseline,
    BaselineR0,
    BaselineC1,
    BaselineA1,
    BaselineA2,
)


def test_benchmark_case_instantiation():
    case = BenchmarkCase(
        case_id="case_001",
        dataset_key="charging_sessions",
        ground_truth_faults=[{"fault_id": "f1", "fault_family": "range_error"}],
        permitted_evidence=["telemetry_logs"],
        seed=123,
    )
    assert case.case_id == "case_001"
    assert case.dataset_key == "charging_sessions"
    assert len(case.ground_truth_faults) == 1
    assert case.permitted_evidence == ["telemetry_logs"]
    assert case.seed == 123


def test_baseline_result_dataclass_defaults():
    res = BaselineResult(tier="R0")
    assert res.tier == "R0"
    assert isinstance(res.predictions, set)
    assert isinstance(res.evidence_refs, list)
    assert isinstance(res.tool_trace, list)
    assert isinstance(res.cost_tokens, int)
    assert isinstance(res.latency_ms, int)
    assert isinstance(res.abstained, bool)
    assert isinstance(res.error, str)
    assert res.cost_tokens == 0
    assert res.latency_ms == 0
    assert res.abstained is False
    assert res.error == ""


def test_baselines_protocol_conformance():
    b_r0 = BaselineR0()
    b_c1 = BaselineC1()
    b_a1 = BaselineA1()
    b_a2 = BaselineA2()

    assert isinstance(b_r0, Baseline)
    assert isinstance(b_c1, Baseline)
    assert isinstance(b_a1, Baseline)
    assert isinstance(b_a2, Baseline)

    assert b_r0.tier == "R0"
    assert b_c1.tier == "C1"
    assert b_a1.tier == "A1"
    assert b_a2.tier == "A2"


@pytest.mark.asyncio
async def test_baseline_r0_run():
    b_r0 = BaselineR0()
    case = BenchmarkCase(
        case_id="case_r0",
        dataset_key="charging_sessions",
        ground_truth_faults=[{"fault_id": "f_type_1", "fault_family": "type_error"}],
    )
    result = await b_r0.run(case)

    assert isinstance(result, BaselineResult)
    assert result.tier == "R0"
    assert isinstance(result.predictions, set)
    assert len(result.evidence_refs) > 0
    assert isinstance(result.evidence_refs, list)
    assert isinstance(result.tool_trace, list)
    assert result.cost_tokens == 0
    assert result.latency_ms >= 0
    assert result.abstained is False
    assert result.error == ""


@pytest.mark.asyncio
async def test_baseline_c1_run():
    mock_llm = MagicMock()
    mock_llm.chat.return_value = MagicMock(
        content='{"predictions": ["f_c1_1"]}', tokens_used=150
    )
    b_c1 = BaselineC1(llm=mock_llm)
    case = BenchmarkCase(
        case_id="case_c1",
        dataset_key="nlp_feedback",
        ground_truth_faults=[{"fault_id": "f_c1_1", "fault_family": "referential_error"}],
    )
    result = await b_c1.run(case)

    assert isinstance(result, BaselineResult)
    assert result.tier == "C1"
    assert "f_c1_1" in result.predictions
    assert isinstance(result.evidence_refs, list)
    assert result.cost_tokens == 150
    assert result.latency_ms >= 0
    assert result.abstained is False
    assert result.error == ""


@pytest.mark.asyncio
async def test_baseline_a1_run():
    mock_engine = MagicMock()
    mock_step = MagicMock(step_index=1, action="data_profiler", action_input={"table": "ev_telemetry"}, observation="ok")
    mock_engine.run.return_value = MagicMock(
        status="completed", total_tokens=450, steps=[mock_step]
    )
    b_a1 = BaselineA1(engine=mock_engine)
    case = BenchmarkCase(
        case_id="case_a1",
        dataset_key="ev_telemetry",
        ground_truth_faults=[{"fault_id": "f_a1_1", "fault_family": "cross_system"}],
    )
    result = await b_a1.run(case)

    assert isinstance(result, BaselineResult)
    assert result.tier == "A1"
    assert result.cost_tokens == 450
    assert len(result.tool_trace) == 1
    assert result.tool_trace[0]["action"] == "data_profiler"
    assert result.latency_ms >= 0
    assert result.abstained is False
    assert result.error == ""


@pytest.mark.asyncio
async def test_baseline_a2_run():
    b_a2 = BaselineA2()
    case = BenchmarkCase(case_id="case_a2", dataset_key="charging_sessions")
    result = await b_a2.run(case)

    assert isinstance(result, BaselineResult)
    assert result.tier == "A2"
    assert result.cost_tokens >= 0
    assert any(t.get("step") == "a2_verifier_audit" for t in result.tool_trace)


@pytest.mark.asyncio
async def test_all_baselines_return_identical_result_attributes():
    case = BenchmarkCase(case_id="c_test", dataset_key="test_db")
    baselines = [BaselineR0(), BaselineC1(), BaselineA1(), BaselineA2()]

    expected_attrs = {
        "tier",
        "predictions",
        "evidence_refs",
        "tool_trace",
        "cost_tokens",
        "latency_ms",
        "abstained",
        "error",
    }

    for b in baselines:
        res = await b.run(case)
        assert isinstance(res, BaselineResult)
        for attr in expected_attrs:
            assert hasattr(res, attr), f"BaselineResult from {b.tier} missing attribute {attr}"

