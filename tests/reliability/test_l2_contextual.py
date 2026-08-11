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
