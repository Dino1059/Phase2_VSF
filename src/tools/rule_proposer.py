from src.tools.base import BaseTool
from src.utils.table_utils import normalize_table_name


class RuleProposerTool(BaseTool):
    name = "quality_rule_proposer"
    description = "Propose data quality rules based on profiling results, NLP insights, and anomaly findings for a target DuckDB table."
    input_schema = {
        "type": "object",
        "properties": {
            "profile_summary": {"type": "string", "description": "Text summary of profile results"},
            "nlp_insights": {"type": "object", "description": "NLP analysis results"},
            "anomaly_findings": {"type": "object", "description": "Anomaly detection results"},
            "target_table": {"type": "string", "description": "Target DuckDB table"}
        },
        "required": ["target_table"]
    }

    def execute(self, input_data: dict) -> dict:
        table = normalize_table_name(input_data.get("target_table", "ev_telemetry"))
        profile = input_data.get("profile_summary", "")
        nlp = input_data.get("nlp_insights", {})
        anomalies = input_data.get("anomaly_findings", {})
        
        rules = []
        
        # Generate rules based on canonical table type
        if table == "ev_telemetry":
            rules.extend([
                {"rule_name": "soc_range", "rule_type": "range", "rule_expression": "battery_soc BETWEEN 0 AND 100", "confidence": 0.99, "rationale": "SOC is a percentage"},
                {"rule_name": "battery_temp_range", "rule_type": "range", "rule_expression": "battery_temp_c BETWEEN -10 AND 85", "confidence": 0.95, "rationale": "Industrial operating temperature range for EV"},
                {"rule_name": "battery_voltage_positive", "rule_type": "range", "rule_expression": "battery_voltage >= 0", "confidence": 0.99, "rationale": "Voltage must be non-negative"},
            ])
        elif table == "charging_sessions":
            rules.extend([
                {"rule_name": "station_temp_range", "rule_type": "range", "rule_expression": "station_temp_c BETWEEN -10 AND 85", "confidence": 0.95, "rationale": "Industrial operating temperature range for EV chargers"},
                {"rule_name": "power_non_negative", "rule_type": "range", "rule_expression": "power_kw >= 0", "confidence": 0.99, "rationale": "Charging power must be non-negative"},
                {"rule_name": "energy_non_negative", "rule_type": "range", "rule_expression": "kwh_consumed >= 0", "confidence": 0.99, "rationale": "Delivered energy must be non-negative"},
            ])
        elif table == "nlp_feedback":
            rules.extend([
                {"rule_name": "sentence_not_null", "rule_type": "null_check", "rule_expression": "sentence IS NOT NULL", "confidence": 0.95, "rationale": "Feedback should have text content"},
                {"rule_name": "sentiment_present", "rule_type": "null_check", "rule_expression": "sentiment IS NOT NULL", "confidence": 0.95, "rationale": "Feedback sentiment label is required"},
                {"rule_name": "topic_present", "rule_type": "null_check", "rule_expression": "topic IS NOT NULL", "confidence": 0.95, "rationale": "Feedback topic label is required"}
            ])
        elif table == "trips":
            rules.extend([
                {"rule_name": "trip_distance_positive", "rule_type": "range", "rule_expression": "trip_distance_km > 0", "confidence": 0.95, "rationale": "Trip distance must be positive"},
                {"rule_name": "fare_non_negative", "rule_type": "range", "rule_expression": "fare_amount >= 0", "confidence": 0.99, "rationale": "Fare must be non-negative"},
                {"rule_name": "total_fare_non_negative", "rule_type": "range", "rule_expression": "total_fare >= 0", "confidence": 0.99, "rationale": "Total fare must be non-negative"},
            ])
        
        # Add anomaly-based rules if anomaly findings provided
        if anomalies.get("anomalies_found", 0) > 0:
            stats = anomalies.get("statistics", {})
            if "mean" in stats and "std" in stats:
                col = anomalies.get("column_name", "value")
                lower = round(stats["mean"] - 3 * stats["std"], 2)
                upper = round(stats["mean"] + 3 * stats["std"], 2)
                rules.append({
                    "rule_name": f"{col}_3sigma",
                    "rule_type": "anomaly",
                    "rule_expression": f"{col} BETWEEN {lower} AND {upper}",
                    "confidence": 0.90,
                    "rationale": f"3-sigma bounds from statistical analysis (mean={stats['mean']}, std={stats['std']})"
                })

        # Persist proposed rules into DuckDB quality_rules table for HITL review
        try:
            from src.tools.chat_tools import persist_hitl_proposals
            d_key = table
            
            proposals_to_persist = []
            for idx, r in enumerate(rules, 1):
                proposals_to_persist.append({
                    "id": f"{d_key}__{r.get('rule_name', f'rule_{idx}')}",
                    "rule_name": r.get("rule_name"),
                    "rule_type": r.get("rule_type", "range_check"),
                    "rule_expression": r.get("rule_expression", "1=1"),
                    "confidence": r.get("confidence", 0.95),
                    "dataset_key": d_key,
                    "target_table": table,
                    "status": "proposed",
                    "proposed_by": "rule_proposer_agent",
                    "problem_discovered": r.get("rationale", "Discovered data quality issue during batch analysis."),
                    "why_proposed": f"Rule generated during analysis of table '{table}'.",
                    "quality_impact": "Prevents invalid or corrupt data from entering clean warehouse."
                })
            persist_hitl_proposals(d_key, proposals_to_persist)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not persist rules in RuleProposerTool: {e}")

        return {"proposed_rules": rules, "proposals": rules, "rule_count": len(rules), "target_table": table}
