from datetime import datetime, timezone
from typing import List, Optional, Tuple, Union
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from src.reliability.models.signal import Signal


class L3RelationalDetector:
    """
    L3 Relational / Collective Detector.
    Detects broken relationships between features where individual variables remain legal.
    Supports both linear regression residuals and IsolationForest comparators, with explicit
    separation of reference (training) and evaluation windows.
    """

    def __init__(
        self,
        residual_z_threshold: float = 3.0,
        comparator: str = "linear_regression",
        contamination: float = 0.05,
        random_state: int = 42
    ):
        self.residual_z_threshold = residual_z_threshold
        self.comparator = comparator
        self.contamination = contamination
        self.random_state = random_state

    def detect_bivariate_residual_anomalies(
        self,
        df: Optional[pd.DataFrame] = None,
        project_id: str = "default_project",
        entity_id_col: str = "entity_id",
        timestamp_col: str = "timestamp",
        feature_x: str = "x",
        feature_y: str = "y",
        ref_df: Optional[pd.DataFrame] = None,
        eval_df: Optional[pd.DataFrame] = None,
        ref_start: Optional[Union[datetime, str]] = None,
        ref_end: Optional[Union[datetime, str]] = None,
        eval_start: Optional[Union[datetime, str]] = None,
        eval_end: Optional[Union[datetime, str]] = None,
        comparator: Optional[str] = None,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Detects relational anomalies by fitting a relationship model (Linear Regression or IsolationForest)
        on a reference/training window and evaluating normalized residuals/scores on an evaluation window.
        """
        signals: List[Signal] = []

        comp_type = (comparator or self.comparator).lower()

        # Resolve Reference Data (ref_data) and Evaluation Data (eval_data)
        if ref_df is not None:
            ref_data = ref_df.copy()
        elif df is not None and not df.empty:
            ref_data = df.copy()
            if timestamp_col in ref_data.columns:
                if ref_start is not None:
                    ref_data = ref_data[pd.to_datetime(ref_data[timestamp_col]) >= pd.to_datetime(ref_start)]
                if ref_end is not None:
                    ref_data = ref_data[pd.to_datetime(ref_data[timestamp_col]) <= pd.to_datetime(ref_end)]
        elif eval_df is not None:
            ref_data = eval_df.copy()
        else:
            return signals

        if eval_df is not None:
            eval_data = eval_df.copy()
        elif df is not None and not df.empty:
            eval_data = df.copy()
            if timestamp_col in eval_data.columns:
                if eval_start is not None:
                    eval_data = eval_data[pd.to_datetime(eval_data[timestamp_col]) >= pd.to_datetime(eval_start)]
                if eval_end is not None:
                    eval_data = eval_data[pd.to_datetime(eval_data[timestamp_col]) <= pd.to_datetime(eval_end)]
        else:
            eval_data = ref_data.copy()

        if ref_data.empty or eval_data.empty:
            return signals

        if feature_x not in ref_data.columns or feature_y not in ref_data.columns:
            return signals
        if feature_x not in eval_data.columns or feature_y not in eval_data.columns:
            return signals

        # Clean valid numeric rows for reference and evaluation windows
        ref_clean = ref_data.dropna(subset=[feature_x, feature_y]).copy()
        ref_clean[feature_x] = ref_clean[feature_x].astype(float)
        ref_clean[feature_y] = ref_clean[feature_y].astype(float)

        eval_clean = eval_data.dropna(subset=[feature_x, feature_y]).copy()
        eval_clean[feature_x] = eval_clean[feature_x].astype(float)
        eval_clean[feature_y] = eval_clean[feature_y].astype(float)

        if len(ref_clean) < 5 or len(eval_clean) == 0:
            return signals

        if comp_type in ["linear_regression", "regression", "linear"]:
            detector_name = "L3_Regression_Residual"
            x_ref = ref_clean[feature_x].values
            y_ref = ref_clean[feature_y].values

            # Fit relationship on reference window
            try:
                poly = np.polyfit(x_ref, y_ref, deg=1)
                slope, intercept = poly[0], poly[1]
            except Exception:
                return signals

            # Calculate baseline residuals on reference window
            ref_preds = slope * x_ref + intercept
            ref_residuals = np.abs(y_ref - ref_preds)

            median_res = np.median(ref_residuals)
            mad_res = np.median(np.abs(ref_residuals - median_res))
            if mad_res < 1e-4:
                mad_res = 1e-4

            # Evaluate residuals on evaluation window using reference relationship & baseline
            x_eval = eval_clean[feature_x].values
            y_eval = eval_clean[feature_y].values
            eval_preds = slope * x_eval + intercept
            eval_residuals = np.abs(y_eval - eval_preds)

            z_scores = 0.6745 * (eval_residuals - median_res) / mad_res

            for i, (idx, row) in enumerate(eval_clean.iterrows()):
                z = z_scores[i]
                if z >= self.residual_z_threshold:
                    event_time = (
                        pd.to_datetime(row[timestamp_col])
                        if timestamp_col in row and pd.notna(row[timestamp_col])
                        else datetime.now(timezone.utc)
                    )
                    if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                        event_time = event_time.tz_localize(timezone.utc)

                    entity_val = str(row[entity_id_col]) if entity_id_col in row else "fleet"

                    sig = Signal(
                        project_id=project_id,
                        entity_ids=[entity_val],
                        layer="L3",
                        signal_type="RELATIONAL_BREAK",
                        metric_or_relationship=f"{feature_y}_vs_{feature_x}",
                        event_time=event_time,
                        window_start=event_time,
                        window_end=event_time,
                        score=round(float(z), 2),
                        severity="HIGH" if z > 4.5 else "MEDIUM",
                        detector=detector_name,
                        detector_version="1.0.0",
                        evidence_refs=[
                            f"observed_{feature_y}={row[feature_y]}",
                            f"expected_{feature_y}={eval_preds[i]:.2f}",
                            f"residual={eval_residuals[i]:.2f}"
                        ],
                        provenance=provenance
                    )
                    signals.append(sig)

        elif comp_type in ["isolation_forest", "iforest", "isolationforest"]:
            detector_name = "L3_Isolation_Forest"
            x_ref = ref_clean[feature_x].values
            y_ref = ref_clean[feature_y].values

            # Fit reference linear relationship residual to enhance relational detection
            try:
                poly = np.polyfit(x_ref, y_ref, deg=1)
                ref_res = y_ref - (poly[0] * x_ref + poly[1])
            except Exception:
                ref_res = np.zeros_like(x_ref)

            x_mean, x_std = x_ref.mean(), (x_ref.std() if x_ref.std() > 0 else 1.0)
            y_mean, y_std = y_ref.mean(), (y_ref.std() if y_ref.std() > 0 else 1.0)

            ref_scaled_x = (x_ref - x_mean) / x_std
            ref_scaled_y = (y_ref - y_mean) / y_std
            ref_X = np.column_stack([ref_scaled_x, ref_scaled_y, ref_res])

            # Fit IsolationForest on reference window
            try:
                model = IsolationForest(
                    contamination=self.contamination,
                    random_state=self.random_state
                )
                model.fit(ref_X)
            except Exception:
                return signals

            # Calculate baseline anomaly scores on reference window
            # -decision_function: higher score = more anomalous
            ref_raw_scores = -model.decision_function(ref_X)
            median_score = np.median(ref_raw_scores)
            mad_score = np.median(np.abs(ref_raw_scores - median_score))
            if mad_score < 1e-4:
                mad_score = 1e-4

            # Evaluate anomaly scores on evaluation window
            x_eval = eval_clean[feature_x].values
            y_eval = eval_clean[feature_y].values
            try:
                eval_res = y_eval - (poly[0] * x_eval + poly[1])
            except Exception:
                eval_res = np.zeros_like(x_eval)

            eval_scaled_x = (x_eval - x_mean) / x_std
            eval_scaled_y = (y_eval - y_mean) / y_std
            eval_X = np.column_stack([eval_scaled_x, eval_scaled_y, eval_res])

            eval_raw_scores = -model.decision_function(eval_X)
            z_scores = 0.6745 * (eval_raw_scores - median_score) / mad_score

            for i, (idx, row) in enumerate(eval_clean.iterrows()):
                z = z_scores[i]
                if z >= self.residual_z_threshold:
                    event_time = (
                        pd.to_datetime(row[timestamp_col])
                        if timestamp_col in row and pd.notna(row[timestamp_col])
                        else datetime.now(timezone.utc)
                    )
                    if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                        event_time = event_time.tz_localize(timezone.utc)

                    entity_val = str(row[entity_id_col]) if entity_id_col in row else "fleet"

                    sig = Signal(
                        project_id=project_id,
                        entity_ids=[entity_val],
                        layer="L3",
                        signal_type="RELATIONAL_BREAK",
                        metric_or_relationship=f"{feature_y}_vs_{feature_x}",
                        event_time=event_time,
                        window_start=event_time,
                        window_end=event_time,
                        score=round(float(z), 2),
                        severity="HIGH" if z > 4.5 else "MEDIUM",
                        detector=detector_name,
                        detector_version="1.0.0",
                        evidence_refs=[
                            f"observed_{feature_x}={row[feature_x]}",
                            f"observed_{feature_y}={row[feature_y]}",
                            f"iforest_raw_score={eval_raw_scores[i]:.4f}",
                            f"z_score={z:.2f}"
                        ],
                        provenance=provenance
                    )
                    signals.append(sig)

        else:
            raise ValueError(
                f"Unsupported comparator: {comp_type}. Must be 'linear_regression' or 'isolation_forest'."
            )

        return signals

