-- =============================================================================
-- DataTrust OS: Non-rule bootstrap data
-- =============================================================================
-- This file intentionally contains no catalog, policy, compliance, treatment,
-- or compatibility-rule seeds. Canonical Lane A and Lane B rules are created
-- and versioned by the schema/migration files executed by database/init_db.py.

-- Operation handlers referenced by the current treatment-rule migrations.
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
