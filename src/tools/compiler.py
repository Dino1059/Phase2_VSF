from typing import Any, Dict, List, Optional
import uuid

from src.models.schemas import (
    ExecutionPlan,
    ExecutionStep,
    Proposal,
    RuleAction,
    RuleFamily,
    RuleSpec,
    TransformSpec,
)

# Aliases for legacy code compatibility
ExecutableInstruction = ExecutionStep
ExecutableTransformPlan = ExecutionPlan


class Compiler:
    """
    Compiler compiles approved RuleSpecs and TransformSpecs from a Proposal
    into a deterministic, ordered ExecutionPlan.
    """

    FAMILY_ORDER = {
        "impute_default": 1,
        "format": 2,
        "not_null": 3,
        "unique": 4,
        "range": 5,
        "cross_field": 6,
        "semantic": 7,
    }

    def compile_rule(self, rule: RuleSpec, order: int = 1) -> ExecutionStep:
        family_str = rule.family.value if isinstance(rule.family, RuleFamily) else str(rule.family)
        action_str = rule.action.value if isinstance(rule.action, RuleAction) else str(rule.action)

        params: Dict[str, Any] = {
            "target_field": rule.target_field,
            "action": action_str,
            "rule_id": rule.rule_id,
            **rule.parameters,
        }

        op_name = family_str
        if family_str == "range":
            op_name = "range_check"

        return ExecutionStep(
            step_id=str(uuid.uuid4()),
            operation=op_name,
            params=params,
            order=order,
        )

    def compile_transform(self, transform: TransformSpec, order: int = 1) -> ExecutionStep:
        return ExecutionStep(
            step_id=str(uuid.uuid4()),
            operation=transform.operation,
            params={
                "source_field": transform.source_field,
                "target_field": transform.target_field,
                **transform.params,
            },
            order=order,
        )

    def compile_plan(self, proposal: Any, run_id: Optional[str] = None) -> ExecutionPlan:
        steps: List[ExecutionStep] = []
        rule_items = []

        rules = []
        transforms = []
        target_run_id = run_id or str(uuid.uuid4())

        if isinstance(proposal, Proposal):
            rules = proposal.rules
            transforms = proposal.transforms
            target_run_id = run_id or proposal.run_id or str(uuid.uuid4())
        elif isinstance(proposal, list):
            rules = proposal
        else:
            if hasattr(proposal, "rules"):
                rules = proposal.rules
            if hasattr(proposal, "transforms"):
                transforms = proposal.transforms

        for r in rules:
            fam = r.family.value if hasattr(r.family, "value") else str(getattr(r, "family", "general"))
            priority = self.FAMILY_ORDER.get(fam, 10)
            rule_items.append((priority, r))

        # Sort rules by deterministic priority
        rule_items.sort(key=lambda x: x[0])

        order_counter = 1
        # First transforms
        for t in transforms:
            steps.append(self.compile_transform(t, order=order_counter))
            order_counter += 1

        # Then rules
        for _, r in rule_items:
            steps.append(self.compile_rule(r, order=order_counter))
            order_counter += 1

        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            run_id=target_run_id,
            steps=steps,
            estimated_rows=0,
        )

    compile = compile_plan

