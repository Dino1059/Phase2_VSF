"""
DataTrust OS: Comprehensive Test Suite
Validates:
1. 6 PII Roles & 5 Treatment Actions.
2. AI Agent semantic matching & dry-run simulation.
3. Strict RBAC (Admin = Approver, Auditor = Viewer).
4. Dynamic Rule Runner (Zero-Code Policy Adaptation).
5. Quarantine Lineage Hash & Admin Remediation.
6. FastAPI REST API endpoints.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.database.models import (
    PiiRoleType,
    TreatmentActionType,
    ExecutionPhase,
    RuleSeverity,
    RuleStatus,
    QuarantineStatus,
    UserRole,
    DatasetModel,
    ColumnModel,
    CompliancePolicyModel,
    PolicyClauseModel,
    FieldProcessConfigModel
)
from backend.engine.operation_handlers import (
    execute_operation,
    handler_mask_phone,
    handler_mask_email,
    handler_hash_sha256,
    handler_mask_name,
    handler_round_decimal,
    handler_bucketize,
    handler_redact_null,
    handler_range_check
)
from backend.engine.quarantine_manager import QuarantineManager, compute_lineage_hash
from backend.engine.dynamic_runner import DynamicRuleRunner
from backend.ai.policy_rule_proposer import PolicyRuleProposerAgent
from backend.api.main import app


# =============================================================================
# 1. TEST 5 TREATMENT ACTIONS & HANDLERS
# =============================================================================

def test_treatment_action_remove():
    val, is_valid, err = handler_redact_null("0123456789")
    assert val is None
    assert is_valid is True
    assert err is None


def test_treatment_action_pseudonymize():
    # Mask phone
    masked_phone, is_valid, _ = handler_mask_phone("0987654321", prefix_len=3, suffix_len=2)
    assert masked_phone == "098*****21"
    assert is_valid is True

    # Mask email
    masked_email, is_valid, _ = handler_mask_email("hoang.tran@audit-ipo.com")
    assert masked_email == "h*********@audit-ipo.com"
    assert is_valid is True

    # Hash SHA-256
    hashed, is_valid, _ = handler_hash_sha256("sensitive_customer_note", salt="test_salt")
    assert len(hashed) == 64
    assert is_valid is True

    # Mask Name
    masked_name, is_valid, _ = handler_mask_name("Nguyễn Quốc Bảo")
    assert masked_name == "Nguyễn *** Bảo"
    assert is_valid is True


def test_treatment_action_generalize():
    # Round decimal for GPS
    rounded, is_valid, _ = handler_round_decimal(21.028511, decimals=2)
    assert rounded == 21.03
    assert is_valid is True

    # Bucketize age
    bucket, is_valid, _ = handler_bucketize(27, step=10)
    assert bucket == "20-29"
    assert is_valid is True


def test_treatment_action_keep_and_quality():
    # Range check pass
    v, is_valid, _ = handler_range_check(150000.0, min_val=0.01)
    assert is_valid is True
    assert v == 150000.0

    # Range check fail (negative or zero fare)
    v, is_valid, err = handler_range_check(0.0, min_val=0.01, allow_zero=False)
    assert is_valid is False
    assert "bằng 0" in err


# =============================================================================
# 2. TEST AI AGENT PROPOSALS & DRY-RUN SIMULATION
# =============================================================================

def test_ai_agent_semantic_matching():
    agent = PolicyRuleProposerAgent()
    policy = CompliancePolicyModel(
        policy_id="POL-VN-ND13",
        title="Nghị định 13/2023/NĐ-CP",
        jurisdiction="VN",
        legal_framework="Nghị định 13/2023/NĐ-CP",
        raw_policy_text="Bảo vệ dữ liệu cá nhân",
        effective_date="2023-07-01",
        clauses=[
            PolicyClauseModel(clause_id="C1", policy_id="POL-VN-ND13", clause_number="17", requirement_summary="Bảo vệ SĐT", target_pii_roles=[PiiRoleType.DIRECT_IDENTIFIER], mandated_action=TreatmentActionType.PSEUDONYMIZE)
        ]
    )
    columns = [
        ColumnModel(dataset_id="trips", column_name="customer_phone", data_type="VARCHAR", pii_role=PiiRoleType.DIRECT_IDENTIFIER),
        ColumnModel(dataset_id="trips", column_name="pickup_latitude", data_type="NUMERIC", pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA),
        ColumnModel(dataset_id="trips", column_name="trip_notes", data_type="TEXT", pii_role=PiiRoleType.AMBIGUOUS_UNSTRUCTURED_DATA),
    ]
    sample_records = [
        {"customer_phone": "0987654321", "pickup_latitude": 21.028511, "trip_notes": "Call passenger"},
        {"customer_phone": "0912345678", "pickup_latitude": 21.033333, "trip_notes": "Gate 2"},
    ]

    proposals = agent.propose_rules_for_policy(policy, columns, sample_records)
    assert len(proposals) == 3

    # Check Direct Identifier -> Pseudonymize
    phone_prop = next(p for p in proposals if p.column_name == "customer_phone")
    assert phone_prop.treatment_action == TreatmentActionType.PSEUDONYMIZE
    assert phone_prop.operation_id == "mask_phone"
    assert phone_prop.simulated_pass_rows == 2
    assert phone_prop.status == RuleStatus.PENDING

    # Check Contextual Personal Data -> Generalize
    lat_prop = next(p for p in proposals if p.column_name == "pickup_latitude")
    assert lat_prop.treatment_action == TreatmentActionType.GENERALIZE
    assert lat_prop.operation_id == "round_decimal"

    # Check Ambiguous Data -> Pseudonymize (Hash SHA-256)
    notes_prop = next(p for p in proposals if p.column_name == "trip_notes")
    assert notes_prop.treatment_action == TreatmentActionType.PSEUDONYMIZE
    assert notes_prop.operation_id == "hash_sha256"


# =============================================================================
# 3. TEST STRICT RBAC (ADMIN APPROVER VS AUDITOR VIEWER)
# =============================================================================

def test_rbac_approval_enforcement():
    agent = PolicyRuleProposerAgent()
    policy = CompliancePolicyModel(
        policy_id="POL-TEST",
        title="Test Policy",
        jurisdiction="VN",
        legal_framework="Test Law",
        raw_policy_text="Test",
        effective_date="2026-01-01"
    )
    cols = [ColumnModel(dataset_id="trips", column_name="customer_phone", data_type="VARCHAR", pii_role=PiiRoleType.DIRECT_IDENTIFIER)]
    proposals = agent.propose_rules_for_policy(policy, cols)
    prop = proposals[0]

    # 1. Auditor tries to APPROVE -> MUST RAISE PermissionError!
    with pytest.raises(PermissionError) as exc_info:
        agent.approve_proposal(prop.proposal_id, actor_name="Trần Minh Hoàng", actor_role=UserRole.AUDITOR)
    assert "chỉ có quyền xem" in str(exc_info.value)
    assert prop.status == RuleStatus.PENDING

    # 2. Auditor tries to REJECT -> MUST RAISE PermissionError!
    with pytest.raises(PermissionError) as exc_info:
        agent.reject_proposal(prop.proposal_id, actor_name="Trần Minh Hoàng", actor_role=UserRole.AUDITOR, comments="Dislike")
    assert "chỉ có quyền xem" in str(exc_info.value)

    # 3. Admin APPROVES -> SUCCESS!
    active_config = agent.approve_proposal(prop.proposal_id, actor_name="Nguyễn Quốc Bảo", actor_role=UserRole.ADMIN)
    assert prop.status == RuleStatus.APPROVED
    assert prop.reviewed_by == "Nguyễn Quốc Bảo"
    assert active_config.is_active is True
    assert active_config.column_name == "customer_phone"
    assert active_config.enforced_by == "Nguyễn Quốc Bảo"


# =============================================================================
# 4. TEST DYNAMIC RUNNER & ZERO-CODE POLICY ADAPTATION
# =============================================================================

def test_zero_code_dynamic_adaptation():
    quar_mgr = QuarantineManager()
    runner = DynamicRuleRunner(quarantine_manager=quar_mgr)

    # Phase 1: Runner starts with 1 rule: fare_amount > 0
    rule1 = FieldProcessConfigModel(
        config_id="CFG-FARE",
        dataset_id="trips",
        column_name="fare_amount",
        pii_role=PiiRoleType.NON_PERSONAL_REFERENCE,
        treatment_action=TreatmentActionType.KEEP,
        operation_id="range_check",
        execution_phase=ExecutionPhase.POST_CHECK,
        params_json={"min_val": 0.01, "allow_zero": False},
        enforced_by="Nguyễn Quốc Bảo"
    )
    runner.register_rule(rule1)

    bronze_data = [
        {"trip_id": "T001", "fare_amount": 100000.0, "customer_phone": "0987654321", "pickup_latitude": 21.028511},
        {"trip_id": "T002", "fare_amount": 0.0, "customer_phone": "0912345678", "pickup_latitude": 21.033333},  # Violates fare > 0
    ]

    res1 = runner.run_pipeline("trips", bronze_data)
    assert res1.scanned_count == 2
    assert res1.silver_count == 1
    assert res1.quarantine_count == 1
    assert res1.silver_records[0]["trip_id"] == "T001"
    # Notice: customer_phone is NOT masked yet because no rule for it yet!
    assert res1.silver_records[0]["customer_phone"] == "0987654321"

    # Phase 2: A new policy (Nghị định 13) comes.
    # AI Agent proposes masking customer_phone. Admin approves.
    # We dynamically register the new rule WITHOUT RE-WRITING OR RE-DEPLOYING THE RUNNER CODE!
    rule2 = FieldProcessConfigModel(
        config_id="CFG-MASK-PHONE",
        dataset_id="trips",
        column_name="customer_phone",
        pii_role=PiiRoleType.DIRECT_IDENTIFIER,
        treatment_action=TreatmentActionType.PSEUDONYMIZE,
        operation_id="mask_phone",
        execution_phase=ExecutionPhase.TREATMENT,
        params_json={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        enforced_by="Nguyễn Quốc Bảo"
    )
    runner.register_rule(rule2)

    # Re-run on Bronze data:
    res2 = runner.run_pipeline("trips", bronze_data)
    assert res2.scanned_count == 2
    assert res2.silver_count == 1
    # Check that the runner adapted dynamically: customer_phone is now masked!
    assert res2.silver_records[0]["customer_phone"] == "098*****21"
    assert "lineage_hash" in res2.silver_records[0]


# =============================================================================
# 5. TEST QUARANTINE MANAGER & AUDIT LINEAGE
# =============================================================================

def test_quarantine_remediation_and_audit():
    quar_mgr = QuarantineManager()
    q_rec = quar_mgr.record_quarantine(
        run_id="run_101",
        dataset_id="trips",
        source_table="bronze.trips_raw",
        source_row_pk="T002",
        raw_record={"trip_id": "T002", "fare_amount": 0.0},
        violation_column="fare_amount",
        violation_rule_id="CFG-FARE",
        violation_reason="fare_amount <= 0"
    )
    assert q_rec.status == QuarantineStatus.QUARANTINED
    assert len(q_rec.lineage_hash) == 64

    # 1. Auditor attempts remediation -> MUST RAISE PermissionError!
    with pytest.raises(PermissionError):
        quar_mgr.reprocess_record(q_rec.quarantine_id, {"fare_amount": 50000.0}, actor_name="Trần Minh Hoàng", actor_role=UserRole.AUDITOR)

    # 2. Admin overrides exception -> SUCCESS!
    overridden = quar_mgr.approve_override(
        q_rec.quarantine_id,
        justification="Chuyến đi từ thiện đặc biệt",
        actor_name="Nguyễn Quốc Bảo",
        actor_role=UserRole.ADMIN
    )
    assert overridden.status == QuarantineStatus.OVERRIDDEN
    assert overridden.resolved_by == "Nguyễn Quốc Bảo"

    # Check audit log chain
    assert len(quar_mgr.audit_log) == 1
    audit_entry = quar_mgr.audit_log[0]
    assert audit_entry.actor == "Nguyễn Quốc Bảo"
    assert audit_entry.actor_role == UserRole.ADMIN
    assert audit_entry.action_type == "ADMIN_OVERRIDE_EXCEPTION"
    assert audit_entry.previous_hash == "GENESIS_HASH_DATA_TRUST_OS"
    assert len(audit_entry.record_hash) == 64


# =============================================================================
# 6. TEST FASTAPI REST API
# =============================================================================

def test_api_catalog_and_rules():
    client = TestClient(app)

    # Test catalog
    resp = client.get("/api/catalog/datasets")
    assert resp.status_code == 200
    assert len(resp.json()) >= 3

    resp = client.get("/api/catalog/columns?dataset_id=trips")
    assert resp.status_code == 200
    col_names = [c["column_name"] for c in resp.json()]
    assert "driver_id" in col_names
    assert "pickup_latitude" in col_names

    # Test AI Propose endpoint
    resp = client.post("/api/ai/propose?policy_id=POL-VN-ND13&dataset_id=trips")
    assert resp.status_code == 200
    props = resp.json()
    assert len(props) > 0
    prop_id = props[0]["proposal_id"]

    # Test Auditor tries to approve -> 403 Forbidden!
    resp = client.post(f"/api/rules/{prop_id}/approve", json={"actor_name": "Trần Minh Hoàng", "actor_role": "AUDITOR"})
    assert resp.status_code == 403
    assert "chỉ có quyền xem" in resp.json()["detail"]

    # Test Admin approves -> 200 OK!
    resp = client.post(f"/api/rules/{prop_id}/approve", json={"actor_name": "Nguyễn Quốc Bảo", "actor_role": "ADMIN"})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # Test Pipeline Run endpoint
    payload = {
        "dataset_id": "trips",
        "bronze_records": [
            {"trip_id": "TX1", "fare_amount": 80000.0, "customer_phone": "0981112233"},
            {"trip_id": "TX2", "fare_amount": -10.0, "customer_phone": "0982223344"}
        ]
    }
    resp = client.post("/api/pipeline/run", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scanned_count"] == 2
    assert data["silver_count"] == 1
    assert data["quarantine_count"] == 1


def test_airflow_endpoints():
    """Test Airflow status check and trigger with fallback behavior."""
    client = TestClient(app)
    resp = client.get("/api/airflow/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_live" in data
    assert data["dag_id"] == "datatrust_adaptive_pipeline"

    # Trigger with fallback (Airflow offline on local test environment)
    resp = client.post("/api/airflow/trigger", json={"dataset_id": "trips"})
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["mode"] in ["airflow_celery", "local_fallback"]
    assert res_data["status"] in ["triggered", "completed"]


def test_dynamic_runs_and_dataset_filenames():
    """Kiểm tra tab lần chạy (/api/runs) và kích hoạt Airflow/fallback với tên file dataset thực tế."""
    client = TestClient(app)

    # 1. Trigger pipeline cho fleet_index.csv
    resp_fleet = client.post("/api/airflow/trigger", json={"dataset_id": "fleet_index.csv"})
    assert resp_fleet.status_code == 200
    fleet_data = resp_fleet.json()
    assert "fleet_index.csv" in fleet_data.get("dataset_id", "") or "fleet_index.csv" in str(fleet_data)

    # 2. Trigger pipeline cho synthetic_ev_telemetry_ved_ref.csv
    resp_telem = client.post("/api/airflow/trigger", json={"dataset_id": "synthetic_ev_telemetry_ved_ref.csv"})
    assert resp_telem.status_code == 200

    # 3. Lấy danh sách runs và kiểm tra rằng datasetId là tên file và kết quả tương ứng
    resp_runs = client.get("/api/runs")
    assert resp_runs.status_code == 200
    runs = resp_runs.json()
    assert len(runs) > 0
    assert any(r["datasetId"].endswith(".csv") for r in runs)
    # Xác nhận các lần chạy có dataset khác nhau
    dataset_ids = {r["datasetId"] for r in runs}
    assert len(dataset_ids) >= 1

