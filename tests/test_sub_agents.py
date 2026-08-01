import pytest

from src.agents.react import BoundedReActEngine
from src.agents.sub_agents import (
    AnomalyDetectorAgent,
    DiagnosisAgent,
    ProfilerAgent,
    RuleProposerAgent,
)
from src.models.schemas import (
    AnomalyItem,
    AnomalyReport,
    DataProfile,
    DecisionObject,
    DiagnosisReport,
    RunState,
)
from src.orchestrator.state_machine import RunStateMachine
from src.services.llm import LLMService, OfflineMockLLM
from src.tools.datatrust_tools import profile_tool


def test_profiler_agent_execution():
    agent = ProfilerAgent()
    sm = RunStateMachine()
    ctx = agent.format_context(table_name="orders", target_schema={"req": "id"})

    assert "=== PROFILER AGENT CONTEXT ===" in ctx
    assert "orders" in ctx

    profile = agent.run(dataset_source="orders", run_state_machine=sm)
    assert isinstance(profile, DataProfile)
    assert profile.table_name == "orders"
    assert sm.current_state == RunState.PROFILED


def test_rule_proposer_agent_success():
    agent = RuleProposerAgent()
    sm = RunStateMachine()
    prof = profile_tool("users")

    sm.transition_to(RunState.PROFILING)
    sm.transition_to(RunState.PROFILED)

    result = agent.run(data_profile=prof, run_state_machine=sm)
    assert result["status"] == "READY_FOR_REVIEW"
    assert sm.current_state == RunState.READY_FOR_REVIEW


def test_rule_proposer_agent_low_confidence_abstention():
    class LowConfLLM(OfflineMockLLM):
        def generate_structured(self, prompt, response_model, system_prompt=None):
            return DecisionObject(
                issue="Uncertain about data types",
                evidence_refs=[],
                confidence=0.3,
                risk="high",
                next_action="abstain",
                action_input={"reason": "Low confidence test"},
            )

    llm = LLMService(provider="offline_mock")
    llm.mock_llm = LowConfLLM()
    agent = RuleProposerAgent(llm_service=llm, confidence_threshold=0.6)
    sm = RunStateMachine()
    prof = profile_tool("users")

    sm.transition_to(RunState.PROFILING)
    sm.transition_to(RunState.PROFILED)

    result = agent.run(data_profile=prof, run_state_machine=sm)
    assert result["status"] == "ABSTAINED"
    assert sm.current_state == RunState.ABSTAINED


def test_rule_proposer_agent_max_repairs():
    class FailingValidationLLM(OfflineMockLLM):
        def generate_structured(self, prompt, response_model, system_prompt=None):
            return DecisionObject(
                issue="Repeatedly invalid rule",
                evidence_refs=[],
                confidence=0.9,
                risk="low",
                next_action="validate",
                action_input={
                    "rules": [{"rule_id": "r_bad", "column": "missing_col", "rule_type": "not_null"}]
                },
            )

    llm = LLMService(provider="offline_mock")
    llm.mock_llm = FailingValidationLLM()
    agent = RuleProposerAgent(llm_service=llm, max_repairs=2)
    sm = RunStateMachine(max_repairs=2)
    prof = profile_tool("users")

    sm.transition_to(RunState.PROFILING)
    sm.transition_to(RunState.PROFILED)

    result = agent.run(data_profile=prof, run_state_machine=sm)
    assert result["status"] == "ABSTAINED"
    assert sm.current_state == RunState.ABSTAINED
    assert sm.repair_count > 2


def test_anomaly_detector_agent():
    agent = AnomalyDetectorAgent()
    curr_prof = profile_tool("users")
    base_prof = profile_tool("users_baseline")

    report = agent.run(current_profile=curr_prof, baseline_profile=base_prof)
    assert isinstance(report, AnomalyReport)
    assert len(report.detected_anomalies) > 0
    assert isinstance(report.detected_anomalies[0], AnomalyItem)


def test_diagnosis_agent():
    agent = DiagnosisAgent()
    violations = [{"rule_id": "r1", "column": "age", "reason": "Range bound error"}]
    prof = profile_tool("users")

    diag = agent.run(violations=violations, data_profile=prof)
    assert isinstance(diag, DiagnosisReport)
    assert diag.root_cause != ""
    assert len(diag.affected_columns) > 0


def test_bounded_react_engine_orchestration_routing():
    engine = BoundedReActEngine()
    sm = RunStateMachine()
    prof = profile_tool("users")

    res = engine.run(run_state_machine=sm, data_profile=prof)
    assert res["status"] in ["READY_FOR_REVIEW", "ABSTAINED"]
    assert sm.current_state in [RunState.READY_FOR_REVIEW, RunState.ABSTAINED]


def test_bounded_react_engine_direct_sub_agent_methods():
    engine = BoundedReActEngine()
    sm = RunStateMachine()

    prof = engine.profile(dataset_source="taxi_trips", run_state_machine=sm)
    assert isinstance(prof, DataProfile)
    assert prof.table_name == "taxi_trips"

    anom = engine.detect_anomalies(current_profile=prof)
    assert isinstance(anom, AnomalyReport)

    diag = engine.diagnose(violations=[{"rule_id": "r1", "column": "fare", "reason": "negative fare"}])
    assert isinstance(diag, DiagnosisReport)
