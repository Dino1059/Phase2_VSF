-- =============================================================================
-- Migration: Add New Columns for 3-Zone Injected Datasets & Policy LifeCycle
-- Date: 2026-10-14
-- Non-destructive, incremental migration for AWS RDS & existing environments.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS orchestration;

-- 1. Create migration history tracking table if not exists
CREATE TABLE IF NOT EXISTS orchestration.schema_migrations (
    migration_name VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);

-- 2. Bronze Schema Upgrades
-- Add fatigue_score to bronze telemetry (populated for EU vehicles, null for VN/US)
ALTER TABLE bronze.synthetic_ev_telemetry_ved_ref 
    ADD COLUMN IF NOT EXISTS fatigue_score NUMERIC(6,2);

-- Add consent lifecycle and opt-out to bronze customers
ALTER TABLE bronze.dim_customers 
    ADD COLUMN IF NOT EXISTS consent_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS consent_withdrawn_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS delete_requested_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS delete_completed_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS opt_out_sharing INT DEFAULT 0;

-- Add legal_basis to bronze drivers (GDPR Art. 6 / PDP compliance)
ALTER TABLE bronze.dim_drivers 
    ADD COLUMN IF NOT EXISTS legal_basis VARCHAR(100);

-- Make subject_zone nullable in bronze synthetic_feedback_scenario_driven
ALTER TABLE bronze.synthetic_feedback_scenario_driven 
    ALTER COLUMN subject_zone DROP NOT NULL;

-- 3. Silver Schema Upgrades (Excludes raw fatigue_score for medical privacy)
-- Add consent lifecycle and opt-out to silver customers
ALTER TABLE silver.dim_customers 
    ADD COLUMN IF NOT EXISTS consent_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS consent_withdrawn_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS delete_requested_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS delete_completed_at VARCHAR(50),
    ADD COLUMN IF NOT EXISTS opt_out_sharing INT DEFAULT 0;

-- Add legal_basis to silver drivers
ALTER TABLE silver.dim_drivers 
    ADD COLUMN IF NOT EXISTS legal_basis VARCHAR(100);

-- 4. Record migration history
INSERT INTO orchestration.schema_migrations (migration_name, applied_at)
VALUES ('migration_20261014_new_columns_and_injected_faults.sql', CURRENT_TIMESTAMP)
ON CONFLICT (migration_name) DO UPDATE SET applied_at = CURRENT_TIMESTAMP;

COMMIT;
