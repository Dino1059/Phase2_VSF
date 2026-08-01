import math
import numpy as np
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

try:
    from sklearn.ensemble import IsolationForest
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class AnomalyDetail(BaseModel):
    metric_name: str
    column: str = ""
    current_value: float
    detector: str
    is_anomaly: bool = True
    severity: str = "medium"
    description: str
    stats: Dict[str, Any] = Field(default_factory=dict)


class DetectionResult(BaseModel):
    detector: str
    is_anomaly: bool
    anomaly_score: float = 0.0
    anomalies_detected: List[AnomalyDetail] = Field(default_factory=list)
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


def _extract_features(profile: Any) -> Dict[str, float]:
    """Extract flat numeric feature dictionary from various Profile representations."""
    features: Dict[str, float] = {}

    if isinstance(profile, dict):
        p_dict = profile
    elif hasattr(profile, "model_dump"):
        p_dict = profile.model_dump()
    elif hasattr(profile, "__dict__"):
        p_dict = profile.__dict__
    else:
        p_dict = {}

    # Extract top-level numeric metrics
    for k in ["row_count", "total_rows", "column_count", "duplicate_count", "total_anomalies", "data_health_score"]:
        if k in p_dict and isinstance(p_dict[k], (int, float)):
            features[k] = float(p_dict[k])

    # Extract column-level numeric metrics
    cols = p_dict.get("columns", [])
    if isinstance(cols, list):
        for col in cols:
            if isinstance(col, dict):
                col_name = col.get("name") or col.get("column_name") or "unknown"
                for field in ["null_count", "null_pct", "null_percentage", "distinct_count", "mean_val", "mean", "anomaly_count"]:
                    if field in col and col[field] is not None and isinstance(col[field], (int, float)):
                        features[f"{col_name}__{field}"] = float(col[field])
    elif isinstance(cols, dict):
        for col_name, col_meta in cols.items():
            if isinstance(col_meta, dict):
                for field in ["null_count", "null_pct", "distinct_count", "mean_val", "anomaly_count"]:
                    if field in col_meta and col_meta[field] is not None and isinstance(col_meta[field], (int, float)):
                        features[f"{col_name}__{field}"] = float(col_meta[field])

    return features


class ZScoreDetector:
    """Statistical Anomaly Detector using Z-Score baseline comparison."""

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold

    def detect(
        self, current_profile: Any, historical_profiles: List[Any], threshold: Optional[float] = None
    ) -> DetectionResult:
        thresh = threshold if threshold is not None else self.threshold
        curr_feats = _extract_features(current_profile)

        if not historical_profiles:
            return DetectionResult(
                detector="ZScoreDetector",
                is_anomaly=False,
                anomaly_score=0.0,
                message="No historical profiles provided for comparison.",
            )

        hist_feats_list = [_extract_features(p) for p in historical_profiles]
        anomalies: List[AnomalyDetail] = []
        scores: List[float] = []

        # Find common numeric features
        all_keys = set(curr_feats.keys())
        for h in hist_feats_list:
            all_keys.intersection_update(h.keys())

        for key in sorted(all_keys):
            curr_val = curr_feats[key]
            hist_vals = [h[key] for h in hist_feats_list]

            mean_val = float(np.mean(hist_vals))
            std_val = float(np.std(hist_vals))

            if std_val == 0:
                z_score = 0.0 if curr_val == mean_val else (5.0 if curr_val > mean_val else -5.0)
            else:
                z_score = float((curr_val - mean_val) / std_val)

            abs_z = abs(z_score)
            scores.append(min(abs_z / thresh, 2.0))

            if abs_z > thresh:
                col_name = key.split("__")[0] if "__" in key else ""
                metric_short = key.split("__")[1] if "__" in key else key
                sev = "critical" if abs_z > (thresh * 1.5) else ("high" if abs_z > (thresh * 1.2) else "medium")

                anomalies.append(
                    AnomalyDetail(
                        metric_name=key,
                        column=col_name,
                        current_value=curr_val,
                        detector="ZScoreDetector",
                        is_anomaly=True,
                        severity=sev,
                        description=(
                            f"Metric '{metric_short}' in column '{col_name or 'dataset'}' has Z-score of {z_score:.2f} "
                            f"(current={curr_val}, hist_mean={mean_val:.2f}, hist_std={std_val:.2f}, threshold={thresh})"
                        ),
                        stats={
                            "z_score": round(z_score, 3),
                            "mean": round(mean_val, 3),
                            "std": round(std_val, 3),
                            "threshold": thresh,
                        },
                    )
                )

        aggregate_score = float(np.mean(scores)) if scores else 0.0
        is_anom = len(anomalies) > 0

        return DetectionResult(
            detector="ZScoreDetector",
            is_anomaly=is_anom,
            anomaly_score=round(min(1.0, aggregate_score / 2.0), 3),
            anomalies_detected=anomalies,
            message=f"ZScoreDetector identified {len(anomalies)} anomalous metrics (threshold={thresh}).",
            details={"total_metrics_evaluated": len(all_keys), "threshold": thresh},
        )


