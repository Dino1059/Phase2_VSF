-- Upgrade policy.compliance_rules to versioned, approval-gated rules.
BEGIN;
CREATE EXTENSION IF NOT EXISTS "btree_gist";

ALTER TABLE policy.compliance_rules
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'PENDING_APPROVAL',
    ADD COLUMN IF NOT EXISTS effective_from TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS effective_to TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approved_by VARCHAR(200),
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approval_role VARCHAR(50),
    ADD COLUMN IF NOT EXISTS evaluation_phase VARCHAR(20) NOT NULL DEFAULT 'PRE_CHECK',
    ADD COLUMN IF NOT EXISTS condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS missing_behavior VARCHAR(20) NOT NULL DEFAULT 'FAIL',
    ADD COLUMN IF NOT EXISTS invalid_type_behavior VARCHAR(20) NOT NULL DEFAULT 'FAIL',
    ADD COLUMN IF NOT EXISTS legal_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS runtime_mode VARCHAR(20) NOT NULL DEFAULT 'SHADOW';

UPDATE policy.compliance_rules
SET effective_from = COALESCE(effective_from, enforced_at, CURRENT_TIMESTAMP),
    status = CASE WHEN status = 'ACTIVE' THEN 'PENDING_APPROVAL' ELSE status END,
    runtime_mode = 'SHADOW'
-- Only legacy rows (which received the empty JSON default above) are
-- downgraded for approval. Re-running this migration must not deactivate
-- subsequently approved, executable versions.
WHERE effective_from IS NULL
   OR (status = 'ACTIVE' AND condition_json = '{}'::jsonb);
ALTER TABLE policy.compliance_rules ALTER COLUMN effective_from SET NOT NULL;
ALTER TABLE policy.compliance_rules ALTER COLUMN effective_from SET DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_pkey;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_version_positive;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_status_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_phase_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_missing_behavior_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_invalid_type_behavior_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_action_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_runtime_mode_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_effective_window_valid;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_condition_object;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_legal_approval_required;
ALTER TABLE policy.compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_no_overlapping_active_versions;
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_pkey PRIMARY KEY (rule_id, version);
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_version_positive CHECK (version > 0);
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_status_valid CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'RETIRED'));
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_phase_valid CHECK (evaluation_phase IN ('PRE_CHECK', 'POST_CHECK'));
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_missing_behavior_valid CHECK (missing_behavior IN ('FAIL', 'WARNING', 'SKIP'));
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_invalid_type_behavior_valid CHECK (invalid_type_behavior IN ('FAIL', 'WARNING'));
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_action_valid CHECK (on_fail_action IN ('BLOCK', 'QUARANTINE', 'QUARANTINE_HITL', 'WARNING', 'FINDING_ONLY'));
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_runtime_mode_valid CHECK (runtime_mode IN ('SHADOW', 'ENFORCED'));
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_effective_window_valid CHECK (effective_to IS NULL OR effective_to > effective_from);
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_condition_object CHECK (jsonb_typeof(condition_json) = 'object');
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_legal_approval_required
    CHECK (status <> 'ACTIVE' OR NOT legal_review_required OR
           (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approval_role IN ('LEGAL', 'DPO')));

CREATE INDEX IF NOT EXISTS idx_policy_compliance_lookup
    ON policy.compliance_rules(dataset_id, jurisdiction, status, effective_from, effective_to);
ALTER TABLE policy.compliance_rules ADD CONSTRAINT compliance_rules_no_overlapping_active_versions
    EXCLUDE USING gist (
        rule_id WITH =, dataset_id WITH =, jurisdiction WITH =, (COALESCE(country, '')) WITH =,
        (tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)')) WITH &&
    ) WHERE (status = 'ACTIVE');

-- Convert legacy display expressions into executable, allow-listed documents.
UPDATE policy.compliance_rules SET condition_json =
    '{"operator":"range","field":"fare_amount","min":0.000001}'::jsonb,
    evaluation_phase = 'POST_CHECK', legal_review_required = TRUE
WHERE rule_id = 'COMP-TRIP-REV-01' AND version = 1;
UPDATE policy.compliance_rules SET condition_json =
    '{"operator":"geofence","latitude_field":"pickup_latitude","longitude_field":"pickup_longitude","bounds":{"min_lat":8.0,"max_lat":24.0,"min_lon":102.0,"max_lon":110.0}}'::jsonb,
    evaluation_phase = 'PRE_CHECK', legal_review_required = TRUE
WHERE rule_id = 'COMP-TRIP-GEO-02' AND version = 1;
UPDATE policy.compliance_rules SET condition_json =
    '{"operator":"masked","field":"customer_phone","pattern":".{2,}\\*+.{2,}"}'::jsonb,
    evaluation_phase = 'POST_CHECK', legal_review_required = TRUE
