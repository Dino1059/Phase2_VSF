-- =============================================================================
-- DataTrust OS x SoD Flow: Migration Phase 3 (Cross-System Integration)
-- Enforces Fail-Closed HITL Governance, Persistent Proposals, Two-Stage Audit Ledger,
-- Version Binding, and Immutable Audit Trails.
-- =============================================================================

-- 1. TẠO SCHEMA QUẢN TRỊ REMEDIATION
CREATE SCHEMA IF NOT EXISTS remediation;

-- 2. TẠO ENUM TRẠNG THÁI PROPOSAL
DO $$ BEGIN
    CREATE TYPE remediation.proposal_status AS ENUM (
        'DRAFT', 
        'DRY_RUN_PASSED', 
        'DRY_RUN_FAILED', 
        'PENDING_SOD_APPROVAL', 
        'APPROVED', 
        'REJECTED', 
        'EXECUTING', 
        'REMEDIATED', 
        'STALE'
    );
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- 3. MỞ RỘNG ENUM TICKET KIND TRONG SCHEMA SOD
DO $$ BEGIN
    ALTER TYPE sod.ticket_kind ADD VALUE IF NOT EXISTS 'remediation';
    ALTER TYPE sod.ticket_kind ADD VALUE IF NOT EXISTS 'rule_change';
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- 4. SEQUENCE VÀ CỘT KIỂM TOÁN TRONG AUDIT.EVIDENCE (CONCURRENCY-SAFE LEDGER)
CREATE SEQUENCE IF NOT EXISTS audit.evidence_seq START WITH 1 INCREMENT BY 1;

ALTER TABLE audit.evidence 
    ADD COLUMN IF NOT EXISTS sequence_no BIGINT,
    ADD COLUMN IF NOT EXISTS event_type VARCHAR(64) NOT NULL DEFAULT 'PIPELINE_RUN_COMPLETED',
    ADD COLUMN IF NOT EXISTS signature_algorithm VARCHAR(32) DEFAULT 'HMAC-SHA256',
    ADD COLUMN IF NOT EXISTS key_id VARCHAR(64) DEFAULT 'datatrust_audit_key_v1',
    ADD COLUMN IF NOT EXISTS canonicalization VARCHAR(32) DEFAULT 'RFC8785';

-- Tạm thời disable trigger bất biến để backfill sequence_no cho các bản ghi cũ
DO $$ BEGIN
    ALTER TABLE audit.evidence DISABLE TRIGGER trg_prevent_evidence_mutation;
EXCEPTION WHEN OTHERS THEN null; END $$;

-- Đồng bộ sequence_no cho các bản ghi cũ nếu chưa có
UPDATE audit.evidence 
SET sequence_no = nextval('audit.evidence_seq') 
WHERE sequence_no IS NULL;

DO $$ BEGIN
    ALTER TABLE audit.evidence ENABLE TRIGGER trg_prevent_evidence_mutation;
EXCEPTION WHEN OTHERS THEN null; END $$;

-- Ràng buộc UNIQUE bảo đảm không bao giờ có 2 khối trùng sequence_no hoặc trùng hash
DO $$ BEGIN
    ALTER TABLE audit.evidence ADD CONSTRAINT uq_audit_evidence_sequence UNIQUE (sequence_no);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN null; END $$;

DO $$ BEGIN
    ALTER TABLE audit.evidence ADD CONSTRAINT uq_audit_evidence_hash UNIQUE (evidence_hash);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN null; END $$;

CREATE INDEX IF NOT EXISTS idx_audit_evidence_seq_desc ON audit.evidence(sequence_no DESC);

