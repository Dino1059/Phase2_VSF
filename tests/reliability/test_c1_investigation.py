import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.c1 import C1FixedInvestigator, LLMAnalysisResult
from src.reliability.governance.recommendations import RecommendationRouter


def test_c1_operational_investigation():
    investigator = C1FixedInvestigator()

    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        signal_ids=["sig-1"],
        admission_reason="Persistent L2 battery anomaly",
        severity="HIGH"
    )

    ev = Evidence(
        evidence_id="ev-101",
        source_type="telemetry",
        source_id="bms-1",
        entity_ids=["VIN-001"],
        content_hash="hash123",
        summary="High battery_temp_c thermal spike recorded"
    )

    hyp, rec = investigator.investigate_incident(inc, [ev])
    assert hyp.classification == "HARDWARE_SENSOR_FAULT"
    assert "Hardware / sensor fault" in hyp.claim
    assert rec.assigned_team == "Hardware_Maintenance_Team"
    assert rec.requires_hitl_approval is True


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
        evidence_id="ev-102",
        source_type="trips",
        source_id="trip-1",
        entity_ids=["VIN-002"],
        content_hash="hash456",
        summary="Negative fare_vnd value detected"
    )

    hyp, rec = investigator.investigate_incident(inc, [ev])
    assert hyp.classification == "SYSTEM_DATA_LOGIC"
    assert rec.assigned_team == "Data_Engineering_Team"
    assert rec.requires_hitl_approval is True


def test_c1_abstention_investigation():
    investigator = C1FixedInvestigator()

    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-003"],
        signal_ids=["sig-3"],
        admission_reason="Unknown anomaly",
        severity="MEDIUM"
    )

    hyp, rec = investigator.investigate_incident(inc, [])
    assert hyp.classification == "UNKNOWN"
    assert hyp.confidence == 0.0
    assert rec.assigned_team == "Tier2_Support_Team"
    assert rec.requires_hitl_approval is False


def test_c1_llm_schema_validation_valid():
    investigator = C1FixedInvestigator()

    inc = Incident(
        incident_id="inc-schema-1",
        project_id="proj-1",
        entity_ids=["VIN-004"],
        signal_ids=["sig-4"],
        admission_reason="Pipeline schema error",
        severity="HIGH"
    )

    ev = Evidence(
        evidence_id="ev_schema_log_ev-schema-1",
        source_type="schema_log",
        source_id="log-1",
        entity_ids=["VIN-004"],
        content_hash="hash789",
        summary="Null fare value violating data contract"
    )

    raw_llm_output = {
        "incident_id": "inc-schema-1",
        "claim": "Data contract violation due to missing fare column",
        "classification": "SYSTEM_DATA_LOGIC",
        "supporting_evidence_ids": ["ev_schema_log_ev-schema-1"],
        "contradicting_evidence_ids": [],
        "missing_evidence": [],
        "confidence": 0.95,
        "reasoning": "Schema validation confirmed null value."
    }

    hyp, rec = investigator.investigate_incident(inc, [ev], raw_llm_response=raw_llm_output)
    assert hyp.classification == "SYSTEM_DATA_LOGIC"
    assert hyp.confidence == 0.95
    assert hyp.supporting_evidence == ["ev_schema_log_ev-schema-1"]
    assert rec.assigned_team == "Data_Engineering_Team"


def test_c1_llm_schema_validation_invalid_fields():
    investigator = C1FixedInvestigator()

    inc = Incident(
        incident_id="inc-invalid-1",
        project_id="proj-1",
        entity_ids=["VIN-005"],
        signal_ids=["sig-5"],
        admission_reason="Test invalid LLM response",
        severity="HIGH"
    )

    # Invalid classification
    invalid_classification_output = {
        "incident_id": "inc-invalid-1",
        "claim": "Some claim",
        "classification": "INVALID_TYPE",
        "confidence": 0.8
    }

    with pytest.raises(ValidationError):
        investigator.investigate_incident(inc, [], raw_llm_response=invalid_classification_output)

    # Invalid confidence range (> 1.0)
    invalid_confidence_output = {
        "incident_id": "inc-invalid-1",
        "claim": "Some claim",
        "classification": "SYSTEM_DATA_LOGIC",
        "confidence": 1.5
    }

    with pytest.raises(ValidationError):
        investigator.investigate_incident(inc, [], raw_llm_response=invalid_confidence_output)


