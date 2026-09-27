"""
DataTrust OS: Quarantine Manager & Audit Lineage Handler
Handles records that fail policy and quality rules, maintaining SHA-256 lineage.
Enforces that ONLY ADMIN can remediate, override, or discard quarantined records.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.database.models import (
    QuarantineRecordModel,
    QuarantineStatus,
    AuditTrailModel,
    UserRole,
    RuleSeverity
)


def compute_lineage_hash(record_data: Dict[str, Any], salt: str = "datatrust_lineage") -> str:
    """Tạo mã băm SHA-256 bất biến cho bản ghi phục vụ audit trail."""
    serialized = json.dumps(record_data, sort_keys=True, default=str)
    return hashlib.sha256(f"{serialized}:{salt}".encode("utf-8")).hexdigest()


class QuarantineManager:
    def __init__(self):
        self.records: Dict[str, QuarantineRecordModel] = {}
        self.audit_log: List[AuditTrailModel] = []
        self._last_audit_hash = "GENESIS_HASH_DATA_TRUST_OS"

    def record_quarantine(
        self,
        run_id: str,
        dataset_id: str,
        source_table: str,
        source_row_pk: str,
        raw_record: Dict[str, Any],
        violation_column: str,
        violation_rule_id: str,
        violation_reason: str,
        severity: RuleSeverity = RuleSeverity.HIGH
    ) -> QuarantineRecordModel:
        """Ghi nhận bản ghi vi phạm vào Quarantine với mã băm SHA-256."""
        lineage_hash = compute_lineage_hash(raw_record)
        record = QuarantineRecordModel(
            run_id=run_id,
            dataset_id=dataset_id,
            source_table=source_table,
            source_row_pk=source_row_pk,
            violation_column=violation_column,
            violation_rule_id=violation_rule_id,
            violation_reason=violation_reason,
            violation_severity=severity,
            raw_record_json=raw_record,
            lineage_hash=lineage_hash,
            status=QuarantineStatus.QUARANTINED
        )
        self.records[record.quarantine_id] = record
        return record

    def list_records(self, dataset_id: Optional[str] = None, status: Optional[QuarantineStatus] = None) -> List[QuarantineRecordModel]:
        """Truy xuất danh sách bản ghi vi phạm (Cả Admin và Auditor đều xem được)."""
        res = list(self.records.values())
        if dataset_id:
            res = [r for r in res if r.dataset_id == dataset_id]
        if status:
            res = [r for r in res if r.status == status]
        return res

    def get_record(self, quarantine_id: str) -> Optional[QuarantineRecordModel]:
        return self.records.get(quarantine_id)

    def _append_audit(self, actor: str, actor_role: UserRole, action_type: str, entity_id: str, prev_state: Any, new_state: Any):
        payload = f"{self._last_audit_hash}:{actor}:{action_type}:{entity_id}:{datetime.now(timezone.utc)}"
        record_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        audit_entry = AuditTrailModel(
            audit_id=len(self.audit_log) + 1,
            actor=actor,
            actor_role=actor_role,
            action_type=action_type,
            entity_type="QUARANTINE_RECORD",
            entity_id=entity_id,
            previous_state=prev_state,
            new_state=new_state,
            record_hash=record_hash,
            previous_hash=self._last_audit_hash
        )
        self.audit_log.append(audit_entry)
        self._last_audit_hash = record_hash

    # =========================================================================
    # HITL REMEDIATION ACTIONS (ADMIN ONLY)
    # =========================================================================

    def reprocess_record(
        self,
        quarantine_id: str,
        cleaned_payload: Dict[str, Any],
        actor_name: str,
        actor_role: UserRole
    ) -> QuarantineRecordModel:
        """
        Remediation: Áp dụng dữ liệu đã làm sạch và đánh dấu REMEDIATED.
        CHỈ ADMIN MỚI ĐƯỢC PHÉP THỰC HIỆN.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối quyền: Vai trò '{actor_role}' chỉ có quyền xem (Auditor/Viewer), không được phép Remediate!")

        record = self.records.get(quarantine_id)
        if not record:
            raise KeyError(f"Quarantine record {quarantine_id} không tồn tại!")

        prev_state = record.model_dump()
        record.status = QuarantineStatus.REMEDIATED
        record.raw_record_json.update(cleaned_payload)
        record.resolution_note = f"Đã được chỉnh sửa và làm sạch bởi Admin: {actor_name}"
        record.resolved_by = actor_name
        record.resolved_at = datetime.now(timezone.utc)
        record.lineage_hash = compute_lineage_hash(record.raw_record_json)

        self._append_audit(actor_name, actor_role, "ADMIN_REMEDIATE_QUARANTINE", quarantine_id, prev_state, record.model_dump())
        return record

    def approve_override(
        self,
        quarantine_id: str,
        justification: str,
        actor_name: str,
        actor_role: UserRole
    ) -> QuarantineRecordModel:
        """
        Duyệt ngoại lệ nghiệp vụ (Override): Cho phép bản ghi vào Silver kèm biên bản giải trình.
        CHỈ ADMIN MỚI ĐƯỢC PHÉP THỰC HIỆN.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối quyền: Vai trò '{actor_role}' chỉ có quyền xem (Auditor/Viewer), không được phép Override!")

        record = self.records.get(quarantine_id)
        if not record:
            raise KeyError(f"Quarantine record {quarantine_id} không tồn tại!")

        prev_state = record.model_dump()
        record.status = QuarantineStatus.OVERRIDDEN
        record.resolution_note = f"Duyệt ngoại lệ nghiệp vụ: {justification}"
        record.resolved_by = actor_name
        record.resolved_at = datetime.now(timezone.utc)

        self._append_audit(actor_name, actor_role, "ADMIN_OVERRIDE_EXCEPTION", quarantine_id, prev_state, record.model_dump())
        return record

    def discard_record(
        self,
        quarantine_id: str,
        reason: str,
        actor_name: str,
        actor_role: UserRole
    ) -> QuarantineRecordModel:
        """
        Hủy bỏ bản ghi vi phạm (Discard) không đưa vào Silver.
        CHỈ ADMIN MỚI ĐƯỢC PHÉP THỰC HIỆN.
        """
        if actor_role != UserRole.ADMIN:
            raise PermissionError(f"Từ chối quyền: Vai trò '{actor_role}' chỉ có quyền xem (Auditor/Viewer), không được phép Discard!")

        record = self.records.get(quarantine_id)
        if not record:
            raise KeyError(f"Quarantine record {quarantine_id} không tồn tại!")

        prev_state = record.model_dump()
        record.status = QuarantineStatus.DISCARDED
        record.resolution_note = f"Hủy bản ghi: {reason}"
        record.resolved_by = actor_name
        record.resolved_at = datetime.now(timezone.utc)

        self._append_audit(actor_name, actor_role, "ADMIN_DISCARD_QUARANTINE", quarantine_id, prev_state, record.model_dump())
        return record
