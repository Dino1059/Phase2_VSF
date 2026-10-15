-- =============================================================================
-- Migration: Phase 2 Lane B Data-Driven Policy Rules
-- Description: Registers compliance rules for B05, B06, B07, B11, B12, B13, B14, B15, B16
-- Uses safe condition AST JSON operators (all, any, not, context_equals, date_age_days, is_null)
-- =============================================================================

BEGIN;

-- 1. B05: US CCPA GPS precision restriction (CTL-US-SPI-01)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-US-SPI-COORDS-V1', 1, '*', 'latitude',
     'US CCPA GPS precision restriction', 'CTL_US_SPI_01',
     'ops_dispatch OR precision(latitude, 2)',
     'US-CCPA-05: Toạ độ chính xác (>=3 số lẻ) dùng ngoài chức năng lõi của xe (ops_dispatch)',
     'POL-US-CCPA', 'California CCPA/CPRA technical controls',
     'US-CCPA-05', 'US', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2023-01-01T00:00:00Z', 'POST_CHECK',
     '{"operator":"any","conditions":[{"operator":"context_equals","key":"purpose_id","value":"ops_dispatch"},{"operator":"precision","field":"latitude","max_decimals":2}]}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-US-CA-PRIVACY-V1',
     'CLAUSE-US-CA-SENSITIVE-PI', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 2. B06: VN PDP location access role check (CTL-VN-PDP-002)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-VN-LOCATION-ROLE-V1', 1, 'synthetic_ev_telemetry_ved_ref', 'latitude',
     'VN PDP location access role check', 'CTL_VN_PDP_002',
     'context.role == "data_steward"',
     'PDP-002: Vai trò không được phép đọc cột vị trí (dữ liệu nhạy cảm ở VN)',
     'POL-VN-LAW91', 'Vietnam privacy technical controls',
     'PDP-002', 'VN', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2026-01-01T00:00:00Z', 'PRE_CHECK',
     '{"operator":"context_equals","key":"role","value":"data_steward"}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-VN-PRIVACY-V1',
     'CLAUSE-VN-PRIVACY-TECH', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 3. B07: EU GDPR fatigue score special category restriction (CTL-GDPR-009)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-EU-FATIGUE-CATALOG-V1', 1, 'synthetic_ev_telemetry_ved_ref', 'fatigue_score',
     'EU GDPR fatigue score health data restriction', 'CTL_GDPR_009',
     'fatigue_score IS NULL OR fatigue_score_tagged == true',
     'GDPR-009: Cột fatigue_score suy ra sức khoẻ tài xế chưa gắn nhãn dữ liệu đặc biệt',
     'POL-EU-GDPR', 'EU GDPR technical controls',
     'GDPR-009', 'EU', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2018-05-25T00:00:00Z', 'PRE_CHECK',
     '{"operator":"any","conditions":[{"operator":"is_null","field":"fatigue_score"},{"operator":"context_equals","key":"fatigue_score_tagged","value":true}]}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-EU-GDPR-V1',
     'CLAUSE-EU-GDPR-5-25-32', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 4. B11: VN PDP customer deletion request SLA 20 days (CTL-VN-PDP-005)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-VN-CUS-DELETE-SLA-V1', 1, 'dim_customers', 'delete_requested_at',
     'VN PDP customer deletion request SLA 20 days', 'CTL_VN_PDP_005',
     'delete_requested_at IS NULL OR delete_completed_at IS NOT NULL OR date_age_days(delete_requested_at) <= 20',
     'PDP-005: Yêu cầu xoá quá 20 ngày mà dữ liệu vẫn còn',
     'POL-VN-LAW91', 'Vietnam privacy technical controls',
     'PDP-005', 'VN', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2026-01-01T00:00:00Z', 'PRE_CHECK',
     '{"operator":"any","conditions":[{"operator":"is_null","field":"delete_requested_at"},{"operator":"not","condition":{"operator":"is_null","field":"delete_completed_at"}},{"operator":"date_age_days","field":"delete_requested_at","max_days":20}]}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-VN-PRIVACY-V1',
     'CLAUSE-VN-PRIVACY-TECH', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 5. B12: VN PDP consent withdrawn processing SLA 15 days (CTL-VN-PDP-003)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-VN-CUS-CONSENT-WITHDRAW-V1', 1, 'dim_customers', 'consent_withdrawn_at',
     'VN PDP consent withdrawn processing SLA 15 days', 'CTL_VN_PDP_003',
     'consent_withdrawn_at IS NULL OR date_age_days(consent_withdrawn_at) <= 15',
     'PDP-003: Rút đồng ý quá 15 ngày mà vẫn xử lý',
     'POL-VN-LAW91', 'Vietnam privacy technical controls',
     'PDP-003', 'VN', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2026-01-01T00:00:00Z', 'PRE_CHECK',
     '{"operator":"any","conditions":[{"operator":"is_null","field":"consent_withdrawn_at"},{"operator":"date_age_days","field":"consent_withdrawn_at","max_days":15}]}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-VN-PRIVACY-V1',
     'CLAUSE-VN-PRIVACY-TECH', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 6. B13: VN PDP customer consent record required (CTL-VN-PDP-006)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-VN-CUS-CONSENT-REQUIRED-V1', 1, 'dim_customers', 'consent_at',
     'VN PDP customer consent record required', 'CTL_VN_PDP_006',
     'consent_at IS NOT NULL',
     'PDP-006: Khách có dữ liệu nhưng không có bản ghi đồng ý',
     'POL-VN-LAW91', 'Vietnam privacy technical controls',
     'PDP-006', 'VN', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2026-01-01T00:00:00Z', 'PRE_CHECK',
     '{"operator":"not","condition":{"operator":"is_null","field":"consent_at"}}'::jsonb,
     'FAIL', 'FAIL', FALSE, 'ENFORCED', 'PACK-VN-PRIVACY-V1',
     'CLAUSE-VN-PRIVACY-TECH', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 7. B14: US CCPA opt-out marketing restriction (CTL-US-OPTOUT-01)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-US-OPTOUT-MARKETING-V1', 1, 'ride_hailing_xanh_sm_trips', 'customer_id',
     'US CCPA opt-out marketing restriction', 'CTL_US_OPTOUT_01',
     'purpose != "marketing" OR exclude_opt_out == true OR opt_out_sharing != 1',
     'US-CCPA-04: Khách đã từ chối chia sẻ nằm trong dữ liệu dùng cho quảng cáo',
     'POL-US-CCPA', 'California CCPA/CPRA technical controls',
     'US-CCPA-04', 'US', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2023-01-01T00:00:00Z', 'PRE_CHECK',
     '{"operator":"any","conditions":[{"operator":"not","condition":{"operator":"context_equals","key":"purpose_id","value":"marketing"}},{"operator":"context_equals","key":"exclude_opt_out","value":true},{"operator":"not","condition":{"operator":"compare","field":"opt_out_sharing","comparator":"==","value":1}}]}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-US-CA-PRIVACY-V1',
     'CLAUSE-US-CA-SENSITIVE-PI', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 8. B15: EU GDPR driver processing valid legal basis (CTL-GDPR-006)
