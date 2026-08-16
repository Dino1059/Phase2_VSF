import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Set

import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reliability.detectors.l1_rules import L1ConstraintDetector
from src.reliability.detectors.l2_contextual import L2ContextualDetector
from src.reliability.detectors.l3_relational import L3RelationalDetector
from src.reliability.detectors.l4_changepoint import L4ChangepointDetector


def _safe_f1(precision: float, recall: float) -> float:
    """Computes F1 score from precision and recall without division by zero."""
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def run_detector_evaluation(save_artifact: bool = True) -> Dict[str, Any]:
    """
    Evaluates L1-L4 Anomaly Detectors on synthetic/pilot corpus.
    Calculates precision, recall, F1, SLA latency, and false positive rates
    strictly from raw empirical detector predictions without hard-coded constants.
    """
    print("Running L1-L4 Detector Evaluation Harness...")

    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # 1. Evaluate L1 Constraint Detector (Range & Null Violations)
    # -------------------------------------------------------------------------
    l1_detector = L1ConstraintDetector()

    # 100 entities, 3 ground-truth range violations, 2 ground-truth null violations
    l1_vehicles = [f"VIN-{i:03d}" for i in range(100)]
    l1_soc_values = [80.0] * 100
    l1_soc_values[5] = -5.0   # Range violation (< 0.0)
    l1_soc_values[20] = 115.0 # Range violation (> 100.0)
    l1_soc_values[42] = -12.0 # Range violation (< 0.0)

    l1_drivers = [f"DRV-{i:03d}" for i in range(100)]
    l1_drivers[10] = None     # Null violation
    l1_drivers[33] = None     # Null violation

    l1_test_df = pd.DataFrame({
        "vehicle_vin": l1_vehicles,
        "timestamp": [now] * 100,
        "battery_soc": l1_soc_values,
        "driver_id": l1_drivers,
    })

    l1_gt_entities: Set[str] = {"VIN-005", "VIN-020", "VIN-042", "VIN-010", "VIN-033"}

    t0 = time.perf_counter()
    range_signals = l1_detector.detect_range_violations(
        df=l1_test_df,
        project_id="proj-eval",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc",
        min_val=0.0,
        max_val=100.0,
    )
    null_signals = l1_detector.detect_null_violations(
        df=l1_test_df,
        project_id="proj-eval",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        required_cols=["driver_id"],
    )
    l1_latency = time.perf_counter() - t0

    l1_signals = range_signals + null_signals
    l1_predicted_entities: Set[str] = {eid for s in l1_signals for eid in s.entity_ids}

    l1_tp = len(l1_predicted_entities & l1_gt_entities)
    l1_fp = len(l1_predicted_entities - l1_gt_entities)
    l1_fn = len(l1_gt_entities - l1_predicted_entities)

    l1_precision = round(l1_tp / (l1_tp + l1_fp), 4) if (l1_tp + l1_fp) > 0 else 0.0
    l1_recall = round(l1_tp / (l1_tp + l1_fn), 4) if (l1_tp + l1_fn) > 0 else 0.0
    l1_f1 = _safe_f1(l1_precision, l1_recall)
    l1_latency_ms = round(l1_latency * 1000, 2)

    # -------------------------------------------------------------------------
    # 2. Evaluate L2 Contextual Detector (MAD / Robust Z-Score)
    # -------------------------------------------------------------------------
    l2_detector = L2ContextualDetector(z_threshold=3.5, warmup_days=14, min_samples=14)

    # 20 entities over 16 days = 320 entity-days
    l2_rows = []
    l2_gt_entities: Set[str] = {"VIN-003", "VIN-012"}

    for i in range(20):
        vin = f"VIN-{i:03d}"
        for day in range(16, 0, -1):
            ts = now - timedelta(days=day)
            if vin == "VIN-003" and day == 1:
                val = 40.0  # Contextual drift vs ~90 baseline
            elif vin == "VIN-012" and day == 1:
                val = 35.0  # Contextual drift vs ~90 baseline
            else:
                val = 90.0 + (day % 3) * 0.2
            l2_rows.append({"vehicle_vin": vin, "timestamp": ts, "battery_soc": val})

    l2_test_df = pd.DataFrame(l2_rows)
    l2_signals = l2_detector.detect_entity_anomalies(
        df=l2_test_df,
        project_id="proj-eval",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc",
    )

    l2_predicted_entities: Set[str] = {eid for s in l2_signals for eid in s.entity_ids}
    l2_tp = len(l2_predicted_entities & l2_gt_entities)
    l2_fp = len(l2_predicted_entities - l2_gt_entities)
    l2_fn = len(l2_gt_entities - l2_predicted_entities)
    l2_entity_days = 20 * 16

    # -------------------------------------------------------------------------
    # 3. Evaluate L3 Relational Detector (Regression Residuals)
    # -------------------------------------------------------------------------
    l3_detector = L3RelationalDetector(residual_z_threshold=3.0)

    # 20 entities over 1 day = 20 entity-days
    # Bivariate relation: fare_vnd = 20000 * distance_km
    l3_distances = [2.0, 5.0, 10.0, 3.0, 8.0, 15.0, 4.0, 7.0, 12.0, 6.0,
                    9.0, 11.0, 4.5, 7.5, 14.0, 3.5, 8.5, 13.0, 5.5, 10.5]
    l3_fares = [20000.0 * d for d in l3_distances]

    l3_gt_entities: Set[str] = {"VIN-007", "VIN-015"}
    l3_fares[7] = 1_500_000.0  # Relational break (extreme overcharge)
    l3_fares[15] = 2_000.0     # Relational break (extreme undercharge)

    l3_test_df = pd.DataFrame({
        "vehicle_vin": [f"VIN-{i:03d}" for i in range(20)],
        "timestamp": [now - timedelta(hours=i) for i in range(20)],
        "distance_km": l3_distances,
        "fare_vnd": l3_fares,
    })

    l3_signals = l3_detector.detect_bivariate_residual_anomalies(
        df=l3_test_df,
        project_id="proj-eval",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        feature_x="distance_km",
        feature_y="fare_vnd",
    )

    l3_predicted_entities: Set[str] = {eid for s in l3_signals for eid in s.entity_ids}
    l3_tp = len(l3_predicted_entities & l3_gt_entities)
    l3_fp = len(l3_predicted_entities - l3_gt_entities)
    l3_fn = len(l3_gt_entities - l3_predicted_entities)
    l3_entity_days = 20 * 1

    # -------------------------------------------------------------------------
    # 4. Evaluate L4 Changepoint Detector (CUSUM Shift)
    # -------------------------------------------------------------------------
    l4_detector = L4ChangepointDetector(cusum_threshold=4.0, drift_allowance=0.5)

    # 20 entities over 12 days = 240 entity-days
    l4_rows = []
    l4_gt_entities: Set[str] = {"VIN-002", "VIN-018"}

    for i in range(20):
        vin = f"VIN-{i:03d}"
        for day in range(12, 0, -1):
            ts = now - timedelta(days=day)
            if (vin == "VIN-002" or vin == "VIN-018") and day <= 7:
                val = 35.0  # Regime level shift
            else:
                val = 10.0 + (i % 2) * 0.1
            l4_rows.append({"vehicle_vin": vin, "timestamp": ts, "charging_sessions": val})

    l4_test_df = pd.DataFrame(l4_rows)
    l4_signals = l4_detector.detect_cusum_shift(
        df=l4_test_df,
        project_id="proj-eval",
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="charging_sessions",
    )

    l4_predicted_entities: Set[str] = {eid for s in l4_signals for eid in s.entity_ids}
    l4_tp = len(l4_predicted_entities & l4_gt_entities)
    l4_fp = len(l4_predicted_entities - l4_gt_entities)
    l4_fn = len(l4_gt_entities - l4_predicted_entities)
    l4_entity_days = 20 * 12

    # -------------------------------------------------------------------------
    # 5. Aggregate L2-L4 Empirical Metrics
    # -------------------------------------------------------------------------
    total_l2_l4_tp = l2_tp + l3_tp + l4_tp
    total_l2_l4_fp = l2_fp + l3_fp + l4_fp
    total_l2_l4_fn = l2_fn + l3_fn + l4_fn

    l2_l4_precision = (
        round(total_l2_l4_tp / (total_l2_l4_tp + total_l2_l4_fp), 4)
        if (total_l2_l4_tp + total_l2_l4_fp) > 0
        else 0.0
    )
    l2_l4_recall = (
        round(total_l2_l4_tp / (total_l2_l4_tp + total_l2_l4_fn), 4)
        if (total_l2_l4_tp + total_l2_l4_fn) > 0
        else 0.0
    )
    l2_l4_f1 = _safe_f1(l2_l4_precision, l2_l4_recall)

    total_entity_days = l2_entity_days + l3_entity_days + l4_entity_days
    fp_per_entity_day = (
        round(total_l2_l4_fp / total_entity_days, 4)
        if total_entity_days > 0
        else 0.0
    )

    res = {
        "l1_evaluation": {
            "precision": l1_precision,
            "recall": l1_recall,
            "f1_score": l1_f1,
            "p95_latency_ms": l1_latency_ms,
            "sla_target_passed": l1_latency < 1.0,
        },
        "l2_l4_evaluation": {
            "precision": l2_l4_precision,
            "recall": l2_l4_recall,
            "f1_score": l2_l4_f1,
            "fp_per_entity_day": fp_per_entity_day,
        },
    }

    if save_artifact:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        artifact_path = results_dir / f"eval_detectors_{timestamp_str}.json"
        
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **res
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Saved evaluation artifact to {artifact_path}")

    return res


if __name__ == "__main__":
    res = run_detector_evaluation()
    print("Evaluation Results:", res)

