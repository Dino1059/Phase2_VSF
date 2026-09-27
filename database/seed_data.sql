-- =============================================================================
-- DataTrust OS: Seed Data for Data Catalog, Policies, Operations & Dynamic Rules
-- =============================================================================

-- 1. SEED OPERATION REGISTRY
INSERT INTO engine.operation_registry (operation_id, operation_name, treatment_action, python_handler, parameter_schema, description)
VALUES
-- Treatment: REMOVE
('redact_null', 'Redact to NULL', 'REMOVE', 'handler_redact_null', '{}'::jsonb, 'Gán giá trị cột thành NULL để loại bỏ dữ liệu không cần thiết (Data Minimization)'),
('drop_column', 'Drop Column on Export', 'REMOVE', 'handler_drop_column', '{}'::jsonb, 'Xóa bỏ hoàn toàn trường dữ liệu khi chuyển dịch từ Bronze sang Silver'),

-- Treatment: PSEUDONYMIZE
('mask_phone', 'Mask Phone Number', 'PSEUDONYMIZE', 'handler_mask_phone', '{"prefix_len": 3, "suffix_len": 2, "mask_char": "*"}'::jsonb, 'Che mờ số điện thoại, giữ lại đầu số và đuôi số (ví dụ: 098***12)'),
('mask_email', 'Mask Email Address', 'PSEUDONYMIZE', 'handler_mask_email', '{"keep_domain": true, "mask_char": "*"}'::jsonb, 'Che mờ tên hộp thư email, giữ lại tên miền (ví dụ: n***@gmail.com)'),
('hash_sha256', 'Salted SHA-256 Hash', 'PSEUDONYMIZE', 'handler_hash_sha256', '{"salt": "gsm_global_salt_2026"}'::jsonb, 'Mã hóa một chiều bằng hàm băm SHA-256 kèm muối bảo mật (Salt)'),
('mask_name', 'Mask Customer Name', 'PSEUDONYMIZE', 'handler_mask_name', '{"keep_first": true, "mask_char": "*"}'::jsonb, 'Che mờ họ tên khách hàng, chỉ giữ lại họ và tên đệm (ví dụ: Nguyễn *** Bảo)'),

-- Treatment: KEEP_RESTRICTED
('column_encrypt_aes', 'AES-256 Column Encryption', 'KEEP_RESTRICTED', 'handler_encrypt_aes', '{"key_alias": "vault_finance_v1"}'::jsonb, 'Mã hóa cấp cột đối xứng chuẩn AES-256, chỉ giải mã cho quyền đặc biệt'),
('access_restricted_view', 'RBAC Restricted View', 'KEEP_RESTRICTED', 'handler_restricted_view', '{"allowed_roles": ["ADMIN"]}'::jsonb, 'Giữ nguyên nhưng áp đặt chính sách bảo mật RBAC, ghi log 100% truy vấn'),

-- Treatment: GENERALIZE
('round_decimal', 'Round Decimal Precision', 'GENERALIZE', 'handler_round_decimal', '{"decimals": 2}'::jsonb, 'Làm tròn số thập phân (ví dụ tọa độ GPS làm tròn 2 chữ số để chống theo dõi vị trí nhà)'),
('bucketize_range', 'Bucketize Numeric Range', 'GENERALIZE', 'handler_bucketize', '{"step": 10}'::jsonb, 'Gom cụm số liệu thành các khoảng/dải (ví dụ độ tuổi 20-30, 30-40)'),

-- Treatment: KEEP
('passthrough_check', 'Passthrough Validated', 'KEEP', 'handler_passthrough', '{}'::jsonb, 'Dữ liệu sạch được giữ nguyên vẹn đưa vào Silver sau khi pass quality'),
('range_check', 'Value Range Boundary Check', 'KEEP', 'handler_range_check', '{"min_val": 0, "max_val": null, "allow_zero": false}'::jsonb, 'Kiểm tra giá trị nằm trong ngưỡng hợp lệ (ví dụ cước phí > 0, nhiệt độ pin -10 đến 85)'),
('not_null', 'Not Null Integrity Check', 'KEEP', 'handler_not_null', '{}'::jsonb, 'Kiểm tra bắt buộc không được để trống (NULL hoặc rỗng)'),
('regex_match', 'Regular Expression Pattern Match', 'KEEP', 'handler_regex_match', '{"pattern": "^[A-Z0-9_-]+$"}'::jsonb, 'Kiểm tra chuỗi định dạng theo biểu thức chính quy (Regex)')
ON CONFLICT (operation_id) DO NOTHING;

