-- Migration 0003: destructive canonical data contract
-- Parquet landing files are the source of truth. Existing DB fact rows are disposable.

CREATE SCHEMA IF NOT EXISTS ref;

DROP VIEW IF EXISTS main.vinfast_bms;
DROP TABLE IF EXISTS main.vinfast_bms;
DROP VIEW IF EXISTS main.vgreen_telemetry;
DROP TABLE IF EXISTS main.vgreen_telemetry;
DROP VIEW IF EXISTS main.vgreen_charging_sessions;
DROP TABLE IF EXISTS main.vgreen_charging_sessions;
DROP VIEW IF EXISTS main.xanhsm_trips;
DROP TABLE IF EXISTS main.xanhsm_trips;
DROP VIEW IF EXISTS main.xanhsm_feedback;
DROP TABLE IF EXISTS main.xanhsm_feedback;

DROP TABLE IF EXISTS main.ev_telemetry;
CREATE TABLE main.ev_telemetry (
    record_id VARCHAR,
    vehicle_vin VARCHAR,
    day_idx BIGINT,
    sample_idx BIGINT,
    timestamp VARCHAR,
    speed_kmh DOUBLE,
    motor_rpm BIGINT,
    battery_soc DOUBLE,
    battery_voltage DOUBLE,
    battery_current DOUBLE,
    battery_temp_c DOUBLE,
    state_at_sample VARCHAR,
    assigned_day_index BIGINT,
    ved_reference_veh_id BIGINT,
    synthetic_gap_indicator BOOLEAN,
    event_sequence_index BIGINT,
    latitude DOUBLE,
    longitude DOUBLE,
    accel_z DOUBLE,
    telemetry_coverage VARCHAR,
    snapshot_id VARCHAR,
    source_ingestion_run_id VARCHAR
);

DROP TABLE IF EXISTS main.charging_sessions;
CREATE TABLE main.charging_sessions (
    vehicle_vin VARCHAR,
    session_id VARCHAR,
    station_id VARCHAR,
    charger_id VARCHAR,
    start_time VARCHAR,
    duration_mins DOUBLE,
    kwh_consumed DOUBLE,
    power_kw DOUBLE,
    charging_pattern VARCHAR,
    assigned_day_index BIGINT,
    station_temp_c DOUBLE,
    cost_vnd DOUBLE,
    status VARCHAR,
    soft_overlap_flag BOOLEAN,
    event_sequence_index BIGINT,
    snapshot_id VARCHAR,
    source_ingestion_run_id VARCHAR
);

DROP TABLE IF EXISTS main.trips;
CREATE TABLE main.trips (
    trip_id VARCHAR,
    vehicle_vin VARCHAR,
    driver_id VARCHAR,
    pickup_datetime VARCHAR,
    dropoff_datetime VARCHAR,
    assigned_day_index BIGINT,
    trip_distance_km DOUBLE,
    fare_amount DOUBLE,
    currency_unverified BOOLEAN,
    tip_amount DOUBLE,
    total_fare DOUBLE,
    pickup_latitude DOUBLE,
    pickup_longitude DOUBLE,
    vehicle_type VARCHAR,
    event_sequence_index BIGINT,
    snapshot_id VARCHAR,
    source_ingestion_run_id VARCHAR
);

DROP TABLE IF EXISTS main.nlp_feedback;
CREATE TABLE main.nlp_feedback (
    feedback_id VARCHAR,
    vehicle_vin VARCHAR,
    sentence VARCHAR,
    sentiment BIGINT,
    topic BIGINT,
    scenario_date VARCHAR,
    raw_comment_text VARCHAR,
    snapshot_id VARCHAR,
    source_ingestion_run_id VARCHAR
);

CREATE OR REPLACE TABLE ref.fleet_index_ref (
    vehicle_vin VARCHAR,
    vehicle_type VARCHAR,
    telemetry_equipped BOOLEAN,
    snapshot_id VARCHAR,
    source_ingestion_run_id VARCHAR
);

DROP SCHEMA IF EXISTS raw CASCADE;

