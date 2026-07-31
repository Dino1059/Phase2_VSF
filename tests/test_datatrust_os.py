import pytest

from src.agents.baselines import run_a1_baseline, run_c0_baseline, run_c1_baseline
from src.agents.context import ContextBuilder
from src.agents.react import BoundedReActEngine
from src.models.schemas import (
    AuditRecord,
    ColumnProfile,
    DataProfile,
    DecisionObject,
    QualityRule,
    RuleProposal,
    RunState,
    ValidationResult,
)
from src.orchestrator.state_machine import InvalidStateTransitionError, RunStateMachine
from src.services.audit import AuditStore
from src.services.llm import LLMService, OfflineMockLLM
from src.tools.datatrust_tools import (
    TOOL_WHITELIST,
    abstain_tool,
    compile_tool,
    profile_tool,
    request_context_tool,
    submit_review_tool,
    test_tool,
    validate_tool,
)


class TestLLMService:
    def test_offline_mock_llm_decision_object(self):
        llm = OfflineMockLLM()
        dec = llm.generate_structured("Generate initial proposal", DecisionObject)
        assert isinstance(dec, DecisionObject)
        assert dec.next_action in TOOL_WHITELIST
        assert 0.0 <= dec.confidence <= 1.0

    def test_offline_mock_llm_rule_proposal(self):
        llm = OfflineMockLLM()
        prop = llm.generate_structured("Propose rules", RuleProposal)
        assert isinstance(prop, RuleProposal)
        assert len(prop.rules) > 0
        assert isinstance(prop.rules[0], QualityRule)

    def test_llm_service_provider_fallback(self):
        service = LLMService(provider="offline_mock")
        dec = service.generate_structured("Test prompt", DecisionObject)
        assert isinstance(dec, DecisionObject)


class TestContextBuilder:
    def test_sanitize_profile_removes_raw_rows(self):
        raw_profile = {
            "table_name": "users",
            "total_rows": 100,
            "raw_rows": [{"id": 1, "secret": "abc"}],
            "sample_rows": [{"id": 1}],
            "columns": {
                "id": {"column_name": "id", "data_type": "INTEGER", "total_count": 100, "null_count": 0, "distinct_count": 100, "records": [1, 2]},
            },
        }
        sanitized = ContextBuilder.sanitize_profile(raw_profile)
        assert "raw_rows" not in sanitized
        assert "sample_rows" not in sanitized
        assert "records" not in sanitized["columns"]["id"]

    def test_build_context_contains_aggregates_and_notice(self):
        profile = profile_tool("orders")
        ctx = ContextBuilder.build_context(profile, target_schema={"req": "order_id"}, task_description="Test task")
        assert "DATASET PROFILE METADATA & AGGREGATES" in ctx
        assert "SECURITY NOTICE" in ctx
        assert "orders" in ctx
        assert "Column: 'email'" in ctx


class TestAuditStore:
    def test_audit_store_logging_and_querying(self):
        audit = AuditStore()
        run_id = "test_run_123"

        r1 = audit.log_transition(run_id, "CREATED", "PROFILING", actor="test")
        r2 = audit.log_decision(run_id, DecisionObject(issue="test", evidence_refs=[], confidence=0.9, next_action="profile"))
        r3 = audit.log_event(run_id, "CUSTOM_EVENT", {"info": "data"})

        history = audit.get_run_history(run_id)
        assert len(history) == 3
        assert history[0].state_from == "CREATED"
        assert history[0].state_to == "PROFILING"
        assert history[1].event_type == "AGENT_DECISION"
        assert history[2].event_type == "CUSTOM_EVENT"


class TestStateMachine:
    def test_state_machine_valid_transitions(self):
        sm = RunStateMachine(run_id="sm_run_01")
        assert sm.current_state == RunState.CREATED

        sm.transition_to(RunState.PROFILING)
        assert sm.current_state == RunState.PROFILING

        sm.transition_to(RunState.PROFILED)
        assert sm.current_state == RunState.PROFILED

        sm.transition_to(RunState.PROPOSING)
        assert sm.current_state == RunState.PROPOSING

        sm.transition_to(RunState.PROPOSED)
        assert sm.current_state == RunState.PROPOSED

        sm.transition_to(RunState.VALIDATING)
        assert sm.current_state == RunState.VALIDATING

        sm.transition_to(RunState.READY_FOR_REVIEW)
        assert sm.current_state == RunState.READY_FOR_REVIEW

        sm.transition_to(RunState.APPROVED)
        assert sm.current_state == RunState.APPROVED

        sm.transition_to(RunState.EXECUTING)
        assert sm.current_state == RunState.EXECUTING

        sm.transition_to(RunState.COMPLETED)
        assert sm.current_state == RunState.COMPLETED
        assert sm.is_terminal()

    def test_state_machine_invalid_transition_raises_error(self):
        sm = RunStateMachine(run_id="sm_run_02")
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(RunState.EXECUTING)  # Cannot jump CREATED -> EXECUTING

    def test_state_machine_repair_counter(self):
        sm = RunStateMachine()
        assert sm.repair_count == 0
        sm.increment_repair()
        assert sm.repair_count == 1


