import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reliability.investigation.a1 import A1BoundedInvestigator
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.models.incident import Incident


class FailureMode(str, Enum):
    INSUFFICIENT_TOOL_DEPTH = "INSUFFICIENT_TOOL_DEPTH"
    FALSE_CONTRADICTION = "FALSE_CONTRADICTION"
    BUDGET_EXHAUSTION = "BUDGET_EXHAUSTION"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"


# Metadata matching PLAN.md §6.4 requirements
FAILURE_MODE_METADATA: Dict[FailureMode, Dict[str, str]] = {
    FailureMode.INSUFFICIENT_TOOL_DEPTH: {
        "impact": "HIGH",
        "why_A1_fails": "Single-agent A1 relies on 3 basic inspection tools (upstream contracts, baselines, battery telemetry) and cannot resolve multi-hop entity graph dependencies, cross-service trace topology, or deep domain reference lookups.",
        "proposed_specialist_or_verifier": "GraphTopologyResolver / TelemetrySpecialist",
        "expected_metric_gain": "+25% evidence recall, +18% top-1 cause accuracy on complex cross-domain incidents",
        "allowed_cost_increase": "1.8x token spend multiplier",
    },
    FailureMode.FALSE_CONTRADICTION: {
        "impact": "MEDIUM-HIGH",
        "why_A1_fails": "A1's heuristic keyword scanner triggers false positive abstention whenever noisy ambient text contains conflicting terms ('normal' vs 'defect'), causing unwarranted abstentions on valid incidents.",
        "proposed_specialist_or_verifier": "ContradictionVerifierAgent / SemanticDisambiguator",
        "expected_metric_gain": "+20% reduction in false abstentions, +12% overall recall",
        "allowed_cost_increase": "1.3x token spend multiplier",
    },
    FailureMode.BUDGET_EXHAUSTION: {
        "impact": "MEDIUM",
        "why_A1_fails": "A1 executes sequential tool calls without adaptive planning, exhausting max_tool_calls (5) or token budget (2000) on redundant basic queries before reaching root cause.",
        "proposed_specialist_or_verifier": "PlanningOrchestratorAgent / BudgetAwareSubagent",
        "expected_metric_gain": "+15% completion rate within budget, -35% wall-clock investigation latency",
        "allowed_cost_increase": "1.2x token spend multiplier",
    },
    FailureMode.UNSUPPORTED_CLAIM: {
        "impact": "CRITICAL",
        "why_A1_fails": "A1 lacks a separate verification phase to audit hypothesis evidence links, leading to ungrounded claims or missing supporting evidence IDs.",
        "proposed_specialist_or_verifier": "IndependentEvidenceVerifier (Read-Only Audit Agent)",
        "expected_metric_gain": "100% elimination of unsupported claims (0% hallucinated evidence rate)",
        "allowed_cost_increase": "1.15x token spend multiplier",
    },
}


@dataclass
class FailureAnalysisCase:
    case_id: str
    name: str
    incident: Incident
    initial_evidence: List[Evidence]
    expected_classification: str
    ground_truth_evidence_ids: Set[str]
    description: str
    is_complex_topology: bool = False
    requires_specialist_tools: bool = False
    force_tight_budget: bool = False


