-- =============================================================================
-- DataTrust OS: IPO-Grade Data Governance & Adaptive Policy Architecture
-- PostgreSQL Schema Definition (7 Schemas)
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- SCHEMA 1: catalog (Data Catalog: Datasets, Columns, PII Roles)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS catalog;

-- 1.1 Enum for 6 PII Roles
DO $$ BEGIN
    CREATE TYPE catalog.pii_role_type AS ENUM (
        'DIRECT_IDENTIFIER',
        'LINKABLE_IDENTIFIER',
        'CONTEXTUAL_PERSONAL_DATA',
        'NON_PERSONAL_REFERENCE',
        'TECHNICAL_METADATA',
        'AMBIGUOUS_UNSTRUCTURED_DATA'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1.2 Enum for 5 Treatment Actions
DO $$ BEGIN
    CREATE TYPE catalog.treatment_action_type AS ENUM (
        'REMOVE',
        'PSEUDONYMIZE',
        'KEEP_RESTRICTED',
        'GENERALIZE',
        'KEEP'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1.3 Dataset Registry
CREATE TABLE IF NOT EXISTS catalog.datasets (
    dataset_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    domain VARCHAR(50) NOT NULL, -- e.g. 'trips', 'customers', 'charging', 'telemetry'
    owner_dept VARCHAR(100) NOT NULL,
    storage_table_bronze VARCHAR(100) NOT NULL,
    storage_table_silver VARCHAR(100) NOT NULL,
    description TEXT,
    retention_days INT DEFAULT 365,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 1.4 Column Catalog with PII Role & Sensitivity
CREATE TABLE IF NOT EXISTS catalog.columns (
    column_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(50) NOT NULL REFERENCES catalog.datasets(dataset_id) ON DELETE CASCADE,
    column_name VARCHAR(100) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    is_primary_key BOOLEAN DEFAULT FALSE,
    is_nullable BOOLEAN DEFAULT TRUE,
    is_personal_data BOOLEAN DEFAULT FALSE,
    pii_role catalog.pii_role_type NOT NULL DEFAULT 'NON_PERSONAL_REFERENCE',
    default_treatment catalog.treatment_action_type NOT NULL DEFAULT 'KEEP',
    semantic_tag VARCHAR(100), -- 'phone_number', 'email', 'gps_coordinate', 'financial', etc.
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dataset_id, column_name)
);

CREATE INDEX IF NOT EXISTS idx_catalog_columns_dataset ON catalog.columns(dataset_id);
CREATE INDEX IF NOT EXISTS idx_catalog_columns_pii_role ON catalog.columns(pii_role);

-- =============================================================================
-- SCHEMA 2: policy (Compliance Policies, Regulations & Clauses)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS policy;

CREATE TABLE IF NOT EXISTS policy.compliance_policies (
    policy_id VARCHAR(50) PRIMARY KEY, -- 'POL-VN-ND13', 'POL-EU-GDPR', 'POL-SOX-404'
    title VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(50) NOT NULL, -- 'VN', 'EU', 'US', 'GLOBAL'
    legal_framework VARCHAR(100) NOT NULL, -- 'Nghị định 13/2023/NĐ-CP', 'GDPR', 'SOX'
    version VARCHAR(20) DEFAULT '1.0',
    raw_policy_text TEXT NOT NULL,
    effective_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'draft', 'deprecated'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy.policy_clauses (
    clause_id VARCHAR(50) PRIMARY KEY,
    policy_id VARCHAR(50) NOT NULL REFERENCES policy.compliance_policies(policy_id) ON DELETE CASCADE,
    clause_number VARCHAR(50) NOT NULL,
    requirement_summary TEXT NOT NULL,
    target_pii_roles catalog.pii_role_type[],
    mandated_action catalog.treatment_action_type NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_policy_clauses_policy ON policy.policy_clauses(policy_id);

-- =============================================================================
-- SCHEMA 3: engine (Operation Registry & Parameterized Dynamic Rules)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS engine;

-- 3.1 Operation Registry (Implemented functions supported by the platform)
CREATE TABLE IF NOT EXISTS engine.operation_registry (
    operation_id VARCHAR(50) PRIMARY KEY,
    operation_name VARCHAR(100) NOT NULL,
    treatment_action catalog.treatment_action_type NOT NULL,
    python_handler VARCHAR(100) NOT NULL,
    parameter_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    description TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3.2 Fixed Compliance Checking Rules (Fixed/Immutable Gates, Managed at Backend Only, Read-Only on UI)
CREATE TABLE IF NOT EXISTS engine.compliance_check_rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    dataset_id VARCHAR(50) NOT NULL REFERENCES catalog.datasets(dataset_id),
    target_column VARCHAR(100) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    expression VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    policy_id VARCHAR(50) REFERENCES policy.compliance_policies(policy_id),
    policy_name VARCHAR(255),
    law_ref VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(50) NOT NULL DEFAULT 'UNSCOPED',
    country VARCHAR(50),
    severity VARCHAR(20) NOT NULL DEFAULT 'CRITICAL',
    on_fail_action VARCHAR(20) NOT NULL DEFAULT 'QUARANTINE',
    is_fixed BOOLEAN NOT NULL DEFAULT TRUE, -- Fixed, cannot be modified on UI, AI cannot propose
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engine_compliance_rules_dataset ON engine.compliance_check_rules(dataset_id);
COMMENT ON TABLE engine.compliance_check_rules IS
    'LEGACY compatibility table. New Lane A configuration belongs in engine.reliability_rules; legal controls belong in policy.compliance_rules.';

-- 3.2a Versioned Lane A detector configuration. Detector implementations remain
-- code-owned and allowlisted; this table contains parameters only (never code).
CREATE TABLE IF NOT EXISTS engine.reliability_rules (
    rule_id VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    dataset_id VARCHAR(100) NOT NULL,
    layer VARCHAR(2) NOT NULL CHECK (layer IN ('L1', 'L2', 'L3', 'L4')),
    detector_id VARCHAR(30) NOT NULL CHECK (detector_id IN
        ('REQUIRED', 'TYPE', 'RANGE', 'ARITHMETIC', 'CONDITION', 'ROBUST_Z', 'RELATION', 'CHANGEPOINT')),
    target_fields TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(params_json) = 'object'),
    severity VARCHAR(20) NOT NULL DEFAULT 'HIGH' CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    on_fail_action VARCHAR(30) NOT NULL DEFAULT 'WARNING'
        CHECK (on_fail_action IN ('BLOCK', 'QUARANTINE', 'QUARANTINE_HITL', 'WARNING', 'FINDING_ONLY')),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'RETIRED')),
    runtime_mode VARCHAR(20) NOT NULL DEFAULT 'SHADOW' CHECK (runtime_mode IN ('SHADOW', 'ENFORCED')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ,
    approved_by VARCHAR(200), approved_at TIMESTAMPTZ, approval_role VARCHAR(50),
    description TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_id, version),
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    CHECK (status <> 'ACTIVE' OR
           (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approval_role IN ('ADMIN', 'DATA_PLATFORM_OWNER')))
);
CREATE INDEX IF NOT EXISTS idx_reliability_rules_lookup
    ON engine.reliability_rules(dataset_id, status, runtime_mode, effective_from, effective_to);

-- 3.3 Data Treatment & Transformation Rules (Masking, Hashing, Rounding, Sanitization - UI Editable & AI Proposable)
CREATE TABLE IF NOT EXISTS engine.data_treatment_rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    dataset_id VARCHAR(50) NOT NULL REFERENCES catalog.datasets(dataset_id),
    column_name VARCHAR(100) NOT NULL,
    operation_id VARCHAR(50) NOT NULL REFERENCES engine.operation_registry(operation_id),
    treatment_name VARCHAR(100) NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression_display VARCHAR(255) NOT NULL,
    description TEXT,
    policy_id VARCHAR(50) REFERENCES policy.compliance_policies(policy_id),
    policy_name VARCHAR(255),
    law_ref VARCHAR(255),
    jurisdiction VARCHAR(50) NOT NULL DEFAULT 'UNSCOPED',
    country VARCHAR(50),
    is_ai_proposed BOOLEAN NOT NULL DEFAULT FALSE, -- Flagged separately if proposed by AI
    ai_rationale TEXT,                             -- AI Rationale note
    ai_confidence NUMERIC(4,3),                    -- Confidence score
    status VARCHAR(20) NOT NULL DEFAULT 'active',   -- 'active', 'pending', 'rejected', 'paused'
    enforced_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engine_treatment_rules_status ON engine.data_treatment_rules(dataset_id, status);

-- 3.4 Backward Compatibility Views / Tables
CREATE TABLE IF NOT EXISTS engine.field_process_configs (
    config_id VARCHAR(50) PRIMARY KEY,
    dataset_id VARCHAR(50) NOT NULL REFERENCES catalog.datasets(dataset_id),
    column_name VARCHAR(100) NOT NULL,
    pii_role catalog.pii_role_type NOT NULL,
    treatment_action catalog.treatment_action_type NOT NULL,
    operation_id VARCHAR(50) NOT NULL REFERENCES engine.operation_registry(operation_id),
    execution_phase VARCHAR(20) NOT NULL DEFAULT 'treatment',
    execution_order INT DEFAULT 1,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression_display VARCHAR(255),
    on_fail_action VARCHAR(20) DEFAULT 'QUARANTINE',
    severity VARCHAR(20) DEFAULT 'HIGH',
    policy_id VARCHAR(50) REFERENCES policy.compliance_policies(policy_id),
    law_ref VARCHAR(255),
    enforced_by VARCHAR(100) NOT NULL,
    enforced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_engine_field_configs_dataset ON engine.field_process_configs(dataset_id, is_active);

-- =============================================================================
-- SCHEMA 4: bronze (Raw Ingested Data)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.trips_raw (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100) NOT NULL,
    _run_id VARCHAR(100) NOT NULL,
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    trip_id VARCHAR(50),
    driver_id VARCHAR(50),
    customer_id VARCHAR(50),
    customer_phone VARCHAR(50),
    customer_name VARCHAR(100),
    fare_amount NUMERIC(12,2),
    trip_distance_km NUMERIC(8,2),
    pickup_latitude NUMERIC(9,6),
    pickup_longitude NUMERIC(9,6),
    trip_notes TEXT,
    raw_payload JSONB
);

CREATE TABLE IF NOT EXISTS bronze.customers_raw (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100) NOT NULL,
    _run_id VARCHAR(100) NOT NULL,
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    customer_id VARCHAR(50),
    customer_name VARCHAR(100),
    customer_phone VARCHAR(50),
    customer_email VARCHAR(100),
    national_id VARCHAR(50),
    raw_payload JSONB
);

-- =============================================================================
-- SCHEMA 5: silver (Cleaned, Standardized & Privacy-Treated Data)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.trips_clean (
    trip_id VARCHAR(50) PRIMARY KEY,
    _batch_id VARCHAR(100) NOT NULL,
    _processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    driver_id VARCHAR(50) NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    customer_phone VARCHAR(50) NOT NULL, -- Pseudonymized (masked)
    customer_name VARCHAR(100) NOT NULL,  -- Pseudonymized (masked)
    fare_amount NUMERIC(12,2) NOT NULL,  -- Kept validated (> 0)
    trip_distance_km NUMERIC(8,2) NOT NULL, -- Kept validated (> 0.1)
    pickup_latitude NUMERIC(5,2) NOT NULL, -- Generalized (rounded)
    pickup_longitude NUMERIC(5,2) NOT NULL, -- Generalized (rounded)
    trip_notes TEXT, -- Pseudonymized / NER redacted
    lineage_hash VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.customers_clean (
    customer_id VARCHAR(50) PRIMARY KEY,
    _batch_id VARCHAR(100) NOT NULL,
    _processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100) NOT NULL,
    customer_phone VARCHAR(50) NOT NULL,
    customer_email VARCHAR(100) NOT NULL,
    national_id VARCHAR(50), -- Removed (NULL) or Salted Hash
    lineage_hash VARCHAR(64) NOT NULL
);

-- =============================================================================
-- SCHEMA 6: quarantine (Violated Records & Audit Lineage)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS quarantine;

CREATE TABLE IF NOT EXISTS quarantine.records (
    quarantine_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(50) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_row_pk VARCHAR(100),
    failure_lane VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    violation_column VARCHAR(100),
    violation_rule_id VARCHAR(50),
    violation_reason TEXT NOT NULL,
    violation_severity VARCHAR(20) NOT NULL,
    raw_record_json JSONB NOT NULL,
    lineage_hash VARCHAR(64) NOT NULL, -- SHA-256 integrity hash
    subject_zone VARCHAR(50) NOT NULL DEFAULT 'GLOBAL',
    country VARCHAR(50),
    jurisdiction_chain TEXT[] NOT NULL DEFAULT ARRAY['GLOBAL']::TEXT[],
    matched_policy_id VARCHAR(100),
    matched_policy_name VARCHAR(255),
    matched_law_ref VARCHAR(255),
    policy_snapshot JSONB,
    applied_policy_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_violations JSONB NOT NULL DEFAULT '[]'::jsonb,
    quarantined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(30) DEFAULT 'QUARANTINED', -- 'QUARANTINED', 'IN_REVIEW', 'REMEDIATED', 'OVERRIDDEN', 'DISCARDED'
    resolution_note TEXT,
    resolved_by VARCHAR(100), -- Strictly Admin only
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_quarantine_records_run ON quarantine.records(run_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_records_status ON quarantine.records(status);

-- =============================================================================
-- SCHEMA 7: orchestration & audit (Pipeline Tracking & Immutable Audit Trail)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS orchestration;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS orchestration.pipeline_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    dag_id VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL, -- 'RUNNING', 'SUCCESS', 'FAILED'
    scanned_count INT DEFAULT 0,
    silver_count INT DEFAULT 0,
    quarantine_count INT DEFAULT 0,
    execution_duration_ms INT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS audit.system_audit_trail (
    audit_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    actor VARCHAR(100) NOT NULL,
    actor_role VARCHAR(50) NOT NULL, -- 'ADMIN', 'AUDITOR'
    action_type VARCHAR(50) NOT NULL, -- 'ADMIN_APPROVE_RULE', 'ADMIN_REJECT_RULE', 'ADMIN_REPROCESS_QUARANTINE', 'AUDITOR_INSPECT_EVIDENCE'
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    record_hash VARCHAR(64) NOT NULL,
    previous_hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_actor ON audit.system_audit_trail(actor, action_type);