WHERE rule_id = 'COMP-CUST-PHONE-03' AND version = 1;
UPDATE policy.compliance_rules SET condition_json =
    '{"operator":"regex","field":"feedback_text","pattern":"^(?!.*(?:[0-9]{9,}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,})).*$"}'::jsonb,
    evaluation_phase = 'POST_CHECK', missing_behavior = 'SKIP', invalid_type_behavior = 'WARNING'
WHERE rule_id = 'COMP-FEEDBACK-PII-04' AND version = 1;
UPDATE policy.compliance_rules SET condition_json =
    '{"operator":"range","field":"battery_temp_c","min":-20.0,"max":65.0}'::jsonb,
    evaluation_phase = 'POST_CHECK'
WHERE rule_id = 'COMP-TEL-BMS-05' AND version = 1;
UPDATE policy.compliance_rules SET condition_json =
    '{"operator":"range","field":"power_kw","min":0.0,"max":350.0}'::jsonb,
    evaluation_phase = 'POST_CHECK'
WHERE rule_id = 'COMP-CHG-KW-06' AND version = 1;

INSERT INTO policy.compliance_rules
(rule_id, version, dataset_id, column_name, rule_name, rule_code, expression,
 description, law_ref, jurisdiction, severity, on_fail_action, status,
 evaluation_phase, condition_json, missing_behavior, invalid_type_behavior,
 legal_review_required, runtime_mode)
VALUES
('COMP-TRIP-DIST-07',1,'ride_hailing_xanh_sm_trips','trip_distance_km','Minimum billable trip distance','TRIP_DISTANCE_MIN','trip_distance_km >= 0.1','Business threshold with explicit exception handling required.','Finance policy pending approval','GLOBAL','HIGH','QUARANTINE','PENDING_APPROVAL','POST_CHECK','{"operator":"range","field":"trip_distance_km","min":0.1}'::jsonb,'FAIL','FAIL',FALSE,'SHADOW'),
('COMP-CHG-METER-08',1,'acn_charging_mapped','meter_kwh_delta','Meter to BMS relative delta','CHARGER_METER_DELTA','relative delta <= 3%','Compares meter and BMS energy.','V-GREEN metering standard pending approval','GLOBAL','HIGH','QUARANTINE','PENDING_APPROVAL','POST_CHECK','{"operator":"relative_delta","left_field":"meter_kwh_delta","right_field":"bms_kwh_delta","denominator":"left","max":0.03}'::jsonb,'FAIL','FAIL',FALSE,'SHADOW'),
('COMP-FLEET-STATUS-09',1,'fleet_index','operating_status','Allowed fleet operating status','FLEET_STATUS_ENUM','operating_status in approved values','Rejects unknown fleet states.','Internal fleet policy','GLOBAL','MEDIUM','WARNING','PENDING_APPROVAL','PRE_CHECK','{"operator":"enum","field":"operating_status","values":["READY","IN_SERVICE","CHARGING"]}'::jsonb,'FAIL','FAIL',FALSE,'SHADOW'),
('COMP-PURPOSE-10',1,'*','purpose_id','Purpose is required','PURPOSE_REQUIRED','purpose_id IS NOT NULL','Foundation control for purpose limitation.','Legal mapping pending review','GLOBAL','HIGH','QUARANTINE_HITL','PENDING_APPROVAL','PRE_CHECK','{"operator":"required","fields":["purpose_id"]}'::jsonb,'FAIL','FAIL',TRUE,'SHADOW'),
('COMP-DESTINATION-11',1,'*','destination_id','Destination is required','DESTINATION_REQUIRED','destination_id IS NOT NULL','Foundation control for destination evaluation.','Legal mapping pending review','GLOBAL','HIGH','QUARANTINE_HITL','PENDING_APPROVAL','PRE_CHECK','{"operator":"required","fields":["destination_id"]}'::jsonb,'FAIL','FAIL',TRUE,'SHADOW'),
('COMP-FORBIDDEN-CREDENTIAL-12',1,'*','password_hash','Forbidden credential material','FORBIDDEN_CREDENTIAL','password_hash MUST NOT BE PRESENT','Blocks credential-bearing records from analytics zones.','Security policy pending approval','GLOBAL','CRITICAL','BLOCK','PENDING_APPROVAL','PRE_CHECK','{"operator":"regex","field":"password_hash","pattern":"^$"}'::jsonb,'SKIP','FAIL',FALSE,'SHADOW')
ON CONFLICT (rule_id, version) DO NOTHING;
COMMIT;
