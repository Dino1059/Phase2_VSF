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
        if table in ("ev_telemetry", "vinfast_bms"):
            rules.extend([
                {"rule_name": "soc_range", "rule_type": "range", "rule_expression": "battery_soc BETWEEN 0 AND 100", "confidence": 0.99, "rationale": "SOC is a percentage"},
                {"rule_name": "temp_range_check", "rule_type": "range", "rule_expression": "temp_c BETWEEN -10 AND 85", "confidence": 0.95, "rationale": "Industrial operating temperature range for EV"},
                {"rule_name": "voltage_positive", "rule_type": "range", "rule_expression": "voltage_v >= 0 AND voltage_v <= 1000", "confidence": 0.99, "rationale": "Voltage must be non-negative and within specs"},
            ])
        elif table in ("charging_sessions", "vgreen_telemetry"):
            rules.extend([
                {"rule_name": "temp_range_check", "rule_type": "range", "rule_expression": "temperature_celsius BETWEEN -10 AND 85", "confidence": 0.95, "rationale": "Industrial operating temperature range for EV chargers"},
                {"rule_name": "voltage_positive", "rule_type": "range", "rule_expression": "voltage >= 0 AND voltage <= 1000", "confidence": 0.99, "rationale": "Voltage must be non-negative and within charger specs"},
                {"rule_name": "duty_cycle_range", "rule_type": "range", "rule_expression": "duty_cycle BETWEEN 0 AND 100", "confidence": 0.99, "rationale": "Duty cycle is a percentage"},
            ])
        elif table in ("xanhsm_feedback", "feedback", "synthetic_feedback", "nlp_feedback"):
            rules.extend([
                {"rule_name": "rating_range", "rule_type": "range", "rule_expression": "rating BETWEEN 1 AND 5", "confidence": 0.99, "rationale": "Star ratings 1-5"},
                {"rule_name": "review_not_empty", "rule_type": "null_check", "rule_expression": "review_text IS NOT NULL AND LENGTH(review_text) > 0", "confidence": 0.95, "rationale": "Reviews should have text content"},
                {"rule_name": "source_valid", "rule_type": "enum", "rule_expression": "source IN ('google_maps', 'play_store', 'shopee', 'uit_vsfc', 'xanh_sm', 'csv')", "confidence": 0.99, "rationale": "Source must be from known providers"}
            ])
        elif table in ("xanhsm_trips", "ride_trips", "trips", "raw_taxi_trips"):
            rules.extend([
                {"rule_name": "distance_positive", "rule_type": "range", "rule_expression": "distance_km > 0 AND distance_km < 500", "confidence": 0.95, "rationale": "Trip distance must be positive and reasonable"},
                {"rule_name": "fare_positive", "rule_type": "range", "rule_expression": "fare_amount >= 0 OR fare_vnd >= 0", "confidence": 0.99, "rationale": "Fare must be positive"},
                {"rule_name": "ledger_mismatch_check", "rule_type": "cross_field", "rule_expression": "ABS(total_fare - (fare_amount + COALESCE(tip_amount, 0))) < 0.01", "confidence": 0.95, "rationale": "Total fare must equal fare plus tip"},
                {"rule_name": "duration_positive", "rule_type": "range", "rule_expression": "duration_minutes > 0 AND duration_minutes < 1440", "confidence": 0.95, "rationale": "Trip duration must be under 24 hours"}
            ])
        elif table in ("vgreen_charging_sessions", "acn_charging", "charging_sessions", "charging"):
            rules.extend([
                {"rule_name": "cost_non_negative", "rule_type": "range", "rule_expression": "cost_vnd >= 0", "confidence": 0.99, "rationale": "Charging session cost must be non-negative"},
                {"rule_name": "duration_positive", "rule_type": "range", "rule_expression": "duration_mins > 0 AND duration_mins < 1440", "confidence": 0.95, "rationale": "Charging duration must be reasonable"},
                {"rule_name": "energy_positive", "rule_type": "range", "rule_expression": "energy_kwh >= 0", "confidence": 0.99, "rationale": "Delivered energy must be non-negative"},
                {"rule_name": "duration_energy_invariant", "rule_type": "cross_field", "rule_expression": "NOT (duration_mins > 180 AND energy_kwh < 5.0)", "confidence": 0.90, "rationale": "Session duration inflated without energy delivered indicates meter/tariff fault"}
            ])
        elif table not in ("unknown_table", "unknown") and (table.startswith("raw.") or any(k in table for k in ["telemetry", "trip", "charging", "bms", "feedback", "pilot", "ev"])):
            # Fallback rules for any new dataset table
            rules.extend([
                {"rule_name": f"{table}_non_null_id", "rule_type": "null_check", "rule_expression": "id IS NOT NULL", "confidence": 0.99, "rationale": "Primary ID field must not be null"},
                {"rule_name": f"{table}_valid_timestamp", "rule_type": "null_check", "rule_expression": "timestamp IS NOT NULL", "confidence": 0.95, "rationale": "Event timestamp must be valid"}
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
            d_key = "ev_telemetry"
            if "charging" in table or "vgreen" in table:
                d_key = "vgreen_charging"
            elif "trip" in table or "ride" in table:
                d_key = "xanhsm_trips"
            elif "feedback" in table:
                d_key = "xanhsm_feedback"
            
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
