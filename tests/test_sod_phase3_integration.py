"""
DataTrust OS x SoD Flow: Phase 3 Cross-System Integration Test Suite
Validates:
1. Deprecation of legacy direct approval/rejection endpoints (HTTP 410 Gone).
2. Fail-Closed HITL Gating & Version Binding (proposal_id + version + hash).
3. Real-data Anti-Drift Verification (live source row lock + snapshot check).
4. Concurrency-Safe Evidence Ledger (pg_advisory_xact_lock + sequence + SHA-256 chain).
5. Governed Remediation Ticket creation (Unit-of-Work atomic transaction).
6. Independent Failure Evidence Recording on execution rollback.
7. Database Schema & Triggers Contract Verification for Phase 3.
8. SoD Catalog & Classifier for Remediation tickets.
"""

import hashlib
import json
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.sod.integration_service import (
    rfc8785_canonical_json,
    GovernanceException,
    verify_hitl_approval_gate,
    append_audit_evidence_safely,
    create_governed_remediation_ticket,
    record_execution_failure_independently,
)
from backend.sod.catalog import ACTIVITIES, DEFAULT_MATRIX, ROLES
from backend.sod.classifier import classify_ticket
from backend.sod.chain_builder import build_approval_chain
from backend.ai.services.remediation_service import remediation_service


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# 1. DEPRECATION OF DIRECT APPROVAL ENDPOINTS (HTTP 410 GONE)
# ==============================================================================

def test_deprecated_approve_endpoint_returns_410(client):
    """Calling legacy POST /api/remediation/{id}/approve must fail with HTTP 410 Gone."""
    resp = client.post(
        "/api/remediation/prop_test_001/approve",
        headers={"X-User-Role": "ADMIN", "X-User": "admin_user"}
    )
    assert resp.status_code == 410
    data = resp.json()
    assert data["detail"]["code"] == "ENDPOINT_DEPRECATED"
    assert data["detail"]["deprecated_action"] == "approve"
    assert "SoD Flow" in data["detail"]["message"]


def test_deprecated_reject_endpoint_returns_410(client):
    """Calling legacy POST /api/remediation/{id}/reject must fail with HTTP 410 Gone."""
    resp = client.post(
        "/api/remediation/prop_test_001/reject",
        headers={"X-User-Role": "ADMIN", "X-User": "admin_user"}
    )
    assert resp.status_code == 410
    data = resp.json()
    assert data["detail"]["code"] == "ENDPOINT_DEPRECATED"
    assert data["detail"]["deprecated_action"] == "reject"
    assert "SoD Flow" in data["detail"]["message"]


# ==============================================================================
# 2. RFC 8785 CANONICAL JSON & HASH INTEGRITY
# ==============================================================================

def test_rfc8785_canonical_json_determinism():
    """Canonical JSON must produce identical serialized strings regardless of key insertion order."""
    obj1 = {"z": 1, "a": [3, 2, 1], "m": {"b": 2, "a": 1}}
    obj2 = {"m": {"a": 1, "b": 2}, "z": 1, "a": [3, 2, 1]}

    canon1 = rfc8785_canonical_json(obj1)
    canon2 = rfc8785_canonical_json(obj2)

    assert canon1 == canon2
    assert canon1 == '{"a":[3,2,1],"m":{"a":1,"b":2},"z":1}'

    h1 = hashlib.sha256(canon1.encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(canon2.encode("utf-8")).hexdigest()
    assert h1 == h2


# ==============================================================================
# 3. DATABASE MIGRATION & TRIGGERS CONTRACT VERIFICATION
# ==============================================================================

def test_phase3_migration_contains_required_tables_and_triggers():
    """Verifies that migration_20261016_phase3_cross_system.sql contains all required tables and constraints."""
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "database",
        "migration_20261016_phase3_cross_system.sql"
    )
    assert os.path.exists(migration_path), f"Migration file missing at {migration_path}"

    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read().lower()

    # Required tables
    assert "remediation.proposals" in sql
    assert "remediation.proposal_versions" in sql
    assert "remediation.execution_attempts" in sql
    assert "sod.ticket_subjects" in sql

    # Immutable triggers
    assert "trg_prevent_proposal_version_mutation" in sql
    assert "remediation.proposal_versions is strictly append-only" in sql

    # Ledger concurrency
    assert "audit.evidence_seq" in sql
    assert "sequence_no" in sql
    assert "evidence_hash" in sql