-- 5. BẢNG PROPOSAL CHÍNH (BỀN VỮNG TRONG CSDL, THAY THẾ RAM SINGLETON)
CREATE TABLE IF NOT EXISTS remediation.proposals (
    proposal_id VARCHAR(64) PRIMARY KEY,
    finding_id VARCHAR(64) NOT NULL REFERENCES audit.findings(finding_id) ON DELETE RESTRICT,
    version INT NOT NULL DEFAULT 1,
    status remediation.proposal_status NOT NULL DEFAULT 'DRAFT',
    
    -- Mục tiêu & Cấu hình xử lý
    dataset_id VARCHAR(64) NOT NULL,
    target_column VARCHAR(64) NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    operation_id VARCHAR(64) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    target_quarantine_ids UUID[] NOT NULL,
    expected_rows INT NOT NULL DEFAULT 0,
    risk_level VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    reason TEXT NOT NULL,

    -- Hashes tính toàn vẹn (Version Binding & Anti-Drift)
    source_snapshot_hash VARCHAR(64) NOT NULL,
    proposal_hash VARCHAR(64) NOT NULL,
    latest_dry_run JSONB,
    dry_run_hash VARCHAR(64),

    -- Metadata phê duyệt & kiểm toán
    approval_evidence_id UUID REFERENCES audit.evidence(evidence_id) ON DELETE RESTRICT,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_remediation_proposals_finding ON remediation.proposals(finding_id);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_status ON remediation.proposals(status);

-- 6. BẢNG SNAPSHOT HOÀN CHỈNH TỪNG PHIÊN BẢN (IMMUTABLE APPEND-ONLY)
CREATE TABLE IF NOT EXISTS remediation.proposal_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id VARCHAR(64) NOT NULL REFERENCES remediation.proposals(proposal_id) ON DELETE RESTRICT,
    version INT NOT NULL,
    finding_id VARCHAR(64) NOT NULL REFERENCES audit.findings(finding_id) ON DELETE RESTRICT,
    dataset_id VARCHAR(64) NOT NULL,
    target_column VARCHAR(64) NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    operation_id VARCHAR(64) NOT NULL,
    params JSONB NOT NULL,
    target_quarantine_ids UUID[] NOT NULL,
    expected_rows INT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL,
    dry_run_hash VARCHAR(64),
    latest_dry_run JSONB,
    source_snapshot_hash VARCHAR(64) NOT NULL,
    proposal_hash VARCHAR(64) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(proposal_id, version)
);

-- Trigger ngăn chặn chỉnh sửa / xóa snapshot phiên bản proposal
CREATE OR REPLACE FUNCTION remediation.prevent_proposal_version_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'remediation.proposal_versions is strictly append-only. UPDATE and DELETE operations are prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_proposal_version_mutation ON remediation.proposal_versions;
CREATE TRIGGER trg_prevent_proposal_version_mutation
    BEFORE UPDATE OR DELETE ON remediation.proposal_versions
    FOR EACH ROW
    EXECUTE FUNCTION remediation.prevent_proposal_version_mutation();

-- 7. BẢNG LIÊN KẾT ĐỐI TƯỢNG SOD (ASSOCIATION TABLE)
CREATE TABLE IF NOT EXISTS sod.ticket_subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES sod.tickets(id) ON DELETE RESTRICT,
    subject_type VARCHAR(32) NOT NULL, -- 'REMEDIATION_PROPOSAL', 'FINDING', 'QUALITY_RULE'
    subject_id VARCHAR(64) NOT NULL,   -- proposal_id, finding_id, rule_id
    subject_version INT NOT NULL DEFAULT 1,
    subject_hash VARCHAR(64) NOT NULL, -- proposal_hash
    source_snapshot_hash VARCHAR(64) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticket_id, subject_type, subject_id)
);

CREATE INDEX IF NOT EXISTS idx_ticket_subjects_lookup 
    ON sod.ticket_subjects(subject_type, subject_id, subject_version, subject_hash);

-- Quy định: Mỗi (proposal_id, version) chỉ được submit TỐI ĐA 1 ticket SoD
CREATE UNIQUE INDEX IF NOT EXISTS uq_one_ticket_per_proposal_version 
    ON sod.ticket_subjects(subject_id, subject_version) 
    WHERE subject_type = 'REMEDIATION_PROPOSAL';

