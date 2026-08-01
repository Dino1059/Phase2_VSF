import time
from typing import Any, Dict, List, Optional, Union

from src.agents.sub_agents import (
    AnomalyDetectorAgent,
    DiagnosisAgent,
    ProfilerAgent,
    RuleProposerAgent,
)
from src.models.schemas import AnomalyReport, DataProfile, DecisionObject, DiagnosisReport, RunState
from src.orchestrator.state_machine import RunStateMachine
from src.services.audit import audit_store
from src.services.llm import LLMService
from src.tools.datatrust_tools import abstain_tool


class BoundedReActEngine:
    """Bounded ReAct engine orchestrating specialized sub-agents:
    ProfilerAgent, RuleProposerAgent, AnomalyDetectorAgent, and DiagnosisAgent.
    """

    DEFAULT_WHITELIST = [
        "profile",
        "validate",
        "compile",
        "test",
        "request_context",
        "submit_review",
        "abstain",
    ]

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        tools_whitelist: Optional[List[str]] = None,
        max_repairs: int = 3,
        confidence_threshold: float = 0.6,
        token_budget: int = 10000,
        timeout_seconds: float = 30.0,
    ):
        self.llm_service = llm_service or LLMService()
        self.tools_whitelist = tools_whitelist or self.DEFAULT_WHITELIST
        self.max_repairs = max_repairs
        self.confidence_threshold = confidence_threshold
        self.token_budget = token_budget
        self.timeout_seconds = timeout_seconds

        # Instantiate specialized sub-agents under the top-level orchestrator
        self.profiler_agent = ProfilerAgent(
            llm_service=self.llm_service,
            max_repairs=self.max_repairs,
            confidence_threshold=self.confidence_threshold,
            timeout_seconds=self.timeout_seconds,
        )
        self.rule_proposer_agent = RuleProposerAgent(
            llm_service=self.llm_service,
            tools_whitelist=self.tools_whitelist,
            max_repairs=self.max_repairs,
            confidence_threshold=self.confidence_threshold,
            timeout_seconds=self.timeout_seconds,
        )
        self.anomaly_detector_agent = AnomalyDetectorAgent(
            llm_service=self.llm_service,
            max_repairs=self.max_repairs,
            confidence_threshold=self.confidence_threshold,
            timeout_seconds=self.timeout_seconds,
        )
        self.diagnosis_agent = DiagnosisAgent(
            llm_service=self.llm_service,
            max_repairs=self.max_repairs,
            confidence_threshold=self.confidence_threshold,
            timeout_seconds=self.timeout_seconds,
        )

    def _sync_sub_agents(self) -> None:
        """Sync configuration and LLM service instance to all sub-agents."""
        for agent in [
            self.profiler_agent,
            self.rule_proposer_agent,
            self.anomaly_detector_agent,
            self.diagnosis_agent,
        ]:
            agent.llm_service = self.llm_service
            agent.max_repairs = self.max_repairs
            agent.confidence_threshold = self.confidence_threshold
            agent.timeout_seconds = self.timeout_seconds

    def profile(
        self,
        dataset_source: str = "dataset",
        sample_aggregates: Optional[Dict[str, Any]] = None,
        run_state_machine: Optional[RunStateMachine] = None,
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
    ) -> DataProfile:
        self._sync_sub_agents()
        return self.profiler_agent.run(
            dataset_source=dataset_source,
            sample_aggregates=sample_aggregates,
            run_state_machine=run_state_machine,
            target_schema=target_schema,
        )

    def propose_rules(
        self,
        data_profile: Union[DataProfile, Dict[str, Any]],
        run_state_machine: Optional[RunStateMachine] = None,
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
        task_description: str = "Generate and validate data quality rules.",
    ) -> Dict[str, Any]:
        self._sync_sub_agents()
        return self.rule_proposer_agent.run(
            data_profile=data_profile,
            run_state_machine=run_state_machine,
            target_schema=target_schema,
            task_description=task_description,
        )

    def detect_anomalies(
        self,
        current_profile: Union[DataProfile, Dict[str, Any]],
        baseline_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        run_state_machine: Optional[RunStateMachine] = None,
        task_description: str = "Detect profile shifts and statistical outliers.",
    ) -> AnomalyReport:
        self._sync_sub_agents()
        return self.anomaly_detector_agent.run(
            current_profile=current_profile,
            baseline_profile=baseline_profile,
            run_state_machine=run_state_machine,
            task_description=task_description,
        )

    def diagnose(
        self,
        violations: Optional[List[Dict[str, Any]]] = None,
        anomalies: Optional[Union[AnomalyReport, List[Dict[str, Any]]]] = None,
        data_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        run_state_machine: Optional[RunStateMachine] = None,
        task_description: str = "Generate root-cause diagnosis object.",
    ) -> DiagnosisReport:
        self._sync_sub_agents()
        return self.diagnosis_agent.run(
            violations=violations,
            anomalies=anomalies,
            data_profile=data_profile,
            run_state_machine=run_state_machine,
            task_description=task_description,
        )

    def run(
        self,
        run_state_machine: RunStateMachine,
        data_profile: Union[DataProfile, Dict[str, Any]],
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
        task_description: str = "Generate and validate data quality rules.",
    ) -> Dict[str, Any]:
        """Routes orchestration workflow requests through specialized sub-agents."""
        self._sync_sub_agents()

        # Step 1: Handle state transitions CREATED -> PROFILING -> PROFILED
        if run_state_machine.can_transition_to(RunState.PROFILING):
            run_state_machine.transition_to(RunState.PROFILING, actor="BoundedReAct")

        if isinstance(data_profile, str):
            data_profile = self.profiler_agent.run(
                dataset_source=data_profile,
                run_state_machine=run_state_machine,
                target_schema=target_schema,
            )
        else:
            if run_state_machine.can_transition_to(RunState.PROFILED):
                run_state_machine.transition_to(RunState.PROFILED, actor="BoundedReAct")

        # Step 2: Route rule proposal & validation through RuleProposerAgent
        proposal_result = self.rule_proposer_agent.run(
            data_profile=data_profile,
            run_state_machine=run_state_machine,
            target_schema=target_schema,
            task_description=task_description,
        )

        # Step 3: If proposal failed/abstained due to rule violations, route to DiagnosisAgent for root-cause analysis
        if (
            proposal_result.get("status") == "ABSTAINED"
            and isinstance(proposal_result.get("details"), dict)
            and "violations" in proposal_result["details"]
        ):
            violations = proposal_result["details"]["violations"]
            diagnosis = self.diagnosis_agent.run(
                violations=violations,
                data_profile=data_profile,
                run_state_machine=run_state_machine,
            )
            proposal_result["diagnosis"] = diagnosis.model_dump()

        return proposal_result

