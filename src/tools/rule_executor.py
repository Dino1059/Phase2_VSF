import uuid
from datetime import datetime
from src.tools.base import BaseTool
from src.db.connection import get_db


class RuleExecutorTool(BaseTool):
    name = "rule_executor"
    description = "Execute an approved quality rule against its target table. Violations are quarantined. Supports dry_run mode for preview."
    input_schema = {
        "type": "object",
        "properties": {
            "rule_id": {"type": "string", "description": "ID of the approved quality rule to execute"},
            "dry_run": {"type": "boolean", "description": "If true, only count violations without quarantining", "default": True}
        },
        "required": ["rule_id"]
    }

    def execute(self, input_data: dict) -> dict:
        rule_id = input_data["rule_id"]
        dry_run = input_data.get("dry_run", True)
        db = get_db()

        # Fetch rule
        rules = db.execute("SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules WHERE id = ?", [rule_id])
        if not rules:
            return {"error": f"Rule '{rule_id}' not found", "records_checked": 0, "violations_found": 0, "quarantined_count": 0, "clean_count": 0}

        rule = rules[0]
        rule_name, rule_type, expression, status = rule[1], rule[2], rule[3], rule[4]

        if status != "approved" and not dry_run:
            return {"error": f"Rule '{rule_id}' status is '{status}', must be 'approved' to execute", "records_checked": 0, "violations_found": 0, "quarantined_count": 0, "clean_count": 0}

        # Determine target table from rule context
        # Simple heuristic: check expression for known column names
        target_table = self._infer_table(expression)

        try:
            # Count total records
            total = db.execute(f"SELECT COUNT(*) FROM {target_table}")[0][0]
            # Count violations (records NOT matching the rule)
            violation_query = f"SELECT COUNT(*) FROM {target_table} WHERE NOT ({expression})"
            violations = db.execute(violation_query)[0][0]
            clean = total - violations

            quarantined = 0
            if not dry_run and violations > 0:
                # Get violation IDs and quarantine them
                violation_rows = db.execute(f"SELECT id FROM {target_table} WHERE NOT ({expression}) LIMIT 1000")
                for row in violation_rows:
                    q_id = str(uuid.uuid4())[:8]
                    db.execute(
                        "INSERT INTO quarantine (id, source_table, source_row_id, rule_id, reason) VALUES (?, ?, ?, ?, ?)",
                        [q_id, target_table, row[0], rule_id, f"Violated rule: {rule_name} ({expression})"]
                    )
                    quarantined += 1

                # Log to audit
                db.execute(
                    "INSERT INTO audit_log (id, action, actor, target_table, target_id, details) VALUES (?, ?, ?, ?, ?, ?)",
                    [str(uuid.uuid4())[:8], "EXECUTE_RULE", "agent", target_table, rule_id,
                     f'{{"violations": {violations}, "quarantined": {quarantined}}}' ]
                )

            return {
                "records_checked": total,
                "violations_found": violations,
                "quarantined_count": quarantined,
                "clean_count": clean,
                "rule_name": rule_name,
                "dry_run": dry_run
            }
        except Exception as e:
            return {"error": str(e), "records_checked": 0, "violations_found": 0, "quarantined_count": 0, "clean_count": 0}

    def _infer_table(self, expression: str) -> str:
        """Infer target table from rule expression column names."""
        expr_lower = expression.lower()
        if any(k in expr_lower for k in ["temperature", "voltage", "duty_cycle", "station_id", "current_amps"]):
            return "vgreen_telemetry"
        elif any(k in expr_lower for k in ["battery_soc", "cell_temp", "bms_fault", "vehicle_id"]):
            return "vinfast_bms"
        elif any(k in expr_lower for k in ["review_text", "rating", "source"]):
            return "xanhsm_feedback"
        elif any(k in expr_lower for k in ["distance_km", "fare_vnd", "duration_minutes", "trip_id"]):
            return "xanhsm_trips"
        return "xanhsm_feedback"  # default fallback
