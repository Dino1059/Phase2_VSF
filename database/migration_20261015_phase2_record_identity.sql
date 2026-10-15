-- Phase 2: deterministic physical-row identity for all Bronze datasets.
-- This migration is intentionally separate from the immutable Phase 1 migration.
BEGIN;

ALTER TABLE bronze.acn_charging_mapped ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.dim_customers ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.dim_drivers ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.feedback_pii ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.fleet_index ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.ride_hailing_xanh_sm_trips ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.synthetic_ev_telemetry_ved_ref ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;
ALTER TABLE bronze.synthetic_feedback_scenario_driven ADD COLUMN IF NOT EXISTS _source_row_number BIGINT;

COMMIT;
