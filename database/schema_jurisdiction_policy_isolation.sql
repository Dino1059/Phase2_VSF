-- Jurisdiction-aware policy evaluation and Finding isolation.
-- Idempotent migration. Apply through the normal database migration workflow.

BEGIN;

ALTER TABLE policy.compliance_rules
    ADD COLUMN IF NOT EXISTS policy_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS policy_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(50) NOT NULL DEFAULT 'UNSCOPED',
    ADD COLUMN IF NOT EXISTS country VARCHAR(50);

ALTER TABLE policy.data_treatment_rules
    ADD COLUMN IF NOT EXISTS policy_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS policy_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS law_ref VARCHAR(255),
    ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(50) NOT NULL DEFAULT 'UNSCOPED',
    ADD COLUMN IF NOT EXISTS country VARCHAR(50);

UPDATE policy.compliance_rules SET
    policy_id = 'POL-IFRS-15', policy_name = 'IFRS 15 / SOX 404',
    jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id = 'COMP-TRIP-REV-01';

UPDATE policy.compliance_rules SET
    policy_id = 'POL-VN-LAW91', policy_name = 'Vietnam Personal Data Protection',
    jurisdiction = 'VN', country = NULL
WHERE rule_id IN ('COMP-TRIP-GEO-02', 'COMP-CUST-PHONE-03');

UPDATE policy.compliance_rules SET
    policy_id = 'POL-INTERNAL-PRIVACY', policy_name = 'Internal privacy control',
    law_ref = 'Internal privacy control', jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id = 'COMP-FEEDBACK-PII-04';

UPDATE policy.compliance_rules SET
    policy_id = 'POL-EV-SAFETY', policy_name = 'EV Safety Standard',
    jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id IN ('COMP-TEL-BMS-05', 'COMP-CHG-KW-06');

UPDATE policy.data_treatment_rules SET
    policy_id = 'POL-VN-LAW91',
    policy_name = 'Vietnam Personal Data Protection',
    law_ref = 'Law 91/2025/QH15 and Decree 356/2025/ND-CP',
    jurisdiction = 'VN', country = NULL
WHERE rule_id = 'TREAT-TRIP-PHONE';

UPDATE policy.data_treatment_rules SET
    policy_id = 'POL-IFRS-15', policy_name = 'IFRS 15 / SOX 404',
    law_ref = 'IFRS 15 / SOX 404', jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id = 'TREAT-TRIP-FARE-ROUND';

UPDATE policy.data_treatment_rules SET
    policy_id = 'POL-INTERNAL-PRIVACY', policy_name = 'Internal privacy control',
    law_ref = 'Internal privacy control', jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id IN ('TREAT-CUST-EMAIL', 'TREAT-FEEDBACK-NAME', 'TREAT-DRV-PHONE');

-- Unknown legacy rules are fail-closed. They cannot become GLOBAL merely
-- because the old schema lacked jurisdiction metadata.
UPDATE policy.compliance_rules
SET jurisdiction = 'UNSCOPED'
WHERE policy_id IS NULL AND jurisdiction = 'GLOBAL';
UPDATE policy.data_treatment_rules
SET jurisdiction = 'UNSCOPED'
WHERE policy_id IS NULL AND jurisdiction = 'GLOBAL';

ALTER TABLE policy.compliance_rules ALTER COLUMN jurisdiction SET DEFAULT 'UNSCOPED';
ALTER TABLE policy.data_treatment_rules ALTER COLUMN jurisdiction SET DEFAULT 'UNSCOPED';

CREATE INDEX IF NOT EXISTS idx_policy_compliance_jurisdiction
    ON policy.compliance_rules(jurisdiction, country);
CREATE INDEX IF NOT EXISTS idx_policy_treatment_jurisdiction
    ON policy.data_treatment_rules(jurisdiction, country);

ALTER TABLE quarantine.records
    ADD COLUMN IF NOT EXISTS subject_zone VARCHAR(50) NOT NULL DEFAULT 'GLOBAL',
    ADD COLUMN IF NOT EXISTS country VARCHAR(50),
    ADD COLUMN IF NOT EXISTS jurisdiction_chain TEXT[] NOT NULL DEFAULT ARRAY['GLOBAL']::TEXT[],
    ADD COLUMN IF NOT EXISTS matched_policy_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS matched_policy_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS matched_law_ref VARCHAR(255),
    ADD COLUMN IF NOT EXISTS policy_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS applied_policy_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS policy_violations JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE quarantine.records
