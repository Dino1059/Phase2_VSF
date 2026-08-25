import pytest
from datetime import datetime, timezone, timedelta
from src.db.connection import DuckDBManager
from src.reliability.models.signal import Signal
from src.reliability.models.incident import Incident
from src.reliability.models.evidence import Evidence
from src.reliability.models.hypothesis import Hypothesis
from src.reliability.models.decision import Decision
from src.reliability.governance.recommendations import Recommendation
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


def test_calibrated_admission_rules():
    policy = AdmissionPolicy()
    now = datetime.now(timezone.utc)

    # 1. Critical L1 rule
    sig_l1 = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="voltage_mv",
        event_time=now,
        window_start=now,
        window_end=now,
        score=9.5,
        severity="CRITICAL",
        detector="L1_Rule"
    )
    admitted, reason = policy.evaluate_admission([sig_l1])
    assert admitted
    assert "Critical L1" in reason

    # 2. Persistent L2 anomaly rule
    sig_l2_a = Signal(
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
    sig_l2_b = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="discharge_rate",
        event_time=now,
        window_start=now,
        window_end=now,
        score=3.8,
        severity="MEDIUM",
        detector="L2_MAD"
    )
    admitted, reason = policy.evaluate_admission([sig_l2_a, sig_l2_b])
    assert admitted
    assert "Persistent L2 anomaly" in reason

    # 3. >=2 layer agreement rule
    sig_l3 = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L3",
        signal_type="RELATIONAL_RESIDUAL",
        metric_or_relationship="efficiency_vs_temp",
        event_time=now,
        window_start=now,
        window_end=now,
        score=2.8,
        severity="MEDIUM",
        detector="L3_Regression"
    )
    admitted, reason = policy.evaluate_admission([sig_l1, sig_l3])
    assert admitted
    assert "Multi-layer agreement" in reason
    assert "L1, L3" in reason

    # 4. Repeated signals across related entities rule
    sig_rel_1 = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="charge_current",
        event_time=now,
        window_start=now,
        window_end=now,
        score=2.0,
        severity="LOW",
        detector="L2_MAD"
    )
    sig_rel_2 = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001", "STATION-005"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="charge_current",
        event_time=now,
        window_start=now,
        window_end=now,
        score=2.2,
        severity="LOW",
        detector="L2_MAD"
    )
    admitted, reason = policy.evaluate_admission([sig_rel_1, sig_rel_2])
    assert admitted
    assert "Repeated signals across related entities" in reason
    assert "STATION-005" in reason

    # Unadmitted single low severity signal
    sig_low = Signal(
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L4",
        signal_type="CHANGEPOINT",
        metric_or_relationship="daily_trips",
        event_time=now,
        window_start=now,
        window_end=now,
        score=1.1,
        severity="LOW",
        detector="L4_CUSUM"
    )
    admitted, reason = policy.evaluate_admission([sig_low])
    assert not admitted
    assert "do not meet" in reason


