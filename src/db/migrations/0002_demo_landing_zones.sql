-- Migration 0002: Demo Landing Zones
-- Additive only: creates clean, quarantine, demo_ops schemas + tables
-- Safe for luồng cũ (ExecutiveDashboard, AgentChatWorkspace)

-- ============================================================
-- SCHEMA 1: clean.* (PASS zone)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS clean;

-- clean.ev_telemetry (mirror raw.ev_telemetry + rule tracking)
CREATE TABLE IF NOT EXISTS clean.ev_telemetry (
    record_id          VARCHAR,
    vehicle_vin        VARCHAR,
    day_idx            BIGINT,
    sample_idx         BIGINT,
    timestamp          VARCHAR,
    speed_kmh          DOUBLE,
    motor_rpm          BIGINT,
    battery_soc        DOUBLE,
    battery_voltage    DOUBLE,
    battery_current    DOUBLE,
    battery_temp_c     DOUBLE,
    state_at_sample    VARCHAR,
    assigned_day_index BIGINT,
    ved_reference_veh_id    BIGINT,
    synthetic_gap_indicator BOOLEAN,
    event_sequence_index    BIGINT,
    latitude           DOUBLE,
    longitude          DOUBLE,
    accel_z            DOUBLE,
    telemetry_coverage VARCHAR,
    snapshot_id        VARCHAR,
    passed_by_rule_id  VARCHAR,
    source_ingestion_run_id VARCHAR,
    detected_snapshot_id VARCHAR,
    passed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- clean.charging_sessions (mirror raw.charging_sessions)
CREATE TABLE IF NOT EXISTS clean.charging_sessions (
    vehicle_vin        VARCHAR,
    session_id         VARCHAR,
    station_id         VARCHAR,
    charger_id         VARCHAR,
    start_time         VARCHAR,
    duration_mins      DOUBLE,
    kwh_consumed       DOUBLE,
    power_kw           DOUBLE,
    charging_pattern   VARCHAR,
    assigned_day_index BIGINT,
    station_temp_c     DOUBLE,
    cost_vnd           DOUBLE,
    status             VARCHAR,
    soft_overlap_flag  BOOLEAN,
    event_sequence_index BIGINT,
    snapshot_id        VARCHAR,
    passed_by_rule_id  VARCHAR,
    source_ingestion_run_id VARCHAR,
    detected_snapshot_id VARCHAR,
    passed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- clean.trips (mirror raw.trips)
CREATE TABLE IF NOT EXISTS clean.trips (
    trip_id            VARCHAR,
    vehicle_vin        VARCHAR,
    driver_id          VARCHAR,
    pickup_datetime    VARCHAR,
    dropoff_datetime  VARCHAR,
    assigned_day_index BIGINT,
    trip_distance_km   DOUBLE,
    fare_amount        DOUBLE,
    currency_unverified BOOLEAN,
    tip_amount         DOUBLE,
    total_fare         DOUBLE,
    pickup_latitude    DOUBLE,
    pickup_longitude   DOUBLE,
    vehicle_type       VARCHAR,
    event_sequence_index BIGINT,
    snapshot_id        VARCHAR,
    passed_by_rule_id  VARCHAR,
    source_ingestion_run_id VARCHAR,
    detected_snapshot_id VARCHAR,
    passed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- clean.nlp_feedback (mirror raw.nlp_feedback)
CREATE TABLE IF NOT EXISTS clean.nlp_feedback (
    sentence           VARCHAR,
    sentiment          BIGINT,
    topic              BIGINT,
    snapshot_id        VARCHAR,
    passed_by_rule_id  VARCHAR,
    source_ingestion_run_id VARCHAR,
    detected_snapshot_id VARCHAR,
    passed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- SCHEMA 2: quarantine.* (FAIL zone - separate from main.quarantine)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS quarantine;

-- quarantine.ev_telemetry
CREATE TABLE IF NOT EXISTS quarantine.ev_telemetry (
    quarantine_id          VARCHAR PRIMARY KEY,
    source_ingestion_run_id VARCHAR NOT NULL,
    day_idx                BIGINT NOT NULL,
    vehicle_vin            VARCHAR,
    rule_id                VARCHAR NOT NULL,
    rule_layer             VARCHAR NOT NULL,
    rule_name              VARCHAR,
    reason                 VARCHAR,
    raw_row                JSON,
    detected_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_via           VARCHAR,
    status                 VARCHAR DEFAULT 'OPEN',
    resolved_at            TIMESTAMP,
    resolved_by            VARCHAR,
    resolution_action      VARCHAR
);

-- quarantine.charging_sessions
CREATE TABLE IF NOT EXISTS quarantine.charging_sessions (
    quarantine_id          VARCHAR PRIMARY KEY,
    source_ingestion_run_id VARCHAR NOT NULL,
    day_idx                BIGINT NOT NULL,
    vehicle_vin            VARCHAR,
    session_id            VARCHAR,
    rule_id                VARCHAR NOT NULL,
    rule_layer             VARCHAR NOT NULL,
    rule_name              VARCHAR,
    reason                 VARCHAR,
    raw_row                JSON,
    detected_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_via           VARCHAR,
    status                 VARCHAR DEFAULT 'OPEN',
    resolved_at            TIMESTAMP,
    resolved_by            VARCHAR,
    resolution_action      VARCHAR
);

-- quarantine.trips
CREATE TABLE IF NOT EXISTS quarantine.trips (
    quarantine_id          VARCHAR PRIMARY KEY,
    source_ingestion_run_id VARCHAR NOT NULL,
    day_idx                BIGINT NOT NULL,
    vehicle_vin            VARCHAR,
    trip_id               VARCHAR,
    rule_id                VARCHAR NOT NULL,
    rule_layer             VARCHAR NOT NULL,
    rule_name              VARCHAR,
    reason                 VARCHAR,
    raw_row                JSON,
    detected_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_via           VARCHAR,
    status                 VARCHAR DEFAULT 'OPEN',
    resolved_at            TIMESTAMP,
    resolved_by            VARCHAR,
    resolution_action      VARCHAR
);

-- quarantine.nlp_feedback
CREATE TABLE IF NOT EXISTS quarantine.nlp_feedback (
    quarantine_id          VARCHAR PRIMARY KEY,
    source_ingestion_run_id VARCHAR NOT NULL,
    day_idx                BIGINT NOT NULL,
    sentence               VARCHAR,
    rule_id                VARCHAR NOT NULL,
    rule_layer             VARCHAR NOT NULL,
    rule_name              VARCHAR,
    reason                 VARCHAR,
    raw_row                JSON,
    detected_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_via           VARCHAR,
    status                 VARCHAR DEFAULT 'OPEN',
    resolved_at            TIMESTAMP,
    resolved_by            VARCHAR,
    resolution_action      VARCHAR
);

-- Views: summary by rule for each table
CREATE OR REPLACE VIEW quarantine.v_summary_ev_telemetry AS
SELECT
    rule_id, rule_layer, rule_name, status, detected_via,
    COUNT(*)                    AS total_records,
    COUNT(DISTINCT day_idx)     AS affected_days,
    COUNT(DISTINCT vehicle_vin) AS affected_entities,
    MIN(detected_at)            AS first_seen,
    MAX(detected_at)            AS last_seen,
    MIN(reason)                 AS sample_reason
FROM quarantine.ev_telemetry
GROUP BY rule_id, rule_layer, rule_name, status, detected_via
ORDER BY total_records DESC;

CREATE OR REPLACE VIEW quarantine.v_summary_charging_sessions AS
SELECT
    rule_id, rule_layer, rule_name, status, detected_via,
    COUNT(*)                    AS total_records,
    COUNT(DISTINCT day_idx)     AS affected_days,
    COUNT(DISTINCT vehicle_vin) AS affected_entities,
    MIN(detected_at)            AS first_seen,
    MAX(detected_at)            AS last_seen,
    MIN(reason)                 AS sample_reason
FROM quarantine.charging_sessions
GROUP BY rule_id, rule_layer, rule_name, status, detected_via
ORDER BY total_records DESC;

CREATE OR REPLACE VIEW quarantine.v_summary_trips AS
SELECT
    rule_id, rule_layer, rule_name, status, detected_via,
    COUNT(*)                    AS total_records,
    COUNT(DISTINCT day_idx)     AS affected_days,
    COUNT(DISTINCT vehicle_vin) AS affected_entities,
    MIN(detected_at)            AS first_seen,
    MAX(detected_at)            AS last_seen,
    MIN(reason)                 AS sample_reason
FROM quarantine.trips
GROUP BY rule_id, rule_layer, rule_name, status, detected_via
ORDER BY total_records DESC;

CREATE OR REPLACE VIEW quarantine.v_summary_nlp_feedback AS
SELECT
    rule_id, rule_layer, rule_name, status, detected_via,
    COUNT(*)                    AS total_records,
    COUNT(DISTINCT day_idx)     AS affected_days,
    MIN(detected_at)            AS first_seen,
    MAX(detected_at)            AS last_seen,
    MIN(reason)                 AS sample_reason
FROM quarantine.nlp_feedback
GROUP BY rule_id, rule_layer, rule_name, status, detected_via
ORDER BY total_records DESC;


-- ============================================================
-- SCHEMA 3: demo_ops.* (Tracking & State Machine)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS demo_ops;

-- landing_day_snapshots: maps CSV/Parquet source files to day_idx
CREATE TABLE IF NOT EXISTS demo_ops.landing_day_snapshots (
    snapshot_id             VARCHAR PRIMARY KEY,
    source_file             VARCHAR NOT NULL,
    day_idx                 BIGINT NOT NULL,
    file_sha256             VARCHAR,
    row_count               BIGINT,
    fault_injected          BOOLEAN DEFAULT FALSE,
    is_activated            BOOLEAN DEFAULT FALSE,
    activated_at            TIMESTAMP,
    source_ingestion_run_id VARCHAR,
    UNIQUE(source_file, day_idx)
);

-- ingestion_runs: tracking each data ingestion event
CREATE TABLE IF NOT EXISTS demo_ops.ingestion_runs (
    ingestion_run_id    VARCHAR PRIMARY KEY,
    snapshot_id         VARCHAR,
    day_idx             BIGINT,
    run_kind            VARCHAR NOT NULL,
    started_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at         TIMESTAMP,
    status              VARCHAR DEFAULT 'RUNNING',
    pipeline_run_id     VARCHAR,
    rows_copied_to_raw  BIGINT,
    rows_passed_clean   BIGINT,
    rows_quarantined    BIGINT,
    error_message       VARCHAR,
    window_start_day    BIGINT,
    window_end_day      BIGINT
);

-- demo_state: singleton state machine
CREATE TABLE IF NOT EXISTS demo_ops.demo_state (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    current_day_idx       BIGINT NOT NULL DEFAULT -1,
    warmup_completed      BOOLEAN DEFAULT FALSE,
    realtime_active_day   BIGINT,
    realtime_running      BOOLEAN DEFAULT FALSE,
    last_reset_at         TIMESTAMP,
    total_ingestion_runs  BIGINT DEFAULT 0
);

-- Initialize singleton
INSERT INTO demo_ops.demo_state(id) VALUES (1) ON CONFLICT(id) DO NOTHING;

-- View: realtime rule set (L1 only, approved)
CREATE OR REPLACE VIEW demo_ops.realtime_rule_set AS
SELECT
    q.id              AS rule_id,
    q.layer,
    q.rule_name,
    q.rule_expression,
    q.dataset_key      AS target_table,
    'medium'          AS severity_default,
    q.confidence
FROM main.quality_rules q
WHERE q.status = 'approved'
  AND q.layer = 'L1'
  AND (q.dataset_key IS NOT NULL AND q.dataset_key != '');


-- ============================================================
-- SCHEMA 4: Additive columns on existing tables
-- ============================================================

-- pipeline_runs: source_ingestion_run_id
ALTER TABLE main.pipeline_runs ADD COLUMN IF NOT EXISTS source_ingestion_run_id VARCHAR;

-- incidents: source_ingestion_run_id
ALTER TABLE main.incidents ADD COLUMN IF NOT EXISTS source_ingestion_run_id VARCHAR;

-- profile_results: source_ingestion_run_id
ALTER TABLE main.profile_results ADD COLUMN IF NOT EXISTS source_ingestion_run_id VARCHAR;

-- agent_traces: source_ingestion_run_id
ALTER TABLE main.agent_traces ADD COLUMN IF NOT EXISTS source_ingestion_run_id VARCHAR;

-- quality_rules: layer column (ensure it exists)
-- Already exists in current DB per inspect_schema output, but add for safety
ALTER TABLE main.quality_rules ADD COLUMN IF NOT EXISTS layer VARCHAR;