class IQRDetector:
    """Statistical Anomaly Detector using Interquartile Range (IQR) bounds."""

    def __init__(self, factor: float = 1.5):
        self.factor = factor

    def detect(
        self, current_profile: Any, historical_profiles: List[Any], factor: Optional[float] = None
    ) -> DetectionResult:
        fac = factor if factor is not None else self.factor
        curr_feats = _extract_features(current_profile)

        if not historical_profiles:
            return DetectionResult(
                detector="IQRDetector",
                is_anomaly=False,
                anomaly_score=0.0,
                message="No historical profiles provided for comparison.",
            )

        hist_feats_list = [_extract_features(p) for p in historical_profiles]
        anomalies: List[AnomalyDetail] = []

        all_keys = set(curr_feats.keys())
        for h in hist_feats_list:
            all_keys.intersection_update(h.keys())

        for key in sorted(all_keys):
            curr_val = curr_feats[key]
            hist_vals = [h[key] for h in hist_feats_list]

            q25 = float(np.percentile(hist_vals, 25))
            q75 = float(np.percentile(hist_vals, 75))
            iqr = q75 - q25

            lower_bound = q25 - (fac * iqr)
            upper_bound = q75 + (fac * iqr)

            if curr_val < lower_bound or curr_val > upper_bound:
                col_name = key.split("__")[0] if "__" in key else ""
                metric_short = key.split("__")[1] if "__" in key else key
                diff = (curr_val - upper_bound) if curr_val > upper_bound else (lower_bound - curr_val)

                anomalies.append(
                    AnomalyDetail(
                        metric_name=key,
                        column=col_name,
                        current_value=curr_val,
                        detector="IQRDetector",
                        is_anomaly=True,
                        severity="high" if diff > iqr else "medium",
                        description=(
                            f"Metric '{metric_short}' in column '{col_name or 'dataset'}' value {curr_val} is outside "
                            f"IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}] (Q1={q25:.2f}, Q3={q75:.2f}, factor={fac})"
                        ),
                        stats={
                            "q25": round(q25, 3),
                            "q75": round(q75, 3),
                            "iqr": round(iqr, 3),
                            "lower_bound": round(lower_bound, 3),
                            "upper_bound": round(upper_bound, 3),
                        },
                    )
                )

        is_anom = len(anomalies) > 0
        anomaly_score = min(1.0, len(anomalies) / max(1, len(all_keys)))

        return DetectionResult(
            detector="IQRDetector",
            is_anomaly=is_anom,
            anomaly_score=round(anomaly_score, 3),
            anomalies_detected=anomalies,
            message=f"IQRDetector identified {len(anomalies)} anomalous metrics outside IQR bounds (factor={fac}).",
            details={"total_metrics_evaluated": len(all_keys), "factor": fac},
        )


