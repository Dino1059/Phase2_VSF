from src.orchestrator.react_engine import ReActEngine, ReActResult
from src.services.llm import GemmaLLMAdapter
from src.tools.base import ToolRegistry
from src.tools.rule_executor import RuleExecutorTool


class ExecutorAgent:
    """Sub-agent that executes approved quality rules."""
    name = "executor"
    description = "Executes approved data quality rules and quarantines violations."

    def __init__(self, llm: GemmaLLMAdapter):
        self.tools = ToolRegistry()
        self.tools.register(RuleExecutorTool())
        self.engine = ReActEngine(llm, self.tools, max_steps=5)

    def run(self, rule_id: str, dry_run: bool = True) -> ReActResult:
        return self.engine.run(
            task=f"Execute quality rule '{rule_id}' in {'dry_run' if dry_run else 'live'} mode. Report violations found.",
            context={"rule_id": rule_id, "dry_run": dry_run}
        )
