-- S1 bước 2: ủy quyền vắng mặt cho người cùng vai trò, có hạn. Quyết định của người được ủy quyền ghi "thay mặt".

ALTER TYPE "notification_kind" ADD VALUE 'DELEGATION';

CREATE TABLE "delegations" (
    "id" UUID NOT NULL,
    "delegator_id" UUID NOT NULL,
    "delegate_id" UUID NOT NULL,
    "role_code" VARCHAR(10) NOT NULL,
    "valid_from" TIMESTAMPTZ NOT NULL,
    "valid_to" TIMESTAMPTZ NOT NULL,
    "reason" VARCHAR(500) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revoked_at" TIMESTAMPTZ,

    CONSTRAINT "delegations_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "delegations_window_chk" CHECK (valid_to > valid_from),
    CONSTRAINT "delegations_self_chk" CHECK (delegator_id <> delegate_id)
);

CREATE INDEX "delegations_delegate_id_role_code_idx" ON "delegations"("delegate_id", "role_code");
CREATE INDEX "delegations_delegator_id_idx" ON "delegations"("delegator_id");
ALTER TABLE "delegations" ADD CONSTRAINT "delegations_delegator_id_fkey" FOREIGN KEY ("delegator_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "delegations" ADD CONSTRAINT "delegations_delegate_id_fkey" FOREIGN KEY ("delegate_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "delegations" ADD CONSTRAINT "delegations_role_code_fkey" FOREIGN KEY ("role_code") REFERENCES "roles"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "step_decisions" ADD COLUMN "on_behalf_of" UUID;
ALTER TABLE "step_decisions" ADD CONSTRAINT "step_decisions_on_behalf_of_fkey" FOREIGN KEY ("on_behalf_of") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Ủy quyền chỉ hợp lệ khi cả hai người đang giữ vai trò đó; chỉ cột revoked_at được đặt (một lần), mọi cột khác cố định
CREATE FUNCTION delegation_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NOT EXISTS (
      SELECT 1 FROM "user_roles" r
      WHERE r.user_id = NEW.delegator_id AND r.role_code = NEW.role_code
        AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
    ) THEN
      RAISE EXCEPTION 'SoD: người ủy quyền không giữ vai trò %', NEW.role_code;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM "user_roles" r
      WHERE r.user_id = NEW.delegate_id AND r.role_code = NEW.role_code
        AND r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())
    ) THEN
      RAISE EXCEPTION 'SoD: chỉ được ủy quyền cho người cùng vai trò %', NEW.role_code;
    END IF;
    NEW.revoked_at := NULL;
    RETURN NEW;
  END IF;
  -- UPDATE
  IF (NEW.id, NEW.delegator_id, NEW.delegate_id, NEW.role_code, NEW.valid_from, NEW.valid_to, NEW.reason, NEW.created_at)
     IS DISTINCT FROM (OLD.id, OLD.delegator_id, OLD.delegate_id, OLD.role_code, OLD.valid_from, OLD.valid_to, OLD.reason, OLD.created_at) THEN
    RAISE EXCEPTION 'SoD: ủy quyền không được sửa, chỉ được thu hồi';
  END IF;
  IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
    RAISE EXCEPTION 'SoD: ủy quyền đã thu hồi';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER delegation_guard
  BEFORE INSERT OR UPDATE ON "delegations"
  FOR EACH ROW EXECUTE FUNCTION delegation_guard();

CREATE TRIGGER delegations_no_delete
  BEFORE DELETE ON "delegations"
  FOR EACH ROW EXECUTE FUNCTION forbid_change();

-- Quyết định: người được giao, hoặc người được ủy quyền còn hiệu lực cho đúng vai trò của bước.
-- on_behalf_of do trigger điền, ứng dụng không chọn được.
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
    IF s.idx = 0 OR NOT EXISTS (
      SELECT 1 FROM "delegations" d
      WHERE d.delegator_id = s.assignee_id AND d.delegate_id = NEW.actor_id AND d.role_code = s.role_code
        AND d.revoked_at IS NULL AND d.valid_from <= now() AND d.valid_to > now()
    ) THEN
      RAISE EXCEPTION 'SoD: người quyết định không phải người được giao bước này';
    END IF;
    NEW.on_behalf_of := s.assignee_id;
  ELSE
    NEW.on_behalf_of := NULL;
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

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT ON "delegations" TO sod_app;
    GRANT UPDATE ("revoked_at") ON "delegations" TO sod_app;
  END IF;
END $$;