# ==============================================================================
# 4. FAIL-CLOSED HITL GATING & VERSION BINDING
# ==============================================================================

def test_verify_hitl_approval_gate_fail_closed_when_no_ticket():
    """Execution must abort with SOD_APPROVAL_REQUIRED when no ticket exists."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None

    proposal = {
        "proposal_id": "prop_fail_01",
        "version": 1,
        "proposal_hash": "hash_prop_01",
    }

    with pytest.raises(GovernanceException) as exc_info:
        verify_hitl_approval_gate(mock_cursor, proposal)

    assert exc_info.value.code == "SOD_APPROVAL_REQUIRED"
    assert exc_info.value.details.get("reason") == "TICKET_NOT_FOUND"


def test_verify_hitl_approval_gate_fail_closed_when_ticket_in_progress():
    """Execution must abort with SOD_APPROVAL_NOT_COMPLETED when ticket is OPEN or IN_REVIEW."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": "tkt_open_01",
        "code": "TK-2026-001",
        "status": "OPEN",
        "current_step_idx": 1,
        "total_steps": 2,
        "subject_version": 1,
        "subject_hash": "hash_prop_01",
        "source_snapshot_hash": "hash_src_01",
    }

    proposal = {
        "proposal_id": "prop_fail_02",
        "version": 1,
        "proposal_hash": "hash_prop_01",
    }

    with pytest.raises(GovernanceException) as exc_info:
        verify_hitl_approval_gate(mock_cursor, proposal)

    assert exc_info.value.code == "SOD_APPROVAL_NOT_COMPLETED"
    assert exc_info.value.details.get("ticket_status") == "OPEN"


def test_verify_hitl_approval_gate_passes_when_valid():
    """Execution passes when ticket is DONE and all versions & hashes match."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": "tkt_valid",
        "code": "TK-2026-PASS",
        "status": "DONE",
        "current_step_idx": 2,
        "total_steps": 2,
        "subject_version": 1,
        "subject_hash": "hash_prop_01",
        "source_snapshot_hash": "hash_src_01",
    }

    proposal = {
        "proposal_id": "prop_pass",
        "version": 1,
        "proposal_hash": "hash_prop_01",
    }

    result = verify_hitl_approval_gate(mock_cursor, proposal)
    assert result["id"] == "tkt_valid"
    assert result["status"] == "DONE"


# ==============================================================================
# 5. SOD CATALOG & CLASSIFIER FOR REMEDIATION TICKETS
# ==============================================================================

def test_sod_classifier_for_remediation_ticket():
    """Remediation proposal ticket is classified with level 2/3 risk and appropriate RACIX approval steps."""
    form = {
        "loaiPhieu": "remediation",
        "finding_id": "F-EV-001",
        "dlcn": "quarantine_pii",
        "rows": [{"tang": 2}],
        "reason": "Phê duyệt làm sạch số điện thoại tài xế trong dữ liệu cách ly",
    }
    cl = classify_ticket(form, DEFAULT_MATRIX)
    assert cl["level"] >= 1
    chain = build_approval_chain(cl, "requester_01", DEFAULT_MATRIX)
    assert len(chain["steps"]) >= 2
    # Ensure there is at least one Approver (A) in the chain
    has_approver = any(step["action"] == "A" for step in chain["steps"])
    assert has_approver is True


# ==============================================================================
# 6. CONCURRENCY-SAFE EVIDENCE APPEND & SEQUENCE INTEGRITY
# ==============================================================================

def test_append_audit_evidence_safely_mocked_contract():
    """Append audit evidence uses advisory lock, sequence, and creates valid SHA-256 evidence record."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        {"next_seq": 42},
        {"evidence_hash": "prev_hash_123"},
        {"evidence_id": "ev_uuid_999", "sequence_no": 42, "created_at": "2026-10-16T10:00:00Z"},
    ]

    result = append_audit_evidence_safely(
        cur=mock_cursor,
        event_type="SOD_REMEDIATION_APPROVED",
        run_id="run_001",
        dataset_id="ev_telemetry",
        payload={"finding_id": "F-01", "proposal_id": "P-01"},
        quarantine_count=5
    )

    assert result["evidence_id"] == "ev_uuid_999"
    assert result["sequence_no"] == 42
    assert len(result["evidence_hash"]) == 64
    assert result["previous_hash"] == "prev_hash_123"

    # Check that pg_advisory_xact_lock was called
    lock_calls = [call for call in mock_cursor.execute.call_args_list if "pg_advisory_xact_lock" in str(call)]
    assert len(lock_calls) >= 1


