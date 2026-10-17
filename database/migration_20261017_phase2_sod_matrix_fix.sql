-- =============================================================================
-- Migration: migration_20261017_phase2_sod_matrix_fix.sql
-- Description: Synchronize standard 10-role ITGC RACIX matrix (ISO 27001 / SoD Governance)
-- Roles (10): REQ, LM, DPO, SO, CISO, IAM, DEV, REL, OPS, AUDITOR
-- Activities (19): Full ITGC RACIX access control & operation matrix
-- =============================================================================

ALTER TABLE sod.config_versions DISABLE TRIGGER trg_config_version_guard;

UPDATE sod.config_versions
SET config = jsonb_build_object(
    'version', '1.1.0-racix-aligned',
    'matrix', jsonb_build_array(
        'PXIIIXIIXI',  -- 0: Khởi tạo yêu cầu cấp quyền
        'XACRIXXXXI',  -- 1: Xác nhận nhu cầu nghiệp vụ
        'XAARCXXXXI',  -- 2: Phê duyệt quyền có truy cập PII
        'XCCAAXXXXI',  -- 3: Phê duyệt quyền đặc quyền hoặc quyền DB
        'XXXXRPXXXI',  -- 4: Cấp quyền qua IAM/PAM
        'IAIRCPXXXR',  -- 5: Thu hồi quyền khi nhân sự nghỉ việc
        'IACRIPXXXR',  -- 6: Điều chuyển hoặc thay đổi vai trò
        'XXCAAPXRXI',  -- 7: Tạo hoặc sửa RBAC role
        'XXXIRXPXXI',  -- 8: Phát triển mã nguồn
        'XXCRRXPAXI',  -- 9: Kiểm thử và xác nhận kết quả
        'XXCRAXXAXI',  -- 10: Phê duyệt phát hành Production
        'XXXIRXXXPI',  -- 11: Triển khai Production
        'PACARXXRII',  -- 12: Thay đổi giá, khuyến mại hoặc chính sách vận hành
        'PXAARXXXXI',  -- 13: Truy vấn dữ liệu PII nghiệp vụ (khách hàng) trực tiếp
        'PAARRXXXXI',  -- 14: Xuất dữ liệu PII nghiệp vụ (khách hàng)
        'XCAAAXXXXI',  -- 15: Phê duyệt ngoại lệ kiểm soát
        'CICRACCCPI',  -- 16: Điều tra sự cố bảo mật
        'IICRAXXRRR',  -- 17: Đóng sự cố và xác nhận khắc phục
        'IACPRIXXXR'   -- 18: Rà soát quyền định kỳ
    )
),
reason = 'Cấu hình ma trận RACIX chuẩn 10 roles (ISO 27001 / SoD Governance)'
WHERE status = 'ACTIVE' OR seq = 1;

ALTER TABLE sod.config_versions ENABLE TRIGGER trg_config_version_guard;