-- Note: QUARANTINE_HITL requires human remediation proposal (HITL gate)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-EU-DRV-LEGAL-BASIS-V1', 1, 'dim_drivers', 'legal_basis',
     'EU GDPR driver processing valid legal basis', 'CTL_GDPR_006',
     'legal_basis IN ("contract", "legitimate_interest")',
     'GDPR-006: Dữ liệu tài xế EU dùng căn cứ consent hoặc để trống vi phạm GDPR Art 6',
     'POL-EU-GDPR', 'EU GDPR technical controls',
     'GDPR-006', 'EU', NULL, 'HIGH',
     'QUARANTINE_HITL', 'ACTIVE', '2018-05-25T00:00:00Z', 'PRE_CHECK',
     '{"operator":"enum","field":"legal_basis","values":["contract","legitimate_interest"]}'::jsonb,
     'FAIL', 'FAIL', FALSE, 'ENFORCED', 'PACK-EU-GDPR-V1',
     'CLAUSE-EU-GDPR-5-25-32', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 9. B16: EU GDPR trip customer contact data minimization (CTL-GDPR-005)
INSERT INTO policy.compliance_rules
    (rule_id, version, dataset_id, column_name, rule_name, rule_code,
     expression, description, policy_id, policy_name, law_ref, jurisdiction,
     country, severity, on_fail_action, status, effective_from,
     evaluation_phase, condition_json, missing_behavior,
     invalid_type_behavior, legal_review_required, runtime_mode,
     pack_id, clause_id, control_kind)
