from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
import json
import pandas as pd
import numpy as np
from src.reliability.models.signal import Signal

# Optional import of ruptures for PELT algorithm
try:
    import ruptures as rpt
    HAS_RUPTURES = True
except ImportError:
    HAS_RUPTURES = False


class L4ChangepointDetector:
    """
    L4 Sequential / Change-Point Detector.
    Detects persistent regime shifts in mean or variance over time.
    Supports CUSUM (Cumulative Sum) and PELT (Pruned Exact Linear Time) algorithms.
    Enforces minimum segment duration and persistence policy.
    """

    def __init__(
        self,
        cusum_threshold: float = 4.0,
        drift_allowance: float = 0.5,
        min_segment_len: int = 3,
        persistence_window: int = 3,
        pen: float = 3.0,
    ):
        self.cusum_threshold = cusum_threshold
        self.drift_allowance = drift_allowance
        self.min_segment_len = min_segment_len
        self.persistence_window = persistence_window
        self.pen = pen

    def _summarize_window(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int,
        metric_col: str,
        timestamp_col: str,
    ) -> Dict[str, Any]:
        """Calculates mean, std, median, count, and time range for a segment."""
        sub = df.iloc[start_idx:end_idx]
        vals = sub[metric_col].astype(float).values
        if len(vals) == 0:
            return {
                "mean": 0.0,
                "std": 0.0,
                "median": 0.0,
                "count": 0,
                "window_start": None,
                "window_end": None,
            }

        start_ts = pd.to_datetime(sub[timestamp_col].iloc[0])
        end_ts = pd.to_datetime(sub[timestamp_col].iloc[-1])
        if hasattr(start_ts, 'tzinfo') and start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize(timezone.utc)
        if hasattr(end_ts, 'tzinfo') and end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize(timezone.utc)

        return {
            "mean": round(float(np.mean(vals)), 4),
            "std": round(float(np.std(vals)), 4),
            "median": round(float(np.median(vals)), 4),
            "count": len(vals),
            "window_start": start_ts.isoformat(),
            "window_end": end_ts.isoformat(),
        }

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
        Enforces minimum segment duration and persistence policy.
        """
        signals: List[Signal] = []

        if df.empty or metric_col not in df.columns or entity_id_col not in df.columns:
            return signals

        min_total_len = self.min_segment_len + self.persistence_window

        for entity_id, group in df.groupby(entity_id_col):
            sorted_group = group.sort_values(timestamp_col).reset_index(drop=True)
            series = sorted_group[metric_col].astype(float).values

            if len(series) < min_total_len:
                continue

            # Establish initial baseline statistics
            baseline_len = max(self.min_segment_len, min(5, len(series) // 2))
            target_mean = float(np.mean(series[:baseline_len]))
            std_dev = float(np.std(series[:baseline_len]))
            if std_dev == 0:
                std_dev = 1e-6

            s_pos = 0.0
            s_neg = 0.0
            s_pos_start: Optional[int] = None
            s_neg_start: Optional[int] = None

            for i in range(len(series)):
                val = float(series[i])
                normalized = (val - target_mean) / std_dev

                pos_diff = normalized - self.drift_allowance
                if s_pos == 0.0 and pos_diff > 0:
                    s_pos_start = i
                s_pos = max(0.0, s_pos + pos_diff)
                if s_pos == 0.0:
                    s_pos_start = None

                neg_diff = -normalized - self.drift_allowance
                if s_neg == 0.0 and neg_diff > 0:
                    s_neg_start = i
                s_neg = max(0.0, s_neg + neg_diff)
                if s_neg == 0.0:
                    s_neg_start = None

                score = max(s_pos, s_neg)
                if s_pos >= self.cusum_threshold or s_neg >= self.cusum_threshold:
                    start = s_pos_start if s_pos >= self.cusum_threshold and s_pos_start is not None else (s_neg_start if s_neg_start is not None else i)

                    # Locate exact index of jump starting from accumulator start up to alarm index i
                    change_idx = start
                    for k in range(start, i + 1):
                        z_k = abs((series[k] - target_mean) / std_dev)
                        if z_k >= 2.0:
                            change_idx = k
                            break

                    # 1. Enforce minimum segment duration (pre-window count >= min_segment_len)
                    if change_idx < self.min_segment_len:
                        change_idx = self.min_segment_len

                    # 2. Enforce persistence policy (post-window count >= persistence_window)
                    post_count = len(series) - change_idx
                    if post_count < self.persistence_window:
                        continue

                    # Verify persistence: post-change values remain persistently shifted over persistence_window
                    post_slice = series[change_idx : change_idx + self.persistence_window]
                    is_persistent = False
                    persist_thresh = max(2.0, self.cusum_threshold * 0.5)
                    if s_pos >= self.cusum_threshold and all((y - target_mean) / std_dev >= persist_thresh for y in post_slice):
                        is_persistent = True
                    elif s_neg >= self.cusum_threshold and all((target_mean - y) / std_dev >= persist_thresh for y in post_slice):
                        is_persistent = True

                    if not is_persistent:
                        s_pos = 0.0
                        s_neg = 0.0
                        s_pos_start = None
                        s_neg_start = None
                        continue

                    event_time = pd.to_datetime(sorted_group.iloc[change_idx][timestamp_col])
                    if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                        event_time = event_time.tz_localize(timezone.utc)

                    pre_summary = self._summarize_window(sorted_group, 0, change_idx, metric_col, timestamp_col)
                    post_summary = self._summarize_window(sorted_group, change_idx, len(series), metric_col, timestamp_col)
                    change_magnitude = round(float(post_summary["mean"] - pre_summary["mean"]), 4)

                    window_start = pd.to_datetime(sorted_group[timestamp_col].min())
                    if hasattr(window_start, 'tzinfo') and window_start.tzinfo is None:
                        window_start = window_start.tz_localize(timezone.utc)

                    window_end = pd.to_datetime(sorted_group[timestamp_col].max())
                    if hasattr(window_end, 'tzinfo') and window_end.tzinfo is None:
                        window_end = window_end.tz_localize(timezone.utc)

                    sig = Signal(
                        project_id=project_id,
                        entity_ids=[str(entity_id)],
                        layer="L4",
                        signal_type="CHANGEPOINT_SHIFT",
                        metric_or_relationship=metric_col,
                        event_time=event_time,
                        window_start=window_start,
                        window_end=window_end,
                        score=round(float(score), 2),
                        severity="HIGH" if score > 7.0 or abs(change_magnitude) > 3 * std_dev else "MEDIUM",
                        detector="L4_CUSUM_Detector",
                        detector_version="1.0.0",
                        evidence_refs=[
                            f"change_time={event_time.isoformat()}",
                            f"change_magnitude={change_magnitude:.4f}",
                            f"pre_window_mean={pre_summary['mean']:.4f}",
                            f"pre_window_std={pre_summary['std']:.4f}",
                            f"pre_window_count={pre_summary['count']}",
                            f"post_window_mean={post_summary['mean']:.4f}",
                            f"post_window_std={post_summary['std']:.4f}",
                            f"post_window_count={post_summary['count']}",
                            f"pre_window_summary={json.dumps(pre_summary)}",
                            f"post_window_summary={json.dumps(post_summary)}",
                            f"baseline_mean={target_mean:.2f}",
                            f"cusum_score={score:.2f}",
                            f"shift_direction={'UP' if change_magnitude > 0 else 'DOWN'}"
                        ],
                        provenance=provenance
                    )
                    signals.append(sig)

                    # Reset CUSUM accumulators and update target baseline to new regime
                    s_pos = 0.0
                    s_neg = 0.0
                    s_pos_start = None
                    s_neg_start = None

                    # Update baseline target_mean to new regime to avoid duplicate alarms for same shift
                    new_slice = series[change_idx : min(len(series), change_idx + self.persistence_window)]
                    target_mean = float(np.mean(new_slice))
                    new_std = float(np.std(new_slice))
                    if new_std > 0:
                        std_dev = new_std

        return signals

    def detect_pelt_shift(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        metric_col: str,
        pen: Optional[float] = None,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        PELT (Pruned Exact Linear Time) change-point detector.
        Detects multiple change-points minimizing L2 cost + penalty.
        Enforces minimum segment duration and persistence policy.
        """
        signals: List[Signal] = []

        if df.empty or metric_col not in df.columns or entity_id_col not in df.columns:
            return signals

        pen_val = pen if pen is not None else self.pen
        min_size = self.min_segment_len

        for entity_id, group in df.groupby(entity_id_col):
            sorted_group = group.sort_values(timestamp_col).reset_index(drop=True)
            series = sorted_group[metric_col].astype(float).values
            n = len(series)

            if n < 2 * min_size:
                continue

            if HAS_RUPTURES:
                algo = rpt.Pelt(model="l2", min_size=min_size).fit(series)
                raw_cps = algo.predict(pen=pen_val)
                cps = [cp for cp in raw_cps if 0 < cp < n]
            else:
                cps = self._native_pelt(series, min_size=min_size, pen=pen_val)

            prev_idx = 0
            for idx, change_idx in enumerate(cps):
                next_idx = cps[idx + 1] if idx + 1 < len(cps) else n

                pre_count = change_idx - prev_idx
                post_count = next_idx - change_idx

                # 1. Enforce minimum segment duration
                if pre_count < min_size or post_count < min_size:
                    continue

                if post_count < self.persistence_window:
                    continue

                pre_vals = series[prev_idx:change_idx]
                post_persist = series[change_idx : change_idx + self.persistence_window]

                pre_mean = float(np.mean(pre_vals))
                pre_std = float(np.std(pre_vals))
                if pre_std == 0:
                    pre_std = 1e-6

                # 2. Enforce persistence policy: all points in post_persist must be persistently shifted
                min_shift = max(1.0, 2.0 * pre_std)
                if not all(abs(y - pre_mean) >= min_shift for y in post_persist):
                    continue

                event_time = pd.to_datetime(sorted_group.iloc[change_idx][timestamp_col])
                if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                    event_time = event_time.tz_localize(timezone.utc)

                pre_summary = self._summarize_window(sorted_group, prev_idx, change_idx, metric_col, timestamp_col)
                post_summary = self._summarize_window(sorted_group, change_idx, next_idx, metric_col, timestamp_col)
                change_magnitude = round(float(post_summary["mean"] - pre_summary["mean"]), 4)

                window_start = pd.to_datetime(sorted_group[timestamp_col].min())
                if hasattr(window_start, 'tzinfo') and window_start.tzinfo is None:
                    window_start = window_start.tz_localize(timezone.utc)

                window_end = pd.to_datetime(sorted_group[timestamp_col].max())
                if hasattr(window_end, 'tzinfo') and window_end.tzinfo is None:
                    window_end = window_end.tz_localize(timezone.utc)

                score = round(float(abs(change_magnitude) / pre_std), 2)

                sig = Signal(
                    project_id=project_id,
                    entity_ids=[str(entity_id)],
                    layer="L4",
                    signal_type="CHANGEPOINT_PELT",
                    metric_or_relationship=metric_col,
                    event_time=event_time,
                    window_start=window_start,
                    window_end=window_end,
                    score=score,
                    severity="HIGH" if score > 4.5 or abs(change_magnitude) > 3 * pre_std else "MEDIUM",
                    detector="L4_PELT_Detector",
                    detector_version="1.0.0",
                    evidence_refs=[
                        f"change_time={event_time.isoformat()}",
                        f"change_magnitude={change_magnitude:.4f}",
                        f"pre_window_mean={pre_summary['mean']:.4f}",
                        f"pre_window_std={pre_summary['std']:.4f}",
                        f"pre_window_count={pre_summary['count']}",
                        f"post_window_mean={post_summary['mean']:.4f}",
                        f"post_window_std={post_summary['std']:.4f}",
                        f"post_window_count={post_summary['count']}",
                        f"pre_window_summary={json.dumps(pre_summary)}",
                        f"post_window_summary={json.dumps(post_summary)}",
                        f"pelt_penalty={pen_val}",
                        f"shift_direction={'UP' if change_magnitude > 0 else 'DOWN'}"
                    ],
                    provenance=provenance
                )
                signals.append(sig)
                prev_idx = change_idx

        return signals

    def _native_pelt(self, series: np.ndarray, min_size: int, pen: float) -> List[int]:
        """
        Native PELT (Pruned Exact Linear Time) algorithm implementation using L2 cost.
        Returns list of change-point indices.
        """
        n = len(series)
        if n < 2 * min_size:
            return []

        cum_sum = np.zeros(n + 1)
        cum_sum_sq = np.zeros(n + 1)
        cum_sum[1:] = np.cumsum(series)
        cum_sum_sq[1:] = np.cumsum(series ** 2)

        def cost(s: int, t: int) -> float:
            length = t - s
            if length <= 0:
                return 0.0
            sum_val = cum_sum[t] - cum_sum[s]
            sum_sq_val = cum_sum_sq[t] - cum_sum_sq[s]
            return float(sum_sq_val - (sum_val ** 2) / length)

        F = np.full(n + 1, np.inf)
        F[0] = 0.0
        cp = np.zeros(n + 1, dtype=int)
        R = [0]

        for t in range(min_size, n + 1):
            valid_r = [s for s in R if (t - s) >= min_size]
            if not valid_r:
                if (n - t) >= min_size:
                    R.append(t)
                continue

            costs = [F[s] + cost(s, t) + pen for s in valid_r]
            best_idx = int(np.argmin(costs))
            F[t] = costs[best_idx]
            cp[t] = valid_r[best_idx]

            new_R = [s for s in R if (t - s < min_size) or (F[s] + cost(s, t) <= F[t])]
            if (n - t) >= min_size:
                new_R.append(t)
            R = list(set(new_R))

        curr = n
        changepoints = []
        while curr > 0:
            prev = int(cp[curr])
            if prev > 0:
                changepoints.append(prev)
            curr = prev

        changepoints.reverse()
        return changepoints

    @staticmethod
    def parse_signal_details(signal: Signal) -> Dict[str, Any]:
        """
        Extracts change_time, pre_window_summary, post_window_summary, and change_magnitude from a Signal.
        """
        details: Dict[str, Any] = {}
        for ref in signal.evidence_refs:
            if "=" in ref:
                key, val = ref.split("=", 1)
                if key in ("pre_window_summary", "post_window_summary"):
                    try:
                        details[key] = json.loads(val)
                    except Exception:
                        details[key] = val
                elif key in ("change_magnitude", "pre_window_mean", "post_window_mean", "pre_window_std", "post_window_std", "score", "cusum_score"):
                    try:
                        details[key] = float(val)
                    except Exception:
                        details[key] = val
                elif key in ("pre_window_count", "post_window_count"):
                    try:
                        details[key] = int(val)
                    except Exception:
                        details[key] = val
                else:
                    details[key] = val
        details["change_time"] = signal.event_time
        return details

