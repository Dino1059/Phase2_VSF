from datetime import datetime, timezone
import pytest
from src.reliability.models.signal import Signal
from src.reliability.fusion.correlation import FaultCorrelationEngine

@pytest.fixture
def correlation_engine():
    return FaultCorrelationEngine()

def test_single_correlation_key_grouping(correlation_engine):
    now = datetime.now(timezone.utc)
    signals = [
        Signal(
            project_id="proj_1",
            entity_ids=[f"entity_{i}"],
            layer="L1",
            signal_type="DATA_QUALITY_OUTBREAK",
            metric_or_relationship="null_rate",
            event_time=now,
            window_start=now,
            window_end=now,
            score=0.5 + (i * 0.001),
            detector="L1_Rule_Engine",
            source_table="acn_charging",
            violation_direction="null_violation",
        )
        for i in range(100)
    ]

    incidents = correlation_engine.correlate_signals(signals, project_id="proj_1")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.occurrence_count == 100
    assert len(inc.signal_ids) == 100
    assert len(inc.representative_signal_ids) == 3
    assert inc.correlation_key is not None

def test_different_rules_different_incidents(correlation_engine):
    now = datetime.now(timezone.utc)
    signals = [
        Signal(
            project_id="proj_1",
            entity_ids=["entity_1"],
            layer="L1",
            signal_type=f"RULE_TYPE_{i}",
            metric_or_relationship=f"metric_{i}",
            event_time=now,
            window_start=now,
            window_end=now,
            score=0.9,
            detector=f"detector_{i}",
        )
        for i in range(3)
    ]

    incidents = correlation_engine.correlate_signals(signals, project_id="proj_1")
    assert len(incidents) == 3
    assert all(inc.occurrence_count == 1 for inc in incidents)

def test_mixed_signals(correlation_engine):
    now = datetime.now(timezone.utc)
    signals_a = [
        Signal(
            project_id="proj_1",
            entity_ids=[f"entity_{i}"],
            layer="L1",
            signal_type="NULL_RATE",
            metric_or_relationship="col_a",
            event_time=now,
            window_start=now,
            window_end=now,
            score=0.8,
            detector="L1_Rule",
            source_table="table_a",
        )
        for i in range(50)
    ]
    signals_b = [
        Signal(
            project_id="proj_1",
            entity_ids=[f"entity_{i}"],
            layer="L2",
            signal_type="OUTLIER",
            metric_or_relationship="col_b",
            event_time=now,
            window_start=now,
            window_end=now,
            score=0.9,
            detector="L2_Contextual",
            source_table="table_b",
        )
        for i in range(3)
    ]

    incidents = correlation_engine.correlate_signals(signals_a + signals_b, project_id="proj_1")
    assert len(incidents) == 2
    counts = sorted([inc.occurrence_count for inc in incidents])
    assert counts == [3, 50]

def test_empty_signals(correlation_engine):
    incidents = correlation_engine.correlate_signals([], project_id="proj_1")
    assert incidents == []

def test_backward_compatibility_missing_optional_fields(correlation_engine):
    now = datetime.now(timezone.utc)
    sig1 = Signal(
        project_id="proj_1",
        entity_ids=["entity_1"],
        layer="L1",
        signal_type="NULL_RATE",
        metric_or_relationship="col_a",
        event_time=now,
        window_start=now,
        window_end=now,
        score=0.8,
        detector="L1_Rule",
    )
    sig2 = Signal(
        project_id="proj_1",
        entity_ids=["entity_2"],
        layer="L1",
        signal_type="NULL_RATE",
        metric_or_relationship="col_a",
        event_time=now,
        window_start=now,
        window_end=now,
        score=0.85,
        detector="L1_Rule",
    )

    incidents = correlation_engine.correlate_signals([sig1, sig2], project_id="proj_1")
    assert len(incidents) == 1
    assert incidents[0].occurrence_count == 2


def test_fault_manifest_14_rules_compression():
    """
    Phase 5 E2E Verification:
    14 rules emitting 20 signals each across 20 entities (280 raw signals total)
    must compress into <= 14 Incident Groups with exactly 280 total occurrence count.
    """
    from src.reliability.fusion.engine import FusionEngine

    engine = FusionEngine()
    now = datetime.now(timezone.utc)

    raw_signals = []
    for rule_idx in range(1, 15):  # 14 distinct fault rules
        for entity_idx in range(20):  # 20 distinct entities per rule
            entity_id = f"VIN-{rule_idx:02d}-{entity_idx:02d}"
            sig = Signal(
                project_id="proj_manifest",
                entity_ids=[entity_id],
                layer="L1" if rule_idx <= 7 else "L2",
                signal_type=f"FAULT_RULE_{rule_idx}",
                metric_or_relationship=f"metric_{rule_idx}",
                event_time=now,
                window_start=now,
                window_end=now,
                score=8.0 + (entity_idx * 0.05),
                severity="CRITICAL" if rule_idx % 2 == 0 else "HIGH",
                detector=f"Detector_Rule_{rule_idx}",
                source_table=f"table_{rule_idx % 3}",
                violation_direction="min_violation" if rule_idx % 2 == 0 else "max_violation",
            )
            raw_signals.append(sig)

    assert len(raw_signals) == 280

    incidents = engine.fuse_signals_into_incidents(raw_signals, project_id="proj_manifest")

    assert len(incidents) <= 14
    assert len(incidents) == 14
    total_compressed_occurrences = sum(inc.occurrence_count for inc in incidents)
    assert total_compressed_occurrences == 280

    for inc in incidents:
        assert inc.correlation_key is not None
        assert inc.occurrence_count == 20
        assert len(inc.representative_signal_ids) <= 3
        assert len(inc.representative_signal_ids) > 0

