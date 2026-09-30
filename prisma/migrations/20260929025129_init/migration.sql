-- CreateEnum
CREATE TYPE "user_status" AS ENUM ('PENDING', 'ACTIVE', 'DISABLED');

-- CreateEnum
CREATE TYPE "code_purpose" AS ENUM ('REGISTER');

-- CreateTable
CREATE TABLE "roles" (
    "code" VARCHAR(10) NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "short_name" VARCHAR(30) NOT NULL,
    "description" TEXT,

    CONSTRAINT "roles_pkey" PRIMARY KEY ("code")
);

-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "username" VARCHAR(50) NOT NULL,
    "email" VARCHAR(254) NOT NULL,
    "full_name" VARCHAR(150) NOT NULL,
    "password_hash" TEXT NOT NULL,
    "status" "user_status" NOT NULL DEFAULT 'PENDING',
    "email_verified_at" TIMESTAMPTZ,
    "must_change_password" BOOLEAN NOT NULL DEFAULT false,
    "failed_login_count" INTEGER NOT NULL DEFAULT 0,
    "locked_until" TIMESTAMPTZ,
    "last_login_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "user_roles" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "role_code" VARCHAR(10) NOT NULL,
    "valid_from" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "valid_to" TIMESTAMPTZ,
    "granted_by" UUID,
    "note" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "user_roles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "verification_codes" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "purpose" "code_purpose" NOT NULL,
    "code_hash" VARCHAR(64) NOT NULL,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "consumed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "verification_codes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "token_hash" VARCHAR(64) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "revoked_at" TIMESTAMPTZ,
    "ip" VARCHAR(64),
    "user_agent" VARCHAR(512),

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audit_log" (
    "id" BIGINT NOT NULL DEFAULT 0,
    "occurred_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actor_user_id" UUID,
    "actor_email" VARCHAR(254),
    "action" VARCHAR(64) NOT NULL,
    "target_type" VARCHAR(32),
    "target_id" VARCHAR(64),
    "ip" VARCHAR(64),
    "user_agent" VARCHAR(512),
    "details" JSONB,
    "prev_hash" VARCHAR(64) NOT NULL DEFAULT '',
    "hash" VARCHAR(64) NOT NULL DEFAULT '',

    CONSTRAINT "audit_log_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_username_key" ON "users"("username");

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE INDEX "user_roles_user_id_role_code_idx" ON "user_roles"("user_id", "role_code");

-- CreateIndex
CREATE INDEX "verification_codes_user_id_purpose_created_at_idx" ON "verification_codes"("user_id", "purpose", "created_at");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_token_hash_key" ON "sessions"("token_hash");

-- CreateIndex
CREATE INDEX "sessions_user_id_idx" ON "sessions"("user_id");

-- CreateIndex
CREATE INDEX "audit_log_actor_user_id_occurred_at_idx" ON "audit_log"("actor_user_id", "occurred_at");

-- CreateIndex
CREATE INDEX "audit_log_action_occurred_at_idx" ON "audit_log"("action", "occurred_at");

-- CreateIndex
CREATE INDEX "audit_log_actor_email_occurred_at_idx" ON "audit_log"("actor_email", "occurred_at");