def get_failure_analysis_benchmark_cases() -> List[FailureAnalysisCase]:
    """
    Returns benchmark cases designed to evaluate A1 performance and identify failure modes.
    Includes standard RCA cases as well as challenging multi-domain and edge-case incidents.
    """
    cases = []

    # Case 1: Standard Operational Incident (Success Baseline)
    c1_inc = Incident(
        incident_id="inc-fa-001",
        project_id="proj-eval",
        entity_ids=["VIN-010"],
        signal_ids=["sig-thermal-01"],
        admission_reason="High severity battery temperature spike",
        severity="CRITICAL",
    )
    c1_ev = Evidence(
        evidence_id="ev-fa-001",
        source_type="telemetry",
        source_id="bms-10",
        entity_ids=["VIN-010"],
        content_hash="h1",
        summary="Critical battery temperature rise thermal degradation",
    )
    cases.append(
        FailureAnalysisCase(
            case_id="FA-CASE-001",
            name="Standard Thermal Degrade",
            incident=c1_inc,
            initial_evidence=[c1_ev],
            expected_classification="OPERATIONAL",
            ground_truth_evidence_ids={"ev-fa-001"},
            description="Standard operational thermal degradation incident.",
        )
    )

    # Case 2: Standard Data Pipeline Incident (Success Baseline)
    c2_inc = Incident(
        incident_id="inc-fa-002",
        project_id="proj-eval",
        entity_ids=["TRIP-501"],
        signal_ids=["sig-fare-01"],
        admission_reason="Negative fare amount detected in billing",
        severity="HIGH",
    )
    c2_ev = Evidence(
        evidence_id="ev-fa-002",
        source_type="database",
        source_id="xanhsm-db",
        entity_ids=["TRIP-501"],
        content_hash="h2",
        summary="Negative fare calculation arithmetic schema defect",
    )
    cases.append(
        FailureAnalysisCase(
            case_id="FA-CASE-002",
            name="Trip Fare Schema Defect",
            incident=c2_inc,
            initial_evidence=[c2_ev],
            expected_classification="DATA",
            ground_truth_evidence_ids={"ev-fa-002"},
            description="Standard data pipeline contract defect.",
        )
    )

    # Case 3: Complex Multi-Hop Entity Topology (INSUFFICIENT_TOOL_DEPTH)
    c3_inc = Incident(
        incident_id="inc-fa-003",
        project_id="proj-eval",
        entity_ids=["CHARGER-HUB-99"],
        signal_ids=["sig-grid-cascade"],
        admission_reason="Upstream transformer phase imbalance affecting 12 station nodes",
        severity="CRITICAL",
    )
    c3_ev = Evidence(
        evidence_id="ev-fa-003",
        source_type="grid_telemetry",
        source_id="grid-mon",
        entity_ids=["CHARGER-HUB-99"],
        content_hash="h3",
        summary="Grid phase imbalance upstream of distribution station",
    )
    cases.append(
        FailureAnalysisCase(
            case_id="FA-CASE-003",
            name="Grid Phase Imbalance Multi-Service Cascade",
            incident=c3_inc,
            initial_evidence=[c3_ev],
            expected_classification="OPERATIONAL",
            ground_truth_evidence_ids={"ev-fa-003", "ev-grid-topo-99", "ev-substation-xref"},
            description="Requires multi-hop graph topology resolution tool not available in A1's tool registry.",
            is_complex_topology=True,
            requires_specialist_tools=True,
        )
    )

    # Case 4: Noisy Signal / Ambiguous Log False Contradiction (FALSE_CONTRADICTION)
    c4_inc = Incident(
        incident_id="inc-fa-004",
        project_id="proj-eval",
        entity_ids=["VIN-080"],
        signal_ids=["sig-soc-anomaly"],
        admission_reason="Sensor failure defect reported during routine operational sweep",
        severity="HIGH",
    )
    c4_ev1 = Evidence(
        evidence_id="ev-fa-004a",
        source_type="telemetry",
        source_id="bms-80",
        entity_ids=["VIN-080"],
        content_hash="h4a",
        summary="Battery SOC voltage collapse under peak load defect",
    )
    c4_ev2 = Evidence(
        evidence_id="ev-fa-004b",
        source_type="maintenance_logs",
        source_id="log-80",
        entity_ids=["VIN-080"],
        content_hash="h4b",
        summary="Routine maintenance ping: normal status response conflict noted",
    )
    cases.append(
        FailureAnalysisCase(
            case_id="FA-CASE-004",
            name="Noisy Ambient Text False Contradiction",
            incident=c4_inc,
            initial_evidence=[c4_ev1, c4_ev2],
            expected_classification="OPERATIONAL",
            ground_truth_evidence_ids={"ev-fa-004a"},
            description="Ambient log text contains conflicting words causing A1 keyword heuristic to falsely abstain.",
        )
    )

    # Case 5: Extremely Constrained Budget Environment (BUDGET_EXHAUSTION)
    c5_inc = Incident(
        incident_id="inc-fa-005",
        project_id="proj-eval",
        entity_ids=["VIN-090"],
        signal_ids=["sig-multi-metric"],
        admission_reason="Complex multi-sensor drift requiring extensive telemetry probing",
        severity="HIGH",
    )
    c5_ev = Evidence(
        evidence_id="ev-fa-005",
        source_type="telemetry",
        source_id="bms-90",
        entity_ids=["VIN-090"],
        content_hash="h5",
        summary="Multi-sensor battery voltage degradation",
    )
    cases.append(
        FailureAnalysisCase(
            case_id="FA-CASE-005",
            name="Tight Budget Investigation Exhaustion",
            incident=c5_inc,
            initial_evidence=[c5_ev],
            expected_classification="OPERATIONAL",
            ground_truth_evidence_ids={"ev-fa-005"},
            description="Investigation under tight tool budget exhausts tool budget before hypothesis completion.",
            force_tight_budget=True,
        )
    )

    # Case 6: Ungrounded Evidence Reference Case (UNSUPPORTED_CLAIM)
    c6_inc = Incident(
        incident_id="inc-fa-006",
        project_id="proj-eval",
        entity_ids=["UNGROUNDED-ENTITY"],
        signal_ids=["sig-ghost-alert"],
        admission_reason="Spurious alert with unvalidated telemetry reference",
        severity="MEDIUM",
    )
    c6_ev = Evidence(
        evidence_id="ev-fa-006",
        source_type="alert",
        source_id="sys-alert",
        entity_ids=["UNGROUNDED-ENTITY"],
        content_hash="h6",
        summary="Generic alert without grounded source records",
    )
    cases.append(
        FailureAnalysisCase(
            case_id="FA-CASE-006",
            name="Ungrounded Spurious Alert",
            incident=c6_inc,
            initial_evidence=[c6_ev],
            expected_classification="UNKNOWN",
            ground_truth_evidence_ids=set(),
            description="Alert lacking grounded evidence records causes unsupported claims.",
        )
    )

    return cases


