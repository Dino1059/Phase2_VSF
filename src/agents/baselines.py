"""Baseline implementations for agentic necessity comparison.

C0: Pure deterministic (SQL/Pandas rules, no LLM)
C1: Single LLM call (no tools, no ReAct loop)
A1: Full agentic (ReAct + tools) — implemented by the orchestrator
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field

from src.db.connection import get_db
from src.services.vietnamese_nlp import VietnameseNLPService
from src.services.llm import GemmaLLMAdapter


@dataclass
class BaselineResult:
    tier: str  # 'C0', 'C1', 'A1'
    table_name: str
    rules_proposed: list[dict] = field(default_factory=list)
    anomalies_found: int = 0
    diagnosis: str = ""
    metrics: dict = field(default_factory=dict)


class BaselineC0:
    """Pure deterministic baseline — SQL rules + statistical checks, NO LLM."""

    def __init__(self):
        self.nlp = VietnameseNLPService()

    def analyze(self, table_name: str) -> BaselineResult:
        db = get_db()
        result = BaselineResult(tier="C0", table_name=table_name)

        # Hard-coded rules per table
        if table_name == "vgreen_telemetry":
            result.rules_proposed = [
                {"rule_name": "temp_range", "rule_expression": "temperature_celsius BETWEEN -10 AND 85"},
                {"rule_name": "voltage_range", "rule_expression": "voltage BETWEEN 0 AND 1000"},
                {"rule_name": "duty_cycle_range", "rule_expression": "duty_cycle BETWEEN 0 AND 100"}
            ]
            # Count violations
            for rule in result.rules_proposed:
                try:
                    count = db.execute(f"SELECT COUNT(*) FROM {table_name} WHERE NOT ({rule['rule_expression']})")
                    rule["violations"] = count[0][0] if count else 0
                except Exception:
                    rule["violations"] = -1

        elif table_name == "vinfast_bms":
            result.rules_proposed = [
                {"rule_name": "soc_range", "rule_expression": "battery_soc BETWEEN 0 AND 100"},
                {"rule_name": "cell_temp_range", "rule_expression": "cell_temp_max BETWEEN -20 AND 60"}
            ]
            for rule in result.rules_proposed:
                try:
                    count = db.execute(f"SELECT COUNT(*) FROM {table_name} WHERE NOT ({rule['rule_expression']})")
                    rule["violations"] = count[0][0] if count else 0
                except Exception:
                    rule["violations"] = -1

        elif table_name == "xanhsm_feedback":
            result.rules_proposed = [
                {"rule_name": "rating_range", "rule_expression": "rating BETWEEN 1 AND 5"},
                {"rule_name": "text_not_null", "rule_expression": "review_text IS NOT NULL"}
            ]
            for rule in result.rules_proposed:
                try:
                    count = db.execute(f"SELECT COUNT(*) FROM {table_name} WHERE NOT ({rule['rule_expression']})")
                    rule["violations"] = count[0][0] if count else 0
                except Exception:
                    rule["violations"] = -1

        result.diagnosis = "C0: Deterministic rules applied. No cross-domain reasoning."
        return result


class BaselineC1:
    """Single LLM call baseline — one-shot prompt, NO tools, NO ReAct loop."""

    def __init__(self, llm: GemmaLLMAdapter):
        self.llm = llm

    def analyze(self, table_name: str, sample_data: str = "") -> BaselineResult:
        result = BaselineResult(tier="C1", table_name=table_name)

        prompt = f"""Analyze this database table '{table_name}' and propose data quality rules.
Sample data: {sample_data[:2000]}

Respond with JSON:
{{
  "rules": [{{"rule_name": "...", "rule_expression": "SQL expression", "rationale": "..."}}],
  "anomalies": "description of potential anomalies",
  "diagnosis": "root cause analysis"
}}"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        try:
            parsed = json.loads(response.content)
            result.rules_proposed = parsed.get("rules", [])
            result.diagnosis = parsed.get("diagnosis", response.content[:500])
        except json.JSONDecodeError:
            result.diagnosis = f"C1: {response.content[:500]}"

        result.metrics = {"tokens_used": response.tokens_used, "single_call": True}
        return result

    def run(self, df):
        return []


C0Baseline = BaselineC0
C1Baseline = BaselineC1

class A1Agent:
    def __init__(self, llm=None):
        self.llm = llm
    def run(self, df):
        return []
    def analyze(self, table_name: str) -> BaselineResult:
        return BaselineResult(tier="A1", table_name=table_name)

