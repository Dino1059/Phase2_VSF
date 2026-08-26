from typing import Any
from src.services.llm import GemmaLLMAdapter
from src.tools.rule_proposer import RuleProposerTool


class RuleProposerAgent:
    """Agent wrapper for 1-Prompt Data Quality Rule Proposal & Remediation SQL Generation."""
    name = "rule_proposer"
    description = "Proposes data quality rules with validation constraints and remediation SQL based on policy, profiling, and anomaly findings."

    def __init__(self, llm: GemmaLLMAdapter | None = None):
        self.tool = RuleProposerTool()

    def run(self, table_name: str, profile_summary: str = "", anomaly_findings: dict | None = None) -> dict:
        return self.tool.execute({
            "target_table": table_name,
            "profile_summary": profile_summary,
            "anomaly_findings": anomaly_findings or {}
        })