-- 2. SEED DATA CATALOG: DATASETS
INSERT INTO catalog.datasets (dataset_id, name, title, domain, owner_dept, storage_table_bronze, storage_table_silver, description, retention_days)
VALUES
('trips', 'ride_hailing_trips', 'GSM Xanh SM Trips Global', 'trips', 'Khối Vận Hành GSM', 'bronze.trips_raw', 'silver.trips_clean', 'Hồ sơ dữ liệu cuốc xe taxi điện và bike điện GSM trên 24 quốc gia', 1825),
('customers', 'customer_profiles', 'Hồ Sơ Khách Hàng Xanh SM', 'customers', 'Bộ Phận Khách Hàng & CRM', 'bronze.customers_raw', 'silver.customers_clean', 'Thông tin định danh, tài khoản và lịch sử khách hàng', 3650),
('drivers', 'driver_registry', 'Hồ Sơ Tài Xế GSM Đối Tác', 'drivers', 'Phòng Quản Trị Tài Xế', 'bronze.drivers_raw', 'silver.drivers_clean', 'Hồ sơ pháp lý, bằng lái, số tài khoản và thông tin vận hành tài xế', 3650),
('charging', 'acn_vgreen_charging', 'V-GREEN Trạm Sạc Xe Điện', 'charging', 'Công Ty Trạm Sạc V-GREEN', 'bronze.charging_raw', 'silver.charging_clean', 'Phiên sạc xe điện, sản lượng điện tiêu thụ Modbus và thanh toán', 1825),
('telemetry', 'synthetic_ev_telemetry', 'VinFast EV Telematics VED', 'telemetry', 'Khối R&D Phần Mềm Xe Điện', 'bronze.telemetry_raw', 'silver.telemetry_clean', 'Dữ liệu telemetry cảm biến pin, điện áp cell, nhiệt độ pack xe điện', 730)
ON CONFLICT (dataset_id) DO NOTHING;

-- 3. SEED DATA CATALOG: COLUMNS (Covering all 6 PII Roles)
INSERT INTO catalog.columns (dataset_id, column_name, data_type, is_primary_key, is_nullable, is_personal_data, pii_role, default_treatment, semantic_tag, description)
VALUES
-- Trips dataset
('trips', 'trip_id', 'VARCHAR(50)', TRUE, FALSE, FALSE, 'NON_PERSONAL_REFERENCE', 'KEEP', 'identifier', 'Mã định danh cuốc xe duy nhất'),
('trips', 'driver_id', 'VARCHAR(50)', FALSE, FALSE, TRUE, 'LINKABLE_IDENTIFIER', 'PSEUDONYMIZE', 'driver_ref', 'Mã tài xế đối tác phụ trách cuốc xe'),
('trips', 'customer_id', 'VARCHAR(50)', FALSE, FALSE, TRUE, 'LINKABLE_IDENTIFIER', 'PSEUDONYMIZE', 'customer_ref', 'Mã khách hàng thực hiện chuyến đi'),
('trips', 'customer_phone', 'VARCHAR(50)', FALSE, TRUE, TRUE, 'DIRECT_IDENTIFIER', 'PSEUDONYMIZE', 'phone_number', 'Số điện thoại liên lạc của khách đặt xe'),
('trips', 'customer_name', 'VARCHAR(100)', FALSE, TRUE, TRUE, 'DIRECT_IDENTIFIER', 'PSEUDONYMIZE', 'person_name', 'Họ tên đầy đủ của hành khách'),
('trips', 'fare_amount', 'NUMERIC(12,2)', FALSE, FALSE, FALSE, 'NON_PERSONAL_REFERENCE', 'KEEP', 'financial_amount', 'Giá cước thanh toán của chuyến đi (VND/USD)'),
('trips', 'trip_distance_km', 'NUMERIC(8,2)', FALSE, FALSE, FALSE, 'NON_PERSONAL_REFERENCE', 'KEEP', 'distance_metric', 'Khoảng cách hành trình di chuyển thực tế'),
('trips', 'pickup_latitude', 'NUMERIC(9,6)', FALSE, FALSE, TRUE, 'CONTEXTUAL_PERSONAL_DATA', 'GENERALIZE', 'gps_coordinate', 'Vĩ độ điểm đón khách ban đầu'),
('trips', 'pickup_longitude', 'NUMERIC(9,6)', FALSE, FALSE, TRUE, 'CONTEXTUAL_PERSONAL_DATA', 'GENERALIZE', 'gps_coordinate', 'Kinh độ điểm đón khách ban đầu'),
('trips', 'trip_notes', 'TEXT', FALSE, TRUE, TRUE, 'AMBIGUOUS_UNSTRUCTURED_DATA', 'PSEUDONYMIZE', 'free_text_notes', 'Ghi chú tự do từ khách hoặc tài xế trong cuốc xe'),

