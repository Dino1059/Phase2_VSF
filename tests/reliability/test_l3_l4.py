from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import pytest
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
    assert sig.detector == "L3_Regression_Residual"


def test_l3_reference_vs_evaluation_window_separation():
    detector = L3RelationalDetector(residual_z_threshold=3.0)

    now = datetime.now(timezone.utc)

    # Clean reference window data (10 normal samples)
    ref_distances = [2.0, 5.0, 10.0, 3.0, 8.0, 15.0, 4.0, 7.0, 12.0, 6.0]
    ref_fares = [20000.0 * d for d in ref_distances]
    ref_dates = [now - timedelta(hours=20 - i) for i in range(10)]

    ref_df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 10,
        "timestamp": ref_dates,
        "distance_km": ref_distances,
        "fare_vnd": ref_fares
    })

    # Evaluation window data (5 samples, 1 anomalous)
    eval_distances = [3.5, 9.0, 11.0, 6.0, 14.0]
    eval_fares = [70000.0, 180000.0, 220000.0, 2500000.0, 280000.0]  # 4th sample is anomalous
    eval_dates = [now - timedelta(hours=5 - i) for i in range(5)]

    eval_df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 5,
        "timestamp": eval_dates,
        "distance_km": eval_distances,
        "fare_vnd": eval_fares
    })

    # Fit on ref_df, evaluate on eval_df
    signals = detector.detect_bivariate_residual_anomalies(
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        feature_x="distance_km",
        feature_y="fare_vnd",
        ref_df=ref_df,
        eval_df=eval_df
    )

    assert len(signals) == 1
    sig = signals[0]
    assert sig.layer == "L3"
    assert sig.signal_type == "RELATIONAL_BREAK"
    # Verify the signal timestamp matches the evaluation window event
    assert sig.event_time == eval_dates[3]

    # Test timestamp range filtering window separation
    combined_df = pd.concat([ref_df, eval_df]).reset_index(drop=True)
    signals_ts = detector.detect_bivariate_residual_anomalies(
        df=combined_df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        feature_x="distance_km",
        feature_y="fare_vnd",
        ref_start=ref_dates[0],
        ref_end=ref_dates[-1],
        eval_start=eval_dates[0],
        eval_end=eval_dates[-1]
    )

    assert len(signals_ts) == 1
    assert signals_ts[0].event_time == eval_dates[3]


def test_l3_isolation_forest_comparator():
    detector = L3RelationalDetector(residual_z_threshold=2.5, comparator="isolation_forest", contamination=0.05)

    now = datetime.now(timezone.utc)

    # Reference window: 20 normal samples following y = 20000 * x
    ref_distances = [2.0, 5.0, 10.0, 3.0, 8.0, 15.0, 4.0, 7.0, 12.0, 6.0,
                    9.0, 11.0, 4.5, 7.5, 14.0, 3.5, 8.5, 13.0, 5.5, 10.5]
    ref_fares = [20000.0 * d for d in ref_distances]
    ref_dates = [now - timedelta(hours=30 - i) for i in range(20)]

    ref_df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 20,
        "timestamp": ref_dates,
        "distance_km": ref_distances,
        "fare_vnd": ref_fares
    })

    # Evaluation window: 5 samples with 1 severe relational break
    eval_distances = [4.0, 8.0, 6.0, 12.0, 5.0]
    eval_fares = [80000.0, 160000.0, 3000000.0, 240000.0, 100000.0]  # index 2 is an outlier
    eval_dates = [now - timedelta(hours=5 - i) for i in range(5)]

    eval_df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 5,
        "timestamp": eval_dates,
        "distance_km": eval_distances,
        "fare_vnd": eval_fares
    })

    signals = detector.detect_bivariate_residual_anomalies(
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        feature_x="distance_km",
        feature_y="fare_vnd",
        ref_df=ref_df,
        eval_df=eval_df,
        comparator="isolation_forest"
    )

    assert len(signals) >= 1
    sig = signals[0]
    assert sig.layer == "L3"
    assert sig.signal_type == "RELATIONAL_BREAK"
    assert sig.detector == "L3_Isolation_Forest"
    assert sig.event_time == eval_dates[2]


def test_l4_changepoint_detector():
    detector = L4ChangepointDetector(cusum_threshold=4.0, min_segment_len=3, persistence_window=3)

    # Days 1-5: ~10.0, Days 6-12: ~30.0 (regime shift at index 5)
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

    assert len(signals) == 1
    sig = signals[0]
    assert sig.layer == "L4"
    assert sig.signal_type == "CHANGEPOINT_SHIFT"
    assert sig.metric_or_relationship == "charging_sessions"
    assert sig.event_time == dates[5]

    details = L4ChangepointDetector.parse_signal_details(sig)
    assert details["change_time"] == dates[5]
    assert abs(details["change_magnitude"] - 20.18) < 0.5
    assert details["pre_window_summary"]["count"] == 5
    assert details["post_window_summary"]["count"] == 7
    assert abs(details["pre_window_summary"]["mean"] - 10.02) < 0.2
    assert abs(details["post_window_summary"]["mean"] - 30.20) < 0.5


def test_l4_pelt_detector():
    detector = L4ChangepointDetector(min_segment_len=3, persistence_window=3, pen=3.0)

    now = datetime.now(timezone.utc)
    dates = [now - timedelta(days=i) for i in range(12, 0, -1)]
    vals = [10.0, 10.2, 9.8, 10.1, 10.0, 30.0, 30.5, 31.0, 29.8, 30.2, 30.0, 29.9]

    df = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 12,
        "timestamp": dates,
        "charging_sessions": vals
    })

    signals = detector.detect_pelt_shift(
        df=df,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="charging_sessions"
    )

    assert len(signals) == 1
    sig = signals[0]
    assert sig.layer == "L4"
    assert sig.signal_type == "CHANGEPOINT_PELT"
    assert sig.detector == "L4_PELT_Detector"
    assert sig.event_time == dates[5]

    details = L4ChangepointDetector.parse_signal_details(sig)
    assert details["change_time"] == dates[5]
    assert abs(details["change_magnitude"] - 20.18) < 0.5
    assert details["pre_window_summary"]["count"] == 5
    assert details["post_window_summary"]["count"] == 7


def test_l4_minimum_segment_duration_and_persistence():
    detector = L4ChangepointDetector(cusum_threshold=4.0, min_segment_len=3, persistence_window=3, pen=3.0)

    now = datetime.now(timezone.utc)
    dates = [now - timedelta(days=i) for i in range(12, 0, -1)]
    # Transient spike on day 6 & 7 only (length 2 < persistence_window 3)
    vals_transient = [10.0, 10.1, 9.9, 10.0, 10.2, 50.0, 50.0, 10.0, 9.8, 10.1, 10.0, 10.2]

    df_transient = pd.DataFrame({
        "vehicle_vin": ["VIN-001"] * 12,
        "timestamp": dates,
        "charging_sessions": vals_transient
    })

    cusum_transient = detector.detect_cusum_shift(
        df=df_transient,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="charging_sessions"
    )

    pelt_transient = detector.detect_pelt_shift(
        df=df_transient,
        project_id="proj-test",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="charging_sessions"
    )

    assert len(cusum_transient) == 0
    assert len(pelt_transient) == 0


