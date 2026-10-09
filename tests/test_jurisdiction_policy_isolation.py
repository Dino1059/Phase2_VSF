from backend.engine.hierarchical_policy_processor import HierarchicalPolicyProcessor
from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig
from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter


def _treatment(zone: str, policy_id: str, law_ref: str):
    return {
        "rule_id": f"MASK-PHONE-{zone}",
        "column": "customer_phone",
        "operation_id": "MASK",
        "params": {"prefix_len": 3, "suffix_len": 2},
        "jurisdiction": zone,
        "policy_id": policy_id,
        "policy_name": policy_id,
        "law_ref": law_ref,
    }


def test_resolver_normalizes_zone_without_inventing_country():
    resolver = JurisdictionHierarchyConfig()
    assert resolver.resolve_chain(" eu ") == ["GLOBAL", "EU"]
    assert resolver.resolve_chain("VN") == ["GLOBAL", "VN"]
    assert resolver.resolve_chain("us") == ["GLOBAL", "US", "US-CA"]
    assert resolver.resolve_chain("EU", "DE") == ["GLOBAL", "EU", "DE"]


def test_mixed_zone_batch_applies_only_matching_treatment():
    treatments = [
        _treatment("EU", "POL-EU-GDPR", "GDPR Art. 5"),
        _treatment("VN", "POL-VN-LAW91", "Luật 91/2025/QH15"),
        _treatment("US", "POL-US-CCPA", "CCPA § 1798.100"),
    ]
    records = [
        {"trip_id": "EU-1", "subject_zone": " EU ", "customer_phone": "0123456789"},
        {"trip_id": "VN-1", "subject_zone": "vn", "customer_phone": "0123456789"},
        {"trip_id": "US-1", "subject_zone": "US", "customer_phone": "0123456789"},
    ]
    verdicts = HierarchicalPolicyProcessor(active_treatments=treatments).process_records("trips", records)

    by_zone = {item.normalized_zone: item for item in verdicts}
    assert set(by_zone) == {"EU", "VN", "US"}
    assert by_zone["EU"].applied_policy_ids == ["POL-EU-GDPR"]
    assert by_zone["VN"].applied_policy_ids == ["POL-VN-LAW91"]
    assert by_zone["US"].applied_policy_ids == ["POL-US-CCPA"]
    for verdict in verdicts:
        assert len(verdict.required_treatments) == 1
        assert verdict.required_treatments[0]["jurisdiction"] == verdict.normalized_zone


def test_country_rule_overrides_zone_and_global_for_same_operation():
    treatments = [
        _treatment("GLOBAL", "POL-GLOBAL", "Global control"),
        _treatment("EU", "POL-EU-GDPR", "GDPR Art. 5"),
        {
            **_treatment("EU", "POL-DE-BDSG", "BDSG"),
            "country": "DE",
        },
    ]
    verdict = HierarchicalPolicyProcessor(active_treatments=treatments).process_single_record(
        "trips",
        {"trip_id": "DE-1", "subject_zone": "EU", "country": "DE", "customer_phone": "0123456789"},
    )
    assert len(verdict.required_treatments) == 1
    assert verdict.required_treatments[0]["policy_id"] == "POL-DE-BDSG"


def test_unknown_zone_uses_only_global_controls_and_reports_missing_pack():
    treatments = [
        _treatment("GLOBAL", "POL-GLOBAL", "Global control"),
        _treatment("EU", "POL-EU-GDPR", "GDPR Art. 5"),
    ]
    verdict = HierarchicalPolicyProcessor(active_treatments=treatments).process_single_record(
        "trips",
        {"trip_id": "XX-1", "subject_zone": "XX", "customer_phone": "0123456789"},
    )
    assert verdict.status == "WARNING"
    assert "NO_ACTIVE_PACK" in verdict.applied_policy_ids
    assert [item["policy_id"] for item in verdict.required_treatments] == ["POL-GLOBAL"]


def test_us_default_privacy_treatment_uses_ccpa_only():
    verdict = HierarchicalPolicyProcessor().process_single_record(
        "trips",
        {"trip_id": "US-1", "subject_zone": "US", "customer_phone": "0123456789"},
    )
    assert verdict.status == "PASS"
    assert verdict.treated_record["customer_phone"] == "012*****89"
    assert verdict.required_treatments[0]["policy_id"] == "POL-US-CCPA"
    assert "CCPA" in verdict.required_treatments[0]["law_ref"]
    assert "91/2025" not in verdict.required_treatments[0]["law_ref"]
    assert "GDPR" not in verdict.required_treatments[0]["law_ref"]


def test_eu_financial_failure_uses_global_ifrs_not_privacy_law():
    record = {
        "trip_id": "EU-BAD-FARE",
        "subject_zone": "EU",
        "fare_amount": -10,
        "trip_distance_km": 2,
    }
    verdict = HierarchicalPolicyProcessor().process_single_record("trips", record)

    assert verdict.status == "FAIL"
    assert verdict.violations[0].policy_id == "POL-IFRS-15"
    assert verdict.violations[0].law_ref == "IFRS 15 / SOX 404"
    assert "91/2025" not in verdict.violations[0].law_ref
    assert "GDPR" not in verdict.violations[0].law_ref

    result = VerdictMergerAndRouter().merge_and_route(
        "trips",
        [record],
        {"EU-BAD-FARE": {"status": "PASS", "evidence": []}},
        [verdict],
        run_id="RUN-EU-IFRS",
    )
    quarantine = result.quarantine_records[0]
    assert quarantine["subject_zone"] == "EU"
    assert quarantine["matched_policy_id"] == "POL-IFRS-15"
    assert quarantine["matched_law_ref"] == "IFRS 15 / SOX 404"


def test_reliability_failure_has_no_cross_zone_legal_fallback():
    record = {"trip_id": "EU-SENSOR", "subject_zone": "EU"}
    verdict = HierarchicalPolicyProcessor().process_single_record("trips", record)
    result = VerdictMergerAndRouter().merge_and_route(
        "trips",
        [record],
        {"EU-SENSOR": {"status": "FAIL", "evidence": ["battery_soc > 100"]}},
        [verdict],
        run_id="RUN-EU-SENSOR",
    )
    quarantine = result.quarantine_records[0]
    assert quarantine["subject_zone"] == "EU"
    assert quarantine["matched_law_ref"] is None
    assert quarantine["law_ref"] is None
