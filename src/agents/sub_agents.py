import time
from typing import Any, Dict, List, Optional, Union

from src.agents.context import ContextBuilder
from src.models.schemas import (
    AnomalyItem,
    AnomalyReport,
    ColumnProfile,
    DataProfile,
    DecisionObject,
    DiagnosisReport,
    QualityRule,
    RuleProposal,
    RunState,
    ValidationResult,
)
from src.orchestrator.state_machine import RunStateMachine
from src.services.audit import audit_store
from src.services.llm import LLMService
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


class BoundedSubAgent:
    """Base class for specialized bounded sub-agents with strict tool whitelisting,
    prompt context formatting, confidence thresholds, and bounded repair loops.
    """

    def __init__(
        self,
        name: str,
        tools_whitelist: List[str],
        llm_service: Optional[LLMService] = None,
        max_repairs: int = 3,
        confidence_threshold: float = 0.6,
        timeout_seconds: float = 30.0,
    ):
        self.name = name
        self.tools_whitelist = tools_whitelist
        self.llm_service = llm_service or LLMService()
        self.max_repairs = max_repairs
        self.confidence_threshold = confidence_threshold
        self.timeout_seconds = timeout_seconds

    def is_action_whitelisted(self, action: str) -> bool:
        return action in self.tools_whitelist


class ProfilerAgent(BoundedSubAgent):
    """ProfilerAgent: Handles dataset source connection and profile aggregation."""

    DEFAULT_WHITELIST = ["profile", "request_context", "abstain"]

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        tools_whitelist: Optional[List[str]] = None,
        max_repairs: int = 3,
        confidence_threshold: float = 0.6,
        timeout_seconds: float = 30.0,
    ):
        super().__init__(
            name="ProfilerAgent",
            tools_whitelist=tools_whitelist or self.DEFAULT_WHITELIST,
            llm_service=llm_service,
            max_repairs=max_repairs,
            confidence_threshold=confidence_threshold,
            timeout_seconds=timeout_seconds,
        )

    def format_context(
        self,
        table_name: str = "dataset",
        sample_aggregates: Optional[Dict[str, Any]] = None,
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
    ) -> str:
        ctx = (
            f"=== PROFILER AGENT CONTEXT ===\n"
            f"Dataset Source Table: '{table_name}'\n"
            f"Whitelisted Tools: {self.tools_whitelist}\n"
        )
        if sample_aggregates:
            ctx += f"Sample Aggregates: {list(sample_aggregates.keys())}\n"
        if target_schema:
            ctx += f"Target Schema Hint: {target_schema}\n"
        return ctx

    def run(
        self,
        dataset_source: str = "dataset",
        sample_aggregates: Optional[Dict[str, Any]] = None,
        run_state_machine: Optional[RunStateMachine] = None,
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
    ) -> DataProfile:
        if run_state_machine and run_state_machine.can_transition_to(RunState.PROFILING):
            run_state_machine.transition_to(RunState.PROFILING, actor=self.name)

        # Deterministic profiling aggregation
        profile = profile_tool(dataset_source, sample_aggregates)

        if run_state_machine and run_state_machine.can_transition_to(RunState.PROFILED):
            run_state_machine.transition_to(RunState.PROFILED, actor=self.name)

        run_id = run_state_machine.run_id if run_state_machine else "default_run"
        audit_store.log_event(
            run_id=run_id,
            event_type="PROFILER_COMPLETE",
            details={
                "table_name": profile.table_name,
                "total_rows": profile.total_rows,
                "columns": list(profile.columns.keys()),
            },
        )

        return profile


