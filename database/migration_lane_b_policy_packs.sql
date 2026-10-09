-- =============================================================================
-- Lane B metadata-driven privacy policy packs (VN / EU / US-CA)
--
-- This migration is deliberately additive and re-runnable.  Approval columns
-- remain for API compatibility, but ACTIVE + effective window is the runtime
-- activation contract.  Legal citations describe the source obligation;
-- executable rules are explicitly internal implementation controls.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS policy;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- -----------------------------------------------------------------------------
-- Jurisdiction resolution is data, not pipeline branching.
-- default_child_id lets the public zone US resolve to the implemented US-CA
-- pack while retaining US as a hierarchy node.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS policy.jurisdictions (
    jurisdiction_id VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(200) NOT NULL,
    parent_id VARCHAR(50) REFERENCES policy.jurisdictions(jurisdiction_id),
    default_child_id VARCHAR(50),
    level_type VARCHAR(20) NOT NULL DEFAULT 'ZONE'
        CHECK (level_type IN ('GLOBAL', 'ZONE', 'COUNTRY', 'STATE')),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'INACTIVE')),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata_json) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (parent_id IS NULL OR parent_id <> jurisdiction_id)
);

DO $$ BEGIN
    ALTER TABLE policy.jurisdictions
        ADD CONSTRAINT jurisdictions_default_child_fk
        FOREIGN KEY (default_child_id)
        REFERENCES policy.jurisdictions(jurisdiction_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS policy.jurisdiction_aliases (
    alias VARCHAR(50) PRIMARY KEY,
    jurisdiction_id VARCHAR(50) NOT NULL
        REFERENCES policy.jurisdictions(jurisdiction_id),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO policy.jurisdictions
    (jurisdiction_id, display_name, parent_id, default_child_id, level_type, status, metadata_json)
VALUES
    ('GLOBAL', 'Global baseline', NULL, NULL, 'GLOBAL', 'ACTIVE',
     '{"resolution_order":0}'::jsonb),
    ('VN', 'Vietnam', 'GLOBAL', NULL, 'ZONE', 'ACTIVE',
     '{"iso_country":"VN"}'::jsonb),
    ('EU', 'European Union', 'GLOBAL', NULL, 'ZONE', 'ACTIVE',
     '{"framework":"GDPR"}'::jsonb),
    ('US', 'United States', 'GLOBAL', NULL, 'ZONE', 'ACTIVE',
     '{"pilot_scope":"California"}'::jsonb),
    ('US-CA', 'California, United States', 'US', NULL, 'STATE', 'ACTIVE',
     '{"iso_subdivision":"US-CA","framework":"CCPA/CPRA"}'::jsonb)
ON CONFLICT (jurisdiction_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    parent_id = EXCLUDED.parent_id,
    level_type = EXCLUDED.level_type,
    status = EXCLUDED.status,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = CURRENT_TIMESTAMP;

UPDATE policy.jurisdictions
SET default_child_id = 'US-CA', updated_at = CURRENT_TIMESTAMP
WHERE jurisdiction_id = 'US';

INSERT INTO policy.jurisdiction_aliases (alias, jurisdiction_id, description)
VALUES
    ('GLOBAL', 'GLOBAL', 'Canonical global scope'),
    ('VN', 'VN', 'Pilot subject_zone value'),
    ('VIETNAM', 'VN', 'Readable Vietnam alias'),
    ('EU', 'EU', 'Pilot subject_zone value'),
    ('EEA', 'EU', 'EU/EEA privacy scope alias for this pilot'),
    ('US', 'US', 'Pilot subject_zone; resolver follows default child US-CA'),
    ('US-CA', 'US-CA', 'Canonical California jurisdiction'),
    ('CA', 'US-CA', 'California alias')
ON CONFLICT (alias) DO UPDATE SET
    jurisdiction_id = EXCLUDED.jurisdiction_id,
    description = EXCLUDED.description;

-- -----------------------------------------------------------------------------
-- Legal sources and clauses already exist. Add canonical sources without
-- rewriting legacy policy rows.
-- -----------------------------------------------------------------------------
INSERT INTO policy.compliance_policies
    (policy_id, title, jurisdiction, legal_framework, version,
     raw_policy_text, effective_date, status)
VALUES
    ('POL-GLOBAL-PRIVACY', 'DataTrust Global Analytics Privacy Baseline',
     'GLOBAL', 'Internal implementation control', '1.0',
     'Technical baseline for valid jurisdiction metadata and prevention of cleartext credentials in analytics data.',
     DATE '2026-01-01', 'active'),
    ('POL-VN-LAW91', 'Vietnam Personal Data Protection Law 91/2025/QH15',
     'VN', 'Law 91/2025/QH15 and Decree 356/2025/ND-CP', '1.0',
     'Personal-data protection obligations mapped to technical minimization, pseudonymization, masking and location generalization controls.',
     DATE '2026-01-01', 'active'),
    ('POL-EU-GDPR', 'EU General Data Protection Regulation',
     'EU', 'Regulation (EU) 2016/679', '3.0',
     'Articles 5, 25 and 32 mapped to internal data-minimization, pseudonymization and security controls.',
     DATE '2018-05-25', 'active'),
    ('POL-US-CCPA', 'California Consumer Privacy Act as amended by CPRA',
     'US-CA', 'CCPA/CPRA', '1.0',
     'California personal-information and sensitive precise-geolocation obligations mapped to internal minimization and de-identification controls.',
     DATE '2023-01-01', 'active')
ON CONFLICT (policy_id) DO UPDATE SET
    title = EXCLUDED.title,
    jurisdiction = EXCLUDED.jurisdiction,
    legal_framework = EXCLUDED.legal_framework,
    version = EXCLUDED.version,
    raw_policy_text = EXCLUDED.raw_policy_text,
    effective_date = EXCLUDED.effective_date,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO policy.policy_clauses
    (clause_id, policy_id, clause_number, requirement_summary,
     target_pii_roles, mandated_action)
VALUES
    ('CLAUSE-GLOBAL-ZONE', 'POL-GLOBAL-PRIVACY', 'BASELINE-JURISDICTION',
     'Every analytics record must declare a supported subject jurisdiction.',
     ARRAY['NON_PERSONAL_REFERENCE']::catalog.pii_role_type[], 'KEEP'),
    ('CLAUSE-GLOBAL-CREDENTIAL', 'POL-GLOBAL-PRIVACY', 'BASELINE-CREDENTIALS',
     'Credential and secret material is forbidden in analytics records.',
     ARRAY['DIRECT_IDENTIFIER']::catalog.pii_role_type[], 'REMOVE'),
    ('CLAUSE-VN-PRIVACY-TECH', 'POL-VN-LAW91', 'Technical protection controls',
     'Apply proportionate technical controls to identifiers, contact details, location and unstructured personal data.',
     ARRAY['DIRECT_IDENTIFIER','LINKABLE_IDENTIFIER','CONTEXTUAL_PERSONAL_DATA']::catalog.pii_role_type[], 'PSEUDONYMIZE'),
    ('CLAUSE-EU-GDPR-5-25-32', 'POL-EU-GDPR', 'Articles 5, 25 and 32',
     'Data minimization, data protection by design and appropriate security controls.',
     ARRAY['DIRECT_IDENTIFIER','LINKABLE_IDENTIFIER','CONTEXTUAL_PERSONAL_DATA']::catalog.pii_role_type[], 'PSEUDONYMIZE'),
    ('CLAUSE-US-CA-SENSITIVE-PI', 'POL-US-CCPA', 'Cal. Civ. Code 1798.100 et seq.',
     'Minimize and protect personal information, including precise geolocation classified as sensitive personal information.',
     ARRAY['DIRECT_IDENTIFIER','LINKABLE_IDENTIFIER','CONTEXTUAL_PERSONAL_DATA']::catalog.pii_role_type[], 'GENERALIZE')
ON CONFLICT (clause_id) DO UPDATE SET
    policy_id = EXCLUDED.policy_id,
    clause_number = EXCLUDED.clause_number,
    requirement_summary = EXCLUDED.requirement_summary,
    target_pii_roles = EXCLUDED.target_pii_roles,
    mandated_action = EXCLUDED.mandated_action;

CREATE TABLE IF NOT EXISTS policy.policy_packs (
    pack_id VARCHAR(100) PRIMARY KEY,
    pack_name VARCHAR(255) NOT NULL,
    jurisdiction_id VARCHAR(50) NOT NULL
        REFERENCES policy.jurisdictions(jurisdiction_id),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED')),
    runtime_mode VARCHAR(20) NOT NULL DEFAULT 'ENFORCED'
        CHECK (runtime_mode IN ('SHADOW', 'ENFORCED')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    UNIQUE (jurisdiction_id, version)
);

CREATE TABLE IF NOT EXISTS policy.policy_pack_members (
    pack_id VARCHAR(100) NOT NULL REFERENCES policy.policy_packs(pack_id),
    policy_id VARCHAR(50) NOT NULL REFERENCES policy.compliance_policies(policy_id),
    clause_id VARCHAR(50) REFERENCES policy.policy_clauses(clause_id),
    control_kind VARCHAR(40) NOT NULL DEFAULT 'INTERNAL_IMPLEMENTATION_CONTROL'
        CHECK (control_kind IN ('DIRECT_LEGAL_REQUIREMENT',
                                'INTERNAL_IMPLEMENTATION_CONTROL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pack_id, policy_id, clause_id)
);

INSERT INTO policy.policy_packs
    (pack_id, pack_name, jurisdiction_id, version, status, runtime_mode,
     effective_from, description)
VALUES
    ('PACK-GLOBAL-PRIVACY-V1', 'Global privacy baseline', 'GLOBAL', 1,
     'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z',
     'System invariants shared by every Lane B record.'),
    ('PACK-VN-PRIVACY-V1', 'Vietnam privacy technical controls', 'VN', 1,
     'ACTIVE', 'ENFORCED', '2026-01-01T00:00:00Z',
     'Law 91/2025/QH15 and Decree 356/2025/ND-CP implementation controls.'),
    ('PACK-EU-GDPR-V1', 'EU GDPR technical controls', 'EU', 1,
     'ACTIVE', 'ENFORCED', '2018-05-25T00:00:00Z',
     'GDPR Articles 5, 25 and 32 implementation controls.'),
    ('PACK-US-CA-PRIVACY-V1', 'California CCPA/CPRA technical controls', 'US-CA', 1,
     'ACTIVE', 'ENFORCED', '2023-01-01T00:00:00Z',
     'CCPA/CPRA implementation controls for the US pilot zone.')
ON CONFLICT (pack_id) DO UPDATE SET
    pack_name = EXCLUDED.pack_name,
    jurisdiction_id = EXCLUDED.jurisdiction_id,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    runtime_mode = EXCLUDED.runtime_mode,
    effective_from = EXCLUDED.effective_from,
    effective_to = EXCLUDED.effective_to,
    description = EXCLUDED.description,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO policy.policy_pack_members
    (pack_id, policy_id, clause_id, control_kind)
VALUES
    ('PACK-GLOBAL-PRIVACY-V1', 'POL-GLOBAL-PRIVACY', 'CLAUSE-GLOBAL-ZONE', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('PACK-GLOBAL-PRIVACY-V1', 'POL-GLOBAL-PRIVACY', 'CLAUSE-GLOBAL-CREDENTIAL', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('PACK-VN-PRIVACY-V1', 'POL-VN-LAW91', 'CLAUSE-VN-PRIVACY-TECH', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('PACK-EU-GDPR-V1', 'POL-EU-GDPR', 'CLAUSE-EU-GDPR-5-25-32', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('PACK-US-CA-PRIVACY-V1', 'POL-US-CCPA', 'CLAUSE-US-CA-SENSITIVE-PI', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (pack_id, policy_id, clause_id) DO UPDATE SET
    control_kind = EXCLUDED.control_kind;

-- -----------------------------------------------------------------------------
-- Upgrade executable rule tables while retaining compatibility columns.
-- -----------------------------------------------------------------------------
ALTER TABLE policy.compliance_rules
    ADD COLUMN IF NOT EXISTS pack_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS clause_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS control_kind VARCHAR(40)
        DEFAULT 'INTERNAL_IMPLEMENTATION_CONTROL';

ALTER TABLE policy.compliance_rules
    DROP CONSTRAINT IF EXISTS compliance_rules_legal_approval_required;
ALTER TABLE policy.compliance_rules
    ALTER COLUMN status SET DEFAULT 'DRAFT';
ALTER TABLE policy.compliance_rules
    ALTER COLUMN runtime_mode SET DEFAULT 'ENFORCED';

DO $$ BEGIN
    ALTER TABLE policy.compliance_rules
        ADD CONSTRAINT compliance_rules_pack_fk FOREIGN KEY (pack_id)
        REFERENCES policy.policy_packs(pack_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.compliance_rules
        ADD CONSTRAINT compliance_rules_clause_fk FOREIGN KEY (clause_id)
        REFERENCES policy.policy_clauses(clause_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.compliance_rules
        ADD CONSTRAINT compliance_rules_control_kind_valid CHECK
        (control_kind IN ('DIRECT_LEGAL_REQUIREMENT',
                          'INTERNAL_IMPLEMENTATION_CONTROL'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE policy.data_treatment_rules
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS pack_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS clause_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS control_kind VARCHAR(40)
        DEFAULT 'INTERNAL_IMPLEMENTATION_CONTROL',
    ADD COLUMN IF NOT EXISTS effective_from TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS effective_to TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS runtime_mode VARCHAR(20) NOT NULL DEFAULT 'ENFORCED',
    ADD COLUMN IF NOT EXISTS on_fail_action VARCHAR(50) NOT NULL DEFAULT 'QUARANTINE',
    ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100;

UPDATE policy.data_treatment_rules
SET effective_from = COALESCE(effective_from, created_at, CURRENT_TIMESTAMP),
    status = CASE UPPER(status)
        WHEN 'ACTIVE' THEN 'ACTIVE'
        WHEN 'DRAFT' THEN 'DRAFT'
        WHEN 'RETIRED' THEN 'RETIRED'
        WHEN 'PAUSED' THEN 'RETIRED'
        ELSE 'DRAFT'
    END;

ALTER TABLE policy.data_treatment_rules
    ALTER COLUMN effective_from SET NOT NULL,
    ALTER COLUMN effective_from SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN status SET DEFAULT 'DRAFT';

DO $$
DECLARE pk_name TEXT;
BEGIN
    SELECT conname INTO pk_name
    FROM pg_constraint
    WHERE conrelid = 'policy.data_treatment_rules'::regclass
      AND contype = 'p';
    IF pk_name IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'policy.data_treatment_rules'::regclass
          AND c.contype = 'p'
          AND pg_get_constraintdef(c.oid) LIKE '%(rule_id, version)%'
    ) THEN
        EXECUTE format('ALTER TABLE policy.data_treatment_rules DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;

DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_pkey PRIMARY KEY (rule_id, version);
EXCEPTION WHEN duplicate_object OR invalid_table_definition THEN NULL;
END $$;

ALTER TABLE policy.data_treatment_rules
    DROP CONSTRAINT IF EXISTS data_treatment_rules_status_valid;
ALTER TABLE policy.data_treatment_rules
    ADD CONSTRAINT data_treatment_rules_status_valid
    CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED'));

DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_version_positive CHECK (version > 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_effective_window_valid CHECK
        (effective_to IS NULL OR effective_to > effective_from);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_runtime_mode_valid CHECK
        (runtime_mode IN ('SHADOW', 'ENFORCED'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_action_valid CHECK
        (on_fail_action IN ('BLOCK', 'QUARANTINE', 'QUARANTINE_HITL',
                            'WARNING', 'FINDING_ONLY'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_control_kind_valid CHECK
        (control_kind IN ('DIRECT_LEGAL_REQUIREMENT',
                          'INTERNAL_IMPLEMENTATION_CONTROL'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_pack_fk FOREIGN KEY (pack_id)
        REFERENCES policy.policy_packs(pack_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_clause_fk FOREIGN KEY (clause_id)
        REFERENCES policy.policy_clauses(clause_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_policy_pack_active
    ON policy.policy_packs(jurisdiction_id, status, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_policy_compliance_pack
    ON policy.compliance_rules(pack_id, status, runtime_mode);
CREATE INDEX IF NOT EXISTS idx_policy_treatment_lookup_v2
    ON policy.data_treatment_rules
       (dataset_id, jurisdiction, status, effective_from, effective_to, priority);

DO $$ BEGIN
    ALTER TABLE policy.data_treatment_rules
        ADD CONSTRAINT data_treatment_rules_no_overlapping_active_versions
        EXCLUDE USING gist (
            rule_id WITH =, dataset_id WITH =, jurisdiction WITH =,
            (COALESCE(country, '')) WITH =,
            (tstzrange(effective_from,
                       COALESCE(effective_to, 'infinity'::timestamptz), '[)')) WITH &&
        ) WHERE (status = 'ACTIVE');
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
END $$;

-- -----------------------------------------------------------------------------
-- Active executable compliance rules. These verify the post-treatment shape;
-- the legal obligation and technical implementation are kept distinct.
-- -----------------------------------------------------------------------------
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-GLOBAL-ZONE-V1', 1, '*', 'subject_zone',
     'Supported subject jurisdiction', 'SUPPORTED_SUBJECT_ZONE',
     'subject_zone IN (VN, EU, US)',
     'System invariant: the record declares one of the pilot zones.',
     'POL-GLOBAL-PRIVACY', 'Global privacy baseline',
     'Internal analytics privacy baseline', 'GLOBAL', NULL, 'CRITICAL',
     'QUARANTINE', 'ACTIVE', '2026-01-01T00:00:00Z', 'PRE_CHECK',
     '{"operator":"enum","field":"subject_zone","values":["VN","EU","US"]}'::jsonb,
     'FAIL', 'FAIL', FALSE, 'ENFORCED', 'PACK-GLOBAL-PRIVACY-V1',
     'CLAUSE-GLOBAL-ZONE', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('COMP-VN-TRIP-ID-V1', 1, 'ride_hailing_xanh_sm_trips', 'customer_id',
     'VN customer identifier pseudonymized', 'VN_CUSTOMER_ID_HASHED',
     'customer_id is pseudonymized',
     'Post-treatment verification for a linkable customer identifier.',
     'POL-VN-LAW91', 'Vietnam privacy technical controls',
     'Law 91/2025/QH15; Decree 356/2025/ND-CP', 'VN', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2026-01-01T00:00:00Z', 'POST_CHECK',
     '{"operator":"hashed","field":"customer_id","algorithm":"HMAC-SHA256","length":64}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-VN-PRIVACY-V1',
     'CLAUSE-VN-PRIVACY-TECH', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('COMP-EU-TRIP-ID-V1', 1, 'ride_hailing_xanh_sm_trips', 'customer_id',
     'EU customer identifier pseudonymized', 'EU_CUSTOMER_ID_HASHED',
     'customer_id is pseudonymized',
     'Post-treatment pseudonymization verification under the GDPR pack.',
     'POL-EU-GDPR', 'EU GDPR technical controls',
     'GDPR Articles 5, 25 and 32', 'EU', NULL, 'HIGH', 'QUARANTINE',
     'ACTIVE', '2018-05-25T00:00:00Z', 'POST_CHECK',
     '{"operator":"hashed","field":"customer_id","algorithm":"HMAC-SHA256","length":64}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-EU-GDPR-V1',
     'CLAUSE-EU-GDPR-5-25-32', 'INTERNAL_IMPLEMENTATION_CONTROL'),
    ('COMP-USCA-TRIP-ID-V1', 1, 'ride_hailing_xanh_sm_trips', 'customer_id',
     'US-CA customer identifier pseudonymized', 'USCA_CUSTOMER_ID_HASHED',
     'customer_id is pseudonymized',
     'Post-treatment identifier protection for the California pilot scope.',
     'POL-US-CCPA', 'California CCPA/CPRA technical controls',
     'CCPA/CPRA; Cal. Civ. Code 1798.100 et seq.', 'US-CA', 'US-CA',
     'HIGH', 'QUARANTINE', 'ACTIVE', '2023-01-01T00:00:00Z', 'POST_CHECK',
     '{"operator":"hashed","field":"customer_id","algorithm":"HMAC-SHA256","length":64}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-US-CA-PRIVACY-V1',
     'CLAUSE-US-CA-SENSITIVE-PI', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    dataset_id = EXCLUDED.dataset_id,
    column_name = EXCLUDED.column_name,
    rule_name = EXCLUDED.rule_name,
    rule_code = EXCLUDED.rule_code,
    expression = EXCLUDED.expression,
    description = EXCLUDED.description,
    policy_id = EXCLUDED.policy_id,
    policy_name = EXCLUDED.policy_name,
    law_ref = EXCLUDED.law_ref,
    jurisdiction = EXCLUDED.jurisdiction,
    country = EXCLUDED.country,
    severity = EXCLUDED.severity,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status,
    effective_from = EXCLUDED.effective_from,
    effective_to = NULL,
    evaluation_phase = EXCLUDED.evaluation_phase,
    condition_json = EXCLUDED.condition_json,
    missing_behavior = EXCLUDED.missing_behavior,
    invalid_type_behavior = EXCLUDED.invalid_type_behavior,
    legal_review_required = FALSE,
    runtime_mode = EXCLUDED.runtime_mode,
    pack_id = EXCLUDED.pack_id,
    clause_id = EXCLUDED.clause_id,
    control_kind = EXCLUDED.control_kind;

-- -----------------------------------------------------------------------------
-- Treatment controls. The same technical operation is intentionally repeated
-- per pack so evidence can name the exact jurisdiction, clause and version.
-- Backend operation registry remains allow-listed; no SQL/code is executed
-- from params_json.
-- -----------------------------------------------------------------------------
INSERT INTO policy.data_treatment_rules
    (rule_id, version, dataset_id, column_name, operation_id, treatment_name,
     params_json, expression_display, description, policy_id, policy_name,
     law_ref, jurisdiction, country, status, effective_from, runtime_mode,
     on_fail_action, priority, pack_id, clause_id, control_kind, enforced_by)
SELECT
    'TREAT-' || zone.code || '-' || field.rule_suffix,
    1, field.dataset_id, field.column_name, field.operation_id,
    zone.code || ' - ' || field.treatment_name,
    field.params_json, field.expression_display,
    field.description, zone.policy_id, zone.policy_name, zone.law_ref,
    zone.jurisdiction, zone.country, 'ACTIVE', zone.effective_from,
    'ENFORCED', 'QUARANTINE', field.priority, zone.pack_id, zone.clause_id,
    'INTERNAL_IMPLEMENTATION_CONTROL', 'POLICY_MIGRATION'
FROM (VALUES
    ('VN', 'VN', NULL::VARCHAR, 'POL-VN-LAW91',
     'Vietnam privacy technical controls',
     'Law 91/2025/QH15; Decree 356/2025/ND-CP',
     'PACK-VN-PRIVACY-V1', 'CLAUSE-VN-PRIVACY-TECH',
     '2026-01-01T00:00:00Z'::timestamptz),
    ('EU', 'EU', NULL::VARCHAR, 'POL-EU-GDPR',
     'EU GDPR technical controls', 'GDPR Articles 5, 25 and 32',
     'PACK-EU-GDPR-V1', 'CLAUSE-EU-GDPR-5-25-32',
     '2018-05-25T00:00:00Z'::timestamptz),
    ('USCA', 'US-CA', 'US-CA'::VARCHAR, 'POL-US-CCPA',
     'California CCPA/CPRA technical controls',
     'CCPA/CPRA; Cal. Civ. Code 1798.100 et seq.',
     'PACK-US-CA-PRIVACY-V1', 'CLAUSE-US-CA-SENSITIVE-PI',
     '2023-01-01T00:00:00Z'::timestamptz)
) AS zone(code, jurisdiction, country, policy_id, policy_name, law_ref,
          pack_id, clause_id, effective_from)
CROSS JOIN (VALUES
    ('TRIP-CUSTOMER-ID', 'ride_hailing_xanh_sm_trips', 'customer_id',
     'hmac_sha256', 'Pseudonymize customer ID',
     '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(customer_id, secret_ref)',
     'Stable keyed pseudonym for linkage without exposing the source identifier.', 10),
    ('TRIP-DRIVER-ID', 'ride_hailing_xanh_sm_trips', 'driver_id',
     'hmac_sha256', 'Pseudonymize driver ID',
     '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(driver_id, secret_ref)',
     'Stable keyed pseudonym for the driver identifier.', 20),
    ('TRIP-VIN', 'ride_hailing_xanh_sm_trips', 'vehicle_vin',
     'hmac_sha256', 'Pseudonymize vehicle VIN',
     '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)',
     'Stable keyed pseudonym for the linkable vehicle identifier.', 30),
    ('TRIP-CONTACT', 'ride_hailing_xanh_sm_trips', 'customer_contact',
     'mask_contact', 'Mask customer contact',
     '{"phone_prefix_len":3,"phone_suffix_len":2,"keep_email_domain":true}'::jsonb,
     'mask_contact(customer_contact)',
     'Deterministically masks either a phone number or an email address.', 40),
    ('TRIP-PICKUP-LAT', 'ride_hailing_xanh_sm_trips', 'pickup_latitude',
     'round_decimal', 'Generalize pickup latitude', '{"decimals":2}'::jsonb,
     'round_decimal(pickup_latitude, 2)',
     'Reduces precise pickup-location resolution before Silver.', 50),
    ('TRIP-PICKUP-LON', 'ride_hailing_xanh_sm_trips', 'pickup_longitude',
     'round_decimal', 'Generalize pickup longitude', '{"decimals":2}'::jsonb,
     'round_decimal(pickup_longitude, 2)',
     'Reduces precise pickup-location resolution before Silver.', 60),
    ('CUSTOMER-ID', 'dim_customers', 'customer_id', 'hmac_sha256',
     'Pseudonymize customer ID',
     '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(customer_id, secret_ref)',
     'Stable keyed pseudonym for the customer identifier.', 10),
    ('CUSTOMER-FIRST-NAME', 'dim_customers', 'first_name', 'mask_name',
     'Mask customer first name', '{"keep_first":false,"mask_char":"*"}'::jsonb,
     'mask_name(first_name)', 'Masks a direct name identifier.', 20),
    ('CUSTOMER-LAST-NAME', 'dim_customers', 'last_name', 'mask_name',
     'Mask customer last name', '{"keep_first":false,"mask_char":"*"}'::jsonb,
     'mask_name(last_name)', 'Masks a direct name identifier.', 30),
    ('CUSTOMER-EMAIL', 'dim_customers', 'email', 'mask_email',
     'Mask customer email', '{"keep_domain":true,"mask_char":"*"}'::jsonb,
     'mask_email(email)', 'Masks the local part while retaining the domain.', 40),
    ('CUSTOMER-PHONE', 'dim_customers', 'phone_number', 'mask_phone',
     'Mask customer phone',
     '{"prefix_len":3,"suffix_len":2,"mask_char":"*"}'::jsonb,
     'mask_phone(phone_number)', 'Masks cleartext phone digits.', 50),
    ('FEEDBACK-CUSTOMER-ID', 'feedback_pii', 'customer_id', 'hmac_sha256',
     'Pseudonymize feedback customer ID',
     '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(customer_id, secret_ref)',
     'Stable keyed pseudonym for the feedback author.', 10),
    ('FEEDBACK-TEXT', 'feedback_pii', 'raw_comment_text', 'redact_pii_text',
     'Redact PII in feedback text',
     '{"detectors":["EMAIL","PHONE"]}'::jsonb,
     'redact_pii_text(raw_comment_text)',
     'Deterministically redacts supported email and phone patterns.', 20),
    ('DRIVER-ID', 'dim_drivers', 'driver_id', 'hmac_sha256',
     'Pseudonymize driver ID', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(driver_id, secret_ref)', 'Stable keyed driver pseudonym.', 10),
    ('DRIVER-VIN', 'dim_drivers', 'vehicle_vin', 'hmac_sha256',
     'Pseudonymize driver vehicle VIN', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)', 'Stable keyed vehicle pseudonym.', 20),
    ('DRIVER-FIRST-NAME', 'dim_drivers', 'first_name', 'mask_name',
     'Mask driver first name', '{"keep_first":false,"mask_char":"*"}'::jsonb,
     'mask_name(first_name)', 'Masks a direct name identifier.', 30),
    ('DRIVER-LAST-NAME', 'dim_drivers', 'last_name', 'mask_name',
     'Mask driver last name', '{"keep_first":false,"mask_char":"*"}'::jsonb,
     'mask_name(last_name)', 'Masks a direct name identifier.', 40),
    ('DRIVER-EMAIL', 'dim_drivers', 'email', 'mask_email',
     'Mask driver email', '{"keep_domain":true,"mask_char":"*"}'::jsonb,
     'mask_email(email)', 'Masks the email local part.', 50),
    ('DRIVER-PHONE', 'dim_drivers', 'phone_number', 'mask_phone',
     'Mask driver phone', '{"prefix_len":3,"suffix_len":2,"mask_char":"*"}'::jsonb,
     'mask_phone(phone_number)', 'Masks cleartext phone digits.', 60),
    ('TELEMETRY-VIN', 'synthetic_ev_telemetry_ved_ref', 'vehicle_vin', 'hmac_sha256',
     'Pseudonymize telemetry VIN', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)', 'Stable keyed vehicle pseudonym.', 10),
    ('TELEMETRY-LAT', 'synthetic_ev_telemetry_ved_ref', 'latitude', 'round_decimal',
     'Generalize telemetry latitude', '{"decimals":2}'::jsonb,
     'round_decimal(latitude, 2)', 'Reduces precise telemetry location.', 20),
    ('TELEMETRY-LON', 'synthetic_ev_telemetry_ved_ref', 'longitude', 'round_decimal',
     'Generalize telemetry longitude', '{"decimals":2}'::jsonb,
     'round_decimal(longitude, 2)', 'Reduces precise telemetry location.', 30),
    ('CHARGING-VIN', 'acn_charging_mapped', 'vehicle_vin', 'hmac_sha256',
     'Pseudonymize charging VIN', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)', 'Stable keyed vehicle pseudonym.', 10),
    ('FLEET-VIN', 'fleet_index', 'vehicle_vin', 'hmac_sha256',
     'Pseudonymize fleet VIN', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)', 'Stable keyed vehicle pseudonym.', 10),
    ('FEEDBACK-VIN', 'feedback_pii', 'vehicle_vin', 'hmac_sha256',
     'Pseudonymize feedback VIN', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)', 'Stable keyed vehicle pseudonym.', 30),
    ('SYNTH-FEEDBACK-VIN', 'synthetic_feedback_scenario_driven', 'vehicle_vin', 'hmac_sha256',
     'Pseudonymize synthetic feedback VIN', '{"secret_ref":"DATATRUST_PSEUDONYMIZATION_KEY"}'::jsonb,
     'hmac_sha256(vehicle_vin, secret_ref)', 'Stable keyed vehicle pseudonym.', 10),
    ('SYNTH-FEEDBACK-TEXT', 'synthetic_feedback_scenario_driven', 'raw_comment_text', 'redact_pii_text',
     'Redact PII in synthetic feedback text', '{"detectors":["EMAIL","PHONE"]}'::jsonb,
     'redact_pii_text(raw_comment_text)', 'Redacts supported email and phone patterns.', 20)
) AS field(rule_suffix, dataset_id, column_name, operation_id, treatment_name,
           params_json, expression_display, description, priority)
ON CONFLICT (rule_id, version) DO UPDATE SET
    dataset_id = EXCLUDED.dataset_id,
    column_name = EXCLUDED.column_name,
    operation_id = EXCLUDED.operation_id,
    treatment_name = EXCLUDED.treatment_name,
    params_json = EXCLUDED.params_json,
    expression_display = EXCLUDED.expression_display,
    description = EXCLUDED.description,
    policy_id = EXCLUDED.policy_id,
    policy_name = EXCLUDED.policy_name,
    law_ref = EXCLUDED.law_ref,
    jurisdiction = EXCLUDED.jurisdiction,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    effective_from = EXCLUDED.effective_from,
    effective_to = NULL,
    runtime_mode = EXCLUDED.runtime_mode,
    on_fail_action = EXCLUDED.on_fail_action,
    priority = EXCLUDED.priority,
    pack_id = EXCLUDED.pack_id,
    clause_id = EXCLUDED.clause_id,
    control_kind = EXCLUDED.control_kind,
    enforced_by = EXCLUDED.enforced_by,
    updated_at = CURRENT_TIMESTAMP;

-- Every treatment has a matching post-condition. This keeps the legal pack
-- declarative: adding a treatment row also has an explicit, auditable check.
INSERT INTO policy.compliance_rules (
    rule_id, version, dataset_id, column_name, rule_name, rule_code,
    expression, description, policy_id, policy_name, law_ref, jurisdiction,
    country, severity, on_fail_action, status, effective_from, effective_to,
    evaluation_phase, condition_json, missing_behavior, invalid_type_behavior,
    legal_review_required, runtime_mode, pack_id, clause_id, control_kind
)
SELECT
    replace(t.rule_id, 'TREAT-', 'COMP-') || '-POST', t.version,
    t.dataset_id, t.column_name, t.treatment_name || ' verified',
    'POST_' || upper(t.operation_id), t.expression_display,
    'Verifies the configured privacy treatment before the record can enter Silver.',
    t.policy_id, t.policy_name, t.law_ref, t.jurisdiction, t.country,
    'HIGH', 'QUARANTINE', 'ACTIVE', t.effective_from, t.effective_to,
    'POST_CHECK',
    CASE
      WHEN lower(t.operation_id) = 'hmac_sha256' THEN
        jsonb_build_object('operator','hashed','field',t.column_name,'length',64)
      WHEN lower(t.operation_id) IN ('mask_contact','mask_name','mask_email','mask_phone') THEN
        jsonb_build_object('operator','masked','field',t.column_name)
      WHEN lower(t.operation_id) = 'round_decimal' THEN
        jsonb_build_object('operator','precision','field',t.column_name,
                           'max_decimals',COALESCE((t.params_json->>'decimals')::int,2))
      WHEN lower(t.operation_id) = 'redact_pii_text' THEN
        jsonb_build_object('operator','redacted','field',t.column_name)
      ELSE jsonb_build_object('operator','required','field',t.column_name)
    END,
    'SKIP', 'FAIL', FALSE, t.runtime_mode, t.pack_id, t.clause_id,
    'INTERNAL_IMPLEMENTATION_CONTROL'
FROM policy.data_treatment_rules t
WHERE t.enforced_by = 'POLICY_MIGRATION'
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    status = EXCLUDED.status,
    runtime_mode = EXCLUDED.runtime_mode,
    effective_from = EXCLUDED.effective_from,
    effective_to = EXCLUDED.effective_to,
    pack_id = EXCLUDED.pack_id,
    clause_id = EXCLUDED.clause_id,
    jurisdiction = EXCLUDED.jurisdiction,
    country = EXCLUDED.country;

-- -----------------------------------------------------------------------------
-- Per-record execution evidence. Values and cleartext PII are intentionally not
-- stored: hashes identify the before/after states while rule_snapshot preserves
-- the executable metadata used by the run.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.record_policy_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100) NOT NULL,
    dataset_id VARCHAR(100) NOT NULL,
    record_id VARCHAR(200) NOT NULL,
    subject_zone VARCHAR(50),
    jurisdiction_chain TEXT[] NOT NULL DEFAULT ARRAY['GLOBAL']::TEXT[],
    pack_id VARCHAR(100) REFERENCES policy.policy_packs(pack_id),
    policy_id VARCHAR(50) REFERENCES policy.compliance_policies(policy_id),
    clause_id VARCHAR(50) REFERENCES policy.policy_clauses(clause_id),
    rule_id VARCHAR(100) NOT NULL,
    rule_version INTEGER NOT NULL,
    execution_type VARCHAR(20) NOT NULL
        CHECK (execution_type IN ('COMPLIANCE', 'TREATMENT')),
    phase VARCHAR(20) NOT NULL
        CHECK (phase IN ('PRE_CHECK', 'TREATMENT', 'POST_CHECK')),
    result VARCHAR(20) NOT NULL CHECK (result IN ('PASS', 'FAIL', 'SKIP')),
    runtime_state VARCHAR(20) NOT NULL
        CHECK (runtime_state IN ('ENFORCED', 'SHADOWED')),
    input_hash VARCHAR(64),
    output_hash VARCHAR(64),
    rule_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(rule_snapshot) = 'object'),
    CHECK (jsonb_typeof(details) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_record_policy_execution_run
    ON audit.record_policy_executions(run_id, dataset_id, record_id);
CREATE INDEX IF NOT EXISTS idx_record_policy_execution_rule
    ON audit.record_policy_executions(rule_id, rule_version, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_record_policy_execution_pack
    ON audit.record_policy_executions(pack_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_record_policy_execution_identity
    ON audit.record_policy_executions(
        run_id, dataset_id, record_id, execution_type, rule_id, rule_version, phase
    );

COMMENT ON COLUMN policy.compliance_rules.approved_by IS
    'Compatibility metadata only; approval is not an ACTIVE-rule prerequisite.';
COMMENT ON COLUMN policy.compliance_rules.approved_at IS
    'Compatibility metadata only; approval is not an ACTIVE-rule prerequisite.';
COMMENT ON TABLE audit.record_policy_executions IS
    'PII-safe record-level evidence for compliance and treatment rule execution.';

COMMIT;
