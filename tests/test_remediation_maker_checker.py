import uuid
import pytest
from datetime import datetime, timezone

from backend.database.models import (
    ProposalStatus,
    RemediationRiskLevel,
    StructuredRemediationProposalModel,
)
from backend.ai.services.remediation_service import RemediationService


@pytest.fixture
def remediation_service():
    service = RemediationService()
    # Stub fetch_quarantine_records so test runs independently of DB state
    service.fetch_quarantine_records = lambda qids: [
        {
            "quarantine_id": qid,
            "lineage_hash": f"hash_{qid}",
            "raw_record_json": {"id": qid, "val": "sample"},
        }
        for qid in qids
    ]
    return service


def test_b15_legal_basis_requires_human_gate_and_legal_role(remediation_service):
    """B15 (GDPR Art 6 driver legal basis) must not auto-remediate to contract; requires HITL maker-checker."""
    q_ids = [str(uuid.uuid4())]
    proposal = remediation_service.create_proposal(
        finding_id="FINDING-B15-DRV-0003",
        run_id="RUN-B15-TEST",
        dataset_id="dim_drivers",
        column="legal_basis",
        quarantine_ids=q_ids,
        operation_id="MANUAL_RECONCILIATION",
        params={"proposed_value": "contract", "contract_doc_ref": "DOC-2026-XANH-0003"},
        reason="GDPR-006: Tài xế thiếu căn cứ pháp lý, đề xuất bổ sung hợp đồng lao động",
        proposer="AI_AGENT",
    )

    # 1. State must be PENDING_MAKER_CHECKER, risk HIGH, requires 2nd approval
    assert proposal.status == ProposalStatus.PENDING_MAKER_CHECKER
    assert proposal.risk_level == RemediationRiskLevel.HIGH
    assert proposal.requires_second_approval is True

    # 2. General data steward cannot approve legal basis without legal role
    with pytest.raises(PermissionError, match="bắt buộc phải do DPO hoặc LEGAL phê duyệt"):
        remediation_service.approve_proposal(
            proposal_id=proposal.proposal_id,
            actor_id="analyst_bob",
            actor_role="DATA_STEWARD",
        )

    # 3. Legal/DPO can approve first stage
    remediation_service.approve_proposal(
        proposal_id=proposal.proposal_id,
        actor_id="dpo_alice",
        actor_role="DPO",
    )
    assert proposal.status == ProposalStatus.PENDING_2ND_APPROVAL
    assert proposal.approved_by == "dpo_alice"

    # 4. Same approver cannot do second approval
    with pytest.raises(PermissionError, match="Approver thứ hai phải là một người dùng khác"):
        remediation_service.approve_proposal(
            proposal_id=proposal.proposal_id,
            actor_id="dpo_alice",
            actor_role="LEGAL",
        )

    # 5. Second distinct approver completes approval
    remediation_service.approve_proposal(
        proposal_id=proposal.proposal_id,
        actor_id="legal_charlie",
        actor_role="LEGAL",
    )
    assert proposal.status == ProposalStatus.APPROVED
    assert proposal.second_approved_by == "legal_charlie"

    # Approval records the decision, but legal basis is never mutated by automation.
    with pytest.raises(PermissionError, match="cannot be auto-remediated"):
        remediation_service.execute_remediation_transaction(
            proposal_id=proposal.proposal_id,
            actor_id="admin_executor",
            actor_role="ADMIN",
        )


def test_f8_gps_drift_proposal_enters_pending_maker_checker(remediation_service):
    """F8 (GPS Drift) proposals must enter PENDING_MAKER_CHECKER and block Silver merge until approved."""
    q_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    proposal = remediation_service.create_proposal(
        finding_id="FINDING-F8-GPS-DRIFT",
        run_id="RUN-F8-TEST",
        dataset_id="synthetic_ev_telemetry_ved_ref",
        column="latitude",
        quarantine_ids=q_ids,
        operation_id="CALIBRATE_TELEMETRY",
        params={"calibration_offset": 0.0001, "reference_map": "HANOI_INNER_ZONE"},
        reason="F8: GPS Alleyway Drift detected; proposed snap-to-road reconstruction",
        proposer="AI_AGENT",
    )

    # Must enter PENDING_MAKER_CHECKER
    assert proposal.status == ProposalStatus.PENDING_MAKER_CHECKER

    # Cannot be executed directly while PENDING_MAKER_CHECKER
    with pytest.raises(ValueError, match="Proposal chưa được phê duyệt"):
        remediation_service.execute_remediation_transaction(
            proposal_id=proposal.proposal_id,
            actor_id="admin_user",
            actor_role="ADMIN",
        )

    # Checker approves proposal
    remediation_service.approve_proposal(
        proposal_id=proposal.proposal_id,
        actor_id="steward_jane",
        actor_role="DATA_STEWARD",
    )
    assert proposal.status == ProposalStatus.APPROVED


def test_maker_checker_proposer_cannot_approve(remediation_service):
    """A human proposer cannot approve their own proposal."""
    q_ids = [str(uuid.uuid4())]
    proposal = remediation_service.create_proposal(
        finding_id="FINDING-CUSTOM-01",
        run_id="RUN-TEST",
        dataset_id="dim_customers",
        column="phone_number",
        quarantine_ids=q_ids,
        operation_id="MASK_PHONE",
        params={"prefix_len": 3, "suffix_len": 2},
        reason="Test phone mask",
        proposer="engineer_john",
    )

    # Advance to dry run passed
    proposal.status = ProposalStatus.DRY_RUN_PASSED

    with pytest.raises(PermissionError, match="Người tạo đề xuất không được tự phê duyệt"):
        remediation_service.approve_proposal(
            proposal_id=proposal.proposal_id,
            actor_id="engineer_john",
            actor_role="ADMIN",
        )
