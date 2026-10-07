-- S1 bước 3: vai trò chỉ được ghi vào user_roles khi phiếu RBAC đã hoàn tất (KE_HOACH.md 9.3.1 lớp 6).
-- Ràng buộc đặt trong DB: tài khoản ứng dụng (sod_app) không cấp / thu hồi vai trò được nếu không có phiếu hợp lệ,
-- và người được cấp không được tham gia xử lý phiếu của chính mình.

ALTER TYPE "notification_kind" ADD VALUE 'ROLE_CHANGED';

ALTER TABLE "user_roles" ADD COLUMN "ticket_id" UUID, ADD COLUMN "revoked_ticket_id" UUID;
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_ticket_id_fkey" FOREIGN KEY ("ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_revoked_ticket_id_fkey" FOREIGN KEY ("revoked_ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
-- Mỗi phiếu chỉ cấp một lần, và chỉ thu hồi một lần
CREATE UNIQUE INDEX "user_roles_ticket_id_key" ON "user_roles"("ticket_id") WHERE "ticket_id" IS NOT NULL;
CREATE UNIQUE INDEX "user_roles_revoked_ticket_id_key" ON "user_roles"("revoked_ticket_id") WHERE "revoked_ticket_id" IS NOT NULL;

-- Phiếu RBAC đã xong mọi bước (kể cả bước IAM thực hiện) cho đúng thao tác / người / vai trò. Trả về người thực hiện bước cuối.
CREATE FUNCTION rbac_ticket_executor(p_ticket uuid, p_op text, p_user uuid, p_role text) RETURNS uuid
LANGUAGE plpgsql STABLE AS $$
DECLARE
  t "tickets"%ROWTYPE;
  last_idx smallint;
  executor uuid;
BEGIN
  SELECT * INTO t FROM "tickets" WHERE id = p_ticket;
  IF NOT FOUND OR t.type_id <> 'rbac' OR t.status <> 'OPEN' THEN RETURN NULL; END IF;
  IF t.form ->> 'op' IS DISTINCT FROM p_op
     OR t.form ->> 'targetUserId' IS DISTINCT FROM p_user::text
     OR t.form ->> 'roleCode' IS DISTINCT FROM p_role THEN RETURN NULL; END IF;
  IF EXISTS (SELECT 1 FROM "ticket_steps" s WHERE s.ticket_id = t.id AND s.status <> 'DONE') THEN RETURN NULL; END IF;
  SELECT max(idx) INTO last_idx FROM "ticket_steps" WHERE ticket_id = t.id;
  SELECT d.actor_id INTO executor
  FROM "step_decisions" d JOIN "ticket_steps" s ON s.id = d.step_id
  WHERE s.ticket_id = t.id AND s.idx = last_idx AND d.rev = t.rev;
  RETURN executor;
END $$;

CREATE FUNCTION user_role_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  executor uuid;
BEGIN
  -- Chỉ áp cho tài khoản ứng dụng. Migration / seed chạy bằng tài khoản chủ sở hữu.
  IF current_user <> 'sod_app' THEN RETURN NEW; END IF;

  IF TG_OP = 'INSERT' THEN
    -- Mọi nhân viên tự có vai trò REQ khi xác nhận email (không cần phiếu)
    IF NEW.role_code = 'REQ' AND NEW.ticket_id IS NULL AND NEW.granted_by IS NULL AND NEW.revoked_ticket_id IS NULL THEN
      RETURN NEW;
    END IF;
    IF NEW.ticket_id IS NULL THEN
      RAISE EXCEPTION 'SoD: vai trò % chỉ được cấp qua phiếu RBAC đã hoàn tất', NEW.role_code;
    END IF;
    executor := rbac_ticket_executor(NEW.ticket_id, 'grant', NEW.user_id, NEW.role_code);
    IF executor IS NULL THEN
      RAISE EXCEPTION 'SoD: phiếu RBAC chưa hoàn tất hoặc không khớp người / vai trò được cấp';
    END IF;
    IF NEW.granted_by IS DISTINCT FROM executor THEN
      RAISE EXCEPTION 'SoD: người cấp vai trò phải là người thực hiện bước cuối của phiếu';
    END IF;
    IF NEW.granted_by = NEW.user_id THEN
      RAISE EXCEPTION 'SoD: người cấp vai trò không được cấp cho chính mình';
    END IF;
    RETURN NEW;
  END IF;

  -- UPDATE: chỉ được đặt valid_to (thu hồi) kèm phiếu thu hồi hợp lệ
  IF (NEW.id, NEW.user_id, NEW.role_code, NEW.valid_from, NEW.granted_by, NEW.note, NEW.created_at, NEW.ticket_id)
     IS DISTINCT FROM (OLD.id, OLD.user_id, OLD.role_code, OLD.valid_from, OLD.granted_by, OLD.note, OLD.created_at, OLD.ticket_id) THEN
    RAISE EXCEPTION 'SoD: không được sửa bản ghi vai trò';
  END IF;
  IF (NEW.valid_to, NEW.revoked_ticket_id) IS DISTINCT FROM (OLD.valid_to, OLD.revoked_ticket_id) THEN
    IF OLD.revoked_ticket_id IS NOT NULL THEN
      RAISE EXCEPTION 'SoD: vai trò đã được thu hồi';
    END IF;
    IF NEW.revoked_ticket_id IS NULL THEN
      RAISE EXCEPTION 'SoD: vai trò chỉ được thu hồi qua phiếu RBAC đã hoàn tất';
    END IF;
    executor := rbac_ticket_executor(NEW.revoked_ticket_id, 'revoke', NEW.user_id, NEW.role_code);
    IF executor IS NULL THEN
      RAISE EXCEPTION 'SoD: phiếu RBAC chưa hoàn tất hoặc không khớp người / vai trò bị thu hồi';
    END IF;
    IF executor = NEW.user_id THEN
      RAISE EXCEPTION 'SoD: người thu hồi vai trò không được là người bị thu hồi';
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER user_role_guard
  BEFORE INSERT OR UPDATE ON "user_roles"
  FOR EACH ROW EXECUTE FUNCTION user_role_guard();

-- Người được cấp / bị thu hồi vai trò không được xử lý phiếu RBAC của chính mình (bước 1 trở đi)
CREATE FUNCTION rbac_target_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  s "ticket_steps"%ROWTYPE;
  t "tickets"%ROWTYPE;
BEGIN
  SELECT * INTO s FROM "ticket_steps" WHERE id = NEW.step_id;
  IF s.idx = 0 THEN RETURN NEW; END IF;
  SELECT * INTO t FROM "tickets" WHERE id = s.ticket_id;
  IF t.type_id = 'rbac' AND t.form ->> 'targetUserId' = NEW.actor_id::text THEN
    RAISE EXCEPTION 'SoD: người được cấp vai trò không được xử lý phiếu RBAC của chính mình';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER rbac_target_guard
  BEFORE INSERT ON "step_decisions"
  FOR EACH ROW EXECUTE FUNCTION rbac_target_guard();

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT EXECUTE ON FUNCTION rbac_ticket_executor(uuid, text, uuid, text) TO sod_app;
  END IF;
END $$;
