import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.investigation.c1 import C1FixedInvestigator


@dataclass
class RCAGroundTruthCase:
    case_id: str
    incident: Incident
    available_evidence: List[Evidence]
    expected_classification: str
    expected_top_causes: List[str]
    ground_truth_evidence_ids: List[str]
    is_abstention_case: bool = False


def get_hidden_rca_ground_truth_cases() -> List[RCAGroundTruthCase]:
    """
    Returns hidden ground-truth evaluation cases for Root Cause Analysis (RCA) bench.
    Covers operational defects, data pipeline contract errors, ambiguous incidents, and abstention cases.
    """
    now = datetime.now(timezone.utc)

    # Case 1: Critical Battery Thermal Anomaly (Operational)
    c1_inc = Incident(
        incident_id="inc-rca-001",
        project_id="proj-eval",
        entity_ids=["VIN-010"],
        signal_ids=["sig-thermal-01"],
        admission_reason="High severity battery temperature spike",
        severity="CRITICAL"
    )
    c1_ev1 = Evidence(
        evidence_id="ev-rca-001",
        source_type="telemetry",
        source_id="bms-10",
        entity_ids=["VIN-010"],
        content_hash="hash01",
        summary="Critical battery temperature rise and thermal degradation"
    )
    c1_ev_noise = Evidence(
        evidence_id="ev-noise-001",
        source_type="telemetry",
        source_id="bms-99",
        entity_ids=["VIN-999"],
        content_hash="hash02",
        summary="Unrelated telemetry for another vehicle"
    )

    # Case 2: Negative Trip Fare Anomaly (Data)
    c2_inc = Incident(
        incident_id="inc-rca-002",
        project_id="proj-eval",
        entity_ids=["TRIP-501"],
        signal_ids=["sig-fare-01"],
        admission_reason="Negative fare amount detected in billing",
        severity="HIGH"
    )
    c2_ev = Evidence(
        evidence_id="ev-rca-002",
        source_type="database",
        source_id="xanhsm-db",
        entity_ids=["TRIP-501"],
        content_hash="hash03",
        summary="Negative fare calculation and arithmetic schema defect"
    )

    # Case 3: Missing Evidence Incident (Abstention)
    c3_inc = Incident(
        incident_id="inc-rca-003",
        project_id="proj-eval",
        entity_ids=["VIN-030"],
        signal_ids=["sig-unknown-01"],
        admission_reason="Unexplained alert with zero telemetry data",
        severity="MEDIUM"
    )

    # Case 4: Low SOC Voltage Degradation (Operational)
    c4_inc = Incident(
        incident_id="inc-rca-004",
        project_id="proj-eval",
        entity_ids=["VIN-040"],
        signal_ids=["sig-voltage-01"],
        admission_reason="Rapid voltage drop under load",
        severity="HIGH"
    )
    c4_ev1 = Evidence(
        evidence_id="ev-rca-004a",
        source_type="telemetry",
        source_id="bms-40",
        entity_ids=["VIN-040"],
        content_hash="hash04",
        summary="Battery SOC voltage collapse under peak load"
    )
    c4_ev2 = Evidence(
        evidence_id="ev-rca-004b",
        source_type="logs",
        source_id="sys-40",
        entity_ids=["VIN-040"],
        content_hash="hash05",
        summary="Routine maintenance inspection logged"
    )

    # Case 5: Type Mismatch Data Pipeline Error (Data)
    c5_inc = Incident(
        incident_id="inc-rca-005",
        project_id="proj-eval",
        entity_ids=["STATION-102"],
        signal_ids=["sig-type-01"],
        admission_reason="Non-numeric string in power measurement field",
        severity="CRITICAL"
    )
    c5_ev = Evidence(
        evidence_id="ev-rca-005",
        source_type="pipeline",
        source_id="ingest-01",
        entity_ids=["STATION-102"],
        content_hash="hash06",
        summary="Type casting failure string value injected into null column"
    )

    # Case 6: Ambiguous Incident Summary (Abstention)
    c6_inc = Incident(
        incident_id="inc-rca-006",
        project_id="proj-eval",
        entity_ids=["VIN-060"],
        signal_ids=["sig-ambig-01"],
        admission_reason="General operational warning without clear diagnostic signal",
        severity="LOW"
    )
    c6_ev = Evidence(
        evidence_id="ev-rca-006",
        source_type="telemetry",
        source_id="bms-60",
        entity_ids=["VIN-060"],
        content_hash="hash07",
        summary="Routine system ping normal response"
    )

    # Case 7: High Severity Battery Cell Degradation (Operational)
    c7_inc = Incident(
        incident_id="inc-rca-007",
        project_id="proj-eval",
        entity_ids=["VIN-070"],
        signal_ids=["sig-batt-02"],
        admission_reason="Cell balance failure and thermal run-away risk",
        severity="CRITICAL"
    )
    c7_ev1 = Evidence(
        evidence_id="ev-rca-007a",
        source_type="telemetry",
        source_id="bms-70",
        entity_ids=["VIN-070"],
        content_hash="hash08",
        summary="Thermal imbalance and battery cell degradation"
    )
    c7_ev2 = Evidence(
        evidence_id="ev-rca-007b",
        source_type="telemetry",
        source_id="bms-70-b",
        entity_ids=["VIN-070"],
        content_hash="hash09",
        summary="Critical battery voltage anomaly"
    )

    # Case 8: Null Constraint Pipeline Violation (Data)
    c8_inc = Incident(
        incident_id="inc-rca-008",
        project_id="proj-eval",
        entity_ids=["FEEDBACK-88"],
        signal_ids=["sig-null-01"],
        admission_reason="Null driver ID in ride feedback",
        severity="HIGH"
    )
    c8_ev = Evidence(
        evidence_id="ev-rca-008",
        source_type="database",
        source_id="feedback-db",
        entity_ids=["FEEDBACK-88"],
        content_hash="hash10",
        summary="Null constraint violation in feedback table"
    )

    # Case 9: Misleading Keyword False Claim Test (Abstention)
    c9_inc = Incident(
        incident_id="inc-rca-009",
        project_id="proj-eval",
        entity_ids=["VIN-090"],
        signal_ids=["sig-noise-01"],
        admission_reason="Unknown status report",
        severity="LOW"
    )
    c9_ev = Evidence(
        evidence_id="ev-rca-009",
        source_type="telemetry",
        source_id="bms-90",
        entity_ids=["VIN-090"],
        content_hash="hash11",
        summary="Driver reported comfortable temperature inside cabin"
    )

    # Case 10: Multi-domain Data Defect (Data)
    c10_inc = Incident(
        incident_id="inc-rca-010",
        project_id="proj-eval",
        entity_ids=["VIN-100"],
        signal_ids=["sig-mixed-01"],
        admission_reason="Combined sensor failure and arithmetic null error",
        severity="CRITICAL"
    )
    c10_ev = Evidence(
        evidence_id="ev-rca-010",
        source_type="telemetry",
        source_id="bms-100",
        entity_ids=["VIN-100"],
        content_hash="hash12",
        summary="Negative fare calculation and arithmetic type defect in log"
    )

    return [
        RCAGroundTruthCase(
            case_id="RCAC-001",
            incident=c1_inc,
            available_evidence=[c1_ev1, c1_ev_noise],
            expected_classification="OPERATIONAL",
            expected_top_causes=["OPERATIONAL"],
            ground_truth_evidence_ids=["ev-rca-001"],
            is_abstention_case=False
        ),
        RCAGroundTruthCase(
            case_id="RCAC-002",
            incident=c2_inc,
            available_evidence=[c2_ev],
            expected_classification="DATA",
            expected_top_causes=["DATA"],
            ground_truth_evidence_ids=["ev-rca-002"],
            is_abstention_case=False
        ),
        RCAGroundTruthCase(
            case_id="RCAC-003",
            incident=c3_inc,
            available_evidence=[],
            expected_classification="UNKNOWN",
            expected_top_causes=["UNKNOWN"],
            ground_truth_evidence_ids=[],
            is_abstention_case=True
        ),
        RCAGroundTruthCase(
            case_id="RCAC-004",
            incident=c4_inc,
            available_evidence=[c4_ev1, c4_ev2],
            expected_classification="OPERATIONAL",
            expected_top_causes=["OPERATIONAL"],
            ground_truth_evidence_ids=["ev-rca-004a"],
            is_abstention_case=False
        ),
        RCAGroundTruthCase(
            case_id="RCAC-005",
            incident=c5_inc,
            available_evidence=[c5_ev],
            expected_classification="DATA",
            expected_top_causes=["DATA"],
            ground_truth_evidence_ids=["ev-rca-005"],
            is_abstention_case=False
        ),
        RCAGroundTruthCase(
            case_id="RCAC-006",
            incident=c6_inc,
            available_evidence=[c6_ev],
            expected_classification="UNKNOWN",
            expected_top_causes=["UNKNOWN"],
            ground_truth_evidence_ids=[],
            is_abstention_case=True
        ),
        RCAGroundTruthCase(
            case_id="RCAC-007",
            incident=c7_inc,
            available_evidence=[c7_ev1, c7_ev2],
            expected_classification="OPERATIONAL",
            expected_top_causes=["OPERATIONAL"],
            ground_truth_evidence_ids=["ev-rca-007a", "ev-rca-007b"],
            is_abstention_case=False
        ),
        RCAGroundTruthCase(
            case_id="RCAC-008",
            incident=c8_inc,
            available_evidence=[c8_ev],
            expected_classification="DATA",
            expected_top_causes=["DATA"],
            ground_truth_evidence_ids=["ev-rca-008"],
            is_abstention_case=False
        ),
        RCAGroundTruthCase(
            case_id="RCAC-009",
            incident=c9_inc,
            available_evidence=[c9_ev],
            expected_classification="UNKNOWN",
            expected_top_causes=["UNKNOWN"],
            ground_truth_evidence_ids=[],
            is_abstention_case=True
        ),
        RCAGroundTruthCase(
            case_id="RCAC-010",
            incident=c10_inc,
            available_evidence=[c10_ev],
            expected_classification="DATA",
            expected_top_causes=["DATA", "OPERATIONAL"],
            ground_truth_evidence_ids=["ev-rca-010"],
            is_abstention_case=False
        ),
    ]


