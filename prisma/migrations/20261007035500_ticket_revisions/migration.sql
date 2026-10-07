-- S1 bước 1: trả lại / bổ sung (phiên bản nội dung) và huỷ phiếu.
-- Nội dung phiếu vẫn khoá sau khi gửi; chỉ đổi được khi phiếu đang ở trạng thái RETURNED và có bản ghi
-- ticket_revisions tương ứng. Quyết định gắn với phiên bản nội dung (rev) nên bước phải duyệt lại thì ghi quyết định mới.

-- AlterEnum
ALTER TYPE "ticket_status" ADD VALUE 'RETURNED';
ALTER TYPE "ticket_status" ADD VALUE 'CANCELLED';
ALTER TYPE "decision_outcome" ADD VALUE 'RETURN';
ALTER TYPE "notification_kind" ADD VALUE 'RETURNED';
ALTER TYPE "notification_kind" ADD VALUE 'CANCELLED';

-- AlterTable
ALTER TABLE "tickets" ADD COLUMN "rev" INTEGER NOT NULL DEFAULT 1;
ALTER TABLE "step_decisions" ADD COLUMN "rev" INTEGER NOT NULL DEFAULT 1;

-- CreateTable
CREATE TABLE "ticket_revisions" (
    "id" UUID NOT NULL,
    "ticket_id" UUID NOT NULL,
    "rev" INTEGER NOT NULL,
    "form" JSONB NOT NULL,
    "form_hash" VARCHAR(64) NOT NULL,
    "created_by" UUID NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ticket_revisions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "ticket_revisions_ticket_id_rev_key" ON "ticket_revisions"("ticket_id", "rev");
ALTER TABLE "ticket_revisions" ADD CONSTRAINT "ticket_revisions_ticket_id_fkey" FOREIGN KEY ("ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "ticket_revisions" ADD CONSTRAINT "ticket_revisions_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Phiên bản 1 của các phiếu đã có
INSERT INTO "ticket_revisions" ("id", "ticket_id", "rev", "form", "form_hash", "created_by", "created_at")
SELECT gen_random_uuid(), "id", 1, "form", "form_hash", "requester_id", "created_at" FROM "tickets";

CREATE TRIGGER ticket_revisions_append_only
  BEFORE UPDATE OR DELETE ON "ticket_revisions"
  FOR EACH ROW EXECUTE FUNCTION forbid_change();

-- Mỗi bước có tối đa một quyết định cho mỗi phiên bản nội dung
DROP INDEX "step_decisions_step_id_key";
CREATE UNIQUE INDEX "step_decisions_step_id_rev_key" ON "step_decisions"("step_id", "rev");

-- Quyết định trên một bước: kiểm lần cuối trước khi ghi
CREATE OR REPLACE FUNCTION step_decision_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  s "ticket_steps"%ROWTYPE;
  t "tickets"%ROWTYPE;
BEGIN
  SELECT * INTO s FROM "ticket_steps" WHERE id = NEW.step_id;
  SELECT * INTO t FROM "tickets" WHERE id = s.ticket_id;

  IF t.status = 'RETURNED' THEN
    RAISE EXCEPTION 'SoD: ticket % đang chờ người yêu cầu bổ sung', t.code;
  END IF;
  IF t.status <> 'OPEN' THEN
    RAISE EXCEPTION 'SoD: ticket % đã đóng', t.code;
  END IF;
  IF NEW.rev <> t.rev THEN
    RAISE EXCEPTION 'SoD: quyết định thuộc phiên bản nội dung cũ của ticket %', t.code;
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

-- Bước chỉ được chuyển sang Xong / Từ chối khi đã có quyết định thuộc phiên bản nội dung hiện tại.
-- Bước Xong chỉ được quay về Chờ / Đang xử lý khi ticket đã sang phiên bản nội dung mới (duyệt lại).
CREATE OR REPLACE FUNCTION ticket_step_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  t "tickets"%ROWTYPE;
BEGIN
  SELECT * INTO t FROM "tickets" WHERE id = NEW.ticket_id;
  IF (NEW.ticket_id, NEW.idx, NEW.role_code, NEW.action, NEW.sod_waived)
     IS DISTINCT FROM (OLD.ticket_id, OLD.idx, OLD.role_code, OLD.action, OLD.sod_waived) THEN
    RAISE EXCEPTION 'SoD: không được sửa định nghĩa bước';
  END IF;
  IF OLD.status IN ('DONE', 'REJECTED') AND NEW IS DISTINCT FROM OLD THEN
    IF NOT (
      OLD.status = 'DONE' AND OLD.idx > 0 AND NEW.status IN ('WAITING', 'CURRENT')
      AND t.status = 'OPEN'
      AND t.rev > COALESCE((SELECT max(d.rev) FROM "step_decisions" d WHERE d.step_id = OLD.id), 0)
    ) THEN
      RAISE EXCEPTION 'SoD: bước đã xử lý không được sửa';
    END IF;
  END IF;
  IF NEW.status IN ('DONE', 'REJECTED')
     AND NOT EXISTS (SELECT 1 FROM "step_decisions" WHERE step_id = NEW.id AND rev = t.rev) THEN
    RAISE EXCEPTION 'SoD: bước chưa có quyết định';
  END IF;
  RETURN NEW;
END $$;

-- Nội dung và người yêu cầu cố định sau khi gửi. Chỉ đổi nội dung khi RETURNED → OPEN kèm phiên bản mới.
-- Ticket đã đóng (Hoàn tất / Từ chối / Huỷ) không mở lại. Huỷ không được nếu đã tới bước thực hiện.
CREATE OR REPLACE FUNCTION ticket_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('DONE', 'REJECTED', 'CANCELLED') AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'SoD: ticket đã đóng';
  END IF;
  IF (NEW.code, NEW.requester_id, NEW.type_id, NEW.acts, NEW.phases, NEW.exception_id)
     IS DISTINCT FROM (OLD.code, OLD.requester_id, OLD.type_id, OLD.acts, OLD.phases, OLD.exception_id) THEN
    RAISE EXCEPTION 'SoD: nội dung ticket đã gửi không được sửa';
  END IF;
  IF (NEW.form, NEW.form_hash, NEW.rev) IS DISTINCT FROM (OLD.form, OLD.form_hash, OLD.rev) THEN
    IF NOT (
      OLD.status = 'RETURNED' AND NEW.status = 'OPEN' AND NEW.rev = OLD.rev + 1
      AND EXISTS (SELECT 1 FROM "ticket_revisions" r WHERE r.ticket_id = NEW.id AND r.rev = NEW.rev AND r.form_hash = NEW.form_hash)
    ) THEN
      RAISE EXCEPTION 'SoD: nội dung ticket đã gửi không được sửa';
    END IF;
  END IF;
  IF OLD.status = 'RETURNED' AND NEW.status IN ('DONE', 'REJECTED') THEN
    RAISE EXCEPTION 'SoD: ticket đang chờ bổ sung, chưa thể đóng';
  END IF;
  IF NEW.status = 'CANCELLED' AND OLD.status <> 'CANCELLED' AND EXISTS (
    SELECT 1 FROM "ticket_steps" s
    WHERE s.ticket_id = NEW.id AND s.idx > 0 AND s.action = 'P' AND s.status IN ('CURRENT', 'DONE')
  ) THEN
    RAISE EXCEPTION 'SoD: đã tới bước thực hiện, không huỷ được';
  END IF;
  RETURN NEW;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT ON "ticket_revisions" TO sod_app;
  END IF;
END $$;
