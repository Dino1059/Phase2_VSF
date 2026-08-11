import pytest
from datetime import datetime, timezone
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.investigation.a1 import A1BoundedInvestigator
from src.reliability.investigation.tools import InvestigationToolRegistry, InvestigationToolResult, readonly_tool


def test_a1_dynamic_bounded_investigation():
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=1000)

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


def test_a1_observation_dependent_tool_paths():
    """Verify tool execution sequence dynamically depends on observation focus (DATA vs OPERATIONAL)."""
    investigator = A1BoundedInvestigator(max_tool_calls=3, max_tokens_budget=2000)

    # Path A: Data contract anomaly observation
    inc_data = Incident(
        project_id="proj-data",
        entity_ids=["VIN-DATA-01"],
        signal_ids=["L1_NULL_VIOLATION"],
        admission_reason="L1 schema NULL_VIOLATION in mandatory field",
        severity="HIGH"
    )
    ev_data = Evidence(
        source_type="schema_log",
        source_id="schema-01",
        entity_ids=["VIN-DATA-01"],
        content_hash="hash_data",
        summary="Trip fare null schema contract defect"
    )
    hyp_d, rec_d, meta_d = investigator.investigate_incident_dynamically(inc_data, [ev_data])
    assert hyp_d.classification == "DATA"
    assert len(meta_d["tool_execution_trace"]) > 0
    assert meta_d["tool_execution_trace"][0]["tool_name"] == "inspect_upstream_contracts"

    # Path B: Operational anomaly observation
    inc_op = Incident(
        project_id="proj-op",
        entity_ids=["VIN-OP-01"],
        signal_ids=["THERMAL_ANOMALY"],
        admission_reason="Battery thermal temp degradation spike",
        severity="CRITICAL"
    )
    ev_op = Evidence(
        source_type="telemetry",
        source_id="bms-op",
        entity_ids=["VIN-OP-01"],
        content_hash="hash_op",
        summary="Battery temperature sensor thermal spike"
    )
    hyp_o, rec_o, meta_o = investigator.investigate_incident_dynamically(inc_op, [ev_op])
    assert hyp_o.classification == "OPERATIONAL"
    assert len(meta_o["tool_execution_trace"]) > 0
    assert meta_o["tool_execution_trace"][0]["tool_name"] == "fetch_entity_telemetry"


def test_a1_explicit_abstention_missing_evidence():
    """Verify explicit abstention when initial evidence is missing and budget prevents tool calls."""
    investigator = A1BoundedInvestigator(max_tool_calls=0, max_tokens_budget=1000)

    inc = Incident(
        project_id="proj-missing",
        entity_ids=["VIN-MISSING"],
        signal_ids=["sig-unk"],
        admission_reason="Unknown anomaly with missing evidence",
        severity="MEDIUM"
    )

    ev_missing = Evidence(
        source_type="unknown",
        source_id="none",
        entity_ids=["VIN-MISSING"],
        content_hash="hash_missing",
        summary="Missing telemetry logs and telemetry unretrievable"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev_missing])

    assert hyp.classification == "UNKNOWN"
    assert rec.recommendation_type == "ABSTENTION"
    assert rec.cause_type == "UNKNOWN"
    assert "abstained" in hyp.claim.lower()
    assert len(hyp.missing_evidence) > 0


def test_a1_explicit_abstention_contradictory_evidence():
    """Verify explicit abstention when evidence contains contradictory signals."""
    investigator = A1BoundedInvestigator(max_tool_calls=3, max_tokens_budget=2000)

    inc = Incident(
        project_id="proj-contradict",
        entity_ids=["VIN-CONTRADICT"],
        signal_ids=["sig-conflicting"],
        admission_reason="System crash with contradictory logs",
        severity="HIGH"
    )

    ev = Evidence(
        source_type="telemetry",
        source_id="bms-contradict",
        entity_ids=["VIN-CONTRADICT"],
        content_hash="hash_contradict",
        summary="Contradictory evidence: routine normal ping response vs critical battery defect"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert hyp.classification == "UNKNOWN"
    assert rec.recommendation_type == "ABSTENTION"
    assert len(hyp.contradicting_evidence) > 0


def test_a1_competing_hypothesis_tracking():
    """Verify support vs contradiction evidence ID lists are tracked across competing hypotheses."""
    investigator = A1BoundedInvestigator(max_tool_calls=3, max_tokens_budget=2000)

    inc = Incident(
        project_id="proj-competing",
        entity_ids=["VIN-COMPETE"],
        signal_ids=["sig-comp"],
        admission_reason="High severity L2 battery degradation",
        severity="CRITICAL"
    )

    ev1 = Evidence(
        evidence_id="ev-op-support",
        source_type="telemetry",
        source_id="bms-comp",
        entity_ids=["VIN-COMPETE"],
        content_hash="hash_op_sup",
        summary="Battery temp thermal degradation anomaly"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev1])

    assert hyp.classification == "OPERATIONAL"
    assert "ev-op-support" in hyp.supporting_evidence
    assert isinstance(hyp.contradicting_evidence, list)
    assert meta["hypothesis_revisions"] > 0