def run_rca_evaluation(
    investigator: Any = None,
    cases: Optional[List[RCAGroundTruthCase]] = None,
    save_artifact: bool = True
) -> Dict[str, Any]:
    """
    Evaluates Root Cause Analysis (RCA) hypothesis accuracy, evidence precision, recall,
    unsupported claim rates, and abstention precision dynamically against ground-truth cases.
    """
    if investigator is None:
        investigator = C1FixedInvestigator()

    if cases is None:
        cases = get_hidden_rca_ground_truth_cases()

    total_cases = len(cases)
    if total_cases == 0:
        res = {
            "rca_evaluation": {
                "top1_cause_accuracy": 0.0,
                "top3_cause_recall": 0.0,
                "evidence_precision": 0.0,
                "evidence_recall": 0.0,
                "unsupported_claim_rate": 0.0,
                "abstention_precision": 0.0
            },
            "safety_guardrails": {
                "evidence_precision_min_target": 0.90,
                "evidence_precision_passed": False,
                "unsupported_claim_rate_max_target": 0.05,
                "unsupported_claim_rate_passed": True,
                "safety_guardrails_passed": False
            }
        }
        if save_artifact:
            results_dir = Path(__file__).parent / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            artifact_path = results_dir / f"eval_rca_{timestamp_str}.json"
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **res
            }
            with open(artifact_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"Saved evaluation artifact to {artifact_path}")
        return res

    correct_top1 = 0
    correct_top3 = 0

    total_tp_ev = 0
    total_fp_ev = 0
    total_fn_ev = 0

    unsupported_claims = 0
    non_abstain_predictions = 0

    correct_abstentions = 0
    total_abstain_predictions = 0

    for case in cases:
        res_inv = investigator.investigate_incident(case.incident, case.available_evidence)
        if isinstance(res_inv, tuple):
            hyp = res_inv[0]
        else:
            hyp = res_inv

        classification = hyp.classification if hyp else "UNKNOWN"
        supporting_ev = hyp.supporting_evidence if hyp else []

        # Top-1 cause accuracy
        if classification == case.expected_classification:
            correct_top1 += 1

        # Top-3 cause recall
        if classification in case.expected_top_causes:
            correct_top3 += 1

        # Evidence precision and recall
        pred_ev_set = set(supporting_ev)
        gt_ev_set = set(case.ground_truth_evidence_ids)

        tp = len(pred_ev_set.intersection(gt_ev_set))
        fp = len(pred_ev_set.difference(gt_ev_set))
        fn = len(gt_ev_set.difference(pred_ev_set))

        total_tp_ev += tp
        total_fp_ev += fp
        total_fn_ev += fn

        # Unsupported claim evaluation
        if classification != "UNKNOWN":
            non_abstain_predictions += 1
            if case.expected_classification == "UNKNOWN" or len(pred_ev_set) == 0 or (gt_ev_set and tp == 0):
                unsupported_claims += 1

        # Abstention precision evaluation
        if classification == "UNKNOWN":
            total_abstain_predictions += 1
            if case.is_abstention_case or case.expected_classification == "UNKNOWN":
                correct_abstentions += 1

    top1_acc = round(correct_top1 / total_cases, 4)
    top3_rec = round(correct_top3 / total_cases, 4)

    ev_prec = round(total_tp_ev / (total_tp_ev + total_fp_ev), 4) if (total_tp_ev + total_fp_ev) > 0 else 1.0
    ev_rec = round(total_tp_ev / (total_tp_ev + total_fn_ev), 4) if (total_tp_ev + total_fn_ev) > 0 else 1.0

    unsup_rate = round(unsupported_claims / non_abstain_predictions, 4) if non_abstain_predictions > 0 else 0.0
    abst_prec = round(correct_abstentions / total_abstain_predictions, 4) if total_abstain_predictions > 0 else 1.0

    ev_prec_pass = bool(ev_prec >= 0.90)
    unsup_rate_pass = bool(unsup_rate <= 0.05)
    safety_guardrails_passed = bool(ev_prec_pass and unsup_rate_pass)

    res = {
        "rca_evaluation": {
            "top1_cause_accuracy": top1_acc,
            "top3_cause_recall": top3_rec,
            "evidence_precision": ev_prec,
            "evidence_recall": ev_rec,
            "unsupported_claim_rate": unsup_rate,
            "abstention_precision": abst_prec
        },
        "safety_guardrails": {
            "evidence_precision_min_target": 0.90,
            "evidence_precision_passed": ev_prec_pass,
            "unsupported_claim_rate_max_target": 0.05,
            "unsupported_claim_rate_passed": unsup_rate_pass,
            "safety_guardrails_passed": safety_guardrails_passed
        }
    }

    if save_artifact:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        artifact_path = results_dir / f"eval_rca_{timestamp_str}.json"
        
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **res
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Saved evaluation artifact to {artifact_path}")

    return res


if __name__ == "__main__":
    res = run_rca_evaluation()
    print("RCA Evaluation Results:", res)

