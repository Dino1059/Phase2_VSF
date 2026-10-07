-- =============================================================================
-- DATATRUST OS: STEP 3 - STEP 5 HARDENING SCHEMA MIGRATION
-- Bổ sung schema lưu trữ Lifecycle, Step Stepper, Findings và bảo vệ Evidence
-- =============================================================================

-- 1. Mở rộng orchestration.pipeline_runs
ALTER TABLE orchestration.pipeline_runs 
    ADD COLUMN IF NOT EXISTS airflow_dag_run_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS not_evaluated_count INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS options_json JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS current_step VARCHAR(64) DEFAULT 'INGEST',
    ADD COLUMN IF NOT EXISTS current_step_progress INT DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_dag_run_id 
    ON orchestration.pipeline_runs(airflow_dag_run_id);

-- 2. Bảng theo dõi tiến độ chi tiết từng Task/Step cho Stepper
CREATE TABLE IF NOT EXISTS orchestration.pipeline_run_steps (
    step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id VARCHAR(64) NOT NULL REFERENCES orchestration.pipeline_runs(run_id) ON DELETE CASCADE,
    step_name VARCHAR(64) NOT NULL, -- 'INGEST', 'BRONZE', 'EVALUATION', 'SILVER'
    step_order INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'WAITING', -- 'WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    CONSTRAINT uq_run_step UNIQUE (run_id, step_name)
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run_id ON orchestration.pipeline_run_steps(run_id);

-- 3. Bảng sự kiện kiểm toán thời gian thực (Run Event Timeline)
CREATE TABLE IF NOT EXISTS orchestration.pipeline_run_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id VARCHAR(64) NOT NULL REFERENCES orchestration.pipeline_runs(run_id) ON DELETE CASCADE,
    step_name VARCHAR(64),
    event_type VARCHAR(32) NOT NULL, -- 'INFO', 'WARN', 'ERROR', 'TASK_STATE_CHANGE'
    message TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON orchestration.pipeline_run_events(run_id);

-- 4. Bảng tổng hợp Finding (Spec 08)
CREATE TABLE IF NOT EXISTS audit.findings (
    finding_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES orchestration.pipeline_runs(run_id) ON DELETE CASCADE,
    dataset_id VARCHAR(64) NOT NULL,
    rule_id VARCHAR(64) NOT NULL,
    policy_id VARCHAR(64),
    policy_name VARCHAR(255),
    law_ref VARCHAR(255),
    column_name VARCHAR(64),
    severity VARCHAR(20) NOT NULL DEFAULT 'HIGH', -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',   -- 'OPEN', 'IN_REVIEW', 'REMEDIATION_PENDING', 'RESOLVED'
    reason TEXT NOT NULL,
    impact TEXT,
    failed_record_count INT NOT NULL DEFAULT 1,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_findings_run_id ON audit.findings(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_rule_id ON audit.findings(rule_id);
CREATE INDEX IF NOT EXISTS idx_findings_dataset ON audit.findings(dataset_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON audit.findings(severity);

-- 5. Bảng liên kết Finding và Quarantine Records
CREATE TABLE IF NOT EXISTS audit.finding_quarantine_records (
    finding_id VARCHAR(64) NOT NULL REFERENCES audit.findings(finding_id) ON DELETE CASCADE,
    quarantine_id UUID NOT NULL REFERENCES quarantine.records(quarantine_id) ON DELETE CASCADE,
    PRIMARY KEY (finding_id, quarantine_id)
);

CREATE INDEX IF NOT EXISTS idx_fqr_finding_id ON audit.finding_quarantine_records(finding_id);
CREATE INDEX IF NOT EXISTS idx_fqr_quarantine_id ON audit.finding_quarantine_records(quarantine_id);

-- 6. Trigger bảo vệ bất biến cho audit.evidence (Immutable Ledger Policy)
CREATE OR REPLACE FUNCTION audit.prevent_evidence_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit evidence is immutable and append-only. UPDATE or DELETE operations are prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_evidence_mutation ON audit.evidence;
CREATE TRIGGER trg_prevent_evidence_mutation
    BEFORE UPDATE OR DELETE ON audit.evidence
    FOR EACH ROW
    EXECUTE FUNCTION audit.prevent_evidence_mutation();
