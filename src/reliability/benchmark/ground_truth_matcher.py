"""
Ground-Truth Matching Engine.
Compares detected Signals/Incidents from the E2E Anomaly Pipeline against fault_manifest.json
to calculate deterministic empirical Precision, Recall, F1, True Positives, False Positives, and False Negatives.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple, Optional
from datetime import datetime, timezone
import pandas as pd

from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident


DATASET_TO_TABLE = {
    "synthetic_ev_telemetry_ved_ref": ["vinfast_bms", "vgreen_telemetry"],
    "acn_charging_mapped": ["vgreen_charging_sessions"],
    "ride_hailing_xanh_sm_trips": ["xanhsm_trips"],
    "nlp_benchmark_uit_vsfc": ["xanhsm_feedback"],
    # Ngan landing / canonical warehouse
    "ev_telemetry": ["ev_telemetry"],
    "acn_charging": ["acn_charging", "charging_sessions"],
    "ride_trips": ["ride_trips", "trips"],
    "charging_sessions": ["charging_sessions", "acn_charging"],
    "trips": ["trips", "ride_trips"],
}

TABLE_TO_DATASET = {
    "vinfast_bms": "synthetic_ev_telemetry_ved_ref",
    "vgreen_telemetry": "synthetic_ev_telemetry_ved_ref",
    "vgreen_charging_sessions": "acn_charging_mapped",
    "xanhsm_trips": "ride_hailing_xanh_sm_trips",
    "xanhsm_feedback": "nlp_benchmark_uit_vsfc",
    "ev_telemetry": "ev_telemetry",
    "acn_charging": "acn_charging",
    "charging_sessions": "acn_charging",
    "ride_trips": "ride_trips",
    "trips": "ride_trips",
}


class GroundTruthMatcher:
    """
    Evaluates detector performance against injected ground-truth fault manifest.
    """

    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path).resolve()
        self.manifest_data = self._load_manifest()
        self.faults = self._normalize_faults(self.manifest_data)

    def _load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Fault manifest not found at: {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _normalize_faults(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Accept legacy `faults[]` or Ngan `incidents[]` (table + row_index + day_idx)."""
        raw = data.get("faults") or data.get("incidents") or []
        out: List[Dict[str, Any]] = []
        for f in raw:
            item = dict(f)
            item["original_index"] = item.get("original_index", item.get("row_index"))
            item["dataset"] = item.get("dataset") or item.get("dataset_table")
            item["affected_vin"] = item.get("affected_vin") or item.get("entity_id")
            out.append(item)
        return out

    def evaluate_signals(
        self,
        signals: Dict[str, List[Signal]],
        dfs: Dict[str, pd.DataFrame],
    ) -> Dict[str, Any]:
        """
        Matches detected signals with ground-truth faults.
        Calculates TP, FP, FN, Precision, Recall, F1 per fault family and overall.
        """
        # Flatten signals
        all_signals: List[Signal] = []
        for layer, sig_list in signals.items():
            all_signals.extend(sig_list)

        # Index ground-truth faults by family
        gt_by_family: Dict[str, List[Dict[str, Any]]] = {}
        for f in self.faults:
            fam = f.get("fault_family", "UNKNOWN")
            gt_by_family.setdefault(fam, []).append(f)

        # Classify detected signals by fault family / detector
        family_results: Dict[str, Dict[str, Any]] = {}
        
        # Build index lookups from dfs for row_index mapping
        df_index_lookup: Dict[str, pd.DataFrame] = {}
        for tbl, df in dfs.items():
            if not df.empty:
                df_copy = df.copy().reset_index(drop=True)
                df_index_lookup[tbl] = df_copy

        # Ground truth matching logic per family
        for fam, fault_list in gt_by_family.items():
            total_gt = len(fault_list)
            first_fault = fault_list[0]
            layer = first_fault.get("layer", "L1")
            dataset = first_fault.get("dataset", "")
            target_tables = DATASET_TO_TABLE.get(dataset, [dataset])

            # Extract matching signals for this fault family
            matching_signals = self._get_matching_signals_for_family(fam, all_signals, layer)
            
            # Match True Positives (TP)
            tp_count = 0
            matched_fault_indices: Set[int] = set()

            for f_idx, fault in enumerate(fault_list):
                orig_idx = fault.get("original_index")
                col = fault.get("column", "")

                # Check if any signal matches this fault
                for sig in matching_signals:
                    if self._is_signal_matching_fault(sig, fault, df_index_lookup, target_tables):
                        matched_fault_indices.add(f_idx)
                        break

            tp_count = len(matched_fault_indices)
            fn_count = total_gt - tp_count
            total_detected_signals = len(matching_signals)
            fp_count = max(0, total_detected_signals - tp_count)

            precision = round(tp_count / (tp_count + fp_count), 4) if (tp_count + fp_count) > 0 else 0.0
            recall = round(tp_count / total_gt, 4) if total_gt > 0 else 0.0
            f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

            family_results[fam] = {
                "fault_family": fam,
                "layer": layer,
                "dataset": dataset,
                "ground_truth_total": total_gt,
                "detected_signals_count": total_detected_signals,
                "true_positives": tp_count,
                "false_positives": fp_count,
                "false_negatives": fn_count,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }

        # Overall summary based on total unique emitted signals
        total_gt_all = sum(res["ground_truth_total"] for res in family_results.values())
        total_tp_all = sum(res["true_positives"] for res in family_results.values())
        total_signals_count = len(all_signals)
        total_fp_all = max(0, total_signals_count - total_tp_all)
        total_fn_all = max(0, total_gt_all - total_tp_all)
        
        overall_precision = round(total_tp_all / total_signals_count, 4) if total_signals_count > 0 else 0.0
        overall_recall = round(total_tp_all / total_gt_all, 4) if total_gt_all > 0 else 0.0
        overall_f1 = round(2 * overall_precision * overall_recall / (overall_precision + overall_recall), 4) if (overall_precision + overall_recall) > 0 else 0.0

        return {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "manifest_path": str(self.manifest_path),
            "total_ground_truth_faults": total_gt_all,
            "overall_metrics": {
                "total_ground_truth": total_gt_all,
                "total_emitted_signals": total_signals_count,
                "true_positives": total_tp_all,
                "false_positives": total_fp_all,
                "false_negatives": total_fn_all,
                "precision": overall_precision,
                "recall": overall_recall,
                "f1_score": overall_f1,
            },
            "by_family": family_results,
        }

    def _get_matching_signals_for_family(
        self, family: str, signals: List[Signal], layer: str
    ) -> List[Signal]:
        """Filters signals strictly relevant to a specific fault family."""
        matched: List[Signal] = []
        fam_l = family.lower()
        for s in signals:
            detector_name = (s.detector or "").lower()
            desc = (s.metric_or_relationship or "").lower()
            sig_type = (s.signal_type or "").lower()
            if fam_l in detector_name or fam_l in desc or fam_l in sig_type:
                matched.append(s)
                continue

            if family == "F1_Negative_SOC":
                if "soc" in desc or "soc" in detector_name:
                    matched.append(s)
            elif family == "F2_Voltage_Overvoltage_Spike":
                if "voltage" in desc or "voltage" in detector_name:
                    matched.append(s)
            elif family == "F3_RPM_Speed_Mismatch":
                if "rpm" in desc or "f3" in desc or "rpm" in detector_name or "f3" in detector_name:
                    matched.append(s)
            elif family == "F5_Negative_Cost":
                if "cost" in desc or "chg" in detector_name or "cost" in detector_name:
                    matched.append(s)
            elif family == "F7_Negative_Fare":
                if "fare" in desc or "trips_fare" in detector_name:
                    matched.append(s)
            elif family == "F8_Ledger_Mismatch":
                if "ledger" in desc or "ledger" in detector_name or "arithmetic" in sig_type:
                    matched.append(s)
            elif family == "F6_GPS_Alleyway_Drift":
                if "gps" in desc or "spatial" in desc or "gps" in detector_name or "spatial" in detector_name:
                    matched.append(s)
            elif family == "F10_SOC_Degradation_Drift":
                if s.layer == "L2" and "soc" in desc:
                    matched.append(s)
            elif family == "F11_BatteryTemp_Drift":
                if s.layer == "L2" and "temp" in desc:
                    matched.append(s)
            elif family == "F13_ChargingTrip_Mismatch":
                if "charging_trip" in detector_name or "discrepancy" in desc or "charging_trip" in sig_type:
                    matched.append(s)
            elif family == "F14_DurationEnergy_Mismatch":
                if "duration" in desc or "kwh" in desc or "chg_relational" in detector_name:
                    matched.append(s)
            elif family == "F15_ChargingFrequency_Shift":
                if s.layer == "L4" and ("charging_frequency" in desc or "chg_freq" in detector_name):
                    matched.append(s)
            elif family == "F16_FareDistribution_Regime":
                if s.layer == "L4" and ("distance" in desc or "driver" in detector_name):
                    matched.append(s)
            elif family == "F17_ForeignKey_Orphan":
                if "orphan" in desc or "orphan" in detector_name or "foreign" in desc:
                    matched.append(s)

        return matched

    def _is_signal_matching_fault(
        self,
        sig: Signal,
        fault: Dict[str, Any],
        df_index_lookup: Dict[str, pd.DataFrame],
        target_tables: List[str],
    ) -> bool:
        """Determines if a signal corresponds to an injected ground-truth fault."""
        orig_idx = fault.get("original_index")
        col = fault.get("column", "")

        # For point anomalies (L1): match timestamp or index
        if orig_idx is not None:
            for tbl in target_tables:
                df = df_index_lookup.get(tbl)
                if df is not None and orig_idx < len(df):
                    row = df.iloc[orig_idx]
                    ts_col = "timestamp" if "timestamp" in df.columns else ("start_time" if "start_time" in df.columns else None)
                    if ts_col and ts_col in row:
                        fault_ts = pd.to_datetime(row[ts_col])
                        sig_ts = pd.to_datetime(sig.event_time)
                        if abs((fault_ts.tz_localize(None) - sig_ts.tz_localize(None)).total_seconds()) <= 1.0:
                            return True
                    ent_col = "vehicle_vin" if "vehicle_vin" in df.columns else ("driver_id" if "driver_id" in df.columns else None)
                    if ent_col and ent_col in row:
                        if str(row[ent_col]) in sig.entity_ids:
                            if fault.get("day_idx") is None:
                                return True
                            day_col = "day_idx" if "day_idx" in df.columns else (
                                "assigned_day_index" if "assigned_day_index" in df.columns else None
                            )
                            if day_col is None:
                                return True
                            try:
                                return int(row[day_col]) == int(fault["day_idx"])
                            except (TypeError, ValueError):
                                return True

        # For window/entity anomalies (L2, L3, L4)
        if "affected_vin" in fault:
            return fault["affected_vin"] in sig.entity_ids
        if "entity_id" in fault:
            return fault["entity_id"] in sig.entity_ids

        return True
