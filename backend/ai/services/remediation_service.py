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
from backend.audit.cryptographic_audit import get_audit_hmac_secret
from database.profiler_engine import get_db_connection


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


def compute_hmac_signature(payload: Dict[str, Any], secret_key: Optional[str] = None) -> str:
    """Computes cryptographic HMAC-SHA256 digital signature over audit payload."""
    secret_key = secret_key or get_audit_hmac_secret()
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


class RemediationService:
    """
    Manages structured remediation proposal lifecycle, in-memory dry-run,
    Maker-Checker governance, and transactional staging execution.
    """

    def __init__(self):
        self.proposals: Dict[str, StructuredRemediationProposalModel] = {}
        self._init_staging_schema()

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
                conn.commit()
            conn.close()
        except Exception as e:
            # Table creation warning log (fallback gracefully for environments with restricted DDL)
            print(f"[RemediationService] Staging schema init notice: {e}")

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

    def _map_row_to_model(self, row: Dict[str, Any]) -> StructuredRemediationProposalModel:
        target_ids = [str(x) for x in (row.get("target_quarantine_ids") or [])]
        target = ProposalTargetModel(
            run_id=row.get("run_id", ""),
            dataset_id=row.get("dataset_id", ""),
            column=row.get("target_column", ""),
            quarantine_ids=target_ids
        )
        dry_run_obj = None
        if row.get("latest_dry_run"):
            try:
                dry_run_data = row["latest_dry_run"] if isinstance(row["latest_dry_run"], dict) else json.loads(row["latest_dry_run"])
                dry_run_obj = DryRunResultModel(**dry_run_data)
            except Exception:
                pass

        status_str = row.get("status", "DRAFT")
        try:
            status_enum = ProposalStatus(status_str)
        except Exception:
            status_enum = ProposalStatus.DRAFT

        risk_str = row.get("risk_level", "MEDIUM")
        try:
            risk_enum = RemediationRiskLevel(risk_str)
        except Exception:
            risk_enum = RemediationRiskLevel.MEDIUM

        params = row.get("params", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}

        return StructuredRemediationProposalModel(
            proposal_id=row["proposal_id"],
            finding_id=row["finding_id"],
            version=row.get("version", 1),
            status=status_enum,
            created_by=row.get("created_by", "ADMIN"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            risk_level=risk_enum,
            proposal_hash=row.get("proposal_hash", ""),
            source_snapshot_hash=row.get("source_snapshot_hash", ""),
            operation_id=row.get("operation_id", "MASK_PHONE"),
            target=target,
            params=params,
            reason=row.get("reason", ""),
            expected_rows=row.get("expected_rows", len(target_ids)),
            latest_dry_run=dry_run_obj,
            proposal_type=row.get("proposal_type") or "EXECUTABLE",
            execution_block_reason=row.get("execution_block_reason"),
            requires_human_input=bool(row.get("requires_human_input", False)),
            created_at=row.get("created_at") or datetime.now(timezone.utc),
            updated_at=row.get("updated_at") or datetime.now(timezone.utc)
        )

    def _persist_proposal(self, proposal: StructuredRemediationProposalModel):
        try:
            conn = get_db_connection()
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO remediation.proposals (
                            proposal_id, finding_id, version, status, dataset_id, target_column,
                            run_id, operation_id, params, target_quarantine_ids, expected_rows,
                            risk_level, reason, source_snapshot_hash, proposal_hash, latest_dry_run,
                            dry_run_hash, created_by, proposal_type, execution_block_reason,
                            requires_human_input, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, NOW()
                        ) ON CONFLICT (proposal_id) DO UPDATE SET
                            version = EXCLUDED.version,
                            status = EXCLUDED.status,
                            operation_id = EXCLUDED.operation_id,
                            params = EXCLUDED.params,
                            target_quarantine_ids = EXCLUDED.target_quarantine_ids,
                            expected_rows = EXCLUDED.expected_rows,
                            risk_level = EXCLUDED.risk_level,
                            reason = EXCLUDED.reason,
                            source_snapshot_hash = EXCLUDED.source_snapshot_hash,
                            proposal_hash = EXCLUDED.proposal_hash,
                            latest_dry_run = EXCLUDED.latest_dry_run,
                            dry_run_hash = EXCLUDED.dry_run_hash,
                            proposal_type = EXCLUDED.proposal_type,
                            execution_block_reason = EXCLUDED.execution_block_reason,
                            requires_human_input = EXCLUDED.requires_human_input,
                            updated_at = NOW();
                    """, (
                        proposal.proposal_id, proposal.finding_id, proposal.version,
                        proposal.status.value if hasattr(proposal.status, "value") else str(proposal.status),
                        proposal.target.dataset_id, proposal.target.column, proposal.target.run_id,
                        proposal.operation_id, json.dumps(proposal.params),
                        proposal.target.quarantine_ids, proposal.expected_rows,
                        proposal.risk_level.value if hasattr(proposal.risk_level, "value") else str(proposal.risk_level),
                        proposal.reason, proposal.source_snapshot_hash, proposal.proposal_hash,
                        json.dumps(proposal.latest_dry_run.model_dump()) if proposal.latest_dry_run else None,
                        proposal.latest_dry_run.dry_run_hash if proposal.latest_dry_run else None,
                        proposal.created_by,
                        proposal.proposal_type,
                        proposal.execution_block_reason,
                        proposal.requires_human_input,
                        proposal.created_at
                    ))
            conn.close()
        except Exception as e:
            pass

    def _persist_proposal_version(self, proposal: StructuredRemediationProposalModel):
        try:
            conn = get_db_connection()
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO remediation.proposal_versions (
                            proposal_id, version, finding_id, dataset_id, target_column,
                            run_id, operation_id, params, target_quarantine_ids, expected_rows,
                            risk_level, reason, dry_run_hash, latest_dry_run, source_snapshot_hash,
                            proposal_hash, created_by, proposal_type, execution_block_reason,
                            requires_human_input, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, NOW()
                        ) ON CONFLICT (proposal_id, version) DO NOTHING;
                    """, (
                        proposal.proposal_id, proposal.version, proposal.finding_id,
                        proposal.target.dataset_id, proposal.target.column, proposal.target.run_id,
                        proposal.operation_id, json.dumps(proposal.params),
                        proposal.target.quarantine_ids, proposal.expected_rows,
                        proposal.risk_level.value if hasattr(proposal.risk_level, "value") else str(proposal.risk_level),
                        proposal.reason,
                        proposal.latest_dry_run.dry_run_hash if proposal.latest_dry_run else None,
                        json.dumps(proposal.latest_dry_run.model_dump()) if proposal.latest_dry_run else None,
                        proposal.source_snapshot_hash, proposal.proposal_hash, proposal.created_by,
                        proposal.proposal_type,
                        proposal.execution_block_reason,
                        proposal.requires_human_input
                    ))
            conn.close()
        except Exception as e:
            pass

    def get_proposal(self, proposal_id: str) -> Optional[StructuredRemediationProposalModel]:
        if proposal_id in self.proposals:
            return self.proposals[proposal_id]
        try:
            conn = get_db_connection()
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM remediation.proposals WHERE proposal_id = %s;", (proposal_id,))
                row = cur.fetchone()
                if row:
                    prop = self._map_row_to_model(dict(row))
                    self.proposals[proposal_id] = prop
                    return prop
            conn.close()
        except Exception:
            pass
        return None

    def get_proposal_by_finding(self, finding_id: str) -> Optional[StructuredRemediationProposalModel]:
        for p in reversed(list(self.proposals.values())):
            if p.finding_id == finding_id:
                return p
        try:
            conn = get_db_connection()
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM remediation.proposals WHERE finding_id = %s ORDER BY version DESC, created_at DESC LIMIT 1;", (finding_id,))
                row = cur.fetchone()
                if row:
                    prop = self._map_row_to_model(dict(row))
                    self.proposals[prop.proposal_id] = prop
                    return prop
            conn.close()
        except Exception:
            pass
        return None

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
        risk_level: Optional[RemediationRiskLevel] = None,
        proposal_type: str = "EXECUTABLE",
        execution_block_reason: Optional[str] = None,
        requires_human_input: bool = False
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

        norm_op = operation_id.strip().upper() if operation_id else "ADVISORY"
        
        # Enforce requires_human_input if operation is manual reconciliation
        if norm_op in ("MANUAL_RECONCILIATION", "RECONCILE_LEDGER"):
            requires_human_input = True

        if proposal_type == "EXECUTABLE":
            # Validate operation exists in OperationRegistry
            OperationRegistry.get_handler(norm_op)
        else:
            proposal_type = "ADVISORY_ONLY"
            if not execution_block_reason:
                execution_block_reason = "Không có automated remediation handler trong RemediationRegistry. Yêu cầu tạo task cho Data Steward / System Owner."
            requires_human_input = False

        # Query source records to compute snapshot hash
        source_records = self.fetch_quarantine_records(quarantine_ids)
        source_hashes = [r.get("lineage_hash", compute_hash(r.get("raw_record_json", {}))) for r in source_records]
        source_snapshot_hash = compute_merkle_snapshot_hash(source_hashes)

        # Determine risk level & HITL requirements
        is_legal_basis_b15 = (column == "legal_basis" or "B15" in finding_id or "GDPR-006" in reason)
        is_f8_gps_drift = ("F8" in finding_id or "drift" in reason.lower() or column in ("latitude", "longitude", "pickup_latitude", "pickup_longitude"))

        auto_risk = RemediationRiskLevel.LOW
        if is_legal_basis_b15 or len(quarantine_ids) > 50 or norm_op in ("REMOVE", "REDACT") or requires_human_input:
            auto_risk = RemediationRiskLevel.HIGH
        elif len(quarantine_ids) > 10 or norm_op in ("HASH", "HASH_SHA256", "HMAC_SHA256"):
            auto_risk = RemediationRiskLevel.MEDIUM

        final_risk = risk_level or auto_risk
        requires_2nd = (final_risk == RemediationRiskLevel.HIGH or is_legal_basis_b15)
        initial_status = ProposalStatus.PENDING_MAKER_CHECKER if (is_legal_basis_b15 or is_f8_gps_drift) else ProposalStatus.DRAFT

        proposal_data = {
            "finding_id": finding_id,
            "target": target.model_dump(),
            "operation_id": norm_op,
            "params": params,
            "expected_rows": len(quarantine_ids),
            "source_snapshot_hash": source_snapshot_hash,
            "proposal_type": proposal_type
        }
        prop_hash = compute_hash(proposal_data)

        proposal = StructuredRemediationProposalModel(
            finding_id=finding_id,
            version=1,
            status=initial_status,
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
            proposal_type=proposal_type,
            execution_block_reason=execution_block_reason,
            requires_human_input=requires_human_input,
            grounding_evidence_ids=grounding_evidence_ids or []
        )

        self.proposals[proposal.proposal_id] = proposal
        self._persist_proposal(proposal)
        self._persist_proposal_version(proposal)
        return proposal

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

        self._persist_proposal(proposal)
        self._persist_proposal_version(proposal)
        return proposal

    def simulate_dry_run(self, proposal_id: str) -> DryRunResultModel:
        """
        Executes In-Memory transformation via OperationRegistry.
        Generates controlled, PII-safe diff samples and benchmarks latency.
        Does NOT execute invalid UPDATE inside a READ ONLY transaction.
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")

        if proposal.proposal_type == "ADVISORY_ONLY":
            raise ValueError(
                f"Đề xuất {proposal_id} thuộc loại ADVISORY_ONLY ({proposal.execution_block_reason or 'Không có automated handler'}). "
                "Hệ thống không cho phép chạy Dry-run đối với đề xuất chỉ mang tính tư vấn."
            )

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

        is_legal_basis_b15 = (proposal.target.column == "legal_basis" or "B15" in proposal.finding_id or "GDPR-006" in proposal.reason)
        allowed_roles = ("ADMIN", "DATA_STEWARD", "LEGAL", "DPO")
        if actor_role.upper() not in allowed_roles:
            raise PermissionError(f"Vai trò '{actor_role}' không có quyền phê duyệt đề xuất khắc phục.")

        if is_legal_basis_b15 and actor_role.upper() not in ("LEGAL", "DPO", "ADMIN"):
            raise PermissionError(f"Đề xuất khắc phục Legal Basis (GDPR Art 6 / B15) bắt buộc phải do DPO hoặc LEGAL phê duyệt.")

        if proposal.created_by == actor_id and proposal.created_by != "AI_AGENT":
            raise PermissionError("Vi phạm nguyên tắc Maker-Checker: Người tạo đề xuất không được tự phê duyệt.")

        if proposal.status not in (
            ProposalStatus.DRY_RUN_PASSED,
            ProposalStatus.PENDING_APPROVAL,
            ProposalStatus.PENDING_2ND_APPROVAL,
            ProposalStatus.PENDING_MAKER_CHECKER,
        ):
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

        proposal.status = ProposalStatus.REJECTED
        proposal.rejected_by = actor_id
        proposal.rejected_at = datetime.now(timezone.utc)
        proposal.reject_reason = reason
        proposal.updated_at = datetime.now(timezone.utc)
        return proposal

    def execute_remediation_transaction(
        self,
        proposal_id: str,
        actor_id: str,
        actor_role: str = "ADMIN",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Thực thi Transaction Remediation chuẩn Phase 3:
        1. Hierarchical locking: Proposal -> Ticket/Subject -> Quarantine rows (sorted by ID ASC).
        2. Live anti-drift check trên dữ liệu thật của quarantine.records.
        3. Fail-Closed HITL gate: Phiếu SoD phải DONE khớp chính xác (proposal_id, version, proposal_hash).
        4. Staging write & compliance post-checks.
        5. Concurrency-safe evidence ledger append với Advisory Lock & sequence_no tường minh.
        6. Nếu lỗi: Tự động rollback dữ liệu và kích hoạt Transaction độc lập ghi nhận REMEDIATION_EXECUTION_FAILED.
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} không tồn tại.")

        if proposal.proposal_type == "ADVISORY_ONLY":
            raise ValueError(
                f"FAIL-CLOSED: Đề xuất {proposal_id} thuộc loại ADVISORY_ONLY ({proposal.execution_block_reason or 'Không có automated handler'}). "
                "Không được phép thực thi tự động hoặc đưa dữ liệu vào Silver."
            )

        if actor_role.upper() != "ADMIN":
            raise PermissionError(f"Chỉ có vai trò ADMIN mới được phép thực thi Remediation Transaction. Vai trò: '{actor_role}'")

        is_legal_basis_b15 = (
            proposal.target.column == "legal_basis"
            or "B15" in proposal.finding_id
            or "GDPR-006" in proposal.reason
        )
        if is_legal_basis_b15:
            raise PermissionError(
                "B15/GDPR legal-basis findings are evidence-only and cannot be auto-remediated. "
                "Record the DPO/LEGAL decision and supporting document instead."
            )

        from backend.sod.integration_service import (
            verify_hitl_approval_gate,
            append_audit_evidence_safely,
            record_execution_failure_independently,
            compute_merkle_snapshot_hash,
            GovernanceException
        )

        col = proposal.target.column
        op_id = proposal.operation_id
        params = proposal.params
        q_ids = proposal.target.quarantine_ids

        conn = None
        try:
            conn = get_db_connection()
            conn.autocommit = False
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. KHÓA PROPOSAL (FOR UPDATE)
                cur.execute("SELECT * FROM remediation.proposals WHERE proposal_id = %s FOR UPDATE;", (proposal_id,))
                prop_row = cur.fetchone()
                if not prop_row:
                    raise KeyError(f"Proposal {proposal_id} không tìm thấy trong CSDL.")

                # Idempotency check
                if prop_row["status"] == "REMEDIATED":
                    cur.execute("""
                        SELECT * FROM remediation.execution_attempts 
                        WHERE proposal_id = %s AND status = 'SUCCEEDED' LIMIT 1;
                    """, (proposal_id,))
                    prev_attempt = cur.fetchone()
                    conn.rollback()
                    conn.close()
                    return {
                        "success": True,
                        "proposal_id": proposal_id,
                        "status": "ALREADY_REMEDIATED",
                        "affected_count": len(q_ids),
                        "attempt": dict(prev_attempt) if prev_attempt else {}
                    }

                # 2. KHÓA TICKET VÀ VERIFY HITL GATE (FAIL-CLOSED)
                ticket_row = verify_hitl_approval_gate(cur, prop_row)

                # 3. KHÓA TỪNG DÒNG QUARANTINE (SORTED ASC ĐỂ CHỐNG DEADLOCK)
                cur.execute("""
                    SELECT quarantine_id, status, lineage_hash, raw_record_json, run_id, dataset_id
                    FROM quarantine.records
                    WHERE quarantine_id::text = ANY(%s)
                    ORDER BY quarantine_id ASC
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

                # 4. ANTI-DRIFT TRÊN DỮ LIỆU THẬT VỪA KHÓA
                live_hashes = [r.get("lineage_hash", "") for r in locked_records]
                live_source_snapshot_hash = compute_merkle_snapshot_hash(live_hashes)

                if live_source_snapshot_hash != prop_row["source_snapshot_hash"] or live_source_snapshot_hash != ticket_row["source_snapshot_hash"]:
                    cur.execute("UPDATE remediation.proposals SET status = 'STALE', updated_at = NOW() WHERE proposal_id = %s;", (proposal_id,))
                    conn.commit()
                    raise GovernanceException(
                        "SOURCE_SNAPSHOT_DRIFT",
                        "Dữ liệu quarantine nguồn trong CSDL đã bị biến đổi so với thời điểm phê duyệt SoD!",
                        {"live_hash": live_source_snapshot_hash, "approved_hash": ticket_row["source_snapshot_hash"]}
                    )

                # 5. GHI VÀO STAGING VÀ POST-CHECKS
                from backend.engine.remediation_registry import RemediationRegistry
                remediated_hashes = []
                cleaned_rows = []
                for r in locked_records:
                    raw_payload = r.get("raw_record_json", {})
                    before_val = raw_payload.get(col)
                    cleaned_val = OperationRegistry.execute(op_id, before_val, params)

                    cleaned_payload = dict(raw_payload)
                    cleaned_payload[col] = cleaned_val

                    # Chạy lại rule gây lỗi và kiểm tra bắt buộc (Post-Check)
                    passed, pc_msg = RemediationRegistry.run_post_check(
                        dataset_id=prop_row["dataset_id"],
                        column=col,
                        before_val=before_val,
                        cleaned_val=cleaned_val,
                        rule_id=r.get("violation_rule_id")
                    )
                    if not passed:
                        raise ValueError(f"Post-Check vi phạm trên bản ghi {r['quarantine_id']}: {pc_msg}")

                    new_lineage_hash = compute_hash(cleaned_payload)
                    remediated_hashes.append(new_lineage_hash)
                    cleaned_rows.append((r, cleaned_payload, new_lineage_hash))

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

                for h in remediated_hashes:
                    if not h:
                        raise ValueError("Post-check thất bại: Lineage hash của bản ghi remediated không hợp lệ.")

                # 6. UPSERT VÀO SILVER QUA ALLOWLISTED SILVER-WRITER
                SILVER_WRITERS = {
                    "ride_hailing_xanh_sm_trips": {"table": "silver.ride_hailing_xanh_sm_trips", "pk": "trip_id"},
                    "trips_clean": {"table": "silver.trips_clean", "pk": "trip_id"},
                    "synthetic_ev_telemetry_ved_ref": {"table": "silver.synthetic_ev_telemetry_ved_ref", "pk": "record_id"},
                    "dim_customers": {"table": "silver.dim_customers", "pk": "customer_id"},
                    "customers_clean": {"table": "silver.customers_clean", "pk": "customer_id"},
                    "dim_drivers": {"table": "silver.dim_drivers", "pk": "driver_id"},
                    "feedback_pii": {"table": "silver.feedback_pii", "pk": "feedback_id"},
                    "synthetic_feedback_scenario_driven": {"table": "silver.synthetic_feedback_scenario_driven", "pk": "feedback_id"},
                    "fleet_index": {"table": "silver.fleet_index", "pk": "vehicle_vin"},
                    "acn_charging_mapped": {"table": "silver.acn_charging_mapped", "pk": "session_id"},
                }

                ds_target = prop_row["dataset_id"].strip().lower()
                writer_config = SILVER_WRITERS.get(ds_target)
                if not writer_config:
                    raise ValueError(f"FAIL-CLOSED: Dataset '{prop_row['dataset_id']}' không có Silver-writer được cấp phép trong allowlist. Không thể đưa bản ghi vào Silver.")

                silver_table = writer_config["table"]
                pk_col = writer_config["pk"]

                # Lấy danh sách cột thực tế của silver_table trong CSDL
                table_parts = silver_table.split(".")
                s_schema = table_parts[0]
                s_table = table_parts[1]
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s;
                """, (s_schema, s_table))
                silver_cols_info = cur.fetchall()
                if not silver_cols_info:
                    raise ValueError(f"FAIL-CLOSED: Bảng Silver '{silver_table}' không tồn tại trong CSDL.")

                silver_col_names = [c["column_name"] for c in silver_cols_info]
                upsert_count = 0

                for r, cleaned_payload, new_lineage_hash in cleaned_rows:
                    record_dict = dict(cleaned_payload)
                    record_dict["lineage_hash"] = new_lineage_hash
                    record_dict["_run_id"] = prop_row["run_id"]
                    record_dict["_processed_at"] = datetime.now(timezone.utc)

                    if pk_col not in record_dict and r.get("source_row_pk"):
                        record_dict[pk_col] = r["source_row_pk"]

                    cols_to_insert = [c for c in silver_col_names if c in record_dict]
                    if pk_col not in cols_to_insert:
                        raise ValueError(f"FAIL-CLOSED: Bản ghi thiếu khóa chính '{pk_col}' cho bảng '{silver_table}'.")

                    vals = [record_dict[c] for c in cols_to_insert]
                    cols_str = ", ".join(f'"{c}"' for c in cols_to_insert)
                    placeholders = ", ".join(["%s"] * len(cols_to_insert))
                    update_cols = [c for c in cols_to_insert if c != pk_col]
                    update_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)

                    upsert_sql = f"""
                        INSERT INTO {silver_table} ({cols_str})
                        VALUES ({placeholders})
                        ON CONFLICT ("{pk_col}") DO UPDATE SET {update_clause};
                    """
                    cur.execute(upsert_sql, vals)
                    upsert_count += 1

                # 7. CHỈ SAU KHI SILVER THÀNH CÔNG: CẬP NHẬT QUARANTINE -> REMEDIATED
                now_utc = datetime.now(timezone.utc)
                resolution_text = f"Đã khắc phục thành công và đưa vào {silver_table} qua đề xuất {proposal_id} ({op_id}) theo phiếu SoD {ticket_row['code']}"
                cur.execute("""
                    UPDATE quarantine.records
                    SET status = 'REMEDIATED',
                        resolved_by = %s,
                        resolved_at = %s,
                        resolution_note = %s
                    WHERE quarantine_id::text = ANY(%s);
                """, (f"{actor_id} ({actor_role})", now_utc, resolution_text, q_ids))

                target_snapshot_hash = compute_merkle_snapshot_hash(remediated_hashes)

                # 8. KHÓA LEDGER HEAD & APPEND REMEDIATION_EXECUTED EVIDENCE
                exec_ev = append_audit_evidence_safely(
                    cur=cur,
                    event_type="REMEDIATION_EXECUTED",
                    run_id=prop_row["run_id"],
                    dataset_id=prop_row["dataset_id"],
                    payload={
                        "event": "REMEDIATION_EXECUTED",
                        "proposal_id": proposal_id,
                        "proposal_version": prop_row["version"],
                        "ticket_id": str(ticket_row["id"]),
                        "ticket_code": ticket_row["code"],
                        "silver_target": silver_table,
                        "upsert_count": upsert_count,
                        "actor_id": actor_id,
                        "actor_role": actor_role,
                        "affected_records": len(locked_records),
                        "source_snapshot_hash": live_source_snapshot_hash,
                        "target_snapshot_hash": target_snapshot_hash,
                        "approval_evidence_id": str(prop_row["approval_evidence_id"]) if prop_row.get("approval_evidence_id") else None
                    },
                    quarantine_count=len(locked_records)
                )

                # 9. CẬP NHẬT PROPOSAL STATUS = REMEDIATED
                cur.execute("""
                    UPDATE remediation.proposals
                    SET status = 'REMEDIATED', updated_at = NOW()
                    WHERE proposal_id = %s;
                """, (proposal_id,))

                # 10. GHI NHẬN EXECUTION ATTEMPT THÀNH CÔNG
                cur.execute("""
                    INSERT INTO remediation.execution_attempts (
                        proposal_id, proposal_version, proposal_hash, ticket_id,
                        actor_id, actor_role, idempotency_key, status, affected_rows,
                        source_snapshot_hash, target_snapshot_hash, approval_evidence_id, execution_evidence_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'SUCCEEDED', %s, %s, %s, %s, %s);
                """, (
                    proposal_id, prop_row["version"], prop_row["proposal_hash"], ticket_row["id"],
                    actor_id, actor_role, idempotency_key, len(locked_records),
                    live_source_snapshot_hash, target_snapshot_hash,
                    prop_row.get("approval_evidence_id"), exec_ev["evidence_id"]
                ))

                # 11. ĐÓNG FINDING TRONG AUDIT.FINDINGS -> RESOLVED
                cur.execute("""
                    UPDATE audit.findings
                    SET status = 'RESOLVED', resolved_at = NOW(), resolved_by = %s
                    WHERE finding_id = %s;
                """, (f"{actor_id} ({actor_role} via SoD {ticket_row['code']})", prop_row["finding_id"]))

                conn.commit()

            conn.close()

            proposal.status = ProposalStatus.REMEDIATED
            proposal.resolved_by = actor_id
            proposal.resolved_at = now_utc
            proposal.resolution_note = resolution_text
            proposal.updated_at = now_utc

            return {
                "success": True,
                "proposal_id": proposal_id,
                "status": "REMEDIATED",
                "ticket_code": ticket_row["code"],
                "silver_target": silver_table,
                "upsert_count": upsert_count,
                "affected_count": len(q_ids),
                "target_snapshot_hash": target_snapshot_hash,
                "execution_evidence_id": exec_ev["evidence_id"],
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

            # Record failure independently in separate transaction!
            err_code = getattr(exc, "error_code", "EXECUTION_ERROR")
            err_msg = str(exc)
            try:
                record_execution_failure_independently(
                    proposal_id=proposal_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    idempotency_key=idempotency_key,
                    error_code=err_code,
                    error_message=err_msg,
                    conn=get_db_connection()
                )
            except Exception as failure_rec_err:
                logger.error(f"Failed to record failure evidence: {failure_rec_err}")

            if isinstance(exc, GovernanceException):
                raise
            raise RuntimeError(f"Lỗi thực thi Transaction Remediation (Đã tự động Rollback 100%): {err_msg}")


# Global singleton instance
remediation_service = RemediationService()
