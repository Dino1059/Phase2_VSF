from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.a1 import A1BoundedInvestigator


def test_a1_dynamic_bounded_investigation():
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_token_budget=1000)

    now = datetime.now(timezone.utc)
    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-010"],
        signal_ids=["sig-10"],
        admission_reason="High severity L2 anomaly",
        severity="CRITICAL"
    )

    ev = Evidence(
        source_type="telemetry",
        source_id="bms-10",
        entity_ids=["VIN-010"],
        content_hash="hash000",
        summary="Initial anomaly signal"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert hyp.classification == "OPERATIONAL"
    assert "Dynamic A1" in hyp.claim
    assert meta["tool_calls_made"] <= 5
    assert meta["tokens_spent"] <= 1000
    assert len(hyp.supporting_evidence) >= 2