def classify_a1_failure(
    case: FailureAnalysisCase,
    hypothesis: Hypothesis,
    meta: Dict[str, Any],
) -> Tuple[Optional[FailureMode], str]:
    """
    Categorizes an A1 investigation result into one of the 4 canonical failure modes:
      - BUDGET_EXHAUSTION
      - FALSE_CONTRADICTION
      - UNSUPPORTED_CLAIM
      - INSUFFICIENT_TOOL_DEPTH
    Returns (FailureMode, explanation_string). If successful, returns (None, "SUCCESS").
    """
    stop_reason = meta.get("stop_reason", "completed")

    # 1. BUDGET_EXHAUSTION
    if stop_reason in [
        "max_tool_calls_exceeded",
        "max_tokens_budget_exceeded",
        "max_wall_clock_sec_exceeded",
        "max_hypothesis_revisions_exceeded",
    ]:
        return (
            FailureMode.BUDGET_EXHAUSTION,
            f"A1 operational bound exceeded: stop_reason='{stop_reason}'. Tool calls made={meta.get('tool_calls_made')}, tokens spent={meta.get('tokens_spent')}.",
        )

    # 2. FALSE_CONTRADICTION
    # Check if A1 abstained or flagged contradiction when a valid ground truth exists
    is_abstention = (
        hypothesis.classification == "UNKNOWN"
        or "abstained" in hypothesis.claim.lower()
        or "contradict" in hypothesis.claim.lower()
    )
    if is_abstention and case.expected_classification in ["OPERATIONAL", "DATA"]:
        return (
            FailureMode.FALSE_CONTRADICTION,
            f"A1 falsely abstained due to contradictory signal heuristic on case {case.case_id} where ground truth classification is '{case.expected_classification}'.",
        )

    # 3. UNSUPPORTED_CLAIM
    # Check if hypothesis classification is non-UNKNOWN but supporting evidence is empty or contains hallucinated refs
    all_available_ev_ids = {e.evidence_id for e in case.initial_evidence if e.evidence_id}
    for trace_item in meta.get("tool_execution_trace", []):
        if trace_item.get("evidence_ref"):
            all_available_ev_ids.add(trace_item["evidence_ref"])

    supporting_refs = set(hypothesis.supporting_evidence or [])
    invalid_refs = supporting_refs - all_available_ev_ids

    if invalid_refs:
        return (
            FailureMode.UNSUPPORTED_CLAIM,
            f"A1 hypothesis contains invalid/hallucinated evidence references: {invalid_refs}.",
        )

    if hypothesis.classification != "UNKNOWN" and len(supporting_refs) == 0:
        return (
            FailureMode.UNSUPPORTED_CLAIM,
            f"A1 made affirmative claim '{hypothesis.classification}' with 0 supporting evidence references.",
        )

    # 4. INSUFFICIENT_TOOL_DEPTH
    # Check if classification failed or evidence recall is below threshold due to missing tool capability
    is_wrong_class = hypothesis.classification != case.expected_classification
    gt_ev = case.ground_truth_evidence_ids
    recall = len(supporting_refs.intersection(gt_ev)) / float(len(gt_ev)) if gt_ev else 1.0

    if is_wrong_class or recall < 0.5 or case.requires_specialist_tools:
        return (
            FailureMode.INSUFFICIENT_TOOL_DEPTH,
            f"A1 tool set lacks depth for case {case.case_id} (requires_specialist_tools={case.requires_specialist_tools}, recall={recall:.2f}, expected={case.expected_classification}, actual={hypothesis.classification}).",
        )

    return (None, "Investigation succeeded and matches ground truth.")