def test_c1_evidence_id_validation_strips_hallucinated_ids():
    investigator = C1FixedInvestigator()

    inc = Incident(
        incident_id="inc-hallucination-1",
        project_id="proj-1",
        entity_ids=["VIN-006"],
        signal_ids=["sig-6"],
        admission_reason="Battery thermal error",
        severity="HIGH"
    )

    valid_ev = Evidence(
        evidence_id="ev_telemetry_ev-valid-100",
        source_type="telemetry",
        source_id="bms-100",
        entity_ids=["VIN-006"],
        content_hash="hash100",
        summary="Thermal overtemp"
    )

    raw_llm_output = {
        "incident_id": "inc-hallucination-1",
        "claim": "Battery thermal runaway",
        "classification": "HARDWARE_SENSOR_FAULT",
        "supporting_evidence_ids": ["ev_telemetry_ev-valid-100", "ev-fake-999"],  # ev-fake-999 is hallucinated!
        "contradicting_evidence_ids": ["ev-fake-888"],
        "confidence": 0.9
    }

    hyp, rec = investigator.investigate_incident(inc, [valid_ev], raw_llm_response=raw_llm_output)
    assert hyp.supporting_evidence == ["ev_telemetry_ev-valid-100"]
    assert hyp.contradicting_evidence == []
    assert rec.assigned_team == "Hardware_Maintenance_Team"


def test_c1_context_builder_bundle_compilation():
    from src.reliability.investigation.c1 import C1FixedContextBuilder

    builder = C1FixedContextBuilder()
    inc = Incident(
        incident_id="inc-bundle-01",
        project_id="proj-bundle",
        entity_ids=["VIN-777"],
        signal_ids=["sig-battery-777"],
        admission_reason="Battery voltage degradation alert",
        severity="HIGH"
    )

    ev_signal = Evidence(evidence_id="ev_sig_01", source_type="telemetry", source_id="src-01", content_hash="hash-01", entity_ids=["VIN-777"], summary="High voltage drift")
    ev_history = Evidence(evidence_id="ev_hist_01", source_type="historical_logs", source_id="src-01", content_hash="hash-01", entity_ids=["VIN-777"], summary="Past battery event")
    ev_profile = Evidence(evidence_id="ev_prof_01", source_type="schema_profile", source_id="src-01", content_hash="hash-01", entity_ids=["VIN-777"], summary="Asset spec battery")
    ev_change = Evidence(evidence_id="ev_chg_01", source_type="pipeline_change", source_id="src-01", content_hash="hash-01", entity_ids=["VIN-777"], summary="Config deployment update")
    ev_rule = Evidence(evidence_id="ev_rule_01", source_type="rule_violation", source_id="src-01", content_hash="hash-01", entity_ids=["VIN-777"], summary="Range contract violation")

    bundle = builder.compile_evidence_bundle(inc, [ev_signal, ev_history, ev_profile, ev_change, ev_rule])

    assert len(bundle.signals) >= 1
    assert len(bundle.entity_history) >= 1
    assert len(bundle.profile) >= 1
    assert len(bundle.recent_changes) >= 1
    assert len(bundle.rule_violations) >= 1
    assert len(bundle.all_evidence) == 5
    assert all(eid.startswith("ev") for eid in bundle.retrievable_evidence_ids)


def test_c1_context_builder_no_hidden_ground_truth():
    from src.reliability.investigation.c1 import C1FixedContextBuilder

    builder = C1FixedContextBuilder()
    inc = Incident(
        incident_id="inc-gt-leak-test",
        project_id="proj-test",
        entity_ids=["VIN-888"],
        signal_ids=["sig-gt-1"],
        admission_reason="ground_truth: OPERATIONAL expected_classification: DATA telemetry alert",
        severity="CRITICAL"
    )

    ev = Evidence(
        evidence_id="ev_gt_01",
        source_type="telemetry",
        source_id="src-01",
        content_hash="hash-01",
        entity_ids=["VIN-888"],
        summary="label: OPERATIONAL preassigned_answer: DATA battery overheating"
    )

    bundle = builder.compile_evidence_bundle(inc, [ev])
    context_prompt = builder.build_llm_context(bundle, incident=inc)

    # Verify no hidden ground truth keys or pre-assigned answers remain in context
    assert "ground_truth:" not in context_prompt
    assert "expected_classification:" not in context_prompt
    assert "preassigned_answer:" not in context_prompt
    assert "label:" not in context_prompt
    assert "=== FIXED EVIDENCE BUNDLE FOR INVESTIGATION ===" in context_prompt


