from datetime import datetime, timezone
import pandas as pd
from src.reliability.detectors.l1_rules import L1ConstraintDetector


def test_l1_range_violations():
    detector = L1ConstraintDetector()

    now = datetime.now(timezone.utc)
    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001", "VIN-002", "VIN-003"],
        "timestamp": [now, now, now],
        "battery_soc": [95.0, -10.0, 105.0]  # -10.0 and 105.0 are range violations
    })

    signals = detector.detect_range_violations(
        df=df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc",
        min_val=0.0,
        max_val=100.0
    )

    assert len(signals) == 2
    assert signals[0].layer == "L1"
    assert signals[0].signal_type == "RANGE_VIOLATION"
    assert signals[0].severity == "CRITICAL"  # negative value triggers critical


def test_l1_null_violations():
    detector = L1ConstraintDetector()

    now = datetime.now(timezone.utc)
    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001", "VIN-002"],
        "timestamp": [now, now],
        "driver_id": ["DRV-1", None]  # second row has NULL driver_id
    })

    signals = detector.detect_null_violations(
        df=df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        required_cols=["driver_id"]
    )

    assert len(signals) == 1
    assert signals[0].layer == "L1"
    assert signals[0].signal_type == "NULL_VIOLATION"
    assert signals[0].entity_ids == ["VIN-002"]