class IsolationForestDetector:
    """Optional ML Upgrade Anomaly Detector active when historical runs > 5."""

    def __init__(self, min_historical_runs: int = 5, contamination: float = 0.1):
        self.min_historical_runs = min_historical_runs
        self.contamination = contamination

    def detect(
        self, current_profile: Any, historical_profiles: List[Any], contamination: Optional[float] = None
    ) -> DetectionResult:
        contam = contamination if contamination is not None else self.contamination
        n_hist = len(historical_profiles) if historical_profiles else 0

        if n_hist <= self.min_historical_runs:
            return DetectionResult(
                detector="IsolationForestDetector",
                is_anomaly=False,
                anomaly_score=0.0,
                message=(
                    f"IsolationForest upgrade inactive: requires > {self.min_historical_runs} historical runs "
                    f"(current historical runs: {n_hist})."
                ),
                details={"historical_runs_count": n_hist, "min_required": self.min_historical_runs + 1},
            )

        if not HAS_SKLEARN:
            return DetectionResult(
                detector="IsolationForestDetector",
                is_anomaly=False,
                anomaly_score=0.0,
                message="scikit-learn is not installed.",
            )

        curr_feats = _extract_features(current_profile)
        hist_feats_list = [_extract_features(p) for p in historical_profiles]

        # Common feature set across historical runs + current run
        common_keys = sorted(list(set(curr_feats.keys())))
        if not common_keys:
            return DetectionResult(
                detector="IsolationForestDetector",
                is_anomaly=False,
                anomaly_score=0.0,
                message="No numeric metrics available for ML vector construction.",
            )

        X_hist = []
        for h in hist_feats_list:
            row_vec = [h.get(k, curr_feats.get(k, 0.0)) for k in common_keys]
            X_hist.append(row_vec)

        X_curr = [[curr_feats[k] for k in common_keys]]

        try:
            clf = IsolationForest(
                n_estimators=100,
                contamination=contam,
                random_state=42,
            )
            clf.fit(X_hist)

            pred = clf.predict(X_curr)[0]  # -1 = anomaly, 1 = normal
            score_sample = float(-clf.score_samples(X_curr)[0])  # higher score = more anomalous

            is_anom = bool(pred == -1)

            # Identify contributing feature anomalies by z-deviation
            anomalies: List[AnomalyDetail] = []
            if is_anom:
                hist_matrix = np.array(X_hist)
                curr_vec = np.array(X_curr[0])
                means = np.mean(hist_matrix, axis=0)
                stds = np.std(hist_matrix, axis=0)

                for idx, k in enumerate(common_keys):
                    std_val = stds[idx] if stds[idx] > 0 else 1.0
                    z = abs((curr_vec[idx] - means[idx]) / std_val)
                    if z > 2.0:
                        col_name = k.split("__")[0] if "__" in k else ""
                        anomalies.append(
                            AnomalyDetail(
                                metric_name=k,
                                column=col_name,
                                current_value=curr_vec[idx],
                                detector="IsolationForestDetector",
                                is_anomaly=True,
                                severity="high" if z > 3.5 else "medium",
                                description=(
                                    f"ML Isolation Forest flagged profile feature '{k}' as an anomaly "
                                    f"(feature z-score={z:.2f})."
                                ),
                                stats={"z_score": round(z, 2), "mean": round(means[idx], 2)},
                            )
                        )

            return DetectionResult(
                detector="IsolationForestDetector",
                is_anomaly=is_anom,
                anomaly_score=round(score_sample, 3),
                anomalies_detected=anomalies,
                message=f"IsolationForest ML detector executed on {n_hist} historical runs. Anomaly = {is_anom}.",
                details={
                    "historical_runs_count": n_hist,
                    "contamination": contam,
                    "raw_score": round(score_sample, 4),
                },
            )
        except Exception as e:
            return DetectionResult(
                detector="IsolationForestDetector",
                is_anomaly=False,
                anomaly_score=0.0,
                message=f"IsolationForest execution error: {e}",
            )


class AnomalyDetector:
    """Unified Anomaly Detector running ZScore, IQR, and optional IsolationForest detectors."""

    def __init__(self, z_threshold: float = 3.0, iqr_factor: float = 1.5, ml_contamination: float = 0.1):
        self.z_detector = ZScoreDetector(threshold=z_threshold)
        self.iqr_detector = IQRDetector(factor=iqr_factor)
        self.ml_detector = IsolationForestDetector(contamination=ml_contamination)

    def detect_all(
        self, current_profile: Any, historical_profiles: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        h_profiles = historical_profiles or []

        z_res = self.z_detector.detect(current_profile, h_profiles)
        iqr_res = self.iqr_detector.detect(current_profile, h_profiles)
        ml_res = self.ml_detector.detect(current_profile, h_profiles)

        is_any_anomaly = z_res.is_anomaly or iqr_res.is_anomaly or ml_res.is_anomaly
        max_score = max(z_res.anomaly_score, iqr_res.anomaly_score, ml_res.anomaly_score)

        all_anomalies = z_res.anomalies_detected + iqr_res.anomalies_detected + ml_res.anomalies_detected

        return {
            "is_anomaly": is_any_anomaly,
            "aggregate_anomaly_score": round(max_score, 3),
            "detectors": {
                "z_score": z_res.model_dump(),
                "iqr": iqr_res.model_dump(),
                "isolation_forest": ml_res.model_dump(),
            },
            "all_anomalies": [a.model_dump() for a in all_anomalies],
            "historical_runs_count": len(h_profiles),
            "summary": (
                f"Anomaly Detection Complete. Flagged = {is_any_anomaly} (Score: {max_score:.2f}). "
                f"Total anomalies: {len(all_anomalies)}."
            ),
        }
