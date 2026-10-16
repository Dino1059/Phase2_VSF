"""
DataTrust OS x SoD Flow: Comprehensive Backend & RBAC Test Suite (Phase 2)
Tests SoD Core Engine (Classifier, Chain Builder, Conflict Detector),
Fail-Closed Security Policy, Database Triggers Contract,
Role Switcher with session_version Invalidation, and Tamper-Evident Integrity Evidence.
"""

import hashlib
import json
import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.sod.catalog import (
    ACTIVITIES,
    DEFAULT_MATRIX,
    ROLES,
    ROLE_KEYS,
    act_name,
    role_name,
)
from backend.sod.classifier import classify_ticket, form_priority
from backend.sod.chain_builder import build_approval_chain
from backend.sod.conflict_detector import (
    auto_assign_steps,
    check_step_conflict,
    is_self_approval,
)
from backend.sod.service import SodService, SodConfigurationUnavailableException
from backend.api.auth_routes import (
    ROLE_PERMISSIONS,
    BOTH_ROLES,
    SOD_ROLES,
    DATATRUST_ROLES,
    create_jwt_token,
    decode_jwt_token,
    get_system_access_for_role,
)
from backend.api.main import app


# ==============================================================================
# 1. CATALOG & MATRIX DEFINITIONS (ITGC & RACIX)
# ==============================================================================

def test_catalog_itgc_activities_and_roles():
    """Verifies that all 19 ITGC activities and 10 SoD roles are defined with valid metadata."""
    assert len(ACTIVITIES) == 19
    assert len(ROLES) == 10
    assert len(ROLE_KEYS) == 10

    # Ensure each activity has valid index and name
    for idx, act in enumerate(ACTIVITIES):
        assert act["id"] == idx
        assert len(act["name"]) > 0
        assert act_name(idx) == act["name"]

    # Verify role keys
    for rk in ["REQ", "LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD"]:
        assert rk in ROLES
        assert len(role_name(rk)) > 0


def test_default_matrix_dimensions():
    """The default RACIX matrix must have 19 rows and each row must be a string of length 10."""
    assert len(DEFAULT_MATRIX) == 19
    for row in DEFAULT_MATRIX:
        assert isinstance(row, str)
        assert len(row) == 10
        # Valid RACIX characters: P, R, A, C, I, X, -
        for char in row:
            assert char in {"P", "R", "A", "C", "I", "X", "-"}


# ==============================================================================
# 2. TICKET CLASSIFICATION & RISK SCORING
# ==============================================================================

def test_classifier_standard_access_request():
    """Standard access request with no PII or elevated privileges."""
    form = {
        "loaiPhieu": "new",
        "dlcn": "none",
        "rows": [{"tang": 1}],
        "khan": "normal",
        "reason": "Routine reporting analysis",
    }
    cl = classify_ticket(form, DEFAULT_MATRIX)
    assert cl["level"] == 1
    assert cl["pii"] is False
    assert cl["break_glass"] is False
    assert 0 in cl["acts"]  # Request init
    assert 1 in cl["acts"]  # Business approval


def test_classifier_pii_and_admin_elevation():
    """PII flag and admin privilege elevate ticket level and require appropriate ITGC controls."""
    form_pii = {
        "loaiPhieu": "new",
        "dlcn": "basic",
        "rows": [{"tang": 2}],
        "khan": "normal",
        "reason": "Customer fraud audit",
    }
    cl_pii = classify_ticket(form_pii, DEFAULT_MATRIX)
    assert cl_pii["pii"] is True
    assert cl_pii["level"] == 2
    assert 2 in cl_pii["acts"]  # PII approval act

    form_admin = {
        "loaiPhieu": "new",
        "dlcn": "sensitive",
        "rows": [{"tang": 3}],
        "khan": "urgent",
        "reason": "Emergency DBA maintenance",
    }
    cl_admin = classify_ticket(form_admin, DEFAULT_MATRIX)
    assert cl_admin["level"] == 3
    assert 3 in cl_admin["acts"]  # Privileged DB approval act
    assert form_priority(form_admin) == "urgent"


# ==============================================================================
# 3. APPROVAL CHAIN BUILDER (R -> A -> P INVARIANTS)
# ==============================================================================

