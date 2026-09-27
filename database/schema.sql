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

-- 3.2 Active Field Process Configurations (Live Rules enforced by Airflow Runner)
CREATE TABLE IF NOT EXISTS engine.field_process_configs (
    config_id VARCHAR(50) PRIMARY KEY,
    dataset_id VARCHAR(50) NOT NULL REFERENCES catalog.datasets(dataset_id),
    column_name VARCHAR(100) NOT NULL,
    pii_role catalog.pii_role_type NOT NULL,
    treatment_action catalog.treatment_action_type NOT NULL,
    operation_id VARCHAR(50) NOT NULL REFERENCES engine.operation_registry(operation_id),
    execution_phase VARCHAR(20) NOT NULL DEFAULT 'treatment', -- 'pre_check', 'treatment', 'post_check'
    execution_order INT DEFAULT 1,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression_display VARCHAR(255),
    on_fail_action VARCHAR(20) DEFAULT 'QUARANTINE', -- 'QUARANTINE', 'DROP_FIELD', 'REJECT_BATCH', 'WARN'
    severity VARCHAR(20) DEFAULT 'HIGH', -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    policy_id VARCHAR(50) REFERENCES policy.compliance_policies(policy_id),
    law_ref VARCHAR(255),
    enforced_by VARCHAR(100) NOT NULL, -- Admin approver name
    enforced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_engine_field_configs_dataset ON engine.field_process_configs(dataset_id, is_active);

-- 3.3 Proposed Rules (Generated by AI Agent, Awaiting Admin Approval - HITL)
CREATE TABLE IF NOT EXISTS engine.proposed_rules (
    proposal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(50) NOT NULL REFERENCES catalog.datasets(dataset_id),
    column_name VARCHAR(100) NOT NULL,
    pii_role catalog.pii_role_type NOT NULL,
    treatment_action catalog.treatment_action_type NOT NULL,
    operation_id VARCHAR(50) NOT NULL REFERENCES engine.operation_registry(operation_id),
    execution_phase VARCHAR(20) NOT NULL DEFAULT 'treatment',
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression_display VARCHAR(255) NOT NULL,
    rationale TEXT NOT NULL,
    domain VARCHAR(50) NOT NULL, -- 'Privacy & Data Protection', 'Data Quality', 'ITGC & Evidence'
    severity VARCHAR(20) NOT NULL,
    confidence NUMERIC(4,3) NOT NULL, -- e.g. 0.950
    law_ref VARCHAR(255) NOT NULL,
    policy_id VARCHAR(50) REFERENCES policy.compliance_policies(policy_id),
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    simulated_pass_rows INT DEFAULT 0,
    simulated_quarantine_rows INT DEFAULT 0,
    reviewed_by VARCHAR(100), -- Strictly Admin only
    reviewed_at TIMESTAMPTZ,
    review_comments TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engine_proposed_rules_status ON engine.proposed_rules(status);

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
    violation_column VARCHAR(100),
    violation_rule_id VARCHAR(50),
    violation_reason TEXT NOT NULL,
    violation_severity VARCHAR(20) NOT NULL,
    raw_record_json JSONB NOT NULL,
    lineage_hash VARCHAR(64) NOT NULL, -- SHA-256 integrity hash
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
