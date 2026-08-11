import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.r0 import R0DeterministicInvestigator
from src.reliability.investigation.c1 import C1FixedInvestigator
from src.reliability.investigation.a1 import A1BoundedInvestigator

# Standard benchmark token pricing ($2.00 per 1M tokens)
COST_PER_TOKEN = 0.000002


def run_unbiased_agentic_evaluation(save_artifact: bool = True) -> Dict[str, Any]:
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
            "ground_truth_evidence": {"ev-bms-10", "ev-contract-VIN-010", "ev-dq-violations-VIN-010"}
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
            "ground_truth_evidence": {"ev-trip-20", "ev-contract-VIN-020", "ev-dq-violations-VIN-020"}
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

    r0_metrics: Dict[str, Any] = {
        "correct": 0,
        "total_tp_ev": 0,
        "total_cited_ev": 0,
        "evidence_recalls": [],
        "unsupported_claims": 0,
        "total_claims": 0,
        "latency_ms": [],
        "tokens": 0,
        "tool_calls": 0
    }
    c1_metrics: Dict[str, Any] = {
        "correct": 0,
        "total_tp_ev": 0,
        "total_cited_ev": 0,
        "evidence_recalls": [],
        "unsupported_claims": 0,
        "total_claims": 0,
        "latency_ms": [],
        "tokens": 0,
        "tool_calls": 0
    }
    a1_metrics: Dict[str, Any] = {
        "correct": 0,
        "total_tp_ev": 0,
        "total_cited_ev": 0,
        "evidence_recalls": [],
        "unsupported_claims": 0,
        "total_claims": 0,
        "latency_ms": [],
        "tokens": 0,
        "tool_calls": 0
    }

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

        cls_r0 = hyp_r0.classification if hyp_r0 else "UNKNOWN"
        if cls_r0 == gt_cls:
            r0_metrics["correct"] += 1

        r0_ev_set = set(hyp_r0.supporting_evidence) if hyp_r0 and hyp_r0.supporting_evidence else set()
        r0_tp = len(r0_ev_set.intersection(gt_ev))
        r0_cited = len(r0_ev_set)
        r0_metrics["total_tp_ev"] += r0_tp
        r0_metrics["total_cited_ev"] += r0_cited

        r0_recall = len(r0_ev_set.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0
        r0_metrics["evidence_recalls"].append(r0_recall)

        if cls_r0 != "UNKNOWN":
            r0_metrics["total_claims"] += 1
            if gt_cls == "UNKNOWN" or r0_cited == 0 or (gt_ev and r0_tp == 0):
                r0_metrics["unsupported_claims"] += 1

        # --- Evaluate C1 Fixed Workflow ---
        t0 = time.perf_counter()
        hyp_c1, rec_c1 = c1.investigate_incident(inc, initial_ev)
        t_c1 = (time.perf_counter() - t0) * 1000.0
        c1_metrics["latency_ms"].append(t_c1)

        cls_c1 = hyp_c1.classification if hyp_c1 else "UNKNOWN"
        if cls_c1 == gt_cls:
            c1_metrics["correct"] += 1

        c1_ev_set = set(hyp_c1.supporting_evidence) if hyp_c1 and hyp_c1.supporting_evidence else set()
        c1_tp = len(c1_ev_set.intersection(gt_ev))
        c1_cited = len(c1_ev_set)
        c1_metrics["total_tp_ev"] += c1_tp
        c1_metrics["total_cited_ev"] += c1_cited

        c1_recall = len(c1_ev_set.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0
        c1_metrics["evidence_recalls"].append(c1_recall)
        c1_tokens = sum(len(e.summary.split()) * 4 for e in initial_ev) + 150
        c1_metrics["tokens"] += c1_tokens

        if cls_c1 != "UNKNOWN":
            c1_metrics["total_claims"] += 1
            if gt_cls == "UNKNOWN" or c1_cited == 0 or (gt_ev and c1_tp == 0):
                c1_metrics["unsupported_claims"] += 1

        # --- Evaluate A1 Bounded Dynamic ---
        t0 = time.perf_counter()
        hyp_a1, rec_a1, meta_a1 = a1.investigate_incident_dynamically(inc, initial_ev)
        t_a1 = (time.perf_counter() - t0) * 1000.0
        a1_metrics["latency_ms"].append(t_a1)

        cls_a1 = hyp_a1.classification if hyp_a1 else "UNKNOWN"
        if cls_a1 == gt_cls:
            a1_metrics["correct"] += 1

        a1_ev_set = set(hyp_a1.supporting_evidence) if hyp_a1 and hyp_a1.supporting_evidence else set()
        a1_tp = len(a1_ev_set.intersection(gt_ev))
        a1_cited = len(a1_ev_set)
        a1_metrics["total_tp_ev"] += a1_tp
        a1_metrics["total_cited_ev"] += a1_cited

        a1_recall = len(a1_ev_set.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0
        a1_metrics["evidence_recalls"].append(a1_recall)
        a1_metrics["tokens"] += meta_a1.get("tokens_spent", 0)
        a1_metrics["tool_calls"] += meta_a1.get("tool_calls_made", 0)

        if cls_a1 != "UNKNOWN":
            a1_metrics["total_claims"] += 1
            if gt_cls == "UNKNOWN" or a1_cited == 0 or (gt_ev and a1_tp == 0):
                a1_metrics["unsupported_claims"] += 1

    # Compute empirical aggregates
    r0_acc = round(r0_metrics["correct"] / total_cases, 4)
    r0_prec = round(r0_metrics["total_tp_ev"] / r0_metrics["total_cited_ev"], 4) if r0_metrics["total_cited_ev"] > 0 else 1.0
    r0_rec = round(sum(r0_metrics["evidence_recalls"]) / total_cases, 4)
    r0_unsup = round(r0_metrics["unsupported_claims"] / r0_metrics["total_claims"], 4) if r0_metrics["total_claims"] > 0 else 0.0
    r0_lat = round(sum(r0_metrics["latency_ms"]) / total_cases, 4)
    r0_tok = int(r0_metrics["tokens"] / total_cases)
    r0_cost = round(r0_tok * COST_PER_TOKEN, 6)

    c1_acc = round(c1_metrics["correct"] / total_cases, 4)
    c1_prec = round(c1_metrics["total_tp_ev"] / c1_metrics["total_cited_ev"], 4) if c1_metrics["total_cited_ev"] > 0 else 1.0
    c1_rec = round(sum(c1_metrics["evidence_recalls"]) / total_cases, 4)
    c1_unsup = round(c1_metrics["unsupported_claims"] / c1_metrics["total_claims"], 4) if c1_metrics["total_claims"] > 0 else 0.0
    c1_lat = round(sum(c1_metrics["latency_ms"]) / total_cases, 4)
    c1_tok = int(c1_metrics["tokens"] / total_cases)
    c1_cost = round(c1_tok * COST_PER_TOKEN, 6)

    a1_acc = round(a1_metrics["correct"] / total_cases, 4)
    a1_prec = round(a1_metrics["total_tp_ev"] / a1_metrics["total_cited_ev"], 4) if a1_metrics["total_cited_ev"] > 0 else 1.0
    a1_rec = round(sum(a1_metrics["evidence_recalls"]) / total_cases, 4)
    a1_unsup = round(a1_metrics["unsupported_claims"] / a1_metrics["total_claims"], 4) if a1_metrics["total_claims"] > 0 else 0.0
    a1_lat = round(sum(a1_metrics["latency_ms"]) / total_cases, 4)
    a1_tok = int(a1_metrics["tokens"] / total_cases)
    a1_cost = round(a1_tok * COST_PER_TOKEN, 6)
    a1_calls = round(a1_metrics["tool_calls"] / total_cases, 2)

    a1_prec_pass = bool(a1_prec >= 0.90)
    a1_unsup_pass = bool(a1_unsup <= 0.05)
    a1_safety_pass = bool(a1_prec_pass and a1_unsup_pass)

    res = {
        "agentic_comparison": {
            "R0_Deterministic": {
                "top1_accuracy": r0_acc,
                "evidence_precision": r0_prec,
                "evidence_recall": r0_rec,
                "unsupported_claim_rate": r0_unsup,
                "latency_ms": r0_lat,
                "cost_usd": r0_cost,
                "token_spend": r0_tok,
                "tool_calls_made": 0
            },
            "C1_Fixed_Workflow": {
                "top1_accuracy": c1_acc,
                "evidence_precision": c1_prec,
                "evidence_recall": c1_rec,
                "unsupported_claim_rate": c1_unsup,
                "latency_ms": c1_lat,
                "cost_usd": c1_cost,
                "token_spend": c1_tok,
                "tool_calls_made": 0
            },
            "A1_Bounded_Dynamic": {
                "top1_accuracy": a1_acc,
                "evidence_precision": a1_prec,
                "evidence_recall": a1_rec,
                "unsupported_claim_rate": a1_unsup,
                "latency_ms": a1_lat,
                "cost_usd": a1_cost,
                "token_spend": a1_tok,
                "tool_calls_made": a1_calls
            }
        },
        "safety_guardrails": {
            "A1_evidence_precision_min_target": 0.90,
            "A1_evidence_precision_passed": a1_prec_pass,
            "A1_unsupported_claim_rate_max_target": 0.05,
            "A1_unsupported_claim_rate_passed": a1_unsup_pass,
            "A1_safety_guardrails_passed": a1_safety_pass
        }
    }

    if save_artifact:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        artifact_path = results_dir / f"eval_agentic_{timestamp_str}.json"
        
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **res
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Saved evaluation artifact to {artifact_path}")

    return res


if __name__ == "__main__":
    res = run_unbiased_agentic_evaluation()
    print("Agentic Evaluation Results:", res)

