from datetime import datetime, timedelta, timezone

import pandas as pd

from src.detectors.detector_suite import L1toL4DetectorSuite


def _signals(result, record_id):
    return result[record_id]["signals"]


def test_versioned_schema_checks_duplicate_type_and_timestamp():
    suite = L1toL4DetectorSuite(reliability_config={
        "version": "2026.10",
        "required_fields": ["vehicle_vin"],
        "field_types": {"battery_soc": "number"},
    })
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    frame = pd.DataFrame([
        {"record_id": "dup", "vehicle_vin": None, "timestamp": "not-a-date", "battery_soc": "bad"},
        {"record_id": "dup", "vehicle_vin": "VIN-1", "timestamp": future.isoformat(), "battery_soc": 80},
    ])

    result = suite.evaluate_records("telemetry", frame)
    kinds = {s.signal_type for s in _signals(result, "dup")}

    assert result["dup"]["status"] == "FAIL"
    assert {"REQUIRED_FIELD", "INVALID_TYPE", "INVALID_TIMESTAMP", "FUTURE_TIMESTAMP", "DUPLICATE_PRIMARY_KEY"} <= kinds
    assert all(s.rule_version == "2026.10" for s in _signals(result, "dup"))


def test_configured_range_has_rule_provenance_and_observed_value():
    suite = L1toL4DetectorSuite(reliability_config={
        "version": "safety-3",
        "ranges": {"battery_soc": {"min": 10, "max": 90}},
    })
    result = suite.evaluate_records("telemetry", pd.DataFrame([
        {"record_id": "r1", "battery_soc": 95},
    ]))
    signal = next(s for s in _signals(result, "r1") if s.signal_type == "RANGE_VIOLATION")

    assert signal.rule_id == "L1.RANGE.battery_soc"
    assert signal.rule_version == "safety-3"
    assert signal.threshold == {"min": 10, "max": 90}
    assert signal.observed_value == "95.0"


def test_l2_checks_every_configured_metric_and_advises_for_short_baseline():
    rows = []
    for i in range(6):
        rows.append({
            "record_id": f"r{i}", "vehicle_vin": "v1", "battery_soc": 50 + i,
            "fare_amount": 100 + i, "timestamp": f"2026-01-01T00:0{i}:00Z",
        })
    suite = L1toL4DetectorSuite(reliability_config={
        "baseline_min_samples": 30,
        "l2_metrics": ["battery_soc", "fare_amount"],
        "l4_metrics": [],
        "l3_relations": [],
    })
    result = suite.evaluate_records("trips", pd.DataFrame(rows))
    advisories = [s for value in result.values() for s in value["signals"] if s.signal_type == "INSUFFICIENT_BASELINE"]

    assert {s.metric_or_relationship for s in advisories} == {"battery_soc", "fare_amount"}
    assert all(value["status"] == "WARNING" for value in result.values())


def test_l2_checks_all_metrics_when_baseline_is_sufficient():
    rows = []
    for i in range(30):
        rows.append({
            "record_id": f"r{i}", "vehicle_vin": "v1", "m1": 100 + (i % 3),
            "m2": 200 + (i % 3), "timestamp": f"2026-01-01T00:{i:02d}:00Z",
        })
    rows[-1]["m1"] = 10000
    rows[-1]["m2"] = 20000
    suite = L1toL4DetectorSuite(reliability_config={
        "ranges": {}, "l2_metrics": ["m1", "m2"], "l3_relations": [], "l4_metrics": [],
    })
    result = suite.evaluate_records("custom", pd.DataFrame(rows))
    metrics = {s.metric_or_relationship for s in _signals(result, "r29") if s.signal_type == "CONTEXTUAL_DRIFT"}

    assert metrics == {"m1", "m2"}


def test_timestamp_freshness_is_configurable_warning():
    old = datetime.now(timezone.utc) - timedelta(days=2)
    suite = L1toL4DetectorSuite(reliability_config={
        "timestamp": {"max_age_seconds": 3600}, "ranges": {},
        "l2_metrics": [], "l3_relations": [], "l4_metrics": [],
    })
    result = suite.evaluate_records("events", pd.DataFrame([
        {"record_id": "old", "timestamp": old.isoformat()},
    ]))

    assert result["old"]["status"] == "WARNING"
    assert any(s.signal_type == "STALE_TIMESTAMP" for s in _signals(result, "old"))


def test_reference_unit_sequence_and_stuck_at_controls_are_configurable():
    suite = L1toL4DetectorSuite(reliability_config={
        "ranges": {}, "l2_metrics": [], "l3_relations": [], "l4_metrics": [],
        "reference_values": {"vehicle_vin": ["VIN-OK"]},
        "unit_fields": {"power_unit": ["kW"]},
        "timestamp": {"max_sequence_gap_seconds": 60, "sequence_entity_field": "vehicle_vin"},
        "stuck_at": {"power_kw": {"min_repeats": 3, "entity_field": "vehicle_vin"}},
    })
    frame = pd.DataFrame([
        {"record_id": "r1", "vehicle_vin": "VIN-BAD", "timestamp": "2026-01-01T00:00:00Z", "power_kw": 7, "power_unit": "W"},
        {"record_id": "r2", "vehicle_vin": "VIN-BAD", "timestamp": "2026-01-01T00:00:30Z", "power_kw": 7, "power_unit": "W"},
        {"record_id": "r3", "vehicle_vin": "VIN-BAD", "timestamp": "2026-01-01T00:03:00Z", "power_kw": 7, "power_unit": "W"},
    ])
    result = suite.evaluate_records("telemetry", frame)
    kinds = {signal.signal_type for value in result.values() for signal in value["signals"]}

    assert {"REFERENTIAL_INTEGRITY", "INVALID_UNIT", "SEQUENCE_GAP", "SENSOR_STUCK_AT"} <= kinds
