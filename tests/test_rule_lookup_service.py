"""
Unit and Integration Tests for RuleLookupService and Rule Ecosystem AI Scope.
Validates:
1. Telemetry-backed Run Execution Inspection (audit.record_policy_executions)
2. PASS rules are included in evaluated_rules
3. FAIL rules link to findings and quarantine
4. SKIP rules are preserved
5. 0 findings does not mean 0 evaluated rules
6. Jurisdiction hierarchy and local override over GLOBAL
7. Historical retired rule lookup with temporal snapshot
8. Missing telemetry marks execution_unknown=True
9. Multiple matches for same operation (e.g. mask_phone) returns FOUND_MANY
10. NOT_FOUND returns no fabricated law references (anti-hallucination)
11. DB connection error resilience returns DB_ERROR
12. IntentClassifier accurately differentiates RULE_INQUIRY vs REMEDIATION_ONLY
13. DataTrustAgentOrchestrator integration for rule queries maintains friendly, empathetic tone
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from backend.ai.agents.orchestrator import DataTrustAgentOrchestrator
from backend.ai.services.intent_classifier import IntentClassifier, UserIntent
from backend.ai.services.rule_lookup_service import (
    RuleFamily,
    RuleLookupResult,
    RuleLookupService,
    RuleLookupStatus,
)


class TestRuleLookupService:

    def test_executed_rules_pass_included(self):
        """
        Test: audit.record_policy_executions includes rules that PASSED,
        ensuring passed rules are part of evaluated_rules.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Simulate 1 PASS rule, 0 FAIL
        mock_cur.fetchall.side_effect = [
            # 1. exec_rows
            [
                {
                    "rule_id": "VAL-PASS-01",
                    "rule_version": 1,
                    "execution_type": "DETERMINISTIC",
                    "phase": "PRE_CHECK",
                    "rule_snapshot": {"rule_name": "Check Passenger Count", "expression": "count > 0", "law_ref": "Standard Ops"},
                    "total_evaluations": 100,
                    "pass_count": 100,
                    "fail_count": 0,
                    "skip_count": 0,
                }
            ],
            # 2. findings
            [],
            # 3. quarantine
            [],
            # 4. warnings
            [],
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_executed_rules_for_run("run_mock_pass_01")

        assert result.status == RuleLookupStatus.FOUND_MANY
        assert len(result.evaluated_rules) == 1
        assert result.evaluated_rules[0]["rule_id"] == "VAL-PASS-01"
        assert result.evaluated_rules[0]["pass_count"] == 100
        assert result.evaluated_rules[0]["fail_count"] == 0
        # Should not be in triggered_rules since fail_count == 0 and no findings
        assert len(result.triggered_rules) == 0
        assert result.execution_unknown is False

    def test_executed_rules_fail_linked_to_finding(self):
        """
        Test: Rules that failed are correctly linked to finding & quarantine records in triggered_rules.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            # 1. exec_rows
            [
                {
                    "rule_id": "L1-PHONE-01",
                    "rule_version": 2,
                    "execution_type": "DETERMINISTIC",
                    "phase": "PRE_CHECK",
                    "rule_snapshot": {"rule_name": "Phone Format VN", "expression": "is_valid_vn_phone", "law_ref": "Nghị định 13/2023/NĐ-CP"},
                    "total_evaluations": 1000,
                    "pass_count": 980,
                    "fail_count": 20,
                    "skip_count": 0,
                }
            ],
            # 2. findings
            [
                {
                    "rule_id": "L1-PHONE-01",
                    "column_name": "customer_phone",
                    "dataset_id": "trips",
                    "severity": "CRITICAL",
                    "reason": "Malformed Vietnamese phone numbers",
                    "law_ref": "Nghị định 13/2023/NĐ-CP",
                    "failed_record_count": 20,
                }
            ],
            # 3. quarantine
            [
                {
                    "violation_rule_id": "L1-PHONE-01",
                    "quarantine_count": 20,
                    "columns": ["customer_phone"],
                }
            ],
            # 4. warnings
            [],
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_executed_rules_for_run("run_mock_fail_01")

        assert result.status == RuleLookupStatus.FOUND_MANY
        assert len(result.evaluated_rules) == 1
        assert len(result.triggered_rules) == 1

        trig = result.triggered_rules[0]
        assert trig["rule_id"] == "L1-PHONE-01"
        assert trig["fail_count"] == 20
        assert trig["finding"]["severity"] == "CRITICAL"
        assert trig["quarantine_count"] == 20
        assert trig["finding"]["column_name"] == "customer_phone"

    def test_executed_rules_skip_handled(self):
        """
        Test: Rules that were skipped during execution are preserved with skip_count intact.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            # 1. exec_rows
            [
                {
                    "rule_id": "VAL-SKIP-01",
                    "rule_version": 1,
                    "execution_type": "DETERMINISTIC",
                    "phase": "POST_CHECK",
                    "rule_snapshot": {"rule_name": "Skip Inactive Phase", "expression": "fare_amount > 0"},
                    "total_evaluations": 50,
                    "pass_count": 0,
                    "fail_count": 0,
                    "skip_count": 50,
                }
            ],
            [],
            [],
            [],
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_executed_rules_for_run("run_mock_skip_01")

        assert len(result.evaluated_rules) == 1
        assert result.evaluated_rules[0]["skip_count"] == 50
        assert result.evaluated_rules[0]["pass_count"] == 0
        assert len(result.triggered_rules) == 0

    def test_no_findings_does_not_mean_no_rules(self):
        """
        Test: A run with 0 findings still returns evaluated rules if policy executions exist.
        Zero findings != Zero rules evaluated.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            # 1. exec_rows: 3 rules all passed perfectly
            [
                {
                    "rule_id": "R1", "rule_version": 1, "execution_type": "DETERMINISTIC",
                    "phase": "PRE_CHECK", "rule_snapshot": {"rule_name": "R1"},
                    "total_evaluations": 500, "pass_count": 500, "fail_count": 0, "skip_count": 0
                },
                {
                    "rule_id": "R2", "rule_version": 1, "execution_type": "DETERMINISTIC",
                    "phase": "PRE_CHECK", "rule_snapshot": {"rule_name": "R2"},
                    "total_evaluations": 500, "pass_count": 500, "fail_count": 0, "skip_count": 0
                },
                {
                    "rule_id": "R3", "rule_version": 1, "execution_type": "DETERMINISTIC",
                    "phase": "PRE_CHECK", "rule_snapshot": {"rule_name": "R3"},
                    "total_evaluations": 500, "pass_count": 500, "fail_count": 0, "skip_count": 0
                },
            ],
            [],  # findings: EMPTY
            [],  # quarantine: EMPTY
            [],  # warnings: EMPTY
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_executed_rules_for_run("clean_run_999")

        assert len(result.evaluated_rules) == 3
        assert len(result.triggered_rules) == 0
        assert result.execution_unknown is False

    def test_jurisdiction_priority_and_overrides(self):
        """
        Test: VN jurisdiction rule overrides GLOBAL compliance rule having the same rule_id.
        Chain: ['GLOBAL', 'VN'] -> VN (index 1) overrides GLOBAL (index 0).
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        now = datetime.now(timezone.utc)
        mock_cur.fetchall.side_effect = [
            # 1. Compliance rows: both GLOBAL and VN versions exist
            [
                {
                    "rule_id": "POL-TAX-01",
                    "version": 1,
                    "dataset_id": "trips",
                    "column_name": "vat_rate",
                    "rule_name": "Standard VAT Global",
                    "rule_code": "TAX-01",
                    "expression": "vat == 0.15",
                    "jurisdiction": "GLOBAL",
                    "law_ref": "Global Tax Framework",
                    "status": "ACTIVE",
                    "effective_from": now - timedelta(days=30),
                    "effective_to": None,
                },
                {
                    "rule_id": "POL-TAX-01",
                    "version": 2,
                    "dataset_id": "trips",
                    "column_name": "vat_rate",
                    "rule_name": "Standard VAT Vietnam",
                    "rule_code": "TAX-01",
                    "expression": "vat == 0.08",
                    "jurisdiction": "VN",
                    "law_ref": "Nghị quyết 110/2023/QH15",
                    "status": "ACTIVE",
                    "effective_from": now - timedelta(days=10),
                    "effective_to": None,
                },
            ],
            # 2. Treatment rows
            [],
            # 3. Reliability rows
            [],
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_configured_rules_for_dataset(
                dataset_id="trips",
                jurisdiction="VN"
            )

        assert result.status == RuleLookupStatus.FOUND_MANY
        assert len(result.rules) == 1
        active_rule = result.rules[0]
        # Should be the VN version overriding the GLOBAL version
        assert active_rule["jurisdiction"] == "VN"
        assert active_rule["rule_name"] == "Standard VAT Vietnam"
        assert active_rule["expression"] == "vat == 0.08"
        assert active_rule["law_ref"] == "Nghị quyết 110/2023/QH15"

    def test_retired_rule_found_in_historical_run(self):
        """
        Test: A rule that has expired/retired today can still be looked up when querying
        with as_of set to the historical run date.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        run_date = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        retired_rule = {
            "rule_id": "RULE-OLD-2025",
            "version": 1,
            "dataset_id": "trips",
            "column_name": "legacy_field",
            "rule_name": "Legacy 2025 Verification",
            "rule_code": "LEG-01",
            "expression": "legacy_field IS NOT NULL",
            "jurisdiction": "GLOBAL",
            "law_ref": "Circular 2024",
            "status": "ACTIVE",
            "effective_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "effective_to": datetime(2025, 12, 31, tzinfo=timezone.utc),
        }

        mock_cur.fetchall.side_effect = [
            [retired_rule],  # compliance
            [],              # treatment
            [],              # reliability
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_configured_rules_for_dataset(
                dataset_id="trips",
                as_of=run_date
            )

        assert result.status == RuleLookupStatus.FOUND_MANY
        assert len(result.rules) == 1
        assert result.rules[0]["rule_id"] == "RULE-OLD-2025"
        # Verify as_of in query
        called_args = mock_cur.execute.call_args_list[0][0][1]
        assert called_args[4] == run_date

    def test_missing_telemetry_marks_unknown(self):
        """
        Test: A run lacking audit.record_policy_executions records returns execution_unknown=True,
        falling back to findings/warnings if available without claiming full telemetry.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            [],  # exec_rows: EMPTY! (No policy execution telemetry)
            [    # finding exists
                {
                    "rule_id": "L1-INFERRED-01",
                    "column_name": "driver_id",
                    "dataset_id": "trips",
                    "severity": "MEDIUM",
                    "reason": "Driver not registered",
                    "law_ref": "Internal Policy",
                    "failed_record_count": 5,
                }
            ],
            [],  # quarantine
            [],  # warnings
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.get_executed_rules_for_run("run_without_telemetry")

        assert result.execution_unknown is True
        assert len(result.triggered_rules) == 1
        assert result.triggered_rules[0]["source"] == "FINDING_INFERRED"
        assert result.triggered_rules[0]["rule_id"] == "L1-INFERRED-01"

    def test_lookup_multiple_rules_same_operation(self):
        """
        Test: Querying 'mask_phone' across datasets or families returns FOUND_MANY
        with all matching rules.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            [],  # compliance
            [    # treatment: 2 rules with operation mask_phone
                {
                    "rule_id": "TRT-PHONE-01",
                    "dataset_id": "ride_hailing_xanh_sm_trips",
                    "column_name": "customer_phone",
                    "operation_id": "mask_phone",
                    "treatment_name": "Che mờ số điện thoại khách hàng",
                    "law_ref": "Nghị định 13/2023/NĐ-CP",
                },
                {
                    "rule_id": "TRT-DRIVER-01",
                    "dataset_id": "driver_profiles",
                    "column_name": "phone_number",
                    "operation_id": "mask_phone",
                    "treatment_name": "Che mờ số điện thoại tài xế",
                    "law_ref": "Nghị định 13/2023/NĐ-CP",
                },
            ],
            [],  # reliability
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.lookup_by_identifier("mask_phone")

        assert result.status == RuleLookupStatus.FOUND_MANY
        assert len(result.rules) == 2
        rule_ids = [r["rule_id"] for r in result.rules]
        assert "TRT-PHONE-01" in rule_ids
        assert "TRT-DRIVER-01" in rule_ids

    def test_lookup_not_found_no_law_fabrication(self):
        """
        Test: A non-existent rule returns NOT_FOUND and does NOT fabricate law citations.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            [],  # compliance: empty
            [],  # treatment: empty
            [],  # reliability: empty
        ]

        with patch("backend.ai.services.rule_lookup_service.get_db_connection", return_value=mock_conn):
            result = RuleLookupService.lookup_by_identifier("NON_EXISTENT_RULE_9999")

        assert result.status == RuleLookupStatus.NOT_FOUND
        assert result.rule is None
        assert "Không tìm thấy" in result.error_message
        # Strictly verify no hallucination
        assert "Nghị định 13" not in result.error_message
        assert "Luật 91" not in result.error_message

    def test_lookup_db_error_resilience(self):
        """
        Test: Simulated database connection failure returns DB_ERROR cleanly
        without crashing the application.
        """
        with patch("backend.ai.services.rule_lookup_service.get_db_connection", side_effect=Exception("DB connection refused")):
            result = RuleLookupService.lookup_by_identifier("L1-01")

        assert result.status == RuleLookupStatus.DB_ERROR
        assert "Lỗi kết nối cơ sở dữ liệu" in result.error_message
        assert result.rule is None


class TestIntentClassifierRuleRouting:

    def test_intent_rule_inquiry_vs_remediation(self):
        """
        Test: Action-based intent differentiation.
        - Questions asking what a rule is, or what rules exist -> RULE_INQUIRY
        - Questions asking to propose, create, or update a rule -> REMEDIATION_ONLY
        """
        # Rule inquiries
        assert IntentClassifier.classify("Rule L1-01 là gì?") == UserIntent.RULE_INQUIRY
        assert IntentClassifier.classify("Giải thích cho tôi quy tắc VAL-02") == UserIntent.RULE_INQUIRY
        assert IntentClassifier.classify("Hệ thống có những compliance rules nào?") == UserIntent.RULE_INQUIRY
        assert IntentClassifier.classify("Có những treatment rule nào cho dataset này?") == UserIntent.RULE_INQUIRY
        assert IntentClassifier.classify("Cho tôi danh sách các quy tắc reliability") == UserIntent.RULE_INQUIRY
        assert IntentClassifier.classify("Định nghĩa của rule mask_phone") == UserIntent.RULE_INQUIRY

        # Remediation requests
        assert IntentClassifier.classify("Đề xuất treatment rule cho customer_phone") == UserIntent.REMEDIATION_ONLY
        assert IntentClassifier.classify("Hãy tạo rule mới để xử lý số điện thoại") == UserIntent.REMEDIATION_ONLY
        assert IntentClassifier.classify("Cần sửa rule này để không bị lỗi") == UserIntent.REMEDIATION_ONLY
        assert IntentClassifier.classify("Đề xuất quy tắc khắc phục vi phạm") == UserIntent.REMEDIATION_ONLY


class TestOrchestratorRuleEcosystemChat:

    @pytest.mark.asyncio
    async def test_orchestrator_handles_single_rule_inquiry(self):
        """
        Test: Orchestrator routes RULE_INQUIRY for a single rule, calls RuleLookupService,
        and generates response with cute emojis and verified data without hallucination.
        """
        mock_rule = {
            "rule_id": "L1-01",
            "rule_code": "VAL-PHONE-01",
            "rule_name": "Kiểm tra định dạng số điện thoại VN",
            "family": "COMPLIANCE",
            "dataset_id": "ride_hailing_xanh_sm_trips",
            "column_name": "customer_phone",
            "expression": "^(\\+84|0)(3|5|7|8|9)[0-9]{8}$",
            "law_ref": "Nghị định 13/2023/NĐ-CP",
            "severity": "CRITICAL",
            "on_fail_action": "QUARANTINE",
            "status": "ACTIVE",
            "version": 1,
            "description": "Số điện thoại di động Việt Nam hợp lệ",
        }

        lookup_result = RuleLookupResult(
            status=RuleLookupStatus.FOUND_ONE,
            query="L1-01",
            family=RuleFamily.COMPLIANCE,
            rule=mock_rule,
            rules=[mock_rule]
        )

        with patch("backend.ai.services.rule_lookup_service.RuleLookupService.lookup_by_identifier", return_value=lookup_result):
            orchestrator = DataTrustAgentOrchestrator()
            res_dict = await orchestrator.chat(
                message="Rule L1-01 là gì?",
                run_id="run_test_01"
            )

        assert res_dict is not None
        response_text = res_dict.get("response", "")
        assert "L1-01" in response_text
        assert "Nghị định 13/2023/NĐ-CP" in response_text
        # Verify cute, friendly tone with sensible emojis
        assert any(emoji in response_text for emoji in ["✨", "🛡️", "🚗", "💡", "📝", "🎉", "🌟"])

    @pytest.mark.asyncio
    async def test_orchestrator_handles_run_executed_rules_query(self):
        """
        Test: Orchestrator routes queries about executed rules in the current run,
        presenting the tri-partition (passed, triggered) with execution ledger backing.
        """
        lookup_result = RuleLookupResult(
            status=RuleLookupStatus.FOUND_MANY,
            query="run_test_01",
            evaluated_rules=[
                {
                    "rule_id": "VAL-01", "rule_version": 1, "rule_name": "Check Fare",
                    "pass_count": 500, "fail_count": 0, "skip_count": 0
                },
                {
                    "rule_id": "VAL-02", "rule_version": 1, "rule_name": "Check Phone",
                    "pass_count": 480, "fail_count": 20, "skip_count": 0
                }
            ],
            triggered_rules=[
                {
                    "rule_id": "VAL-02", "rule_version": 1, "rule_name": "Check Phone",
                    "fail_count": 20
                }
            ],
            execution_unknown=False
        )

        with patch("backend.ai.services.rule_lookup_service.RuleLookupService.get_executed_rules_for_run", return_value=lookup_result):
            orchestrator = DataTrustAgentOrchestrator()
            res_dict = await orchestrator.chat(
                message="Lần chạy này đã áp dụng những quy tắc nào?",
                run_id="run_test_01"
            )

        response_text = res_dict.get("response", "")
        assert "VAL-01" in response_text
        assert "VAL-02" in response_text
        assert "audit.record_policy_executions" in response_text
        assert "Tổng quy tắc đã đánh giá" in response_text
        assert any(emoji in response_text for emoji in ["✨", "📋", "🟢", "🔴", "💡"])
