from datetime import datetime, timezone

from backend.engine.hierarchical_policy_processor import LaneBVerdict
from backend.engine.verdict_merger_and_router import VerdictMergerAndRouter
from dags.parallel_evaluation_engine import compute_rule_snapshot_hash


def test_rule_snapshot_hash_is_deterministic_and_version_sensitive():
    base = [{
        "rule_id": "R-1",
        "version": 1,
        "condition_json": {"operator": "range", "field": "x", "min": 0},
        "jurisdiction": "GLOBAL",
        "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "effective_to": None,
    }]
    assert compute_rule_snapshot_hash(base) == compute_rule_snapshot_hash(list(base))
    changed = [{**base[0], "version": 2}]
    assert compute_rule_snapshot_hash(base) != compute_rule_snapshot_hash(changed)


def test_warning_storage_uses_lane_b_treated_record():
    raw = {
        "trip_id": "T-1",
        "subject_zone": "VN",
        "customer_phone": "0987654321",
        "fare_amount": 10,
    }
    treated = {**raw, "customer_phone": "098*****21"}
    verdict = LaneBVerdict(
        record_id="T-1",
        status="WARNING",
        treated_record=treated,
        raw_record=raw,
        compliance_evidence=["advisory"],
    )
    result = VerdictMergerAndRouter().merge_and_route(
        "trips",
        [raw],
        {"T-1": {"status": "PASS", "signals": [], "evidence": []}},
        [verdict],
        run_id="run-warning-treated",
    )
    assert result.warning_count == 1
    assert result.warning_records[0]["redacted_record_json"]["customer_phone"] == "098*****21"

