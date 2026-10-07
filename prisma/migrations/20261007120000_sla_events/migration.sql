-- S1 bước 5: SLA chạy nền. Mỗi mốc của một bước chỉ ghi nhận một lần (sla_events), và Admin đóng phiếu "hết hạn"
-- chỉ được khi bước hiện tại đã quá số ngày cấu hình không ai xử lý. Không có đường nào tự duyệt.

ALTER TYPE "ticket_status" ADD VALUE 'EXPIRED';
ALTER TYPE "notification_kind" ADD VALUE 'EXPIRED';

CREATE TYPE "sla_level" AS ENUM ('REMIND', 'OVERDUE', 'CRITICAL', 'STALE');

CREATE TABLE "sla_events" (
    "id" UUID NOT NULL,
    "ticket_id" UUID NOT NULL,
    "step_id" UUID NOT NULL,
    "rev" INTEGER NOT NULL,
    "level" "sla_level" NOT NULL,
    "pct" DOUBLE PRECISION NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sla_events_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "sla_events_step_id_rev_level_key" ON "sla_events"("step_id", "rev", "level");
CREATE INDEX "sla_events_ticket_id_idx" ON "sla_events"("ticket_id");
ALTER TABLE "sla_events" ADD CONSTRAINT "sla_events_ticket_id_fkey" FOREIGN KEY ("ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "sla_events" ADD CONSTRAINT "sla_events_step_id_fkey" FOREIGN KEY ("step_id") REFERENCES "ticket_steps"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE TRIGGER sla_events_append_only
  BEFORE UPDATE OR DELETE ON "sla_events"
  FOR EACH ROW EXECUTE FUNCTION forbid_change();

-- ticket_guard: thêm trạng thái EXPIRED. Chỉ phiếu đang xử lý (OPEN) mới đóng hết hạn được, và chỉ khi bước hiện tại
-- đã chờ từ staleCloseDays ngày trở lên theo cấu hình lúc tạo phiếu.
CREATE OR REPLACE FUNCTION ticket_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('DONE', 'REJECTED', 'CANCELLED', 'EXPIRED') AND NEW IS DISTINCT FROM OLD THEN
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
  IF NEW.status = 'EXPIRED' AND OLD.status <> 'EXPIRED' THEN
    IF OLD.status <> 'OPEN' THEN
      RAISE EXCEPTION 'SoD: chỉ phiếu đang xử lý mới đóng hết hạn được';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM "ticket_steps" s JOIN "config_versions" cv ON cv.id = NEW.config_version_id
      WHERE s.ticket_id = NEW.id AND s.status = 'CURRENT' AND s.idx > 0
        AND s.started_at <= now() - make_interval(days => (cv.config ->> 'staleCloseDays')::int)
    ) THEN
      RAISE EXCEPTION 'SoD: phiếu chưa đủ số ngày không ai xử lý để đóng hết hạn';
    END IF;
  END IF;
  RETURN NEW;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT ON "sla_events" TO sod_app;
  END IF;
END $$;
