from datetime import datetime, timezone

import pytest

from dags import parallel_evaluation_engine as engine


def test_injected_lane_a_config_changes_range_without_code_change():
    records = [{"record_id": "r1", "battery_soc": 95}]

    permissive = engine.execute_lane_a_detectors(
        "telemetry", records,
        reliability_config={"version": "v1", "ranges": {"battery_soc": {"min": 0, "max": 100}}},
    )
    strict = engine.execute_lane_a_detectors(
        "telemetry", records,
        reliability_config={"version": "v2", "ranges": {"battery_soc": {"min": 0, "max": 90}}},
    )

    assert permissive["r1"]["status"] == "PASS"
    assert strict["r1"]["status"] == "FAIL"
    assert strict["r1"]["rule_snapshot_hash"]
    assert strict["r1"]["rule_snapshot"][0]["source"] == "INJECTED_CONFIG"


def test_snapshot_hash_is_deterministic_and_changes_with_version():
    first = [{"rule_id": "A", "version": 1, "params_json": {"max": 90}}]
    reordered = [{"params_json": {"max": 90}, "version": 1, "rule_id": "A"}]
    changed = [{"rule_id": "A", "version": 2, "params_json": {"max": 90}}]

    assert engine._lane_a_snapshot_hash(first) == engine._lane_a_snapshot_hash(reordered)
    assert engine._lane_a_snapshot_hash(first) != engine._lane_a_snapshot_hash(changed)


def test_compiler_rejects_dynamic_or_unknown_detector():
    with pytest.raises(ValueError, match="Unsupported Lane A detector_id"):
        engine._compile_lane_a_config([{
            "rule_id": "unsafe", "version": 1, "detector_id": "PYTHON_IMPORT",
            "target_fields": ["battery_soc"], "params_json": {"module": "os"},
        }])


def test_compiler_maps_allowlisted_rows_to_fixed_detector_config():
    config = engine._compile_lane_a_config([
        {"rule_id": "range", "version": 3, "detector_id": "RANGE",
         "target_fields": ["battery_temp_c"], "params_json": {"min": -20, "max": 65}},
        {"rule_id": "z", "version": 3, "detector_id": "ROBUST_Z",
         "target_fields": ["battery_temp_c"],
         "params_json": {"z_threshold": 3.5, "baseline_min_samples": 20}},
        {"rule_id": "cp", "version": 3, "detector_id": "CHANGEPOINT",
         "target_fields": ["battery_temp_c"],
         "params_json": {"penalty": 7, "min_segment_len": 4, "attribution_window": 2}},
    ])

    assert config["ranges"]["battery_temp_c"] == {
        "min": -20, "max": 65, "rule_id": "range"
    }
    assert config["l2"]["z_threshold"] == 3.5
    assert config["baseline_min_samples"] == 20
    assert config["l4"] == {"penalty": 7, "min_segment_len": 4, "attribution_window": 2}
    assert config["version"] == "3"


def test_compiler_accepts_seeded_relation_bundle():
    config = engine._compile_lane_a_config([{
        "rule_id": "relations", "version": 1, "detector_id": "RELATION",
        "target_fields": ["duration_mins", "kwh_consumed", "fare_amount", "total_fare"],
        "params_json": {
            "relations": [
                {"x": "duration_mins", "y": "kwh_consumed"},
                {"x": "fare_amount", "y": "total_fare"},
            ],
            "residual_z_threshold": 4.0,
        },
    }])

    assert [(r["x"], r["y"]) for r in config["l3_relations"]] == [
        ("duration_mins", "kwh_consumed"),
        ("fare_amount", "total_fare"),
    ]


def test_compiler_maps_named_arithmetic_and_condition_without_eval():
    config = engine._compile_lane_a_config([
        {"rule_id": "fare", "version": 1, "detector_id": "ARITHMETIC",
         "target_fields": ["total_fare", "fare_amount", "tip_amount"],
         "params_json": {"tolerance": 0.5}},
        {"rule_id": "rpm", "version": 1, "detector_id": "CONDITION",
         "target_fields": ["speed_kmh", "motor_rpm"],
         "params_json": {"condition_id": "ZERO_SPEED_HIGH_RPM", "rpm_max": 10000}},
    ])

    assert config["arithmetic_checks"][0]["sum_fields"] == ["fare_amount", "tip_amount"]
    assert config["arithmetic_checks"][0]["tolerance"] == 0.5
    assert config["condition_checks"][0]["condition_id"] == "ZERO_SPEED_HIGH_RPM"
    assert config["condition_checks"][0]["rpm_max"] == 10000


def test_db_failure_is_explicit_outside_fixture_mode(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("DATATRUST_ALLOW_RULE_FIXTURES", raising=False)
    monkeypatch.setattr(engine, "get_db_connection", lambda: (_ for _ in ()).throw(OSError("offline")))

    with pytest.raises(RuntimeError, match="Lane A rule snapshot load failed"):
        engine.load_active_lane_a_config_from_db("telemetry", datetime.now(timezone.utc))


def test_treatment_db_failure_is_explicit_outside_fixture_mode(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("DATATRUST_ALLOW_RULE_FIXTURES", raising=False)
    monkeypatch.setattr(engine, "get_db_connection", lambda: (_ for _ in ()).throw(OSError("offline")))

    with pytest.raises(RuntimeError, match="Treatment rule snapshot load failed"):
        engine.load_active_treatments_from_db("trips")