def test_fusion_strict_grouping():
    engine = FusionEngine()
    now = datetime.now(timezone.utc)
    later = now + timedelta(hours=5)

    # Signal 1: proj-1, VIN-001, Window 1, L1
    sig1 = Signal(
        signal_id="sig-001",
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="battery_soc",
        event_time=now,
        window_start=now,
        window_end=now + timedelta(minutes=15),
        score=8.0,
        severity="CRITICAL",
        detector="L1_Rules"
    )

    # Signal 2: proj-1, VIN-001, Window 1 (overlapping), L2
    sig2 = Signal(
        signal_id="sig-002",
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="temp_c",
        event_time=now + timedelta(minutes=5),
        window_start=now + timedelta(minutes=5),
        window_end=now + timedelta(minutes=20),
        score=4.5,
        severity="HIGH",
        detector="L2_MAD"
    )

    # Signal 3: proj-2 (different project!), VIN-001, Window 1, L1
    sig3 = Signal(
        signal_id="sig-003",
        project_id="proj-2",
        entity_ids=["VIN-001"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="battery_soc",
        event_time=now,
        window_start=now,
        window_end=now + timedelta(minutes=15),
        score=8.0,
        severity="CRITICAL",
        detector="L1_Rules"
    )

    # Signal 4: proj-1, VIN-002 (different entity!), Window 1, L1
    sig4 = Signal(
        signal_id="sig-004",
        project_id="proj-1",
        entity_ids=["VIN-002"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="battery_soc",
        event_time=now,
        window_start=now,
        window_end=now + timedelta(minutes=15),
        score=8.0,
        severity="CRITICAL",
        detector="L1_Rules"
    )

    # Signal 5: proj-1, VIN-001, Window 2 (5 hours later - disjoint time_window!), L1
    sig5 = Signal(
        signal_id="sig-005",
        project_id="proj-1",
        entity_ids=["VIN-001"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="battery_soc",
        event_time=later,
        window_start=later,
        window_end=later + timedelta(minutes=15),
        score=8.5,
        severity="CRITICAL",
        detector="L1_Rules"
    )

    all_signals = [sig1, sig2, sig3, sig4, sig5]

    # Without correlation (Tầng 1 only)
    engine_nocorr = FusionEngine(use_correlation=False)
    incidents_nocorr = engine_nocorr.fuse_signals_into_incidents(all_signals, project_id="proj-1")
    assert len(incidents_nocorr) == 3

    # With correlation (Tầng 1 + Tầng 2 Phase 3)
    incidents_proj1 = engine.fuse_signals_into_incidents(all_signals, project_id="proj-1")

    # Under FaultCorrelationEngine, sig4 (VIN-002 L1) and sig5 (VIN-001 L1) share correlation_key
    # and compress into 1 Incident group (occurrence_count=2), leaving sig1+sig2 multi-layer as incident #1
    assert len(incidents_proj1) == 2

    # Check sig1 + sig2 incident
    inc_v1_w1 = [i for i in incidents_proj1 if set(i.signal_ids) == {"sig-001", "sig-002"}][0]
    assert sorted(inc_v1_w1.supporting_layers) == ["L1", "L2"]
    assert inc_v1_w1.admission_reason != ""
    assert set(inc_v1_w1.signal_ids) == {"sig-001", "sig-002"}

    # Fuse for proj-2
    incidents_proj2 = engine.fuse_signals_into_incidents(all_signals, project_id="proj-2")
    assert len(incidents_proj2) == 1
    assert incidents_proj2[0].entity_ids == ["VIN-002"] or incidents_proj2[0].entity_ids == ["VIN-001"]


def test_latent_scenario_reproducible_deduplication():
    """
    Verifies that multi-layer signals from a latent scenario (L1-L4)
    reproducibly aggregate into exactly 1 Incident even when duplicate
    signals or redundant emissions occur.
    """
    engine = FusionEngine()
    now = datetime.now(timezone.utc)

    # Latent Scenario: Battery degradation starting at T0
    # Detector 1: L1 voltage violation
    sig_l1 = Signal(
        signal_id="sig-latent-l1",
        project_id="proj-scenario",
        entity_ids=["VIN-099"],
        layer="L1",
        signal_type="RANGE_VIOLATION",
        metric_or_relationship="min_cell_voltage_mv",
        event_time=now,
        window_start=now,
        window_end=now + timedelta(minutes=30),
        score=9.0,
        severity="CRITICAL",
        detector="L1_VoltageGuard",
        evidence_refs=["ev-l1-01"]
    )

    # Detector 2: L2 temperature drift
    sig_l2 = Signal(
        signal_id="sig-latent-l2",
        project_id="proj-scenario",
        entity_ids=["VIN-099"],
        layer="L2",
        signal_type="CONTEXTUAL_DRIFT",
        metric_or_relationship="temp_c",
        event_time=now + timedelta(minutes=5),
        window_start=now + timedelta(minutes=5),
        window_end=now + timedelta(minutes=35),
        score=4.2,
        severity="HIGH",
        detector="L2_MAD_Detector",
        evidence_refs=["ev-l2-01"]
    )

    # Detector 3: L3 trip energy vs charge efficiency residual
    sig_l3 = Signal(
        signal_id="sig-latent-l3",
        project_id="proj-scenario",
        entity_ids=["VIN-099"],
        layer="L3",
        signal_type="RELATIONAL_RESIDUAL",
        metric_or_relationship="efficiency_vs_temperature",
        event_time=now + timedelta(minutes=10),
        window_start=now + timedelta(minutes=10),
        window_end=now + timedelta(minutes=40),
        score=3.5,
        severity="MEDIUM",
        detector="L3_Regression",
        evidence_refs=["ev-l3-01"]
    )

    # Detector 4: L4 CUSUM degradation changepoint
    sig_l4 = Signal(
        signal_id="sig-latent-l4",
        project_id="proj-scenario",
        entity_ids=["VIN-099"],
        layer="L4",
        signal_type="CHANGEPOINT",
        metric_or_relationship="discharge_rate_cusum",
        event_time=now + timedelta(minutes=15),
        window_start=now + timedelta(minutes=15),
        window_end=now + timedelta(minutes=45),
        score=5.0,
        severity="HIGH",
        detector="L4_PELT",
        evidence_refs=["ev-l4-01"]
    )

    latent_signals = [sig_l1, sig_l2, sig_l3, sig_l4]

    # Add duplicate instances of signals (simulating duplicate detector runs/messages)
    latent_signals_with_duplicates = latent_signals + [sig_l1, sig_l2, sig_l3, sig_l4]

    # Run fusion multiple times to verify reproducibility
    for _ in range(3):
        incidents = engine.fuse_signals_into_incidents(
            latent_signals_with_duplicates, project_id="proj-scenario"
        )
        assert len(incidents) == 1, "Latent scenario must aggregate into exactly 1 Incident"
        inc = incidents[0]
        assert inc.project_id == "proj-scenario"
        assert inc.entity_ids == ["VIN-099"]
        assert inc.supporting_layers == ["L1", "L2", "L3", "L4"]
        assert inc.severity == "CRITICAL"
        assert len(inc.signal_ids) == 4
        assert set(inc.signal_ids) == {
            "sig-latent-l1", "sig-latent-l2", "sig-latent-l3", "sig-latent-l4"
        }
        assert set(inc.evidence_refs) == {"ev-l1-01", "ev-l2-01", "ev-l3-01", "ev-l4-01"}
        assert "Critical L1" in inc.admission_reason or "Multi-layer agreement" in inc.admission_reason


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
    assert inc.supporting_layers == ["L2"]

    service.save_incident(inc)
    retrieved = service.get_incident(inc.incident_id)
    assert retrieved is not None
    assert retrieved.incident_id == inc.incident_id



def _isolated_file_db(path: str) -> DuckDBManager:
    """File-backed manager that does not steal DuckDBManager._instance."""
    mgr = object.__new__(DuckDBManager)
    mgr._initialized = False
    DuckDBManager.__init__(mgr, path)
    conn = mgr.get_connection()
    mgr._ensure_reliability_tables(conn)
    return mgr


def test_incident_service_db_persistence(tmp_path):
    """
    Verifies that created/updated Incidents, Evidence, Hypotheses, Decisions,
    and Recommendations are persisted to DuckDB and successfully restored across backend restarts.
    """
    db_file = str(tmp_path / "test_persistence.duckdb")
    # Do not use get_db(tmp): that closes/rebinds the process-wide DuckDB
    # singleton (session fixture + earlier tests) and can deadlock the suite.
    db = _isolated_file_db(db_file)

    service1 = IncidentService(db=db)

    # 1. Create incident and update status
    inc = service1.create_incident(
        project_id="proj-test-persist",
        entity_ids=["VIN-100"],
        signal_ids=["sig-100"],
        admission_reason="Test persistence admission",
        severity="HIGH"
    )
    service1.update_incident_status(inc.incident_id, "RESOLVED")

    # 2. Add evidence
    ev = Evidence(
        evidence_id="ev-persist-1",
        source_type="TELEMETRY",
        source_id="station-01",
        entity_ids=["VIN-100"],
        content_hash="hash123",
        summary="High voltage anomaly",
        provenance="REAL_OPERATIONAL"
    )
    service1.add_evidence(ev)

    # 3. Add hypothesis
    hyp = Hypothesis(
        hypothesis_id="hyp-persist-1",
        incident_id=inc.incident_id,
        claim="Overheating caused voltage spike",
        classification="OPERATIONAL",
        supporting_evidence=["ev-persist-1"],
        confidence=0.9,
        status="CONFIRMED"
    )
    service1.add_hypothesis(hyp)

    # 4. Add recommendation
    rec = Recommendation(
        recommendation_id="rec-persist-1",
        incident_id=inc.incident_id,
        cause_type="OPERATIONAL",
        action_type="MAINTENANCE_ROUTING",
        summary="Route vehicle for thermal check",
        requires_hitl_approval=False
    )
    service1.add_recommendation(rec)

    # 5. Add decision
    dec = Decision(
        decision_id="dec-persist-1",
        incident_id=inc.incident_id,
        hypothesis_id=hyp.hypothesis_id,
        recommendation_id=rec.recommendation_id,
        action="APPROVE_MAINTENANCE",
        actor="OPERATOR_1",
        rationale="Hypothesis confirmed by thermal logs"
    )
    service1.add_decision(dec)

    # Close connection to simulate backend shutdown
    db.close()

    # Simulate backend restart with a fresh service instance reading from the same DB file
    db2 = _isolated_file_db(db_file)
    service2 = IncidentService(db=db2)

    # Assertions on restored state
    loaded_inc = service2.get_incident(inc.incident_id)
    assert loaded_inc is not None
    assert loaded_inc.incident_id == inc.incident_id
    assert loaded_inc.status == "RESOLVED"
    assert loaded_inc.project_id == "proj-test-persist"
    assert loaded_inc.entity_ids == ["VIN-100"]

    loaded_ev = service2.get_evidence("ev-persist-1")
    assert loaded_ev is not None
    assert loaded_ev.summary == "High voltage anomaly"
    assert loaded_ev.source_type == "TELEMETRY"

    loaded_hyp = service2.get_hypothesis("hyp-persist-1")
    assert loaded_hyp is not None
    assert loaded_hyp.claim == "Overheating caused voltage spike"
    assert loaded_hyp.status == "CONFIRMED"
    assert loaded_hyp.confidence == pytest.approx(0.9)

    loaded_rec = service2.get_recommendation("rec-persist-1")
    assert loaded_rec is not None
    assert loaded_rec.action_type == "MAINTENANCE_ROUTING"
    assert loaded_rec.cause_type == "OPERATIONAL"

    loaded_dec = service2.get_decision("dec-persist-1")
    assert loaded_dec is not None
    assert loaded_dec.action == "APPROVE_MAINTENANCE"
    assert loaded_dec.actor == "OPERATOR_1"

    db2.close()


def test_cross_incident_evidence_isolation():
    """
    Verifies strict evidence isolation between incidents so that
    Incident A evidence ∩ Incident B evidence = ∅ (empty set).
    Prevents cross-incident evidence leakage during investigation.
    """
    service = IncidentService()
    now = datetime.now(timezone.utc)

    # 1. Create Incident A (proj-1, VIN-001, Window T1)
    inc_a = Incident(
        incident_id="inc-iso-001",
        project_id="proj-1",
        entity_ids=["VIN-001"],
        signal_ids=["sig-001"],
        admission_reason="L1 Voltage violation on VIN-001",
        severity="HIGH",
        time_window={"start": now, "end": now + timedelta(minutes=30)}
    )
    service.save_incident(inc_a)

    # 2. Create Incident B (proj-1, VIN-002, Window T1)
    inc_b = Incident(
        incident_id="inc-iso-002",
        project_id="proj-1",
        entity_ids=["VIN-002"],
        signal_ids=["sig-002"],
        admission_reason="L2 Thermal anomaly on VIN-002",
        severity="HIGH",
        time_window={"start": now, "end": now + timedelta(minutes=30)}
    )
    service.save_incident(inc_b)

    # 3. Create Evidence A scoped to VIN-001 / Incident A
    ev_a = Evidence(
        evidence_id="ev-iso-a",
        project_id="proj-1",
        incident_id="inc-iso-001",
        source_type="telemetry",
        source_id="bms-001",
        entity_ids=["VIN-001"],
        time_range={"start": now, "end": now + timedelta(minutes=30)},
        content_hash="hash-a",
        summary="Voltage drop on VIN-001"
    )
    service.add_evidence(ev_a)

    # 4. Create Evidence B scoped to VIN-002 / Incident B
    ev_b = Evidence(
        evidence_id="ev-iso-b",
        project_id="proj-1",
        incident_id="inc-iso-002",
        source_type="telemetry",
        source_id="bms-002",
        entity_ids=["VIN-002"],
        time_range={"start": now, "end": now + timedelta(minutes=30)},
        content_hash="hash-b",
        summary="Temperature spike on VIN-002"
    )
    service.add_evidence(ev_b)

    # 5. Retrieve evidence for Incident A and Incident B
    evidence_a = service.get_evidence_for_incident(inc_a.incident_id)
    evidence_b = service.get_evidence_for_incident(inc_b.incident_id)

    set_a = {e.evidence_id for e in evidence_a}
    set_b = {e.evidence_id for e in evidence_b}

    # Core assertion: Incident A evidence ∩ Incident B evidence = ∅
    assert set_a.intersection(set_b) == set()
    assert "ev-iso-a" in set_a
    assert "ev-iso-a" not in set_b
    assert "ev-iso-b" in set_b
    assert "ev-iso-b" not in set_a

    # 6. Test disjoint time windows on the SAME entity (VIN-001)
    inc_c = Incident(
        incident_id="inc-iso-003",
        project_id="proj-1",
        entity_ids=["VIN-001"],
        signal_ids=["sig-003"],
        admission_reason="L4 Degradation on VIN-001 5 hours later",
        severity="MEDIUM",
        time_window={"start": now + timedelta(hours=5), "end": now + timedelta(hours=5, minutes=30)}
    )
    service.save_incident(inc_c)

    ev_c = Evidence(
        evidence_id="ev-iso-c",
        project_id="proj-1",
        incident_id="inc-iso-003",
        source_type="telemetry",
        source_id="bms-001-c",
        entity_ids=["VIN-001"],
        time_range={"start": now + timedelta(hours=5), "end": now + timedelta(hours=5, minutes=30)},
        content_hash="hash-c",
        summary="Later degradation signal on VIN-001"
    )
    service.add_evidence(ev_c)

    evidence_c = service.get_evidence_for_incident(inc_c.incident_id)
    set_c = {e.evidence_id for e in evidence_c}

    # Verify time-window based isolation on same entity
    assert set_a.intersection(set_c) == set()
    assert set_b.intersection(set_c) == set()
    assert "ev-iso-c" in set_c
    assert "ev-iso-c" not in set_a



