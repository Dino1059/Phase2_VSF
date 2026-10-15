-- Seed parent policy rows referenced by executable rules and audit evidence.
-- Idempotent and safe for existing production databases.

BEGIN;

INSERT INTO policy.compliance_policies
    (policy_id, title, jurisdiction, legal_framework, version,
     raw_policy_text, effective_date, status)
VALUES
    (
        'POL-IFRS-15',
        'Quy Chuẩn Doanh Thu & Kiểm Soát Cuốc Xe IFRS 15 / SOX 404',
        'GLOBAL',
        'IFRS 15 Revenue Contracts & SOX 404',
        '1.0',
        'Quy chuẩn toàn cầu: cước phí cuốc xe (fare_amount) bắt buộc > 0 và cự ly di chuyển (trip_distance_km) >= 0.1km. Toàn bộ record vi phạm phải vào Quarantine giải trình.',
        DATE '2024-01-01',
        'active'
    ),
    (
        'POL-EV-SAFETY',
        'Quy Chuẩn An Toàn Vận Hành Pin Xe Điện VinFast IEC 62660-1',
        'GLOBAL',
        'IEC 62660-1 & VinFast Technical Standard',
        '1.0',
        'Quy chuẩn an toàn pin: Nhiệt độ pack pin (battery_temp_c) nằm trong dải an toàn [-10°C, 85°C], dung lượng pin (battery_soc) nằm trong khoảng [0%, 100%].',
        DATE '2024-01-01',
        'active'
    )
ON CONFLICT (policy_id) DO NOTHING;

INSERT INTO policy.policy_clauses
    (clause_id, policy_id, clause_number, requirement_summary,
     target_pii_roles, mandated_action)
VALUES
    (
        'C-REV-01',
        'POL-IFRS-15',
        'Section 404',
        'Kiểm toán cước phí và cự ly hợp lệ',
        ARRAY['NON_PERSONAL_REFERENCE']::catalog.pii_role_type[],
        'KEEP'
    ),
    (
        'C-EV-01',
        'POL-EV-SAFETY',
        'IEC 62660 Section 4',
        'Giám sát nhiệt độ pin an toàn',
        ARRAY['TECHNICAL_METADATA']::catalog.pii_role_type[],
        'KEEP'
    )
ON CONFLICT (clause_id) DO NOTHING;

COMMIT;
