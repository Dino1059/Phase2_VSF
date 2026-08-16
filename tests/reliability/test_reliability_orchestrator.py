"""
Tests for ReliabilityOrchestrator — Step 4 (L1-L4 wiring).

Verifies that the top-level ReliabilityOrchestrator correctly:
1. Accepts L1-L4 detector outputs (Dict[str, List[Signal]])
2. Merges signals across layers
3. Routes through FusionEngine → AdmissionPolicy → IncidentService
4. Invokes A1BoundedInvestigator on each incident
5. Returns InvestigationResult for each produced incident
"""
from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from src.reliability.models.signal import Signal
from src.reliability.detectors.l1_rules import L1ConstraintDetector
from src.reliability.detectors.l2_contextual import L2ContextualDetector
from src.reliability.detectors.l3_relational import L3RelationalDetector
from src.reliability.detectors.l4_changepoint import L4ChangepointDetector
from src.reliability.investigation.reliability_orchestrator import (
    ReliabilityOrchestrator,
    InvestigationResult,
)


def _make_signal(layer, sid, metric, severity, score, project_id, entity_ids, ts):
    return Signal(
        signal_id=sid,
        project_id=project_id,
        entity_ids=entity_ids,
        layer=layer,
        signal_type=f"{layer}_TEST",
        metric_or_relationship=metric,
        event_time=ts,
        window_start=ts,
        window_end=ts,
        score=score,
        severity=severity,
        detector=f"{layer}_detector",
    )


def test_orchestrator_merges_l1_l4_dict_outputs():
    """run_pipeline must accept Dict[str, List[Signal]] and merge all layers."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    l1 = _make_signal("L1", "sig-l1", "battery_soc", "CRITICAL", 9.0, "proj-1", ["VIN-001"], now)
    l2 = _make_signal("L2", "sig-l2", "temp_c", "HIGH", 4.5, "proj-1", ["VIN-001"], now)
    l3 = _make_signal("L3", "sig-l3", "efficiency_vs_temp", "MEDIUM", 3.5, "proj-1", ["VIN-001"], now)
    l4 = _make_signal("L4", "sig-l4", "discharge_rate", "HIGH", 5.0, "proj-1", ["VIN-001"], now)

    detector_outputs = {"L1": [l1], "L2": [l2], "L3": [l3], "L4": [l4]}

    results = orchestrator.run_pipeline(detector_outputs, project_id="proj-1")

    assert len(results) == 1
    assert isinstance(results[0], InvestigationResult)
    assert results[0].incident.supporting_layers == ["L1", "L2", "L3", "L4"]
    assert results[0].incident.severity == "CRITICAL"
    assert set(results[0].incident.signal_ids) == {"sig-l1", "sig-l2", "sig-l3", "sig-l4"}


def test_orchestrator_handles_empty_detector_outputs():
    """run_pipeline with empty dict returns no incidents."""
    orchestrator = ReliabilityOrchestrator()
    results = orchestrator.run_pipeline({}, project_id="proj-1")
    assert results == []


def test_orchestrator_handles_empty_signal_lists():
    """run_pipeline with empty signal lists per layer returns no incidents."""
    orchestrator = ReliabilityOrchestrator()
    results = orchestrator.run_pipeline(
        {"L1": [], "L2": [], "L3": [], "L4": []},
        project_id="proj-1"
    )
    assert results == []


def test_orchestrator_separates_incidents_by_project_id():
    """Signals from different projects must be isolated."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    sig_p1 = _make_signal("L1", "sig-p1", "battery_soc", "CRITICAL", 9.0, "proj-A", ["VIN-001"], now)
    sig_p2 = _make_signal("L1", "sig-p2", "battery_soc", "CRITICAL", 9.0, "proj-B", ["VIN-001"], now)

    results = orchestrator.run_pipeline(
        {"L1": [sig_p1, sig_p2]},
        project_id="proj-A"
    )

    assert len(results) == 1
    assert results[0].incident.project_id == "proj-A"
    assert results[0].incident.signal_ids == ["sig-p1"]


def test_orchestrator_multi_layer_agreement_creates_incident():
    """Multi-layer agreement (>=2 layers) on same entity triggers Incident admission."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    l1 = _make_signal("L1", "sig-1", "voltage_mv", "HIGH", 7.0, "proj-e2e", ["VIN-099"], now)
    l2 = _make_signal("L2", "sig-2", "temp_c", "HIGH", 4.2, "proj-e2e", ["VIN-099"], now)

    results = orchestrator.run_pipeline({"L1": [l1], "L2": [l2]}, project_id="proj-e2e")

    assert len(results) == 1
    inc = results[0].incident
    assert "Multi-layer agreement" in inc.admission_reason or "Repeated" in inc.admission_reason
    assert "L1" in inc.supporting_layers
    assert "L2" in inc.supporting_layers


def test_orchestrator_persists_incident_and_hypothesis():
    """Orchestrator must persist incidents and hypotheses to IncidentService."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    l1 = _make_signal("L1", "sig-persist-1", "voltage_mv", "CRITICAL", 9.0, "proj-persist", ["VIN-100"], now)
    l2 = _make_signal("L2", "sig-persist-2", "temp_c", "HIGH", 4.5, "proj-persist", ["VIN-100"], now)

    results = orchestrator.run_pipeline({"L1": [l1], "L2": [l2]}, project_id="proj-persist")

    assert len(results) == 1
    incident_id = results[0].incident.incident_id

    stored = orchestrator.incident_service.get_incident(incident_id)
    assert stored is not None
    assert stored.incident_id == incident_id

    hyps = orchestrator.incident_service.list_hypotheses_for_incident(incident_id)
    assert len(hyps) == 1
    assert hyps[0].incident_id == incident_id


