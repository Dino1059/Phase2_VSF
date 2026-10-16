-- =============================================================================
-- DataTrust OS × SoD Flow: Phase 2 Backend SoD & RBAC Schema Migration
-- Migration: migration_20261016_phase2_sod_schema.sql
-- Namespace: Schema "sod"
-- Dedicated Database Role: sod_app (Least Privilege)
-- =============================================================================

-- 1. TẠO ROLE DATABASE RIÊNG BIỆT CHO SOD BACKEND (Tách biệt hoàn toàn khỏi airflow)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
        CREATE ROLE sod_app WITH LOGIN PASSWORD 'sod_secure_password_phase2';
    END IF;
END $$;

-- 2. TẠO SCHEMA RIÊNG
CREATE SCHEMA IF NOT EXISTS sod;
GRANT USAGE ON SCHEMA sod TO sod_app;

-- 3. TẠO CÁC ENUM TYPE CHUẨN TRONG SCHEMA SOD
DO $$ BEGIN
    CREATE TYPE sod.ticket_kind AS ENUM ('access', 'offboard', 'rbac', 'bg');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE sod.ticket_status AS ENUM ('OPEN', 'DONE', 'REJECTED', 'RETURNED', 'CANCELLED');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE sod.step_action AS ENUM ('R', 'A', 'P');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE sod.step_status AS ENUM ('WAITING', 'CURRENT', 'DONE', 'REJECTED', 'RETURNED', 'SKIPPED');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE sod.decision_outcome AS ENUM ('SUBMIT', 'APPROVE', 'RETURN', 'REJECT', 'COMPLETE');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE sod.config_status AS ENUM ('PROPOSED', 'ACTIVE', 'REJECTED', 'SUPERSEDED', 'CANCELLED');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE sod.sla_level AS ENUM ('REMIND', 'OVERDUE', 'CRITICAL', 'STALE');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- 4. BẢNG VAI TRÒ (14 VAI TRÒ THEO KE_HOACH_SOD_DATATRUST.MD MỤC 2)
CREATE TABLE IF NOT EXISTS sod.roles (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    rank SMALLINT NOT NULL,
    kind VARCHAR(20) NOT NULL, -- 'both', 'sod_only', 'datatrust_only'
    description TEXT
);

-- 5. BẢNG NGƯỜI DÙNG HỢP NHẤT (DATATRUST & SOD FLOW)
CREATE TABLE IF NOT EXISTS sod.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,
    dept VARCHAR(200),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash VARCHAR(255),
    session_version INT NOT NULL DEFAULT 1, -- Chống Privilege Escalation: vô hiệu hóa token cũ khi đổi vai trò
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. BẢNG PHÂN BỔ VAI TRÒ CHO NGƯỜI DÙNG (MULTI-ROLE SUPPORT)
CREATE TABLE IF NOT EXISTS sod.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES sod.users(id) ON DELETE RESTRICT,
    role_code VARCHAR(20) NOT NULL REFERENCES sod.roles(code) ON DELETE RESTRICT,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    UNIQUE(user_id, role_code)
);
CREATE INDEX IF NOT EXISTS idx_sod_user_roles_lookup ON sod.user_roles(user_id, role_code);

-- 7. BẢNG QUẢN TRỊ PHIÊN BẢN CẤU HÌNH MA TRẬN RACIX (QUY TẮC 2 NGƯỜI: ADMIN ĐỀ XUẤT ≠ CISO DUYỆT)
CREATE TABLE IF NOT EXISTS sod.config_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq SERIAL UNIQUE,
    config JSONB NOT NULL,
    status sod.config_status NOT NULL DEFAULT 'PROPOSED',
    reason VARCHAR(1000) NOT NULL,
    base_seq INT,
    proposed_by UUID REFERENCES sod.users(id) ON DELETE RESTRICT,
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by UUID REFERENCES sod.users(id) ON DELETE RESTRICT,
    decided_at TIMESTAMPTZ,
    decision_note VARCHAR(1000),
    activated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sod_config_status ON sod.config_versions(status);