-- 8. BẢNG LỊCH SỬ THỰC THI GIAO DỊCH (EXECUTION ATTEMPTS)
CREATE TABLE IF NOT EXISTS remediation.execution_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id VARCHAR(64) NOT NULL REFERENCES remediation.proposals(proposal_id) ON DELETE RESTRICT,
    proposal_version INT NOT NULL,
    proposal_hash VARCHAR(64) NOT NULL,
    ticket_id UUID NOT NULL REFERENCES sod.tickets(id) ON DELETE RESTRICT,
    actor_id VARCHAR(64) NOT NULL,
    actor_role VARCHAR(20) NOT NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('SUCCEEDED', 'FAILED')),
    affected_rows INT NOT NULL DEFAULT 0,
    source_snapshot_hash VARCHAR(64) NOT NULL,
    target_snapshot_hash VARCHAR(64),
    execution_duration_ms DOUBLE PRECISION,
    error_message TEXT,
    approval_evidence_id UUID REFERENCES audit.evidence(evidence_id) ON DELETE RESTRICT,
    execution_evidence_id UUID REFERENCES audit.evidence(evidence_id) ON DELETE RESTRICT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_execution_attempts_proposal 
    ON remediation.execution_attempts(proposal_id, proposal_version);

-- 9. TRIGGER KIỂM SOÁT TRẠNG THÁI APPROVED TẠI TẦNG CSDL (STATE MACHINE GUARD)
CREATE OR REPLACE FUNCTION remediation.check_proposal_approval_guard()
RETURNS TRIGGER AS $$
DECLARE
    v_ticket_status sod.ticket_status;
BEGIN
    -- Chỉ kiểm tra khi có sự kiện chuyển status sang 'APPROVED'
    IF NEW.status = 'APPROVED' AND (OLD.status IS DISTINCT FROM 'APPROVED') THEN
        -- Tìm kiếm ticket tương ứng khớp chính xác (proposal_id, version, proposal_hash)
        SELECT t.status INTO v_ticket_status
        FROM sod.ticket_subjects ts
        JOIN sod.tickets t ON ts.ticket_id = t.id
        WHERE ts.subject_type = 'REMEDIATION_PROPOSAL'
          AND ts.subject_id = NEW.proposal_id
          AND ts.subject_version = NEW.version
          AND ts.subject_hash = NEW.proposal_hash;

        IF v_ticket_status IS NULL THEN
            RAISE EXCEPTION 'DB State Machine Violation: Cannot mark proposal % as APPROVED without a linked SoD ticket matching version % and hash %.', 
                NEW.proposal_id, NEW.version, NEW.proposal_hash;
        END IF;

        IF v_ticket_status != 'DONE' THEN
            RAISE EXCEPTION 'DB State Machine Violation: Linked SoD ticket is not DONE (Current status: %).', v_ticket_status;
        END IF;
    END IF;

    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_remediation_proposal_status_guard ON remediation.proposals;
CREATE TRIGGER trg_remediation_proposal_status_guard
    BEFORE UPDATE ON remediation.proposals
    FOR EACH ROW
    EXECUTE FUNCTION remediation.check_proposal_approval_guard();

-- 10. BỔ SUNG CỘT SOD TRONG BẢNG AUDIT.FINDINGS
ALTER TABLE audit.findings
    ADD COLUMN IF NOT EXISTS sod_ticket_id UUID REFERENCES sod.tickets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS sod_ticket_code VARCHAR(30),
    ADD COLUMN IF NOT EXISTS sod_approval_status VARCHAR(30) NOT NULL DEFAULT 'NONE';

CREATE INDEX IF NOT EXISTS idx_findings_sod_ticket ON audit.findings(sod_ticket_id);
CREATE INDEX IF NOT EXISTS idx_findings_sod_status ON audit.findings(sod_approval_status);

-- 11. PHÂN QUYỀN TRUY CẬP CHO SOD_APP
-- Objects are owned by the managed DATABASE_URL identity. Do not grant to a
-- separately provisioned login role or embed another database credential.
