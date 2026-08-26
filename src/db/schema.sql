-- DataTrust OS v4.0 Schema DDL

CREATE TABLE IF NOT EXISTS raw_snapshots (
    id VARCHAR PRIMARY KEY,
    source_name VARCHAR,
    file_path VARCHAR,
    sha256_hash VARCHAR,
    row_count INT,
    column_count INT,
    provenance VARCHAR,
    tag VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ev_telemetry (
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

CREATE TABLE IF NOT EXISTS charging_sessions (
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

CREATE TABLE IF NOT EXISTS trips (
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

CREATE TABLE IF NOT EXISTS nlp_feedback (
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

CREATE TABLE IF NOT EXISTS profile_results (
    id VARCHAR PRIMARY KEY,
    snapshot_id VARCHAR,
    column_name VARCHAR,
    dtype VARCHAR,
    null_count INT,
    null_pct FLOAT,
    unique_count INT,
    min_val VARCHAR,
    max_val VARCHAR,
    mean_val FLOAT,
    std_val FLOAT,
    profiled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quality_rules (
    id VARCHAR PRIMARY KEY,
    snapshot_id VARCHAR,
    dataset_key VARCHAR,
    rule_name VARCHAR,
    rule_type VARCHAR,
    rule_expression VARCHAR,
    confidence FLOAT,
    status VARCHAR DEFAULT 'proposed',
    proposed_by VARCHAR,
    approved_by VARCHAR,
    reject_reason VARCHAR,
    feedback_by VARCHAR,
    feedback_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quarantine (
    id VARCHAR PRIMARY KEY,
    snapshot_id VARCHAR,
    source_table VARCHAR,
    source_row_id INT,
    rule_id VARCHAR,
    rule_version_id VARCHAR,
    reason VARCHAR,
    original_data JSON,
    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lineage_hash VARCHAR,
    status VARCHAR DEFAULT 'QUARANTINED',
    user_action VARCHAR DEFAULT 'NONE',
    action_at TIMESTAMP,
    action_by VARCHAR,
    UNIQUE (snapshot_id, rule_version_id, source_row_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_quarantine_idempotency ON quarantine (snapshot_id, rule_version_id, source_row_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id VARCHAR PRIMARY KEY,
    action VARCHAR,
    actor VARCHAR,
    target_table VARCHAR,
    target_id VARCHAR,
    details JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    previous_event_hash VARCHAR,
    event_hash VARCHAR
);

CREATE TABLE IF NOT EXISTS agent_traces (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR,
    agent_type VARCHAR,
    step_index INT,
    thought VARCHAR,
    action VARCHAR,
    tool_name VARCHAR,
    tool_input JSON,
    tool_output JSON,
    observation VARCHAR,
    tokens_used INT,
    cost_usd FLOAT,
    duration_ms INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR,
    tool_title VARCHAR,
    tool_about VARCHAR
);

CREATE TABLE IF NOT EXISTS schedules (
    id VARCHAR PRIMARY KEY,
    dataset_key VARCHAR,
    cron_expression VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    next_run_at TIMESTAMP,
    name VARCHAR,
    schedule_type VARCHAR,
    interval_seconds INT,
    action VARCHAR
);

CREATE TABLE IF NOT EXISTS job_runs (
    id VARCHAR PRIMARY KEY,
    schedule_id VARCHAR,
    dataset_key VARCHAR,
    status VARCHAR,
    result_summary JSON,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    agent_id VARCHAR,
    content VARCHAR NOT NULL,
    metadata_json VARCHAR,
    timestamp VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);

CREATE TABLE IF NOT EXISTS execution_authorizations (
    id VARCHAR PRIMARY KEY,
    dataset_key VARCHAR,
    rule_ids JSON,
    actor VARCHAR,
    payload_hash VARCHAR,
    authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datasets (
    dataset_key VARCHAR PRIMARY KEY,
    file_path VARCHAR,
    provenance VARCHAR,
    tag VARCHAR,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    entity_ids JSON,
    signal_ids JSON,
    admission_reason VARCHAR,
    supporting_layers JSON,
    severity VARCHAR,
    time_window JSON,
    confirmed_facts JSON,
    evidence_refs JSON,
    owner VARCHAR,
    feedback_type VARCHAR,
    feedback_reason VARCHAR,
    feedback_by VARCHAR,
    feedback_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id VARCHAR PRIMARY KEY,
    source_type VARCHAR,
    source_id VARCHAR,
    time_range JSON,
    entity_ids JSON,
    content_hash VARCHAR,
    summary VARCHAR,
    provenance VARCHAR
);

CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    claim VARCHAR NOT NULL,
    classification VARCHAR,
    supporting_evidence JSON,
    contradicting_evidence JSON,
    missing_evidence JSON,
    confidence DOUBLE,
    status VARCHAR
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    hypothesis_id VARCHAR,
    recommendation_id VARCHAR,
    action VARCHAR NOT NULL,
    actor VARCHAR,
    rationale VARCHAR,
    details JSON,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    cause_type VARCHAR,
    action_type VARCHAR,
    summary VARCHAR,
    details JSON,
    requires_hitl_approval BOOLEAN
);



