-- Data-driven Lane A configuration and explicit Lane B ownership.
-- Idempotent and non-destructive: engine.compliance_check_rules remains available
-- for legacy readers, but must not receive new rules.
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE SCHEMA IF NOT EXISTS engine;

DO $$ BEGIN
    IF to_regclass('engine.compliance_check_rules') IS NOT NULL THEN
        COMMENT ON TABLE engine.compliance_check_rules IS
            'LEGACY compatibility table. New Lane A configuration belongs in engine.reliability_rules; legal controls belong in policy.compliance_rules.';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS engine.reliability_rules (
    rule_id VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    dataset_id VARCHAR(100) NOT NULL,
    layer VARCHAR(2) NOT NULL CHECK (layer IN ('L1', 'L2', 'L3', 'L4')),
    detector_id VARCHAR(30) NOT NULL CHECK (detector_id IN
        ('REQUIRED', 'TYPE', 'RANGE', 'ARITHMETIC', 'CONDITION', 'ROBUST_Z', 'RELATION', 'CHANGEPOINT')),
    target_fields TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(params_json) = 'object'),
    severity VARCHAR(20) NOT NULL DEFAULT 'HIGH' CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    on_fail_action VARCHAR(30) NOT NULL DEFAULT 'WARNING'
        CHECK (on_fail_action IN ('BLOCK', 'QUARANTINE', 'QUARANTINE_HITL', 'WARNING', 'FINDING_ONLY')),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'RETIRED')),
    runtime_mode VARCHAR(20) NOT NULL DEFAULT 'SHADOW' CHECK (runtime_mode IN ('SHADOW', 'ENFORCED')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ,
    approved_by VARCHAR(200), approved_at TIMESTAMPTZ, approval_role VARCHAR(50),
    description TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_id, version),
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    CHECK (status <> 'ACTIVE' OR
           (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approval_role IN ('ADMIN', 'DATA_PLATFORM_OWNER')))
);
CREATE INDEX IF NOT EXISTS idx_reliability_rules_lookup
    ON engine.reliability_rules(dataset_id, status, runtime_mode, effective_from, effective_to);
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'reliability_rules_no_overlapping_active_versions'
          AND conrelid = 'engine.reliability_rules'::regclass
    ) THEN
        ALTER TABLE engine.reliability_rules
            ADD CONSTRAINT reliability_rules_no_overlapping_active_versions
            EXCLUDE USING gist (
                rule_id WITH =, dataset_id WITH =,
                (tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)')) WITH &&
            ) WHERE (status = 'ACTIVE');
    END IF;
END $$;

ALTER TABLE policy.compliance_rules
    ADD COLUMN IF NOT EXISTS rule_domain VARCHAR(20) NOT NULL DEFAULT 'LANE_B';
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_domain_valid;
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_domain_valid CHECK (rule_domain = 'LANE_B');
COMMENT ON COLUMN policy.compliance_rules.rule_domain IS 'Explicit legal/compliance ownership; policy rules execute only in Lane B.';

-- Seed the code defaults as approved version-1 configuration. ON CONFLICT makes
-- repeated deployments safe and preserves any administrator-created versions.
INSERT INTO engine.reliability_rules
    (rule_id, version, dataset_id, layer, detector_id, target_fields, params_json,
     severity, on_fail_action, status, runtime_mode, effective_from,
     approved_by, approved_at, approval_role, description)
VALUES
 ('L1-RANGE-BATTERY-SOC', 1, '*', 'L1', 'RANGE', ARRAY['battery_soc'], '{"min":0.0,"max":100.0}', 'CRITICAL', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Migrated from L1toL4DetectorSuite.DEFAULT_CONFIG'),
 ('L1-RANGE-BATTERY-TEMP', 1, '*', 'L1', 'RANGE', ARRAY['battery_temp_c'], '{"min":-20.0,"max":65.0}', 'CRITICAL', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Technical battery safety threshold migrated out of Lane B'),
 ('L1-RANGE-POWER', 1, '*', 'L1', 'RANGE', ARRAY['power_kw'], '{"min":0.0,"max":350.0}', 'CRITICAL', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Technical charger range migrated out of Lane B'),
 ('L1-RANGE-FARE', 1, 'ride_hailing_xanh_sm_trips', 'L1', 'RANGE', ARRAY['fare_amount'], '{"min":0.000001}', 'HIGH', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Positive fare data-quality gate migrated out of Lane B'),
 ('L1-RANGE-TRIP-DISTANCE', 1, 'ride_hailing_xanh_sm_trips', 'L1', 'RANGE', ARRAY['trip_distance_km'], '{"min":0.1}', 'HIGH', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Minimum trip distance data-quality gate migrated out of Lane B'),
 ('L1-ARITHMETIC-TOTAL-FARE', 1, 'ride_hailing_xanh_sm_trips', 'L1', 'ARITHMETIC', ARRAY['total_fare','fare_amount','tip_amount'], '{"total_field":"total_fare","sum_fields":["fare_amount","tip_amount"],"tolerance":1.0}', 'HIGH', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Fare ledger arithmetic uses a fixed allowlisted detector'),
 ('L1-CONDITION-ZERO-SPEED-RPM', 1, '*', 'L1', 'CONDITION', ARRAY['speed_kmh','motor_rpm'], '{"condition_id":"ZERO_SPEED_HIGH_RPM","rpm_max":12000}', 'CRITICAL', 'QUARANTINE', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Impossible physical state uses a fixed named predicate'),
 ('L2-DEFAULT-METRICS', 1, '*', 'L2', 'ROBUST_Z', ARRAY['battery_soc','kwh_consumed','fare_amount'], '{"baseline_min_samples":30,"z_threshold":4.5,"warmup_days":2,"min_samples":3}', 'MEDIUM', 'WARNING', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Migrated from L1toL4DetectorSuite.DEFAULT_CONFIG'),
 ('L3-DEFAULT-RELATIONS', 1, '*', 'L3', 'RELATION', ARRAY['duration_mins','kwh_consumed','trip_distance_km','soc_delta','fare_amount','total_fare'], '{"relations":[{"x":"duration_mins","y":"kwh_consumed"},{"x":"duration_mins","y":"trip_distance_km"},{"x":"soc_delta","y":"kwh_consumed"},{"x":"fare_amount","y":"total_fare"}],"residual_z_threshold":4.0}', 'MEDIUM', 'WARNING', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Migrated from L1toL4DetectorSuite.DEFAULT_CONFIG'),
 ('L4-DEFAULT-METRICS', 1, '*', 'L4', 'CHANGEPOINT', ARRAY['battery_temp_c','battery_soc','trip_distance_km'], '{"penalty":3.0,"min_segment_len":3,"persistence_window":3,"attribution_window":5}', 'MEDIUM', 'WARNING', 'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z', 'SYSTEM_MIGRATION', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER', 'Migrated from L1toL4DetectorSuite.DEFAULT_CONFIG')
ON CONFLICT (rule_id, version) DO NOTHING;

-- These checks are technical reliability controls and must no longer execute
-- as legal/policy controls in Lane B. History is retained for audit.
UPDATE policy.compliance_rules
SET status = 'RETIRED', runtime_mode = 'SHADOW'
WHERE rule_id IN (
    'COMP-TRIP-REV-01', 'COMP-TEL-BMS-05', 'COMP-CHG-KW-06',
    'COMP-TRIP-DIST-07', 'COMP-CHG-METER-08', 'COMP-FLEET-STATUS-09'
);