def test_a1_budget_enforcement_max_tool_calls():
    """Verify max_tool_calls operational bound limit."""
    investigator = A1BoundedInvestigator(max_tool_calls=1, max_tokens_budget=2000)

    inc = Incident(
        project_id="proj-bound-1",
        entity_ids=["VIN-BOUND-1"],
        signal_ids=["sig-b1"],
        admission_reason="Battery voltage degradation",
        severity="HIGH"
    )
    ev = Evidence(
        evidence_id="ev-b1",
        source_type="telemetry",
        source_id="b1",
        entity_ids=["VIN-BOUND-1"],
        content_hash="h1",
        summary="Voltage degradation"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])
    assert meta["tool_calls_made"] <= 1
    assert meta["stop_reason"] == "max_tool_calls_exceeded"
    assert meta["bounded_stop"] is True


def test_a1_budget_enforcement_max_tokens_budget():
    """Verify max_tokens_budget operational bound limit."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=100)

    inc = Incident(
        project_id="proj-bound-2",
        entity_ids=["VIN-BOUND-2"],
        signal_ids=["sig-b2"],
        admission_reason="Battery degradation",
        severity="CRITICAL"
    )
    ev = Evidence(
        evidence_id="ev-b2",
        source_type="telemetry",
        source_id="b2",
        entity_ids=["VIN-BOUND-2"],
        content_hash="h2",
        summary="Voltage degradation"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])
    assert meta["tool_calls_made"] <= 1
    assert meta["tokens_spent"] <= 150
    assert meta["stop_reason"] == "max_tokens_budget_exceeded"


def test_a1_budget_enforcement_max_hypothesis_revisions():
    """Verify max_hypothesis_revisions operational bound limit."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000, max_hypothesis_revisions=1)

    inc = Incident(
        project_id="proj-bound-3",
        entity_ids=["VIN-BOUND-3"],
        signal_ids=["sig-b3"],
        admission_reason="Battery degradation",
        severity="HIGH"
    )
    ev = Evidence(
        evidence_id="ev-b3",
        source_type="telemetry",
        source_id="b3",
        entity_ids=["VIN-BOUND-3"],
        content_hash="h3",
        summary="Battery anomaly"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])
    assert meta["hypothesis_revisions"] == 1
    assert meta["stop_reason"] == "max_hypothesis_revisions_exceeded"


def test_investigation_tool_registry_8_typed_tools():
    """Verify all 8 typed read-only tools exist and return InvestigationToolResult."""
    registry = InvestigationToolRegistry()

    # 1. fetch_entity_telemetry
    r1 = registry.fetch_entity_telemetry(entity_id="VIN-099", metric="battery_soc")
    assert isinstance(r1, InvestigationToolResult)
    assert r1.success is True
    assert "ev-telemetry-VIN-099-battery_soc" in r1.evidence_ref

    # 2. fetch_trip_history
    r2 = registry.fetch_trip_history(entity_id="VIN-099")
    assert isinstance(r2, InvestigationToolResult)
    assert r2.data["total_trips"] > 0

    # 3. fetch_charging_history
    r3 = registry.fetch_charging_history(entity_id="VIN-099")
    assert isinstance(r3, InvestigationToolResult)
    assert "primary_station_id" in r3.data

    # 4. fetch_profile
    r4 = registry.fetch_profile(entity_id="VIN-099")
    assert isinstance(r4, InvestigationToolResult)
    assert r4.data["entity_type"] == "VEHICLE"

    # 5. fetch_dq_violations
    r5 = registry.fetch_dq_violations(entity_id="VIN-099")
    assert isinstance(r5, InvestigationToolResult)
    assert len(r5.data["violations"]) > 0

    # 6. fetch_recent_changes
    r6 = registry.fetch_recent_changes(entity_id="VIN-099")
    assert isinstance(r6, InvestigationToolResult)
    assert "recent_changes" in r6.data

    # 7. resolve_entity_relationships
    r7 = registry.resolve_entity_relationships(entity_id="VIN-099")
    assert isinstance(r7, InvestigationToolResult)
    assert len(r7.data["discovered_entity_ids"]) >= 2

    # 8. calculate_detector_detail
    r8 = registry.calculate_detector_detail(entity_id="VIN-099", layer="L2")
    assert isinstance(r8, InvestigationToolResult)
    assert r8.data["is_anomalous"] is True


def test_zero_state_mutation_guarantee():
    """Verify zero state mutation tools exist in registry and validation prevents mutating methods."""
    registry = InvestigationToolRegistry()
    assert registry.verify_zero_state_mutation() is True

    for tool_name in registry.registered_tools:
        assert not any(kw in tool_name.lower() for kw in ["update", "delete", "create", "insert", "drop", "write", "mutate"])


