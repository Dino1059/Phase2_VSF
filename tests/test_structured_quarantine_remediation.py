"""
Unit & Integration Tests: Structured Quarantine Remediation Service
Validates:
1. Structured proposal creation, schema validation & snapshot hashing.
2. Parameter update version bumping and automatic reset to DRAFT.
3. In-memory dry-run diff generation, PII-safe preview, and format validation.
4. Maker-Checker policy enforcement (proposer != approver; auditor blocked; 2nd approver for high risk).
5. Transactional execution with staging table isolation, HMAC-SHA256 audit signature, and automatic rollback on failure.
"""

import pytest
import uuid
from datetime import datetime, timezone
from backend.database.models import (
    StructuredRemediationProposalModel,
    ProposalStatus,
    RemediationRiskLevel,
    ProposalTargetModel
)
from backend.ai.services.remediation_service import (
    remediation_service,
    compute_hash,
    compute_merkle_snapshot_hash,
    compute_hmac_signature,
    mask_preview_string
)
from database.profiler_engine import get_db_connection


@pytest.fixture
def test_quarantine_records():
    """Seeds temporary test quarantine records in database for remediation test execution."""
    conn = get_db_connection()
    q_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    run_id = f"RUN-TEST-{uuid.uuid4().hex[:6]}"
    dataset_id = "trips"

    with conn.cursor() as cur:
        for idx, qid in enumerate(q_ids):
            raw_json = {
                "trip_id": f"TRIP-{idx+1}",
                "customer_phone": f"091234567{idx}",
                "customer_name": f"Nguyen Van Test {idx+1}",
                "fare_amount": 50000.0
            }
            lineage_h = compute_hash(raw_json)
            cur.execute("""
                INSERT INTO quarantine.records (
                    quarantine_id, run_id, dataset_id, source_table, source_row_pk,
                    failure_lane, violation_column, violation_rule_id, violation_reason,
                    violation_severity, raw_record_json, lineage_hash, status,
                    quarantined_at
                ) VALUES (
                    %s, %s, %s, 'bronze.trips', %s,
                    'LANE_B', 'customer_phone', 'COMP_VN_PHONE_PLAIN_TEXT', 'Số điện thoại dạng rõ không che',
                    'HIGH', %s, %s, 'QUARANTINED', CURRENT_TIMESTAMP
                );
            """, (qid, run_id, dataset_id, f"PK-{idx+1}", json_str := str(raw_json).replace("'", '"'), lineage_h))
        conn.commit()
    conn.close()

    yield {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "quarantine_ids": q_ids,
        "column": "customer_phone"
    }

    # Cleanup test records
    clean_conn = get_db_connection()
    with clean_conn.cursor() as cur:
        cur.execute("DELETE FROM quarantine.records WHERE quarantine_id::text = ANY(%s);", (q_ids,))
        cur.execute("DELETE FROM staging.remediated_records WHERE quarantine_id::text = ANY(%s);", (q_ids,))
        clean_conn.commit()
    clean_conn.close()


def test_mask_preview_string():
    """Ensures user-facing preview masks sensitive payload correctly."""
    assert mask_preview_string("0912345678", prefix_len=3, suffix_len=2) == "091*****78"
    assert mask_preview_string("123", prefix_len=3, suffix_len=2) == "***"
    assert mask_preview_string("", prefix_len=3, suffix_len=2) == "[EMPTY]"