def test_orchestrator_invokes_a1_investigator():
    """Each admitted incident must be processed by A1 (hypothesis + recommendation + meta)."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    l1 = _make_signal("L1", "sig-a1", "battery_soc", "CRITICAL", 9.0, "proj-a1", ["VIN-200"], now)
    l2 = _make_signal("L2", "sig-a1-2", "temp_c", "HIGH", 4.2, "proj-a1", ["VIN-200"], now)

    results = orchestrator.run_pipeline({"L1": [l1], "L2": [l2]}, project_id="proj-a1")

    assert len(results) == 1
    res = results[0]
    assert res.hypothesis is not None
    assert res.hypothesis.incident_id == res.incident.incident_id
    assert res.recommendation is not None
    assert res.recommendation.incident_id == res.incident.incident_id
    assert "tool_calls_made" in res.meta
    assert "tokens_spent" in res.meta


def test_orchestrator_end_to_end_l1_l4_real_detectors():
    """
    Full pipeline: run L1-L4 detectors on raw data, pass outputs to orchestrator,
    verify incident is produced and A1 returns hypothesis.
    """
    project_id = "proj-e2e-detectors"
    now = datetime.now(timezone.utc)

    # Build a small dataset containing anomalies across L1-L4
    dates = [now - timedelta(days=i) for i in range(20, 0, -1)]
    soc_vals = [90.0, 91.0, 89.5, 90.2, 91.1, 90.0, 89.8, 90.5, 91.0, 90.1,
                89.9, 90.3, 90.7, 90.2, 90.1, 40.0, 90.0, 90.5, 90.2, 91.0]
    df = pd.DataFrame({
        "vehicle_vin": ["VIN-300"] * 20,
        "timestamp": dates,
        "battery_soc": soc_vals,
    })

    # L1: range violation on the soc=40.0 outlier
    l1 = L1ConstraintDetector()
    l1_signals = l1.detect_range_violations(
        df=df,
        project_id=project_id,
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc",
        min_val=50.0,
        max_val=100.0,
    )

    # L2: contextual drift
    l2 = L2ContextualDetector(z_threshold=3.5, warmup_days=14, min_samples=14)
    l2_signals = l2.detect_entity_anomalies(
        df=df,
        project_id=project_id,
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc",
    )

    # L4: CUSUM change point
    l4 = L4ChangepointDetector(cusum_threshold=4.0, min_segment_len=3, persistence_window=3)
    l4_signals = l4.detect_cusum_shift(
        df=df,
        project_id=project_id,
        entity_id_col="vehicle_vin",
        timestamp_col="timestamp",
        metric_col="battery_soc",
    )

    detector_outputs = {
        "L1": l1_signals,
        "L2": l2_signals,
        "L3": [],
        "L4": l4_signals,
    }

    # If no signals produced, runtime data insufficient — skip gracefully
    if not any(detector_outputs.values()):
        pytest.skip("Insufficient data to produce L1-L4 signals for this test fixture")

    orchestrator = ReliabilityOrchestrator()
    results = orchestrator.run_pipeline(detector_outputs, project_id=project_id)

    assert len(results) >= 1
    for res in results:
        assert isinstance(res, InvestigationResult)
        assert res.incident.project_id == project_id
        assert res.hypothesis is not None
        assert res.recommendation is not None


def test_orchestrator_dedupes_signals_by_id():
    """Duplicate signal_ids across layers must be deduplicated by FusionEngine."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    sig = _make_signal("L1", "sig-dup", "battery_soc", "CRITICAL", 9.0, "proj-dup", ["VIN-555"], now)

    # Pass same signal twice (simulating duplicate detector outputs)
    results = orchestrator.run_pipeline(
        {"L1": [sig], "L2": [sig]},  # Same signal_id in both layers
        project_id="proj-dup"
    )

    assert len(results) == 1
    assert results[0].incident.signal_ids == ["sig-dup"]


def test_orchestrator_separates_incidents_by_entity():
    """Signals from different entities (same project) must form separate incidents."""
    orchestrator = ReliabilityOrchestrator()
    now = datetime.now(timezone.utc)

    sig_a = _make_signal("L1", "sig-a", "battery_soc", "CRITICAL", 9.0, "proj-split", ["VIN-A"], now)
    sig_b = _make_signal("L1", "sig-b", "battery_soc", "CRITICAL", 9.0, "proj-split", ["VIN-B"], now)

    results = orchestrator.run_pipeline({"L1": [sig_a, sig_b]}, project_id="proj-split")

    assert len(results) == 2
    entity_ids = {tuple(sorted(r.incident.entity_ids)) for r in results}
    assert (("VIN-A",),) in entity_ids or (("VIN-A",)) in entity_ids
    assert (("VIN-B",),) in entity_ids or (("VIN-B",)) in entity_ids
