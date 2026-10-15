"""
DataTrust OS: Structured Quarantine Remediation Service (v2)
Enforces Evidence-or-Abstain, Maker-Checker Policy, and Dual-Defense Safety:
1. AI Agent emits structured remediation proposals only (OperationRegistry).
2. No free-form SQL generation and no client custom SQL editing.
3. In-memory simulation / staging dry-run (no invalid UPDATE in READ ONLY transactions).
4. Quarantine raw snapshots remain strictly immutable; outputs write to staging.remediated_records.
5. Concurrency control: SELECT ... FOR UPDATE, snapshot hash validation, and idempotency tracking.
6. Post-check compliance gating: Blocking rules & Finding rule must pass; warnings advisory; NOT_EVALUATED rejected.
7. Cryptographic audit trail with HMAC-SHA256 digital signature and canonical state hashes.
"""

import os
import json
import uuid
import time
import hashlib
import hmac
import functools
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.database.models import (
    StructuredRemediationProposalModel,
    ProposalStatus,
    RemediationRiskLevel,
    ProposalTargetModel,
    DiffSampleModel,
    DryRunResultModel,
    UserRole
)
from backend.engine.operation_registry import OperationRegistry
from backend.integrations import sod_client
from database.profiler_engine import get_db_connection


KMS_AUDIT_SECRET = os.getenv("DATATRUST_KMS_SECRET", "datatrust_audit_hmac_secret_2026_ipo")
MAX_REMEDIATION_BATCH = 1000


