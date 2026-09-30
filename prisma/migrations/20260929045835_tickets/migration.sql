-- Mã ticket SOD-YYYYMM-NNNN (cần có trước khi tạo bảng tickets vì dùng làm DEFAULT)
CREATE SEQUENCE "ticket_code_seq";
CREATE FUNCTION next_ticket_code() RETURNS TEXT
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public AS $$
  SELECT 'SOD-' || to_char(now() AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYYMM') || '-'
         || lpad(nextval('ticket_code_seq')::text, 4, '0')
$$;

-- CreateEnum
CREATE TYPE "ticket_status" AS ENUM ('OPEN', 'DONE', 'REJECTED');

-- CreateEnum
CREATE TYPE "step_status" AS ENUM ('WAITING', 'CURRENT', 'DONE', 'REJECTED');

-- CreateEnum
CREATE TYPE "step_action" AS ENUM ('P', 'R', 'A');

-- CreateEnum
CREATE TYPE "decision_outcome" AS ENUM ('SUBMIT', 'APPROVE', 'COMPLETE', 'REJECT');

-- CreateTable
CREATE TABLE "tickets" (
    "id" UUID NOT NULL,
    "code" VARCHAR(20) NOT NULL DEFAULT next_ticket_code(),
    "requester_id" UUID NOT NULL,
    "type_id" VARCHAR(20) NOT NULL,
    "title" VARCHAR(300) NOT NULL,
    "system" VARCHAR(500) NOT NULL,
    "priority" VARCHAR(10) NOT NULL,
    "level" SMALLINT NOT NULL,
    "pii" BOOLEAN NOT NULL,
    "break_glass" BOOLEAN NOT NULL,
    "acts" INTEGER[],
    "reasons" TEXT[],
    "phases" JSONB NOT NULL,
    "form" JSONB NOT NULL,
    "form_hash" VARCHAR(64) NOT NULL,
    "conflicts" TEXT[],
    "exception_id" VARCHAR(30),
    "status" "ticket_status" NOT NULL DEFAULT 'OPEN',
    "version" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "closed_at" TIMESTAMPTZ,

    CONSTRAINT "tickets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ticket_steps" (
    "id" UUID NOT NULL,
    "ticket_id" UUID NOT NULL,
    "idx" SMALLINT NOT NULL,
    "phase" SMALLINT NOT NULL,
    "key" VARCHAR(30) NOT NULL,
    "role_code" VARCHAR(10) NOT NULL,
    "action" "step_action" NOT NULL,
    "acts" TEXT[],
    "assignee_id" UUID,
    "sod_waived" BOOLEAN NOT NULL DEFAULT false,
    "break_glass" BOOLEAN NOT NULL DEFAULT false,
    "status" "step_status" NOT NULL DEFAULT 'WAITING',
    "sla_hours" DOUBLE PRECISION,
    "started_at" TIMESTAMPTZ,
    "due_at" TIMESTAMPTZ,

    CONSTRAINT "ticket_steps_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "step_decisions" (
    "id" UUID NOT NULL,
    "step_id" UUID NOT NULL,
    "actor_id" UUID NOT NULL,
    "outcome" "decision_outcome" NOT NULL,
    "comment" VARCHAR(2000),
    "form_hash" VARCHAR(64) NOT NULL,
    "decided_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "step_decisions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "tickets_code_key" ON "tickets"("code");

-- CreateIndex
CREATE UNIQUE INDEX "tickets_exception_id_key" ON "tickets"("exception_id");

-- CreateIndex
CREATE INDEX "tickets_requester_id_created_at_idx" ON "tickets"("requester_id", "created_at");

-- CreateIndex
CREATE INDEX "tickets_status_idx" ON "tickets"("status");

-- CreateIndex
CREATE INDEX "ticket_steps_assignee_id_status_idx" ON "ticket_steps"("assignee_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "ticket_steps_ticket_id_idx_key" ON "ticket_steps"("ticket_id", "idx");

-- CreateIndex
CREATE UNIQUE INDEX "step_decisions_step_id_key" ON "step_decisions"("step_id");

-- CreateIndex
CREATE INDEX "step_decisions_actor_id_idx" ON "step_decisions"("actor_id");

-- AddForeignKey
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_requester_id_fkey" FOREIGN KEY ("requester_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ticket_steps" ADD CONSTRAINT "ticket_steps_ticket_id_fkey" FOREIGN KEY ("ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ticket_steps" ADD CONSTRAINT "ticket_steps_role_code_fkey" FOREIGN KEY ("role_code") REFERENCES "roles"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ticket_steps" ADD CONSTRAINT "ticket_steps_assignee_id_fkey" FOREIGN KEY ("assignee_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "step_decisions" ADD CONSTRAINT "step_decisions_step_id_fkey" FOREIGN KEY ("step_id") REFERENCES "ticket_steps"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "step_decisions" ADD CONSTRAINT "step_decisions_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;


-- =====================================================================
-- Phần viết tay: chặn tự duyệt ngay trong DB (KE_HOACH.md 9.3.3)
-- Lỗi có tiền tố "SoD:" để ứng dụng nhận ra và báo lại cho người dùng.
-- =====================================================================

ALTER TABLE "tickets"
  ADD CONSTRAINT "tickets_priority_chk" CHECK (priority IN ('urgent', 'high', 'normal', 'low')),
  ADD CONSTRAINT "tickets_level_chk" CHECK (level BETWEEN 1 AND 3);

-- Quyết định trên một bước: kiểm lần cuối trước khi ghi
CREATE FUNCTION step_decision_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  s "ticket_steps"%ROWTYPE;
  t "tickets"%ROWTYPE;
BEGIN
  SELECT * INTO s FROM "ticket_steps" WHERE id = NEW.step_id;
  SELECT * INTO t FROM "tickets" WHERE id = s.ticket_id;

  IF t.status <> 'OPEN' THEN
    RAISE EXCEPTION 'SoD: ticket % đã đóng', t.code;
  END IF;
  IF s.status <> 'CURRENT' THEN
    RAISE EXCEPTION 'SoD: bước % của ticket % chưa tới lượt hoặc đã xử lý', s.idx, t.code;
  END IF;
  IF NEW.actor_id IS DISTINCT FROM s.assignee_id THEN
    RAISE EXCEPTION 'SoD: người quyết định không phải người được giao bước này';
  END IF;
  IF NEW.form_hash <> t.form_hash THEN
    RAISE EXCEPTION 'SoD: nội dung phiếu đã thay đổi, cần xem lại trước khi quyết định';
  END IF;
  IF (s.idx = 0) <> (NEW.outcome = 'SUBMIT')
     OR (NEW.outcome = 'APPROVE' AND s.action = 'P')
     OR (NEW.outcome = 'COMPLETE' AND s.action <> 'P') THEN
    RAISE EXCEPTION 'SoD: quyết định % không hợp lệ cho bước %', NEW.outcome, s.action;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM "user_roles" r
    WHERE r.user_id = NEW.actor_id AND r.role_code = s.role_code
      AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
  ) THEN
    RAISE EXCEPTION 'SoD: người quyết định không còn giữ vai trò %', s.role_code;
  END IF;

  IF s.idx > 0 AND NOT s.sod_waived THEN
    -- Requestor ↔ Approver: người yêu cầu chỉ được làm bước P không phải cấp quyền / triển khai
    IF NEW.actor_id = t.requester_id AND NOT (s.action = 'P' AND s.role_code NOT IN ('IAM', 'OPS')) THEN
      RAISE EXCEPTION 'SoD: người yêu cầu không được tự % ticket của mình', lower(s.action::text);
    END IF;
    -- Một người không được xử lý hai vai trò khác nhau trên cùng ticket (rule.md mục 4)
    IF EXISTS (
      SELECT 1 FROM "step_decisions" d JOIN "ticket_steps" o ON o.id = d.step_id
      WHERE o.ticket_id = t.id AND o.idx > 0 AND d.actor_id = NEW.actor_id AND o.role_code <> s.role_code
    ) THEN
      RAISE EXCEPTION 'SoD: người này đã xử lý một vai trò khác trên cùng ticket';
    END IF;
  END IF;

  NEW.decided_at := now();
  RETURN NEW;
END $$;

CREATE TRIGGER step_decision_guard
  BEFORE INSERT ON "step_decisions"
  FOR EACH ROW EXECUTE FUNCTION step_decision_guard();

-- Bước chỉ được chuyển sang Xong / Từ chối khi đã có quyết định; các trường gốc không được sửa
CREATE FUNCTION ticket_step_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.ticket_id, NEW.idx, NEW.role_code, NEW.action, NEW.sod_waived)
     IS DISTINCT FROM (OLD.ticket_id, OLD.idx, OLD.role_code, OLD.action, OLD.sod_waived) THEN
    RAISE EXCEPTION 'SoD: không được sửa định nghĩa bước';
  END IF;
  IF OLD.status IN ('DONE', 'REJECTED') AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'SoD: bước đã xử lý không được sửa';
  END IF;
  IF NEW.status IN ('DONE', 'REJECTED')
     AND NOT EXISTS (SELECT 1 FROM "step_decisions" WHERE step_id = NEW.id) THEN
    RAISE EXCEPTION 'SoD: bước chưa có quyết định';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER ticket_step_guard
  BEFORE UPDATE ON "ticket_steps"
  FOR EACH ROW EXECUTE FUNCTION ticket_step_guard();

-- Nội dung và người yêu cầu cố định sau khi gửi; ticket đã đóng không mở lại
CREATE FUNCTION ticket_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.code, NEW.requester_id, NEW.form, NEW.form_hash, NEW.type_id, NEW.acts, NEW.phases, NEW.exception_id)
     IS DISTINCT FROM (OLD.code, OLD.requester_id, OLD.form, OLD.form_hash, OLD.type_id, OLD.acts, OLD.phases, OLD.exception_id) THEN
    RAISE EXCEPTION 'SoD: nội dung ticket đã gửi không được sửa';
  END IF;
  IF OLD.status <> 'OPEN' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'SoD: ticket đã đóng';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER ticket_guard
  BEFORE UPDATE ON "tickets"
  FOR EACH ROW EXECUTE FUNCTION ticket_guard();

-- Quyết định: chỉ ghi thêm
CREATE FUNCTION forbid_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% chỉ được ghi thêm (% bị chặn)', TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER step_decisions_append_only
  BEFORE UPDATE OR DELETE ON "step_decisions"
  FOR EACH ROW EXECUTE FUNCTION forbid_change();

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT, UPDATE ON "tickets", "ticket_steps" TO sod_app;
    GRANT SELECT, INSERT ON "step_decisions" TO sod_app;
    GRANT EXECUTE ON FUNCTION next_ticket_code() TO sod_app;
  END IF;
END $$;
