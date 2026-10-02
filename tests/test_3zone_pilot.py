"""
DataTrust OS: 3-Zone Pilot Ingestion & Execution Test Suite
Tests integration with real data in data/vingroup_clean_3zone_pilot:
1. 3-Zone Catalog & Policy verification.
2. Real Trips (10,382 rows) processing: Driver ID pseudonymization, GPS generalization, fare validation.
3. Real Telemetry (86,400 rows) processing: Battery temp and SOC quality checks.
4. Quarantine isolation for injected violations.
5. AI Agent proposal & Admin approval loop on real 3-zone columns.
"""

import pytest
from backend.ingestion.load_3zone_pilot import (
    ThreeZonePilotLoader,
    get_3zone_datasets,
    get_3zone_columns,
    get_3zone_policies
)
from backend.database.models import (
    PiiRoleType,
    TreatmentActionType,
    RuleStatus,
    UserRole
)


def test_3zone_catalog_and_policies():
    datasets = get_3zone_datasets()
    assert len(datasets) == 5
    assert "trips" in datasets
    assert "telemetry" in datasets
    assert "charging" in datasets
    assert "nlp_feedback" in datasets
    assert "fleet" in datasets

    columns = get_3zone_columns()
    # Check trips columns
    trips_cols = {c.column_name: c for c in columns["trips"]}
    assert trips_cols["driver_id"].pii_role == PiiRoleType.LINKABLE_IDENTIFIER
    assert trips_cols["driver_id"].default_treatment == TreatmentActionType.PSEUDONYMIZE
    assert trips_cols["pickup_latitude"].pii_role == PiiRoleType.CONTEXTUAL_PERSONAL_DATA
    assert trips_cols["pickup_latitude"].default_treatment == TreatmentActionType.GENERALIZE
    assert trips_cols["fare_amount"].pii_role == PiiRoleType.NON_PERSONAL_REFERENCE

    # Check telemetry columns
    telem_cols = {c.column_name: c for c in columns["telemetry"]}
    assert telem_cols["battery_temp_c"].pii_role == PiiRoleType.TECHNICAL_METADATA
    assert telem_cols["battery_soc"].pii_role == PiiRoleType.TECHNICAL_METADATA

    # Check NLP feedback
    nlp_cols = {c.column_name: c for c in columns["nlp_feedback"]}
    assert nlp_cols["sentence"].pii_role == PiiRoleType.AMBIGUOUS_UNSTRUCTURED_DATA
    assert nlp_cols["sentence"].default_treatment == TreatmentActionType.PSEUDONYMIZE

    policies = get_3zone_policies()
    assert "POL-EU-GDPR" in policies
    assert "POL-VN-LAW91" in policies or "POL-VN-ND13" in policies
    assert "POL-IFRS-15" in policies
    assert "POL-EV-SAFETY" in policies


def test_process_real_trips_data():
    loader = ThreeZonePilotLoader()
    loader.initialize_pilot_environment()

    # Process first 500 trips from ride_hailing_xanh_sm_trips.csv
    res = loader.process_pilot_trips(limit=500)
    assert res["scanned"] == 500
    assert res["silver"] + res["quarantine"] == 500
    assert res["silver"] >= 490

    sample = res["sample_silver"]
    assert sample is not None

    # Verify Driver ID is pseudonymized (hashed SHA-256)
    assert len(sample["driver_id"]) == 64
    assert sample["driver_id"] != "DRV_XANH_0001"

    # Verify GPS latitude/longitude is generalized (rounded to 2 decimal places: 52.52)
    assert sample["pickup_latitude"] == 52.52
    assert sample["pickup_longitude"] == 13.36

    # Verify fare is valid (> 0)
    assert sample["fare_amount"] > 0
    assert "lineage_hash" in sample


def test_process_real_telemetry_data():
    loader = ThreeZonePilotLoader()
    loader.initialize_pilot_environment()

    # Process 1000 telemetry records from synthetic_ev_telemetry_ved_ref.csv
    res = loader.process_pilot_telemetry(limit=1000)
    assert res["scanned"] == 1000
    assert res["silver"] + res["quarantine"] == 1000
    assert res["silver"] >= 990

    sample = res["sample_silver"]
    assert sample is not None
    # Battery SOC between 0 and 100
    assert 0 <= sample["battery_soc"] <= 100
    # Battery Temp between -10 and 85
    assert -10 <= sample["battery_temp_c"] <= 85
    assert "lineage_hash" in sample


def test_quarantine_violation_isolation_on_pilot():
    loader = ThreeZonePilotLoader()
    loader.initialize_pilot_environment()

    # Ingest 3 records: 2 valid, 1 corrupted (fare_amount = -100.0)
    raw_trips = [
        {"trip_id": "VAL_01", "fare_amount": 150000.0, "trip_distance_km": 5.2, "pickup_latitude": 21.028511, "pickup_longitude": 105.854444, "driver_id": "DRV_01"},
        {"trip_id": "CORRUPT_01", "fare_amount": -100.0, "trip_distance_km": 2.0, "pickup_latitude": 21.03, "pickup_longitude": 105.85, "driver_id": "DRV_02"},
        {"trip_id": "VAL_02", "fare_amount": 80000.0, "trip_distance_km": 3.1, "pickup_latitude": 21.04, "pickup_longitude": 105.86, "driver_id": "DRV_03"},
    ]

    res = loader.runner.run_pipeline("trips", raw_trips)
    assert res.scanned_count == 3
    assert res.silver_count == 2
    assert res.quarantine_count == 1

    # Verify quarantined record details
    q_rec = res.quarantine_records[0]
    assert q_rec.source_row_pk == "CORRUPT_01"
    assert q_rec.violation_column == "fare_amount"
    assert "nhỏ hơn ngưỡng tối thiểu" in q_rec.violation_reason
    assert len(q_rec.lineage_hash) == 64


def test_ai_agent_on_3zone_pilot():
    loader = ThreeZonePilotLoader()
    env = loader.initialize_pilot_environment()

    policy = env["policies"]["POL-EU-GDPR"]
    cols = env["columns"]["trips"]

    # AI Agent proposes rules for GDPR on Trips
    proposals = loader.agent.propose_rules_for_policy(policy, cols)
    assert len(proposals) > 0

    # Ensure proposal starts as PENDING
    prop = proposals[0]
    assert prop.status == RuleStatus.PENDING

    # Auditor cannot approve -> Raises PermissionError
    with pytest.raises(PermissionError):
        loader.agent.approve_proposal(prop.proposal_id, actor_name="Trần Minh Hoàng", actor_role=UserRole.AUDITOR)

    # Admin approves -> Promotes to active rule!
    active_cfg = loader.agent.approve_proposal(prop.proposal_id, actor_name="Nguyễn Quốc Bảo", actor_role=UserRole.ADMIN)
    assert active_cfg.is_active is True
    assert prop.status == RuleStatus.APPROVED