class RuleProposerAgent(BoundedSubAgent):
    """RuleProposerAgent: Analyzes profiles and generates quality rules with evidence and confidence scores."""

    DEFAULT_WHITELIST = ["profile", "validate", "compile", "test", "request_context", "submit_review", "abstain"]

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        tools_whitelist: Optional[List[str]] = None,
        max_repairs: int = 3,
        confidence_threshold: float = 0.6,
        timeout_seconds: float = 30.0,
    ):
        super().__init__(
            name="RuleProposerAgent",
            tools_whitelist=tools_whitelist or self.DEFAULT_WHITELIST,
            llm_service=llm_service,
            max_repairs=max_repairs,
            confidence_threshold=confidence_threshold,
            timeout_seconds=timeout_seconds,
        )

    def format_context(
        self,
        data_profile: Union[DataProfile, Dict[str, Any]],
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
        task_description: str = "Generate and validate data quality rules with evidence and confidence scores.",
        feedback_context: str = "",
    ) -> str:
        full_task = task_description
        if feedback_context:
            full_task += f"\n\nPrevious attempt violations to repair:\n{feedback_context}"

        context_str = ContextBuilder.build_context(
            data_profile=data_profile,
            target_schema=target_schema,
            task_description=full_task,
        )
        prompt = (
            f"{context_str}\n\n"
            f"Agent: {self.name}\n"
            f"Make a structured decision with an issue, evidence_refs, confidence score, "
            f"risk level, and next_action from whitelisted tools: {self.tools_whitelist}."
        )
        return prompt

    def run(
        self,
        data_profile: Union[DataProfile, Dict[str, Any]],
        run_state_machine: Optional[RunStateMachine] = None,
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
        task_description: str = "Generate and validate data quality rules.",
    ) -> Dict[str, Any]:
        start_time = time.time()
        feedback_context = ""
        current_profile = data_profile

        if run_state_machine and run_state_machine.can_transition_to(RunState.PROPOSING):
            run_state_machine.transition_to(RunState.PROPOSING, actor=self.name)

        while True:
            # 1. Timeout Check
            if time.time() - start_time > self.timeout_seconds:
                if run_state_machine and run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor=self.name,
                        details={"reason": "Timeout exceeded"},
                    )
                return abstain_tool("Execution timed out in RuleProposerAgent.")

            # 2. Assemble Prompt Context
            prompt = self.format_context(
                data_profile=current_profile,
                target_schema=target_schema,
                task_description=task_description,
                feedback_context=feedback_context,
            )

            # 3. Generate Structured Decision Object
            decision: DecisionObject = self.llm_service.generate_structured(
                prompt=prompt,
                response_model=DecisionObject,
                system_prompt="You are RuleProposerAgent for DataTrust OS. Output structured DecisionObject only.",
            )

            run_id = run_state_machine.run_id if run_state_machine else "default_run"
            audit_store.log_decision(run_id=run_id, decision=decision, actor=self.name)

            # 4. Low Confidence Abstention Check
            if decision.confidence < self.confidence_threshold or decision.next_action == "abstain":
                reason = decision.issue or f"RuleProposerAgent confidence ({decision.confidence}) below threshold ({self.confidence_threshold})."
                if run_state_machine and run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor=self.name,
                        details={"reason": reason, "confidence": decision.confidence},
                    )
                return abstain_tool(reason)

            # 5. Whitelist Tool Check
            if not self.is_action_whitelisted(decision.next_action):
                reason = f"Action '{decision.next_action}' not in RuleProposerAgent whitelisted tools: {self.tools_whitelist}."
                if run_state_machine and run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor=self.name,
                        details={"reason": reason},
                    )
                return abstain_tool(reason)

            # 6. Execute Whitelisted Action
            act = decision.next_action
            act_input = decision.action_input or {}

            if act == "profile":
                t_name = act_input.get("table_name", "dataset")
                current_profile = profile_tool(t_name)
                continue

            elif act == "request_context":
                target_s = act_input.get("target_schema_name", "production")
                target_schema = request_context_tool(target_s)
                continue

            elif act == "compile":
                rules = act_input.get("rules", [])
                compile_tool(rules)
                continue

            elif act == "test":
                rules = act_input.get("rules", [])
                prof_dict = (
                    current_profile.model_dump()
                    if isinstance(current_profile, DataProfile)
                    else current_profile
                )
                test_tool(rules, prof_dict)
                continue

            elif act == "validate":
                rules = act_input.get("rules", [])
                prof_dict = (
                    current_profile.model_dump()
                    if isinstance(current_profile, DataProfile)
                    else current_profile
                )

                if run_state_machine:
                    if run_state_machine.can_transition_to(RunState.PROPOSED):
                        run_state_machine.transition_to(RunState.PROPOSED, actor=self.name)
                    if run_state_machine.can_transition_to(RunState.VALIDATING):
                        run_state_machine.transition_to(RunState.VALIDATING, actor=self.name)

                val_res = validate_tool(rules, prof_dict)

                if val_res.is_valid:
                    prop_id = act_input.get("proposal_id", "prop_001")
                    reasoning = act_input.get("reasoning", decision.issue)
                    sub_res = submit_review_tool(prop_id, rules, reasoning)
                    if run_state_machine and run_state_machine.can_transition_to(RunState.READY_FOR_REVIEW):
                        run_state_machine.transition_to(
                            RunState.READY_FOR_REVIEW,
                            actor=self.name,
                            details=sub_res,
                        )
                    return sub_res
                else:
                    repairs = run_state_machine.increment_repair() if run_state_machine else 1
                    if repairs > self.max_repairs:
                        reason = f"Exceeded maximum repair limit ({self.max_repairs}) in RuleProposerAgent. Abstaining."
                        if run_state_machine and run_state_machine.can_transition_to(RunState.ABSTAINED):
                            run_state_machine.transition_to(
                                RunState.ABSTAINED,
                                actor=self.name,
                                details={"reason": reason, "violations": val_res.violations},
                            )
                        ret_abs = abstain_tool(reason)
                        ret_abs["details"] = {"violations": val_res.violations}
                        return ret_abs

                    if run_state_machine:
                        if run_state_machine.can_transition_to(RunState.NEEDS_REPAIR):
                            run_state_machine.transition_to(
                                RunState.NEEDS_REPAIR,
                                actor=self.name,
                                details={"violations": val_res.violations},
                            )
                        if run_state_machine.can_transition_to(RunState.PROPOSING):
                            run_state_machine.transition_to(RunState.PROPOSING, actor=self.name)

                    feedback_context = f"Violations: {val_res.violations}"
                    continue

            elif act == "submit_review":
                rules = act_input.get("rules", [])
                prop_id = act_input.get("proposal_id", "prop_001")
                reasoning = act_input.get("reasoning", decision.issue)
                sub_res = submit_review_tool(prop_id, rules, reasoning)

                if run_state_machine:
                    if run_state_machine.can_transition_to(RunState.PROPOSED):
                        run_state_machine.transition_to(RunState.PROPOSED, actor=self.name)
                    if run_state_machine.can_transition_to(RunState.VALIDATING):
                        run_state_machine.transition_to(RunState.VALIDATING, actor=self.name)
                    if run_state_machine.can_transition_to(RunState.READY_FOR_REVIEW):
                        run_state_machine.transition_to(
                            RunState.READY_FOR_REVIEW,
                            actor=self.name,
                            details=sub_res,
                        )
                return sub_res

            elif act == "abstain":
                reason = act_input.get("reason", "Agent requested abstention.")
                if run_state_machine and run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor=self.name,
                        details={"reason": reason},
                    )
                return abstain_tool(reason)

            else:
                return abstain_tool(f"Unknown action '{act}' in RuleProposerAgent.")


