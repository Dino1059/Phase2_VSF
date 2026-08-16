"""
Smoke test for Step 4 — Wire L1-L4 into ReliabilityOrchestrator.

Feeds sample signals through ReliabilityOrchestrator, verifies incident created
and A1 returns hypothesis. Per plan verification section.
"""
from datetime import datetime, timezone
import json
import sys

from src.reliability.models.signal import Signal
from src.reliability.investigation.reliability_orchestrator import ReliabilityOrchestrator


def main():
    now = datetime.now(timezone.utc)

    # Build L1-L4 sample signals representing a single anomaly scenario
    sig_l1 = Signal(
        signal_id="smoke-l1",
        project_id="smoke-proj",
        entity_ids=["VIN-SMOKE-1"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="battery_soc",
        event_time=now,
        window_start=now,
        window_end=now,
        score=10.0,
        severity="CRITICAL",
        detector="L1_constraint",
    )
    sig_l2 = Signal(
        signal_id="smoke-l2",
        project_id="smoke-proj",
        entity_ids=["VIN-SMOKE-1"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="temp_c",
        event_time=now,
        window_start=now,
        window_end=now,
        score=4.5,
        severity="HIGH",
        detector="L2_mad",
    )
    sig_l3 = Signal(
        signal_id="smoke-l3",
        project_id="smoke-proj",
        entity_ids=["VIN-SMOKE-1"],
        layer="L3",
        signal_type="RELATIONAL_BREAK",
        metric_or_relationship="efficiency_vs_temp",
        event_time=now,
        window_start=now,
        window_end=now,
        score=3.5,
        severity="MEDIUM",
        detector="L3_regression",
    )
    sig_l4 = Signal(
        signal_id="smoke-l4",
        project_id="smoke-proj",
        entity_ids=["VIN-SMOKE-1"],
        layer="L4",
        signal_type="CHANGEPOINT_SHIFT",
        metric_or_relationship="discharge_rate",
        event_time=now,
        window_start=now,
        window_end=now,
        score=5.0,
        severity="HIGH",
        detector="L4_cusum",
    )

    orchestrator = ReliabilityOrchestrator()
    results = orchestrator.run_pipeline(
        {"L1": [sig_l1], "L2": [sig_l2], "L3": [sig_l3], "L4": [sig_l4]},
        project_id="smoke-proj",
    )

    print(f"Incidents produced: {len(results)}")
    for r in results:
        print(f"  Incident ID: {r.incident.incident_id}")
        print(f"  Layers: {r.incident.supporting_layers}")
        print(f"  Severity: {r.incident.severity}")
        print(f"  Admission reason: {r.incident.admission_reason}")
        print(f"  Hypothesis classification: {r.hypothesis.classification}")
        print(f"  Hypothesis claim: {r.hypothesis.claim[:80]}...")
        print(f"  Recommendation action: {r.recommendation.action_type}")
        print(f"  A1 tool_calls: {r.meta.get('tool_calls_made')}")
        print(f"  A1 tokens_spent: {r.meta.get('tokens_spent')}")

    assert len(results) == 1, f"Expected 1 incident, got {len(results)}"
    result = results[0]
    assert result.incident.supporting_layers == ["L1", "L2", "L3", "L4"]
    assert result.hypothesis is not None
    assert result.recommendation is not None
    print("\n[OK] Smoke test passed: L1-L4 -> Fusion -> A1 -> Hypothesis chain complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
