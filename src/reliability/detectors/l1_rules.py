from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd
from src.reliability.models.signal import Signal


class L1ConstraintDetector:
    """
    L1 Point / Constraint Detector.
    Fast-path detection of known invalid states (nulls, range violations, arithmetic mismatches, negative values).
    Target SLA: <1s.
    """

    def detect_range_violations(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        metric_col: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Detects hard range constraint violations (e.g. battery_soc < 0 or > 100).
        """
        signals: List[Signal] = []

        if df.empty or metric_col not in df.columns:
            return signals

        for idx, row in df.iterrows():
            val = float(row[metric_col]) if pd.notna(row[metric_col]) else None

            if val is None:
                continue

            is_violation = False
            reason = ""

            if min_val is not None and val < min_val:
                is_violation = True
                reason = f"{metric_col} ({val}) < min_val ({min_val})"
            elif max_val is not None and val > max_val:
                is_violation = True
                reason = f"{metric_col} ({val}) > max_val ({max_val})"

            if is_violation:
                event_time = pd.to_datetime(row[timestamp_col]) if timestamp_col in row and pd.notna(row[timestamp_col]) else datetime.now(timezone.utc)
                if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                    event_time = event_time.tz_localize(timezone.utc)

                entity_id = str(row[entity_id_col]) if entity_id_col in row else "unknown"

                sig = Signal(
                    project_id=project_id,
                    entity_ids=[entity_id],
                    layer="L1",
                    signal_type="RANGE_VIOLATION",
                    metric_or_relationship=metric_col,
                    event_time=event_time,
                    window_start=event_time,
                    window_end=event_time,
                    score=1.0,
                    severity="CRITICAL" if (min_val is not None and val < 0) else "HIGH",
                    detector="L1_Constraint_Detector",
                    detector_version="1.0.0",
                    evidence_refs=[reason, f"observed_value={val}"],
                    provenance=provenance
                )
                signals.append(sig)

        return signals

    def detect_null_violations(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        required_cols: List[str],
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Detects nullability constraint violations on mandatory columns.
        """
        signals: List[Signal] = []

        if df.empty:
            return signals

        for col in required_cols:
            if col not in df.columns:
                continue

            null_rows = df[df[col].isna()]
            for idx, row in null_rows.iterrows():
                event_time = pd.to_datetime(row[timestamp_col]) if timestamp_col in row and pd.notna(row[timestamp_col]) else datetime.now(timezone.utc)
                if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                    event_time = event_time.tz_localize(timezone.utc)

                entity_id = str(row[entity_id_col]) if entity_id_col in row else "unknown"

                sig = Signal(
                    project_id=project_id,
                    entity_ids=[entity_id],
                    layer="L1",
                    signal_type="NULL_VIOLATION",
                    metric_or_relationship=col,
                    event_time=event_time,
                    window_start=event_time,
                    window_end=event_time,
                    score=1.0,
                    severity="HIGH",
                    detector="L1_Null_Detector",
                    detector_version="1.0.0",
                    evidence_refs=[f"Mandatory column '{col}' is NULL"],
                    provenance=provenance
                )
                signals.append(sig)

        return signals

    def detect_arithmetic_violations(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        total_col: str,
        sum_cols: List[str],
        tolerance: float = 1.0,
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Detects arithmetic ledger violations (e.g. total_fare != fare_amount + tip_amount).
        """
        signals: List[Signal] = []
        if df.empty or total_col not in df.columns or not all(c in df.columns for c in sum_cols):
            return signals

        for idx, row in df.iterrows():
            total_val = float(row[total_col]) if pd.notna(row[total_col]) else None
            sum_val = sum(float(row[c]) if pd.notna(row[c]) else 0.0 for c in sum_cols)

            if total_val is None:
                continue

            diff = abs(total_val - sum_val)
            if diff > tolerance:
                event_time = pd.to_datetime(row[timestamp_col]) if timestamp_col in row and pd.notna(row[timestamp_col]) else datetime.now(timezone.utc)
                if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                    event_time = event_time.tz_localize(timezone.utc)

                entity_id = str(row[entity_id_col]) if entity_id_col in row else "unknown"

                sig = Signal(
                    project_id=project_id,
                    entity_ids=[entity_id],
                    layer="L1",
                    signal_type="ARITHMETIC_VIOLATION",
                    metric_or_relationship=total_col,
                    event_time=event_time,
                    window_start=event_time,
                    window_end=event_time,
                    score=min(10.0, diff / 1000.0) if diff > 10.0 else 1.0,
                    severity="HIGH",
                    detector="L1_Arithmetic_Detector",
                    detector_version="1.0.0",
                    evidence_refs=[
                        f"observed_{total_col}={total_val:,.2f}",
                        f"computed_sum_{'+'.join(sum_cols)}={sum_val:,.2f}",
                        f"discrepancy_delta={diff:,.2f}"
                    ],
                    provenance=provenance
                )
                signals.append(sig)

        return signals

    def detect_condition_violations(
        self,
        df: pd.DataFrame,
        project_id: str,
        entity_id_col: str,
        timestamp_col: str,
        condition_mask: pd.Series,
        metric_name: str,
        description: str,
        severity: str = "HIGH",
        provenance: str = "SEMI_SYNTHETIC"
    ) -> List[Signal]:
        """
        Detects deterministic rule condition violations (e.g. speed_kmh == 0 and motor_rpm > 12000).
        """
        signals: List[Signal] = []
        if df.empty or condition_mask is None or not condition_mask.any():
            return signals

        violation_df = df[condition_mask]
        for idx, row in violation_df.iterrows():
            event_time = pd.to_datetime(row[timestamp_col]) if timestamp_col in row and pd.notna(row[timestamp_col]) else datetime.now(timezone.utc)
            if hasattr(event_time, 'tzinfo') and event_time.tzinfo is None:
                event_time = event_time.tz_localize(timezone.utc)

            entity_id = str(row[entity_id_col]) if entity_id_col in row else "unknown"

            sig = Signal(
                project_id=project_id,
                entity_ids=[entity_id],
                layer="L1",
                signal_type="RANGE_VIOLATION",
                metric_or_relationship=metric_name,
                event_time=event_time,
                window_start=event_time,
                window_end=event_time,
                score=1.0,
                severity=severity,
                detector="L1_Constraint_Detector",
                detector_version="1.0.0",
                evidence_refs=[description],
                provenance=provenance
            )
            signals.append(sig)

        return signals

