"""
DataTrust OS: Rule Proposer Sub-Agent (Strict Human-In-The-Loop)
IMPORTANT GOVERNANCE SPECIFICATION:
1. Generates rule proposals with status = PENDING.
2. Validates proposal syntax internally via ProposalSyntaxValidator.
3. Performs Dry-run simulation to measure pass/quarantine rates on Bronze sample records.
4. STRICTLY NEVER mutates or writes rules directly to Lane B!
5. ONLY a human Administrator (UserRole.ADMIN) can approve and promote a proposal into an active Lane B rule.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import logging

from backend.database.models import (
    ColumnModel,
    CompliancePolicyModel,
    ProposedRuleModel,
    FieldProcessConfigModel,
    PiiRoleType,
    TreatmentActionType,
    ExecutionPhase,
    RuleSeverity,
    RuleStatus,
    UserRole
)
from backend.ai.engine.syntax_validator import ProposalSyntaxValidator
from backend.ai.tools.dry_run_tool import DryRunTool
from backend.ai.engine.react_engine import ReActEngine

logger = logging.getLogger("DataTrust.RuleProposerAgent")


class RuleProposerAgent:
    def __init__(
        self,
        react_engine: Optional[ReActEngine] = None,
        dry_run_tool: Optional[DryRunTool] = None
    ):
        self.react_engine = react_engine or ReActEngine()
        self.dry_run_tool = dry_run_tool or DryRunTool()
        self.proposals: Dict[str, ProposedRuleModel] = {}

    def propose_rules(
        self,
        policy: CompliancePolicyModel,
        columns: List[ColumnModel],
        sample_size: int = 200
    ) -> List[ProposedRuleModel]:
        """
        Generates candidate rule proposals for policy & columns, checks syntax internally,
        runs dry-run simulation, and registers them in PENDING state.
        """
        generated_proposals: List[ProposedRuleModel] = []

        for col in columns:
            candidate = self._generate_candidate_for_column(col, policy)
            if not candidate:
                continue

            # 1. Internal Syntax Validation Check
            is_valid, err_msg = ProposalSyntaxValidator.validate_proposal(
                operation_id=candidate.operation_id,
                params=candidate.params_json,
                expression_display=candidate.expression_display
            )
            if not is_valid:
                logger.warning(f"Proposal for {col.column_name} failed internal validation: {err_msg}")
                continue

            # 2. Dry-Run Simulation (Purely read-only, does not mutate Lane B)
            sim_result = self.dry_run_tool.execute({
                "proposal": candidate.model_dump(),
                "sample_size": sample_size
            })

            candidate.simulated_pass_rows = sim_result.get("simulated_pass_rows", 0)
            candidate.simulated_quarantine_rows = sim_result.get("simulated_quarantine_rows", 0)

            # 3. Store proposal with status strictly PENDING
            candidate.status = RuleStatus.PENDING
            self.proposals[candidate.proposal_id] = candidate
            generated_proposals.append(candidate)

        return generated_proposals

    def _generate_candidate_for_column(
        self,
        col: ColumnModel,
        policy: CompliancePolicyModel
    ) -> Optional[ProposedRuleModel]:
        col_name = col.column_name.lower()

        if col.pii_role == PiiRoleType.DIRECT_IDENTIFIER:
            if "phone" in col_name:
                return ProposedRuleModel(
                    dataset_id=col.dataset_id,
                    column_name=col.column_name,
                    pii_role=col.pii_role,
                    treatment_action=TreatmentActionType.PSEUDONYMIZE,
                    operation_id="mask_phone",
                    execution_phase=ExecutionPhase.TREATMENT,
                    params_json={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
                    expression_display=f"mask_phone({col.column_name})",
                    rationale=f"Che mờ số điện thoại bảo vệ danh tính cá nhân theo {policy.legal_framework}.",
                    domain="Privacy & Data Protection",
                    severity=RuleSeverity.HIGH,
                    confidence=0.965,
                    law_ref=f"{policy.legal_framework} - Quy định bảo vệ số liên lạc",
                    policy_id=policy.policy_id
                )
            elif "name" in col_name:
                return ProposedRuleModel(
                    dataset_id=col.dataset_id,
                    column_name=col.column_name,
                    pii_role=col.pii_role,
                    treatment_action=TreatmentActionType.PSEUDONYMIZE,
                    operation_id="mask_name",
                    execution_phase=ExecutionPhase.TREATMENT,
                    params_json={"keep_first": True, "mask_char": "*"},
                    expression_display=f"mask_name({col.column_name})",
                    rationale=f"Che mờ họ tên khách hàng theo {policy.legal_framework}.",
                    domain="Privacy & Data Protection",
                    severity=RuleSeverity.MEDIUM,
                    confidence=0.940,
                    law_ref=f"{policy.legal_framework} - Quy định bảo vệ họ tên cá nhân",
                    policy_id=policy.policy_id
                )
        elif col.pii_role == PiiRoleType.LINKABLE_IDENTIFIER:
            if "vin" in col_name:
                return ProposedRuleModel(
                    dataset_id=col.dataset_id,
                    column_name=col.column_name,
                    pii_role=col.pii_role,
                    treatment_action=TreatmentActionType.KEEP_RESTRICTED,
                    operation_id="to_upper",
                    execution_phase=ExecutionPhase.TREATMENT,
                    params_json={},
                    expression_display=f"to_upper({col.column_name})",
                    rationale=f"Chuẩn hóa in hoa mã VIN xe điện theo ISO 3779 và {policy.legal_framework}.",
                    domain="Fleet Telematics Standards",
                    severity=RuleSeverity.HIGH,
                    confidence=0.980,
                    law_ref="ISO 3779 Vehicle Identification",
                    policy_id=policy.policy_id
                )
            elif "driver" in col_name:
                return ProposedRuleModel(
                    dataset_id=col.dataset_id,
                    column_name=col.column_name,
                    pii_role=col.pii_role,
                    treatment_action=TreatmentActionType.PSEUDONYMIZE,
                    operation_id="hash_sha256",
                    execution_phase=ExecutionPhase.TREATMENT,
                    params_json={"salt": "gsm_driver_salt_2026"},
                    expression_display=f"hash_sha256({col.column_name})",
                    rationale=f"Bí danh hóa mã tài xế bằng SHA-256 có muối bảo mật theo {policy.legal_framework}.",
                    domain="Data Privacy & Pseudonymization",
                    severity=RuleSeverity.CRITICAL,
                    confidence=0.990,
                    law_ref=f"{policy.legal_framework} Article 5(1)(c)",
                    policy_id=policy.policy_id
                )
        elif col.pii_role == PiiRoleType.CONTEXTUAL_PERSONAL_DATA:
            if any(k in col_name for k in ["lat", "latitude", "lon", "longitude", "gps"]):
                return ProposedRuleModel(
                    dataset_id=col.dataset_id,
                    column_name=col.column_name,
                    pii_role=col.pii_role,
                    treatment_action=TreatmentActionType.GENERALIZE,
                    operation_id="round_decimal",
                    execution_phase=ExecutionPhase.TREATMENT,
                    params_json={"decimals": 2},
                    expression_display=f"round_decimal({col.column_name}, 2)",
                    rationale=f"Làm mờ tọa độ địa lý GPS xuống 2 chữ số thập phân (~1.1km) theo {policy.legal_framework}.",
                    domain="Geolocation Privacy",
                    severity=RuleSeverity.MEDIUM,
                    confidence=0.950,
                    law_ref=f"{policy.legal_framework} - Hạn chế định vị chính xác",
                    policy_id=policy.policy_id
                )

        return None

    # =========================================================================
    # STRICT HITL APPROVAL & REJECTION (ADMIN ROLE REQUIRED)
    # =========================================================================

    def approve_proposal(
        self,
        proposal_id: str,
        actor_name: str,
        actor_role: UserRole
    ) -> FieldProcessConfigModel:
        """
        Promotes a proposed rule to an Active Field Process Config in Lane B.
        Enforces: ONLY ADMIN CAN APPROVE. Non-admin throws PermissionError.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối quyền: Vai trò '{actor_role}' không được phép phê duyệt. Chỉ ADMIN mới có quyền duyệt và cập nhật Lane B!")

        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Không tìm thấy Proposal ID: {proposal_id}")

        proposal.status = RuleStatus.APPROVED
        proposal.reviewed_by = actor_name
        proposal.reviewed_at = datetime.now(timezone.utc)

        # Build active Lane B configuration
        active_config = FieldProcessConfigModel(
            config_id=f"ACT-{proposal.dataset_id.upper().replace('.CSV', '')}-{uuid.uuid4().hex[:6].upper()}",
            dataset_id=proposal.dataset_id,
            column_name=proposal.column_name,
            pii_role=proposal.pii_role,
            treatment_action=proposal.treatment_action,
            operation_id=proposal.operation_id,
            execution_phase=proposal.execution_phase,
            params_json=proposal.params_json,
            expression_display=proposal.expression_display,
            on_fail_action="QUARANTINE",
            severity=proposal.severity,
            policy_id=proposal.policy_id,
            law_ref=proposal.law_ref,
            enforced_by=actor_name,
            enforced_at=datetime.now(timezone.utc),
            is_active=True,
            version=1
        )
        return active_config

    def reject_proposal(
        self,
        proposal_id: str,
        actor_name: str,
        actor_role: UserRole,
        comments: str
    ) -> ProposedRuleModel:
        """
        Rejects a proposed rule with justification.
        Enforces: ONLY ADMIN CAN REJECT. Non-admin throws PermissionError.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối quyền: Vai trò '{actor_role}' không được phép từ chối đề xuất. Chỉ ADMIN mới có quyền!")

        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Không tìm thấy Proposal ID: {proposal_id}")

        proposal.status = RuleStatus.REJECTED
        proposal.reviewed_by = actor_name
        proposal.reviewed_at = datetime.now(timezone.utc)
        proposal.review_comments = comments
        return proposal