-- 8. BẢNG PHIẾU YÊU CẦU CẤP QUYỀN (TICKETS CÓ SNAPSHOT CONFIG_VERSION_ID)
CREATE TABLE IF NOT EXISTS sod.tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    seq INT NOT NULL,
    kind sod.ticket_kind NOT NULL DEFAULT 'access',
    status sod.ticket_status NOT NULL DEFAULT 'OPEN',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    level SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 3),
    pii BOOLEAN NOT NULL DEFAULT FALSE,
    break_glass BOOLEAN NOT NULL DEFAULT FALSE,

    -- Snapshot Phiên bản Ma trận lúc nộp phiếu (Bất biến trong suốt vòng đời ticket)
    config_version_id UUID NOT NULL REFERENCES sod.config_versions(id) ON DELETE RESTRICT,
    config_seq INT NOT NULL,

    -- Dữ liệu Form & Hàm băm tính toàn vẹn (Integrity Hash SHA-256)
    form JSONB NOT NULL,
    form_hash VARCHAR(64) NOT NULL,

    -- Snapshot chuỗi kiểm soát
    acts INT[] NOT NULL,
    phases JSONB NOT NULL,

    requester_id UUID NOT NULL REFERENCES sod.users(id) ON DELETE RESTRICT,
    active_step_id UUID,
    current_step_idx SMALLINT NOT NULL DEFAULT 1,
    total_steps SMALLINT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sod_tickets_requester ON sod.tickets(requester_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sod_tickets_status ON sod.tickets(status);
CREATE INDEX IF NOT EXISTS idx_sod_tickets_config ON sod.tickets(config_version_id);

-- 9. BẢNG CÁC BƯỚC DUYỆT TUẦN TỰ TRONG CHUỖI RACIX
CREATE TABLE IF NOT EXISTS sod.ticket_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES sod.tickets(id) ON DELETE RESTRICT,
    idx SMALLINT NOT NULL,
    phase SMALLINT NOT NULL,
    key VARCHAR(30) NOT NULL,
    role_code VARCHAR(20) NOT NULL REFERENCES sod.roles(code) ON DELETE RESTRICT,
    action sod.step_action NOT NULL,
    acts TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    assignee_id UUID REFERENCES sod.users(id) ON DELETE RESTRICT,
    sod_waived BOOLEAN NOT NULL DEFAULT FALSE,
    break_glass BOOLEAN NOT NULL DEFAULT FALSE,
    status sod.step_status NOT NULL DEFAULT 'WAITING',
    sla_hours DOUBLE PRECISION,
    started_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    UNIQUE(ticket_id, idx)
);
CREATE INDEX IF NOT EXISTS idx_sod_steps_assignee_status ON sod.ticket_steps(assignee_id, status);

-- 10. BẢNG QUYẾT ĐỊNH DUYỆT (APPEND-ONLY: BẤT BIẾN, CẤM SỬA/XÓA)
CREATE TABLE IF NOT EXISTS sod.step_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id UUID NOT NULL REFERENCES sod.ticket_steps(id) ON DELETE RESTRICT,
    actor_id UUID NOT NULL REFERENCES sod.users(id) ON DELETE RESTRICT,
    outcome sod.decision_outcome NOT NULL,
    comment VARCHAR(2000),
    form_hash VARCHAR(64) NOT NULL,
    rev INT NOT NULL DEFAULT 1,
    on_behalf_of UUID REFERENCES sod.users(id) ON DELETE RESTRICT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(step_id, rev)
);
CREATE INDEX IF NOT EXISTS idx_sod_decisions_actor ON sod.step_decisions(actor_id);

-- 11. BẢNG ỦY QUYỀN VẮNG MẶT CÓ THỜI HẠN (DELEGATIONS)
CREATE TABLE IF NOT EXISTS sod.delegations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delegator_id UUID NOT NULL REFERENCES sod.users(id) ON DELETE RESTRICT,
    delegate_id UUID NOT NULL REFERENCES sod.users(id) ON DELETE RESTRICT,
    role_code VARCHAR(20) NOT NULL REFERENCES sod.roles(code) ON DELETE RESTRICT,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NOT NULL,
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    CHECK (valid_to > valid_from),
    CHECK (delegator_id <> delegate_id)
);
CREATE INDEX IF NOT EXISTS idx_sod_delegations_lookup ON sod.delegations(delegate_id, role_code, valid_from, valid_to);