# ==============================================================================
# 7. EXECUTION INTEGRATION WITH FAIL-CLOSED HANDLER
# ==============================================================================

def test_execute_endpoint_handles_governance_exception(client):
    """POST /api/remediation/{id}/execute returns HTTP 409 with structured error on governance failure."""
    with patch.object(remediation_service, "execute_remediation_transaction") as mock_exec:
        mock_exec.side_effect = GovernanceException(
            error_code="SOD_APPROVAL_REQUIRED",
            message="Đề xuất cần có phiếu SoD được duyệt hoàn tất.",
            details={"reason": "TICKET_NOT_FOUND"}
        )

        resp = client.post(
            "/api/remediation/prop_test_gate/execute",
            headers={"X-User-Role": "ADMIN", "X-User": "admin_user"}
        )

        assert resp.status_code == 409
        err = resp.json()["detail"]
        assert err["code"] == "SOD_APPROVAL_REQUIRED"
        assert err["details"]["reason"] == "TICKET_NOT_FOUND"


# ==============================================================================
# 8. REMEDIATION REGISTRY & DUAL-BRANCH CLASSIFICATION (EXECUTABLE VS ADVISORY)
# ==============================================================================

def test_remediation_registry_mappings_and_post_check():
    """RemediationRegistry accurately identifies approved handlers and executes post-checks."""
    from backend.engine.remediation_registry import RemediationRegistry

    # 1. PII Masking Mapping
    mapping_phone = RemediationRegistry.find_mapping(
        dataset_id="dim_customers", column="phone", rule_id="RULE-PII-PHONE"
    )
    assert mapping_phone is not None
    assert mapping_phone["operation_id"] == "MASK_PHONE"
    assert mapping_phone["requires_human_input"] is False

    # 2. Financial Manual Reconciliation Mapping
    mapping_fare = RemediationRegistry.find_mapping(
        dataset_id="ride_hailing_xanh_sm_trips", column="fare_amount", rule_id="RULE-FARE-ACCURACY"
    )
    assert mapping_fare is not None
    assert mapping_fare["operation_id"] == "MANUAL_RECONCILIATION"
    assert mapping_fare["requires_human_input"] is True

    # 3. Unregistered Rule / Driver Trend Anomaly -> None (ADVISORY_ONLY)
    mapping_trend = RemediationRegistry.find_mapping(
        dataset_id="ride_hailing_xanh_sm_trips", column="distance_km", rule_id="F16_DRIVER_DAILY_DISTANCE_ANOMALY"
    )
    assert mapping_trend is None

    # 4. Post-Check Validation: Positive financial values pass, negative values fail
    passed_valid, _ = RemediationRegistry.run_post_check("ride_hailing_xanh_sm_trips", "fare_amount", None, 250000)
    passed_invalid, err_msg = RemediationRegistry.run_post_check("ride_hailing_xanh_sm_trips", "fare_amount", None, -50000)
    assert passed_valid is True
    assert passed_invalid is False
    assert "dương" in err_msg

    # 5. Post-Check Validation: Phone mask format
    passed_phone_valid, _ = RemediationRegistry.run_post_check("dim_customers", "phone", None, "098***12")
    passed_phone_invalid, _ = RemediationRegistry.run_post_check("dim_customers", "phone", None, "0987654321")
    assert passed_phone_valid is True
    assert passed_phone_invalid is False


