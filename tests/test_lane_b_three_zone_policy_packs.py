import copy

import pytest

from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor
from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig
from backend.engine.operation_registry import OperationRegistry


def _rule(zone: str, pack_id: str, country=None):
    return {
        "rule_id": f"COMP-{zone}-CUSTOMER-ID",
        "version": 1,
        "dataset_id": "trips",
        "column_name": "customer_id",
        "rule_name": "Customer ID is pseudonymized",
        "rule_code": "CUSTOMER_ID_HASHED",
        "expression": "customer_id is pseudonymized",
        "description": "Post-treatment privacy control",
        "law_ref": zone,
        "policy_id": f"POL-{zone}",
        "pack_id": pack_id,
        "clause_id": f"CLAUSE-{zone}",
        "jurisdiction": zone,
        "country": country,
        "severity": "HIGH",
        "on_fail_action": "QUARANTINE",
        "status": "ACTIVE",
        "runtime_mode": "ENFORCED",
        "effective_from": "2020-01-01T00:00:00+00:00",
        "effective_to": None,
        "evaluation_phase": "POST_CHECK",
        "condition_json": {"operator": "hashed", "field": "customer_id", "length": 64},
        "missing_behavior": "FAIL",
        "invalid_type_behavior": "FAIL",
        "legal_review_required": False,
    }


def _treatment(zone: str, pack_id: str, country=None):
    return {
        "rule_id": f"TREAT-{zone}-CUSTOMER-ID",
        "version": 1,
        "dataset_id": "trips",
        "column": "customer_id",
        "operation_id": "HMAC_SHA256",
        "params": {"secret_ref": "DATATRUST_PSEUDONYMIZATION_KEY"},
        "policy_id": f"POL-{zone}",
        "pack_id": pack_id,
        "clause_id": f"CLAUSE-{zone}",
        "jurisdiction": zone,
        "country": country,
        "status": "ACTIVE",
        "runtime_mode": "ENFORCED",
        "effective_from": "2020-01-01T00:00:00+00:00",
    }


def test_three_zone_rules_are_selected_without_cross_zone_leakage(monkeypatch):
    monkeypatch.setenv("DATATRUST_PSEUDONYMIZATION_KEY", "test-only-key")
    rules = [
        _rule("VN", "PACK-VN"),
        _rule("EU", "PACK-EU"),
        _rule("US-CA", "PACK-USCA", country="US-CA"),
    ]
    treatments = [
        _treatment("VN", "PACK-VN"),
        _treatment("EU", "PACK-EU"),
        _treatment("US-CA", "PACK-USCA", country="US-CA"),
    ]
    processor = HierarchicalPolicyProcessor(
        active_compliance_rules=rules,
        active_treatments=treatments,
        compliance_mode="ENFORCED",
    )

    expected = {
        "VN": ("VN", "PACK-VN"),
        "EU": ("EU", "PACK-EU"),
        "US": ("US-CA", "PACK-USCA"),
    }
    for zone, (rule_zone, pack_id) in expected.items():
        raw = {"trip_id": zone, "subject_zone": zone, "customer_id": "CUSTOMER-1"}
        original = copy.deepcopy(raw)
        verdict = processor.process_single_record("trips", raw)
        assert verdict.status == "PASS"
        assert raw == original
        assert verdict.treated_record["customer_id"] != raw["customer_id"]
        assert len(verdict.treated_record["customer_id"]) == 64
        assert {item["pack_id"] for item in verdict.rule_executions if item["result"] == "PASS"} == {pack_id}
        assert verdict.treatment_executions[0]["jurisdiction"] == rule_zone


def test_missing_pack_is_fail_closed_even_in_shadow_mode():
    processor = HierarchicalPolicyProcessor(
        active_compliance_rules=[], active_treatments=[], compliance_mode="SHADOW"
    )
    verdict = processor.process_single_record(
        "trips", {"trip_id": "EU-1", "subject_zone": "EU"}
    )
    assert verdict.status == "FAIL"
    assert any(item.rule_id == "NO_ACTIVE_PACK" for item in verdict.violations)
    assert verdict.treated_record is None


def test_metadata_hierarchy_resolves_default_child():
    hierarchy = JurisdictionHierarchyConfig.from_rows([
        {"code": "GLOBAL", "parent_code": None},
        {"code": "US", "parent_code": "GLOBAL"},
        {"code": "US-CA", "parent_code": "US", "is_default": True},
    ])
    assert hierarchy.resolve_chain("US") == ["GLOBAL", "US", "US-CA"]


def test_privacy_operations_are_allowlisted_and_fail_closed(monkeypatch):
    monkeypatch.setenv("DATATRUST_PSEUDONYMIZATION_KEY", "test-only-key")
    assert len(OperationRegistry.execute(
        "HMAC_SHA256", "C-1", {"secret_ref": "DATATRUST_PSEUDONYMIZATION_KEY"}
    )) == 64
    assert OperationRegistry.execute("MASK_CONTACT", "a.person@example.com", {"keep_domain": True}).endswith("@example.com")
    assert "0987654321" not in OperationRegistry.execute("REDACT_PII_TEXT", "Call 0987654321 now")
    monkeypatch.delenv("DATATRUST_PSEUDONYMIZATION_KEY")
    with pytest.raises(RuntimeError, match="HMAC secret is unavailable"):
        OperationRegistry.execute(
            "HMAC_SHA256", "C-1", {"secret_ref": "DATATRUST_PSEUDONYMIZATION_KEY"}
        )