-- 12. BẢNG SỰ KIỆN THEO DÕI SLA CHẠY NỀN (CHỐNG TRÙNG LẶP)
CREATE TABLE IF NOT EXISTS sod.sla_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES sod.tickets(id) ON DELETE RESTRICT,
    step_id UUID NOT NULL REFERENCES sod.ticket_steps(id) ON DELETE RESTRICT,
    rev INT NOT NULL,
    level sod.sla_level NOT NULL,
    pct DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(step_id, rev, level)
);

-- 13. BẢNG THÔNG BÁO NỘI BỘ
CREATE TABLE IF NOT EXISTS sod.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES sod.users(id) ON DELETE CASCADE,
    ticket_id UUID REFERENCES sod.tickets(id) ON DELETE RESTRICT,
    kind VARCHAR(50) NOT NULL,
    level VARCHAR(10) NOT NULL,
    message VARCHAR(500) NOT NULL,
    dedupe_key VARCHAR(100) NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, dedupe_key)
);

-- 14. HÀM TỰ ĐỘNG SINH MÃ PHIẾU (ATOMIC TICKET CODE GENERATOR)
CREATE SEQUENCE IF NOT EXISTS sod.ticket_code_seq START WITH 91;

CREATE OR REPLACE FUNCTION sod.next_ticket_code() RETURNS VARCHAR AS $$
BEGIN
    RETURN 'TK-' || to_char(CURRENT_DATE, 'YYYY') || '-' || lpad(nextval('sod.ticket_code_seq')::text, 3, '0');
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 15. 5 DATABASE TRIGGERS BẢO VỆ SOD CẤP CSDL (DEFENSE-IN-DEPTH)
-- =============================================================================

-- TRIGGER 1: step_decision_guard
-- Kiểm tra lần cuối trước khi ghi quyết định:
-- Chặn tự duyệt (No Self-Approval), chặn 1 người kiêm 2 vai trò trên cùng phiếu, kiểm tra form_hash.
CREATE OR REPLACE FUNCTION sod.step_decision_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    s sod.ticket_steps%ROWTYPE;
    t sod.tickets%ROWTYPE;
    is_delegated BOOLEAN := FALSE;