class TestTools:
    def test_profile_tool(self):
        prof = profile_tool("customers")
        assert isinstance(prof, DataProfile)
        assert prof.table_name == "customers"
        assert "id" in prof.columns

    def test_validate_tool_success_and_failure(self):
        prof = profile_tool("users").model_dump()

        valid_rules = [
            {"rule_id": "r1", "column": "id", "rule_type": "not_null"},
            {"rule_id": "r2", "column": "age", "rule_type": "range", "params": {"min": 10, "max": 100}},
        ]
        res1 = validate_tool(valid_rules, prof)
        assert res1.is_valid is True

        invalid_rules = [
            {"rule_id": "r3", "column": "non_existent_col", "rule_type": "not_null"},
        ]
        res2 = validate_tool(invalid_rules, prof)
        assert res2.is_valid is False
        assert len(res2.violations) == 1

    def test_compile_tool(self):
        rules = [{"rule_id": "r1", "column": "age", "rule_type": "range", "params": {"min": 18, "max": 65}}]
        compiled = compile_tool(rules)
        assert compiled["status"] == "success"
        assert 'BETWEEN 18 AND 65' in compiled["compiled_rules"][0]["sql_expression"]

    def test_test_tool(self):
        prof = profile_tool("users").model_dump()
        rules = [{"rule_id": "r1", "column": "id", "rule_type": "not_null"}]
        res = test_tool(rules, prof)
        assert res["status"] == "tested"
        assert res["passed_count"] == 1

    def test_request_context_tool(self):
        ctx = request_context_tool("production")
        assert "target_schema" in ctx

    def test_submit_review_tool(self):
        sub = submit_review_tool("p1", [{"rule_id": "r1", "column": "id", "rule_type": "not_null"}], "Reasoning")
        assert sub["status"] == "READY_FOR_REVIEW"
        assert sub["proposal_id"] == "p1"

    def test_abstain_tool(self):
        abs_res = abstain_tool("Low confidence score")
        assert abs_res["status"] == "ABSTAINED"


class TestBoundedReActAndBaselines:
    def test_c0_baseline(self):
        prof = profile_tool("users")
        proposal = run_c0_baseline(prof)
        assert isinstance(proposal, RuleProposal)
        assert len(proposal.rules) > 0

    def test_c1_baseline(self):
        res = run_c1_baseline("users")
        assert res["status"] in ["READY_FOR_REVIEW", "FAILED_VALIDATION"]
        assert "run_id" in res

    def test_a1_baseline_bounded_react(self):
        res = run_a1_baseline("users", max_repairs=3, confidence_threshold=0.6)
        assert "run_id" in res
        assert res["final_state"] in [RunState.READY_FOR_REVIEW.value, RunState.ABSTAINED.value]

    def test_react_engine_abstention_on_low_confidence(self):
        sm = RunStateMachine()
        prof = profile_tool("users")

        class LowConfidenceMockLLM(OfflineMockLLM):
            def generate_structured(self, prompt, response_model, system_prompt=None):
                return DecisionObject(
                    issue="Extremely low confidence on schema",
                    evidence_refs=[],
                    confidence=0.2,
                    risk="high",
                    next_action="abstain",
                    action_input={"reason": "Low confidence test"},
                )

        engine = BoundedReActEngine(llm_service=LLMService(provider="offline_mock"), confidence_threshold=0.6)
        engine.llm_service.mock_llm = LowConfidenceMockLLM()

        res = engine.run(sm, prof)
        assert res["status"] == "ABSTAINED"
        assert sm.current_state == RunState.ABSTAINED

    def test_react_engine_max_repairs_abstention(self):
        sm = RunStateMachine(max_repairs=2)
        prof = profile_tool("users")

        class ValidationFailingMockLLM(OfflineMockLLM):
            def generate_structured(self, prompt, response_model, system_prompt=None):
                return DecisionObject(
                    issue="Proposing invalid rule repeatedly",
                    evidence_refs=[],
                    confidence=0.9,
                    risk="low",
                    next_action="validate",
                    action_input={
                        "rules": [{"rule_id": "bad_rule", "column": "non_existent_column", "rule_type": "not_null"}]
                    },
                )

        engine = BoundedReActEngine(llm_service=LLMService(provider="offline_mock"), max_repairs=2)
        engine.llm_service.mock_llm = ValidationFailingMockLLM()

        res = engine.run(sm, prof)
        assert res["status"] == "ABSTAINED"
        assert sm.repair_count > 2
        assert sm.current_state == RunState.ABSTAINED
