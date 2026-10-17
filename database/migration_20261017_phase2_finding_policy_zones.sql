-- =============================================================================
-- Migration: migration_20261017_phase2_finding_policy_zones.sql
-- Description: Align policy_id, policy_name, and law_ref with subject jurisdiction/zone
-- VN -> POL-VN-LAW91 (Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP)
-- US -> POL-US-CCPA (US CCPA/CPRA Privacy Standard)
-- EU -> POL-EU-GDPR (EU General Data Protection Regulation)
-- =============================================================================

UPDATE audit.findings
SET 
    policy_id = CASE 
        WHEN UPPER(TRIM(jurisdiction)) = 'VN' THEN 'POL-VN-LAW91'
        WHEN UPPER(TRIM(jurisdiction)) = 'US' THEN 'POL-US-CCPA'
        ELSE 'POL-EU-GDPR'
    END,
    policy_name = CASE 
        WHEN UPPER(TRIM(jurisdiction)) = 'VN' THEN 'Vietnam Personal Data Protection (Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP)'
        WHEN UPPER(TRIM(jurisdiction)) = 'US' THEN 'US CCPA/CPRA Privacy Standard'
        ELSE 'EU General Data Protection Regulation (GDPR)'
    END,
    law_ref = CASE 
        WHEN UPPER(TRIM(jurisdiction)) = 'VN' THEN 'Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP'
        WHEN UPPER(TRIM(jurisdiction)) = 'US' THEN 'CCPA/CPRA § 1798.100 et seq.'
        ELSE 'GDPR Art. 5(1)(c) & Art. 25'
    END
WHERE policy_id IS NULL OR policy_id = '' OR policy_name IS NULL OR policy_name = '' OR (UPPER(TRIM(jurisdiction)) IN ('VN', 'US') AND policy_id = 'POL-EU-GDPR');
