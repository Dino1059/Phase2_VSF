from src.orchestrator.react_engine import ReActEngine, ReActResult
from src.services.llm import GemmaLLMAdapter
from src.tools.base import ToolRegistry
from src.tools.rule_proposer import RuleProposerTool


class RuleProposerAgent:
    """Sub-agent that proposes data quality rules based on analysis findings."""
    name = "rule_proposer"
    description = "Proposes data quality rules based on profiling and anomaly analysis."

    def __init__(self, llm: GemmaLLMAdapter):
        self.tools = ToolRegistry()
        self.tools.register(RuleProposerTool())
        self.engine = ReActEngine(llm, self.tools, max_steps=5)

    def run(self, table_name: str, profile_summary: str = "", anomaly_findings: dict | None = None) -> ReActResult:
        return self.engine.run(
            task=f"Propose quality rules for '{table_name}' based on the profile and anomaly data.",
            context={"target_table": table_name, "profile_summary": profile_summary, "anomaly_findings": anomaly_findings or {}}
        )
