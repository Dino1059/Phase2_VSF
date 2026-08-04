from src.tools.base import BaseTool


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
        table = input_data["target_table"]
        profile = input_data.get("profile_summary", "")
        nlp = input_data.get("nlp_insights", {})
        anomalies = input_data.get("anomaly_findings", {})
        
        rules = []
        
        # Generate rules based on table type
        if table == "vgreen_telemetry":
            rules.extend([
                {"rule_name": "temp_range_check", "rule_type": "range", "rule_expression": "temperature_celsius BETWEEN -10 AND 85", "confidence": 0.95, "rationale": "Industrial operating temperature range for EV chargers"},
                {"rule_name": "voltage_positive", "rule_type": "range", "rule_expression": "voltage >= 0 AND voltage <= 1000", "confidence": 0.99, "rationale": "Voltage must be non-negative and within charger specs"},
                {"rule_name": "duty_cycle_range", "rule_type": "range", "rule_expression": "duty_cycle BETWEEN 0 AND 100", "confidence": 0.99, "rationale": "Duty cycle is a percentage"},
                {"rule_name": "fault_temp_correlation", "rule_type": "cross_field", "rule_expression": "NOT (temperature_celsius > 80 AND fault_code IS NULL)", "confidence": 0.85, "rationale": "High temp without fault code suggests sensor/logging issue"}
            ])
        elif table == "vinfast_bms":
            rules.extend([
                {"rule_name": "soc_range", "rule_type": "range", "rule_expression": "battery_soc BETWEEN 0 AND 100", "confidence": 0.99, "rationale": "SOC is a percentage"},
                {"rule_name": "cell_temp_range", "rule_type": "range", "rule_expression": "cell_temp_max BETWEEN -20 AND 60", "confidence": 0.95, "rationale": "Lithium cell safe operating temperature"},
                {"rule_name": "cell_temp_delta", "rule_type": "cross_field", "rule_expression": "cell_temp_max - cell_temp_min < 15", "confidence": 0.90, "rationale": "Large temp delta indicates cell imbalance"}
            ])
        elif table == "xanhsm_feedback":
            rules.extend([
                {"rule_name": "rating_range", "rule_type": "range", "rule_expression": "rating BETWEEN 1 AND 5", "confidence": 0.99, "rationale": "Star ratings 1-5"},
                {"rule_name": "review_not_empty", "rule_type": "null_check", "rule_expression": "review_text IS NOT NULL AND LENGTH(review_text) > 0", "confidence": 0.95, "rationale": "Reviews should have text content"},
                {"rule_name": "source_valid", "rule_type": "enum", "rule_expression": "source IN ('google_maps', 'play_store', 'shopee', 'uit_vsfc', 'xanh_sm', 'csv')", "confidence": 0.99, "rationale": "Source must be from known providers"}
            ])
        elif table == "xanhsm_trips":
            rules.extend([
                {"rule_name": "distance_positive", "rule_type": "range", "rule_expression": "distance_km > 0 AND distance_km < 500", "confidence": 0.95, "rationale": "Trip distance must be positive and reasonable"},
                {"rule_name": "fare_positive", "rule_type": "range", "rule_expression": "fare_vnd > 0", "confidence": 0.99, "rationale": "Fare must be positive"},
                {"rule_name": "duration_positive", "rule_type": "range", "rule_expression": "duration_minutes > 0 AND duration_minutes < 1440", "confidence": 0.95, "rationale": "Trip duration must be under 24 hours"}
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

        return {"proposed_rules": rules, "rule_count": len(rules), "target_table": table}