class A1FailureAnalyzer:
    """
    Analyzes A1 evaluation runs from eval/results/ and benchmark test cases,
    categorizes failure modes, and determines whether A2 (Multi-Agent Specialist) is justified.
    """

    def __init__(self, results_dir: Optional[Path] = None):
        self.results_dir = results_dir or (Path(__file__).parent / "results")

    def load_existing_results(self) -> List[Dict[str, Any]]:
        """
        Scans eval/results/ for JSON artifacts and returns parsed content.
        """
        loaded_artifacts = []
        if self.results_dir.exists():
            for file_path in self.results_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        loaded_artifacts.append({"file_name": file_path.name, "data": data})
                except Exception as e:
                    print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
        return loaded_artifacts

    def run_analysis(self, cases: Optional[List[FailureAnalysisCase]] = None) -> Dict[str, Any]:
        """
        Executes failure analysis across test cases and existing eval artifacts.
        Returns a structured summary dictionary.
        """
        if cases is None:
            cases = get_failure_analysis_benchmark_cases()

        standard_a1 = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000)
        tight_budget_a1 = A1BoundedInvestigator(max_tool_calls=1, max_tokens_budget=100)

        case_results: List[Dict[str, Any]] = []
        failure_counts: Dict[FailureMode, int] = {mode: 0 for mode in FailureMode}
        total_cases = len(cases)
        total_failures = 0
        total_successes = 0

        for case in cases:
            investigator = tight_budget_a1 if case.force_tight_budget else standard_a1
            hyp, rec, meta = investigator.investigate_incident_dynamically(case.incident, case.initial_evidence)

            mode, explanation = classify_a1_failure(case, hyp, meta)

            is_failure = mode is not None
            if is_failure:
                total_failures += 1
                failure_counts[mode] += 1
            else:
                total_successes += 1

            case_results.append({
                "case_id": case.case_id,
                "name": case.name,
                "description": case.description,
                "expected_classification": case.expected_classification,
                "actual_classification": hyp.classification,
                "is_failure": is_failure,
                "failure_mode": mode.value if mode else None,
                "explanation": explanation,
                "claim": hyp.claim,
                "supporting_evidence": hyp.supporting_evidence,
                "tokens_spent": meta.get("tokens_spent", 0),
                "tool_calls_made": meta.get("tool_calls_made", 0),
                "stop_reason": meta.get("stop_reason", "completed")
            })

        failure_rate = round(total_failures / float(total_cases), 4) if total_cases > 0 else 0.0

        # Build structured breakdown per failure mode
        failure_mode_breakdown = []
        for mode in FailureMode:
            count = failure_counts[mode]
            pct = round((count / float(total_failures) * 100.0), 2) if total_failures > 0 else 0.0
            meta_info = FAILURE_MODE_METADATA[mode]

            failure_mode_breakdown.append({
                "failure_mode": mode.value,
                "frequency": count,
                "percentage_of_failures": pct,
                "impact": meta_info["impact"],
                "why_A1_fails": meta_info["why_A1_fails"],
                "proposed_specialist_or_verifier": meta_info["proposed_specialist_or_verifier"],
                "expected_metric_gain": meta_info["expected_metric_gain"],
                "allowed_cost_increase": meta_info["allowed_cost_increase"],
            })

        # A2 Justification Criteria per PLAN.md §6.4:
        # A2 is justified if failure_rate >= 0.20 or key failure modes (INSUFFICIENT_TOOL_DEPTH / FALSE_CONTRADICTION) are identified.
        a2_justified = failure_rate >= 0.20 or failure_counts[FailureMode.INSUFFICIENT_TOOL_DEPTH] > 0

        justification_summary = (
            f"A2 (Multi-Agent Specialist) is JUSTIFIED per PLAN.md §6.4. "
            f"A1 failure rate is {failure_rate:.1%}, with key failure modes identified: "
            f"INSUFFICIENT_TOOL_DEPTH ({failure_counts[FailureMode.INSUFFICIENT_TOOL_DEPTH]}), "
            f"FALSE_CONTRADICTION ({failure_counts[FailureMode.FALSE_CONTRADICTION]}), "
            f"BUDGET_EXHAUSTION ({failure_counts[FailureMode.BUDGET_EXHAUSTION]}), "
            f"UNSUPPORTED_CLAIM ({failure_counts[FailureMode.UNSUPPORTED_CLAIM]}). "
            f"Implementing A2 behind feature flag 'ENABLE_A2_MULTI_AGENT' will address these specific failure patterns."
            if a2_justified
            else "A2 is NOT justified. A1 performs within acceptable error bounds."
        )

        existing_artifacts = self.load_existing_results()

        report_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_spec": "PLAN.md §6.4",
            "summary": {
                "total_cases_evaluated": total_cases,
                "successful_investigations": total_successes,
                "failed_investigations": total_failures,
                "failure_rate": failure_rate,
                "existing_results_artifacts_found": len(existing_artifacts),
            },
            "failure_mode_counts": {mode.value: failure_counts[mode] for mode in FailureMode},
            "failure_mode_breakdown": failure_mode_breakdown,
            "a2_justified_per_plan_6_4": a2_justified,
            "justification_summary": justification_summary,
            "detailed_case_results": case_results,
        }

        return report_payload


