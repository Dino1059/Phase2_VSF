from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.r0 import R0DeterministicInvestigator
from src.reliability.governance.preventive_controls import PreventiveControlManager


def test_r0_investigator_known_rule():
    investigator = R0DeterministicInvestigator()

    now = datetime.now(timezone.utc)
    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        signal_ids=["RANGE_VIOLATION_battery_soc"],
        admission_reason="Out of range sensor value",
        severity="CRITICAL"
    )

    ev = Evidence(
        source_type="telemetry",
        source_id="ev-1",
        entity_ids=["VIN-001"],
        content_hash="hash1",
        summary="Sensor value -10.0"
    )

    hyp, rec = investigator.investigate_incident(inc, [ev])

    assert hyp is not None
    assert hyp.classification == "DATA"
    assert hyp.status == "CONFIRMED"
    assert rec is not None
    assert rec.action_type == "PREVENTIVE_DQ_RULE_PROPOSAL"


def test_r0_investigator_fallback():
    investigator = R0DeterministicInvestigator()

    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-002"],
        signal_ids=["L2_contextual_drift"],
        admission_reason="Gradual SOC drift",
        severity="HIGH"
    )

    hyp, rec = investigator.investigate_incident(inc, [])

    assert hyp is None
    assert rec is None


def test_preventive_control_governance():
    mgr = PreventiveControlManager()

    ctrl = mgr.propose_control(
        control_id="ctrl-01",
        rule_type="range",
        rule_expression="battery_soc >= 0 AND battery_soc <= 100",
        target_table="ev_telemetry",
        target_column="battery_soc"
    )

    assert ctrl.status == "PROPOSED"

    auth = mgr.approve_control(control_id="ctrl-01", actor="data_steward_1")

    assert mgr.verify_authorization(auth.authorization_id) is True
    assert auth.authorized_actor == "data_steward_1"

