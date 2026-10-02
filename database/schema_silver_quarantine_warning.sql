-- =============================================================================
-- DataTrust OS: Silver, Quarantine, Warning & Orchestration Schemas
-- Supporting 3-Lane Architecture (Lane A // Lane B -> Lane C 3-Way Router)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS quarantine;
CREATE SCHEMA IF NOT EXISTS warning;
CREATE SCHEMA IF NOT EXISTS orchestration;
CREATE SCHEMA IF NOT EXISTS policy;

-- =============================================================================
-- 1. SILVER SCHEMA: Clean, Standardized & Privacy-Treated Data
-- =============================================================================

CREATE TABLE IF NOT EXISTS silver.ride_hailing_xanh_sm_trips (
    trip_id VARCHAR(100) PRIMARY KEY,
    vehicle_vin VARCHAR(100),
    driver_id VARCHAR(100), -- Pseudonymized (SHA-256)
    customer_id VARCHAR(100),
    customer_contact VARCHAR(100), -- Masked (098*****21)
    pickup_datetime VARCHAR(50),
    dropoff_datetime VARCHAR(50),
    trip_distance_km NUMERIC(10,2),
    fare_amount NUMERIC(14,2),
    tip_amount NUMERIC(14,2),
    total_fare NUMERIC(14,2),
    pickup_latitude NUMERIC(8,2), -- Generalized (2 decimals)
    pickup_longitude NUMERIC(8,2), -- Generalized (2 decimals)
    vehicle_type VARCHAR(50),
    subject_zone VARCHAR(20),
    country VARCHAR(20),
    lineage_hash VARCHAR(64) NOT NULL,
    _run_id VARCHAR(100),
    _processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.synthetic_ev_telemetry_ved_ref (
    record_id VARCHAR(100) PRIMARY KEY,
    vehicle_vin VARCHAR(100),
    timestamp VARCHAR(50),
    speed_kmh NUMERIC(8,2),
    motor_rpm INT,
    battery_soc NUMERIC(8,2),
    battery_voltage NUMERIC(8,2),
    battery_current NUMERIC(8,2),
    battery_temp_c NUMERIC(8,2),
    latitude NUMERIC(8,2), -- Generalized (2 decimals)
    longitude NUMERIC(8,2), -- Generalized (2 decimals)
    subject_zone VARCHAR(20),
    country VARCHAR(20),
    lineage_hash VARCHAR(64) NOT NULL,
    _run_id VARCHAR(100),
    _processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.acn_charging_mapped (
    session_id VARCHAR(100) PRIMARY KEY,
    vehicle_vin VARCHAR(100),
    station_id VARCHAR(100),
    charger_id VARCHAR(100),
    start_time VARCHAR(50),
    duration_mins NUMERIC(10,2),
    kwh_consumed NUMERIC(10,2),
    power_kw NUMERIC(10,2),
    station_temp_c NUMERIC(8,2),
    cost_vnd NUMERIC(16,2),
    subject_zone VARCHAR(20),
    country VARCHAR(20),
    lineage_hash VARCHAR(64) NOT NULL,
    _run_id VARCHAR(100),
    _processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.generic_clean_records (
    record_pk VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(100) NOT NULL,
    treated_payload JSONB NOT NULL,
    subject_zone VARCHAR(20),
    country VARCHAR(20),
    lineage_hash VARCHAR(64) NOT NULL,
    _run_id VARCHAR(100),
    _processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (dataset_id, record_pk)
);

-- =============================================================================
-- 2. QUARANTINE SCHEMA: Isolated Critical Failures (Full Raw Records)
-- =============================================================================

CREATE TABLE IF NOT EXISTS quarantine.records (
    quarantine_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_row_pk VARCHAR(100),
    failure_lane VARCHAR(20) NOT NULL, -- 'LANE_A', 'LANE_B', 'BOTH'
    violation_column VARCHAR(100),
    violation_rule_id VARCHAR(100),
    violation_reason TEXT NOT NULL,
    violation_severity VARCHAR(20) NOT NULL DEFAULT 'CRITICAL',
    raw_record_json JSONB NOT NULL, -- Full 100% raw record for RCA & audit
    lineage_hash VARCHAR(64) NOT NULL,
    status VARCHAR(30) DEFAULT 'QUARANTINED', -- 'QUARANTINED', 'IN_REVIEW', 'REMEDIATED', 'OVERRIDDEN'
    quarantined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_quarantine_records_run ON quarantine.records(run_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_records_dataset ON quarantine.records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_records_lane ON quarantine.records(failure_lane);

-- =============================================================================
-- 3. WARNING SCHEMA: Statistical Anomalies & Advisory Warnings (Controlled PII)
-- =============================================================================

CREATE TABLE IF NOT EXISTS warning.records (
    warning_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(100) NOT NULL,
    source_row_pk VARCHAR(100),
    signal_lane VARCHAR(20) NOT NULL, -- 'LANE_A', 'LANE_B'
    signal_layer VARCHAR(20), -- 'L2', 'L3', 'L4', 'POLICY'
    warning_type VARCHAR(100) NOT NULL,
    warning_reason TEXT NOT NULL,
    score_or_zvalue NUMERIC(10,4),
    evidence_json JSONB DEFAULT '{}'::jsonb,
    redacted_record_json JSONB NOT NULL, -- PII redacted / controlled
    lineage_hash VARCHAR(64) NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_warning_records_run ON warning.records(run_id);
CREATE INDEX IF NOT EXISTS idx_warning_records_dataset ON warning.records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_warning_records_type ON warning.records(warning_type);

-- =============================================================================
-- 4. ORCHESTRATION SCHEMA: Pipeline Run Counters & Tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS orchestration.pipeline_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    dag_id VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL, -- 'RUNNING', 'SUCCESS', 'FAILED'
    scanned_count INT DEFAULT 0,
    silver_count INT DEFAULT 0,
    quarantine_count INT DEFAULT 0,
    warning_count INT DEFAULT 0,
    execution_duration_ms INT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_dag ON orchestration.pipeline_runs(dag_id, started_at);
