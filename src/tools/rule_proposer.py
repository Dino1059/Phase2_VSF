import concurrent.futures
import json
import logging
import os
from typing import Any, Dict, List

from src.canonical_policy import get_canonical_policy
from src.services.llm import GemmaLLMAdapter
from src.tools.base import BaseTool
from src.utils.table_utils import normalize_table_name

logger = logging.getLogger(__name__)
LLM_RULE_TIMEOUT = float(os.environ.get("RULE_PROPOSER_LLM_TIMEOUT", "20"))


class RuleProposerTool(BaseTool):
    name = "quality_rule_proposer"
    description = (
        "Propose data quality rules with both validation checks and SQL remediation strategies "
        "based on policy manifest, profiling data, and anomaly findings."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "profile_summary": {"type": "string", "description": "Text or JSON summary of profile results"},
            "nlp_insights": {"type": "object", "description": "NLP analysis results"},
            "anomaly_findings": {"type": "object", "description": "Anomaly detection results"},
            "target_table": {"type": "string", "description": "Target DuckDB table"}
        },
        "required": ["target_table"]
    }

    def __init__(self, llm: GemmaLLMAdapter | None = None):
        self.llm = llm

    def execute(self, input_data: dict) -> dict:
        raw_target = input_data.get("target_table", "ev_telemetry")
        try:
            table = normalize_table_name(raw_target)
        except ValueError:
            table = "ev_telemetry"
        profile = input_data.get("profile_summary", "")
        anomalies = input_data.get("anomaly_findings", {})
        policy = get_canonical_policy(table)

        rules = []
        try:
            # 1. Attempt LLM 1-Prompt Rule Generation
            rules = self._generate_llm_rules(table, policy, profile, anomalies)
        except Exception as err:
            logger.warning(f"LLM rule generation failed or unavailable ({err}). Falling back to heuristic rules.")
            rules = []

        if not rules:
            # 2. Fallback to Heuristic Rules with Remediation SQL
            rules = self._generate_heuristic_rules(table, policy, anomalies)

        # 3. Persist proposals into DuckDB quality_rules table for HITL review
        try:
            from src.tools.chat_tools import persist_hitl_proposals
            d_key = table
            proposals_to_persist = []
            for idx, r in enumerate(rules, 1):
                rule_name = r.get("rule_name") or f"rule_{idx}"
                proposals_to_persist.append({
                    "id": f"{d_key}__{rule_name}",
                    "rule_name": rule_name,
                    "rule_type": r.get("rule_type", "range"),
                    "rule_expression": r.get("rule_expression", "1=1"),
                    "remediation_action": r.get("remediation_action", "NO_OP"),
                    "remediation_sql_expr": r.get("remediation_sql_expr", ""),
                    "confidence": r.get("confidence", 0.95),
                    "dataset_key": d_key,
                    "target_table": table,
                    "status": "proposed",
                    "proposed_by": "rule_proposer_agent",
                    "problem_discovered": r.get("problem_discovered") or r.get("rationale") or f"Discovered quality constraint on '{table}'.",
                    "why_proposed": r.get("why_proposed") or f"Rule generated during analysis of table '{table}'.",
                    "quality_impact": r.get("quality_impact") or "Prevents invalid or corrupt data from entering clean warehouse."
                })
            persist_hitl_proposals(d_key, proposals_to_persist)
        except Exception as e:
            logger.warning(f"Could not persist rules in RuleProposerTool: {e}")

        return {"proposed_rules": rules, "proposals": rules, "rule_count": len(rules), "target_table": table}

    def _generate_llm_rules(self, table: str, policy: dict, profile: Any, anomalies: dict) -> List[dict]:
        prompt = f"""
You are an expert Data Quality Engineer & SQL Specialist for DataTrust OS.
TASK: Analyze the provided Policy Manifest, Profiler Statistics, and Anomaly Findings for target table '{table}'.
Generate executable Data Quality Rules. Each rule MUST include BOTH a Validation Check SQL Expression (`rule_expression`) AND a Data Remediation SQL Expression (`remediation_sql_expr`).

INPUT CONTEXT:
1. Policy Manifest:
{json.dumps(policy, indent=2)}

2. Profiler Statistics:
{json.dumps(profile) if isinstance(profile, (dict, list)) else str(profile)[:1000]}

3. Anomaly Findings:
{json.dumps(anomalies, indent=2)[:1000]}

REQUIREMENTS:
Return JSON with key "rules" containing an array of objects. Schema for each object:
- "rule_name": string (e.g. "soc_range_clip")
- "rule_type": "range" | "null_check" | "anomaly" | "categorical"
- "rule_expression": string SQL validation check (e.g. "battery_soc BETWEEN 0 AND 100")
- "remediation_action": "CLIP" | "CLIP_ZERO" | "IMPUTE_MEAN" | "IMPUTE_DEFAULT" | "NO_OP"
- "remediation_sql_expr": string SQL expression (e.g. "CASE WHEN battery_soc < 0 THEN 0.0 WHEN battery_soc > 100 THEN 100.0 ELSE battery_soc END")
- "confidence": float between 0.50 and 0.99
- "problem_discovered": string explanation of data flaw
- "why_proposed": string remediation rationale
- "quality_impact": string benefit to clean warehouse
"""
        schema = {
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule_name": {"type": "string"},
                            "rule_type": {"type": "string"},
                            "rule_expression": {"type": "string"},
                            "remediation_action": {"type": "string"},
                            "remediation_sql_expr": {"type": "string"},
                            "confidence": {"type": "number"},
                            "problem_discovered": {"type": "string"},
                            "why_proposed": {"type": "string"},
                            "quality_impact": {"type": "string"}
                        },
                        "required": ["rule_name", "rule_expression", "remediation_action", "remediation_sql_expr"]
                    }
                }
            },
            "required": ["rules"]
        }

        def _call():
            llm = self.llm or GemmaLLMAdapter()
            return llm.generate_structured(prompt=prompt, schema=schema)

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            res = pool.submit(_call).result(timeout=LLM_RULE_TIMEOUT)
        except Exception as err:
            logger.warning("LLM rule generation timed out or failed (%s). Using heuristic/Ngan path.", err)
            pool.shutdown(wait=False, cancel_futures=True)
            return []
        else:
            pool.shutdown(wait=False)
        if isinstance(res, dict) and "rules" in res and isinstance(res["rules"], list):
            cleaned = []
            for r in res["rules"]:
                if isinstance(r, dict):
                    expr = r.get("rule_expression") or r.get("condition") or r.get("expression")
                    remed_act = r.get("remediation_action") or r.get("action") or "NO_OP"
                    remed_sql = r.get("remediation_sql_expr") or ""
                    if expr:
                        if not remed_sql:
                            if "battery_soc" in expr or "soc" in expr.lower():
                                remed_sql = "CASE WHEN battery_soc < 0 THEN 0.0 WHEN battery_soc > 100 THEN 100.0 ELSE battery_soc END"
                                remed_act = "CLIP"
                            elif "temp" in expr.lower():
                                remed_sql = "CASE WHEN battery_temp_c < -10 THEN -10.0 WHEN battery_temp_c > 85 THEN 85.0 ELSE battery_temp_c END"
                                remed_act = "CLIP_3SIGMA"
                            elif ">=" in expr or ">" in expr:
                                col_m = expr.split()[0].replace('"', '')
                                remed_sql = f"CASE WHEN {col_m} < 0 THEN 0.0 ELSE {col_m} END"
                                remed_act = "CLIP_ZERO"
                        cleaned.append({
                            "rule_name": r.get("rule_name", "custom_rule"),
                            "rule_type": r.get("rule_type", "range"),
                            "rule_expression": expr,
                            "remediation_action": remed_act,
                            "remediation_sql_expr": remed_sql,
                            "confidence": float(r.get("confidence", 0.95)),
                            "problem_discovered": r.get("problem_discovered") or r.get("reasoning") or "",
                            "why_proposed": r.get("why_proposed") or r.get("reasoning") or "",
                            "quality_impact": r.get("quality_impact") or ""
                        })
            if cleaned:
                return cleaned
        return []

    def _generate_heuristic_rules(self, table: str, policy: dict, anomalies: dict) -> List[dict]:
        rules = []
        cols = policy.get("columns", {})

        if table == "ev_telemetry":
            rules.extend([
                {
                    "rule_name": "soc_range",
                    "rule_type": "range",
                    "rule_expression": "battery_soc BETWEEN 0 AND 100",
                    "remediation_action": "CLIP",
                    "remediation_sql_expr": "CASE WHEN battery_soc < 0 THEN 0.0 WHEN battery_soc > 100 THEN 100.0 ELSE battery_soc END",
                    "confidence": 0.99,
                    "problem_discovered": "Battery SOC out of physical 0-100% bounds.",
                    "why_proposed": "SOC is percentage metric. Clip underflow to 0.0 and overflow to 100.0.",
                    "quality_impact": "Prevents corrupt battery state values from entering clean data warehouse."
                },
                {
                    "rule_name": "battery_temp_range",
                    "rule_type": "range",
                    "rule_expression": "battery_temp_c BETWEEN -10 AND 85",
                    "remediation_action": "CLIP",
                    "remediation_sql_expr": "CASE WHEN battery_temp_c < -10 THEN -10.0 WHEN battery_temp_c > 85 THEN 85.0 ELSE battery_temp_c END",
                    "confidence": 0.95,
                    "problem_discovered": "Battery temp out of industrial operating range (-10 to 85 C).",
                    "why_proposed": "Clip temperature anomalies to industrial bounds.",
                    "quality_impact": "Ensures temperature metrics remain within physical limits."
                },
                {
                    "rule_name": "battery_voltage_positive",
                    "rule_type": "range",
                    "rule_expression": "battery_voltage >= 0",
                    "remediation_action": "CLIP_ZERO",
                    "remediation_sql_expr": "CASE WHEN battery_voltage < 0 THEN 0.0 ELSE battery_voltage END",
                    "confidence": 0.99,
                    "problem_discovered": "Negative battery voltage detected.",
                    "why_proposed": "Battery voltage cannot be negative. Clip negative noise to 0.0.",
                    "quality_impact": "Eliminates negative sensor noise."
                }
            ])
        elif table == "charging_sessions":
            rules.extend([
                {
                    "rule_name": "station_temp_range",
                    "rule_type": "range",
                    "rule_expression": "station_temp_c BETWEEN -10 AND 85",
                    "remediation_action": "CLIP",
                    "remediation_sql_expr": "CASE WHEN station_temp_c < -10 THEN -10.0 WHEN station_temp_c > 85 THEN 85.0 ELSE station_temp_c END",
                    "confidence": 0.95,
                    "problem_discovered": "Charger station temp out of operating bounds.",
                    "why_proposed": "Clip extreme sensor values to physical charger limits.",
                    "quality_impact": "Maintains valid station telemetry."
                },
                {
                    "rule_name": "power_non_negative",
                    "rule_type": "range",
                    "rule_expression": "power_kw >= 0",
                    "remediation_action": "CLIP_ZERO",
                    "remediation_sql_expr": "CASE WHEN power_kw < 0 THEN 0.0 ELSE power_kw END",
                    "confidence": 0.99,
                    "problem_discovered": "Charging power is negative.",
                    "why_proposed": "Charging power must be non-negative.",
                    "quality_impact": "Prevents negative power telemetry."
                },
                {
                    "rule_name": "energy_non_negative",
                    "rule_type": "range",
                    "rule_expression": "kwh_consumed >= 0",
                    "remediation_action": "CLIP_ZERO",
                    "remediation_sql_expr": "CASE WHEN kwh_consumed < 0 THEN 0.0 ELSE kwh_consumed END",
                    "confidence": 0.99,
                    "problem_discovered": "Delivered energy (kWh) is negative.",
                    "why_proposed": "Energy consumed cannot be negative.",
                    "quality_impact": "Ensures accurate billing telemetry."
                }
            ])
        elif table == "nlp_feedback":
            rules.extend([
                {
                    "rule_name": "sentence_not_null",
                    "rule_type": "null_check",
                    "rule_expression": "sentence IS NOT NULL",
                    "remediation_action": "IMPUTE_DEFAULT",
                    "remediation_sql_expr": "COALESCE(sentence, 'UNSPECIFIED_FEEDBACK')",
                    "confidence": 0.95,
                    "problem_discovered": "Missing feedback comment text.",
                    "why_proposed": "Replace NULL sentence with default placeholder string.",
                    "quality_impact": "Prevents NULL NLP errors in sentiment processing pipeline."
                },
                {
                    "rule_name": "sentiment_present",
                    "rule_type": "null_check",
                    "rule_expression": "sentiment IS NOT NULL",
                    "remediation_action": "IMPUTE_DEFAULT",
                    "remediation_sql_expr": "COALESCE(sentiment, 'NEUTRAL')",
                    "confidence": 0.95,
                    "problem_discovered": "Missing sentiment tag.",
                    "why_proposed": "Default missing sentiment to NEUTRAL.",
                    "quality_impact": "Ensures sentiment analytics complete."
                }
            ])
        elif table == "trips":
            rules.extend([
                {
                    "rule_name": "trip_distance_positive",
                    "rule_type": "range",
                    "rule_expression": "trip_distance_km > 0",
                    "remediation_action": "CLIP_ZERO",
                    "remediation_sql_expr": "CASE WHEN trip_distance_km <= 0 THEN 0.01 ELSE trip_distance_km END",
                    "confidence": 0.95,
                    "problem_discovered": "Trip distance is zero or negative.",
                    "why_proposed": "Set minimum valid trip distance to 0.01 km.",
                    "quality_impact": "Guarantees positive trip distance."
                },
                {
                    "rule_name": "fare_non_negative",
                    "rule_type": "range",
                    "rule_expression": "fare_amount >= 0",
                    "remediation_action": "CLIP_ZERO",
                    "remediation_sql_expr": "CASE WHEN fare_amount < 0 THEN 0.0 ELSE fare_amount END",
                    "confidence": 0.99,
                    "problem_discovered": "Negative trip fare detected.",
                    "why_proposed": "Fare cannot be negative. Clip to 0.0.",
                    "quality_impact": "Fixes negative accounting entries."
                }
            ])

        # Dynamic 3-sigma anomaly rules if anomaly statistics provided
        anom_list = []
        if isinstance(anomalies, dict):
            if "all_anomalies" in anomalies and isinstance(anomalies["all_anomalies"], list):
                anom_list = anomalies["all_anomalies"]
            elif anomalies.get("anomalies_found", 0) > 0 and "statistics" in anomalies:
                anom_list = [anomalies]

        for anom in anom_list:
            if isinstance(anom, dict):
                stats = anom.get("stats") or anom.get("statistics") or {}
                col = anom.get("column") or anom.get("column_name") or "value"
                if "mean" in stats and "std" in stats:
                    mean_val = float(stats["mean"])
                    std_val = float(stats["std"])
                    lower = round(mean_val - 3 * std_val, 2)
                    upper = round(mean_val + 3 * std_val, 2)
                    rules.append({
                        "rule_name": f"{col}_3sigma",
                        "rule_type": "anomaly",
                        "rule_expression": f"{col} BETWEEN {lower} AND {upper}",
                        "remediation_action": "CLIP_3SIGMA",
                        "remediation_sql_expr": f"CASE WHEN {col} < {lower} THEN {lower} WHEN {col} > {upper} THEN {upper} ELSE {col} END",
                        "confidence": 0.90,
                        "problem_discovered": f"Statistical anomaly detected in column '{col}'.",
                        "why_proposed": f"3-sigma bounds from statistical analysis (mean={mean_val}, std={std_val}).",
                        "quality_impact": f"Clips statistical outliers in '{col}' to 3-sigma bounds."
                    })

        return rules
