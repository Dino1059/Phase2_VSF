import unittest
import duckdb
from src.canonical_policy import get_canonical_policy, CANONICAL_POLICY_MANIFEST
from src.tools.rule_proposer import RuleProposerTool
from src.api.quarantine_api import synthesize_remediation_sql


class TestRuleProposalRemediation(unittest.TestCase):

    def test_canonical_policy_manifest(self):
        policy = get_canonical_policy("ev_telemetry")
        self.assertIn("columns", policy)
        self.assertIn("battery_soc", policy["columns"])
        self.assertEqual(policy["columns"]["battery_soc"]["physical_min"], 0.0)
        self.assertEqual(policy["columns"]["battery_soc"]["physical_max"], 100.0)

    def test_rule_proposer_tool_execution(self):
        tool = RuleProposerTool()
        result = tool.execute({
            "target_table": "ev_telemetry",
            "profile_summary": "SOC min = -5.0, max = 105.0",
            "anomaly_findings": {"anomalies_found": 1, "statistics": {"mean": 50.0, "std": 10.0}, "column_name": "battery_temp_c"}
        })

        self.assertIn("proposed_rules", result)
        rules = result["proposed_rules"]
        self.assertGreater(len(rules), 0)

        soc_rule = next((r for r in rules if "soc" in r.get("rule_name", "").lower()), None)
        self.assertIsNotNone(soc_rule)
        self.assertIn("rule_expression", soc_rule)
        self.assertIn("remediation_sql_expr", soc_rule)
        self.assertIn("CASE WHEN battery_soc", soc_rule["remediation_sql_expr"])

    def test_synthesize_remediation_sql_incorporation(self):
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE quality_rules (
                id VARCHAR PRIMARY KEY,
                dataset_key VARCHAR,
                target_table VARCHAR,
                rule_name VARCHAR,
                rule_type VARCHAR,
                rule_expression VARCHAR,
                remediation_action VARCHAR,
                remediation_sql_expr TEXT,
                status VARCHAR
            );
            CREATE SCHEMA IF NOT EXISTS main;
            CREATE TABLE main.ev_telemetry (
                record_id VARCHAR,
                battery_soc DOUBLE
            );
        """)
        rule_id = "test_ev_telemetry__soc_range"
        conn.execute("""
            INSERT INTO quality_rules (id, dataset_key, target_table, rule_name, rule_type, rule_expression, remediation_action, remediation_sql_expr, status)
            VALUES (?, 'ev_telemetry', 'ev_telemetry', 'soc_range', 'range', 'battery_soc BETWEEN 0 AND 100', 'CLIP', 'CASE WHEN battery_soc < 0 THEN 0.0 WHEN battery_soc > 100 THEN 100.0 ELSE battery_soc END', 'proposed')
        """, [rule_id])

        sql, strategy, severity = synthesize_remediation_sql(rule_id, "SOC out of bounds", "ev_telemetry", db=conn)
        self.assertIn("clean.ev_telemetry", sql)
        self.assertIn("CLIP", strategy)


if __name__ == "__main__":
    unittest.main()