BEGIN
    SELECT * INTO s FROM sod.ticket_steps WHERE id = NEW.step_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'SoD: bước duyệt không tồn tại';
    END IF;

    SELECT * INTO t FROM sod.tickets WHERE id = s.ticket_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'SoD: phiếu yêu cầu không tồn tại';
    END IF;

    IF t.status <> 'OPEN' THEN
        RAISE EXCEPTION 'SoD: ticket % đã đóng (trạng thái: %)', t.code, t.status;
    END IF;

    IF s.status <> 'CURRENT' THEN
        RAISE EXCEPTION 'SoD: bước % của ticket % chưa tới lượt hoặc đã xử lý (trạng thái: %)', s.idx, t.code, s.status;
    END IF;

    -- Kiểm tra người xử lý: đúng assignee hoặc có ủy quyền hợp lệ
    IF NEW.actor_id IS DISTINCT FROM s.assignee_id THEN
        -- Kiểm tra ủy quyền vắng mặt
        SELECT TRUE INTO is_delegated
        FROM sod.delegations
        WHERE delegator_id = s.assignee_id
          AND delegate_id = NEW.actor_id
          AND role_code = s.role_code
          AND valid_from <= now() AND valid_to > now()
          AND revoked_at IS NULL;

        IF NOT is_delegated THEN
            RAISE EXCEPTION 'SoD: người quyết định không phải người được giao bước này và không có ủy quyền hợp lệ';
        END IF;

        NEW.on_behalf_of := s.assignee_id;
    END IF;

    IF NEW.form_hash <> t.form_hash THEN
        RAISE EXCEPTION 'SoD: nội dung phiếu đã thay đổi (hash không khớp), cần xem lại trước khi quyết định';
    END IF;

    -- Kiểm tra vai trò của người quyết định
    IF NOT EXISTS (
        SELECT 1 FROM sod.user_roles r
        WHERE r.user_id = NEW.actor_id AND r.role_code = s.role_code
          AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
          AND r.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'SoD: người quyết định không có vai trò hiệu lực %', s.role_code;
    END IF;

    -- QUY TẮC SOD 1: CHỐNG TỰ DUYỆT (NO SELF-APPROVAL)
    -- Người yêu cầu không bao giờ được phép duyệt hoặc rà soát phiếu của chính mình
    IF s.idx > 0 AND NOT s.sod_waived THEN
        IF NEW.actor_id = t.requester_id AND NOT (s.action = 'P' AND s.role_code NOT IN ('IAM', 'OPS')) THEN
            RAISE EXCEPTION 'SoD: người yêu cầu không được tự duyệt hoặc rà soát ticket của mình';
        END IF;

        -- QUY TẮC SOD 2: MỘT NGƯỜI KHÔNG ĐƯỢC XỬ LÝ HAI VAI TRÒ KHÁC NHAU TRÊN CÙNG TICKET
        IF EXISTS (
            SELECT 1 FROM sod.step_decisions d
            JOIN sod.ticket_steps o ON o.id = d.step_id
            WHERE o.ticket_id = t.id AND o.idx > 0
              AND d.actor_id = NEW.actor_id
              AND o.role_code <> s.role_code
        ) THEN
            RAISE EXCEPTION 'SoD: người này đã xử lý một vai trò khác trên cùng ticket';
        END IF;
    END IF;

    NEW.decided_at := now();
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_step_decision_guard ON sod.step_decisions;
CREATE TRIGGER trg_step_decision_guard
    BEFORE INSERT ON sod.step_decisions
    FOR EACH ROW EXECUTE FUNCTION sod.step_decision_guard();

-- TRIGGER 2: ticket_step_guard
-- Cấm sửa định nghĩa bước; bước chỉ chuyển trạng thái khi đã có quyết định
CREATE OR REPLACE FUNCTION sod.ticket_step_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.ticket_id, NEW.idx, NEW.role_code, NEW.action, NEW.sod_waived)
       IS DISTINCT FROM (OLD.ticket_id, OLD.idx, OLD.role_code, OLD.action, OLD.sod_waived) THEN
        RAISE EXCEPTION 'SoD: không được sửa định nghĩa bước duyệt đã tạo';
    END IF;
    IF OLD.status IN ('DONE', 'REJECTED') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'SoD: bước đã kết thúc không được phép sửa đổi';
    END IF;
    IF NEW.status IN ('DONE', 'REJECTED')
       AND NOT EXISTS (SELECT 1 FROM sod.step_decisions WHERE step_id = NEW.id) THEN
        RAISE EXCEPTION 'SoD: bước chưa có bản ghi quyết định hợp lệ';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_ticket_step_guard ON sod.ticket_steps;
CREATE TRIGGER trg_ticket_step_guard
    BEFORE UPDATE ON sod.ticket_steps
    FOR EACH ROW EXECUTE FUNCTION sod.ticket_step_guard();

-- TRIGGER 3: ticket_guard
-- Nội dung phiếu bất biến sau khi nộp; phiếu đã đóng không mở lại
CREATE OR REPLACE FUNCTION sod.ticket_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.code, NEW.requester_id, NEW.form, NEW.form_hash, NEW.config_version_id, NEW.acts, NEW.phases)
       IS DISTINCT FROM (OLD.code, OLD.requester_id, OLD.form, OLD.form_hash, OLD.config_version_id, OLD.acts, OLD.phases) THEN
        RAISE EXCEPTION 'SoD: nội dung ticket và phiên bản cấu hình đã nộp không được sửa đổi';
    END IF;
    IF OLD.status <> 'OPEN' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'SoD: ticket đã đóng, không được phép thay đổi trạng thái';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_ticket_guard ON sod.tickets;
CREATE TRIGGER trg_ticket_guard
    BEFORE UPDATE ON sod.tickets
    FOR EACH ROW EXECUTE FUNCTION sod.ticket_guard();

-- TRIGGER 4: step_decisions_append_only
-- Bảng quyết định và sự kiện SLA là bất biến (Append-Only Enforcement)
CREATE OR REPLACE FUNCTION sod.forbid_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% là bảng bất biến chỉ được ghi thêm (% bị chặn)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;

