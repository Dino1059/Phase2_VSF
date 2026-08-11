import time
from typing import Dict, Any, List, Set
from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.r0 import R0DeterministicInvestigator
from src.reliability.investigation.c1 import C1FixedInvestigator
from src.reliability.investigation.a1 import A1BoundedInvestigator

# Standard benchmark token pricing ($2.00 per 1M tokens)
COST_PER_TOKEN = 0.000002


def run_unbiased_agentic_evaluation() -> Dict[str, Any]:
    """
    Unbiased comparison harness evaluating R0 (Deterministic), C1 (Fixed AI), and A1 (Bounded Dynamic AI).
    Evaluates SLA latency, cost per incident, Top-1 accuracy, evidence recall, and tool calls using empirical trace outputs.
    """
    r0 = R0DeterministicInvestigator()
    c1 = C1FixedInvestigator()
    a1 = A1BoundedInvestigator()

    test_cases = [
        {
            "incident": Incident(
                project_id="proj-eval",
                entity_ids=["VIN-010"],
                signal_ids=["RANGE_VIOLATION_battery_soc"],
                admission_reason="Out of range sensor value",
                severity="CRITICAL"
            ),
            "evidence": [
                Evidence(
                    evidence_id="ev-bms-10",
                    source_type="telemetry",
                    source_id="bms-10",
                    entity_ids=["VIN-010"],
                    content_hash="hash0",
                    summary="SOC value -10.0 out of range sensor value"
                )
            ],
            "ground_truth_classification": "DATA",
            "ground_truth_evidence": {"ev-bms-10"}
        },
        {
            "incident": Incident(
                project_id="proj-eval",
                entity_ids=["VIN-020"],
                signal_ids=["NULL_VIOLATION_driver_id"],
                admission_reason="L1 schema NULL_VIOLATION in mandatory field",
                severity="HIGH"
            ),
            "evidence": [
                Evidence(
                    evidence_id="ev-trip-20",
                    source_type="trips",
                    source_id="trip-20",
                    entity_ids=["VIN-020"],
                    content_hash="hash1",
                    summary="Trip fare negative arithmetic null schema defect"
                )
            ],
            "ground_truth_classification": "DATA",
            "ground_truth_evidence": {"ev-trip-20"}
        },
        {
            "incident": Incident(
                project_id="proj-eval",
                entity_ids=["VIN-030"],
                signal_ids=["THERMAL_DEGRADATION"],
                admission_reason="Thermal degradation drift",
                severity="HIGH"
            ),
            "evidence": [
                Evidence(
                    evidence_id="ev-bms-30",
                    source_type="telemetry",
                    source_id="bms-30",
                    entity_ids=["VIN-030"],
                    content_hash="hash2",
                    summary="Battery temp thermal degradation spike"
                )
            ],
            "ground_truth_classification": "OPERATIONAL",
            "ground_truth_evidence": {"ev-bms-30", "ev-telemetry-VIN-030-battery_soc", "ev-baseline-VIN-030"}
        },
        {
            "incident": Incident(
                project_id="proj-eval",
                entity_ids=["VIN-040"],
                signal_ids=["DEGRADATION_WARNING"],
                admission_reason="Battery voltage degradation",
                severity="CRITICAL"
            ),
            "evidence": [
                Evidence(
                    evidence_id="ev-bms-40",
                    source_type="telemetry",
                    source_id="bms-40",
                    entity_ids=["VIN-040"],
                    content_hash="hash3",
                    summary="Voltage degradation in battery pack"
                )
            ],
            "ground_truth_classification": "OPERATIONAL",
            "ground_truth_evidence": {"ev-bms-40", "ev-telemetry-VIN-040-battery_soc", "ev-baseline-VIN-040"}
        }
    ]

    total_cases = len(test_cases)

    r0_metrics: Dict[str, Any] = {"correct": 0, "evidence_recalls": [], "latency_ms": [], "tokens": 0, "tool_calls": 0}
    c1_metrics: Dict[str, Any] = {"correct": 0, "evidence_recalls": [], "latency_ms": [], "tokens": 0, "tool_calls": 0}
    a1_metrics: Dict[str, Any] = {"correct": 0, "evidence_recalls": [], "latency_ms": [], "tokens": 0, "tool_calls": 0}

    for case in test_cases:
        inc = case["incident"]
        initial_ev = case["evidence"]
        gt_cls = case["ground_truth_classification"]
        gt_ev: Set[str] = case["ground_truth_evidence"]

        # --- Evaluate R0 Deterministic ---
        t0 = time.perf_counter()
        hyp_r0, rec_r0 = r0.investigate_incident(inc, initial_ev)
        t_r0 = (time.perf_counter() - t0) * 1000.0
        r0_metrics["latency_ms"].append(t_r0)

        if hyp_r0 and hyp_r0.classification == gt_cls:
            r0_metrics["correct"] += 1

        r0_evidence = set(hyp_r0.supporting_evidence) if hyp_r0 and hyp_r0.supporting_evidence else set()
        r0_recall = len(r0_evidence.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0
        r0_metrics["evidence_recalls"].append(r0_recall)

        # --- Evaluate C1 Fixed Workflow ---
        t0 = time.perf_counter()
        hyp_c1, rec_c1 = c1.investigate_incident(inc, initial_ev)
        t_c1 = (time.perf_counter() - t0) * 1000.0
        c1_metrics["latency_ms"].append(t_c1)

        if hyp_c1 and hyp_c1.classification == gt_cls:
            c1_metrics["correct"] += 1

        c1_evidence = set(hyp_c1.supporting_evidence) if hyp_c1 and hyp_c1.supporting_evidence else set()
        c1_recall = len(c1_evidence.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0
        c1_metrics["evidence_recalls"].append(c1_recall)
        c1_tokens = sum(len(e.summary.split()) * 4 for e in initial_ev) + 150
        c1_metrics["tokens"] += c1_tokens

        # --- Evaluate A1 Bounded Dynamic ---
        t0 = time.perf_counter()
        hyp_a1, rec_a1, meta_a1 = a1.investigate_incident_dynamically(inc, initial_ev)
        t_a1 = (time.perf_counter() - t0) * 1000.0
        a1_metrics["latency_ms"].append(t_a1)

        if hyp_a1 and hyp_a1.classification == gt_cls:
            a1_metrics["correct"] += 1

        a1_evidence = set(hyp_a1.supporting_evidence) if hyp_a1 and hyp_a1.supporting_evidence else set()
        a1_recall = len(a1_evidence.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0
        a1_metrics["evidence_recalls"].append(a1_recall)
        a1_metrics["tokens"] += meta_a1.get("tokens_spent", 0)
        a1_metrics["tool_calls"] += meta_a1.get("tool_calls_made", 0)

    # Compute empirical aggregates
    r0_acc = round(r0_metrics["correct"] / total_cases, 4)
    r0_rec = round(sum(r0_metrics["evidence_recalls"]) / total_cases, 4)
    r0_lat = round(sum(r0_metrics["latency_ms"]) / total_cases, 4)
    r0_tok = int(r0_metrics["tokens"] / total_cases)
    r0_cost = round(r0_tok * COST_PER_TOKEN, 6)

    c1_acc = round(c1_metrics["correct"] / total_cases, 4)
    c1_rec = round(sum(c1_metrics["evidence_recalls"]) / total_cases, 4)
    c1_lat = round(sum(c1_metrics["latency_ms"]) / total_cases, 4)
    c1_tok = int(c1_metrics["tokens"] / total_cases)
    c1_cost = round(c1_tok * COST_PER_TOKEN, 6)

    a1_acc = round(a1_metrics["correct"] / total_cases, 4)
    a1_rec = round(sum(a1_metrics["evidence_recalls"]) / total_cases, 4)
    a1_lat = round(sum(a1_metrics["latency_ms"]) / total_cases, 4)
    a1_tok = int(a1_metrics["tokens"] / total_cases)
    a1_cost = round(a1_tok * COST_PER_TOKEN, 6)
    a1_calls = round(a1_metrics["tool_calls"] / total_cases, 2)

    return {
        "agentic_comparison": {
            "R0_Deterministic": {
                "top1_accuracy": r0_acc,
                "evidence_recall": r0_rec,
                "latency_ms": r0_lat,
                "cost_usd": r0_cost,
                "token_spend": r0_tok,
                "tool_calls_made": 0
            },
            "C1_Fixed_Workflow": {
                "top1_accuracy": c1_acc,
                "evidence_recall": c1_rec,
                "latency_ms": c1_lat,
                "cost_usd": c1_cost,
                "token_spend": c1_tok,
                "tool_calls_made": 0
            },
            "A1_Bounded_Dynamic": {
                "top1_accuracy": a1_acc,
                "evidence_recall": a1_rec,
                "latency_ms": a1_lat,
                "cost_usd": a1_cost,
                "token_spend": a1_tok,
                "tool_calls_made": a1_calls
            }
        }
    }


if __name__ == "__main__":
    res = run_unbiased_agentic_evaluation()
    print("Agentic Evaluation Results:", res)

