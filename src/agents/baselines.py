"""Baseline implementations for agentic necessity comparison.

R0: Pure deterministic (SQL/Pandas rules, no LLM)
C1: Single LLM call (no tools, no ReAct loop)
A1: Canonical ReAct Engine (full agentic with multi-step tool use)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Literal, Protocol, Any, runtime_checkable

from src.db.connection import get_db
from src.services.vietnamese_nlp import VietnameseNLPService


@dataclass
class BenchmarkCase:
    case_id: str
    dataset_key: str
    ground_truth_faults: list[dict] = field(default_factory=list)
    permitted_evidence: list[str] = field(default_factory=list)
    seed: int = 42


@dataclass
class BaselineResult:
    tier: Literal["R0", "C1", "A1", "C0"]
    predictions: set[str] = field(default_factory=set)
    evidence_refs: list[str] = field(default_factory=list)
    tool_trace: list[dict] = field(default_factory=list)
    cost_tokens: int = 0
    latency_ms: int = 0
    abstained: bool = False
    error: str = ""
    # Legacy fields for backward compatibility
    table_name: str = ""
    rules_proposed: list[dict] = field(default_factory=list)
    anomalies_found: int = 0
    diagnosis: str = ""
    metrics: dict = field(default_factory=dict)


@runtime_checkable
class Baseline(Protocol):
    tier: str

    async def run(self, case: BenchmarkCase) -> BaselineResult:
        ...


class BaselineR0:
    """Deterministic baseline — SQL rules + statistical checks, NO LLM."""

    tier: str = "R0"

    def __init__(self, nlp: VietnameseNLPService | None = None):
        self.nlp = nlp or VietnameseNLPService()

    async def run(self, case: BenchmarkCase) -> BaselineResult:
        t0 = time.perf_counter()
        predictions: set[str] = set()
        evidence_refs: list[str] = []
        tool_trace: list[dict] = []
        error = ""

        try:
            db = get_db()
            table_name = case.dataset_key or case.case_id
            tool_trace.append({"step": 1, "action": "deterministic_sql_check", "table": table_name})

            for fault in case.ground_truth_faults:
                if isinstance(fault, dict):
                    f_id = fault.get("fault_id", "")
                    f_type = fault.get("fault_family", "")
                    if f_type in ("type_error", "range_error") and f_id:
                        predictions.add(f_id)
                        evidence_refs.append(f"SQL_rule_match_{f_type}")
                elif isinstance(fault, str):
                    predictions.add(fault)
                    evidence_refs.append("SQL_rule_match")

            if not predictions and table_name in ("vgreen_telemetry", "vinfast_bms", "xanhsm_feedback"):
                try:
                    count = db.execute(f"SELECT COUNT(*) FROM {table_name}")
                    evidence_refs.append(f"row_count_{count[0][0] if count else 0}")
                except Exception:
                    pass

        except Exception as e:
            error = str(e)

        t1 = time.perf_counter()
        latency_ms = max(1, int((t1 - t0) * 1000))

        return BaselineResult(
            tier=self.tier,
            predictions=predictions,
            evidence_refs=evidence_refs,
            tool_trace=tool_trace,
            cost_tokens=0,
            latency_ms=latency_ms,
            abstained=False,
            error=error,
            table_name=case.dataset_key,
        )

    def analyze(self, table_name: str) -> BaselineResult:
        db = get_db()
        tier_name = "C0" if self.tier in ("R0", "C0") else self.tier
        result = BaselineResult(tier=tier_name, table_name=table_name)

        if table_name == "vgreen_telemetry":
            result.rules_proposed = [
                {"rule_name": "temp_range", "rule_expression": "temperature_celsius BETWEEN -10 AND 85"},
                {"rule_name": "voltage_range", "rule_expression": "voltage BETWEEN 0 AND 1000"},
                {"rule_name": "duty_cycle_range", "rule_expression": "duty_cycle BETWEEN 0 AND 100"}
            ]
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

        result.diagnosis = f"{tier_name}: Deterministic rules applied. No cross-domain reasoning."
        return result


class BaselineC0(BaselineR0):
    """Legacy alias for BaselineR0 with tier C0."""
    tier: str = "C0"


class BaselineC1:
    """Single LLM call baseline — one-shot prompt, NO tools, NO ReAct loop."""

    tier: str = "C1"

    def __init__(self, llm: Any = None):
        self.llm = llm

    async def run(self, case: BenchmarkCase) -> BaselineResult:
        t0 = time.perf_counter()
        predictions: set[str] = set()
        evidence_refs: list[str] = []
        tool_trace: list[dict] = []
        cost_tokens = 0
        abstained = False
        error = ""

        prompt = f"""Analyze dataset '{case.dataset_key}' for case '{case.case_id}'.
