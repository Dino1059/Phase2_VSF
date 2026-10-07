-- S1 bước 4: cấu hình SoD có phiên bản. Admin đề xuất, người khác giữ vai trò CISO duyệt thì mới có hiệu lực.
-- Ticket giữ phiên bản cấu hình lúc tạo (tickets.config_version_id). Phiên bản 1 = giá trị mặc định đang dùng trong code.

ALTER TYPE "notification_kind" ADD VALUE 'CONFIG';

CREATE TYPE "config_status" AS ENUM ('PROPOSED', 'ACTIVE', 'REJECTED', 'SUPERSEDED', 'CANCELLED');

CREATE TABLE "config_versions" (
    "id" UUID NOT NULL,
    "seq" SERIAL NOT NULL,
    "config" JSONB NOT NULL,
    "status" "config_status" NOT NULL DEFAULT 'PROPOSED',
    "reason" VARCHAR(1000) NOT NULL,
    "base_seq" INTEGER,
    "proposed_by" UUID,
    "proposed_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "decided_by" UUID,
    "decided_at" TIMESTAMPTZ,
    "decision_note" VARCHAR(1000),
    "activated_at" TIMESTAMPTZ,

    CONSTRAINT "config_versions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "config_versions_seq_key" ON "config_versions"("seq");
CREATE INDEX "config_versions_status_idx" ON "config_versions"("status");
-- Đúng một phiên bản đang hiệu lực
CREATE UNIQUE INDEX "config_versions_one_active" ON "config_versions"("status") WHERE "status" = 'ACTIVE';
ALTER TABLE "config_versions" ADD CONSTRAINT "config_versions_proposed_by_fkey" FOREIGN KEY ("proposed_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "config_versions" ADD CONSTRAINT "config_versions_decided_by_fkey" FOREIGN KEY ("decided_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Phiên bản 1: giá trị mặc định (do hệ thống, không có người đề xuất)
INSERT INTO "config_versions" ("id", "config", "status", "reason", "activated_at")
VALUES (gen_random_uuid(), '{"sla":{"P":8,"R":24,"A":24},"priority":{"urgent":0.25,"high":0.5,"normal":1,"low":2},"remindPct":75,"escalatePct":100,"criticalPct":200,"staleCloseDays":7,"delegationMaxDays":30,"matrix":["PXIIIXIIXI","XACRIXXXXI","XAARCXXXXI","XCCAAXXXXI","XXXXRPXXXI","IAIRCPXXXR","IACRIPXXXR","XXCAAPXRXI","XXXIRXPXXI","XXCRRXPAXI","XXCRAXXAXI","XXXIRXXXPI","PACARXXRPI","PXAARPXXXI","PAARRPXXXI","XCAAAXXXXI","CICRAPCCPI","IICRAXXRRA","IACRRPXXXA"]}'::jsonb, 'ACTIVE', 'Phiên bản đầu tiên: giá trị mặc định theo rule.md và KE_HOACH.md', now());

-- Ticket giữ phiên bản cấu hình lúc tạo
ALTER TABLE "tickets" ADD COLUMN "config_version_id" UUID;
UPDATE "tickets" SET "config_version_id" = (SELECT id FROM "config_versions" WHERE seq = 1);
ALTER TABLE "tickets" ALTER COLUMN "config_version_id" SET NOT NULL;
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_config_version_id_fkey" FOREIGN KEY ("config_version_id") REFERENCES "config_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE FUNCTION ticket_config_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.config_version_id IS DISTINCT FROM OLD.config_version_id THEN
    RAISE EXCEPTION 'SoD: phiên bản cấu hình của ticket không được đổi';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER ticket_config_guard
  BEFORE UPDATE ON "tickets"
  FOR EACH ROW EXECUTE FUNCTION ticket_config_guard();

-- Đề xuất ≠ duyệt. Admin đề xuất, CISO duyệt. Nội dung đã đề xuất không sửa được. Chỉ tài khoản ứng dụng bị ràng buộc.
CREATE FUNCTION config_version_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_user <> 'sod_app' THEN RETURN NEW; END IF;

  IF TG_OP = 'INSERT' THEN
    IF NEW.status <> 'PROPOSED' OR NEW.decided_by IS NOT NULL OR NEW.decided_at IS NOT NULL OR NEW.activated_at IS NOT NULL THEN
      RAISE EXCEPTION 'SoD: phiên bản cấu hình mới phải ở trạng thái đề xuất';
    END IF;
    IF NEW.proposed_by IS NULL OR NOT EXISTS (
      SELECT 1 FROM "user_roles" r
      WHERE r.user_id = NEW.proposed_by AND r.role_code = 'ADMIN' AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
    ) THEN
      RAISE EXCEPTION 'SoD: chỉ Quản trị SoD mới đề xuất đổi cấu hình';
    END IF;
    RETURN NEW;
  END IF;

  -- UPDATE
  IF (NEW.id, NEW.seq, NEW.config, NEW.reason, NEW.base_seq, NEW.proposed_by, NEW.proposed_at)
     IS DISTINCT FROM (OLD.id, OLD.seq, OLD.config, OLD.reason, OLD.base_seq, OLD.proposed_by, OLD.proposed_at) THEN
    RAISE EXCEPTION 'SoD: nội dung phiên bản cấu hình không được sửa';
  END IF;
  IF NEW.status = OLD.status THEN
    IF (NEW.decided_by, NEW.decided_at, NEW.decision_note, NEW.activated_at)
       IS DISTINCT FROM (OLD.decided_by, OLD.decided_at, OLD.decision_note, OLD.activated_at) THEN
      RAISE EXCEPTION 'SoD: phiên bản cấu hình đã có quyết định, không sửa';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD.status = 'PROPOSED' AND NEW.status IN ('ACTIVE', 'REJECTED') THEN
    IF NEW.decided_by IS NULL THEN
      RAISE EXCEPTION 'SoD: thiếu người duyệt';
    END IF;
    IF NEW.decided_by = OLD.proposed_by THEN
      RAISE EXCEPTION 'SoD: người đề xuất không được tự duyệt thay đổi cấu hình của mình';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM "user_roles" r
      WHERE r.user_id = NEW.decided_by AND r.role_code = 'CISO' AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
    ) THEN
      RAISE EXCEPTION 'SoD: chỉ CISO mới duyệt thay đổi cấu hình';
    END IF;
    IF NEW.status = 'ACTIVE' THEN
      NEW.activated_at := now();
      -- Phiên bản cũ tự chuyển sang SUPERSEDED (lệnh lồng, xem nhánh dưới)
      UPDATE "config_versions" SET status = 'SUPERSEDED' WHERE status = 'ACTIVE' AND id <> NEW.id;
    END IF;
    NEW.decided_at := now();
    RETURN NEW;
  END IF;
  IF OLD.status = 'PROPOSED' AND NEW.status = 'CANCELLED' THEN
    IF NEW.decided_by IS DISTINCT FROM OLD.proposed_by THEN
      RAISE EXCEPTION 'SoD: chỉ người đề xuất mới rút lại đề xuất';
    END IF;
    NEW.decided_at := now();
    RETURN NEW;
  END IF;
  -- Chỉ được thay thế phiên bản đang hiệu lực khi có phiên bản khác được duyệt (lệnh lồng trong trigger)
  IF OLD.status = 'ACTIVE' AND NEW.status = 'SUPERSEDED' AND pg_trigger_depth() > 1 THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'SoD: không chuyển được phiên bản cấu hình từ % sang %', OLD.status, NEW.status;
END $$;

CREATE TRIGGER config_version_guard
  BEFORE INSERT OR UPDATE ON "config_versions"
  FOR EACH ROW EXECUTE FUNCTION config_version_guard();

CREATE TRIGGER config_versions_no_delete
  BEFORE DELETE ON "config_versions"
  FOR EACH ROW EXECUTE FUNCTION forbid_change();

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT, UPDATE ON "config_versions" TO sod_app;
    GRANT USAGE ON SEQUENCE "config_versions_seq_seq" TO sod_app;
  END IF;
END $$;