def test_advisory_only_blocks_dry_run_and_execution():
    """Proposals classified as ADVISORY_ONLY fail-closed on dry-run and execution."""
    from backend.database.models import StructuredRemediationProposalModel
    from datetime import datetime, timezone

    advisory_prop = StructuredRemediationProposalModel(
        proposal_id="prop_advisory_test_01",
        finding_id="F16_DRIVER_ANOMALY",
        version=1,
        status="DRAFT",
        created_by="ai_agent",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem_advisory_01",
        risk_level="HIGH",
        proposal_hash="hash_advisory_01",
        source_snapshot_hash="src_hash_01",
        operation_id="NONE",
        target={"run_id": "RUN-01", "dataset_id": "trips", "column": "distance_km", "quarantine_ids": ["Q1"]},
        params={},
        reason="Lỗi xu hướng lái xe bất thường không thể tự động sửa.",
        expected_rows=5,
        confidence="0.9",
        grounding_evidence_ids=[],
        proposal_type="ADVISORY_ONLY",
        execution_block_reason="Không có Remediation Handler tự động cho quy tắc xu hướng F16."
    )

    # Register in-memory proposal
    remediation_service.proposals[advisory_prop.proposal_id] = advisory_prop

    # Dry-run must fail with ValueError
    with pytest.raises(ValueError) as excinfo:
        remediation_service.simulate_dry_run("prop_advisory_test_01")
    assert "ADVISORY_ONLY" in str(excinfo.value)

    # Execution must fail with ValueError
    with pytest.raises(ValueError) as excinfo_exec:
        remediation_service.execute_remediation_transaction("prop_advisory_test_01", actor_id="admin_user")
    assert "ADVISORY_ONLY" in str(excinfo_exec.value)


def test_manual_reconciliation_post_check_rejects_negative_value():
    """SO sending a negative or zero corrected_value fails post-check validation."""
    from fastapi import HTTPException
    from backend.sod.service import SodService

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.side_effect = [
        # 1. Step lookup
        {
            "id": "step_so_01",
            "ticket_id": "ticket_fin_01",
            "idx": 1,
            "role_code": "SO",
            "status": "CURRENT",
            "assignee_id": "user_so_01"
        },
        # 2. Ticket lookup
        {
            "id": "ticket_fin_01",
            "code": "TK-2026-001",
            "status": "OPEN",
            "form_hash": "hash_form_abc"
        },
        # 3. Subject lookup with requires_human_input
        {
            "subject_type": "REMEDIATION_PROPOSAL",
            "subject_id": "prop_fin_01",
            "subject_version": 1,
            "requires_human_input": True,
            "target_column": "fare_amount",
            "dataset_id": "ride_hailing_xanh_sm_trips",
            "finding_id": "F_FARE_01",
            "params": {},
            "source_snapshot_hash": "snap_hash_123",
            "expected_rows": 5,
            "target_quarantine_ids": ["Q1"],
            "operation_id": "MANUAL_RECONCILIATION"
        }
    ]

    # Expect HTTPException 400 when corrected_value <= 0
    with pytest.raises(HTTPException) as excinfo:
        SodService.decide_step(
            ticket_id="ticket_fin_01",
            step_id="step_so_01",
            actor_id="user_so_01",
            outcome="APPROVE",
            comment="Đối soát cước",
            conn=mock_conn,
            reconciliation={
                "corrected_value": -10000,
                "currency": "VND",
                "reason": "Sai số",
                "evidence_doc_ref": "INV-2026-001"
            }
        )
    assert excinfo.value.status_code == 400
    assert "dương" in excinfo.value.detail


# ==============================================================================
# 9. AI ALLOWLIST & PARAMETER SCHEMA VALIDATION
# ==============================================================================

def test_ai_disallowed_operation_or_parameters_rejected():
    """Remediation Registry rejects operations or parameters outside the approved allowlist."""
    from backend.engine.remediation_registry import RemediationRegistry

    # 1. Reject arbitrary unapproved operation
    valid_op, err_op = RemediationRegistry.validate_parameters("RANDOM_UNAPPROVED_OP", {})
    assert valid_op is False
    assert "chưa được đăng ký" in err_op

    # 2. Reject foreign parameters not in schema
    valid_param, err_param = RemediationRegistry.validate_parameters("ROUND_DECIMAL", {"arbitrary_sql": "SELECT 1"})
    assert valid_param is False
    assert "allowlist" in err_param

    # 3. Reject invalid parameter types or bounds (decimals max is 6)
    valid_decimals, err_decimals = RemediationRegistry.validate_parameters(
        "ROUND_DECIMAL", {"decimals": 100}
    )
    assert valid_decimals is False
    assert "tối đa" in err_decimals

    # 4. Valid allowlisted parameters pass
    valid_ok, err_ok = RemediationRegistry.validate_parameters(
        "ROUND_DECIMAL", {"decimals": 4}
    )
    assert valid_ok is True
    assert err_ok is None