DROP TRIGGER IF EXISTS trg_step_decisions_append_only ON sod.step_decisions;
CREATE TRIGGER trg_step_decisions_append_only
    BEFORE UPDATE OR DELETE ON sod.step_decisions
    FOR EACH ROW EXECUTE FUNCTION sod.forbid_change();

DROP TRIGGER IF EXISTS trg_sla_events_append_only ON sod.sla_events;
CREATE TRIGGER trg_sla_events_append_only
    BEFORE UPDATE OR DELETE ON sod.sla_events
    FOR EACH ROW EXECUTE FUNCTION sod.forbid_change();

-- TRIGGER 5: config_version_guard (Quy tắc 2 người: Admin đề xuất ≠ CISO duyệt)
CREATE OR REPLACE FUNCTION sod.config_version_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Chỉ cho phép cập nhật khi duyệt / từ chối phiên bản PROPOSED
        IF OLD.status <> 'PROPOSED' THEN
            RAISE EXCEPTION 'SoD: chỉ được quyết định trên phiên bản cấu hình đang chờ duyệt (PROPOSED)';
        END IF;

        IF NEW.status = 'ACTIVE' THEN
            -- QUY TẮC 2 NGƯỜI: Người đề xuất không được tự duyệt
            IF NEW.decided_by IS NOT DISTINCT FROM OLD.proposed_by THEN
                RAISE EXCEPTION 'SoD: vi phạm quy tắc 2 người: người đề xuất cấu hình không được tự duyệt';
            END IF;

            -- Người quyết định bắt buộc phải giữ vai trò CISO
            IF NOT EXISTS (
                SELECT 1 FROM sod.user_roles r
                WHERE r.user_id = NEW.decided_by AND r.role_code = 'CISO'
                  AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
                  AND r.revoked_at IS NULL
            ) THEN
                RAISE EXCEPTION 'SoD: chỉ người giữ vai trò CISO mới có thẩm quyền phê duyệt ma trận RACIX';
            END IF;

            -- Chuyển các phiên bản ACTIVE cũ thành SUPERSEDED
            UPDATE sod.config_versions SET status = 'SUPERSEDED' WHERE status = 'ACTIVE' AND id <> NEW.id;
            NEW.activated_at := now();
            NEW.decided_at := now();
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_config_version_guard ON sod.config_versions;
CREATE TRIGGER trg_config_version_guard
    BEFORE UPDATE ON sod.config_versions
    FOR EACH ROW EXECUTE FUNCTION sod.config_version_guard();

-- =============================================================================
-- 16. NẠP DỮ LIỆU CƠ BẢN: 14 VAI TRÒ & MA TRẬN PHIÊN BẢN 1 ACTIVE
-- =============================================================================

INSERT INTO sod.roles (code, name, rank, kind, description) VALUES
    ('ADMIN', 'Quản trị viên hệ thống', 10, 'both', 'Toàn quyền cấu hình hệ thống, đề xuất ma trận SoD (Maker)'),
    ('AUDITOR', 'Kiểm toán viên độc lập', 20, 'both', 'Rà soát kiểm soát độc lập (Auditor R), xuất bằng chứng SHA-256'),
    ('DPO', 'Bảo vệ dữ liệu cá nhân', 30, 'both', 'Phê duyệt các yêu cầu có PII và ngoại lệ bảo mật SoD'),
    ('SO', 'Chủ quản hệ thống & Dữ liệu', 40, 'both', 'Phê duyệt quyền truy cập ứng dụng/database do mình quản lý'),
    ('REQ', 'Người khởi tạo yêu cầu', 50, 'sod_only', 'Khởi tạo phiếu đề nghị cấp quyền hoặc thay đổi vai trò'),
    ('LM', 'Quản lý trực tiếp', 60, 'sod_only', 'Xác nhận nhu cầu công việc của nhân viên cấp dưới trực tiếp'),
    ('IAM', 'Quản trị định danh', 70, 'sod_only', 'Thực thi cấp/thu hồi tài khoản trên hệ thống IAM/PAM'),
    ('DEV', 'Lập trình viên phát triển', 80, 'sod_only', 'Phát triển mã nguồn; bị chặn quyền phát hành và deploy Prod'),
    ('REL', 'Quản lý phát hành', 90, 'sod_only', 'Phê duyệt phát hành phiên bản lên môi trường Production'),
    ('OPS', 'Vận hành hệ thống', 100, 'sod_only', 'Triển khai hạ tầng và release Prod sau khi có duyệt của Release Manager'),
    ('CISO', 'Giám đốc an toàn thông tin', 110, 'sod_only', 'Phê duyệt cấu hình ma trận RACIX (Checker), duyệt ngoại lệ Level 3'),
    ('DATA_STEWARD', 'Người bảo hộ dữ liệu', 120, 'datatrust_only', 'Duyệt Quality Rules, duyệt đề xuất khắc phục vi phạm'),
    ('ANALYST', 'Chuyên viên phân tích dữ liệu', 130, 'datatrust_only', 'Khảo sát dữ liệu, phân tích finding, đề xuất quy tắc'),
    ('VIEWER', 'Người xem báo cáo', 140, 'datatrust_only', 'Xem dashboard tổng quan, chỉ số KPI tuân thủ (Read-only)')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    rank = EXCLUDED.rank,
    kind = EXCLUDED.kind,
    description = EXCLUDED.description;

