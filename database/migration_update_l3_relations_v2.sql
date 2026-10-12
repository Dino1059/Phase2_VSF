-- =============================================================================
-- Migration: Create Version 2 for L3-DEFAULT-RELATIONS in engine.reliability_rules
-- Preserves Version 1 immutably for forensic audit history.
-- Version 2 removes non-deterministic fare_amount vs total_fare regression.
-- Fare math is deterministically verified by L1-ARITHMETIC-TOTAL-FARE.
-- =============================================================================

-- 1. Expire Version 1
UPDATE engine.reliability_rules
SET effective_to = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE rule_id = 'L3-DEFAULT-RELATIONS' AND version = 1;

-- 2. Insert Version 2
INSERT INTO engine.reliability_rules (
    rule_id, version, dataset_id, layer, detector_id, target_fields, params_json,
    severity, on_fail_action, status, runtime_mode, effective_from, effective_to,
    approved_by, approved_at, approval_role, description
) VALUES (
    'L3-DEFAULT-RELATIONS', 2, '*', 'L3', 'RELATION',
    ARRAY['duration_mins','kwh_consumed','trip_distance_km','soc_delta'],
    '{"relations":[{"x":"duration_mins","y":"kwh_consumed"},{"x":"duration_mins","y":"trip_distance_km"},{"x":"soc_delta","y":"kwh_consumed"}],"residual_z_threshold":4.0}'::jsonb,
    'MEDIUM', 'WARNING', 'ACTIVE', 'ENFORCED', CURRENT_TIMESTAMP, NULL,
    'DATA_PLATFORM_OWNER', CURRENT_TIMESTAMP, 'DATA_PLATFORM_OWNER',
    'Version 2: Removed fare_amount vs total_fare regression. Fare math is verified deterministically by L1-ARITHMETIC-TOTAL-FARE.'
)
ON CONFLICT (rule_id, version) DO UPDATE SET
    params_json = EXCLUDED.params_json,
    status = EXCLUDED.status,
    runtime_mode = EXCLUDED.runtime_mode,
    effective_from = EXCLUDED.effective_from,
    effective_to = EXCLUDED.effective_to,
    updated_at = CURRENT_TIMESTAMP;
