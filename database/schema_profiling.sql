-- =============================================================================
-- DataTrust OS: Task 2 Data Profiling Schema & View
-- Tables: catalog.table_profiles, catalog.column_profiles, catalog.v_column_profiles
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS catalog;

-- 1. Table Profiles: Snapshot metrics per dataset execution/batch
CREATE TABLE IF NOT EXISTS catalog.table_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(100) NOT NULL REFERENCES catalog.datasets(dataset_id) ON DELETE CASCADE,
    batch_id VARCHAR(100),
    total_rows INT NOT NULL DEFAULT 0,
    total_columns INT NOT NULL DEFAULT 0,
    health_score NUMERIC(5,2),
    signals_summary JSONB DEFAULT '{}'::jsonb,
    summary TEXT,
    profiled_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_table_profiles_dataset ON catalog.table_profiles(dataset_id);
CREATE INDEX IF NOT EXISTS idx_table_profiles_profiled_at ON catalog.table_profiles(profiled_at DESC);

-- 2. Column Profiles: Statistical metric snapshot per column (references catalog.columns)
-- Note: Does NOT duplicate static metadata (column_name, data_type, pii_role are in catalog.columns)
CREATE TABLE IF NOT EXISTS catalog.column_profiles (
    profile_id UUID NOT NULL REFERENCES catalog.table_profiles(profile_id) ON DELETE CASCADE,
    column_id UUID NOT NULL REFERENCES catalog.columns(column_id) ON DELETE CASCADE,
    null_count INT NOT NULL DEFAULT 0,
    null_pct NUMERIC(7,4) NOT NULL DEFAULT 0.0,
    unique_count INT NOT NULL DEFAULT 0,
    distinct_pct NUMERIC(7,4) NOT NULL DEFAULT 0.0,
    min_val TEXT,
    max_val TEXT,
    mean_val NUMERIC(18,4),
    std_val NUMERIC(18,4),
    zeros_count INT DEFAULT 0,
    negative_count INT DEFAULT 0,
    top_values JSONB DEFAULT '[]'::jsonb,
    signals JSONB DEFAULT '[]'::jsonb,
    PRIMARY KEY (profile_id, column_id)
);

CREATE INDEX IF NOT EXISTS idx_column_profiles_col ON catalog.column_profiles(column_id);

-- 3. Composite View: Combines catalog metadata with profile metrics for fast API/UI querying
CREATE OR REPLACE VIEW catalog.v_column_profiles AS
SELECT 
    cp.profile_id,
    tp.dataset_id,
    d.table_name,
    c.column_id,
    c.column_name,
    c.data_type,
    c.is_personal_data,
    c.pii_role,
    c.semantic_tag,
    c.data_category,
    cp.null_count,
    cp.null_pct,
    cp.unique_count,
    cp.distinct_pct,
    cp.min_val,
    cp.max_val,
    cp.mean_val,
    cp.std_val,
    cp.zeros_count,
    cp.negative_count,
    cp.top_values,
    cp.signals,
    tp.profiled_at
FROM catalog.column_profiles cp
JOIN catalog.columns c ON cp.column_id = c.column_id
JOIN catalog.table_profiles tp ON cp.profile_id = tp.profile_id
JOIN catalog.datasets d ON tp.dataset_id = d.dataset_id;
