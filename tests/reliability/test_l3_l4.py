from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from src.reliability.detectors.l3_relational import L3RelationalDetector
from src.reliability.detectors.l4_changepoint import L4ChangepointDetector


def test_l3_relational_detector():
    detector = L3RelationalDetector(residual_z_threshold=3.0)

    # Normal relation: fare_vnd = 20000 * distance_km
    distances = [2.0, 5.0, 10.0, 3.0, 8.0, 15.0, 4.0, 7.0, 12.0, 6.0]
    fares = [40000.0, 100000.0, 200000.0, 60000.0, 160000.0, 300000.0, 80000.0, 140000.0, 240000.0, 2500000.0] # last one is abnormal residual

    now = datetime.now(timezone.utc)
    dates = [now - timedelta(hours=i) for i in range(10)]

    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 10,
        "timestamp": dates,
        "distance_km": distances,
        "fare_vnd": fares
    })

    signals = detector.detect_bivariate_residual_anomalies(
        df=df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        feature_x="distance_km",
        feature_y="fare_vnd"
    )

    assert len(signals) >= 1
    sig = signals[0]
    assert sig.layer == "L3"
    assert sig.signal_type == "RELATIONAL_BREAK"
    assert "fare_vnd_vs_distance_km" in sig.metric_or_relationship


def test_l4_changepoint_detector():
    detector = L4ChangepointDetector(cusum_threshold=4.0)

    # Days 1-5: ~10.0, Days 6-12: ~30.0 (regime shift)
    now = datetime.now(timezone.utc)
    dates = [now - timedelta(days=i) for i in range(12, 0, -1)]
    vals = [10.0, 10.2, 9.8, 10.1, 10.0, 30.0, 30.5, 31.0, 29.8, 30.2, 30.0, 29.9]

    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 12,
        "timestamp": dates,
        "charging_sessions": vals
    })

    signals = detector.detect_cusum_shift(
        df=df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="charging_sessions"
    )

    assert len(signals) >= 1
    sig = signals[0]
    assert sig.layer == "L4"
    assert sig.signal_type == "CHANGEPOINT_SHIFT"
    assert sig.metric_or_relationship == "charging_sessions"
