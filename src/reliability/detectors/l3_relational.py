from datetime import datetime, timezone
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from src.reliability.models.signal import Signal


class L3RelationalDetector:
    """
    L3 Relational / Collective Detector.
    Detects broken relationships between features where individual variables remain legal.
    """

    def __init__(self, residual_z_threshold: float = 3.0):
        self.residual_z_threshold = residual_z_threshold

    def detect_bivariate_residual_anomalies(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        feature_x: str,
        feature_y: str,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Fits linear relation y = alpha * x + beta per entity (or globally) and checks residual outliers.
        """
        signals: List[Signal] = []

        if df.empty or feature_x not in df.columns or feature_y not in df.columns:
            return signals

        # Clean valid numeric rows
        clean_df = df.dropna(subset=[feature_x, feature_y]).copy()
        clean_df[feature_x] = clean_df[feature_x].astype(float)
        clean_df[feature_y] = clean_df[feature_y].astype(float)

        if len(clean_df) < 5:
            return signals

        x = clean_df[feature_x].values
        y = clean_df[feature_y].values

        # Linear regression slope & intercept
        try:
            poly = np.polyfit(x, y, deg=1)
            slope, intercept = poly[0], poly[1]
        except Exception:
            return signals

        predictions = slope * x + intercept
        residuals = np.abs(y - predictions)

        median_res = np.median(residuals)
        mad_res = np.median(np.abs(residuals - median_res))
        if mad_res == 0:
            mad_res = 1e-6

        z_scores = 0.6745 * (residuals - median_res) / mad_res

        for i, (idx, row) in enumerate(clean_df.iterrows()):
            z = z_scores[i]
            if z >= self.residual_z_threshold:
                event_time = pd.to_datetime(row[timestamp_col]) if timestamp_col in row and pd.notna(row[timestamp_col]) else datetime.now(timezone.utc)
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
                    detector="L3_Regression_Residual",
                    detector_version="1.0.0",
                    evidence_refs=[
                        f"observed_{feature_y}={row[feature_y]}",
                        f"expected_{feature_y}={predictions[i]:.2f}",
                        f"residual={residuals[i]:.2f}"
                    ],
                    provenance=provenance
                )
                signals.append(sig)

        return signals
