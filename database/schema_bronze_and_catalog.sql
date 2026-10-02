-- =============================================================================
-- DataTrust OS: Reset & Initialization of Bronze & Catalog Schemas
-- DDL for 8 Ingested Datasets (vingroup_pii_faulty_testset_3zone) + Data Catalog
-- =============================================================================

-- Step 1: Drop old custom schemas cleanly
DROP SCHEMA IF EXISTS bronze CASCADE;
DROP SCHEMA IF EXISTS silver CASCADE;
DROP SCHEMA IF EXISTS quarantine CASCADE;
DROP SCHEMA IF EXISTS catalog CASCADE;
DROP SCHEMA IF EXISTS policy CASCADE;
DROP SCHEMA IF EXISTS engine CASCADE;
DROP SCHEMA IF EXISTS orchestration CASCADE;
DROP SCHEMA IF EXISTS audit CASCADE;

-- Step 2: Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Step 3: Create schemas
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS catalog;

-- =============================================================================
-- SCHEMA: catalog (Data Catalog for Dataset & Column Metadata)
-- =============================================================================

CREATE TABLE catalog.datasets (
    dataset_id VARCHAR(100) PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL UNIQUE,
    source_file VARCHAR(100) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    row_count INT DEFAULT 0,
    column_count INT DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE catalog.columns (
    column_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(100) NOT NULL REFERENCES catalog.datasets(dataset_id) ON DELETE CASCADE,
    column_name VARCHAR(100) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    ordinal_position INT NOT NULL,
    is_primary_key BOOLEAN DEFAULT FALSE,
    is_nullable BOOLEAN DEFAULT TRUE,
    is_personal_data BOOLEAN DEFAULT FALSE,
    pii_role VARCHAR(50) NOT NULL DEFAULT 'NON_PERSONAL_REFERENCE',
    semantic_tag VARCHAR(100),
    data_category VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dataset_id, column_name)
);

CREATE INDEX idx_catalog_columns_dataset ON catalog.columns(dataset_id);
CREATE INDEX idx_catalog_columns_tag ON catalog.columns(semantic_tag);
CREATE INDEX idx_catalog_columns_pii ON catalog.columns(pii_role);

-- =============================================================================
-- SCHEMA: bronze (8 Raw Ingested Tables)
-- =============================================================================

-- 1. acn_charging_mapped
CREATE TABLE bronze.acn_charging_mapped (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    vehicle_vin VARCHAR(50),
    session_id VARCHAR(100),
    station_id VARCHAR(50),
    charger_id VARCHAR(50),
    start_time VARCHAR(50),
    duration_mins NUMERIC(10,2),
    kwh_consumed NUMERIC(10,2),
    power_kw NUMERIC(10,2),
    charging_pattern VARCHAR(50),
    assigned_day_index INT,
    station_temp_c NUMERIC(6,2),
    cost_vnd NUMERIC(14,2),
    status VARCHAR(50),
    soft_overlap_flag BOOLEAN,
    event_sequence_index INT,
    subject_zone VARCHAR(10)
);

-- 2. dim_customers
CREATE TABLE bronze.dim_customers (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    customer_id VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(150),
    phone_number VARCHAR(50),
    created_at VARCHAR(50),
    subject_zone VARCHAR(10)
);

-- 3. dim_drivers
CREATE TABLE bronze.dim_drivers (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    driver_id VARCHAR(50),
    vehicle_vin VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(150),
    phone_number VARCHAR(50),
    created_at VARCHAR(50),
    subject_zone VARCHAR(10)
);

-- 4. feedback_pii
CREATE TABLE bronze.feedback_pii (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    feedback_id VARCHAR(50),
    vehicle_vin VARCHAR(50),
    scenario_date VARCHAR(50),
    assigned_day_index INT,
    topic VARCHAR(50),
    sentiment INT,
    raw_comment_text TEXT,
    subject_zone VARCHAR(10),
    trip_id VARCHAR(50),
    customer_id VARCHAR(50)
);

-- 5. fleet_index
CREATE TABLE bronze.fleet_index (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    vehicle_vin VARCHAR(50),
    vehicle_type VARCHAR(50),
    telemetry_equipped BOOLEAN,
    subject_zone VARCHAR(10)
);

-- 6. ride_hailing_xanh_sm_trips
CREATE TABLE bronze.ride_hailing_xanh_sm_trips (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    trip_id VARCHAR(50),
    vehicle_vin VARCHAR(50),
    driver_id VARCHAR(50),
    pickup_datetime VARCHAR(50),
    dropoff_datetime VARCHAR(50),
    assigned_day_index INT,
    trip_distance_km NUMERIC(10,3),
    fare_amount NUMERIC(14,2),
    currency_unverified BOOLEAN,
    tip_amount NUMERIC(14,2),
    total_fare NUMERIC(14,2),
    pickup_latitude NUMERIC(10,6),
    pickup_longitude NUMERIC(10,6),
    vehicle_type VARCHAR(50),
    event_sequence_index INT,
    subject_zone VARCHAR(10),
    customer_id VARCHAR(50),
    customer_contact VARCHAR(100)
);

-- 7. synthetic_ev_telemetry_ved_ref
CREATE TABLE bronze.synthetic_ev_telemetry_ved_ref (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    record_id VARCHAR(50),
    vehicle_vin VARCHAR(50),
    day_idx INT,
    sample_idx INT,
    timestamp VARCHAR(50),
    speed_kmh NUMERIC(8,2),
    motor_rpm INT,
    battery_soc NUMERIC(6,2),
    battery_voltage NUMERIC(8,2),
    battery_current NUMERIC(8,2),
    battery_temp_c NUMERIC(6,2),
    state_at_sample VARCHAR(50),
    assigned_day_index INT,
    ved_reference_veh_id INT,
    synthetic_gap_indicator BOOLEAN,
    event_sequence_index INT,
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    accel_z NUMERIC(8,4),
    telemetry_coverage VARCHAR(50),
    subject_zone VARCHAR(10)
);

-- 8. synthetic_feedback_scenario_driven
CREATE TABLE bronze.synthetic_feedback_scenario_driven (
    _raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    _batch_id VARCHAR(100),
    _ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    feedback_id VARCHAR(50),
    vehicle_vin VARCHAR(50),
    scenario_date VARCHAR(50),
    assigned_day_index INT,
    topic VARCHAR(50),
    sentiment INT,
    raw_comment_text TEXT,
    subject_zone VARCHAR(10)
);
