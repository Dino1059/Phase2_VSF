"""
RCA Ground-Truth Matching and Evaluation Engine.
Evaluates A1 ReAct LLM Root Cause Analysis (RCA) Hypotheses against injected faults from fault_manifest.json.

Evaluates 4 core dimensions:
1. Classification Accuracy (DATA vs OPERATIONAL vs MIXED)
2. Root Cause Alignment Score (Semantic keyword coverage between Hypothesis Claim and Ground Truth Fault Description)
3. Evidence Grounding Verification (Ensuring cited evidence references actual tool observations)
4. Bounded ReAct Efficiency (Tool calls count, Token usage, Latency)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone
import pandas as pd

from src.reliability.models.incident import Incident
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.models.evidence import Evidence


# Mapping from fault families to Ground Truth RCA expectations
FAULT_FAMILY_RCA_SPECS: Dict[str, Dict[str, Any]] = {
    "F1_Negative_SOC": {
        "layer": "L1",
        "domain": "EV_TELEMETRY",
        "expected_classification": "DATA",
        "target_entity": "vinfast_bms",
        "ground_truth_cause": "BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0).",
        "expected_keywords": ["soc", "negative", "bms", "sensor", "range", "telemetry", "data", "glitch", "bound"],
        "expected_action": "QUARANTINE_DATA",
    },
    "F2_Voltage_Overvoltage_Spike": {
        "layer": "L1",
        "domain": "EV_TELEMETRY",
        "expected_classification": "DATA",
        "target_entity": "vinfast_bms",
        "ground_truth_cause": "CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V).",
        "expected_keywords": ["voltage", "overvoltage", "spike", "can", "sensor", "telemetry", "surge", "range"],
        "expected_action": "QUARANTINE_DATA",
    },
    "F3_RPM_Speed_Mismatch": {
        "layer": "L1",
        "domain": "EV_TELEMETRY",
        "expected_classification": "DATA",
        "target_entity": "vgreen_telemetry",
        "ground_truth_cause": "CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000).",
        "expected_keywords": ["rpm", "speed", "mismatch", "tachometer", "desync", "telemetry", "sensor", "zero"],
        "expected_action": "QUARANTINE_DATA",
    },
    "F5_Negative_Cost": {
        "layer": "L1",
        "domain": "CHARGING_NETWORK",
        "expected_classification": "DATA",
        "target_entity": "vgreen_charging_sessions",
        "ground_truth_cause": "Tariff billing engine calculation defect or negative pricing multiplier in charging session.",
        "expected_keywords": ["cost", "negative", "charging", "billing", "tariff", "pricing", "arithmetic", "fee"],
        "expected_action": "QUARANTINE_DATA",
    },
    "F7_Negative_Fare": {
        "layer": "L1",
        "domain": "RIDE_HAILING",
        "expected_classification": "DATA",
        "target_entity": "xanhsm_trips",
        "ground_truth_cause": "Ride-hailing billing pipeline defect producing negative trip fare amounts.",
        "expected_keywords": ["fare", "negative", "trip", "billing", "ride", "pipeline", "amount", "arithmetic"],
        "expected_action": "QUARANTINE_DATA",
    },
    "F8_Ledger_Mismatch": {
        "layer": "L1",
        "domain": "RIDE_HAILING",
        "expected_classification": "DATA",
        "target_entity": "xanhsm_trips",
        "ground_truth_cause": "Accounting ledger schema inconsistency where total_fare does not equal fare_amount + tip_amount.",
        "expected_keywords": ["ledger", "mismatch", "total_fare", "fare", "tip", "arithmetic", "accounting", "sum", "inconsistency"],
        "expected_action": "QUARANTINE_DATA",
    },
    "F10_SOC_Degradation_Drift": {
        "layer": "L2",
        "domain": "EV_TELEMETRY",
        "expected_classification": "OPERATIONAL",
        "target_entity": "vinfast_bms",
        "ground_truth_cause": "Battery cell degradation or increased internal resistance leading to accelerated SOC discharge rate over 14-day baseline.",
        "expected_keywords": ["soc", "degradation", "drift", "discharge", "battery", "wear", "baseline", "capacity", "cell", "operational"],
        "expected_action": "ALERT_MAINTENANCE",
    },
    "F11_BatteryTemp_Drift": {
        "layer": "L2",
        "domain": "EV_TELEMETRY",
        "expected_classification": "OPERATIONAL",
        "target_entity": "vinfast_bms",
        "ground_truth_cause": "Cooling system thermal degradation or pack heat dissipation failure leading to sustained temperature drift.",
        "expected_keywords": ["temperature", "temp", "thermal", "cooling", "drift", "heat", "baseline", "operational", "dissipation"],
        "expected_action": "ALERT_MAINTENANCE",
    },
    "F6_GPS_Alleyway_Drift": {
        "layer": "L3",
        "domain": "RIDE_HAILING",
        "expected_classification": "DATA",
        "target_entity": "xanhsm_trips",
        "ground_truth_cause": "Driver app GPS sensor drift or coordinate truncation placing pickup coordinates outside Hanoi bounding box.",
        "expected_keywords": ["gps", "drift", "bounding", "coordinates", "pickup", "location", "spatial", "bbox", "telemetry"],
        "expected_action": "FLAG_SENSOR_FAILURE",
    },
    "F13_ChargingTrip_Mismatch": {
        "layer": "L3",
        "domain": "CHARGING_NETWORK",
        "expected_classification": "OPERATIONAL",
        "target_entity": "vgreen_charging_sessions",
        "ground_truth_cause": "Vehicle utilization anomaly with high charging frequency (15+ sessions) but very low trip generation (<= 5 trips), indicating ghost charging or idle vehicle.",
        "expected_keywords": ["charging", "trip", "mismatch", "session", "utilization", "ghost", "cross", "ratio", "imbalance"],
        "expected_action": "ALERT_OPERATIONS",
    },
    "F14_DurationEnergy_Mismatch": {
        "layer": "L3",
        "domain": "CHARGING_NETWORK",
        "expected_classification": "MIXED",
        "target_entity": "vgreen_charging_sessions",
        "ground_truth_cause": "Relational break where charging duration increases significantly while delivered energy (kWh) remains flat, indicating power stall or charger meter fault.",
        "expected_keywords": ["duration", "kwh", "energy", "charging", "stall", "meter", "relational", "power", "flat", "mismatch"],
        "expected_action": "ALERT_MAINTENANCE",
    },
    "F15_ChargingFrequency_Shift": {
        "layer": "L4",
        "domain": "CHARGING_NETWORK",
        "expected_classification": "OPERATIONAL",
        "target_entity": "vgreen_charging_sessions",
        "ground_truth_cause": "Fleet charging regime shift where vehicle charging frequency abruptly jumps from 1/day to 3/day (CUSUM shift).",
        "expected_keywords": ["frequency", "shift", "cusum", "regime", "charging", "temporal", "pattern", "changepoint", "operational"],
        "expected_action": "ALERT_OPERATIONS",
    },
    "F16_FareDistribution_Regime": {
        "layer": "L4",
        "domain": "RIDE_HAILING",
        "expected_classification": "OPERATIONAL",
        "target_entity": "xanhsm_trips",
        "ground_truth_cause": "Driver route operating regime shift causing a persistent 50% shift in daily mean trip distance (CUSUM shift).",
        "expected_keywords": ["trip", "distance", "driver", "shift", "cusum", "mean", "regime", "distribution", "route"],
        "expected_action": "ALERT_OPERATIONS",
    },
}


class RCAGroundTruthMatcher:
    """
    Evaluates RCA hypotheses from A1 Investigator against Ground Truth fault definitions.
    """

    def __init__(self, manifest_path: Optional[str | Path] = None):
        self.manifest_path = Path(manifest_path).resolve() if manifest_path else None
        self.faults: List[Dict[str, Any]] = []
        if self.manifest_path and self.manifest_path.exists():
            self._load_manifest()

    def _load_manifest(self) -> None:
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.faults = data.get("faults", [])

    def match_incident_to_fault(
        self,
        incident: Incident,
        dfs: Optional[Dict[str, pd.DataFrame]] = None,
        signal_lookup: Optional[Dict[str, Signal]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Matches an admitted Incident to its underlying injected ground-truth fault.
        Inspects incident metadata and underlying Signal objects for exact fault family attribution.
        """
        reason = (incident.admission_reason or "").lower()
        signal_ids_str = " ".join(incident.signal_ids or []).lower()
        entity_ids = set(incident.entity_ids or [])
        layers = set(incident.supporting_layers or [])

        # Inspect underlying signals if lookup is provided
        incident_signals: List[Signal] = []
        if signal_lookup:
            incident_signals = [signal_lookup[sid] for sid in incident.signal_ids if sid in signal_lookup]

        # Priority 1: Match by direct detector and metric inspection from underlying signals
        for sig in incident_signals:
            det = (sig.detector or "").lower()
            metric = (sig.metric_or_relationship or "").lower()
            sig_type = (sig.signal_type or "").lower()

            if "speed_vs_motor_rpm" in metric or "speed_rpm" in det:
                return {"fault_family": "F3_RPM_Speed_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F3_RPM_Speed_Mismatch"], "matched_by": "signal_metric"}
            if "ledger" in det or "ledger" in metric or "arithmetic" in sig_type:
                return {"fault_family": "F8_Ledger_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F8_Ledger_Mismatch"], "matched_by": "signal_metric"}
            if "spatial" in det or "bounding" in det or "gps" in metric:
                return {"fault_family": "F6_GPS_Alleyway_Drift", "spec": FAULT_FAMILY_RCA_SPECS["F6_GPS_Alleyway_Drift"], "matched_by": "signal_metric"}
            if sig.layer == "L1" and ("soc_pct" in metric or "battery_soc" in metric):
                return {"fault_family": "F1_Negative_SOC", "spec": FAULT_FAMILY_RCA_SPECS["F1_Negative_SOC"], "matched_by": "signal_metric"}
            if sig.layer == "L1" and "voltage" in metric:
                return {"fault_family": "F2_Voltage_Overvoltage_Spike", "spec": FAULT_FAMILY_RCA_SPECS["F2_Voltage_Overvoltage_Spike"], "matched_by": "signal_metric"}
            if sig.layer == "L1" and "cost_vnd" in metric:
                return {"fault_family": "F5_Negative_Cost", "spec": FAULT_FAMILY_RCA_SPECS["F5_Negative_Cost"], "matched_by": "signal_metric"}
            if sig.layer == "L1" and ("fare_amount" in metric or "fare_vnd" in metric):
                return {"fault_family": "F7_Negative_Fare", "spec": FAULT_FAMILY_RCA_SPECS["F7_Negative_Fare"], "matched_by": "signal_metric"}
            if sig.layer == "L2" and "soc" in metric:
                return {"fault_family": "F10_SOC_Degradation_Drift", "spec": FAULT_FAMILY_RCA_SPECS["F10_SOC_Degradation_Drift"], "matched_by": "signal_metric"}
            if sig.layer == "L2" and "temp" in metric:
                return {"fault_family": "F11_BatteryTemp_Drift", "spec": FAULT_FAMILY_RCA_SPECS["F11_BatteryTemp_Drift"], "matched_by": "signal_metric"}
            if "charging_trip" in sig_type or "charging_sessions_vs_trips" in metric:
                return {"fault_family": "F13_ChargingTrip_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F13_ChargingTrip_Mismatch"], "matched_by": "signal_metric"}
            if "duration_mins" in metric or "kwh_consumed" in metric:
                return {"fault_family": "F14_DurationEnergy_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F14_DurationEnergy_Mismatch"], "matched_by": "signal_metric"}
            if sig.layer == "L4" and "charging_frequency" in metric:
                return {"fault_family": "F15_ChargingFrequency_Shift", "spec": FAULT_FAMILY_RCA_SPECS["F15_ChargingFrequency_Shift"], "matched_by": "signal_metric"}
            if sig.layer == "L4" and ("distance" in metric or "driver" in det):
                return {"fault_family": "F16_FareDistribution_Regime", "spec": FAULT_FAMILY_RCA_SPECS["F16_FareDistribution_Regime"], "matched_by": "signal_metric"}

        # Priority 2: Match by direct fault family keyword in reason or signals
        for fam, spec in FAULT_FAMILY_RCA_SPECS.items():
            fam_clean = fam.lower()
            fam_short = fam.split("_")[0].lower() # e.g. f1, f3, f10
            if fam_clean in reason or fam_clean in signal_ids_str or f"{fam_short}_" in reason or f"({fam_short})" in reason or f"{fam_short} " in reason:
                return {
                    "fault_family": fam,
                    "spec": spec,
                    "matched_by": "family_name_keyword"
                }

        # Priority 3: Match by semantic characteristics in admission reason
        if "negative soc" in reason or ("soc" in reason and "< 0" in reason):
            return {"fault_family": "F1_Negative_SOC", "spec": FAULT_FAMILY_RCA_SPECS["F1_Negative_SOC"], "matched_by": "reason_semantic"}
        if "voltage" in reason and ("overvoltage" in reason or "spike" in reason or "1000" in reason):
            return {"fault_family": "F2_Voltage_Overvoltage_Spike", "spec": FAULT_FAMILY_RCA_SPECS["F2_Voltage_Overvoltage_Spike"], "matched_by": "reason_semantic"}
        if "rpm" in reason or "speed" in reason and "mismatch" in reason:
            return {"fault_family": "F3_RPM_Speed_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F3_RPM_Speed_Mismatch"], "matched_by": "reason_semantic"}
        if "cost" in reason and "negative" in reason:
            return {"fault_family": "F5_Negative_Cost", "spec": FAULT_FAMILY_RCA_SPECS["F5_Negative_Cost"], "matched_by": "reason_semantic"}
        if "negative fare" in reason or "fare_amount" in reason and "< 0" in reason:
            return {"fault_family": "F7_Negative_Fare", "spec": FAULT_FAMILY_RCA_SPECS["F7_Negative_Fare"], "matched_by": "reason_semantic"}
        if "ledger" in reason or ("fare" in reason and "tip" in reason and "total" in reason):
            return {"fault_family": "F8_Ledger_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F8_Ledger_Mismatch"], "matched_by": "reason_semantic"}
        if "gps" in reason or "bounding box" in reason or "spatial" in reason:
            return {"fault_family": "F6_GPS_Alleyway_Drift", "spec": FAULT_FAMILY_RCA_SPECS["F6_GPS_Alleyway_Drift"], "matched_by": "reason_semantic"}
        if "soc" in reason and ("drift" in reason or "degradation" in reason or "l2" in layers):
            return {"fault_family": "F10_SOC_Degradation_Drift", "spec": FAULT_FAMILY_RCA_SPECS["F10_SOC_Degradation_Drift"], "matched_by": "reason_semantic"}
        if ("temp" in reason or "thermal" in reason) and ("drift" in reason or "l2" in layers):
            return {"fault_family": "F11_BatteryTemp_Drift", "spec": FAULT_FAMILY_RCA_SPECS["F11_BatteryTemp_Drift"], "matched_by": "reason_semantic"}
        if "charging" in reason and "trip" in reason and ("discrepancy" in reason or "mismatch" in reason or "ratio" in reason):
            return {"fault_family": "F13_ChargingTrip_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F13_ChargingTrip_Mismatch"], "matched_by": "reason_semantic"}
        if ("duration" in reason or "kwh" in reason) and ("relational" in reason or "bivariate" in reason):
            return {"fault_family": "F14_DurationEnergy_Mismatch", "spec": FAULT_FAMILY_RCA_SPECS["F14_DurationEnergy_Mismatch"], "matched_by": "reason_semantic"}
        if "charging_frequency" in reason or ("charging" in reason and ("cusum" in reason or "l4" in layers or "frequency" in reason)):
            return {"fault_family": "F15_ChargingFrequency_Shift", "spec": FAULT_FAMILY_RCA_SPECS["F15_ChargingFrequency_Shift"], "matched_by": "reason_semantic"}
        if "driver" in reason and ("cusum" in reason or "distance" in reason or "l4" in layers):
            return {"fault_family": "F16_FareDistribution_Regime", "spec": FAULT_FAMILY_RCA_SPECS["F16_FareDistribution_Regime"], "matched_by": "reason_semantic"}

        # Priority 3: Match from manifest by entity_id
        for fault in self.faults:
            f_vin = fault.get("affected_vin") or fault.get("entity_id")
            if f_vin and str(f_vin) in entity_ids:
                fam = fault.get("fault_family", "")
                if fam in FAULT_FAMILY_RCA_SPECS:
                    return {"fault_family": fam, "spec": FAULT_FAMILY_RCA_SPECS[fam], "matched_by": "manifest_entity"}

        return None

    def evaluate_hypothesis(
        self,
        incident: Incident,
        hypothesis: Hypothesis,
        gt_match: Optional[Dict[str, Any]],
        meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Scores a single RCA hypothesis against ground truth expectations.
        """
        if not gt_match:
            return {
                "verdict": "UNMATCHED_GT",
                "classification_score": 0.0,
                "root_cause_score": 0.0,
                "evidence_grounding_score": 0.0,
                "overall_score": 0.0,
                "reason": "Could not associate incident with an injected ground truth fault family."
            }

        spec = gt_match["spec"]
        fam = gt_match["fault_family"]
        expected_cls = spec["expected_classification"].upper()
        actual_cls = (hypothesis.classification or "UNKNOWN").upper()

        # 1. Classification Scoring (0.0 to 1.0)
        if actual_cls == expected_cls:
            class_score = 1.0
        elif expected_cls == "MIXED" and actual_cls in ["DATA", "OPERATIONAL"]:
            class_score = 0.7
        elif actual_cls == "MIXED" and expected_cls in ["DATA", "OPERATIONAL"]:
            class_score = 0.7
        else:
            class_score = 0.0

        # 2. Root Cause Claim Semantic Keyword Coverage (0.0 to 1.0)
        claim_text = (hypothesis.claim or "").lower()
        expected_keywords = [k.lower() for k in spec["expected_keywords"]]
        matched_keywords = [k for k in expected_keywords if re.search(r'\b' + re.escape(k) + r'\b', claim_text)]
        
        # Calculate coverage ratio
        keyword_hit_ratio = len(matched_keywords) / max(3, min(len(expected_keywords), 5))
        rc_score = round(min(1.0, keyword_hit_ratio), 2)
        if len(matched_keywords) >= 2:
            rc_score = max(0.8, rc_score)

        # 3. Evidence Grounding Verification
        supporting_ev = hypothesis.supporting_evidence or []
        tool_trace = meta.get("tool_execution_trace", [])
        tool_evidence_refs = {t.get("evidence_ref") for t in tool_trace if t.get("evidence_ref")}
        
        if supporting_ev:
            grounded_ev = [e for e in supporting_ev if e in tool_evidence_refs or "ev-" in e]
            grounding_score = round(len(grounded_ev) / len(supporting_ev), 2)
        else:
            grounding_score = 0.5  # Neutral if no evidence list

        # 4. ReAct Operational Efficiency
        tool_calls = meta.get("tool_calls_made", 0)
        tokens_spent = meta.get("tokens_spent", 0)
        wall_clock_sec = meta.get("wall_clock_elapsed_sec", 0.0)
        
        bounded_pass = (tool_calls <= 5) and (tokens_spent <= 12000) and (wall_clock_sec <= 60.0)

        # 5. Composite Score & Verdict
        # Weighting: 40% Classification + 40% Root Cause Claim + 20% Evidence Grounding
        overall_score = round(0.40 * class_score + 0.40 * rc_score + 0.20 * grounding_score, 3)

        if overall_score >= 0.80:
            verdict = "PASS"
        elif overall_score >= 0.50:
            verdict = "PARTIAL"
        else:
            verdict = "FAIL"

        return {
            "fault_family": fam,
            "layer": spec["layer"],
            "domain": spec["domain"],
            "expected_classification": expected_cls,
            "actual_classification": actual_cls,
            "classification_score": class_score,
            "ground_truth_cause": spec["ground_truth_cause"],
            "llm_claim": hypothesis.claim,
            "matched_keywords": matched_keywords,
            "root_cause_score": rc_score,
            "evidence_grounding_score": grounding_score,
            "supporting_evidence": supporting_ev,
            "tool_calls_made": tool_calls,
            "tokens_spent": tokens_spent,
            "wall_clock_sec": wall_clock_sec,
            "bounded_efficiency_pass": bounded_pass,
            "overall_score": overall_score,
            "verdict": verdict,
        }

    def generate_benchmark_summary(
        self,
        evaluated_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregates metrics across all evaluated RCA cases.
        """
        total = len(evaluated_cases)
        if total == 0:
            return {"total_cases": 0}

        pass_count = sum(1 for c in evaluated_cases if c.get("eval", {}).get("verdict") == "PASS")
        partial_count = sum(1 for c in evaluated_cases if c.get("eval", {}).get("verdict") == "PARTIAL")
        fail_count = sum(1 for c in evaluated_cases if c.get("eval", {}).get("verdict") == "FAIL")

        avg_class_score = sum(c.get("eval", {}).get("classification_score", 0.0) for c in evaluated_cases) / total
        avg_rc_score = sum(c.get("eval", {}).get("root_cause_score", 0.0) for c in evaluated_cases) / total
        avg_grounding_score = sum(c.get("eval", {}).get("evidence_grounding_score", 0.0) for c in evaluated_cases) / total
        avg_overall_score = sum(c.get("eval", {}).get("overall_score", 0.0) for c in evaluated_cases) / total

        avg_tool_calls = sum(c.get("eval", {}).get("tool_calls_made", 0) for c in evaluated_cases) / total
        avg_tokens = sum(c.get("eval", {}).get("tokens_spent", 0) for c in evaluated_cases) / total
        avg_latency = sum(c.get("eval", {}).get("wall_clock_sec", 0.0) for c in evaluated_cases) / total

        return {
            "total_cases_evaluated": total,
            "passed_cases": pass_count,
            "partial_cases": partial_count,
            "failed_cases": fail_count,
            "pass_rate": round(pass_count / total, 4),
            "effective_accuracy": round((pass_count + 0.5 * partial_count) / total, 4),
            "average_metrics": {
                "classification_accuracy": round(avg_class_score, 4),
                "root_cause_alignment": round(avg_rc_score, 4),
                "evidence_grounding": round(avg_grounding_score, 4),
                "overall_rca_score": round(avg_overall_score, 4),
            },
            "operational_efficiency": {
                "avg_tool_calls": round(avg_tool_calls, 1),
                "avg_tokens_spent": round(avg_tokens, 1),
                "avg_latency_sec": round(avg_latency, 2),
            }
        }
