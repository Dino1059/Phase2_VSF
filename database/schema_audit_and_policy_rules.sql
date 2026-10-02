-- =============================================================================
-- DataTrust OS: Audit Evidence Ledger & Policy Rules Schema
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

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
    rule_id VARCHAR(100) PRIMARY KEY,
    dataset_id VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    rule_name VARCHAR(200) NOT NULL,
    rule_code VARCHAR(100) NOT NULL,
    expression VARCHAR(500) NOT NULL,
    description TEXT,
    law_ref VARCHAR(200) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'HIGH',
    on_fail_action VARCHAR(50) NOT NULL DEFAULT 'QUARANTINE',
    is_fixed BOOLEAN DEFAULT TRUE,
    enforced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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


-- -----------------------------------------------------------------------------
-- 3. Seed Compliance Check Rules (Read-Only / Fixed by Law & IPO Standards)
-- Legal Reference: Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP, IFRS 15, GDPR, CCPA
-- -----------------------------------------------------------------------------
INSERT INTO policy.compliance_rules 
(rule_id, dataset_id, column_name, rule_name, rule_code, expression, description, law_ref, severity, on_fail_action, is_fixed)
VALUES
(
    'COMP-TRIP-REV-01',
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
ON CONFLICT (rule_id) DO UPDATE SET
    rule_name = EXCLUDED.rule_name,
    expression = EXCLUDED.expression,
    description = EXCLUDED.description,
    law_ref = EXCLUDED.law_ref,
    severity = EXCLUDED.severity;


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
