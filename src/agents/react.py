import time
from typing import Any, Dict, List, Optional, Union

from src.agents.context import ContextBuilder
from src.models.schemas import DataProfile, DecisionObject, RunState
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


class BoundedReActEngine:
    """Bounded ReAct engine with structured decision objects, tool whitelisting,
    bounded repair loop policy (max 3 repairs), token budget, and confidence abstention.
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

    def run(
        self,
        run_state_machine: RunStateMachine,
        data_profile: Union[DataProfile, Dict[str, Any]],
        target_schema: Optional[Union[Dict[str, Any], str]] = None,
        task_description: str = "Generate and validate data quality rules.",
    ) -> Dict[str, Any]:
        start_time = time.time()
        estimated_tokens_used = 0

        # State transition: CREATED -> PROFILING -> PROFILED -> PROPOSING
        if run_state_machine.can_transition_to(RunState.PROFILING):
            run_state_machine.transition_to(RunState.PROFILING, actor="BoundedReAct")
        if run_state_machine.can_transition_to(RunState.PROFILED):
            run_state_machine.transition_to(RunState.PROFILED, actor="BoundedReAct")
        if run_state_machine.can_transition_to(RunState.PROPOSING):
            run_state_machine.transition_to(RunState.PROPOSING, actor="BoundedReAct")

        current_profile = data_profile
        feedback_context = ""

        while True:
            # 1. Timeout Check
            if time.time() - start_time > self.timeout_seconds:
                if run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor="BoundedReAct",
                        details={"reason": "Timeout exceeded"},
                    )
                return abstain_tool("Execution timed out.")

            # 2. Token Budget Check
            if estimated_tokens_used > self.token_budget:
                if run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor="BoundedReAct",
                        details={"reason": "Token budget exceeded"},
                    )
                return abstain_tool("Token budget exceeded.")

            # 3. Assemble Prompt Context
            full_task = task_description
            if feedback_context:
                full_task += f"\n\nPrevious attempt violations:\n{feedback_context}"

            context_str = ContextBuilder.build_context(
                data_profile=current_profile,
                target_schema=target_schema,
                task_description=full_task,
            )

            prompt = (
                f"{context_str}\n\n"
                f"Make a structured decision with an issue, evidence_refs, confidence score, "
                f"risk level, and next_action from whitelisted tools: {self.tools_whitelist}."
            )

            # 4. Generate Structured Decision Object
            decision: DecisionObject = self.llm_service.generate_structured(
                prompt=prompt,
                response_model=DecisionObject,
                system_prompt="You are DataTrust OS ReAct engine. Output structured DecisionObject only.",
            )
            estimated_tokens_used += len(prompt) // 4 + 200

            audit_store.log_decision(
                run_id=run_state_machine.run_id,
                decision=decision,
                actor="BoundedReAct",
            )

            # 5. Low Confidence Abstention Check
            if decision.confidence < self.confidence_threshold or decision.next_action == "abstain":
                reason = decision.issue or "Confidence score below threshold."
                if run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor="BoundedReAct",
                        details={"reason": reason, "confidence": decision.confidence},
                    )
                return abstain_tool(reason)

            # 6. Tool Whitelist Check
            if decision.next_action not in self.tools_whitelist:
                reason = f"Action '{decision.next_action}' not in whitelisted tools."
                if run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor="BoundedReAct",
                        details={"reason": reason},
                    )
                return abstain_tool(reason)

            # 7. Execute Action
            act = decision.next_action
            act_input = decision.action_input or {}

            if act == "profile":
                t_name = act_input.get("table_name", "dataset")
                current_profile = profile_tool(t_name)
                continue

            elif act == "request_context":
                target_s = act_input.get("target_schema_name", "production")
                ctx = request_context_tool(target_s)
                target_schema = ctx
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
                if run_state_machine.can_transition_to(RunState.PROPOSED):
                    run_state_machine.transition_to(RunState.PROPOSED, actor="BoundedReAct")
                if run_state_machine.can_transition_to(RunState.VALIDATING):
                    run_state_machine.transition_to(RunState.VALIDATING, actor="BoundedReAct")

                val_res = validate_tool(rules, prof_dict)

                if val_res.is_valid:
                    # Valid rules! Transition to READY_FOR_REVIEW
                    prop_id = act_input.get("proposal_id", "prop_001")
                    reasoning = act_input.get("reasoning", "Validated rules passed check.")
                    sub_res = submit_review_tool(prop_id, rules, reasoning)
                    if run_state_machine.can_transition_to(RunState.READY_FOR_REVIEW):
                        run_state_machine.transition_to(
                            RunState.READY_FOR_REVIEW,
                            actor="BoundedReAct",
                            details=sub_res,
                        )
                    return sub_res
                else:
                    # Validation Failed -> Increment Repair
                    repairs = run_state_machine.increment_repair()
                    if repairs > self.max_repairs:
                        reason = f"Exceeded maximum repair limit ({self.max_repairs}). Abstaining."
                        if run_state_machine.can_transition_to(RunState.ABSTAINED):
                            run_state_machine.transition_to(
                                RunState.ABSTAINED,
                                actor="BoundedReAct",
                                details={"reason": reason, "violations": val_res.violations},
                            )
                        return abstain_tool(reason)

                    # Transition to NEEDS_REPAIR -> PROPOSING
                    if run_state_machine.can_transition_to(RunState.NEEDS_REPAIR):
                        run_state_machine.transition_to(
                            RunState.NEEDS_REPAIR,
                            actor="BoundedReAct",
                            details={"violations": val_res.violations},
                        )
                    if run_state_machine.can_transition_to(RunState.PROPOSING):
                        run_state_machine.transition_to(RunState.PROPOSING, actor="BoundedReAct")

                    feedback_context = f"Violations: {val_res.violations}"
                    continue

            elif act == "submit_review":
                rules = act_input.get("rules", [])
                prop_id = act_input.get("proposal_id", "prop_001")
                reasoning = act_input.get("reasoning", "Rule proposal ready for review.")
                sub_res = submit_review_tool(prop_id, rules, reasoning)

                # Ensure proposed state before ready for review if needed
                if run_state_machine.can_transition_to(RunState.PROPOSED):
                    run_state_machine.transition_to(RunState.PROPOSED, actor="BoundedReAct")
                if run_state_machine.can_transition_to(RunState.VALIDATING):
                    run_state_machine.transition_to(RunState.VALIDATING, actor="BoundedReAct")

                if run_state_machine.can_transition_to(RunState.READY_FOR_REVIEW):
                    run_state_machine.transition_to(
                        RunState.READY_FOR_REVIEW,
                        actor="BoundedReAct",
                        details=sub_res,
                    )
                return sub_res

            elif act == "abstain":
                reason = act_input.get("reason", "Agent requested abstention.")
                if run_state_machine.can_transition_to(RunState.ABSTAINED):
                    run_state_machine.transition_to(
                        RunState.ABSTAINED,
                        actor="BoundedReAct",
                        details={"reason": reason},
                    )
                return abstain_tool(reason)

            else:
                return abstain_tool(f"Unknown action {act}")
