from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

from src.reliability.models.signal import Signal
from src.detectors.l1_rules import L1ConstraintDetector
from src.detectors.l2_contextual import L2ContextualDetector
from src.detectors.l3_relational import L3RelationalDetector
from src.detectors.l4_changepoint import L4ChangepointDetector


class L1toL4DetectorSuite:
    """
    Lane A: Comprehensive Data Reliability & Sensor Anomaly Suite.
    Integrates L1 (Physical/Schema/Ledger), L2 (Contextual Drift),
    L3 (Bivariate Residuals), and L4 (Changepoint Shifts with Per-Record Attribution).
    """

    def __init__(self, project_id: str = "datatrust_gsm_pilot"):
        self.project_id = project_id
        self.l1 = L1ConstraintDetector()
        self.l2 = L2ContextualDetector(z_threshold=4.5, warmup_days=2, min_samples=3)
        self.l3 = L3RelationalDetector(residual_z_threshold=4.0)
        self.l4 = L4ChangepointDetector(pen=3.0, min_segment_len=3)

    def evaluate_records(
        self,
        dataset_id: str,
        df: pd.DataFrame,
        pk_col: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Runs L1-L4 detectors across dataframe records.
        Returns mapping:
        record_id -> {
            "status": "PASS" | "WARNING" | "FAIL",
            "signals": [Signal, ...],
            "evidence": [str, ...]
        }
        """
        if df.empty:
            return {}

        # 1. Determine primary key column
        resolved_pk = pk_col
        if not resolved_pk:
            for candidate in ["trip_id", "record_id", "session_id", "customer_id", "driver_id", "feedback_id", "id"]:
                if candidate in df.columns:
                    resolved_pk = candidate
                    break
        if not resolved_pk:
            resolved_pk = "_index"
            df = df.copy()
            df["_index"] = [f"rec_{i}" for i in range(len(df))]

        found_time_col = next((c for c in ["timestamp", "pickup_datetime", "start_time", "created_at", "scenario_date"] if c in df.columns), None)
        if not found_time_col:
            df = df.copy()
            df["_eval_time"] = datetime.now(timezone.utc)
            time_col = "_eval_time"
        else:
            time_col = found_time_col

        entity_col = next((c for c in ["vehicle_vin", "driver_id", "customer_id"] if c in df.columns), resolved_pk)

        record_signals: Dict[str, List[Signal]] = {str(row[resolved_pk]): [] for _, row in df.iterrows()}

        # =========================================================================
        # 1. LANE A - L1: Physical / Sensor / Schema / Ledger Constraints
        # =========================================================================
        # Physical battery bounds
        if "battery_soc" in df.columns:
            soc_sigs = self.l1.detect_range_violations(
                df, self.project_id, resolved_pk, time_col, "battery_soc",
                min_val=0.0, max_val=100.0, source_table=dataset_id
            )
            self._accumulate_signals(soc_sigs, record_signals, df, resolved_pk, resolved_pk)

        if "battery_temp_c" in df.columns:
            # Physical hardware sensor limits
            temp_sigs = self.l1.detect_range_violations(
                df, self.project_id, resolved_pk, time_col, "battery_temp_c",
                min_val=-40.0, max_val=120.0, source_table=dataset_id
            )
            self._accumulate_signals(temp_sigs, record_signals, df, resolved_pk, resolved_pk)

        if "power_kw" in df.columns:
            pwr_sigs = self.l1.detect_range_violations(
                df, self.project_id, resolved_pk, time_col, "power_kw",
                min_val=0.0, source_table=dataset_id
            )
            self._accumulate_signals(pwr_sigs, record_signals, df, resolved_pk, resolved_pk)

        # Ledger Math balance
        if "total_fare" in df.columns and "fare_amount" in df.columns:
            sum_cols = ["fare_amount"]
            if "tip_amount" in df.columns:
                sum_cols.append("tip_amount")
            arith_sigs = self.l1.detect_arithmetic_violations(
                df, self.project_id, resolved_pk, time_col,
                total_col="total_fare", sum_cols=sum_cols, tolerance=1.0, source_table=dataset_id
            )
            self._accumulate_signals(arith_sigs, record_signals, df, resolved_pk, resolved_pk)

        # Impossible physical state: speed == 0 and motor_rpm > 12000
        if "speed_kmh" in df.columns and "motor_rpm" in df.columns:
            cond = (pd.to_numeric(df["speed_kmh"], errors="coerce") == 0) & (pd.to_numeric(df["motor_rpm"], errors="coerce") > 12000)
            cond_sigs = self.l1.detect_condition_violations(
                df, self.project_id, resolved_pk, time_col,
                condition_mask=cond, metric_name="speed_kmh_vs_motor_rpm",
                description="Impossible physical state: zero vehicle speed while motor RPM > 12,000",
                severity="CRITICAL", source_table=dataset_id
            )
            self._accumulate_signals(cond_sigs, record_signals, df, resolved_pk, resolved_pk)

        # Schema invariants: Non-null primary identifiers
        for col in [resolved_pk]:
            if col in df.columns:
                null_sigs = self.l1.detect_null_violations(
                    df, self.project_id, resolved_pk, time_col,
                    required_cols=[col], source_table=dataset_id
                )
                self._accumulate_signals(null_sigs, record_signals, df, resolved_pk, resolved_pk)

        # =========================================================================
        # 2. LANE A - L2: Contextual Outlier Detection (Robust Z-Score)
        # =========================================================================
        metric_candidates = [m for m in ["battery_soc", "kwh_consumed", "fare_amount"] if m in df.columns]
        if metric_candidates and entity_col in df.columns and entity_col != resolved_pk:
            metric_target = metric_candidates[0]
            entities = df[entity_col].dropna().unique()
            for ent in entities:
                ent_mask = df[entity_col] == ent
                sub_df = df[ent_mask]
                if len(sub_df) >= 5:
                    vals = pd.to_numeric(sub_df[metric_target], errors="coerce").dropna()
                    med = float(vals.median())
                    mad = float((vals - med).abs().median())
                    if mad > 1e-4:
                        for idx, row in sub_df.iterrows():
                            v = float(row[metric_target]) if pd.notna(row[metric_target]) else None
                            if v is not None:
                                z = 0.6745 * abs(v - med) / mad
                                if z > 4.5:
                                    pk_val = str(row[resolved_pk])
                                    ev_time = pd.to_datetime(row[time_col]) if time_col in row and pd.notna(row[time_col]) else datetime.now(timezone.utc)
                                    sig = Signal(
                                        project_id=self.project_id,
                                        entity_ids=[str(ent)],
                                        layer="L2",
                                        signal_type="CONTEXTUAL_DRIFT",
                                        metric_or_relationship=metric_target,
                                        event_time=ev_time,
                                        window_start=ev_time,
                                        window_end=ev_time,
                                        score=float(z),
                                        severity="MEDIUM",
                                        detector="L2_Contextual_Detector",
                                        evidence_refs=[f"Robust Z-Score ({z:.2f}) > 4.5 baseline ({metric_target}={v}, median={med:.2f}, MAD={mad:.2f})"],
                                        source_table=dataset_id
                                    )
                                    record_signals[pk_val].append(sig)

        # =========================================================================
        # 3. LANE A - L3: Bivariate Physical Residual Breaks
        # =========================================================================
        if "duration_mins" in df.columns and "kwh_consumed" in df.columns:
            l3_sigs = self.l3.detect_bivariate_residual_anomalies(
                df=df, project_id=self.project_id, entity_id_col=entity_col,
                timestamp_col=time_col, feature_x="duration_mins", feature_y="kwh_consumed",
                source_table=dataset_id
            )
            self._accumulate_signals(l3_sigs, record_signals, df, resolved_pk, entity_col)

        # =========================================================================
        # 4. LANE A - L4: Changepoint Shift & Granular Window Attribution
        # =========================================================================
        changepoint_metric = next((m for m in ["battery_temp_c", "battery_soc", "trip_distance_km"] if m in df.columns), None)
        if changepoint_metric and time_col in df.columns and len(df) >= 15:
            l4_signals = self.l4.detect_pelt_shift(
                df=df, project_id=self.project_id, entity_id_col=entity_col,
                timestamp_col=time_col, metric_col=changepoint_metric, source_table=dataset_id
            )
            # Map macro changepoint signal down to specific transition window records
            self._map_changepoints_to_records(df, l4_signals, record_signals, resolved_pk, time_col, window_size=5)

        # =========================================================================
        # Consolidate Lane A Verdict per Record
        # =========================================================================
        results: Dict[str, Dict[str, Any]] = {}
        for pk_val, sigs in record_signals.items():
            has_fail = any(s.layer == "L1" and s.severity in ["CRITICAL", "HIGH"] for s in sigs)
            has_warning = any(s.layer in ["L2", "L3", "L4"] or s.severity in ["MEDIUM", "LOW", "WARNING"] for s in sigs)

            if has_fail:
                status = "FAIL"
            elif has_warning:
                status = "WARNING"
            else:
                status = "PASS"

            evidence = [ref for s in sigs for ref in s.evidence_refs]
            results[pk_val] = {
                "status": status,
                "signals": sigs,
                "evidence": evidence
            }

        return results

    def _accumulate_signals(
        self,
        signals: List[Signal],
        record_signals: Dict[str, List[Signal]],
        df: pd.DataFrame,
        pk_col: str,
        entity_col: str
    ):
        """Helper to link signals to specific records."""
        for sig in signals:
            for ent_id in sig.entity_ids:
                if ent_id in record_signals:
                    record_signals[ent_id].append(sig)
                else:
                    matching = df[df[entity_col].astype(str) == ent_id]
                    for _, row in matching.iterrows():
                        pk_val = str(row[pk_col])
                        if pk_val in record_signals:
                            record_signals[pk_val].append(sig)

    def _map_changepoints_to_records(
        self,
        df: pd.DataFrame,
        changepoint_signals: List[Signal],
        record_signals: Dict[str, List[Signal]],
        pk_col: str,
        time_col: str,
        window_size: int = 5
    ):
        """
        Maps a macro L4 changepoint signal to individual granular records.
        Records in [t_change, t_change + window_size] receive the L4 WARNING signal.
        """
        if not changepoint_signals or df.empty:
            return

        sorted_df = df.sort_values(time_col).reset_index(drop=True)

        for sig in changepoint_signals:
            t_change = pd.to_datetime(sig.event_time, utc=True)
            # Find index closest to t_change
            times = pd.to_datetime(sorted_df[time_col], utc=True)
            diffs = (times - t_change).abs()
            anchor_idx = int(diffs.idxmin())

            # Transition window: anchor record + subsequent window_size records
            window_indices = range(anchor_idx, min(len(sorted_df), anchor_idx + window_size))
            for widx in window_indices:
                row = sorted_df.iloc[widx]
                pk_val = str(row[pk_col])
                is_anchor = (widx == anchor_idx)
                
                # Clone signal with per-record metadata
                rec_sig = Signal(
                    project_id=sig.project_id,
                    entity_ids=sig.entity_ids,
                    layer="L4",
                    signal_type="CHANGEPOINT_SHIFT",
                    metric_or_relationship=sig.metric_or_relationship,
                    event_time=pd.to_datetime(row[time_col]),
                    window_start=sig.window_start,
                    window_end=sig.window_end,
                    score=sig.score,
                    severity="MEDIUM",
                    detector="L4_Changepoint_Window_Attributor",
                    evidence_refs=[
                        f"{'ANCHOR ' if is_anchor else 'WINDOW '}Observation in changepoint transition window",
                        *sig.evidence_refs
                    ],
                    source_table=sig.source_table
                )
                if pk_val in record_signals:
                    record_signals[pk_val].append(rec_sig)