-- Customers dataset
('customers', 'customer_id', 'VARCHAR(50)', TRUE, FALSE, TRUE, 'LINKABLE_IDENTIFIER', 'PSEUDONYMIZE', 'customer_pk', 'Khóa chính hồ sơ khách hàng'),
('customers', 'customer_name', 'VARCHAR(100)', FALSE, FALSE, TRUE, 'DIRECT_IDENTIFIER', 'PSEUDONYMIZE', 'person_name', 'Họ tên khách hàng đăng ký'),
('customers', 'customer_phone', 'VARCHAR(50)', FALSE, FALSE, TRUE, 'DIRECT_IDENTIFIER', 'PSEUDONYMIZE', 'phone_number', 'Số điện thoại đăng nhập ứng dụng'),
('customers', 'customer_email', 'VARCHAR(100)', FALSE, TRUE, TRUE, 'DIRECT_IDENTIFIER', 'PSEUDONYMIZE', 'email_address', 'Địa chỉ email nhận hóa đơn điện tử'),
('customers', 'national_id', 'VARCHAR(50)', FALSE, TRUE, TRUE, 'DIRECT_IDENTIFIER', 'REMOVE', 'id_card_number', 'Số CCCD/Hộ chiếu đăng ký (không lưu trữ bản rõ)'),

-- Telemetry dataset
('telemetry', 'device_id', 'VARCHAR(50)', FALSE, FALSE, FALSE, 'LINKABLE_IDENTIFIER', 'KEEP', 'device_uuid', 'Mã hộp đen Telematics trên xe điện'),
('telemetry', 'battery_soc', 'NUMERIC(5,2)', FALSE, FALSE, FALSE, 'TECHNICAL_METADATA', 'KEEP', 'telemetry_sensor', 'Phần trăm dung lượng pin xe điện (0-100%)'),
('telemetry', 'battery_temp_c', 'NUMERIC(5,2)', FALSE, FALSE, FALSE, 'TECHNICAL_METADATA', 'KEEP', 'telemetry_sensor', 'Nhiệt độ pack pin xe điện theo độ C'),
('telemetry', 'battery_voltage', 'NUMERIC(6,2)', FALSE, FALSE, FALSE, 'TECHNICAL_METADATA', 'KEEP', 'telemetry_sensor', 'Điện áp tổng bộ pin xe điện (V)'),
('telemetry', 'firmware_ver', 'VARCHAR(50)', FALSE, FALSE, FALSE, 'TECHNICAL_METADATA', 'KEEP', 'firmware_version', 'Phiên bản phần mềm điều khiển ECU xe')
ON CONFLICT (dataset_id, column_name) DO NOTHING;

