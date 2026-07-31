from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.models.schemas import ColumnProfile, Profile, ProfileReport, QualityFlag, RuleSeverity


class Profiler:
    """
    Profiler computes deterministic statistical profiles and metadata for a DataFrame.
    """

    def __init__(self, snapshot_id: str = "snap_001"):
        self.snapshot_id = snapshot_id

    def profile(self, data: pd.DataFrame, snapshot_id: Optional[str] = None) -> Profile:
        snap_id = snapshot_id or self.snapshot_id or "snap_001"
        row_count = len(data)
        duplicate_count = int(data.duplicated().sum()) if not data.empty else 0

        column_profiles: List[ColumnProfile] = []
        candidate_keys: List[str] = []
        quality_flags: List[QualityFlag] = []

        for col in data.columns:
            col_series = data[col]
            null_cnt = int(col_series.isna().sum())
            null_pct = float(null_cnt / row_count) if row_count > 0 else 0.0
            unique_cnt = int(col_series.nunique(dropna=True))
            cardinality = float(unique_cnt / row_count) if row_count > 0 else 0.0

            if unique_cnt == row_count and null_cnt == 0 and row_count > 0:
                candidate_keys.append(col)

            if null_pct > 0.2:
                quality_flags.append(
                    QualityFlag(
                        column=col,
                        flag_type="high_nulls",
                        message=f"Column '{col}' has {null_pct:.1%} null values.",
                        severity=RuleSeverity.WARNING if null_pct < 0.5 else RuleSeverity.ERROR,
                    )
                )

            if unique_cnt == 1 and row_count > 1:
                quality_flags.append(
                    QualityFlag(
                        column=col,
                        flag_type="constant_column",
                        message=f"Column '{col}' has a single constant value.",
                        severity=RuleSeverity.INFO,
                    )
                )

            col_min: Optional[Any] = None
            col_max: Optional[Any] = None
            col_mean: Optional[float] = None
            col_median: Optional[float] = None
            col_std: Optional[float] = None

            if pd.api.types.is_numeric_dtype(col_series):
                non_nulls = col_series.dropna()
                if len(non_nulls) > 0:
                    col_min = float(non_nulls.min()) if not pd.isna(non_nulls.min()) else None
                    col_max = float(non_nulls.max()) if not pd.isna(non_nulls.max()) else None
                    col_mean = float(non_nulls.mean()) if not pd.isna(non_nulls.mean()) else None
                    col_median = float(non_nulls.median()) if not pd.isna(non_nulls.median()) else None
                    col_std = float(non_nulls.std()) if not pd.isna(non_nulls.std()) else None
            elif pd.api.types.is_datetime64_any_dtype(col_series):
                non_nulls = col_series.dropna()
                if len(non_nulls) > 0:
                    col_min = str(non_nulls.min())
                    col_max = str(non_nulls.max())
            else:
                non_nulls = col_series.dropna()
                if len(non_nulls) > 0:
                    try:
                        col_min = str(non_nulls.min())
                        col_max = str(non_nulls.max())
                    except Exception:
                        pass

            top_counts = col_series.value_counts(dropna=False).head(5)
            top_values = [
                {"value": str(val) if not pd.isna(val) else None, "count": int(cnt)}
                for val, cnt in top_counts.items()
            ]

            pattern_summary = f"dtype={col_series.dtype}, unique={unique_cnt}, nulls={null_cnt}"

            column_profiles.append(
                ColumnProfile(
                    name=col,
                    dtype=str(col_series.dtype),
                    null_count=null_cnt,
                    null_pct=null_pct,
                    unique_count=unique_cnt,
                    cardinality=cardinality,
                    min=col_min,
                    max=col_max,
                    mean=col_mean,
                    median=col_median,
                    std=col_std,
                    top_values=top_values,
                    pattern_summary=pattern_summary,
                )
            )

        return Profile(
            snapshot_id=snap_id,
            columns=column_profiles,
            row_count=row_count,
            duplicate_count=duplicate_count,
            cross_field_correlations=[],
            candidate_keys=candidate_keys,
            quality_flags=quality_flags,
        )
