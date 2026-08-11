from datetime import datetime, timezone
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from src.reliability.models.signal import Signal


class L4ChangepointDetector:
    """
    L4 Sequential / Change-Point Detector.
    Detects persistent regime shifts in mean or variance over time.
    """

    def __init__(self, cusum_threshold: float = 4.0, drift_allowance: float = 0.5):
        self.cusum_threshold = cusum_threshold
        self.drift_allowance = drift_allowance

    def detect_cusum_shift(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        metric_col: str,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Calculates cumulative sum (CUSUM) to detect persistent level shifts.
        """
        signals: List[Signal] = []

        if df.empty or metric_col not in df.columns:
            return signals

        for entity_id, group in df.groupby(entity_id_col):
            sorted_group = group.sort_values(timestamp_col)
            series = sorted_group[metric_col].astype(float).values

            if len(series) < 10:
                continue

            target_mean = np.mean(series[:5])
            std_dev = np.std(series[:5])
            if std_dev == 0:
                std_dev = 1e-6

            s_pos = 0.0
            s_neg = 0.0

            for i, (idx, row) in enumerate(sorted_group.iterrows()):
                val = float(row[metric_col])
                normalized = (val - target_mean) / std_dev

                s_pos = max(0.0, s_pos + normalized - self.drift_allowance)
                s_neg = max(0.0, s_neg - normalized - self.drift_allowance)

                if s_pos >= self.cusum_threshold or s_neg >= self.cusum_threshold:
                    event_time = pd.to_datetime(row[timestamp_col])
                    if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                        event_time = event_time.tz_localize(timezone.utc)

                    score = max(s_pos, s_neg)
                    sig = Signal(
                        project_id=project_id,
                        entity_ids=[str(entity_id)],
                        layer="L4",
                        signal_type="CHANGEPOINT_SHIFT",
                        metric_or_relationship=metric_col,
                        event_time=event_time,
                        window_start=sorted_group[timestamp_col].min(),
                        window_end=sorted_group[timestamp_col].max(),
                        score=round(float(score), 2),
                        severity="HIGH" if score > 7.0 else "MEDIUM",
                        detector="L4_CUSUM_Detector",
                        detector_version="1.0.0",
                        evidence_refs=[
                            f"baseline_mean={target_mean:.2f}",
                            f"cusum_score={score:.2f}",
                            f"shift_direction={'UP' if s_pos >= self.cusum_threshold else 'DOWN'}"
                        ],
                        provenance=provenance
                    )
                    signals.append(sig)
                    # Reset CUSUM accumulators after alarm to avoid redundant signals for same shift
                    s_pos = 0.0
                    s_neg = 0.0

        return signals