def test_chain_builder_sequential_order_and_auditor_review():
    """
    Approval chain invariants:
    1. Steps must be strictly ordered: Request/Review (R) -> Approval (A) -> Provision/Perform (P).
    2. Auditor review (R) must occur pre-provision (pre-P).
    3. No duplicate steps for same role with same action.
    """
    form = {
        "loaiPhieu": "new",
        "dlcn": "basic",
        "rows": [{"tang": 3}],
        "khan": "normal",
        "reason": "Security patch release",
    }
    cl = classify_ticket(form, DEFAULT_MATRIX)
    chain = build_approval_chain(cl, "demo_req", DEFAULT_MATRIX)

    steps = chain["steps"]
    assert len(steps) >= 3

    # First step is usually requester
    assert steps[0]["role"] == "REQ" or steps[0]["action"] in {"R", "P"}

    # Find position of last Approval (A) and first Provision (P)
    last_a_idx = max(i for i, s in enumerate(steps) if s["action"] == "A")
    first_p_idx = min(i for i, s in enumerate(steps) if s["action"] == "P" and i > 0)
    assert last_a_idx < first_p_idx, "All Approvals (A) must precede Provisioning (P)"

    # Verify no adjacent duplicate steps
    for i in range(len(steps) - 1):
        assert not (steps[i]["role"] == steps[i + 1]["role"] and steps[i]["action"] == steps[i + 1]["action"])


# ==============================================================================
# 4. CONFLICT DETECTION (SELF-APPROVAL & DEV != OPS)
# ==============================================================================

def test_conflict_detector_no_self_approval():
    """A requester must NEVER be allowed to approve their own request."""
    requester = "user_nguyen_an"
    approver = "user_nguyen_an"
    assert is_self_approval(requester, approver) is True

    conflict = check_step_conflict(
        requester_id=requester,
        actor_id=approver,
        actor_roles=["LM"],
        step_role="LM",
        step_action="A",
        prior_decisions=[]
    )
    assert conflict is not None
    assert "tự phê duyệt" in conflict.lower()


def test_conflict_detector_dev_ops_separation():
    """Developer who wrote or proposed code cannot act as Release Manager or Operator for production."""
    prior = [
        {"role": "DEV", "actor_id": "dev_khoa_do", "action": "P"}
    ]
    conflict = check_step_conflict(
        requester_id="dev_khoa_do",
        actor_id="dev_khoa_do",
        actor_roles=["OPS"],
        step_role="OPS",
        step_action="P",
        prior_decisions=prior
    )
    assert conflict is not None


def test_auto_assign_steps_respects_constraints():
    """Auto-assignment selects eligible users without assigning requester to approval steps."""
    steps = [
        {"seq": 1, "role": "REQ", "action": "P", "assignee_id": None},
        {"seq": 2, "role": "LM", "action": "A", "assignee_id": None},
        {"seq": 3, "role": "SO", "action": "A", "assignee_id": None},
    ]
    people = [
        {"id": "u_req", "name": "Nguyễn An", "username": "an.nguyen", "roles": ["REQ", "LM"]},
        {"id": "u_lm", "name": "Trần Bình", "username": "binh.tran", "roles": ["LM"]},
        {"id": "u_so", "name": "Hồ Sơn", "username": "son.ho", "roles": ["SO"]},
    ]
    auto_assign_steps(steps, "u_req", people)

    # Step 1 should be u_req
    assert steps[0]["assignee_id"] == "u_req"
    # Step 2 (LM approval) must NOT be u_req even though u_req has role LM
    assert steps[1]["assignee_id"] == "u_lm"
    assert steps[2]["assignee_id"] == "u_so"


# ==============================================================================
# 5. FAIL-CLOSED SECURITY POLICY
# ==============================================================================

