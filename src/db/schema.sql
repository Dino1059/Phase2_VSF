-- DataTrust OS v4.0 Schema DDL

CREATE TABLE IF NOT EXISTS raw_snapshots (
    id VARCHAR PRIMARY KEY,
    source_name VARCHAR,
    file_path VARCHAR,
    sha256_hash VARCHAR,
    row_count INT,
    column_count INT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS xanhsm_feedback (
    id INTEGER PRIMARY KEY,
    review_text VARCHAR,
    normalized_text VARCHAR,
    rating FLOAT,
    location VARCHAR,
    timestamp TIMESTAMP,
    source VARCHAR,
    aspects JSON,
    snapshot_id VARCHAR
);

CREATE TABLE IF NOT EXISTS vgreen_telemetry (
    id INTEGER PRIMARY KEY,
    station_id VARCHAR,
    station_name VARCHAR,
    temperature_celsius FLOAT,
    voltage FLOAT,
    current_amps FLOAT,
    duty_cycle FLOAT,
    status VARCHAR,
    fault_code VARCHAR,
    timestamp TIMESTAMP,
    snapshot_id VARCHAR
);

CREATE TABLE IF NOT EXISTS vinfast_bms (
    id INTEGER PRIMARY KEY,
    vehicle_id VARCHAR,
    battery_soc FLOAT,
    battery_voltage FLOAT,
    cell_temp_max FLOAT,
    cell_temp_min FLOAT,
    bms_fault_code VARCHAR,
    charging_station_id VARCHAR,
    timestamp TIMESTAMP,
    snapshot_id VARCHAR
);

CREATE TABLE IF NOT EXISTS xanhsm_trips (
    id INTEGER PRIMARY KEY,
    trip_id VARCHAR,
    driver_id VARCHAR,
    pickup_location VARCHAR,
    dropoff_location VARCHAR,
    distance_km FLOAT,
    fare_vnd FLOAT,
    duration_minutes FLOAT,
    rating FLOAT,
    timestamp TIMESTAMP,
    snapshot_id VARCHAR
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
    rule_name VARCHAR,
    rule_type VARCHAR,
    rule_expression VARCHAR,
    confidence FLOAT,
    status VARCHAR DEFAULT 'proposed',
    proposed_by VARCHAR,
    approved_by VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quarantine (
    id VARCHAR PRIMARY KEY,
    source_table VARCHAR,
    source_row_id INT,
    rule_id VARCHAR,
    reason VARCHAR,
    original_data JSON,
    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lineage_hash VARCHAR
);

CREATE TABLE IF NOT EXISTS audit_log (
    id VARCHAR PRIMARY KEY,
    action VARCHAR,
    actor VARCHAR,
    target_table VARCHAR,
    target_id VARCHAR,
    details JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
