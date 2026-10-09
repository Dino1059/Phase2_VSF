from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from copy import deepcopy
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

    DEFAULT_CONFIG: Dict[str, Any] = {
        "version": "1.0.0",
        "detector_version": "2.0.0",
        "baseline_min_samples": 30,
        "l2": {"z_threshold": 4.5, "warmup_days": 2, "min_samples": 3},
        "l3": {"residual_z_threshold": 4.0},
        "l4": {"penalty": 3.0, "min_segment_len": 3, "persistence_window": 3, "attribution_window": 5},
        "required_fields": [],
        "field_types": {},
        "reference_values": {},
        "unit_fields": {},
        "stuck_at": {},
        "ranges": {
            "battery_soc": {"min": 0.0, "max": 100.0},
            "battery_temp_c": {"min": -20.0, "max": 65.0},
            "power_kw": {"min": 0.0, "max": 350.0},
            "fare_amount": {"min": 0.000001},
            "trip_distance_km": {"min": 0.1},
        },
        "arithmetic_checks": [
            {"total_field": "total_fare", "sum_fields": ["fare_amount", "tip_amount"], "tolerance": 1.0},
        ],
        "condition_checks": [
            {"condition_id": "ZERO_SPEED_HIGH_RPM", "speed_field": "speed_kmh", "rpm_field": "motor_rpm", "rpm_max": 12000},
        ],
        "l2_metrics": ["battery_soc", "kwh_consumed", "fare_amount"],
        "l3_relations": [
            {"x": "duration_mins", "y": "kwh_consumed"},
            {"x": "duration_mins", "y": "trip_distance_km"},
            {"x": "soc_delta", "y": "kwh_consumed"},
            {"x": "fare_amount", "y": "total_fare"},
        ],
        "l4_metrics": ["battery_temp_c", "battery_soc", "trip_distance_km"],
        "timestamp": {"future_tolerance_seconds": 300, "max_sequence_gap_seconds": None, "sequence_entity_field": None},
    }

    def __init__(self, project_id: str = "datatrust_gsm_pilot", reliability_config: Optional[Dict[str, Any]] = None):
        self.project_id = project_id
        supplied = deepcopy(reliability_config or {})
        replace_configurable = bool(supplied.pop("_replace_configurable", False))
        base = deepcopy(self.DEFAULT_CONFIG)
        if replace_configurable:
            # A database snapshot is authoritative: absent rows must not be
            # silently restored from code defaults.
            base.update({
                "ranges": {}, "required_fields": [], "field_types": {},
                "arithmetic_checks": [], "condition_checks": [],
                "l2_metrics": [], "l3_relations": [], "l4_metrics": [],
            })
        self.reliability_config = self._deep_merge(base, supplied)
        self.l1 = L1ConstraintDetector()
        # Detector implementations are fixed code. Only their validated numeric
        # settings and target fields are supplied by configuration.
        self.l2 = L2ContextualDetector()
        self.l3 = L3RelationalDetector()
        self.l4 = L4ChangepointDetector()

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

        cfg = self._dataset_config(dataset_id)
        l2_cfg = cfg.get("l2", {})
        l3_cfg = cfg.get("l3", {})
        l4_cfg = cfg.get("l4", {})
        self.l2 = L2ContextualDetector(
            z_threshold=float(l2_cfg.get("z_threshold", 4.5)),
            warmup_days=int(l2_cfg.get("warmup_days", 2)),
            min_samples=int(l2_cfg.get("min_samples", 3)),
        )
        self.l3 = L3RelationalDetector(
            residual_z_threshold=float(l3_cfg.get("residual_z_threshold", 4.0))
        )
        self.l4 = L4ChangepointDetector(
            pen=float(l4_cfg.get("penalty", 3.0)),
            min_segment_len=int(l4_cfg.get("min_segment_len", 3)),
            persistence_window=int(l4_cfg.get("persistence_window", 3)),
        )

        # 1. Determine primary key column
        resolved_pk = pk_col
        if not resolved_pk:
            for candidate in ["trip_id", "record_id", "session_id", "customer_id", "driver_id", "feedback_id", "vehicle_vin", "vin", "id"]:
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

        # Validate schema values before numeric detectors so malformed input is
        # a deterministic L1 failure rather than an exception or silent PASS.
        self._run_schema_checks(df, record_signals, resolved_pk, time_col, dataset_id, cfg)
        numeric_df = df.copy()
        if time_col in numeric_df.columns:
            safe_times = pd.to_datetime(numeric_df[time_col], errors="coerce", utc=True)
            numeric_df[time_col] = safe_times.fillna(pd.Timestamp.now(tz="UTC"))
        numeric_fields = set(cfg.get("ranges", {})) | set(cfg.get("l2_metrics", [])) | {
            r[k] for r in cfg.get("l3_relations", []) for k in ("x", "y") if k in r
        }
        for col in numeric_fields:
            if col in numeric_df.columns:
                numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")

        # =========================================================================
        # 1. LANE A - L1: Physical / Sensor / Schema / Ledger Constraints
        # =========================================================================
        # Physical battery bounds
        ranges = cfg.get("ranges", {})
        for field_name, bounds in ranges.items():
            if field_name not in numeric_df.columns:
                continue
            range_sigs = self.l1.detect_range_violations(
                numeric_df, self.project_id, resolved_pk, time_col, field_name,
                min_val=bounds.get("min"), max_val=bounds.get("max"), source_table=dataset_id
            )
            self._tag_signals(
                range_sigs, bounds.get("rule_id") or f"L1.RANGE.{field_name}", cfg, bounds
            )
            self._accumulate_signals(range_sigs, record_signals, df, resolved_pk, resolved_pk)

        # Ledger math uses fixed detector code with declarative field mappings.
        for check in cfg.get("arithmetic_checks", []):
          total_field = check.get("total_field")
          sum_cols = [field for field in check.get("sum_fields", []) if field in df.columns]
          if total_field in df.columns and sum_cols:
            arith_sigs = self.l1.detect_arithmetic_violations(
                df, self.project_id, resolved_pk, time_col,
                total_col=total_field, sum_cols=sum_cols,
                tolerance=float(check.get("tolerance", 1.0)), source_table=dataset_id
            )
            self._tag_signals(arith_sigs, check.get("rule_id", f"L1.ARITHMETIC.{total_field}"), cfg, check)
            self._accumulate_signals(arith_sigs, record_signals, df, resolved_pk, resolved_pk)

        # Named conditions are allowlisted; no expression from the DB is evaluated.
        for check in cfg.get("condition_checks", []):
          speed_field = check.get("speed_field")
          rpm_field = check.get("rpm_field")
          if check.get("condition_id") == "ZERO_SPEED_HIGH_RPM" and speed_field in df.columns and rpm_field in df.columns:
            rpm_max = float(check.get("rpm_max", 12000))
            cond = (pd.to_numeric(df[speed_field], errors="coerce") == 0) & (pd.to_numeric(df[rpm_field], errors="coerce") > rpm_max)
            cond_sigs = self.l1.detect_condition_violations(
                df, self.project_id, resolved_pk, time_col,
                condition_mask=cond, metric_name=f"{speed_field}_vs_{rpm_field}",
                description=f"Impossible physical state: zero vehicle speed while motor RPM > {rpm_max:g}",
                severity="CRITICAL", source_table=dataset_id
            )
            self._tag_signals(cond_sigs, check.get("rule_id", "L1.CONDITION.ZERO_SPEED_HIGH_RPM"), cfg, check)
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
        metric_candidates = [m for m in cfg.get("l2_metrics", []) if m in numeric_df.columns]
        if metric_candidates and entity_col in df.columns and entity_col != resolved_pk:
            entities = df[entity_col].dropna().unique()
            for metric_target in metric_candidates:
              for ent in entities:
                ent_mask = numeric_df[entity_col] == ent
                sub_df = numeric_df[ent_mask]
                valid_count = int(pd.to_numeric(sub_df[metric_target], errors="coerce").notna().sum())
                minimum = int(cfg.get("baseline_min_samples", 30))
                if 5 <= valid_count < minimum:
                    self._add_advisory(sub_df, record_signals, resolved_pk, time_col, dataset_id, metric_target, ent, minimum, cfg)
                elif valid_count >= minimum:
                    vals = pd.to_numeric(sub_df[metric_target], errors="coerce").dropna()
                    med = float(vals.median())
                    mad = float((vals - med).abs().median())
                    if mad > 1e-4:
                        for idx, row in sub_df.iterrows():
                            v = float(row[metric_target]) if pd.notna(row[metric_target]) else None
                            if v is not None:
                                z = 0.6745 * abs(v - med) / mad
                                z_threshold = float(l2_cfg.get("z_threshold", 4.5))
                                if z > z_threshold:
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
                                        evidence_refs=[f"Robust Z-Score ({z:.2f}) > {z_threshold:g} baseline ({metric_target}={v}, median={med:.2f}, MAD={mad:.2f})"],
                                        source_table=dataset_id,
                                        detector_version=cfg.get("detector_version", "2.0.0"),
                                        rule_id=f"L2.ROBUST_Z.{metric_target}", rule_version=cfg["version"],
                                        threshold=z_threshold, observed_value=v
                                    )
                                    record_signals[pk_val].append(sig)

        # =========================================================================
        # 3. LANE A - L3: Bivariate Physical Residual Breaks
        # =========================================================================
        for relation in cfg.get("l3_relations", []):
          feature_x, feature_y = relation.get("x"), relation.get("y")
          if feature_x in numeric_df.columns and feature_y in numeric_df.columns:
            l3_sigs = self.l3.detect_bivariate_residual_anomalies(
                df=numeric_df, project_id=self.project_id, entity_id_col=entity_col,
                timestamp_col=time_col, feature_x=feature_x, feature_y=feature_y,
                source_table=dataset_id
            )
            self._tag_signals(l3_sigs, relation.get("rule_id", f"L3.RELATION.{feature_y}_vs_{feature_x}"), cfg, relation)
            self._accumulate_signals(l3_sigs, record_signals, df, resolved_pk, entity_col)

        # =========================================================================
        # 4. LANE A - L4: Changepoint Shift & Granular Window Attribution
        # =========================================================================
        for changepoint_metric in [m for m in cfg.get("l4_metrics", []) if m in numeric_df.columns]:
          if time_col in numeric_df.columns and len(numeric_df) >= 15:
            l4_signals = self.l4.detect_pelt_shift(
                df=numeric_df, project_id=self.project_id, entity_id_col=entity_col,
                timestamp_col=time_col, metric_col=changepoint_metric, source_table=dataset_id
            )
            self._tag_signals(l4_signals, f"L4.CHANGEPOINT.{changepoint_metric}", cfg, {
                "penalty": float(l4_cfg.get("penalty", 3.0)),
                "min_segment_len": int(l4_cfg.get("min_segment_len", 3)),
                "persistence_window": int(l4_cfg.get("persistence_window", 3)),
            })
            # Map macro changepoint signal down to specific transition window records
            self._map_changepoints_to_records(
                df, l4_signals, record_signals, resolved_pk, time_col,
                window_size=int(l4_cfg.get("attribution_window", 5)),
            )

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

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = L1toL4DetectorSuite._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def _dataset_config(self, dataset_id: str) -> Dict[str, Any]:
        cfg = deepcopy(self.reliability_config)
        datasets = cfg.pop("datasets", {})
        if dataset_id in datasets:
            cfg = self._deep_merge(cfg, datasets[dataset_id])
        return cfg

    def _signal(self, row, pk_col, time_col, dataset_id, signal_type, metric, evidence, cfg, observed=None, severity="HIGH"):
        event_time = pd.to_datetime(row.get(time_col), errors="coerce", utc=True)
        if pd.isna(event_time):
            event_time = datetime.now(timezone.utc)
        return Signal(project_id=self.project_id, entity_ids=[str(row.get(pk_col))], layer="L1",
            signal_type=signal_type, metric_or_relationship=metric, event_time=event_time,
            window_start=event_time, window_end=event_time, score=1.0, severity=severity,
            detector="L1_Configured_Validator", detector_version=cfg.get("detector_version", "2.0.0"),
            rule_id=f"L1.{signal_type}.{metric}", rule_version=cfg["version"],
            observed_value=observed, evidence_refs=[evidence], source_table=dataset_id)

    def _run_schema_checks(self, df, record_signals, pk_col, time_col, dataset_id, cfg):
        required = list(dict.fromkeys([pk_col, *cfg.get("required_fields", [])]))
        for col in required:
            missing_col = col not in df.columns
            for _, row in df.iterrows():
                if missing_col or pd.isna(row.get(col)):
                    sig = self._signal(row, pk_col, time_col, dataset_id, "REQUIRED_FIELD", col,
                        f"Required field '{col}' is missing or NULL", cfg, row.get(col))
                    record_signals.setdefault(str(row.get(pk_col)), []).append(sig)

        numeric_fields = set(cfg.get("ranges", {})) | {k for k, v in cfg.get("field_types", {}).items() if v in ("number", "float", "integer")}
        for col in numeric_fields:
            if col not in df.columns:
                continue
            converted = pd.to_numeric(df[col], errors="coerce")
            for idx in df.index[df[col].notna() & converted.isna()]:
                row = df.loc[idx]
                sig = self._signal(row, pk_col, time_col, dataset_id, "INVALID_TYPE", col,
                    f"Field '{col}' is not parseable as numeric", cfg, str(row[col]))
                record_signals[str(row[pk_col])].append(sig)
            if cfg.get("field_types", {}).get(col) == "integer":
                invalid_int = converted.notna() & (converted % 1 != 0)
                for idx in df.index[invalid_int]:
                    row = df.loc[idx]
                    sig = self._signal(row, pk_col, time_col, dataset_id, "INVALID_TYPE", col,
                        f"Field '{col}' is not an integer", cfg, row[col])
                    record_signals[str(row[pk_col])].append(sig)

        for col, expected in cfg.get("field_types", {}).items():
            if col not in df.columns or expected in ("number", "float", "integer"):
                continue
            for idx, value in df[col].items():
                if pd.isna(value):
                    continue
                valid = ((expected == "string" and isinstance(value, str)) or
                         (expected == "boolean" and isinstance(value, (bool, np.bool_))) or
                         (expected == "datetime" and not pd.isna(pd.to_datetime(value, errors="coerce", utc=True))))
                if not valid:
                    row = df.loc[idx]
                    sig = self._signal(row, pk_col, time_col, dataset_id, "INVALID_TYPE", col,
                        f"Field '{col}' is not parseable as {expected}", cfg, str(value))
                    record_signals[str(row[pk_col])].append(sig)

        for col, allowed_values in cfg.get("reference_values", {}).items():
            if col not in df.columns:
                continue
            allowed = {str(value) for value in allowed_values}
            for idx, value in df[col].items():
                if pd.notna(value) and str(value) not in allowed:
                    row = df.loc[idx]
                    sig = self._signal(row, pk_col, time_col, dataset_id, "REFERENTIAL_INTEGRITY", col,
                        f"Field '{col}' does not reference an approved entity", cfg, str(value))
                    record_signals[str(row[pk_col])].append(sig)

        for col, allowed_units in cfg.get("unit_fields", {}).items():
            if col not in df.columns:
                continue
            allowed = {str(value) for value in allowed_units}
            for idx, value in df[col].items():
                if pd.notna(value) and str(value) not in allowed:
                    row = df.loc[idx]
                    sig = self._signal(row, pk_col, time_col, dataset_id, "INVALID_UNIT", col,
                        f"Unit field '{col}' is outside the configured unit vocabulary", cfg, str(value))
                    record_signals[str(row[pk_col])].append(sig)

        if pk_col in df.columns:
            duplicate_mask = df[pk_col].notna() & df[pk_col].duplicated(keep=False)
            for idx in df.index[duplicate_mask]:
                row = df.loc[idx]
                sig = self._signal(row, pk_col, time_col, dataset_id, "DUPLICATE_PRIMARY_KEY", pk_col,
                    f"Duplicate primary key '{row[pk_col]}'", cfg, str(row[pk_col]))
                record_signals[str(row[pk_col])].append(sig)

        if time_col != "_eval_time" and time_col in df.columns:
            parsed = pd.to_datetime(df[time_col], errors="coerce", utc=True)
            now = pd.Timestamp.now(tz="UTC")
            tolerance = pd.Timedelta(seconds=cfg.get("timestamp", {}).get("future_tolerance_seconds", 300))
            freshness = cfg.get("timestamp", {}).get("max_age_seconds")
            for pos, idx in enumerate(df.index):
                row, ts = df.loc[idx], parsed.iloc[pos]
                if pd.isna(ts):
                    sig = self._signal(row, pk_col, time_col, dataset_id, "INVALID_TIMESTAMP", time_col,
                        f"Timestamp '{row[time_col]}' is invalid", cfg, str(row[time_col]))
                    record_signals[str(row[pk_col])].append(sig)
                elif ts > now + tolerance:
                    sig = self._signal(row, pk_col, time_col, dataset_id, "FUTURE_TIMESTAMP", time_col,
                        f"Timestamp exceeds future tolerance of {tolerance.total_seconds():.0f}s", cfg, ts.isoformat())
                    record_signals[str(row[pk_col])].append(sig)
                elif freshness is not None and ts < now - pd.Timedelta(seconds=float(freshness)):
                    sig = self._signal(row, pk_col, time_col, dataset_id, "STALE_TIMESTAMP", time_col,
                        f"Timestamp exceeds freshness limit of {freshness}s", cfg, ts.isoformat(), severity="MEDIUM")
                    record_signals[str(row[pk_col])].append(sig)

            max_gap = cfg.get("timestamp", {}).get("max_sequence_gap_seconds")
            if max_gap is not None:
                entity_field = cfg.get("timestamp", {}).get("sequence_entity_field")
                groups = df.groupby(entity_field, dropna=False) if entity_field in df.columns else [(None, df)]
                for _, group in groups:
                    ordered = group.assign(_parsed_time=parsed.loc[group.index]).sort_values("_parsed_time")
                    gaps = ordered["_parsed_time"].diff().dt.total_seconds()
                    for idx in ordered.index[gaps > float(max_gap)]:
                        row = df.loc[idx]
                        sig = self._signal(row, pk_col, time_col, dataset_id, "SEQUENCE_GAP", time_col,
                            f"Timestamp gap exceeds {max_gap}s", cfg, float(gaps.loc[idx]), severity="MEDIUM")
                        record_signals[str(row[pk_col])].append(sig)

        for metric, options in cfg.get("stuck_at", {}).items():
            if metric not in df.columns:
                continue
            minimum = int(options.get("min_repeats", 5))
            entity_field = options.get("entity_field")
            groups = df.groupby(entity_field, dropna=False) if entity_field in df.columns else [(None, df)]
            for _, group in groups:
                runs = group[metric].ne(group[metric].shift()).cumsum()
                for _, repeated in group.groupby(runs):
                    if len(repeated) < minimum or repeated[metric].isna().all():
                        continue
                    for idx, row in repeated.iterrows():
                        sig = self._signal(row, pk_col, time_col, dataset_id, "SENSOR_STUCK_AT", metric,
                            f"Sensor value repeated for {len(repeated)} consecutive records", cfg,
                            row[metric], severity="MEDIUM")
                        record_signals[str(row[pk_col])].append(sig)

    def _tag_signals(self, signals, rule_id, cfg, threshold):
        for sig in signals:
            sig.rule_id, sig.rule_version, sig.threshold = rule_id, cfg["version"], threshold
            sig.detector_version = cfg.get("detector_version", "2.0.0")
            if sig.observed_value is None:
                match = next((x for x in sig.evidence_refs if x.startswith("observed_value=")), None)
                sig.observed_value = match.split("=", 1)[1] if match else None

    def _add_advisory(self, sub_df, record_signals, pk_col, time_col, dataset_id, metric, entity, minimum, cfg):
        for _, row in sub_df.iterrows():
            event_time = pd.to_datetime(row.get(time_col), errors="coerce", utc=True)
            if pd.isna(event_time): event_time = datetime.now(timezone.utc)
            sig = Signal(project_id=self.project_id, entity_ids=[str(entity)], layer="L2",
                signal_type="INSUFFICIENT_BASELINE", metric_or_relationship=metric,
                event_time=event_time, window_start=event_time, window_end=event_time, score=0.0,
                severity="LOW", detector="L2_Contextual_Detector", detector_version=cfg.get("detector_version", "2.0.0"),
                rule_id=f"L2.ROBUST_Z.{metric}", rule_version=cfg["version"], threshold={"min_samples": minimum},
                observed_value=row.get(metric), evidence_refs=[f"INSUFFICIENT_BASELINE: {len(sub_df)} valid samples < {minimum}"], source_table=dataset_id)
            record_signals[str(row[pk_col])].append(sig)

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