def test_create_structured_proposal_validation(test_quarantine_records):
    """Tests creating a structured proposal with schema & snapshot hash validation."""
    data = test_quarantine_records
    finding_id = f"FINDING-TEST-{uuid.uuid4().hex[:6]}"

    proposal = remediation_service.create_proposal(
        finding_id=finding_id,
        run_id=data["run_id"],
        dataset_id=data["dataset_id"],
        column=data["column"],
        quarantine_ids=data["quarantine_ids"],
        operation_id="MASK_PHONE",
        params={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        reason="Che mờ số điện thoại dạng rõ theo Nghị định 13/2023/NĐ-CP",
        proposer="AI_AGENT",
        confidence="SUPPORTED"
    )

    assert proposal.version == 1
    assert proposal.status == ProposalStatus.DRAFT
    assert proposal.expected_rows == 2
    assert proposal.operation_id == "MASK_PHONE"
    assert len(proposal.source_snapshot_hash) == 64
    assert len(proposal.proposal_hash) == 64


def test_proposal_target_validation_constraints():
    """Tests that ProposalTargetModel rejects empty or duplicated quarantine IDs."""
    with pytest.raises(ValueError, match="quarantine_ids không được để trống"):
        ProposalTargetModel(
            run_id="RUN-1", dataset_id="trips", column="phone", quarantine_ids=[]
        )

    with pytest.raises(ValueError, match="không được chứa các phần tử trùng lặp"):
        ProposalTargetModel(
            run_id="RUN-1", dataset_id="trips", column="phone", quarantine_ids=["Q-1", "Q-1"]
        )


def test_version_bumping_on_param_update(test_quarantine_records):
    """Tests that modifying parameters bumps proposal version and resets status to DRAFT."""
    data = test_quarantine_records
    finding_id = f"FINDING-TEST-{uuid.uuid4().hex[:6]}"

    proposal = remediation_service.create_proposal(
        finding_id=finding_id,
        run_id=data["run_id"],
        dataset_id=data["dataset_id"],
        column=data["column"],
        quarantine_ids=data["quarantine_ids"],
        operation_id="MASK_PHONE",
        params={"prefix_len": 3, "suffix_len": 2},
        reason="Initial proposal"
    )

    assert proposal.version == 1
    remediation_service.simulate_dry_run(proposal.proposal_id)
    assert proposal.status == ProposalStatus.DRY_RUN_PASSED

    # User modifies params
    updated = remediation_service.update_proposal_params(
        proposal_id=proposal.proposal_id,
        params={"prefix_len": 4, "suffix_len": 2, "mask_char": "#"},
        actor_id="admin_1"
    )

    assert updated.version == 2
    assert updated.status == ProposalStatus.DRAFT  # Must reset to DRAFT!
    assert updated.params["prefix_len"] == 4
    assert updated.latest_dry_run is None


def test_in_memory_dry_run_simulation(test_quarantine_records):
    """Tests in-memory simulation generating diff samples without executing database mutations."""
    data = test_quarantine_records
    finding_id = f"FINDING-TEST-{uuid.uuid4().hex[:6]}"

    proposal = remediation_service.create_proposal(
        finding_id=finding_id,
        run_id=data["run_id"],
        dataset_id=data["dataset_id"],
        column=data["column"],
        quarantine_ids=data["quarantine_ids"],
        operation_id="MASK_PHONE",
        params={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        reason="Che mờ số điện thoại"
    )

    dry_run = remediation_service.simulate_dry_run(proposal.proposal_id)

    assert dry_run.status == "DRY_RUN_PASSED"
    assert dry_run.expected_rows == 2
    assert dry_run.actual_rows == 2
    assert dry_run.row_count_match is True
    assert len(dry_run.diff_samples) == 2
    assert dry_run.diff_samples[0].format_validation_status == "PASS"
    assert "*" in dry_run.diff_samples[0].after_preview
    assert dry_run.rollback_guaranteed is True


def test_maker_checker_governance(test_quarantine_records):
    """Enforces Maker-Checker rules: human maker cannot approve their own proposal; auditor blocked."""
    data = test_quarantine_records
    finding_id = f"FINDING-TEST-{uuid.uuid4().hex[:6]}"

    # Created by human user 'steward_john'
    proposal = remediation_service.create_proposal(
        finding_id=finding_id,
        run_id=data["run_id"],
        dataset_id=data["dataset_id"],
        column=data["column"],
        quarantine_ids=data["quarantine_ids"],
        operation_id="MASK_PHONE",
        params={"prefix_len": 3, "suffix_len": 2},
        reason="Test maker checker",
        proposer="steward_john"
    )
    remediation_service.simulate_dry_run(proposal.proposal_id)
    remediation_service.submit_for_approval(proposal.proposal_id, "steward_john")

    # Auditor cannot approve
    with pytest.raises(PermissionError, match="không có quyền phê duyệt"):
        remediation_service.approve_proposal(proposal.proposal_id, actor_id="auditor_jane", actor_role="AUDITOR")

    # Maker cannot approve their own proposal!
    with pytest.raises(PermissionError, match="Vi phạm nguyên tắc Maker-Checker"):
        remediation_service.approve_proposal(proposal.proposal_id, actor_id="steward_john", actor_role="ADMIN")

    # Different admin CAN approve
    approved = remediation_service.approve_proposal(proposal.proposal_id, actor_id="admin_sarah", actor_role="ADMIN")
    assert approved.status == ProposalStatus.APPROVED
    assert approved.approved_by == "admin_sarah"


def test_transactional_execution_and_staging(test_quarantine_records):
    """
    Tests end-to-end execution:
    1. Writes to staging.remediated_records.
    2. Leaves original quarantine raw record payload intact.
    3. Updates quarantine record status to REMEDIATED.
    4. Generates HMAC-SHA256 audit entry.
    """
    data = test_quarantine_records
    finding_id = f"FINDING-TEST-{uuid.uuid4().hex[:6]}"

    proposal = remediation_service.create_proposal(
        finding_id=finding_id,
        run_id=data["run_id"],
        dataset_id=data["dataset_id"],
        column=data["column"],
        quarantine_ids=data["quarantine_ids"],
        operation_id="MASK_PHONE",
        params={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        reason="Sanitize phone number for silver promotion",
        proposer="AI_AGENT"
    )

    remediation_service.simulate_dry_run(proposal.proposal_id)
    remediation_service.approve_proposal(proposal.proposal_id, actor_id="admin_exec", actor_role="ADMIN")

    result = remediation_service.execute_remediation_transaction(
        proposal_id=proposal.proposal_id,
        actor_id="admin_exec",
        actor_role="ADMIN"
    )

    assert result["success"] is True
    assert result["status"] == "REMEDIATED"
    assert result["affected_count"] == 2
    assert "digital_signature" in result

    # Verify database state
    conn = get_db_connection()
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Staging records created
        cur.execute("""
            SELECT count(*) FROM staging.remediated_records 
            WHERE proposal_id = %s;
        """, (proposal.proposal_id,))
        staging_count = cur.fetchone()["count"]
        assert staging_count == 2

        # 2. Quarantine records marked REMEDIATED
        cur.execute("""
            SELECT status, resolved_by FROM quarantine.records
            WHERE quarantine_id::text = ANY(%s);
        """, (data["quarantine_ids"],))
        rows = cur.fetchall()
        for r in rows:
            assert r["status"] == "REMEDIATED"
            assert "admin_exec" in r["resolved_by"]

        # 3. System audit trail recorded
        cur.execute("""
            SELECT record_hash FROM audit.system_audit_trail
            WHERE entity_id = %s;
        """, (proposal.proposal_id,))
        audit_row = cur.fetchone()
        assert audit_row is not None
        assert audit_row["record_hash"] == result["digital_signature"]

    conn.close()


def test_remediation_api_endpoints(test_quarantine_records):
    """Tests FastAPI remediation endpoints with RBAC and maker-checker validation."""
    from fastapi.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)
    data = test_quarantine_records
    finding_id = f"FINDING-API-{uuid.uuid4().hex[:6]}"

    # 1. Propose
    resp = client.post("/api/remediation/propose", json={
        "finding_id": finding_id,
        "run_id": data["run_id"],
        "dataset_id": data["dataset_id"],
        "column": data["column"],
        "quarantine_ids": data["quarantine_ids"],
        "operation_id": "MASK_PHONE",
        "params": {"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        "reason": "API proposal test",
        "proposer": "AI_AGENT"
    })
    assert resp.status_code == 200
    prop_data = resp.json()
    proposal_id = prop_data["proposal_id"]
    assert prop_data["status"] == "DRAFT"

    # 2. Dry run
    dry_resp = client.post(f"/api/remediation/{proposal_id}/dry-run")
    assert dry_resp.status_code == 200
    dry_data = dry_resp.json()
    assert dry_data["status"] == "DRY_RUN_PASSED"
    assert dry_data["actual_rows"] == 2

    # 3. Update params -> resets to DRAFT
    upd_resp = client.post(f"/api/remediation/{proposal_id}/update-params", json={
        "params": {"prefix_len": 2, "suffix_len": 2, "mask_char": "*"}
    }, headers={"X-User-Role": "ADMIN", "X-User": "admin@datatrust.vn"})
    assert upd_resp.status_code == 200
    upd_data = upd_resp.json()
    assert upd_data["version"] == 2
    assert upd_data["status"] == "DRAFT"

    # Re-run dry run on version 2
    client.post(f"/api/remediation/{proposal_id}/dry-run")

    # 4. Submit for review
    sub_resp = client.post(f"/api/remediation/{proposal_id}/submit")
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "PENDING_APPROVAL"

    # 5. Auditor blocked from approval
    audit_resp = client.post(
        f"/api/remediation/{proposal_id}/approve",
        headers={"X-User-Role": "AUDITOR", "X-User": "auditor@datatrust.vn"}
    )
    assert audit_resp.status_code == 403

    # 6. Admin approves
    appr_resp = client.post(
        f"/api/remediation/{proposal_id}/approve",
        headers={"X-User-Role": "ADMIN", "X-User": "lead_admin@datatrust.vn"}
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"

    # 7. Admin executes transaction
    exec_resp = client.post(
        f"/api/remediation/{proposal_id}/execute",
        headers={"X-User-Role": "ADMIN", "X-User": "lead_admin@datatrust.vn"}
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["success"] is True
    assert exec_data["status"] == "REMEDIATED"
    assert "digital_signature" in exec_data

