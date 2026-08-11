from datetime import datetime, timezone
from src.reliability.models import Signal, Incident, Evidence, Hypothesis, DataProvenance

def test_signal_contract():
    now = datetime.now(timezone.utc)
    sig = Signal(
        project_id="proj-123",
        entity_ids=["VIN-001"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="discharge_rate",
        event_time=now,
        window_start=now,
        window_end=now,
        score=3.5,
        severity="HIGH",
        detector="MAD_Detector",
        provenance="SEMI_SYNTHETIC"
    )
    assert sig.signal_id.startswith("sig-")
    assert sig.layer == "L2"
    assert sig.provenance == "SEMI_SYNTHETIC"

def test_incident_contract():
    now = datetime.now(timezone.utc)
    inc = Incident(
        project_id="proj-123",
        entity_ids=["VIN-001"],
        signal_ids=["sig-1"],
        admission_reason="Persistent L2 contextual anomaly",
        severity="HIGH"
    )
    assert inc.incident_id.startswith("inc-")
    assert inc.status == "OPEN"

def test_evidence_contract():
    ev = Evidence(
        source_type="telemetry_snapshot",
        source_id="snap-99",
        entity_ids=["VIN-001"],
        content_hash="abc123hash",
        summary="High temperature anomalies recorded"
    )
    assert ev.evidence_id.startswith("ev-")
    assert ev.provenance == "SEMI_SYNTHETIC"

def test_data_provenance_enum():
    assert DataProvenance.REAL_OPERATIONAL == "REAL_OPERATIONAL"
    assert DataProvenance.PUBLIC_PROXY == "PUBLIC_PROXY"
    assert DataProvenance.SEMI_SYNTHETIC == "SEMI_SYNTHETIC"
    assert DataProvenance.SYNTHETIC == "SYNTHETIC"
    assert list(DataProvenance) == [
        DataProvenance.REAL_OPERATIONAL,
        DataProvenance.PUBLIC_PROXY,
        DataProvenance.SEMI_SYNTHETIC,
        DataProvenance.SYNTHETIC,
    ]

def test_hypothesis_contract():
    hyp = Hypothesis(
        incident_id="inc-1",
        claim="Battery degradation starting at day 35",
        classification="OPERATIONAL",
        confidence=0.85
    )
    assert hyp.hypothesis_id.startswith("hyp-")
    assert hyp.classification == "OPERATIONAL"
    assert hyp.status == "PROPOSED"
