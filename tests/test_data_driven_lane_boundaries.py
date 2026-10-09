from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor


def test_empty_lane_b_snapshot_does_not_reactivate_hardcoded_fallbacks():
    record = {
        "trip_id": "TRIP-EMPTY-SNAPSHOT",
        "subject_zone": "EU",
        "customer_phone": "0901234567",
        "pickup_latitude": 52.52,
        "pickup_longitude": 13.40,
    }

    verdict = HierarchicalPolicyProcessor(
        active_compliance_rules=[],
        active_treatments=[],
    ).process_single_record("trips", record)

    assert verdict.required_treatments == []
    assert verdict.treated_record is None
    assert verdict.status == "FAIL"
    assert verdict.rule_snapshot == []
    assert verdict.rule_snapshot_hash
    assert [item.rule_id for item in verdict.violations] == ["NO_ACTIVE_PACK"]


def test_treatment_requires_an_explicit_database_row():
    record = {
        "trip_id": "TRIP-CONFIGURED",
        "subject_zone": "VN",
        "customer_phone": "0901234567",
    }
    treatment = {
        "rule_id": "VN-PHONE-MASK",
        "dataset_id": "trips",
        "column_name": "customer_phone",
        "operation_id": "MASK",
        "params": {"prefix_len": 3, "suffix_len": 2},
        "jurisdiction": "VN",
        "policy_id": "POL-VN-LAW91",
    }
    compliance_rule = {
        "rule_id": "VN-PHONE-MASK-POST", "version": 1, "dataset_id": "trips",
        "column_name": "customer_phone", "rule_name": "Phone is masked",
        "rule_code": "PHONE_MASKED", "expression": "customer_phone is masked",
        "description": "Post-treatment verification", "law_ref": "VN privacy pack",
        "policy_id": "POL-VN-LAW91", "jurisdiction": "VN", "severity": "HIGH",
        "on_fail_action": "QUARANTINE", "status": "ACTIVE", "runtime_mode": "ENFORCED",
        "effective_from": "2020-01-01T00:00:00+00:00", "evaluation_phase": "POST_CHECK",
        "condition_json": {"operator": "masked", "field": "customer_phone"},
        "missing_behavior": "FAIL", "invalid_type_behavior": "FAIL",
    }

    verdict = HierarchicalPolicyProcessor(
        active_compliance_rules=[compliance_rule],
        active_treatments=[treatment],
    ).process_single_record("trips", record)

    assert verdict.treated_record["customer_phone"] == "090*****67"
    assert [item["rule_id"] for item in verdict.required_treatments] == ["VN-PHONE-MASK"]
