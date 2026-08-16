from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd


class EntityFeatureBuilder:
    """
    Builds rolling historical baselines (median, MAD, z-score) for an entity time-series.
    Enforces a 14-day warm-up period policy before scoring signals.
    """

    def __init__(self, warmup_days: int = 14, min_samples: int = 14):
        self.warmup_days = warmup_days
        self.min_samples = min_samples

    def calculate_rolling_stats(
        self, series: pd.Series
    ) -> Tuple[Optional[float], Optional[float], bool]:
        """
        Calculates rolling median and Median Absolute Deviation (MAD).
        Returns (median, mad, is_warmed_up).
        If history < min_samples, returns (None, None, False).
        """
        clean_series = series.dropna()
        if len(clean_series) < self.min_samples:
            return None, None, False

        median = float(clean_series.median())
        mad = float((clean_series - median).abs().median())
        
        # Ensure MAD is not zero to prevent division by zero in Z-score calculation
        if mad == 0:
            mad = 1e-6

        return median, mad, True

    def calculate_robust_zscore(self, current_val: float, median: float, mad: float) -> float:
        """
        Calculates robust Z-score: 0.6745 * (x - median) / MAD
        """
        if mad == 0 or mad is None:
            return 0.0
        return 0.6745 * (current_val - median) / mad
