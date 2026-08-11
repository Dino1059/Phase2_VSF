from datetime import datetime, timezone, timedelta
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

    # Fuse for proj-1
    incidents_proj1 = engine.fuse_signals_into_incidents(all_signals, project_id="proj-1")

    # Should separate into:
    # 1. VIN-001 Window 1 (sig1 + sig2 fused together)
    # 2. VIN-002 Window 1 (sig4)
    # 3. VIN-001 Window 2 (sig5)
    assert len(incidents_proj1) == 3

    # Check sig1 + sig2 incident
    inc_v1_w1 = [i for i in incidents_proj1 if "VIN-001" in i.entity_ids and i.time_window["start"] == now][0]
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