class AnomalyDetectorAgent(BoundedSubAgent):
    """AnomalyDetectorAgent: Analyzes profile shifts and statistical outliers on scheduled/batch runs."""

    DEFAULT_WHITELIST = ["profile", "validate", "abstain"]

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        tools_whitelist: Optional[List[str]] = None,
        max_repairs: int = 3,
        confidence_threshold: float = 0.6,
        timeout_seconds: float = 30.0,
    ):
        super().__init__(
            name="AnomalyDetectorAgent",
            tools_whitelist=tools_whitelist or self.DEFAULT_WHITELIST,
            llm_service=llm_service,
            max_repairs=max_repairs,
            confidence_threshold=confidence_threshold,
            timeout_seconds=timeout_seconds,
        )

    def format_context(
        self,
        current_profile: Union[DataProfile, Dict[str, Any]],
        baseline_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        task_description: str = "Analyze statistical outliers and profile shifts.",
    ) -> str:
        ctx = (
            f"=== ANOMALY DETECTOR AGENT CONTEXT ===\n"
            f"Task: {task_description}\n"
            f"Whitelisted Tools: {self.tools_whitelist}\n\n"
        )
        curr_dict = (
            current_profile.model_dump()
            if isinstance(current_profile, DataProfile)
            else current_profile
        )
        ctx += (
            f"CURRENT PROFILE:\n"
            f"Table: {curr_dict.get('table_name', 'dataset')}, Total Rows: {curr_dict.get('total_rows', 0)}\n"
        )
        cols = curr_dict.get("columns", {})
        for col_name, c_info in cols.items():
            if isinstance(c_info, dict):
                null_pct = c_info.get("null_percentage") or c_info.get("null_pct") or 0.0
                min_v = c_info.get("min_val") if c_info.get("min_val") is not None else c_info.get("min")
                max_v = c_info.get("max_val") if c_info.get("max_val") is not None else c_info.get("max")
            else:
                null_pct = getattr(c_info, "null_percentage", 0.0)
                min_v = getattr(c_info, "min_val", getattr(c_info, "min", None))
                max_v = getattr(c_info, "max_val", getattr(c_info, "max", None))
            ctx += f"  Column '{col_name}': null_pct={null_pct}%, range=[{min_v}, {max_v}]\n"

        if baseline_profile:
            base_dict = (
                baseline_profile.model_dump()
                if isinstance(baseline_profile, DataProfile)
                else baseline_profile
            )
            ctx += (
                f"\nBASELINE PROFILE:\n"
                f"Table: {base_dict.get('table_name', 'dataset')}, Total Rows: {base_dict.get('total_rows', 0)}\n"
            )
            base_cols = base_dict.get("columns", {})
            for col_name, c_info in base_cols.items():
                if isinstance(c_info, dict):
                    null_pct = c_info.get("null_percentage") or c_info.get("null_pct") or 0.0
                else:
                    null_pct = getattr(c_info, "null_percentage", 0.0)
                ctx += f"  Baseline Column '{col_name}': null_pct={null_pct}%\n"

        return ctx

    def run(
        self,
        current_profile: Union[DataProfile, Dict[str, Any]],
        baseline_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        run_state_machine: Optional[RunStateMachine] = None,
        task_description: str = "Detect profile shifts and statistical outliers.",
    ) -> AnomalyReport:
        prompt = self.format_context(current_profile, baseline_profile, task_description)

        report: AnomalyReport = self.llm_service.generate_structured(
            prompt=prompt,
            response_model=AnomalyReport,
            system_prompt="You are AnomalyDetectorAgent. Output structured AnomalyReport JSON.",
        )

        repairs = 0
        while report.anomaly_score < 0.0 or any(a.confidence < self.confidence_threshold for a in report.detected_anomalies):
            repairs += 1
            if repairs > self.max_repairs:
                break
            prompt += f"\n\nRetry Attempt {repairs}: Ensure anomaly confidence >= {self.confidence_threshold}."
            report = self.llm_service.generate_structured(
                prompt=prompt,
                response_model=AnomalyReport,
                system_prompt="Output structured AnomalyReport JSON with high confidence scores.",
            )

        run_id = run_state_machine.run_id if run_state_machine else "default_run"
        audit_store.log_event(
            run_id=run_id,
            event_type="ANOMALY_DETECTION_COMPLETE",
            details=report.model_dump(),
        )

        return report


