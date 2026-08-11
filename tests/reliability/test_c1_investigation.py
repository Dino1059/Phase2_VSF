from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.c1 import C1FixedInvestigator
from src.reliability.governance.recommendations import RecommendationRouter


def test_c1_operational_investigation():
    investigator = C1FixedInvestigator()

    now = datetime.now(timezone.utc)
    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        signal_ids=["sig-1"],
        admission_reason="Persistent L2 battery anomaly",
        severity="HIGH"
    )

    ev = Evidence(
        source_type="telemetry",
        source_id="bms-1",
        entity_ids=["VIN-001"],
        content_hash="hash123",
        summary="High battery_temp_c thermal spike recorded"
    )

    hyp, rec = investigator.investigate_incident(inc, [ev])
    assert hyp.classification == "OPERATIONAL"
    assert "Operational asset defect" in hyp.claim
    assert rec.action_type == "MAINTENANCE_ROUTING"
    assert rec.requires_hitl_approval is False


def test_c1_data_investigation():
    investigator = C1FixedInvestigator()

    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-002"],
        signal_ids=["sig-2"],
        admission_reason="Arithmetic fare mismatch",
        severity="HIGH"
    )

    ev = Evidence(
        source_type="trips",
        source_id="trip-1",
        entity_ids=["VIN-002"],
        content_hash="hash456",
        summary="Negative fare_vnd value detected"
    )

    hyp, rec = investigator.investigate_incident(inc, [ev])
    assert hyp.classification == "DATA"
    assert rec.action_type == "PREVENTIVE_DQ_RULE_PROPOSAL"
    assert rec.requires_hitl_approval is True