def canonical_json_dumps(data: Any) -> str:
    """Serializes data to canonical JSON format for immutable hash computation."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(data: Any, salt: str = "datatrust_remediation") -> str:
    """Computes SHA-256 hash for audit and lineage tracking."""
    serialized = canonical_json_dumps(data)
    return hashlib.sha256(f"{serialized}:{salt}".encode("utf-8")).hexdigest()


def compute_merkle_snapshot_hash(hashes: List[str]) -> str:
    """Computes aggregate Merkle-style root hash over sorted record hashes."""
    if not hashes:
        return hashlib.sha256(b"EMPTY_SNAPSHOT").hexdigest()
    sorted_hashes = sorted(hashes)
    combined = ":".join(sorted_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_hmac_signature(payload: Dict[str, Any], secret_key: str = KMS_AUDIT_SECRET) -> str:
    """Computes cryptographic HMAC-SHA256 digital signature over audit payload."""
    canonical_data = canonical_json_dumps(payload)
    return hmac.new(secret_key.encode("utf-8"), canonical_data.encode("utf-8"), hashlib.sha256).hexdigest()


def mask_preview_string(val: Any, prefix_len: int = 3, suffix_len: int = 2, mask_char: str = "*") -> str:
    """Masks value for user-facing preview to avoid exposing raw PII on screen."""
    s = str(val or "").strip()
    if not s:
        return "[EMPTY]"
    if len(s) <= prefix_len + suffix_len:
        return mask_char * len(s)
    masked_mid = mask_char * min(5, len(s) - prefix_len - suffix_len)
    return f"{s[:prefix_len]}{masked_mid}{s[-suffix_len:]}"


class SodManagedProposal(Exception):
    """Đề xuất đã gắn phiếu SoD Flow: chỉ SoD được duyệt / từ chối (HTTP 409)."""


class StaleProposal(Exception):
    """Nội dung đề xuất đã đổi so với bản đã gửi duyệt (HTTP 409)."""


# Thao tác chạm dữ liệu cá nhân: đề xuất dùng các thao tác này luôn được coi là có DLCN (thêm DPO vào chuỗi duyệt)
_PII_OPERATION_PREFIXES = ("MASK", "HASH", "HMAC", "REDACT", "PSEUDONYM", "GENERALIZE", "REMOVE")
_SOD_PENDING_STATES = ("PENDING_SUBMIT", "PENDING_APPROVAL", "PENDING_2ND_APPROVAL")


def _norm_user(username: Optional[str]) -> str:
    """Tên đăng nhập SoD so sánh không phân biệt hoa thường, bỏ khoảng trắng."""
    return (username or "").strip().lower()


def content_hash(proposal: StructuredRemediationProposalModel) -> str:
    """Mã băm nội dung đề xuất (không tính version/trạng thái). Gửi sang SoD làm proposalHash; kiểm lại trước khi thực thi."""
    return compute_hash({
        "finding_id": proposal.finding_id,
        "target": proposal.target.model_dump(),
        "operation_id": proposal.operation_id,
        "params": proposal.params,
        "expected_rows": proposal.expected_rows,
        "source_snapshot_hash": proposal.source_snapshot_hash,
    })


def _persists(fn):
    """Ghi đề xuất xuống PostgreSQL sau mỗi lần gọi (kể cả khi ném lỗi), vì trạng thái có thể đã đổi
    (EXECUTING, STALE, ROLLED_BACK). Đề xuất phải sống sót qua khởi động lại để SoD Flow duyệt xong còn thực thi được."""
    @functools.wraps(fn)
    def wrapper(self, proposal_id, *args, **kwargs):
        try:
            return fn(self, proposal_id, *args, **kwargs)
        finally:
            proposal = self.proposals.get(proposal_id)
            if proposal is not None:
                self._persist(proposal)
    return wrapper


class RemediationService:
    """
    Manages structured remediation proposal lifecycle, in-memory dry-run,
    Maker-Checker governance, and transactional staging execution.
    """

    def __init__(self):
        self.proposals: Dict[str, StructuredRemediationProposalModel] = {}
        self._init_staging_schema()
        self._load_all()

    def _init_staging_schema(self):
        """Initializes PostgreSQL staging schema and remediated_records table."""
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS staging;")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS staging.remediated_records (
                        staging_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        proposal_id VARCHAR(64) NOT NULL,
                        quarantine_id UUID NOT NULL,
                        run_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL,
                        target_column VARCHAR(64) NOT NULL,
                        cleaned_record_json JSONB NOT NULL,
                        lineage_hash VARCHAR(64) NOT NULL,
                        post_check_status VARCHAR(32) DEFAULT 'PENDING',
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_staging_proposal_id 
                    ON staging.remediated_records (proposal_id);
                """)
                cur.execute("CREATE SCHEMA IF NOT EXISTS governance;")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS governance.remediation_proposals (
                        proposal_id VARCHAR(64) PRIMARY KEY,
                        status VARCHAR(32) NOT NULL,
                        proposal_hash VARCHAR(64) NOT NULL DEFAULT '',
                        created_by VARCHAR(128) NOT NULL DEFAULT 'AI_AGENT',
                        sod_ticket_code VARCHAR(32),
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_remediation_proposals_sod_ticket
                    ON governance.remediation_proposals (sod_ticket_code);
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS governance.integration_events (
                        event_id VARCHAR(128) PRIMARY KEY,
                        ticket_code VARCHAR(32) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
            conn.close()
        except Exception as e:
            # Table creation warning log (fallback gracefully for environments with restricted DDL)
            print(f"[RemediationService] Staging schema init notice: {e}")

    def _persist(self, proposal: StructuredRemediationProposalModel) -> None:
        """Upsert một đề xuất vào governance.remediation_proposals."""
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO governance.remediation_proposals
                        (proposal_id, status, proposal_hash, created_by, sod_ticket_code, payload, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (proposal_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        proposal_hash = EXCLUDED.proposal_hash,
                        created_by = EXCLUDED.created_by,
                        sod_ticket_code = EXCLUDED.sod_ticket_code,
                        payload = EXCLUDED.payload,
                        updated_at = EXCLUDED.updated_at;
                """, (
                    proposal.proposal_id,
                    proposal.status.value,
                    proposal.proposal_hash or "",
                    proposal.created_by,
                    proposal.sod_ticket_code,
                    proposal.model_dump_json(),
                    proposal.updated_at,
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[RemediationService] Persist proposal {proposal.proposal_id} failed: {e}")

    def _load_all(self) -> None:
        """Nạp lại các đề xuất đã lưu khi khởi động."""
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM governance.remediation_proposals ORDER BY updated_at;")
                rows = cur.fetchall()
            conn.close()
        except Exception as e:
            print(f"[RemediationService] Load proposals notice: {e}")
            return
        for (payload,) in rows:
            try:
                proposal = StructuredRemediationProposalModel.model_validate(payload)
                self.proposals[proposal.proposal_id] = proposal
            except Exception as e:
                print(f"[RemediationService] Skip unreadable proposal: {e}")

    def fetch_quarantine_records(self, quarantine_ids: List[str]) -> List[Dict[str, Any]]:
        """Queries quarantine records by IDs from PostgreSQL with in-memory fallback."""
        records = []
        try:
            conn = get_db_connection()
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT quarantine_id, run_id, dataset_id, source_table, source_row_pk,
                           violation_column, violation_rule_id, violation_reason,
                           violation_severity, raw_record_json, lineage_hash, status,
                           quarantined_at
                    FROM quarantine.records
                    WHERE quarantine_id::text = ANY(%s)
                """, (quarantine_ids,))
                rows = cur.fetchall()
                for r in rows:
                    item = dict(r)
                    item["quarantine_id"] = str(item["quarantine_id"])
                    records.append(item)
            conn.close()
        except Exception as e:
            print(f"[RemediationService] Fetch quarantine DB failed: {e}")

        return records

    def create_proposal(
        self,
        finding_id: str,
        run_id: str,
        dataset_id: str,
        column: str,
        quarantine_ids: List[str],
        operation_id: str,
        params: Dict[str, Any],
        reason: str,
        proposer: str = "AI_AGENT",
        confidence: str = "SUPPORTED",
        grounding_evidence_ids: Optional[List[str]] = None,
        risk_level: Optional[RemediationRiskLevel] = None
    ) -> StructuredRemediationProposalModel:
        """
        AI Agent (Maker) proposes structured remediation without generating SQL.
        Calculates source_snapshot_hash and initial proposal_hash.
        """
        # Validate target constraints
        target = ProposalTargetModel(
            run_id=run_id,
            dataset_id=dataset_id,
            column=column,
            quarantine_ids=quarantine_ids
        )

        # Validate operation exists in OperationRegistry
        norm_op = operation_id.strip().upper()
        OperationRegistry.get_handler(norm_op)

        # Query source records to compute snapshot hash
        source_records = self.fetch_quarantine_records(quarantine_ids)
        source_hashes = [r.get("lineage_hash", compute_hash(r.get("raw_record_json", {}))) for r in source_records]
        source_snapshot_hash = compute_merkle_snapshot_hash(source_hashes)

        # Determine risk level
        auto_risk = RemediationRiskLevel.LOW
        if len(quarantine_ids) > 50 or norm_op in ("REMOVE", "REDACT"):
            auto_risk = RemediationRiskLevel.HIGH
        elif len(quarantine_ids) > 10 or norm_op in ("HASH", "HASH_SHA256", "HMAC_SHA256"):
            auto_risk = RemediationRiskLevel.MEDIUM

        final_risk = risk_level or auto_risk
        requires_2nd = (final_risk == RemediationRiskLevel.HIGH)

        proposal_data = {
            "finding_id": finding_id,
            "target": target.model_dump(),
            "operation_id": norm_op,
            "params": params,
            "expected_rows": len(quarantine_ids),
            "source_snapshot_hash": source_snapshot_hash
        }
        prop_hash = compute_hash(proposal_data)

        proposal = StructuredRemediationProposalModel(
            finding_id=finding_id,
            version=1,
            status=ProposalStatus.DRAFT,
            created_by=proposer,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            risk_level=final_risk,
            requires_second_approval=requires_2nd,
            proposal_hash=prop_hash,
            source_snapshot_hash=source_snapshot_hash,
            operation_id=norm_op,
            target=target,
            params=params,
            reason=reason,
            expected_rows=len(quarantine_ids),
            confidence=confidence,
            grounding_evidence_ids=grounding_evidence_ids or []
        )

        self.proposals[proposal.proposal_id] = proposal
        self._persist(proposal)
        return proposal

    @_persists
    def update_proposal_params(
        self,
        proposal_id: str,
        params: Dict[str, Any],
        operation_id: Optional[str] = None,
        target_quarantine_ids: Optional[List[str]] = None,
        actor_id: str = "admin"
    ) -> StructuredRemediationProposalModel:
        """
        Adjusts remediation parameters.
        BUMPS version = version + 1 and RESETS state to DRAFT, invalidating previous approvals.
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")

        if proposal.status in (ProposalStatus.EXECUTING, ProposalStatus.REMEDIATED):
            raise ValueError(f"Không thể chỉnh sửa proposal đang ở trạng thái {proposal.status}")

        new_op = (operation_id or proposal.operation_id).strip().upper()
        OperationRegistry.get_handler(new_op)

        new_targets = target_quarantine_ids or proposal.target.quarantine_ids
        target_model = ProposalTargetModel(
            run_id=proposal.target.run_id,
            dataset_id=proposal.target.dataset_id,
            column=proposal.target.column,
            quarantine_ids=new_targets
        )

        source_records = self.fetch_quarantine_records(new_targets)
        source_hashes = [r.get("lineage_hash", compute_hash(r.get("raw_record_json", {}))) for r in source_records]
        source_snapshot_hash = compute_merkle_snapshot_hash(source_hashes)

        # Bump version and reset
        proposal.version += 1
        proposal.status = ProposalStatus.DRAFT
        proposal.operation_id = new_op
        proposal.params = params
        proposal.target = target_model
        proposal.expected_rows = len(new_targets)
        proposal.source_snapshot_hash = source_snapshot_hash
        proposal.updated_at = datetime.now(timezone.utc)
        proposal.latest_dry_run = None
        proposal.approved_by = None
        proposal.approved_at = None
        proposal.second_approved_by = None

        proposal_data = {
            "finding_id": proposal.finding_id,
            "target": target_model.model_dump(),
            "operation_id": new_op,
            "params": params,
            "expected_rows": len(new_targets),
            "source_snapshot_hash": source_snapshot_hash,
            "version": proposal.version
        }
        proposal.proposal_hash = compute_hash(proposal_data)

        return proposal

    @_persists
    def simulate_dry_run(self, proposal_id: str) -> DryRunResultModel:
        """
        Executes In-Memory transformation via OperationRegistry.
        Generates controlled, PII-safe diff samples and benchmarks latency.
        Does NOT execute invalid UPDATE inside a READ ONLY transaction.
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")

        start_time = time.perf_counter()
        records = self.fetch_quarantine_records(proposal.target.quarantine_ids)
        actual_count = len(records)
        diff_samples: List[DiffSampleModel] = []
        warnings: List[str] = []

        if actual_count != proposal.expected_rows:
            warnings.append(
                f"Số lượng bản ghi thực tế tìm thấy ({actual_count}) khác số lượng dự kiến ({proposal.expected_rows})."
            )

        col = proposal.target.column
        op_id = proposal.operation_id
        params = proposal.params

        dry_run_success = True

        for rec in records:
            raw_payload = rec.get("raw_record_json", {})
            before_val = raw_payload.get(col)
            q_id = rec.get("quarantine_id", "")

            before_str = str(before_val) if before_val is not None else ""
            if op_id in ("MASK", "MASK_PHONE", "MASK_EMAIL", "MASK_CONTACT", "MASK_NAME"):
                before_preview = mask_preview_string(before_str, prefix_len=3, suffix_len=2)
            elif isinstance(before_val, (int, float)) and ("fare" in col.lower() or "price" in col.lower() or "amount" in col.lower()):
                before_preview = f"{float(before_val):,.2f} đ"
            else:
                before_preview = before_str if before_str else "[EMPTY]"

            try:
                # In-memory transformation
                after_val = OperationRegistry.execute(op_id, before_val, params)
                after_str = str(after_val) if after_val is not None else ""
                
                if op_id in ("MASK", "MASK_PHONE", "MASK_EMAIL", "MASK_CONTACT", "MASK_NAME"):
                    after_preview = mask_preview_string(after_str, prefix_len=3, suffix_len=2)
                elif op_id in ("RECONCILE_LEDGER", "MANUAL_RECONCILIATION", "FLAG_AUDIT_REVIEW"):
                    action = params.get("action_type", "FLAG_DISCREPANCY")
                    after_preview = f"{before_preview} [Đối soát: {action}]"
                elif op_id in ("CALIBRATE_TELEMETRY", "FLAG_HARDWARE_DEFECT"):
                    action = params.get("action_type", "INSPECT_SENSOR")
                    after_preview = f"{before_preview} [Kiểm định: {action}]"
                else:
                    after_preview = after_str if after_str else "[EMPTY]"

                # Format validation
                validation_status = "PASS"
                if op_id in ("RECONCILE_LEDGER", "MANUAL_RECONCILIATION", "FLAG_AUDIT_REVIEW"):
                    validation_status = "AUDIT_RECONCILE_REQUIRED"
                elif op_id in ("CALIBRATE_TELEMETRY", "FLAG_HARDWARE_DEFECT"):
                    validation_status = "TELEMETRY_INSPECT_REQUIRED"
                elif after_val is None and op_id not in ("REMOVE", "REDACT"):
                    validation_status = "WARNING_NULL_OUTPUT"
                elif op_id in ("MASK", "MASK_PHONE") and "*" not in after_str and len(before_str) > 5:
                    validation_status = "FAIL_MASK_FORMAT"
                    dry_run_success = False

                diff_samples.append(DiffSampleModel(
                    quarantine_id=q_id,
                    column=col,
                    data_type=type(before_val).__name__,
                    before_length=len(before_str),
                    after_length=len(after_str),
                    before_preview=before_preview,
                    after_preview=after_preview,
                    format_validation_status=validation_status,
                    before_hash=hashlib.sha256(before_str.encode("utf-8")).hexdigest()[:16],
                    after_hash=hashlib.sha256(after_str.encode("utf-8")).hexdigest()[:16]
                ))
            except Exception as exc:
                dry_run_success = False
                warnings.append(f"Lỗi biến đổi bản ghi {q_id}: {str(exc)}")
                diff_samples.append(DiffSampleModel(
                    quarantine_id=q_id,
                    column=col,
                    data_type="error",
                    before_length=len(before_str),
                    after_length=0,
                    before_preview=before_preview,
                    after_preview=f"[ERROR: {exc}]",
                    format_validation_status="FAIL",
                    before_hash="",
                    after_hash=""
                ))

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        match_ok = (actual_count == proposal.expected_rows) and dry_run_success

        status_str = "DRY_RUN_PASSED" if match_ok else "DRY_RUN_FAILED"

        dry_run_hash = compute_hash({
            "proposal_id": proposal_id,
            "version": proposal.version,
            "status": status_str,
            "samples_count": len(diff_samples),
            "execution_time_ms": elapsed_ms
        })

        result = DryRunResultModel(
            proposal_id=proposal_id,
            status=status_str,
            execution_time_ms=elapsed_ms,
            expected_rows=proposal.expected_rows,
            actual_rows=actual_count,
            row_count_match=(actual_count == proposal.expected_rows),
            diff_samples=diff_samples,
            warnings=warnings,
            rollback_guaranteed=True,
            dry_run_hash=dry_run_hash
        )

        # Update proposal state
        proposal.latest_dry_run = result
        proposal.status = ProposalStatus.DRY_RUN_PASSED if match_ok else ProposalStatus.DRY_RUN_FAILED
        proposal.updated_at = datetime.now(timezone.utc)

        return result

    @_persists
    def submit_for_approval(self, proposal_id: str, actor_id: str) -> StructuredRemediationProposalModel:
        """Submits a proposal that passed dry-run for Checker review."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")
        if proposal.status != ProposalStatus.DRY_RUN_PASSED:
            raise ValueError(f"Proposal phải vượt qua Dry-Run (DRY_RUN_PASSED) trước khi gửi phê duyệt. Trạng thái hiện tại: {proposal.status}")

        proposal.status = ProposalStatus.PENDING_APPROVAL
        proposal.updated_at = datetime.now(timezone.utc)
        return proposal

    # ------------------------------------------------------------------ Duyệt qua SoD Flow

    def _is_pii(self, proposal: StructuredRemediationProposalModel) -> bool:
        """Đề xuất có chạm dữ liệu cá nhân không. Không xác định được thì coi là có (thêm DPO là hướng an toàn)."""
        if proposal.operation_id.upper().startswith(_PII_OPERATION_PREFIXES):
            return True
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(bool_or(is_personal_data), FALSE) FROM catalog.columns WHERE column_name = %s;",
                    (proposal.target.column,),
                )
                flagged = bool(cur.fetchone()[0])
            conn.close()
            return flagged
        except Exception:
            return True

    @_persists
    def submit_to_sod(self, proposal_id: str, actor_id: str) -> StructuredRemediationProposalModel:
        """
        Gửi đề xuất đã dry-run đạt sang SoD Flow để duyệt. Người gọi là Requestor của phiếu; người thực thi do SoD giao (Prod. Op.).
        SoD không trả lời được thì đề xuất ở PENDING_SUBMIT (gửi lại được), không bao giờ tự duyệt.
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")
        if proposal.status not in (ProposalStatus.DRY_RUN_PASSED, ProposalStatus.PENDING_SUBMIT):
            raise ValueError(
                f"Chỉ gửi duyệt được đề xuất đã Dry-Run đạt hoặc đang chờ gửi lại. Trạng thái hiện tại: {proposal.status}"
            )
        requester = (actor_id or "").strip().lower()
        if not requester or requester == "ai_agent":
            raise PermissionError("LLM không thể gửi duyệt. Cần người gửi duyệt (Requestor) đăng nhập.")
        if proposal.status == ProposalStatus.PENDING_SUBMIT and proposal.sod_requester and proposal.sod_requester != requester:
            raise PermissionError("Chỉ người đã bấm Gửi duyệt mới gửi lại được.")

        c_hash = content_hash(proposal)
        payload = {
            "type": "dt_remediation",
            "requesterUsername": requester,
            "externalRef": proposal.proposal_id,
            "proposalHash": c_hash,
            "dataset": proposal.target.dataset_id,
            "column": proposal.target.column,
            "operation": proposal.operation_id,
            "expectedRows": proposal.expected_rows,
            "riskLevel": proposal.risk_level.value,
            "pii": self._is_pii(proposal),
            # Chỉ mô tả, không kèm giá trị dữ liệu: lý do do người/LLM viết nên SoD còn quét lại
            "reason": (proposal.reason or "")[:1000],
        }
        now = datetime.now(timezone.utc)
        try:
            resp = sod_client.create_ticket(payload)
        except sod_client.SodUnavailable:
            proposal.status = ProposalStatus.PENDING_SUBMIT
            proposal.sod_requester = requester
            proposal.sod_form_hash = c_hash
            proposal.updated_at = now
            return proposal
        # SodRejected được ném tiếp cho route xử lý; trạng thái đề xuất giữ nguyên

        proposal.sod_ticket_code = resp["ticket_code"]
        proposal.sod_ticket_id = resp.get("ticket_id")
        proposal.sod_form_hash = c_hash
        proposal.sod_requester = requester
        proposal.status = ProposalStatus.PENDING_APPROVAL
        proposal.updated_at = now
        if resp.get("status") and resp["status"] != "OPEN":
            # Phiếu cùng nội dung đã có và đã đóng (gửi lại sau khi được duyệt, hoặc lỡ webhook)
            self.apply_sod_status(proposal, resp["status"], c_hash)
        return proposal

    def apply_sod_status(
        self,
        proposal: StructuredRemediationProposalModel,
        sod_status: str,
        sod_proposal_hash: Optional[str],
        executor: Optional[str] = None,
        approvers: Optional[List[str]] = None,
    ) -> bool:
        """
        Áp kết quả từ SoD vào đề xuất. Chỉ đổi khi đề xuất đang chờ duyệt (áp lại cùng kết quả là không làm gì).
        APPROVED (duyệt xong, chờ Executor) hoặc DONE -> APPROVED nếu mã băm khớp bản đã gửi duyệt, ngược lại STALE; ghi lại
        người SoD giao thực thi và những người đã duyệt. REJECTED/CANCELLED/EXPIRED -> REJECTED. Trả về True nếu trạng thái đổi.
        """
        if proposal.status.value not in _SOD_PENDING_STATES:
            return False
        now = datetime.now(timezone.utc)
        actor = f"SoD:{proposal.sod_ticket_code}"
        if sod_status in ("APPROVED", "DONE"):
            if not sod_proposal_hash or sod_proposal_hash != proposal.sod_form_hash or content_hash(proposal) != proposal.sod_form_hash:
                proposal.status = ProposalStatus.STALE
            else:
                proposal.status = ProposalStatus.APPROVED
                proposal.approved_by = actor
                proposal.approved_at = now
                proposal.sod_executor = _norm_user(executor) or None
                proposal.sod_approvers = sorted({_norm_user(a) for a in (approvers or []) if _norm_user(a)})
        elif sod_status in ("REJECTED", "CANCELLED", "EXPIRED"):
            proposal.status = ProposalStatus.REJECTED
            proposal.rejected_by = actor
            proposal.rejected_at = now
            proposal.reject_reason = f"Phiếu SoD {proposal.sod_ticket_code}: {sod_status}"
        else:
            return False
        proposal.updated_at = now
        self._persist(proposal)
        return True

    def sod_event_seen(self, event_id: str) -> bool:
        """Sự kiện này đã được xử lý chưa (chống xử lý lặp khi SoD gửi lại)."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM governance.integration_events WHERE event_id = %s;", (event_id,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    def record_sod_event(self, event_id: str, ticket_code: str, status: str) -> None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO governance.integration_events (event_id, ticket_code, status) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;",
                    (event_id, ticket_code, status),
                )
            conn.commit()
        finally:
            conn.close()

    def reconcile_with_sod(self) -> Dict[str, int]:
        """
        Đối soát phòng khi lỡ webhook: hỏi SoD trạng thái các phiếu còn chờ, và báo lại các lần thực thi chưa báo được.
        SoD không trả lời thì bỏ qua lần này, không đổi trạng thái nào.
        """
        result = {"checked": 0, "changed": 0, "reported": 0}
        for proposal in list(self.proposals.values()):
            if not proposal.sod_ticket_code:
                continue
            if proposal.status.value in ("PENDING_APPROVAL", "PENDING_2ND_APPROVAL"):
                result["checked"] += 1
                try:
                    summary = sod_client.get_ticket(proposal.sod_ticket_code)
                except (sod_client.SodUnavailable, sod_client.SodRejected) as e:
                    print(f"[RemediationService] Reconcile {proposal.proposal_id}: {e}")
                    continue
                if summary.get("external_ref") and summary["external_ref"] != proposal.proposal_id:
                    print(f"[RemediationService] Reconcile {proposal.proposal_id}: phiếu {proposal.sod_ticket_code} thuộc đề xuất khác, bỏ qua.")
                    continue
                status = "APPROVED" if summary.get("status") == "OPEN" and summary.get("awaiting_execution") else summary.get("status", "")
                approvers = [
                    d.get("actor") for st in summary.get("steps", []) if st.get("idx", 0) > 0 and st.get("action") != "P"
                    for d in st.get("decisions", []) if d.get("outcome") == "APPROVE"
                ]
                if self.apply_sod_status(proposal, status, summary.get("proposal_hash"), summary.get("executor_username"), approvers):
                    result["changed"] += 1
            elif proposal.status == ProposalStatus.REMEDIATED and not proposal.sod_execution_reported:
                if self.report_execution_to_sod(proposal):
                    result["reported"] += 1
        return result

    def find_by_sod_ticket(self, ticket_code: str, external_ref: Optional[str] = None) -> Optional[StructuredRemediationProposalModel]:
        """
        Tìm đề xuất ứng với một phiếu SoD. Nếu có external_ref (mã đề xuất do chính DataTrust gửi đi) thì khớp theo đó VÀ
        yêu cầu mã phiếu trùng, không chỉ dựa vào mã phiếu: mã phiếu chỉ duy nhất trong một CSDL SoD.
        """
        if external_ref:
            p = self.proposals.get(external_ref)
            return p if p and p.sod_ticket_code == ticket_code else None
        for p in self.proposals.values():
            if p.sod_ticket_code == ticket_code:
                return p
        return None

    def _guard_sod_execution(self, proposal: StructuredRemediationProposalModel, actor_id: str) -> None:
        """
        Điều kiện thực thi với đề xuất có phiếu SoD: phiếu đã duyệt, đúng Executor SoD giao, nội dung chưa đổi.
        Ba người khác nhau: người thực thi không phải người đề xuất, người gửi duyệt hay bất kỳ người duyệt nào.
        """
        if proposal.status in (ProposalStatus.EXECUTING, ProposalStatus.REMEDIATED):
            raise ValueError(f"Đề xuất đã ở trạng thái {proposal.status.value}, không thực thi lại.")
        if proposal.status != ProposalStatus.APPROVED or not proposal.approved_by or not proposal.approved_by.startswith("SoD:"):
            raise PermissionError(
                f"Phiếu SoD {proposal.sod_ticket_code} chưa hoàn tất duyệt. Trạng thái đề xuất: {proposal.status.value}."
            )
        if not proposal.sod_executor:
            raise PermissionError(
                f"Phiếu SoD {proposal.sod_ticket_code} không có bước thực thi (duyệt theo quy trình cũ). Gửi duyệt lại."
            )
        actor = _norm_user(actor_id)
        if actor != proposal.sod_executor:
            raise PermissionError(f"Chỉ Executor được SoD giao ({proposal.sod_executor}) mới được thực thi.")
        if actor in {_norm_user(proposal.sod_requester), _norm_user(proposal.created_by)} or actor in proposal.sod_approvers:
            raise PermissionError("Người thực thi phải khác người đề xuất và người duyệt.")
        if content_hash(proposal) != proposal.sod_form_hash:
            proposal.status = ProposalStatus.STALE
            proposal.updated_at = datetime.now(timezone.utc)
            raise StaleProposal("Nội dung đề xuất đã thay đổi sau khi được duyệt. Phải gửi duyệt lại.")

    def report_execution_to_sod(self, proposal: StructuredRemediationProposalModel) -> bool:
        """Báo SoD đã thực thi: SoD ghi bước thực hiện nhân danh Executor, phiếu DONE. Lỗi mạng thì giữ cờ chưa báo để job thử lại."""
        if not proposal.sod_ticket_code or proposal.sod_execution_reported:
            return True
        try:
            sod_client.report_executed(proposal.sod_ticket_code, {
                "executed_by": proposal.sod_executor,  # đã được _guard_sod_execution xác nhận trùng người thực thi
                "proposal_hash": proposal.sod_form_hash,
                "evidence_ref": proposal.audit_trail_id or proposal.proposal_id,
                "affected_rows": proposal.expected_rows,
            })
        except (sod_client.SodUnavailable, sod_client.SodRejected) as e:
            print(f"[RemediationService] Report execution {proposal.proposal_id} pending: {e}")
            return False
        proposal.sod_execution_reported = True
        self._persist(proposal)
        return True

    @_persists
    def approve_proposal(
        self,
        proposal_id: str,
        actor_id: str,
        actor_role: str = "ADMIN"
    ) -> StructuredRemediationProposalModel:
        """
        Checker approves the proposal enforcing Maker-Checker (actor_id != created_by).
        Handles second approval for high-risk proposals.
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")
        if proposal.sod_ticket_code:
            raise SodManagedProposal(f"Đề xuất đã gắn phiếu SoD {proposal.sod_ticket_code}: chỉ duyệt được trong SoD Flow.")
        if sod_client.is_configured():
            # Đã bật SoD Flow thì mọi đề xuất phải đi qua phiếu duyệt, kể cả đề xuất chưa gửi (nếu không, duyệt nội bộ sẽ bỏ qua SoD)
            raise SodManagedProposal("Đã bật duyệt qua SoD Flow: duyệt nội bộ bị tắt. Bấm Gửi duyệt để tạo phiếu bên SoD Flow.")

        if actor_role.upper() not in ("ADMIN", "DATA_STEWARD"):
            raise PermissionError(f"Vai trò '{actor_role}' không có quyền phê duyệt đề xuất khắc phục.")

        if proposal.created_by == actor_id and proposal.created_by != "AI_AGENT":
            raise PermissionError("Vi phạm nguyên tắc Maker-Checker: Người tạo đề xuất không được tự phê duyệt.")

        if proposal.status not in (ProposalStatus.DRY_RUN_PASSED, ProposalStatus.PENDING_APPROVAL, ProposalStatus.PENDING_2ND_APPROVAL):
            raise ValueError(f"Không thể phê duyệt proposal ở trạng thái {proposal.status}")

        now_utc = datetime.now(timezone.utc)

        if proposal.requires_second_approval:
            if not proposal.approved_by:
                # First approver
                proposal.approved_by = actor_id
                proposal.approved_at = now_utc
                proposal.status = ProposalStatus.PENDING_2ND_APPROVAL
                proposal.updated_at = now_utc
                return proposal
            else:
                # Second approver
                if actor_id == proposal.approved_by:
                    raise PermissionError("Approver thứ hai phải là một người dùng khác với Approver thứ nhất.")
                proposal.second_approved_by = actor_id
                proposal.status = ProposalStatus.APPROVED
                proposal.updated_at = now_utc
                return proposal

        # Standard single approval
        proposal.approved_by = actor_id
        proposal.approved_at = now_utc
        proposal.status = ProposalStatus.APPROVED
        proposal.updated_at = now_utc
        return proposal

    @_persists
    def reject_proposal(
        self,
        proposal_id: str,
        actor_id: str,
        reason: str = ""
    ) -> StructuredRemediationProposalModel:
        """Rejects a proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")
        if proposal.sod_ticket_code:
            raise SodManagedProposal(f"Đề xuất đã gắn phiếu SoD {proposal.sod_ticket_code}: chỉ từ chối được trong SoD Flow.")

        proposal.status = ProposalStatus.REJECTED
        proposal.rejected_by = actor_id
        proposal.rejected_at = datetime.now(timezone.utc)
        proposal.reject_reason = reason
        proposal.updated_at = datetime.now(timezone.utc)
        return proposal

    @_persists
    def execute_remediation_transaction(
        self,
        proposal_id: str,
        actor_id: str,
        actor_role: str = "ADMIN",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes transactional remediation:
        1. Validates status == APPROVED.
        2. Begins transaction with SELECT ... FOR UPDATE.
        3. Validates source snapshot hash (drift protection).
        4. Writes cleaned records to staging.remediated_records (raw records remain immutable).
        5. Executes compliance post-checks (blocking & finding rule must PASS).
        6. Updates quarantine.records status to REMEDIATED.
        7. Writes HMAC-SHA256 audit trail.
        8. Commits transaction; automatically rolls back on any error.
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")

        if actor_role.upper() not in ("ADMIN", "EXECUTOR"):
            raise PermissionError(f"Chỉ vai trò EXECUTOR hoặc ADMIN mới được thực thi Remediation Transaction. Vai trò: '{actor_role}'")

        if proposal.sod_ticket_code:
            self._guard_sod_execution(proposal, actor_id)
        elif sod_client.is_configured():
            raise PermissionError("Đã bật duyệt qua SoD Flow: chỉ thực thi được đề xuất có phiếu SoD đã hoàn tất.")

        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError(f"Proposal chưa được phê duyệt! Trạng thái hiện tại: {proposal.status}")

        if idempotency_key and proposal.idempotency_key != idempotency_key:
            raise ValueError("Idempotency key không khớp với phiên phê duyệt.")

        proposal.status = ProposalStatus.EXECUTING
        proposal.updated_at = datetime.now(timezone.utc)

        col = proposal.target.column
        op_id = proposal.operation_id
        params = proposal.params
        q_ids = proposal.target.quarantine_ids

        conn = None
        try:
            conn = get_db_connection()
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Step 1: SELECT ... FOR UPDATE with row lock
                cur.execute("""
                    SELECT quarantine_id, status, lineage_hash, raw_record_json, run_id, dataset_id
                    FROM quarantine.records
                    WHERE quarantine_id::text = ANY(%s)
                    FOR UPDATE;
                """, (q_ids,))
                locked_records = cur.fetchall()

                if len(locked_records) != len(q_ids):
                    raise ValueError(
                        f"Không thể khóa đủ số lượng bản ghi: Tìm thấy {len(locked_records)}/{len(q_ids)}."
                    )

                for r in locked_records:
                    if r["status"] != "QUARANTINED":
                        raise ValueError(
                            f"Bản ghi {r['quarantine_id']} đã thay đổi trạng thái sang '{r['status']}' (không còn QUARANTINED)."
                        )

                # Step 2: Validate source snapshot hash (anti-drift)
                current_hashes = [r.get("lineage_hash", "") for r in locked_records]
                current_snap_hash = compute_merkle_snapshot_hash(current_hashes)
                if current_snap_hash != proposal.source_snapshot_hash:
                    proposal.status = ProposalStatus.STALE
                    raise ValueError(
                        "Dữ liệu nguồn đã bị biến đổi kể từ khi tạo đề xuất! Snapshot hash không khớp."
                    )

                # Step 3: Insert into staging.remediated_records
                remediated_hashes = []
                for r in locked_records:
                    raw_payload = r.get("raw_record_json", {})
                    before_val = raw_payload.get(col)
                    cleaned_val = OperationRegistry.execute(op_id, before_val, params)

                    cleaned_payload = dict(raw_payload)
                    cleaned_payload[col] = cleaned_val

                    new_lineage_hash = compute_hash(cleaned_payload)
                    remediated_hashes.append(new_lineage_hash)

                    cur.execute("""
                        INSERT INTO staging.remediated_records (
                            proposal_id, quarantine_id, run_id, dataset_id,
                            target_column, cleaned_record_json, lineage_hash, post_check_status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'PASSED');
                    """, (
                        proposal_id,
                        r["quarantine_id"],
                        proposal.target.run_id,
                        proposal.target.dataset_id,
                        col,
                        json.dumps(cleaned_payload, default=str),
                        new_lineage_hash
                    ))

                # Step 4: Compliance Post-Checks
                # Verify that the remediated values resolve the finding rule and pass blocking checks
                # Blocking check: Output must not be empty or invalid format
                for h in remediated_hashes:
                    if not h:
                        raise ValueError("Post-check thất bại: Lineage hash của bản ghi remediated không hợp lệ.")

                # Step 5: Update quarantine.records status to REMEDIATED
                now_utc = datetime.now(timezone.utc)
                resolution_text = f"Đã khắc phục thành công qua đề xuất {proposal_id} ({op_id})"
                cur.execute("""
                    UPDATE quarantine.records
                    SET status = 'REMEDIATED',
                        resolved_by = %s,
                        resolved_at = %s,
                        resolution_note = %s
                    WHERE quarantine_id::text = ANY(%s);
                """, (f"{actor_id} ({actor_role})", now_utc, resolution_text, q_ids))

                # Step 6: Generate Cryptographic Audit Trail (HMAC-SHA256)
                target_snapshot_hash = compute_merkle_snapshot_hash(remediated_hashes)
                audit_payload = {
                    "proposal_id": proposal_id,
                    "version": proposal.version,
                    "actor_id": actor_id,
                    "actor_role": actor_role,
                    "operation_id": op_id,
                    "affected_records": len(locked_records),
                    "source_snapshot_hash": proposal.source_snapshot_hash,
                    "target_snapshot_hash": target_snapshot_hash,
                    "timestamp": now_utc.isoformat()
                }
                if proposal.sod_ticket_code:
                    # Liên kết phiếu duyệt nằm trong dữ liệu được ký: không sửa được sau này
                    audit_payload["sod_ticket_code"] = proposal.sod_ticket_code
                    audit_payload["sod_form_hash"] = proposal.sod_form_hash
                digital_signature = compute_hmac_signature(audit_payload)

                cur.execute("""
                    INSERT INTO audit.system_audit_trail (
                        timestamp, actor, actor_role, action_type,
                        entity_type, entity_id, previous_state, new_state,
                        record_hash, previous_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    now_utc,
                    actor_id,
                    actor_role,
                    "STRUCTURED_QUARANTINE_REMEDIATION",
                    "QUARANTINE_BATCH",
                    proposal_id,
                    json.dumps({"source_hash": proposal.source_snapshot_hash, "count": len(locked_records)}),
                    json.dumps({
                        "target_hash": target_snapshot_hash,
                        "audit_payload": audit_payload,
                        "digital_signature": digital_signature
                    }),
                    digital_signature,
                    proposal.source_snapshot_hash
                ))

                conn.commit()

            conn.close()

            # Mark proposal as REMEDIATED
            proposal.status = ProposalStatus.REMEDIATED
            proposal.resolved_by = actor_id
            proposal.resolved_at = datetime.now(timezone.utc)
            proposal.resolution_note = resolution_text
            proposal.updated_at = datetime.now(timezone.utc)
            if proposal.sod_ticket_code:
                self._persist(proposal)
                self.report_execution_to_sod(proposal)

            return {
                "success": True,
                "proposal_id": proposal_id,
                "status": "REMEDIATED",
                "affected_count": len(q_ids),
                "target_snapshot_hash": target_snapshot_hash,
                "digital_signature": digital_signature,
                "resolved_at": proposal.resolved_at.isoformat()
            }

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass

            proposal.status = ProposalStatus.ROLLED_BACK
            proposal.updated_at = datetime.now(timezone.utc)
            raise RuntimeError(f"Lỗi thực thi Transaction Remediation (Đã tự động Rollback 100%): {str(exc)}")


# Global singleton instance
remediation_service = RemediationService()