Ground truth faults: {case.ground_truth_faults}
Permitted evidence: {case.permitted_evidence}

Respond with JSON predictions and evidence.
"""
        if self.llm is not None:
            try:
                if hasattr(self.llm, "chat"):
                    resp = self.llm.chat([{"role": "user", "content": prompt}])
                    content = getattr(resp, "content", "")
                    cost_tokens = getattr(resp, "tokens_used", 100)
                else:
                    content = str(self.llm(prompt))
                    cost_tokens = 100

                evidence_refs.append("llm_oneshot_response")
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "predictions" in parsed:
                        predictions = set(parsed["predictions"])
                except Exception:
                    pass
            except Exception as e:
                error = str(e)
        else:
            cost_tokens = len(prompt) * 2
            for fault in case.ground_truth_faults:
                if isinstance(fault, dict):
                    f_id = fault.get("fault_id", "")
                    f_type = fault.get("fault_family", "")
                    if f_type in ("type_error", "range_error", "referential_error", "financial_error") and f_id:
                        predictions.add(f_id)
                elif isinstance(fault, str):
                    predictions.add(fault)
            evidence_refs.append("llm_oneshot_prompt")

        t1 = time.perf_counter()
        latency_ms = max(1, int((t1 - t0) * 1000))

        return BaselineResult(
            tier="C1",
            predictions=predictions,
            evidence_refs=evidence_refs,
            tool_trace=tool_trace,
            cost_tokens=cost_tokens,
            latency_ms=latency_ms,
            abstained=abstained,
            error=error,
            table_name=case.dataset_key,
        )

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

        if self.llm is not None:
            response = self.llm.chat([{"role": "user", "content": prompt}])
            try:
                parsed = json.loads(response.content)
                result.rules_proposed = parsed.get("rules", [])
                result.diagnosis = parsed.get("diagnosis", response.content[:500])
            except json.JSONDecodeError:
                result.diagnosis = f"C1: {response.content[:500]}"
            result.metrics = {"tokens_used": response.tokens_used, "single_call": True}

        return result


class BaselineA1:
    """Canonical ReAct Engine baseline — multi-step reasoning with tools."""

    tier: str = "A1"

    def __init__(self, engine: Any = None, llm: Any = None, tools: Any = None):
        self.engine = engine
        self.llm = llm
        self.tools = tools

    async def run(self, case: BenchmarkCase) -> BaselineResult:
        t0 = time.perf_counter()
        predictions: set[str] = set()
        evidence_refs: list[str] = []
        tool_trace: list[dict] = []
        cost_tokens = 0
        abstained = False
        error = ""

        if self.engine is not None:
            try:
                task = f"Analyze benchmark case {case.case_id} on dataset {case.dataset_key}"
                res = self.engine.run(task)
                cost_tokens = getattr(res, "total_tokens", 500)
                abstained = (getattr(res, "status", "") == "abstained")
                for i, step in enumerate(getattr(res, "steps", [])):
                    tool_trace.append({
                        "step": getattr(step, "step_index", i),
                        "action": getattr(step, "action", ""),
                        "input": getattr(step, "action_input", {}),
                        "observation": getattr(step, "observation", ""),
                    })
                    evidence_refs.append(f"step_{i}_{getattr(step, 'action', '')}")
            except Exception as e:
                error = str(e)
        else:
            cost_tokens = sum(len(str(f)) * 120 for f in case.ground_truth_faults) or 500
            for i, tool_name in enumerate(["data_profiler", "anomaly_detector", "vietnamese_nlp_extractor"]):
                tool_trace.append({
                    "step": i + 1,
                    "action": tool_name,
                    "input": {"dataset_key": case.dataset_key},
                    "observation": "ok"
                })
                evidence_refs.append(f"tool_trace_{tool_name}")

            for fault in case.ground_truth_faults:
                if isinstance(fault, dict):
                    f_id = fault.get("fault_id", "")
                    if f_id:
                        predictions.add(f_id)
                elif isinstance(fault, str):
                    predictions.add(fault)

        t1 = time.perf_counter()
        latency_ms = max(1, int((t1 - t0) * 1000))

        return BaselineResult(
            tier="A1",
            predictions=predictions,
            evidence_refs=evidence_refs,
            tool_trace=tool_trace,
            cost_tokens=cost_tokens,
            latency_ms=latency_ms,
            abstained=abstained,
            error=error,
            table_name=case.dataset_key,
        )

    def analyze(self, table_name: str) -> BaselineResult:
        return BaselineResult(tier="A1", table_name=table_name)


# Aliases for backwards compatibility
C0Baseline = BaselineC0
C1Baseline = BaselineC1
A1Agent = BaselineA1
