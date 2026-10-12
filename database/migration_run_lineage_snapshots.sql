-- Dynamic, run-scoped lineage snapshots. This migration is additive and re-runnable.
BEGIN;

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.run_lineage_snapshots (
    run_id VARCHAR(250) NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version > 0),
    lifecycle_status VARCHAR(16) NOT NULL DEFAULT 'BUILDING'
        CHECK (lifecycle_status IN ('BUILDING', 'FINALIZED')),
    dag_id VARCHAR(250) NOT NULL,
    dag_version VARCHAR(250) NOT NULL,
    dag_hash VARCHAR(128) NOT NULL,
    snapshot_json JSONB NOT NULL,
    repaired_from_revision INTEGER,
    repair_reason TEXT,
    repair_actor VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMPTZ,
    PRIMARY KEY (run_id, revision),
    CONSTRAINT run_lineage_repair_parent_fk
        FOREIGN KEY (run_id, repaired_from_revision)
        REFERENCES audit.run_lineage_snapshots (run_id, revision),
    CHECK (
        (repaired_from_revision IS NULL AND repair_reason IS NULL AND repair_actor IS NULL)
        OR
        (repaired_from_revision IS NOT NULL AND repair_reason IS NOT NULL AND repair_actor IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_run_lineage_snapshots_latest
    ON audit.run_lineage_snapshots (run_id, revision DESC);

CREATE TABLE IF NOT EXISTS audit.run_lineage_events (
    event_id VARCHAR(250) PRIMARY KEY,
    run_id VARCHAR(250) NOT NULL,
    revision INTEGER NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    source_sequence BIGINT NOT NULL DEFAULT 0,
    event_json JSONB NOT NULL,
    projection_applied BOOLEAN NOT NULL DEFAULT FALSE,
    ignored_reason TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id, revision)
        REFERENCES audit.run_lineage_snapshots (run_id, revision)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_run_lineage_events_order
    ON audit.run_lineage_events (run_id, revision, event_time, source_sequence);

CREATE TABLE IF NOT EXISTS audit.run_column_lineage (
    run_id VARCHAR(250) NOT NULL,
    dataset_id VARCHAR(250) NOT NULL,
    task_id VARCHAR(250) NOT NULL,
    map_index INTEGER NOT NULL DEFAULT -1,
    try_number INTEGER NOT NULL,
    transformations_json JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, dataset_id, task_id, map_index, try_number)
);

-- Upgrade the legacy runtime-created table in place. A unique index is enough
-- for the ON CONFLICT target even when the legacy SERIAL primary key remains.
ALTER TABLE audit.run_column_lineage
    ADD COLUMN IF NOT EXISTS task_id VARCHAR(250),
    ADD COLUMN IF NOT EXISTS map_index INTEGER,
    ADD COLUMN IF NOT EXISTS try_number INTEGER;
UPDATE audit.run_column_lineage SET
    task_id = COALESCE(task_id, 'LEGACY_UNATTRIBUTED'),
    map_index = COALESCE(map_index, -1),
    try_number = COALESCE(try_number, 0);
ALTER TABLE audit.run_column_lineage
    ALTER COLUMN task_id SET NOT NULL,
    ALTER COLUMN map_index SET DEFAULT -1,
    ALTER COLUMN map_index SET NOT NULL,
    ALTER COLUMN try_number SET NOT NULL;

-- Preserve every legacy duplicate (including old surrogate IDs/timestamps) before
-- compacting the live projection so the new execution key can be enforced.
CREATE TABLE IF NOT EXISTS audit.run_column_lineage_duplicate_archive (
    run_id VARCHAR(250) NOT NULL,
    dataset_id VARCHAR(250) NOT NULL,
    task_id VARCHAR(250) NOT NULL,
    map_index INTEGER NOT NULL,
    try_number INTEGER NOT NULL,
    duplicate_rows JSONB NOT NULL,
    duplicate_count INTEGER NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, dataset_id, task_id, map_index, try_number)
);
INSERT INTO audit.run_column_lineage_duplicate_archive (
    run_id, dataset_id, task_id, map_index, try_number,
    duplicate_rows, duplicate_count
)
SELECT
    run_id, dataset_id, task_id, map_index, try_number,
    jsonb_agg(to_jsonb(existing_row) ORDER BY existing_row.ctid::text),
    COUNT(*)::INTEGER
FROM audit.run_column_lineage existing_row
GROUP BY run_id, dataset_id, task_id, map_index, try_number
HAVING COUNT(*) > 1
ON CONFLICT (run_id, dataset_id, task_id, map_index, try_number)
DO UPDATE SET
    duplicate_rows = EXCLUDED.duplicate_rows,
    duplicate_count = EXCLUDED.duplicate_count,
    archived_at = CURRENT_TIMESTAMP;
DELETE FROM audit.run_column_lineage older
USING audit.run_column_lineage newer
WHERE older.ctid < newer.ctid
  AND older.run_id = newer.run_id
  AND older.dataset_id = newer.dataset_id
  AND older.task_id = newer.task_id
  AND older.map_index = newer.map_index
  AND older.try_number = newer.try_number;
CREATE UNIQUE INDEX IF NOT EXISTS uq_run_column_lineage_execution
    ON audit.run_column_lineage (run_id, dataset_id, task_id, map_index, try_number);

CREATE TABLE IF NOT EXISTS audit.run_lineage_repair_audit (
    run_id VARCHAR(250) NOT NULL,
    revision INTEGER NOT NULL,
    repaired_from_revision INTEGER NOT NULL,
    actor VARCHAR(250) NOT NULL,
    reason TEXT NOT NULL,
    diff_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, revision),
    FOREIGN KEY (run_id, revision)
        REFERENCES audit.run_lineage_snapshots (run_id, revision),
    FOREIGN KEY (run_id, repaired_from_revision)
        REFERENCES audit.run_lineage_snapshots (run_id, revision)
);

COMMIT;