def test_dynamic_entity_and_time_scope_resolution():
    """Verify dynamic time/entity scope resolution during investigation based on intermediate tool outputs."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000)

    now = datetime.now(timezone.utc)
    inc = Incident(
        project_id="proj-1",
        entity_ids=["VIN-200"],
        signal_ids=["sig-20"],
        admission_reason="Interrupted charging session on station CS-200",
        severity="HIGH",
        time_window={"start": "2026-08-11T10:00:00Z", "end": "2026-08-11T12:00:00Z"}
    )

    ev = Evidence(
        source_type="charging_event",
        source_id="sess-200",
        entity_ids=["VIN-200"],
        content_hash="hash200",
        summary="Thermal anomaly during fast charging session"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert "resolved_entity_scope" in meta
    assert len(meta["resolved_entity_scope"]) >= 1
    assert "VIN-200" in meta["resolved_entity_scope"]

    assert "resolved_time_scope" in meta
    assert meta["bounded_stop"] is True


def test_a1_domain_scoped_allowlisting_ev_telemetry():
    """Verify domain detection and upfront filtering for EV_TELEMETRY domain."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000)

    inc = Incident(
        project_id="ev-telemetry",
        entity_ids=["VIN-999"],
        signal_ids=["SOC_DEGRADATION"],
        admission_reason="Battery thermal degradation warning",
        severity="HIGH"
    )
    ev = Evidence(
        source_type="telemetry",
        source_id="bms-999",
        entity_ids=["VIN-999"],
        content_hash="h999",
        summary="Battery SoC cell voltage degradation"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert meta["target_domain"] == "EV_TELEMETRY"
    executed_tools = [t["tool_name"] for t in meta["tool_execution_trace"]]
    assert "fetch_trip_history" not in executed_tools
    assert "fetch_charging_history" not in executed_tools
    assert "fetch_entity_telemetry" in executed_tools


def test_a1_domain_scoped_allowlisting_charging_network():
    """Verify domain detection and upfront filtering for CHARGING_NETWORK domain."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000)

    inc = Incident(
        project_id="vgreen",
        entity_ids=["CS-500"],
        signal_ids=["STATION_OVERHEAT"],
        admission_reason="V-GREEN charging station thermal fault",
        severity="CRITICAL"
    )
    ev = Evidence(
        source_type="station_log",
        source_id="cs-500",
        entity_ids=["CS-500"],
        content_hash="h500",
        summary="Charging station temperature threshold exceeded"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert meta["target_domain"] == "CHARGING_NETWORK"
    executed_tools = [t["tool_name"] for t in meta["tool_execution_trace"]]
    assert executed_tools[0] == "fetch_charging_history"
    assert "fetch_trip_history" not in executed_tools


def test_a1_domain_scoped_allowlisting_ride_hailing():
    """Verify domain detection and upfront filtering for RIDE_HAILING domain."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000)

    inc = Incident(
        project_id="xanh_sm",
        entity_ids=["TRIP-800"],
        signal_ids=["TRIP_ABORT"],
        admission_reason="Xanh SM trip aborted driver route delay",
        severity="MEDIUM"
    )
    ev = Evidence(
        source_type="trip_log",
        source_id="trip-800",
        entity_ids=["TRIP-800"],
        content_hash="h800",
        summary="Aborted trip history log recorded"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert meta["target_domain"] == "RIDE_HAILING"
    executed_tools = [t["tool_name"] for t in meta["tool_execution_trace"]]
    assert "fetch_trip_history" in executed_tools
    assert "fetch_charging_history" not in executed_tools



def test_a1_domain_scoped_allowlisting_customer_feedback():
    """Verify domain detection and upfront filtering for CUSTOMER_FEEDBACK domain."""
    investigator = A1BoundedInvestigator(max_tool_calls=5, max_tokens_budget=2000)

    inc = Incident(
        project_id="feedback",
        entity_ids=["FB-100"],
        signal_ids=["FEEDBACK_NEG"],
        admission_reason="Negative customer feedback regarding charging speed",
        severity="MEDIUM"
    )
    ev = Evidence(
        source_type="customer_feedback",
        source_id="fb-100",
        entity_ids=["FB-100"],
        content_hash="h100",
        summary="User feedback comment text extracted via NLP"
    )

    hyp, rec, meta = investigator.investigate_incident_dynamically(inc, [ev])

    assert meta["target_domain"] == "CUSTOMER_FEEDBACK"
    executed_tools = [t["tool_name"] for t in meta["tool_execution_trace"]]
    assert "fetch_trip_history" not in executed_tools
    assert "fetch_charging_history" not in executed_tools
    assert "fetch_entity_telemetry" not in executed_tools