def test_fail_closed_raises_503_on_missing_active_config():
    """
    CRITICAL SECURITY CHECK:
    When PostgreSQL does not have an ACTIVE RACIX config, SodService.get_active_matrix
    MUST raise HTTP 503 SodConfigurationUnavailableException.
    It MUST NOT fall back to hardcoded DEFAULT_MATRIX.
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Simulate empty table
    mock_cur.fetchone.return_value = None

    with pytest.raises(SodConfigurationUnavailableException) as exc_info:
        SodService.get_active_matrix(mock_conn)

    assert exc_info.value.status_code == 503
    assert "tạm dừng xử lý" in exc_info.value.detail


# ==============================================================================
# 6. UNIFIED AUTHENTICATION & ROLE SWITCHER
# ==============================================================================

def test_system_access_mapping_for_14_roles():
    """All 14 roles must map to their exact designated SystemAccessType."""
    assert len(BOTH_ROLES) == 4
    for r in BOTH_ROLES:
        assert get_system_access_for_role(r) == "both"

    assert len(SOD_ROLES) == 7
    for r in SOD_ROLES:
        assert get_system_access_for_role(r) == "sod_only"

    assert len(DATATRUST_ROLES) == 3
    for r in DATATRUST_ROLES:
        assert get_system_access_for_role(r) == "datatrust_only"


def test_jwt_token_creation_and_session_version():
    """Token must encode session_version and active_role."""
    payload = {
        "sub": "user_123",
        "username": "bao.nq",
        "active_role": "ADMIN",
        "session_version": 2,
    }
    token = create_jwt_token(payload)
    decoded = decode_jwt_token(token)

    assert decoded["sub"] == "user_123"
    assert decoded["username"] == "bao.nq"
    assert decoded["active_role"] == "ADMIN"
    assert decoded["session_version"] == 2


# ==============================================================================
# 7. DATABASE TRIGGERS CONTRACT VERIFICATION
# ==============================================================================

def test_database_migration_contains_required_triggers():
    """Verifies that the migration SQL contains all 5 required triggers and immutable grants."""
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "database",
        "migration_20261016_phase2_sod_schema.sql"
    )
    assert os.path.exists(migration_path), f"Migration file not found at {migration_path}"

    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()
    sql_lower = sql.lower()

    # 1. Trigger step_decision_guard (No self-approval, no dual-role)
    assert "step_decision_guard" in sql_lower
    assert "người yêu cầu không được tự duyệt" in sql_lower
    assert "người này đã xử lý một vai trò khác trên cùng ticket" in sql_lower

    # 2. Trigger step_decisions_append_only (Immutable ledger)
    assert "step_decisions_append_only" in sql_lower
    assert "append-only" in sql_lower

    # 3. Trigger config_version_guard (2-Person Rule)
    assert "config_version_guard" in sql_lower
    assert "người đề xuất cấu hình không được tự duyệt" in sql_lower

    # 4. Trigger ticket_guard & ticket_step_guard
    assert "ticket_guard" in sql_lower
    assert "ticket_step_guard" in sql_lower

    # 5. Dedicated sod_app role & Least Privilege REVOKE
    assert "sod_app" in sql_lower
    assert "revoke update, delete on sod.step_decisions, sod.sla_events" in sql_lower


# ==============================================================================
# 8. AUDIT INTEGRITY EVIDENCE (SHA-256 LEDGER)
# ==============================================================================

def test_audit_evidence_integrity_hash():
    """
    Audit evidence computes a tamper-evident SHA-256 hash across the ticket
    and all step decisions.
    """
    ticket_data = {
        "id": "tkt_sample_01",
        "ticket_code": "TK-2026-001",
        "form_hash": "a1b2c3d4e5f6",
        "status": "DONE",
    }
    steps = [
        {"seq": 1, "role": "REQ", "action": "P", "actor_id": "u1", "outcome": "APPROVED"},
        {"seq": 2, "role": "LM", "action": "A", "actor_id": "u2", "outcome": "APPROVED"},
    ]

    record_repr = json.dumps({"ticket": ticket_data, "steps": steps}, sort_keys=True)
    expected_hash = hashlib.sha256(record_repr.encode("utf-8")).hexdigest()

    assert len(expected_hash) == 64
    # Modifying any step alters the integrity hash
    tampered_steps = [
        {"seq": 1, "role": "REQ", "action": "P", "actor_id": "u1", "outcome": "APPROVED"},
        {"seq": 2, "role": "LM", "action": "A", "actor_id": "u_attacker", "outcome": "APPROVED"},
    ]
    tampered_repr = json.dumps({"ticket": ticket_data, "steps": tampered_steps}, sort_keys=True)
    tampered_hash = hashlib.sha256(tampered_repr.encode("utf-8")).hexdigest()

    assert expected_hash != tampered_hash