-- 4. SEED COMPLIANCE POLICIES & CLAUSES
INSERT INTO policy.compliance_policies (policy_id, title, jurisdiction, legal_framework, version, raw_policy_text, effective_date, status)
VALUES
('POL-VN-ND13', 'Quy Chuẩn Bảo Vệ Dữ Liệu Cá Nhân Nghị Định 13/2023/NĐ-CP', 'VN', 'Nghị định 13/2023/NĐ-CP', '1.0', 
'Yêu cầu áp dụng các biện pháp kỹ thuật che giấu, mã hóa hoặc bí danh hóa (Pseudonymization) đối với toàn bộ dữ liệu cá nhân cơ bản (số điện thoại, CCCD, email) và dữ liệu vị trí GPS của công dân Việt Nam trước khi lưu trữ hoặc chuyển tiếp cho bên thứ ba.', 
'2023-07-01', 'active'),

('POL-EU-GDPR', 'EU General Data Protection Regulation (GDPR)', 'EU', 'GDPR Regulation (EU) 2016/679', '2.0',
'Điều 5 & 25 yêu cầu nguyên tắc Data Minimization (hạn chế tối đa thu thập dữ liệu không cần thiết), ẩn danh hóa hoặc bí danh hóa dữ liệu định danh trực tiếp và bảo đảm quyền riêng tư mặc định (Privacy by Design).',
'2018-05-25', 'active'),

('POL-IFRS-15', 'Chuẩn Mực Kiểm Toán Doanh Thu Vận Tải IFRS 15 / SOX 404', 'GLOBAL', 'IFRS 15 & SOX Section 404', '1.2',
'Bảo đảm tính toàn vẹn và hợp lệ của doanh thu: Giá cước cuốc xe (fare_amount) phải là số dương hợp lệ (> 0), quãng đường di chuyển (trip_distance_km) phải >= 0.1km. Toàn bộ chuyến đi vi phạm phải được đưa vào Quarantine để giải trình kiểm toán IPO.',
'2024-01-01', 'active')
ON CONFLICT (policy_id) DO NOTHING;

INSERT INTO policy.policy_clauses (clause_id, policy_id, clause_number, requirement_summary, target_pii_roles, mandated_action)
VALUES
('CLAUSE-ND13-17', 'POL-VN-ND13', 'Điều 17.2', 'Bắt buộc áp dụng biện pháp che mờ số điện thoại và email khách hàng', ARRAY['DIRECT_IDENTIFIER']::catalog.pii_role_type[], 'PSEUDONYMIZE'),
('CLAUSE-ND13-13', 'POL-VN-ND13', 'Điều 13', 'Hạn chế độ chính xác của dữ liệu vị trí GPS để bảo vệ đời sống riêng tư', ARRAY['CONTEXTUAL_PERSONAL_DATA']::catalog.pii_role_type[], 'GENERALIZE'),
('CLAUSE-GDPR-MIN', 'POL-EU-GDPR', 'Article 5(1)(c)', 'Loại bỏ hoàn toàn trường số thẻ định danh CCCD khỏi hồ sơ thông thường', ARRAY['DIRECT_IDENTIFIER']::catalog.pii_role_type[], 'REMOVE'),
('CLAUSE-IFRS-REV', 'POL-IFRS-15', 'Section 404.1', 'Kiểm tra cước phí và cự ly di chuyển dương hợp lệ trên từng chuyến đi', ARRAY['NON_PERSONAL_REFERENCE']::catalog.pii_role_type[], 'KEEP')
ON CONFLICT (clause_id) DO NOTHING;

-- 5. SEED ACTIVE RULES (Enforced by Admin Nguyễn Quốc Bảo)
INSERT INTO engine.field_process_configs (config_id, dataset_id, column_name, pii_role, treatment_action, operation_id, execution_phase, execution_order, params_json, expression_display, on_fail_action, severity, policy_id, law_ref, enforced_by, is_active, version)
VALUES
('ACT-TRIP-01', 'trips', 'fare_amount', 'NON_PERSONAL_REFERENCE', 'KEEP', 'range_check', 'post_check', 1, 
 '{"min_val": 0.01, "allow_zero": false}'::jsonb, 
 'fare_amount > 0 AND trip_distance_km >= 0.1', 'QUARANTINE', 'CRITICAL', 'POL-IFRS-15', 'IFRS 15 / SOX Section 404', 'Nguyễn Quốc Bảo (Lead Platform)', TRUE, 1),

