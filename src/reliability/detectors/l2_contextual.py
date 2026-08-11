from datetime import datetime, timezone
from typing import List, Optional
import pandas as pd
from src.reliability.models.signal import Signal
from src.reliability.features.entity_features import EntityFeatureBuilder


class L2ContextualDetector:
    """
    L2 Contextual Anomaly Detector.
    Detects observations that are valid globally but abnormal relative to an entity's baseline.
    """

    def __init__(
        self,
        z_threshold: float = 3.5,
        warmup_days: int = 14,
        min_samples: int = 14
    ):
        self.z_threshold = z_threshold
        self.feature_builder = EntityFeatureBuilder(warmup_days=warmup_days, min_samples=min_samples)

    def detect_entity_anomalies(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        metric_col: str,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Evaluates a DataFrame of observations per entity.
        Returns a list of L2 contextual anomaly Signals.
        """
        signals: List[Signal] = []

        if df.empty or metric_col not in df.columns or entity_id_col not in df.columns:
            return signals

        # Process per entity
        for entity_id, group in df.groupby(entity_id_col):
            sorted_group = group.sort_values(timestamp_col)
            series = sorted_group[metric_col].astype(float)

            if len(series) < self.feature_builder.min_samples:
                # Cold start: Insufficient history
                continue

            # Calculate baseline on historical window
            median, mad, is_warmed_up = self.feature_builder.calculate_rolling_stats(series)
            if not is_warmed_up or median is None or mad is None:
                continue

            # Evaluate recent observation
            for idx, row in sorted_group.iterrows():
                val = float(row[metric_col])
                z_score = self.feature_builder.calculate_robust_zscore(val, median, mad)

                if abs(z_score) >= self.z_threshold:
                    event_time = pd.to_datetime(row[timestamp_col])
                    if event_time.tzinfo is None:
                        event_time = event_time.tz_localize(timezone.utc)

                    severity = "CRITICAL" if abs(z_score) > 6.0 else ("HIGH" if abs(z_score) > 4.5 else "MEDIUM")

                    sig = Signal(
                        project_id=project_id,
                        entity_ids=[str(entity_id)],
                        layer="L2",
                        signal_type="CONTEXTUAL_DRIFT",
                        metric_or_relationship=metric_col,
                        event_time=event_time,
                        window_start=sorted_group[timestamp_col].min(),
                        window_end=sorted_group[timestamp_col].max(),
                        score=round(abs(z_score), 2),
                        severity=severity,
                        detector="L2_MAD_Robust_ZScore",
                        detector_version="1.0.0",
                        evidence_refs=[f"median={median:.2f}", f"mad={mad:.2f}", f"z_score={z_score:.2f}"],
                        provenance=provenance
                    )
                    signals.append(sig)

        return signals
