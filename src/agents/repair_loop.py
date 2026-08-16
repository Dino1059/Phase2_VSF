from typing import List, Tuple
from src.agents.llm_adapter import LLMAdapter, LLMResponse
from src.tools.compiler import Compiler, ExecutableTransformPlan
from src.tools.validator import RuleSpec


class RepairLoopResult:
    def __init__(self, plan: ExecutableTransformPlan, rules: List[RuleSpec], retries: int, abstained: bool):
        self.plan = plan
        self.rules = rules
        self.retries = retries
        self.abstained = abstained


class RepairLoop:
    def __init__(self, llm_adapter: LLMAdapter, compiler: Compiler, max_retries: int = 3):
        self.llm_adapter = llm_adapter
        self.compiler = compiler
        self.max_retries = max_retries

    def repair_and_compile(self, context_str: str, initial_rules: List[RuleSpec]) -> RepairLoopResult:
        rules = initial_rules
        retries = 0

        while retries <= self.max_retries:
            plan = self.compiler.compile(rules)
            if plan.compiled_successfully:
                return RepairLoopResult(plan=plan, rules=rules, retries=retries, abstained=False)

            # Attempt repair via LLM
            retries += 1
            if retries <= self.max_retries:
                error_msg = "; ".join(plan.compilation_errors)
                llm_res = self.llm_adapter.propose_rules(context_str, retry_error=error_msg)
                rules = llm_res.rules

        # If max retries exceeded, abstain from invalid rules and compile valid ones
        valid_rules = [r for r in rules if r.action in self.compiler.ALLOWED_ACTIONS]
        final_plan = self.compiler.compile(valid_rules)
        return RepairLoopResult(plan=final_plan, rules=valid_rules, retries=retries, abstained=True)
