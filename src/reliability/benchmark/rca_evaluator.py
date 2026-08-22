"""
RCA Benchmark Evaluator with Structured Diagnosis Validation.

Implements a 3-tier deterministic evaluation:
Tier 1: Classification Match (DATA / OPERATIONAL / MIXED)
Tier 2: Structured Diagnosis Validation (Target Component, Metric, Failure Mechanism)
Tier 3: Evidence Grounding & Bounded Operational Efficiency
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.reliability.models.hypothesis import Hypothesis


# Normalization synonyms for deterministic component matching
COMPONENT_SYNONYMS: Dict[str, List[str]] = {
    "BMS": ["bms", "battery", "battery_management_system", "battery_pack", "cell", "pack"],
    "BATTERY_CELL": ["battery_cell", "battery", "cell", "pack", "bms", "internal_resistance"],
    "COOLING_SYSTEM": ["cooling_system", "cooling", "thermal", "heat_dissipation", "radiator", "chiller"],
    "MOTOR": ["motor", "tachometer", "powertrain", "electric_motor", "drive_unit"],
    "TACHOMETER": ["tachometer", "motor_rpm", "rpm_sensor", "speed_sensor"],
    "BILLING_PIPELINE": ["billing_pipeline", "billing", "tariff_engine", "pricing_engine", "fare_calculation", "payment"],
    "ACCOUNTING_LEDGER": ["accounting_ledger", "ledger", "accounting", "fare_schema", "ledger_schema"],
    "GPS_SENSOR": ["gps_sensor", "gps", "driver_app", "telemetry_gps", "location_service"],
    "FLEET_UTILIZATION": ["fleet_utilization", "utilization", "charging_trip_ratio", "charging_session", "ghost_charging"],
    "CHARGER_METER": ["charger_meter", "charger", "charging_station", "power_delivery", "meter_stall"],
    "CHARGING_REGIME": ["charging_regime", "fleet_charging", "charging_frequency", "fleet_operations"],
    "DRIVER_ROUTE": ["driver_route", "route_regime", "driver_behavior", "trip_distribution", "route"]
}

# Normalization synonyms for metric matching
METRIC_SYNONYMS: Dict[str, List[str]] = {
    "battery_soc": ["battery_soc", "soc", "state_of_charge", "soc_pct"],
    "battery_voltage": ["battery_voltage", "voltage", "pack_voltage", "volts", "v"],
    "motor_rpm": ["motor_rpm", "rpm", "motor_speed", "tachometer_rpm"],
    "cost_vnd": ["cost_vnd", "cost", "charging_cost", "session_cost"],
    "fare_amount": ["fare_amount", "fare", "trip_fare", "fare_vnd"],
    "total_fare": ["total_fare", "total_amount", "ledger_sum", "fare_plus_tip"],
    "pickup_latitude": ["pickup_latitude", "latitude", "gps_coords", "coordinates", "location", "pickup_coords"],
    "battery_temp_c": ["battery_temp_c", "battery_temp", "temperature", "temp_c", "thermal"],
    "charging_sessions_vs_trips": ["charging_sessions_vs_trips", "charging_vs_trips", "sessions_vs_trips", "session_id"],
    "duration_vs_kwh": ["duration_vs_kwh", "duration_energy", "duration_mins", "kwh_consumed", "kwh_delivered"],
    "charging_frequency": ["charging_frequency", "session_frequency", "daily_charges", "frequency"],
    "trip_distance_km": ["trip_distance_km", "trip_distance", "distance_km", "mean_distance"]
}

# Normalization synonyms for failure mechanism matching
MECHANISM_SYNONYMS: Dict[str, List[str]] = {
    "SENSOR_GLITCH": ["sensor_glitch", "glitch", "sensor_error", "range_violation", "spike", "out_of_bounds", "telemetry_corruption"],
    "DESYNCHRONIZATION": ["desynchronization", "desync", "mismatch", "speed_rpm_mismatch", "sensor_mismatch"],
    "ARITHMETIC_ERROR": ["arithmetic_error", "calculation_defect", "calculation_error", "negative_multiplier", "tariff_defect"],
    "PIPELINE_DEFECT": ["pipeline_defect", "billing_defect", "data_corruption", "negative_fare", "pipeline_bug"],
    "SCHEMA_MISMATCH": ["schema_mismatch", "ledger_mismatch", "accounting_error", "inconsistency", "sum_mismatch"],
    "DEGRADATION_DRIFT": ["degradation_drift", "degradation", "hardware_wear", "capacity_loss", "battery_wear"],
    "THERMAL_DRIFT": ["thermal_drift", "cooling_degradation", "heat_dissipation_failure", "thermal_runaway", "overheating"],
    "SPATIAL_DRIFT": ["spatial_drift", "gps_drift", "bounding_box_violation", "out_of_bounds_coords", "location_drift"],
    "RELATIONAL_BREAK": ["relational_break", "bivariate_break", "ghost_charging", "power_stall", "meter_stall"],
    "CHANGEPOINT_SHIFT": ["changepoint_shift", "regime_shift", "cusum_shift", "distribution_shift", "temporal_shift"]
}


class RCABenchmarkEvaluator:
    """
    Deterministic RCA Benchmark Evaluator using structured fields and explicit rubric.
    """

    def __init__(self):
        pass

    def evaluate_case(
        self,
        case: Dict[str, Any],
        hypothesis: Hypothesis,
        execution_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates a single Test Case hypothesis against Ground Truth expectations.
        """
        gt = case.get("ground_truth", {})
        expected_cls = (gt.get("expected_classification") or "DATA").upper()
        actual_cls = (hypothesis.classification or "UNKNOWN").upper()

        # ----------------------------------------------------
        # Tier 1: Classification Score (Weight: 40%)
        # ----------------------------------------------------
        if actual_cls == expected_cls:
            class_score = 1.0
        elif (expected_cls == "MIXED" and actual_cls in ["DATA", "OPERATIONAL"]) or \
             (actual_cls == "MIXED" and expected_cls in ["DATA", "OPERATIONAL"]):
            class_score = 0.7
        else:
            class_score = 0.0

        # ----------------------------------------------------
        # Tier 2: Structured Diagnosis Validation (Weight: 40%)
        # ----------------------------------------------------
        expected_comp = gt.get("target_component", "")
        expected_metric = gt.get("target_metric", "")
        expected_mech = gt.get("failure_mechanism", "")

        # LLM values (explicit or extracted fallback)
        actual_comp = (hypothesis.target_component or "").strip().lower()
        actual_metric = (hypothesis.target_metric or "").strip().lower()
        actual_mech = (hypothesis.failure_mechanism or "").strip().lower()
        claim_text = (hypothesis.claim or "").lower()

        # Sub-check 1: Target Component
        comp_valid_synonyms = COMPONENT_SYNONYMS.get(expected_comp, [expected_comp.lower()])
        comp_match = any(syn in actual_comp or syn in claim_text for syn in comp_valid_synonyms)
        comp_score = 1.0 if comp_match else 0.0

        # Sub-check 2: Target Metric
        metric_valid_synonyms = METRIC_SYNONYMS.get(expected_metric, [expected_metric.lower()])
        metric_match = any(syn in actual_metric or syn in claim_text for syn in metric_valid_synonyms)
        metric_score = 1.0 if metric_match else 0.0

        # Sub-check 3: Failure Mechanism
        mech_valid_synonyms = MECHANISM_SYNONYMS.get(expected_mech, [expected_mech.lower()])
        mech_match = any(syn in actual_mech or syn in claim_text for syn in mech_valid_synonyms)
        mech_score = 1.0 if mech_match else 0.0

        diagnosis_score = round((comp_score + metric_score + mech_score) / 3.0, 3)

        # ----------------------------------------------------
        # Tier 3: Evidence Grounding & Bounds (Weight: 20%)
        # ----------------------------------------------------
        tool_trace = execution_meta.get("tool_execution_trace", [])
        tool_evidence_refs = {t.get("evidence_ref") for t in tool_trace if t.get("evidence_ref")}
        
        # Include initial evidence IDs as valid
        init_ev_ids = {e.get("evidence_id") for e in case.get("initial_evidence", [])}
        all_valid_refs = tool_evidence_refs.union(init_ev_ids)

        sup_evidence = hypothesis.supporting_evidence or []
        if sup_evidence:
            valid_sup = [e for e in sup_evidence if e in all_valid_refs or "EV-" in e.upper()]
            grounding_score = round(len(valid_sup) / len(sup_evidence), 2)
        else:
            grounding_score = 0.5  # Neutral fallback

        # Operational bounds check
        tool_calls = execution_meta.get("tool_calls_made", 0)
        tokens_spent = execution_meta.get("tokens_spent", 0)
        wall_clock_sec = execution_meta.get("wall_clock_elapsed_sec", 0.0)

        bounds_passed = (tool_calls <= 5) and (tokens_spent <= 12000) and (wall_clock_sec <= 60.0)

        # ----------------------------------------------------
        # Composite Score & Final Verdict
        # Weighting: 40% Classification + 40% Diagnosis + 20% Grounding
        # ----------------------------------------------------
        overall_score = round(0.40 * class_score + 0.40 * diagnosis_score + 0.20 * grounding_score, 3)

        if overall_score >= 0.80 and bounds_passed:
            verdict = "PASS"
        elif overall_score >= 0.50:
            verdict = "PARTIAL"
        else:
            verdict = "FAIL"

        return {
            "case_id": case.get("case_id"),
            "fault_family": case.get("fault_family"),
            "layer": case.get("layer"),
            "domain": case.get("domain"),
            "entity_id": case.get("entity_id"),
            "expected_classification": expected_cls,
            "actual_classification": actual_cls,
            "classification_score": class_score,
            "target_component": {
                "expected": expected_comp,
                "actual": hypothesis.target_component,
                "matched": comp_match,
            },
            "target_metric": {
                "expected": expected_metric,
                "actual": hypothesis.target_metric,
                "matched": metric_match,
            },
            "failure_mechanism": {
                "expected": expected_mech,
                "actual": hypothesis.failure_mechanism,
                "matched": mech_match,
            },
            "diagnosis_score": diagnosis_score,
            "ground_truth_cause": gt.get("ground_truth_cause"),
            "llm_claim": hypothesis.claim,
            "supporting_evidence": sup_evidence,
            "grounding_score": grounding_score,
            "operational_efficiency": {
                "tool_calls_made": tool_calls,
                "tokens_spent": tokens_spent,
                "wall_clock_sec": wall_clock_sec,
                "bounds_passed": bounds_passed
            },
            "overall_score": overall_score,
            "verdict": verdict
        }

    def generate_markdown_report(
        self,
        results: List[Dict[str, Any]],
        output_file: Optional[Path] = None
    ) -> str:
        """
        Generates a comprehensive Benchmark Report with Human Audit Matrix.
        """
        total = len(results)
        passes = sum(1 for r in results if r["verdict"] == "PASS")
        partials = sum(1 for r in results if r["verdict"] == "PARTIAL")
        fails = sum(1 for r in results if r["verdict"] == "FAIL")

        avg_score = round(sum(r["overall_score"] for r in results) / max(1, total), 3)
        avg_class = round(sum(r["classification_score"] for r in results) / max(1, total), 3)
        avg_diag = round(sum(r["diagnosis_score"] for r in results) / max(1, total), 3)
        avg_ground = round(sum(r["grounding_score"] for r in results) / max(1, total), 3)

        lines = [
            "# Root Cause Analysis (RCA) Benchmark Report",
            "",
            f"**Total Gold Cases Evaluated:** {total}",
            f"- **PASS:** {passes} ({passes/max(1, total)*100:.1f}%)",
            f"- **PARTIAL:** {partials} ({partials/max(1, total)*100:.1f}%)",
            f"- **FAIL:** {fails} ({fails/max(1, total)*100:.1f}%)",
            "",
            "## Score Breakdown Across Tiers",
            f"- **Overall Mean Score:** `{avg_score * 100:.1f}%`",
            f"- **Tier 1 - Classification Accuracy:** `{avg_class * 100:.1f}%`",
            f"- **Tier 2 - Structured Diagnosis Accuracy:** `{avg_diag * 100:.1f}%`",
            f"- **Tier 3 - Evidence Grounding Score:** `{avg_ground * 100:.1f}%`",
            "",
            "---",
            "",
            "## Human Audit Matrix (Visual Verification)",
            "",
            "| Case ID | Layer | Fault Family | Ground Truth Cause | LLM Diagnosis & Claim | Classification | Diag (Comp/Met/Mech) | Verdict |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for r in results:
            tc = r["case_id"]
            layer = r["layer"]
            fam = r["fault_family"]
            gt_cause = r["ground_truth_cause"]
            llm_claim = r["llm_claim"].replace("|", "/")
            cls_status = f"{r['actual_classification']} ({'OK' if r['classification_score'] == 1.0 else 'MISMATCH'})"
            
            c_ok = "V" if r["target_component"]["matched"] else "X"
            m_ok = "V" if r["target_metric"]["matched"] else "X"
            f_ok = "V" if r["failure_mechanism"]["matched"] else "X"
            diag_str = f"{c_ok}/{m_ok}/{f_ok} ({int(r['diagnosis_score']*100)}%)"

            verdict_badge = f"**{r['verdict']}**"
            lines.append(f"| `{tc}` | `{layer}` | `{fam}` | {gt_cause} | {llm_claim} | {cls_status} | {diag_str} | {verdict_badge} |")

        lines.extend([
            "",
            "---",
            "",
            "## Operational Efficiency Summary",
            "",
            "| Case ID | Tool Calls | Tokens Spent | Latency (sec) | Bounded Gate |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])

        for r in results:
            tc = r["case_id"]
            eff = r["operational_efficiency"]
            tc_made = eff["tool_calls_made"]
            tok = eff["tokens_spent"]
            lat = eff["wall_clock_sec"]
            gate = "PASS" if eff["bounds_passed"] else "EXCEEDED"
            lines.append(f"| `{tc}` | {tc_made} | {tok:,} | {lat:.2f}s | `{gate}` |")

        report_md = "\n".join(lines)

        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_md)

        return report_md
