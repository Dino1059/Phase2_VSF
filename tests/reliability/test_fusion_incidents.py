from datetime import datetime, timezone
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.fusion.policy import AdmissionPolicy
from src.reliability.fusion.engine import FusionEngine
from src.reliability.incidents.service import IncidentService


def test_admission_policy_rules():
    policy = AdmissionPolicy()

    # Empty signals
    admitted, reason = policy.evaluate_admission([])
    assert not admitted

    # Critical L1 signal
    now = datetime.now(timezone.utc)
    sig_l1 = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="battery_soc",
        event_time=now,
        window_start=now,
        window_end=now,
        score=10.0,
        severity="CRITICAL",
        detector="L1_Constraint"
    )
    admitted, reason = policy.evaluate_admission([sig_l1])
    assert admitted
    assert "Critical L1" in reason


def test_fusion_engine_and_service():
    engine = FusionEngine()
    service = IncidentService()

    now = datetime.now(timezone.utc)
    sig_l2 = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="battery_temp_c",
        event_time=now,
        window_start=now,
        window_end=now,
        score=4.0,
        severity="HIGH",
        detector="L2_MAD"
    )

    incidents = engine.fuse_signals_into_incidents([sig_l2], project_id="proj-1")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.entity_ids == ["VIN-001"]
    assert inc.severity == "HIGH"

    service.save_incident(inc)
    retrieved = service.get_incident(inc.incident_id)
    assert retrieved is not None
    assert retrieved.incident_id == inc.incident_id
