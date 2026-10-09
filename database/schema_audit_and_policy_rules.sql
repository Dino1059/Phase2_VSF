-- =============================================================================
-- DataTrust OS: Audit Evidence Ledger & Policy Rules Schema
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- -----------------------------------------------------------------------------
-- 1. Schema: audit
-- Immutable audit ledger with hash-chain integrity
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.evidence (
    evidence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100) NOT NULL,
    dag_id VARCHAR(100) NOT NULL DEFAULT 'datatrust_adaptive_pipeline',
    dataset_id VARCHAR(100) NOT NULL,
    digital_signature VARCHAR(100) NOT NULL,
    evidence_hash VARCHAR(64) NOT NULL,
    previous_hash VARCHAR(64),
    scanned_count INT DEFAULT 0,
    silver_count INT DEFAULT 0,
    quarantine_count INT DEFAULT 0,
    warning_count INT DEFAULT 0,
    metrics JSONB NOT NULL DEFAULT '{}',
    evidence_payload JSONB NOT NULL DEFAULT '{}',
    jurisdiction_chain TEXT[],
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_evidence_run ON audit.evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_evidence_dataset ON audit.evidence(dataset_id);
CREATE INDEX IF NOT EXISTS idx_audit_evidence_created ON audit.evidence(created_at DESC);


-- -----------------------------------------------------------------------------
-- 2. Schema: policy
-- Source of Truth for Compliance Rules (Fixed) & Data Treatment Rules (Configurable)
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS policy;

CREATE TABLE IF NOT EXISTS policy.compliance_rules (
    rule_id VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    dataset_id VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    rule_name VARCHAR(200) NOT NULL,
    rule_code VARCHAR(100) NOT NULL,
    expression VARCHAR(500) NOT NULL,
    description TEXT,
    policy_id VARCHAR(100),
    policy_name VARCHAR(255),
    law_ref VARCHAR(200) NOT NULL,
    jurisdiction VARCHAR(50) NOT NULL DEFAULT 'UNSCOPED',
    country VARCHAR(50),
    rule_domain VARCHAR(20) NOT NULL DEFAULT 'LANE_B' CHECK (rule_domain = 'LANE_B'),
    severity VARCHAR(20) NOT NULL DEFAULT 'HIGH',
    on_fail_action VARCHAR(50) NOT NULL DEFAULT 'QUARANTINE'
        CHECK (on_fail_action IN ('BLOCK', 'QUARANTINE', 'QUARANTINE_HITL', 'WARNING', 'FINDING_ONLY')),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_APPROVAL'
        CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'RETIRED')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ,
    approved_by VARCHAR(200),
    approved_at TIMESTAMPTZ,
    approval_role VARCHAR(50),
    evaluation_phase VARCHAR(20) NOT NULL DEFAULT 'PRE_CHECK'
        CHECK (evaluation_phase IN ('PRE_CHECK', 'POST_CHECK')),
    condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_behavior VARCHAR(20) NOT NULL DEFAULT 'FAIL'
        CHECK (missing_behavior IN ('FAIL', 'WARNING', 'SKIP')),
    invalid_type_behavior VARCHAR(20) NOT NULL DEFAULT 'FAIL'
        CHECK (invalid_type_behavior IN ('FAIL', 'WARNING')),
    legal_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    runtime_mode VARCHAR(20) NOT NULL DEFAULT 'SHADOW'
        CHECK (runtime_mode IN ('SHADOW', 'ENFORCED')),
    is_fixed BOOLEAN DEFAULT TRUE,
    enforced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_id, version),
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    CHECK (jsonb_typeof(condition_json) = 'object'),
    CHECK (status <> 'ACTIVE' OR NOT legal_review_required OR
           (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approval_role IN ('LEGAL', 'DPO')))
);

