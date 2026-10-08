"""
Unit & Integration Tests for:
1. Fixed Compliance Check Rules (Backend managed, Read-Only, immutable)
2. Dynamic Data Treatment Rules (Generic, AI proposed noted separately, UI expression editable, approve/reject/toggle)
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.database.models import ComplianceCheckRuleModel, DataTreatmentRuleModel, RuleSeverity, OnFailAction
from backend.ingestion.load_3zone_pilot import get_3zone_compliance_rules, get_3zone_treatment_rules


@pytest.fixture
def client():
    return TestClient(app)


def test_compliance_check_rules_model():
    rule = ComplianceCheckRuleModel(
        rule_id="CHK-TEST-01",
        dataset_id="trips",
        column_name="fare_amount",
        rule_name="Test Revenue Check",
        rule_code="VAL-TEST-01",
        expression="fare_amount > 0",
        description="Must be strictly positive",
        law_ref="IFRS 15",
        severity=RuleSeverity.CRITICAL,
        on_fail_action=OnFailAction.QUARANTINE,
        is_fixed=True
    )
    assert rule.is_fixed is True
    assert rule.rule_code == "VAL-TEST-01"


def test_data_treatment_rules_model():
    rule = DataTreatmentRuleModel(
        rule_id="TRT-TEST-01",
        dataset_id="trips",
        column_name="customer_phone",
        operation_id="mask_phone",
        treatment_name="Che mờ số điện thoại",
        expression_display="mask_phone(customer_phone)",
        is_ai_proposed=True,
        ai_rationale="Protect PII according to Decree 13",
        ai_confidence=0.97,
        status="pending"
    )
    assert rule.is_ai_proposed is True
    assert rule.status == "pending"
    assert rule.ai_confidence == 0.97


def test_get_compliance_check_rules_endpoint(client):
    res = client.get("/api/rules/compliance-checks")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 5
    for r in data:
        assert r["is_fixed"] is True
        assert "rule_code" in r
        assert "expression" in r


def test_get_data_treatment_rules_endpoint(client):
    res = client.get("/api/rules/treatments")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 5
    ai_proposed = [r for r in data if r["is_ai_proposed"]]
    assert len(ai_proposed) >= 2


def test_update_treatment_rule_expression(client):
    new_expr = "mask_phone(customer_phone, prefix=4, suffix=2)"
    res = client.put(
        "/api/rules/treatments/TRT-PROP-PHONE",
        json={"expression_display": new_expr, "params_json": {"prefix": 4, "suffix": 2}}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["expression_display"] == new_expr
    assert data["params_json"]["prefix"] == 4


def test_ai_treatment_rule_approval_is_disabled(client):
    res_appr = client.post(
        "/api/rules/treatments/TRT-PROP-NAME/approve",
        json={"actor_name": "Nguyễn Quốc Bảo", "actor_role": "ADMIN"}
    )
    assert res_appr.status_code == 410


def test_ai_treatment_rule_rejection_is_disabled(client):
    res_rej = client.post(
        "/api/rules/treatments/TRT-PROP-VIN/reject",
        json={"actor_name": "Nguyễn Quốc Bảo", "actor_role": "ADMIN", "comments": "Not needed right now"}
    )
    assert res_rej.status_code == 410