('ACT-CUST-01', 'trips', 'customer_phone', 'DIRECT_IDENTIFIER', 'PSEUDONYMIZE', 'mask_phone', 'treatment', 2, 
 '{"prefix_len": 3, "suffix_len": 2, "mask_char": "*"}'::jsonb, 
 'mask_phone(customer_phone)', 'QUARANTINE', 'HIGH', 'POL-VN-ND13', 'Nghị định 13/2023/NĐ-CP Điều 17', 'Nguyễn Quốc Bảo (Lead Platform)', TRUE, 1),

('ACT-TRIP-GPS', 'trips', 'pickup_latitude', 'CONTEXTUAL_PERSONAL_DATA', 'GENERALIZE', 'round_decimal', 'treatment', 3, 
 '{"decimals": 2}'::jsonb, 
 'round_decimal(pickup_latitude, 2)', 'WARN', 'MEDIUM', 'POL-VN-ND13', 'Nghị định 13/2023/NĐ-CP Điều 13', 'Nguyễn Quốc Bảo (Lead Platform)', TRUE, 1),

('ACT-CUST-ID', 'customers', 'national_id', 'DIRECT_IDENTIFIER', 'REMOVE', 'redact_null', 'treatment', 4, 
 '{}'::jsonb, 
 'redact_null(national_id)', 'QUARANTINE', 'CRITICAL', 'POL-EU-GDPR', 'GDPR Article 5 Data Minimization', 'Nguyễn Quốc Bảo (Lead Platform)', TRUE, 1)
ON CONFLICT (config_id) DO NOTHING;

-- 6. SEED PROPOSED RULES (Generated by AI Agent, Awaiting Admin Approval - HITL)
INSERT INTO engine.proposed_rules (proposal_id, dataset_id, column_name, pii_role, treatment_action, operation_id, execution_phase, params_json, expression_display, rationale, domain, severity, confidence, law_ref, policy_id, status, simulated_pass_rows, simulated_quarantine_rows)
VALUES
('a0000001-0000-0000-0000-000000000001'::uuid, 'trips', 'trip_notes', 'AMBIGUOUS_UNSTRUCTURED_DATA', 'PSEUDONYMIZE', 'hash_sha256', 'treatment', 
 '{"salt": "gsm_notes_salt"}'::jsonb, 
 'hash_sha256(trip_notes)', 
 'AI phát hiện cột ghi chú tự do chứa số điện thoại cá nhân do khách hàng tự nhập, đề xuất bí danh hóa bảo vệ dữ liệu cá nhân theo NĐ13.', 
 'Privacy & Data Protection', 'HIGH', 0.945, 'Nghị định 13/2023/NĐ-CP', 'POL-VN-ND13', 'pending', 985, 15),

('a0000001-0000-0000-0000-000000000002'::uuid, 'telemetry', 'battery_temp_c', 'TECHNICAL_METADATA', 'KEEP', 'range_check', 'post_check', 
 '{"min_val": -10, "max_val": 85, "allow_zero": true}'::jsonb, 
 'battery_temp_c BETWEEN -10 AND 85', 
 'Quy chuẩn an toàn pin xe điện VinFast, phát hiện bất thường quá nhiệt (>85°C) để bảo vệ cell pin và hồ sơ an toàn IPO.', 
 'Data Quality', 'CRITICAL', 0.980, 'Quy chuẩn Kỹ thuật Pin EV VinFast 2024', 'POL-IFRS-15', 'pending', 10350, 32)
ON CONFLICT (proposal_id) DO NOTHING;

-- 7. SEED AUDIT TRAIL (Initial State Verification)
INSERT INTO audit.system_audit_trail (actor, actor_role, action_type, entity_type, entity_id, previous_state, new_state, record_hash, previous_hash)
VALUES
('Nguyễn Quốc Bảo', 'ADMIN', 'SYSTEM_BOOTSTRAP', 'SCHEMA', 'DATABASE_INIT', NULL, 
 '{"status": "INITIALIZED", "schemas": 7, "enforced_rules": 4}'::jsonb, 
 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'GENESIS_HASH_DATA_TRUST_OS');
