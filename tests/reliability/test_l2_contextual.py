from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from src.reliability.features.entity_features import EntityFeatureBuilder
from src.reliability.detectors.l2_contextual import L2ContextualDetector


def test_entity_feature_builder_warmup():
    builder = EntityFeatureBuilder(warmup_days=14, min_samples=14)
    short_series = pd.Series([10.0] * 5)
    med, mad, warmed_up = builder.calculate_rolling_stats(short_series)
    assert not warmed_up
    assert med is None
    assert mad is None

    long_series = pd.Series([10.0] * 20)
    med, mad, warmed_up = builder.calculate_rolling_stats(long_series)
    assert warmed_up
    assert med == 10.0
    assert mad > 0  # Zero mad replaced with 1e-6


def test_l2_contextual_detector():
    detector = L2ContextualDetector(z_threshold=3.5, min_samples=14)

    # Generate 15 normal observations for VIN-001 plus 1 anomalous observation
    now = datetime.now(timezone.utc)
    dates = [now - timedelta(days=i) for i in range(16, 0, -1)]
    soc_vals = [90.0, 91.0, 89.5, 90.2, 91.1, 90.0, 89.8, 90.5, 91.0, 90.1, 89.9, 90.3, 90.7, 90.2, 90.1, 40.0] # 40.0 is an anomaly relative to ~90.0 baseline

    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 16,
        "timestamp": dates,
        "battery_soc": soc_vals
    })

    signals = detector.detect_entity_anomalies(
        df=df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc"
    )

    assert len(signals) >= 1
    sig = signals[0]
    assert sig.layer == "L2"
    assert sig.entity_ids == ["VIN-001"]
    assert sig.metric_or_relationship == "battery_soc"
    assert sig.score >= 3.5


def test_l2_temporal_leakage_regression():
    """
    Verifies that score(entity, day=30) strictly calculates baselines from historical observations
    prior to day 30 and does NOT change when day 31-60 values are modified.
    Also verifies 14-day warm-up policy returning INSUFFICIENT_HISTORY for day < 14.
    """
    detector = L2ContextualDetector(z_threshold=3.5, warmup_days=14, min_samples=14)
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Create 60 days of data for VIN-001
    dates = [start_time + timedelta(days=i) for i in range(60)]
    days = list(range(1, 61))

    # Normal values around 90.0 with minor fluctuations for 60 days
    base_vals = [90.0 + (i % 5) * 0.5 for i in range(60)]

    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 60,
        "timestamp": dates,
        "day": days,
        "battery_soc": base_vals.copy()
    })

    # Warm-up check: Day 10 should return INSUFFICIENT_HISTORY (only 9 prior historical observations < 14)
    score_day_10 = detector.score(df, entity_id="VIN-001", day=10)
    assert score_day_10 == "INSUFFICIENT_HISTORY"

    # Score day 30 before modifying future observations (days 31-60)
    score_day_30_original = detector.score(df, entity_id="VIN-001", day=30)
    assert isinstance(score_day_30_original, float)

    # Modify day 31-60 values significantly
    df_modified = df.copy()
    modified_vals = base_vals.copy()
    for i in range(30, 60):  # indices 30..59 correspond to days 31..60
        modified_vals[i] = 10.0 if i % 2 == 0 else 500.0
    df_modified["battery_soc"] = modified_vals

    # Score day 30 after modifying future values
    score_day_30_modified = detector.score(df_modified, entity_id="VIN-001", day=30)
    assert isinstance(score_day_30_modified, float)

    # Verify ZERO temporal look-ahead leakage
    assert score_day_30_original == score_day_30_modified