UPDATE main.quality_rules
SET dataset_key = CASE
    WHEN lower(dataset_key) IN ('vinfast_bms', 'vinfast_ev_telemetry', 'vinfast_ev_telemetry_dirty', 'bms') THEN 'ev_telemetry'
    WHEN lower(dataset_key) IN ('vgreen_telemetry', 'vgreen_charging_sessions', 'vgreen_charging_stations', 'acn_charging') THEN 'charging_sessions'
    WHEN lower(dataset_key) IN ('xanhsm_trips', 'xanh_sm_trips', 'ride_trips') THEN 'trips'
    WHEN lower(dataset_key) IN ('xanhsm_feedback', 'xanh_sm_customer_feedback', 'customer_nlp', 'feedback') THEN 'nlp_feedback'
    ELSE dataset_key
END
WHERE dataset_key IS NOT NULL;

UPDATE main.quarantine
SET source_table = CASE
    WHEN lower(source_table) IN ('vinfast_bms', 'vinfast_ev_telemetry', 'vinfast_ev_telemetry_dirty', 'bms') THEN 'ev_telemetry'
    WHEN lower(source_table) IN ('vgreen_telemetry', 'vgreen_charging_sessions', 'vgreen_charging_stations', 'acn_charging') THEN 'charging_sessions'
    WHEN lower(source_table) IN ('xanhsm_trips', 'xanh_sm_trips', 'ride_trips') THEN 'trips'
    WHEN lower(source_table) IN ('xanhsm_feedback', 'xanh_sm_customer_feedback', 'customer_nlp', 'feedback') THEN 'nlp_feedback'
    ELSE source_table
END
WHERE source_table IS NOT NULL;

UPDATE main.audit_log
SET target_table = CASE
    WHEN lower(target_table) IN ('vinfast_bms', 'vinfast_ev_telemetry', 'vinfast_ev_telemetry_dirty', 'bms') THEN 'ev_telemetry'
    WHEN lower(target_table) IN ('vgreen_telemetry', 'vgreen_charging_sessions', 'vgreen_charging_stations', 'acn_charging') THEN 'charging_sessions'
    WHEN lower(target_table) IN ('xanhsm_trips', 'xanh_sm_trips', 'ride_trips') THEN 'trips'
    WHEN lower(target_table) IN ('xanhsm_feedback', 'xanh_sm_customer_feedback', 'customer_nlp', 'feedback') THEN 'nlp_feedback'
    ELSE target_table
END
WHERE target_table IS NOT NULL;

UPDATE main.job_runs
SET dataset_key = CASE
    WHEN lower(dataset_key) IN ('vinfast_bms', 'vinfast_ev_telemetry', 'vinfast_ev_telemetry_dirty', 'bms') THEN 'ev_telemetry'
    WHEN lower(dataset_key) IN ('vgreen_telemetry', 'vgreen_charging_sessions', 'vgreen_charging_stations', 'acn_charging') THEN 'charging_sessions'
    WHEN lower(dataset_key) IN ('xanhsm_trips', 'xanh_sm_trips', 'ride_trips') THEN 'trips'
    WHEN lower(dataset_key) IN ('xanhsm_feedback', 'xanh_sm_customer_feedback', 'customer_nlp', 'feedback') THEN 'nlp_feedback'
    ELSE dataset_key
END
WHERE dataset_key IS NOT NULL;

UPDATE main.pipeline_runs
SET dataset_key = CASE
    WHEN lower(dataset_key) IN ('vinfast_bms', 'vinfast_ev_telemetry', 'vinfast_ev_telemetry_dirty', 'bms') THEN 'ev_telemetry'
    WHEN lower(dataset_key) IN ('vgreen_telemetry', 'vgreen_charging_sessions', 'vgreen_charging_stations', 'acn_charging') THEN 'charging_sessions'
    WHEN lower(dataset_key) IN ('xanhsm_trips', 'xanh_sm_trips', 'ride_trips') THEN 'trips'
    WHEN lower(dataset_key) IN ('xanhsm_feedback', 'xanh_sm_customer_feedback', 'customer_nlp', 'feedback') THEN 'nlp_feedback'
    ELSE dataset_key
END
WHERE dataset_key IS NOT NULL;
