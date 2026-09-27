"""
DataTrust OS: AI Agent - Adaptive Policy-to-Rule Proposer
Analyzes Data Catalog (PII Roles) and Compliance Policies.
Proposes parameterized rules across the 5 Treatment Actions.
Performs dry-run simulation on Bronze data to predict pass/quarantine impact.
Enforces Human-in-the-Loop approval: ONLY ADMIN can approve/reject.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid

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
from backend.engine.operation_handlers import execute_operation


class PolicyRuleProposerAgent:
    def __init__(self):
        self.proposals: Dict[str, ProposedRuleModel] = {}

    def propose_rules_for_policy(
        self,
        policy: CompliancePolicyModel,
        columns: List[ColumnModel],
        sample_bronze_records: Optional[List[Dict[str, Any]]] = None
    ) -> List[ProposedRuleModel]:
        """
        AI Agent đọc Policy + Data Catalog columns và tự động suy luận đề xuất Rule/Process.
        Sau đó thực hiện Dry-run simulation trên tập mẫu Bronze để ước lượng tỷ lệ pass/quarantine.
        """
        sample_bronze_records = sample_bronze_records or []
        generated_proposals: List[ProposedRuleModel] = []

        # Trích xuất danh sách pii_roles mà các điều khoản trong policy nhắm tới
        targeted_roles = set()
        for clause in policy.clauses:
            for r in clause.target_pii_roles:
                targeted_roles.add(r)

        for col in columns:
            proposal = None

            # RULE MAPPING LOGIC: Căn cứ vào PII Role và Policy
            if col.pii_role == PiiRoleType.DIRECT_IDENTIFIER:
                if "phone" in col.column_name.lower():
                    proposal = ProposedRuleModel(
                        dataset_id=col.dataset_id,
                        column_name=col.column_name,
                        pii_role=col.pii_role,
                        treatment_action=TreatmentActionType.PSEUDONYMIZE,
                        operation_id="mask_phone",
                        execution_phase=ExecutionPhase.TREATMENT,
                        params_json={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
                        expression_display=f"mask_phone({col.column_name})",
                        rationale=f"Phát hiện trường định danh trực tiếp '{col.column_name}'. Đề xuất bí danh hóa (che mờ) tuân thủ {policy.legal_framework}.",
                        domain="Privacy & Data Protection",
                        severity=RuleSeverity.HIGH,
                        confidence=0.965,
                        law_ref=f"{policy.legal_framework} - Quy định bảo vệ số điện thoại",
                        policy_id=policy.policy_id,
                        status=RuleStatus.PENDING
                    )
                elif "name" in col.column_name.lower():
                    proposal = ProposedRuleModel(
                        dataset_id=col.dataset_id,
                        column_name=col.column_name,
                        pii_role=col.pii_role,
                        treatment_action=TreatmentActionType.PSEUDONYMIZE,
                        operation_id="mask_name",
                        execution_phase=ExecutionPhase.TREATMENT,
                        params_json={"keep_first": True, "mask_char": "*"},
                        expression_display=f"mask_name({col.column_name})",
                        rationale=f"Họ tên khách hàng '{col.column_name}' cần được che mờ tên đệm/tên riêng theo {policy.legal_framework}.",
                        domain="Privacy & Data Protection",
                        severity=RuleSeverity.MEDIUM,
                        confidence=0.940,
                        law_ref=f"{policy.legal_framework} - Quy định bảo vệ danh tính",
                        policy_id=policy.policy_id,
                        status=RuleStatus.PENDING
                    )
                elif "national_id" in col.column_name.lower() or "id_card" in col.column_name.lower():
                    proposal = ProposedRuleModel(
                        dataset_id=col.dataset_id,
                        column_name=col.column_name,
                        pii_role=col.pii_role,
                        treatment_action=TreatmentActionType.REMOVE,
                        operation_id="redact_null",
                        execution_phase=ExecutionPhase.TREATMENT,
                        params_json={},
                        expression_display=f"redact_null({col.column_name})",
                        rationale=f"Số CCCD/Định danh cá nhân '{col.column_name}' không được lưu trữ bản rõ (Data Minimization) theo {policy.legal_framework}.",
                        domain="Privacy & Data Protection",
                        severity=RuleSeverity.CRITICAL,
                        confidence=0.985,
                        law_ref=f"{policy.legal_framework} - Nguyên tắc tối thiểu hóa dữ liệu",
                        policy_id=policy.policy_id,
                        status=RuleStatus.PENDING
                    )

            elif col.pii_role == PiiRoleType.CONTEXTUAL_PERSONAL_DATA:
                if "lat" in col.column_name.lower() or "lon" in col.column_name.lower() or "gps" in col.column_name.lower():
                    proposal = ProposedRuleModel(
                        dataset_id=col.dataset_id,
                        column_name=col.column_name,
                        pii_role=col.pii_role,
                        treatment_action=TreatmentActionType.GENERALIZE,
                        operation_id="round_decimal",
                        execution_phase=ExecutionPhase.TREATMENT,
                        params_json={"decimals": 2},
                        expression_display=f"round_decimal({col.column_name}, 2)",
                        rationale=f"Dữ liệu vị trí địa lý '{col.column_name}' tiết lộ nơi cư trú. Đề xuất làm tròn 2 chữ số thập phân (độ chính xác ~1.1km) theo {policy.legal_framework}.",
                        domain="Privacy & Data Protection",
                        severity=RuleSeverity.MEDIUM,
                        confidence=0.920,
                        law_ref=f"{policy.legal_framework} - Bảo vệ dữ liệu vị trí nhạy cảm",
                        policy_id=policy.policy_id,
                        status=RuleStatus.PENDING
                    )

            elif col.pii_role == PiiRoleType.AMBIGUOUS_UNSTRUCTURED_DATA:
                proposal = ProposedRuleModel(
                    dataset_id=col.dataset_id,
                    column_name=col.column_name,
                    pii_role=col.pii_role,
                    treatment_action=TreatmentActionType.PSEUDONYMIZE,
                    operation_id="hash_sha256",
                    execution_phase=ExecutionPhase.TREATMENT,
                    params_json={"salt": "gsm_unstructured_salt"},
                    expression_display=f"hash_sha256({col.column_name})",
                    rationale=f"Trường văn bản tự do '{col.column_name}' có nguy cơ người dùng tự nhập PII. Đề xuất băm một chiều SHA-256.",
                    domain="Privacy & Data Protection",
                    severity=RuleSeverity.HIGH,
                    confidence=0.910,
                    law_ref=f"{policy.legal_framework} - Xử lý dữ liệu phi cấu trúc",
                    policy_id=policy.policy_id,
                    status=RuleStatus.PENDING
                )

            elif col.pii_role == PiiRoleType.TECHNICAL_METADATA:
                if "temp" in col.column_name.lower():
                    proposal = ProposedRuleModel(
                        dataset_id=col.dataset_id,
                        column_name=col.column_name,
                        pii_role=col.pii_role,
                        treatment_action=TreatmentActionType.KEEP,
                        operation_id="range_check",
                        execution_phase=ExecutionPhase.POST_CHECK,
                        params_json={"min_val": -10, "max_val": 85, "allow_zero": True},
                        expression_display=f"{col.column_name} BETWEEN -10 AND 85",
                        rationale=f"Kiểm tra chất lượng kỹ thuật cảm biến nhiệt độ '{col.column_name}' trong dải -10°C đến 85°C.",
                        domain="Data Quality",
                        severity=RuleSeverity.CRITICAL,
                        confidence=0.990,
                        law_ref="Quy chuẩn An toàn Pin EV GSM 2024",
                        policy_id=policy.policy_id,
                        status=RuleStatus.PENDING
                    )

            if proposal:
                # DRY-RUN SIMULATION TRÊN SAMPLE DATA
                pass_count = 0
                quar_count = 0
                for record in sample_bronze_records:
                    val = record.get(proposal.column_name)
                    _, is_valid, _ = execute_operation(proposal.operation_id, val, proposal.params_json)
                    if is_valid:
                        pass_count += 1
                    else:
                        quar_count += 1
                
                proposal.simulated_pass_rows = pass_count
                proposal.simulated_quarantine_rows = quar_count
                self.proposals[proposal.proposal_id] = proposal
                generated_proposals.append(proposal)

        return generated_proposals

    # =========================================================================
    # HUMAN-IN-THE-LOOP APPROVAL (ADMIN ONLY)
    # =========================================================================

    def approve_proposal(
        self,
        proposal_id: str,
        actor_name: str,
        actor_role: UserRole
    ) -> FieldProcessConfigModel:
        """
        Phê duyệt Rule do AI đề xuất -> Chuyển thành Active Field Process Config.
        CHỈ ADMIN MỚI ĐƯỢC DUYỆT. AUDITOR BỊ TỪ CHỐI.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối quyền duyệt: Vai trò '{actor_role}' chỉ có quyền xem (Auditor/Viewer). Chỉ ADMIN mới có quyền duyệt Rule!")

        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal ID {proposal_id} không tìm thấy!")

        proposal.status = RuleStatus.APPROVED
        proposal.reviewed_by = actor_name
        proposal.reviewed_at = datetime.now(timezone.utc)

        # Chuyển hóa thành Active Field Process Config
        active_config = FieldProcessConfigModel(
            config_id=f"ACT-{proposal.dataset_id.upper()}-{uuid.uuid4().hex[:6].upper()}",
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
        Từ chối Rule do AI đề xuất kèm lý do.
        CHỈ ADMIN MỚI ĐƯỢC THAO TÁC.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối thao tác: Vai trò '{actor_role}' chỉ có quyền xem (Auditor/Viewer). Chỉ ADMIN mới có quyền từ chối Rule!")

        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal ID {proposal_id} không tìm thấy!")

        proposal.status = RuleStatus.REJECTED
        proposal.reviewed_by = actor_name
        proposal.reviewed_at = datetime.now(timezone.utc)
        proposal.review_comments = comments
        return proposal
