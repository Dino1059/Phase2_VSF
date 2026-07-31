import math
import random
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class GroundTruthLabel(BaseModel):
    row_idx: int
    col_name: Optional[str] = None
    error_type: str  # "null", "duplicate", "invalid_format", "outlier_range", "schema_drift", "cross_field"
    severity: str = "medium"  # "low", "medium", "high"
    details: str = ""


class ErrorInjector:
    """Fixed-seed synthetic error injector across 6 error families and 5/10/20% rates."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def _set_seed(self):
        random.seed(self.seed)
        np.random.seed(self.seed)

    def inject_errors(
        self,
        df: pd.DataFrame,
        error_rate: float = 0.10,
        error_families: Optional[List[str]] = None,
    ) -> Tuple[pd.DataFrame, List[GroundTruthLabel]]:
        self._set_seed()
        df_dirty = df.copy()
        labels: List[GroundTruthLabel] = []
        n_rows = len(df_dirty)

        if n_rows == 0:
            return df_dirty, labels

        families = error_families or [
            "null",
            "duplicate",
            "invalid_format",
            "outlier_range",
            "schema_drift",
            "cross_field",
        ]

        target_error_rows = max(1, int(math.ceil(n_rows * error_rate)))
        per_family_count = max(1, target_error_rows // len(families))

        # 1. Null errors
        if "null" in families:
            cols = [c for c in df_dirty.columns if pd.api.types.is_numeric_dtype(df_dirty[c])]
            col = cols[0] if cols else df_dirty.columns[0]
            sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
            for idx in sampled_indices:
                df_dirty.at[idx, col] = None
                labels.append(
                    GroundTruthLabel(
                        row_idx=idx,
                        col_name=col,
                        error_type="null",
                        severity="medium",
                        details=f"Injected null into column '{col}'",
                    )
                )

        # 2. Duplicate errors
        if "duplicate" in families and n_rows > 1:
            sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows // 2))
            dup_rows = []
            for idx in sampled_indices:
                dup_row = df_dirty.iloc[idx].copy()
                dup_rows.append(dup_row)
                labels.append(
                    GroundTruthLabel(
                        row_idx=len(df_dirty) + len(dup_rows) - 1,
                        col_name=None,
                        error_type="duplicate",
                        severity="high",
                        details=f"Injected duplicate of row index {idx}",
                    )
                )
            if dup_rows:
                df_dup = pd.DataFrame(dup_rows)
                df_dirty = pd.concat([df_dirty, df_dup], ignore_index=True)

        n_rows = len(df_dirty)

        # 3. Invalid format errors
        if "invalid_format" in families:
            date_cols = [c for c in df_dirty.columns if "date" in c.lower() or "time" in c.lower()]
            col = date_cols[0] if date_cols else df_dirty.columns[0]
            sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
            for idx in sampled_indices:
                df_dirty.at[idx, col] = "99/99/9999_INVALID"
                labels.append(
                    GroundTruthLabel(
                        row_idx=idx,
                        col_name=col,
                        error_type="invalid_format",
                        severity="medium",
                        details=f"Injected invalid datetime string into column '{col}'",
                    )
                )

        # 4. Outlier / range errors
        if "outlier_range" in families:
            num_cols = [c for c in df_dirty.columns if pd.api.types.is_numeric_dtype(df_dirty[c])]
            col = num_cols[0] if num_cols else None
            if col:
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, col] = 9999999.0
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name=col,
                            error_type="outlier_range",
                            severity="high",
                            details=f"Injected extreme outlier into column '{col}'",
                        )
                    )

        # 5. Schema drift error
        if "schema_drift" in families and len(df_dirty.columns) > 1:
            col_to_drift = df_dirty.columns[-1]
            drifted_col_name = f"{col_to_drift}_drift"
            df_dirty = df_dirty.rename(columns={col_to_drift: drifted_col_name})
            labels.append(
                GroundTruthLabel(
                    row_idx=0,
                    col_name=drifted_col_name,
                    error_type="schema_drift",
                    severity="high",
                    details=f"Renamed column '{col_to_drift}' to '{drifted_col_name}'",
                )
            )

        # 6. Cross-field inconsistency error
        if "cross_field" in families:
            cols = list(df_dirty.columns)
            if "PULocationID" in cols and "DOLocationID" in cols and "trip_miles" in cols:
                sampled_indices = random.sample(range(n_rows), min(per_family_count, n_rows))
                for idx in sampled_indices:
                    df_dirty.at[idx, "PULocationID"] = 100
                    df_dirty.at[idx, "DOLocationID"] = 100
                    df_dirty.at[idx, "trip_miles"] = 25.5
                    labels.append(
                        GroundTruthLabel(
                            row_idx=idx,
                            col_name="PULocationID__DOLocationID",
                            error_type="cross_field",
                            severity="high",
                            details="Injected PULocationID == DOLocationID but trip_miles > 0",
                        )
                    )

        return df_dirty, labels

    def generate_datasets(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        easy_df, easy_labels = self.inject_errors(df, error_rate=0.05)
        medium_df, medium_labels = self.inject_errors(df, error_rate=0.10)
        hard_df, hard_labels = self.inject_errors(df, error_rate=0.20)

        return {
            "easy": {"df": easy_df, "ground_truth": easy_labels, "error_rate": 0.05},
            "medium": {"df": medium_df, "ground_truth": medium_labels, "error_rate": 0.10},
            "hard": {"df": hard_df, "ground_truth": hard_labels, "error_rate": 0.20},
        }