SET subject_zone = upper(trim(coalesce(
        nullif(raw_record_json->>'subject_zone', ''),
        nullif(raw_record_json->>'zone', ''),
        subject_zone,
        'GLOBAL'
    ))),
    country = nullif(upper(trim(coalesce(
        raw_record_json->>'country', raw_record_json->>'subject_jurisdiction', country, ''
    ))), '');

UPDATE quarantine.records
SET jurisdiction_chain = CASE
    WHEN subject_zone = 'GLOBAL' THEN ARRAY['GLOBAL']::TEXT[]
    WHEN country IS NULL OR country = subject_zone THEN ARRAY['GLOBAL', subject_zone]::TEXT[]
    ELSE ARRAY['GLOBAL', subject_zone, country]::TEXT[]
END;

CREATE INDEX IF NOT EXISTS idx_quarantine_records_jurisdiction
    ON quarantine.records(subject_zone, country);
CREATE INDEX IF NOT EXISTS idx_quarantine_records_policy
    ON quarantine.records(matched_policy_id);

ALTER TABLE audit.findings
    ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(50) NOT NULL DEFAULT 'GLOBAL',
    ADD COLUMN IF NOT EXISTS country VARCHAR(50),
    ADD COLUMN IF NOT EXISTS jurisdiction_chain TEXT[] NOT NULL DEFAULT ARRAY['GLOBAL']::TEXT[],
    ADD COLUMN IF NOT EXISTS policy_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS legacy_policy_snapshot JSONB;

-- Existing aggregated findings cannot be safely split without replaying their
-- run. Mark cross-zone legacy groups explicitly and let new runs use the
-- jurisdiction-aware identity implemented by the DAG.
WITH finding_zones AS (
    SELECT link.finding_id,
           CASE WHEN count(DISTINCT q.subject_zone) = 1 THEN min(q.subject_zone) ELSE 'MIXED' END AS zone,
           CASE WHEN count(DISTINCT q.country) = 1 THEN min(q.country) ELSE NULL END AS country
    FROM audit.finding_quarantine_records link
    JOIN quarantine.records q ON q.quarantine_id = link.quarantine_id
    GROUP BY link.finding_id
)
UPDATE audit.findings f
SET jurisdiction = z.zone,
    country = z.country,
    jurisdiction_chain = CASE
        WHEN z.zone = 'GLOBAL' THEN ARRAY['GLOBAL']::TEXT[]
        WHEN z.country IS NULL OR z.country = z.zone THEN ARRAY['GLOBAL', z.zone]::TEXT[]
        ELSE ARRAY['GLOBAL', z.zone, z.country]::TEXT[]
    END
FROM finding_zones z
WHERE z.finding_id = f.finding_id;

-- Legacy Findings did not persist the matched policy and therefore cannot be
-- assigned a trustworthy legal basis after the fact. Clear it instead of
-- retaining the former broad-join or LAW-91-GDPR fallback; replay creates
-- correctly split Findings with an immutable policy snapshot.
UPDATE audit.findings
SET legacy_policy_snapshot = jsonb_build_object(
        'policy_id', policy_id,
        'policy_name', policy_name,
        'law_ref', law_ref,
        'status', 'UNVERIFIED_LEGACY_ATTRIBUTION'
    )
WHERE policy_snapshot IS NULL AND legacy_policy_snapshot IS NULL
  AND (policy_id IS NOT NULL OR policy_name IS NOT NULL OR law_ref IS NOT NULL);

UPDATE audit.findings
SET policy_id = NULL, policy_name = NULL, law_ref = NULL
WHERE policy_snapshot IS NULL;

CREATE INDEX IF NOT EXISTS idx_findings_jurisdiction
    ON audit.findings(jurisdiction, country);
CREATE INDEX IF NOT EXISTS idx_findings_policy
    ON audit.findings(policy_id);

COMMIT;