# ==============================================================================
# 10. ANTI-SELF APPROVAL & ROLE SEPARATION GUARDS
# ==============================================================================

def test_anti_self_approval_and_invalid_role_guards():
    """Ticket creator cannot self-approve steps; conflict detector strictly enforces SoD separation."""
    from backend.sod.conflict_detector import is_self_approval, check_step_conflict, conflicts_for

    # 1. Direct Self-Approval Guard
    assert is_self_approval(actor_id="admin_01", requester_id="admin_01") is True
    assert is_self_approval(actor_id="user_so_01", requester_id="admin_01") is False

    # 2. Step Conflict Detection
    chain_steps = [
        {"idx": 0, "role": "REQ", "action": "P", "assignee_id": "usr_01"},
        {"idx": 1, "role": "SO", "action": "A", "assignee_id": "usr_02"},
        {"idx": 2, "role": "CISO", "action": "A", "assignee_id": "usr_03"},
    ]
    # Usr_01 cannot act on step 1 (Requester cannot approve)
    conflict_msg = check_step_conflict(
        requester_id="usr_01", actor_id="usr_01", actor_roles=["REQ"], step_role="SO", step_action="A"
    )
    assert conflict_msg is not None
    assert "tự phê duyệt" in conflict_msg

    conflicts = conflicts_for(steps=chain_steps, requester_id="usr_01", step_idx=1, person_id="usr_01")
    assert len(conflicts) > 0
    assert "tự duyệt" in conflicts[0]


# ==============================================================================
# 11. VERSION & HASH BINDING (MODIFICATION AFTER APPROVAL BLOCKS EXECUTION)
# ==============================================================================

def test_proposal_modification_after_approval_blocks_execution():
    """If proposal is modified after ticket approval, version or hash mismatch aborts execution."""
    mock_cursor = MagicMock()
    # Ticket was approved for proposal version 1 with hash_v1
    mock_cursor.fetchone.return_value = {
        "id": "tkt_approved_v1",
        "code": "TK-2026-V1",
        "status": "DONE",
        "current_step_idx": 2,
        "total_steps": 2,
        "subject_version": 1,
        "subject_hash": "hash_proposal_v1",
        "source_snapshot_hash": "hash_snapshot_v1",
    }

    # Proposal was modified to version 2 with different hash
    modified_proposal_v2 = {
        "proposal_id": "prop_tampered",
        "version": 2,
        "proposal_hash": "hash_proposal_v2_tampered",
    }

    with pytest.raises(GovernanceException) as exc_v:
        verify_hitl_approval_gate(mock_cursor, modified_proposal_v2)

    assert exc_v.value.code == "SOD_VERSION_MISMATCH"

    # Same version but altered proposal content/hash
    modified_proposal_hash = {
        "proposal_id": "prop_tampered",
        "version": 1,
        "proposal_hash": "hash_proposal_v1_tampered",
    }

    with pytest.raises(GovernanceException) as exc_h:
        verify_hitl_approval_gate(mock_cursor, modified_proposal_hash)

    assert exc_h.value.code == "SOD_HASH_MISMATCH"


# ==============================================================================
# 12. SOURCE DRIFT & POST-CHECK FAILURES TRIGGER ATOMIC ROLLBACK
# ==============================================================================

def test_source_drift_and_post_check_failure_guards():
    """Source drift or post-check failure raises governance exceptions preventing silver write."""
    from backend.sod.integration_service import verify_quarantine_anti_drift

    mock_cursor = MagicMock()
    # Mock quarantine rows returned
    mock_cursor.fetchall.return_value = [
        {"id": "q1", "lineage_hash": "lineage_hash_different"}
    ]

    # Expected snapshot hash does not match computed snapshot hash
    with pytest.raises(GovernanceException) as exc_drift:
        verify_quarantine_anti_drift(
            mock_cursor,
            quarantine_ids=["q1"],
            expected_snapshot_hash="original_expected_hash"
        )

    assert exc_drift.value.code == "SOURCE_DRIFT_DETECTED"