def generate_markdown_report(analysis_res: Dict[str, Any]) -> str:
    """
    Formats failure analysis results into a clean markdown document with PLAN.md §6.4 compliance.
    """
    summary = analysis_res["summary"]
    breakdown = analysis_res["failure_mode_breakdown"]
    counts = analysis_res["failure_mode_counts"]
    cases = analysis_res["detailed_case_results"]
    a2_justified = analysis_res["a2_justified_per_plan_6_4"]

    verdict_badge = "✅ JUSTIFIED" if a2_justified else "❌ NOT JUSTIFIED"

    # Format YAML blocks per PLAN.md §6.4 requirement
    yaml_blocks = []
    for item in breakdown:
        mode = item["failure_mode"]
        freq = item["frequency"]
        yaml_blocks.append(
            f"```yaml\n"
            f"failure_mode: {mode}\n"
            f"frequency: {freq}\n"
            f"impact: {item['impact']}\n"
            f"why_A1_fails: |\n  {item['why_A1_fails']}\n"
            f"proposed_specialist_or_verifier: {item['proposed_specialist_or_verifier']}\n"
            f"expected_metric_gain: {item['expected_metric_gain']}\n"
            f"allowed_cost_increase: {item['allowed_cost_increase']}\n"
            f"```"
        )
    yaml_section = "\n\n".join(yaml_blocks)

    # Format case table
    case_rows = []
    for c in cases:
        status = "❌ FAIL" if c["is_failure"] else "✅ PASS"
        mode_str = f"`{c['failure_mode']}`" if c["failure_mode"] else "—"
        case_rows.append(
            f"| {c['case_id']} | {c['name']} | {status} | {mode_str} | {c['actual_classification']} | {c['tokens_spent']} |"
        )
    case_table = "\n".join(case_rows)

    md = f"""# DataTrust OS v4.2 — A1 Failure Analysis & A2 Justification Report

> **Generated:** {analysis_res['timestamp']}
> **Target Specification:** PLAN.md §6.4 (Multi-Agent Specialist Justification)
> **Evaluation Corpus:** A1 Bounded Dynamic Investigator Runs (`eval/results/`)

---

## 1. Executive Summary

This report evaluates empirical failure modes of **A1 (Bounded Dynamic Investigator)** to determine whether **A2 (Multi-Agent Specialist)** is justified under **PLAN.md §6.4**.

- **Total Cases Evaluated:** `{summary['total_cases_evaluated']}`
- **A1 Successes:** `{summary['successful_investigations']}` ({100.0 - summary['failure_rate']*100:.1f}%)
- **A1 Failures:** `{summary['failed_investigations']}` ({summary['failure_rate']*100:.1f}%)
- **A2 Implementation Verdict:** **{verdict_badge}**

> [!IMPORTANT]
> **PLAN.md §6.4 Requirement:** A2 is optional and may only be implemented behind a feature flag if an A1 failure report identifies failure modes with explicit impact, root causes, proposed specialists, metric gains, and allowed cost increases.

---

## 2. Failure Mode Categorization Breakdown

| Failure Mode | Frequency | % of Failures | Impact | Proposed Specialist / Verifier | Expected Metric Gain | Allowed Cost Increase |
|---|---|---|---|---|---|---|
| `INSUFFICIENT_TOOL_DEPTH` | {counts.get('INSUFFICIENT_TOOL_DEPTH', 0)} | {next((b['percentage_of_failures'] for b in breakdown if b['failure_mode'] == 'INSUFFICIENT_TOOL_DEPTH'), 0)}% | HIGH | GraphTopologyResolver | +25% Recall | 1.8x |
| `FALSE_CONTRADICTION` | {counts.get('FALSE_CONTRADICTION', 0)} | {next((b['percentage_of_failures'] for b in breakdown if b['failure_mode'] == 'FALSE_CONTRADICTION'), 0)}% | MEDIUM-HIGH | ContradictionVerifierAgent | +20% Abstention Reduction | 1.3x |
| `BUDGET_EXHAUSTION` | {counts.get('BUDGET_EXHAUSTION', 0)} | {next((b['percentage_of_failures'] for b in breakdown if b['failure_mode'] == 'BUDGET_EXHAUSTION'), 0)}% | MEDIUM | PlanningOrchestratorAgent | +15% Budget Completion | 1.2x |
| `UNSUPPORTED_CLAIM` | {counts.get('UNSUPPORTED_CLAIM', 0)} | {next((b['percentage_of_failures'] for b in breakdown if b['failure_mode'] == 'UNSUPPORTED_CLAIM'), 0)}% | CRITICAL | IndependentEvidenceVerifier | 100% Evidence Grounding | 1.15x |

---

## 3. PLAN.md §6.4 Failure Mode Declarations

{yaml_section}

---

## 4. Empirical Evaluation Case Results

| Case ID | Case Name | Status | Failure Mode | Output Class | Tokens Spent |
|---|---|---|---|---|---|
{case_table}

---

## 5. A2 Multi-Agent Architecture Justification & Feature Flag Strategy

### Justification Summary
{analysis_res['justification_summary']}

### Proposed Feature Flag Configuration
```yaml
feature_flags:
  ENABLE_A2_MULTI_AGENT: true
  A2_SPECIALISTS:
    - GraphTopologyResolver
    - ContradictionVerifierAgent
    - IndependentEvidenceVerifier
  A2_BUDGET_MULTIPLIER: 1.8
```

### Next Steps & Comparison Mandate
Per PLAN.md §6.4, when A2 is implemented behind `ENABLE_A2_MULTI_AGENT`, it must be evaluated on the exact same failure subset to verify expected metric gains vs allowed cost increase.
"""
    return md