VALUES
    ('COMP-EU-TRIP-MINIMIZATION-V1', 1, 'ride_hailing_xanh_sm_trips', 'customer_contact',
     'EU GDPR trip customer contact data minimization', 'CTL_GDPR_005',
     'purpose != "fleet_analytics" OR uses_customer_contact == false OR customer_contact IS NULL',
     'GDPR-005: Thu thập thừa, cột customer_contact không cần cho mục đích fleet_analytics',
     'POL-EU-GDPR', 'EU GDPR technical controls',
     'GDPR-005', 'EU', NULL, 'HIGH',
     'QUARANTINE', 'ACTIVE', '2018-05-25T00:00:00Z', 'PRE_CHECK',
     '{"operator":"any","conditions":[{"operator":"not","condition":{"operator":"context_equals","key":"purpose_id","value":"fleet_analytics"}},{"operator":"context_equals","key":"uses_customer_contact","value":false},{"operator":"is_null","field":"customer_contact"}]}'::jsonb,
     'SKIP', 'FAIL', FALSE, 'ENFORCED', 'PACK-EU-GDPR-V1',
     'CLAUSE-EU-GDPR-5-25-32', 'INTERNAL_IMPLEMENTATION_CONTROL')
ON CONFLICT (rule_id, version) DO UPDATE SET
    condition_json = EXCLUDED.condition_json,
    evaluation_phase = EXCLUDED.evaluation_phase,
    on_fail_action = EXCLUDED.on_fail_action,
    status = EXCLUDED.status;

-- 10. Treatments for telemetry coordinates generalization (US-CA)
INSERT INTO policy.data_treatment_rules
    (rule_id, version, dataset_id, column_name, operation_id, treatment_name,
     params_json, expression_display, description, policy_id, policy_name,
     law_ref, jurisdiction, country, status, effective_from, runtime_mode,
     on_fail_action, priority, pack_id, clause_id, control_kind, enforced_by)
VALUES
    ('TREAT-USCA-TELEM-LAT', 1, 'synthetic_ev_telemetry_ved_ref', 'latitude',
     'round_decimal', 'USCA - Generalize telemetry latitude',
     '{"decimals":2}'::jsonb, 'round_decimal(latitude, 2)',
     'Reduces precise vehicle location resolution.', 'POL-US-CCPA',
     'California CCPA/CPRA technical controls', 'US-CCPA-05', 'US-CA', 'US-CA',
     'ACTIVE', '2023-01-01T00:00:00Z', 'ENFORCED', 'QUARANTINE', 50,
     'PACK-US-CA-PRIVACY-V1', 'CLAUSE-US-CA-SENSITIVE-PI',
     'INTERNAL_IMPLEMENTATION_CONTROL', 'POLICY_MIGRATION'),
    ('TREAT-USCA-TELEM-LON', 1, 'synthetic_ev_telemetry_ved_ref', 'longitude',
     'round_decimal', 'USCA - Generalize telemetry longitude',
     '{"decimals":2}'::jsonb, 'round_decimal(longitude, 2)',
     'Reduces precise vehicle location resolution.', 'POL-US-CCPA',
     'California CCPA/CPRA technical controls', 'US-CCPA-05', 'US-CA', 'US-CA',
     'ACTIVE', '2023-01-01T00:00:00Z', 'ENFORCED', 'QUARANTINE', 60,
     'PACK-US-CA-PRIVACY-V1', 'CLAUSE-US-CA-SENSITIVE-PI',
     'INTERNAL_IMPLEMENTATION_CONTROL', 'POLICY_MIGRATION')
ON CONFLICT (rule_id, version) DO UPDATE SET
    params_json = EXCLUDED.params_json,
    status = EXCLUDED.status;

COMMIT;