-- Nạp cấu hình ma trận mặc định ban đầu: seq = 1, status = 'ACTIVE'
INSERT INTO sod.config_versions (seq, config, status, reason, activated_at)
VALUES (
    1,
    jsonb_build_object(
        'version', '1.0.0-seed',
        'matrix', jsonb_build_array(
            '--X--C--A-P',  -- 0: Đề nghị cấp / thay đổi quyền
            '----R-A--P-',  -- 1: Phê duyệt cấp quyền thông thường
            '--R-C--A--P',  -- 2: Phê duyệt quyền có truy cập PII
            '---RC--A--P',  -- 3: Phê duyệt quyền đặc quyền hoặc quyền DB
            '--A-P------',  -- 4: Khởi tạo & phân quyền tài khoản
            '---P-A-----',  -- 5: Thu hồi quyền truy cập
            '--X--R--A-P',  -- 6: Yêu cầu thay đổi mã nguồn
            '--X-R--A-P-',  -- 7: Phê duyệt Merge Request vào main branch
            '---R-A-P---',  -- 8: Build & đóng gói bản phát hành
            '--X-R-A-P--',  -- 9: Phê duyệt phát hành (Release Approval)
            '----R-A-P--',  -- 10: Phê duyệt triển khai Production
            '---P-A-----',  -- 11: Triển khai hạ tầng Production
            '--P--A-----',  -- 12: Đăng ký & cấu hình ứng dụng mới
            '--R-A-P----',  -- 13: Cấp phát tài nguyên hệ thống
            '---P-A-----',  -- 14: Đóng tài nguyên hệ thống
            '--R-C--A--P',  -- 15: Phê duyệt ngoại lệ kiểm soát
            '---P-A-----',  -- 16: Kích hoạt quyền khẩn cấp (Break-glass)
            '--R-A-P----',  -- 17: Phê duyệt cấu hình ma trận phân quyền
            '---P-A-----'   -- 18: Rà soát định kỳ quyền truy cập
        )
    ),
    'ACTIVE',
    'Cấu hình ma trận RACIX ban đầu chuẩn ISO 27001 / SoD Governance',
    now()
)
ON CONFLICT (seq) DO NOTHING;

-- =============================================================================
-- 17. PHÂN QUYỀN TRUY CẬP CHO ROLE SOD_APP (LEAST PRIVILEGE)
-- =============================================================================
GRANT SELECT, INSERT, UPDATE ON sod.tickets, sod.ticket_steps, sod.delegations, sod.config_versions TO sod_app;
GRANT SELECT, INSERT ON sod.users, sod.roles, sod.user_roles, sod.step_decisions, sod.sla_events, sod.notifications TO sod_app;
GRANT USAGE, SELECT ON SEQUENCE sod.config_versions_seq_seq, sod.ticket_code_seq TO sod_app;

-- Tước bỏ triệt để quyền UPDATE / DELETE trên bảng quyết định để bảo đảm Append-Only
REVOKE UPDATE, DELETE ON sod.step_decisions, sod.sla_events FROM sod_app;