-- AddForeignKey
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_role_code_fkey" FOREIGN KEY ("role_code") REFERENCES "roles"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_granted_by_fkey" FOREIGN KEY ("granted_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "verification_codes" ADD CONSTRAINT "verification_codes_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- =====================================================================
-- Phần viết tay (Prisma không mô hình hoá được)
-- =====================================================================

-- Email / username luôn lưu chữ thường để đăng nhập không phân biệt hoa thường
ALTER TABLE "users"
  ADD CONSTRAINT "users_email_lower_chk"    CHECK (email = lower(email)),
  ADD CONSTRAINT "users_username_lower_chk" CHECK (username = lower(username)),
  ADD CONSTRAINT "users_username_format_chk" CHECK (username ~ '^[a-z0-9][a-z0-9._-]{2,49}$');

ALTER TABLE "user_roles"
  ADD CONSTRAINT "user_roles_valid_range_chk" CHECK (valid_to IS NULL OR valid_to > valid_from);

-- ---------------------------------------------------------------------
-- Nhật ký kiểm toán: chỉ ghi thêm, mỗi dòng giữ mã băm của dòng trước
-- (KE_HOACH.md mục 6.2)
-- ---------------------------------------------------------------------

-- Đầu chuỗi: một dòng duy nhất, khoá dòng này để ghi nhật ký tuần tự
CREATE TABLE "audit_chain_head" (
  "singleton" BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  "last_id"   BIGINT  NOT NULL,
  "last_hash" VARCHAR(64) NOT NULL
);
INSERT INTO "audit_chain_head" VALUES (TRUE, 0, repeat('0', 64));

-- Nội dung được băm của một dòng. Dùng chung cho trigger và hàm kiểm tra.
CREATE FUNCTION audit_log_payload(r "audit_log") RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
  SELECT concat_ws('|',
    r.id::text,
    to_char(r.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    coalesce(r.actor_user_id::text, ''),
    coalesce(r.actor_email, ''),
    r.action,
    coalesce(r.target_type, ''),
    coalesce(r.target_id, ''),
    coalesce(r.ip, ''),
    coalesce(r.user_agent, ''),
    coalesce(r.details::text, ''),
    r.prev_hash)
$$;

-- SECURITY DEFINER: ứng dụng không cần (và không có) quyền trên audit_chain_head
CREATE FUNCTION audit_log_chain() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  head "audit_chain_head"%ROWTYPE;
BEGIN
  SELECT * INTO head FROM "audit_chain_head" WHERE singleton FOR UPDATE;
  NEW.id          := head.last_id + 1;
  NEW.occurred_at := clock_timestamp();
  NEW.prev_hash   := head.last_hash;
  NEW.hash        := encode(sha256(convert_to(audit_log_payload(NEW), 'UTF8')), 'hex');
  UPDATE "audit_chain_head" SET last_id = NEW.id, last_hash = NEW.hash WHERE singleton;
  RETURN NEW;
END $$;

CREATE TRIGGER audit_log_chain
  BEFORE INSERT ON "audit_log"
  FOR EACH ROW EXECUTE FUNCTION audit_log_chain();

CREATE FUNCTION audit_log_readonly() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log chỉ được ghi thêm (% bị chặn)', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER audit_log_no_update_delete
  BEFORE UPDATE OR DELETE ON "audit_log"
  FOR EACH ROW EXECUTE FUNCTION audit_log_readonly();

CREATE TRIGGER audit_log_no_truncate
  BEFORE TRUNCATE ON "audit_log"
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_readonly();

-- Kiểm tra toàn vẹn chuỗi. Trả về các dòng bị sai (rỗng = nguyên vẹn).
CREATE FUNCTION audit_log_verify()
RETURNS TABLE (id BIGINT, problem TEXT)
LANGUAGE sql STABLE AS $$
  WITH chain AS (
    SELECT a.id, a.prev_hash, a.hash,
           encode(sha256(convert_to(audit_log_payload(a), 'UTF8')), 'hex') AS computed_hash,
           lag(a.hash) OVER (ORDER BY a.id) AS expected_prev,
           lag(a.id)   OVER (ORDER BY a.id) AS prev_id
    FROM "audit_log" a
  )
  SELECT c.id, CASE
      WHEN c.id <> coalesce(c.prev_id, 0) + 1 THEN 'thiếu dòng trước (id nhảy cóc)'
      WHEN c.prev_hash <> coalesce(c.expected_prev, repeat('0', 64)) THEN 'prev_hash không khớp dòng trước'
      ELSE 'hash không khớp nội dung'
    END
  FROM chain c
  WHERE c.id <> coalesce(c.prev_id, 0) + 1
     OR c.prev_hash <> coalesce(c.expected_prev, repeat('0', 64))
     OR c.hash <> c.computed_hash
  ORDER BY c.id
$$;

-- ---------------------------------------------------------------------
-- Quyền cho tài khoản ứng dụng (nếu có trong cụm Postgres này)
-- ---------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT USAGE ON SCHEMA public TO sod_app;
    GRANT SELECT ON "roles" TO sod_app;
    GRANT SELECT, INSERT, UPDATE ON "users", "user_roles" TO sod_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON "verification_codes", "sessions" TO sod_app;
    -- Nhật ký: chỉ đọc và ghi thêm
    GRANT SELECT, INSERT ON "audit_log" TO sod_app;
    GRANT EXECUTE ON FUNCTION audit_log_verify() TO sod_app;
  END IF;
END $$;