CREATE TABLE IF NOT EXISTS policy.data_treatment_rules (
    rule_id VARCHAR(100) PRIMARY KEY,
    dataset_id VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    operation_id VARCHAR(50) NOT NULL,
    treatment_name VARCHAR(200) NOT NULL,
    params_json JSONB DEFAULT '{}',
    expression_display VARCHAR(500) NOT NULL,
    description TEXT,
    policy_id VARCHAR(100),
    policy_name VARCHAR(255),
    law_ref VARCHAR(255),
    jurisdiction VARCHAR(50) NOT NULL DEFAULT 'UNSCOPED',
    country VARCHAR(50),
    is_ai_proposed BOOLEAN DEFAULT FALSE,
    ai_rationale TEXT,
    ai_confidence NUMERIC(5,2),
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, pending, rejected, paused
    enforced_by VARCHAR(100) DEFAULT 'Admin',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_policy_treatment_ds ON policy.data_treatment_rules(dataset_id);
CREATE INDEX IF NOT EXISTS idx_policy_treatment_status ON policy.data_treatment_rules(status);
CREATE INDEX IF NOT EXISTS idx_policy_treatment_jurisdiction ON policy.data_treatment_rules(jurisdiction, country);
CREATE INDEX IF NOT EXISTS idx_policy_compliance_jurisdiction ON policy.compliance_rules(jurisdiction, country);
CREATE INDEX IF NOT EXISTS idx_policy_compliance_lookup
    ON policy.compliance_rules(dataset_id, jurisdiction, status, effective_from, effective_to);
DO $$ BEGIN
    ALTER TABLE policy.compliance_rules
        ADD CONSTRAINT compliance_rules_no_overlapping_active_versions
        EXCLUDE USING gist (
            rule_id WITH =, dataset_id WITH =, jurisdiction WITH =, (COALESCE(country, '')) WITH =,
            (tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)')) WITH &&
        ) WHERE (status = 'ACTIVE');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- -----------------------------------------------------------------------------
-- 3. Seed Compliance Check Rules (Read-Only / Fixed by Law & IPO Standards)
-- Legal Reference: Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP, IFRS 15, GDPR, CCPA
-- -----------------------------------------------------------------------------
INSERT INTO policy.compliance_rules 
(rule_id, version, dataset_id, column_name, rule_name, rule_code, expression, description, law_ref, severity, on_fail_action, is_fixed)
VALUES
(
    'COMP-TRIP-REV-01',
    1,
    'ride_hailing_xanh_sm_trips',
    'fare_amount',
    'Doanh thu cước chuyến đi không âm (IFRS 15)',
    'REV_POSITIVE_CHECK',
    'fare_amount > 0 AND trip_distance_km > 0',
    'Bắt buộc giá trị cước chuyến đi và khoảng cách di chuyển phải lớn hơn 0 để ghi nhận doanh thu kiểm toán IPO.',
    'Chuẩn mực Kế toán Quốc tế IFRS 15 / SOX 404',
    'CRITICAL',
    'QUARANTINE',
    TRUE
),
(
    'COMP-TRIP-GEO-02',
    1,
    'ride_hailing_xanh_sm_trips',
    'pickup_latitude',
    'Tọa độ điểm đón trong phạm vi cấp phép lãnh thổ',
    'GEO_TERRITORIAL_CHECK',
    '8.0 <= pickup_latitude <= 24.0 (VN) | 52.0 <= lat <= 53.5 (EU)',
    'Chuyến đi phải nằm trong phạm vi địa lý được cấp phép theo phân vùng thị trường.',
    'Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & Nghị định 356/2025/NĐ-CP',
    'CRITICAL',
    'QUARANTINE',
    TRUE
),
(
    'COMP-CUST-PHONE-03',
    1,
    'dim_customers',
    'customer_phone',
    'Bảo vệ dữ liệu số điện thoại cá nhân (PII)',
    'PII_PHONE_PROTECT_CHECK',
    'customer_phone IS NOT NULL AND length(customer_phone) >= 9',
    'Số điện thoại khách hàng phải được xử lý bảo vệ trước khi đưa vào vùng dữ liệu khai thác Silver.',
    'Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & Nghị định 356/2025/NĐ-CP',
    'HIGH',
    'QUARANTINE',
    TRUE
),
(
    'COMP-FEEDBACK-PII-04',
    1,
    'feedback_pii',
    'feedback_text',
    'Kiểm soát dữ liệu nhạy cảm trong phản hồi tự do',
    'UNSTRUCTURED_PII_CHECK',
    'feedback_text IS NOT NULL AND length(feedback_text) > 3',
    'Phản hồi khách hàng có chứa thông tin cá nhân cần được phân tách và che giấu.',
    'Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & GDPR Art. 5',
    'HIGH',
    'QUARANTINE',
    TRUE
),
(
    'COMP-TEL-BMS-05',
    1,
    'synthetic_ev_telemetry_ved_ref',
    'battery_temp_c',
    'Ngưỡng an toàn nhiệt độ cell pin BMS',
    'BMS_TEMP_SAFETY_CHECK',
    '-20.0 <= battery_temp_c <= 65.0',
    'Nhiệt độ khối pin EV phải nằm trong giới hạn an toàn vật lý của phương tiện.',
    'Quy chuẩn Kỹ thuật An toàn Pin Xe điện UN ECE R100',
    'CRITICAL',
    'QUARANTINE',
    TRUE
),
(
    'COMP-CHG-KW-06',
    1,
    'acn_charging_mapped',
    'power_kw',
    'Dung lượng và công suất trụ sạc không vượt trần',
    'CHARGER_POWER_CHECK',
    'power_kw >= 0.0 AND power_kw <= 350.0',
    'Công suất sạc thực tế ghi nhận từ trụ sạc V-GREEN không được âm và không vượt quá công suất thiết kế.',
    'Quy chuẩn Đo lường Năng lượng Trụ sạc V-GREEN',
    'HIGH',
    'QUARANTINE',
    TRUE
)
ON CONFLICT (rule_id, version) DO UPDATE SET
    rule_name = EXCLUDED.rule_name,
    expression = EXCLUDED.expression,
    description = EXCLUDED.description,
    law_ref = EXCLUDED.law_ref,
    severity = EXCLUDED.severity;

-- Jurisdiction and policy identity are explicit; legal bases are never inferred
-- later from a shared column name.
UPDATE policy.compliance_rules SET
    policy_id = 'POL-IFRS-15', policy_name = 'IFRS 15 / SOX 404',
    jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id = 'COMP-TRIP-REV-01';
UPDATE policy.compliance_rules SET
    policy_id = 'POL-VN-LAW91', policy_name = 'Luật Bảo vệ dữ liệu cá nhân Việt Nam',
    jurisdiction = 'VN', country = NULL
WHERE rule_id IN ('COMP-TRIP-GEO-02', 'COMP-CUST-PHONE-03');
UPDATE policy.compliance_rules SET
    policy_id = NULL, policy_name = 'Internal privacy control',
    law_ref = 'Internal privacy control', jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id = 'COMP-FEEDBACK-PII-04';
UPDATE policy.compliance_rules SET
    policy_id = 'POL-EV-SAFETY', policy_name = 'EV Safety Standard',
    jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id IN ('COMP-TEL-BMS-05', 'COMP-CHG-KW-06');

-- Executable structured conditions. Seed rules remain approval-gated and in
-- SHADOW until their owners approve the exact threshold and legal mapping.
UPDATE policy.compliance_rules SET
    condition_json = '{"operator":"range","field":"fare_amount","min":0.000001}'::jsonb,
    evaluation_phase = 'POST_CHECK', missing_behavior = 'FAIL',
    invalid_type_behavior = 'FAIL', legal_review_required = TRUE
WHERE rule_id = 'COMP-TRIP-REV-01' AND version = 1;
UPDATE policy.compliance_rules SET
    condition_json = '{"operator":"geofence","latitude_field":"pickup_latitude","longitude_field":"pickup_longitude","bounds":{"min_lat":8.0,"max_lat":24.0,"min_lon":102.0,"max_lon":110.0}}'::jsonb,
    evaluation_phase = 'PRE_CHECK', missing_behavior = 'FAIL',
    invalid_type_behavior = 'FAIL', legal_review_required = TRUE
WHERE rule_id = 'COMP-TRIP-GEO-02' AND version = 1;
UPDATE policy.compliance_rules SET
    condition_json = '{"operator":"masked","field":"customer_phone","pattern":".{2,}\\*+.{2,}"}'::jsonb,
    evaluation_phase = 'POST_CHECK', missing_behavior = 'FAIL',
    invalid_type_behavior = 'FAIL', legal_review_required = TRUE
WHERE rule_id = 'COMP-CUST-PHONE-03' AND version = 1;
UPDATE policy.compliance_rules SET
    condition_json = '{"operator":"regex","field":"feedback_text","pattern":"^(?!.*(?:[0-9]{9,}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,})).*$"}'::jsonb,
    evaluation_phase = 'POST_CHECK', missing_behavior = 'SKIP',
    invalid_type_behavior = 'WARNING'
WHERE rule_id = 'COMP-FEEDBACK-PII-04' AND version = 1;
UPDATE policy.compliance_rules SET
    condition_json = '{"operator":"range","field":"battery_temp_c","min":-20.0,"max":65.0}'::jsonb,
    evaluation_phase = 'POST_CHECK', missing_behavior = 'FAIL',
    invalid_type_behavior = 'FAIL'
WHERE rule_id = 'COMP-TEL-BMS-05' AND version = 1;
UPDATE policy.compliance_rules SET
    condition_json = '{"operator":"range","field":"power_kw","min":0.0,"max":350.0}'::jsonb,
    evaluation_phase = 'POST_CHECK', missing_behavior = 'FAIL',
    invalid_type_behavior = 'FAIL'
WHERE rule_id = 'COMP-CHG-KW-06' AND version = 1;

INSERT INTO policy.compliance_rules
(rule_id, version, dataset_id, column_name, rule_name, rule_code, expression,
 description, law_ref, jurisdiction, severity, on_fail_action, status,
 evaluation_phase, condition_json, missing_behavior, invalid_type_behavior,
 legal_review_required, runtime_mode)
VALUES
('COMP-TRIP-DIST-07', 1, 'ride_hailing_xanh_sm_trips', 'trip_distance_km',
 'Minimum billable trip distance', 'TRIP_DISTANCE_MIN', 'trip_distance_km >= 0.1',
 'Business threshold; explicit free/refund trip exceptions must be resolved before activation.',
 'Finance policy pending approval', 'GLOBAL', 'HIGH', 'QUARANTINE', 'PENDING_APPROVAL',
 'POST_CHECK', '{"operator":"range","field":"trip_distance_km","min":0.1}'::jsonb, 'FAIL', 'FAIL', FALSE, 'SHADOW'),
('COMP-CHG-METER-08', 1, 'acn_charging_mapped', 'meter_kwh_delta',
 'Meter to BMS relative delta', 'CHARGER_METER_DELTA', 'relative delta <= 3%',
 'Compares meter and BMS energy with an explicit zero-denominator failure.',
 'V-GREEN metering standard pending approval', 'GLOBAL', 'HIGH', 'QUARANTINE', 'PENDING_APPROVAL',
 'POST_CHECK', '{"operator":"relative_delta","left_field":"meter_kwh_delta","right_field":"bms_kwh_delta","denominator":"left","max":0.03}'::jsonb, 'FAIL', 'FAIL', FALSE, 'SHADOW'),
('COMP-FLEET-STATUS-09', 1, 'fleet_index', 'operating_status',
 'Allowed fleet operating status', 'FLEET_STATUS_ENUM', 'operating_status in approved values',
 'Rejects unknown fleet states.', 'Internal fleet policy', 'GLOBAL', 'MEDIUM', 'WARNING', 'PENDING_APPROVAL',
 'PRE_CHECK', '{"operator":"enum","field":"operating_status","values":["READY","IN_SERVICE","CHARGING"]}'::jsonb, 'FAIL', 'FAIL', FALSE, 'SHADOW'),
('COMP-PURPOSE-10', 1, '*', 'purpose_id', 'Purpose is required', 'PURPOSE_REQUIRED',
 'purpose_id IS NOT NULL', 'Foundation control for purpose limitation.',
 'Legal mapping pending review', 'GLOBAL', 'HIGH', 'QUARANTINE_HITL', 'PENDING_APPROVAL',
 'PRE_CHECK', '{"operator":"required","fields":["purpose_id"]}'::jsonb, 'FAIL', 'FAIL', TRUE, 'SHADOW'),
('COMP-DESTINATION-11', 1, '*', 'destination_id', 'Destination is required', 'DESTINATION_REQUIRED',
 'destination_id IS NOT NULL', 'Foundation control for destination and transfer evaluation.',
 'Legal mapping pending review', 'GLOBAL', 'HIGH', 'QUARANTINE_HITL', 'PENDING_APPROVAL',
 'PRE_CHECK', '{"operator":"required","fields":["destination_id"]}'::jsonb, 'FAIL', 'FAIL', TRUE, 'SHADOW'),
('COMP-FORBIDDEN-CREDENTIAL-12', 1, '*', 'password_hash', 'Forbidden credential material', 'FORBIDDEN_CREDENTIAL',
 'password_hash MUST NOT BE PRESENT', 'Blocks credential-bearing records from analytics zones.',
 'Security policy pending approval', 'GLOBAL', 'CRITICAL', 'BLOCK', 'PENDING_APPROVAL',
 'PRE_CHECK', '{"operator":"regex","field":"password_hash","pattern":"^$"}'::jsonb, 'SKIP', 'FAIL', FALSE, 'SHADOW')
ON CONFLICT (rule_id, version) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 4. Seed Data Treatment Rules (Configurable / Editable by Admin)
-- Operations: MASK, HASH, ROUND, GENERALIZE, REMOVE
-- -----------------------------------------------------------------------------
INSERT INTO policy.data_treatment_rules
(rule_id, dataset_id, column_name, operation_id, treatment_name, params_json, expression_display, description, is_ai_proposed, ai_rationale, ai_confidence, status, enforced_by)
VALUES
(
    'TREAT-TRIP-PHONE',
    'ride_hailing_xanh_sm_trips',
    'customer_phone',
    'MASK',
    'Che giấu số điện thoại khách hàng (Masking)',
    '{"prefix_len": 3, "suffix_len": 2, "mask_char": "*"}',
    'MASK(customer_phone, prefix=3, suffix=2)',
    'Giữ lại 3 chữ số đầu và 2 chữ số cuối của số điện thoại, phần giữa thay bằng dấu hoa thị.',
    FALSE,
    'Tuân thủ điều khoản bảo vệ dữ liệu cá nhân theo Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP',
    98.50,
    'active',
    'Trần Minh Hoàng (Auditor IPO)'
),
(
    'TREAT-CUST-EMAIL',
    'dim_customers',
    'customer_email',
    'MASK',
    'Ẩn địa chỉ email khách hàng (Email Masking)',
    '{"prefix_len": 1, "suffix_len": 4, "mask_char": "*"}',
    'MASK(customer_email, prefix=1, suffix=4)',
    'Rút gọn email chỉ hiển thị ký tự đầu và tên miền kết thúc.',
    FALSE,
    'Bảo mật thông tin liên lạc cá nhân',
    95.00,
    'active',
    'Nguyễn Quốc Bảo (Lead Platform)'
),
(
    'TREAT-TRIP-FARE-ROUND',
    'ride_hailing_xanh_sm_trips',
    'fare_amount',
    'ROUND',
    'Làm tròn giá trị cước kế toán (Financial Rounding)',
    '{"decimals": 0}',
    'ROUND(fare_amount, 0)',
    'Làm tròn doanh thu cước chuyến đi VND về số nguyên đồng chuẩn sổ cái kế toán.',
    FALSE,
    'Chuẩn hóa sổ cái tài chính theo quy định hạch toán',
    99.00,
    'active',
    'Admin'
),
(
    'TREAT-FEEDBACK-NAME',
    'feedback_pii',
    'customer_name',
    'REMOVE',
    'Khử định danh họ tên người dùng trong Feedback',
    '{}',
    'REMOVE(customer_name)',
    'Loại bỏ họ tên khách hàng, chuyển thành null để ngăn chặn truy vết ngược danh tính.',
    TRUE,
    'AI Agent phát hiện họ tên khách hàng cleartext trong bảng feedback',
    94.50,
    'active',
    'Admin'
),
(
    'TREAT-TEL-GPS-GENERALIZE',
    'synthetic_ev_telemetry_ved_ref',
    'latitude',
    'GENERALIZE',
    'Khái quát hóa tọa độ xe (Location Coarsening)',
    '{"decimals": 2}',
    'GENERALIZE(latitude, decimals=2)',
    'Làm tròn tọa độ GPS xuống 2 chữ số thập phân (~1.1 km) để bảo vệ quỹ đạo di chuyển người dùng.',
    TRUE,
    'AI đề xuất theo chuẩn GDPR Art. 5 và Luật 91/2025/QH15 cho telemetry vị trí xe',
    92.00,
    'pending',
    'AI Agent'
),
(
    'TREAT-DRV-PHONE',
    'dim_drivers',
    'driver_phone',
    'MASK',
    'Che giấu số điện thoại tài xế',
    '{"prefix_len": 3, "suffix_len": 2, "mask_char": "*"}',
    'MASK(driver_phone, prefix=3, suffix=2)',
    'Che số điện thoại tài xế chỉ giữ 3 số đầu và 2 số cuối.',
    FALSE,
    'Bảo vệ dữ liệu thông tin liên lạc tài xế',
    96.00,
    'active',
    'Admin'
)
ON CONFLICT (rule_id) DO UPDATE SET
    treatment_name = EXCLUDED.treatment_name,
    operation_id = EXCLUDED.operation_id,
    params_json = EXCLUDED.params_json,
    expression_display = EXCLUDED.expression_display,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

UPDATE policy.data_treatment_rules SET
    policy_id = 'POL-VN-LAW91', policy_name = 'Vietnam Personal Data Protection',
    law_ref = 'Law 91/2025/QH15 and Decree 356/2025/ND-CP',
    jurisdiction = 'VN', country = NULL
WHERE rule_id = 'TREAT-TRIP-PHONE';
UPDATE policy.data_treatment_rules SET
    policy_id = 'POL-IFRS-15', policy_name = 'IFRS 15 / SOX 404',
    law_ref = 'IFRS 15 / SOX 404', jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id = 'TREAT-TRIP-FARE-ROUND';
UPDATE policy.data_treatment_rules SET
    policy_id = NULL, policy_name = 'Internal privacy control',
    law_ref = 'Internal privacy control', jurisdiction = 'GLOBAL', country = NULL
WHERE rule_id IN ('TREAT-CUST-EMAIL', 'TREAT-FEEDBACK-NAME', 'TREAT-DRV-PHONE');