class DiagnosisAgent(BoundedSubAgent):
    """DiagnosisAgent: Generates structured root-cause diagnosis JSON objects when anomalies or rule failures occur."""

    DEFAULT_WHITELIST = ["request_context", "abstain"]

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        tools_whitelist: Optional[List[str]] = None,
        max_repairs: int = 3,
        confidence_threshold: float = 0.6,
        timeout_seconds: float = 30.0,
    ):
        super().__init__(
            name="DiagnosisAgent",
            tools_whitelist=tools_whitelist or self.DEFAULT_WHITELIST,
            llm_service=llm_service,
            max_repairs=max_repairs,
            confidence_threshold=confidence_threshold,
            timeout_seconds=timeout_seconds,
        )

    def format_context(
        self,
        violations: Optional[List[Dict[str, Any]]] = None,
        anomalies: Optional[Union[AnomalyReport, List[Dict[str, Any]]]] = None,
        data_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        task_description: str = "Perform root-cause diagnosis for rule failures or anomalies.",
    ) -> str:
        ctx = (
            f"=== DIAGNOSIS AGENT CONTEXT ===\n"
            f"Task: {task_description}\n"
            f"Whitelisted Tools: {self.tools_whitelist}\n\n"
        )
        if violations:
            ctx += f"RULE VIOLATIONS ({len(violations)}):\n"
            for v in violations:
                ctx += f"  - Rule '{v.get('rule_id')}': Column '{v.get('column')}', Reason: {v.get('reason')}\n"

        if anomalies:
            anom_list = (
                anomalies.detected_anomalies
                if isinstance(anomalies, AnomalyReport)
                else anomalies
            )
            ctx += f"\nDETECTED ANOMALIES ({len(anom_list)}):\n"
            for a in anom_list:
                if isinstance(a, AnomalyItem):
                    ctx += f"  - Column '{a.column}': {a.anomaly_type} - {a.description}\n"
                elif isinstance(a, dict):
                    ctx += f"  - Column '{a.get('column')}': {a.get('anomaly_type')} - {a.get('description')}\n"

        if data_profile:
            prof_dict = (
                data_profile.model_dump()
                if isinstance(data_profile, DataProfile)
                else data_profile
            )
            ctx += f"\nDATASET PROFILE SUMMARY:\nTable: {prof_dict.get('table_name', 'dataset')}, Total Rows: {prof_dict.get('total_rows', 0)}\n"

        return ctx

    def run(
        self,
        violations: Optional[List[Dict[str, Any]]] = None,
        anomalies: Optional[Union[AnomalyReport, List[Dict[str, Any]]]] = None,
        data_profile: Optional[Union[DataProfile, Dict[str, Any]]] = None,
        run_state_machine: Optional[RunStateMachine] = None,
        task_description: str = "Generate root-cause diagnosis object.",
    ) -> DiagnosisReport:
        prompt = self.format_context(violations, anomalies, data_profile, task_description)

        diagnosis: DiagnosisReport = self.llm_service.generate_structured(
            prompt=prompt,
            response_model=DiagnosisReport,
            system_prompt="You are DiagnosisAgent. Output structured DiagnosisReport JSON only.",
        )

        repairs = 0
        while diagnosis.confidence < self.confidence_threshold:
            repairs += 1
            if repairs > self.max_repairs:
                break
            prompt += f"\n\nRetry Attempt {repairs}: Diagnosis confidence {diagnosis.confidence} below threshold {self.confidence_threshold}."
            diagnosis = self.llm_service.generate_structured(
                prompt=prompt,
                response_model=DiagnosisReport,
                system_prompt="Output structured DiagnosisReport JSON with high confidence and detailed evidence.",
            )

        run_id = run_state_machine.run_id if run_state_machine else "default_run"
        audit_store.log_event(
            run_id=run_id,
            event_type="DIAGNOSIS_COMPLETE",
            details=diagnosis.model_dump(),
        )

        return diagnosis
