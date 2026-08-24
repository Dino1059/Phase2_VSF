from datetime import datetime, timezone
from typing import List, Optional, Union, Any
import pandas as pd
import numpy as np
from src.reliability.models.signal import Signal
from src.reliability.features.entity_features import EntityFeatureBuilder


class L2ContextualDetector:
    """
    L2 Contextual Anomaly Detector.
    Detects observations that are valid globally but abnormal relative to an entity's baseline.
    Strictly calculates baselines from historical observations occurring strictly prior to timestamp t.
    Enforces a 10-day warm-up policy (returning INSUFFICIENT_HISTORY when history is below 10 days/samples).
    """

    def __init__(
        self,
        z_threshold: float = 3.5,
        warmup_days: int = 10,
        min_samples: int = 10
    ):
        self.z_threshold = z_threshold
        self.feature_builder = EntityFeatureBuilder(warmup_days=warmup_days, min_samples=min_samples)

    def score(
        self,
        df: pd.DataFrame,
        entity_id: str,
        day: Optional[int] = None,
        target_timestamp: Optional[Any] = None,
        entity_id_col: str = "vehicle_vin",
        timestamp_col: str = "timestamp",
        metric_col: str = "battery_soc"
    ) -> Union[float, str]:
        """
        Calculates the robust Z-score for a specific entity observation at day or target_timestamp.
        Strictly calculates baseline from observations occurring strictly prior to timestamp t (zero look-ahead leakage).
        Enforces 14-day warm-up policy (returns 'INSUFFICIENT_HISTORY' when historical observations are below 14 days/samples).
        """
        if df.empty or entity_id_col not in df.columns or metric_col not in df.columns:
            return "INSUFFICIENT_HISTORY"

        entity_df = df[df[entity_id_col] == entity_id].copy()
        if entity_df.empty:
            return "INSUFFICIENT_HISTORY"

        if timestamp_col in entity_df.columns:
            entity_df = entity_df.sort_values(timestamp_col)

        target_row = None
        if day is not None:
            if "day" in entity_df.columns:
                match_df = entity_df[entity_df["day"] == day]
                if not match_df.empty:
                    target_row = match_df.iloc[0]
            elif timestamp_col in entity_df.columns and pd.api.types.is_numeric_dtype(entity_df[timestamp_col]):
                match_df = entity_df[entity_df[timestamp_col] == day]
                if not match_df.empty:
                    target_row = match_df.iloc[0]

            if target_row is None and timestamp_col in entity_df.columns:
                ts_series = pd.to_datetime(entity_df[timestamp_col], errors="coerce")
                if not ts_series.isna().all():
                    min_ts = ts_series.min()
                    day_offsets = (ts_series - min_ts).dt.days + 1
                    match_df = entity_df[day_offsets == day]
                    if not match_df.empty:
                        target_row = match_df.iloc[0]

            if target_row is None and len(entity_df) >= day:
                target_row = entity_df.iloc[day - 1]
        elif target_timestamp is not None:
            if timestamp_col in entity_df.columns:
                match_df = entity_df[entity_df[timestamp_col] == target_timestamp]
                if match_df.empty:
                    ts_target = pd.to_datetime(target_timestamp)
                    match_df = entity_df[pd.to_datetime(entity_df[timestamp_col]) == ts_target]
                if not match_df.empty:
                    target_row = match_df.iloc[0]
        else:
            target_row = entity_df.iloc[-1]

        if target_row is None:
            return "INSUFFICIENT_HISTORY"

        if timestamp_col in target_row and pd.notna(target_row[timestamp_col]):
            t = target_row[timestamp_col]
            history_df = entity_df[entity_df[timestamp_col] < t]
        elif "day" in target_row:
            d = target_row["day"]
            history_df = entity_df[entity_df["day"] < d]
        else:
            target_idx = entity_df.index.get_loc(target_row.name) if target_row.name in entity_df.index else 0
            history_df = entity_df.iloc[:target_idx]

        history_series = history_df[metric_col].dropna().astype(float)
        warmup_limit = max(self.feature_builder.min_samples, self.feature_builder.warmup_days)
        if len(history_series) < warmup_limit:
            return "INSUFFICIENT_HISTORY"

        median, mad, is_warmed_up = self.feature_builder.calculate_rolling_stats(history_series)
        if not is_warmed_up or median is None or mad is None:
            return "INSUFFICIENT_HISTORY"

        val = float(target_row[metric_col])
        z_score = self.feature_builder.calculate_robust_zscore(val, median, mad)
        return float(z_score)

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
        Calculates baselines strictly from historical observations strictly prior to timestamp t.
        """
        signals: List[Signal] = []

        if df.empty or metric_col not in df.columns or entity_id_col not in df.columns:
            return signals

        warmup_limit = max(self.feature_builder.min_samples, self.feature_builder.warmup_days)

        # Process per entity with numpy vectorized history search & caching
        for entity_id, group in df.groupby(entity_id_col):
            sorted_group = group.sort_values(timestamp_col).reset_index(drop=True)
            ts_series = pd.to_datetime(sorted_group[timestamp_col])
            ts_values = ts_series.values
            vals = sorted_group[metric_col].astype(float).values

            last_pos = -1
            last_median = None
            last_mad = None

            for i in range(len(sorted_group)):
                t_raw = sorted_group.at[i, timestamp_col]
                t_val = ts_values[i]
                val = float(vals[i])
                if np.isnan(val):
                    continue

                # Fast binary search for index of observations strictly prior to timestamp t
                pos = int(np.searchsorted(ts_values, t_val, side='left'))
                if pos < warmup_limit:
                    continue

                if pos == last_pos:
                    median, mad = last_median, last_mad
                else:
                    history = vals[:pos]
                    history = history[~np.isnan(history)]
                    if len(history) < warmup_limit:
                        continue
                    median = float(np.median(history))
                    mad = float(np.median(np.abs(history - median)))
                    last_pos, last_median, last_mad = pos, median, mad

                if median is None or mad is None:
                    continue

                z_score = self.feature_builder.calculate_robust_zscore(val, median, mad)

                if abs(z_score) >= self.z_threshold:
                    event_time = pd.to_datetime(t_raw)
                    if getattr(event_time, 'tzinfo', None) is None:
                        event_time = event_time.tz_localize(timezone.utc)

                    severity = "CRITICAL" if abs(z_score) > 6.0 else ("HIGH" if abs(z_score) > 4.5 else "MEDIUM")

                    win_start = pd.to_datetime(ts_series.iloc[0])
                    if getattr(win_start, 'tzinfo', None) is None:
                        win_start = win_start.tz_localize(timezone.utc)

                    sig = Signal(
                        project_id=project_id,
                        entity_ids=[str(entity_id)],
                        layer="L2",
                        signal_type="CONTEXTUAL_DRIFT",
                        metric_or_relationship=metric_col,
                        event_time=event_time,
                        window_start=win_start,
                        window_end=event_time,
                        score=round(abs(z_score), 2),
                        severity=severity,
                        detector="L2_MAD_Robust_ZScore",
                        detector_version="1.0.0",
                        evidence_refs=[f"median={median:.2f}", f"mad={mad:.2f}", f"z_score={z_score:.2f}"],
                        provenance=provenance
                    )
                    signals.append(sig)

        return signals


def score(
    df: pd.DataFrame,
    entity_id: str,
    day: Optional[int] = None,
    target_timestamp: Optional[Any] = None,
    entity_id_col: str = "vehicle_vin",
    timestamp_col: str = "timestamp",
    metric_col: str = "battery_soc",
    z_threshold: float = 3.5,
    warmup_days: int = 10,
    min_samples: int = 10
) -> Union[float, str]:
    """
    Module-level score function for scoring an entity observation at day or target_timestamp.
    """
    detector = L2ContextualDetector(z_threshold=z_threshold, warmup_days=warmup_days, min_samples=min_samples)
    return detector.score(
        df=df,
        entity_id=entity_id,
        day=day,
        target_timestamp=target_timestamp,
        entity_id_col=entity_id_col,
        timestamp_col=timestamp_col,
        metric_col=metric_col
    )