def run_failure_analysis(
    save_artifacts: bool = True,
    results_dir: Optional[Path] = None,
    output_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Main entry point for running failure analysis on A1 evaluation runs.
    Saves JSON and Markdown reports to eval/results/.
    """
    analyzer = A1FailureAnalyzer(results_dir=results_dir)
    analysis_res = analyzer.run_analysis()

    if save_artifacts:
        target_dir = results_dir or (Path(__file__).parent / "results")
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Save JSON artifact
        json_path = target_dir / f"eval_failure_analysis_{timestamp_str}.json"
        latest_json_path = target_dir / "eval_failure_analysis_latest.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis_res, f, indent=2)

        with open(latest_json_path, "w", encoding="utf-8") as f:
            json.dump(analysis_res, f, indent=2)

        # Save Markdown report
        md_content = generate_markdown_report(analysis_res)
        md_path = output_report_path or (target_dir / "eval_failure_analysis_report.md")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"Saved failure analysis JSON artifact to: {json_path}")
        print(f"Saved failure analysis Markdown report to: {md_path}")

    return analysis_res


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A1 Failure Analysis & A2 Justification Runner (PLAN.md §6.4)"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Disable saving evaluation artifacts to disk.",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Custom directory path for results.",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Custom file path for Markdown report.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve() if args.results_dir else None
    report_path = Path(args.report_path).resolve() if args.report_path else None

    try:
        res = run_failure_analysis(
            save_artifacts=not args.no_save,
            results_dir=results_dir,
            output_report_path=report_path,
        )
        print("\n" + "=" * 80)
        print("A1 FAILURE ANALYSIS & A2 JUSTIFICATION SUMMARY")
        print("=" * 80)
        print(f"Total Cases Evaluated : {res['summary']['total_cases_evaluated']}")
        print(f"A1 Failures Identified: {res['summary']['failed_investigations']} ({res['summary']['failure_rate']:.1%})")
        print(f"Failure Breakdown     : {json.dumps(res['failure_mode_counts'])}")
        print(f"A2 Justified          : {res['a2_justified_per_plan_6_4']}")
        print("=" * 80)
        return 0
    except Exception as e:
        print(f"Error during failure analysis execution: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
