-- Tích hợp DataTrust: sự kiện gửi sang hệ thống khác được ghi cùng transaction với quyết định duyệt (outbox).
-- Nếu hệ thống đích đang tắt, sự kiện nằm chờ và được gửi lại; không bao giờ mất, không bao giờ tự duyệt thay.

CREATE TABLE "integration_outbox" (
    "id" UUID NOT NULL,
    "ticket_id" UUID NOT NULL,
    "event_id" VARCHAR(100) NOT NULL,
    "target" VARCHAR(30) NOT NULL,
    "payload" JSONB NOT NULL,
    "status" VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "next_attempt_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "sent_at" TIMESTAMPTZ,
    "last_error" VARCHAR(500),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "integration_outbox_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "integration_outbox_status_check" CHECK ("status" IN ('PENDING', 'SENT', 'FAILED'))
);

CREATE UNIQUE INDEX "integration_outbox_event_id_key" ON "integration_outbox"("event_id");
CREATE INDEX "integration_outbox_status_next_attempt_at_idx" ON "integration_outbox"("status", "next_attempt_at");
CREATE INDEX "integration_outbox_ticket_id_idx" ON "integration_outbox"("ticket_id");
ALTER TABLE "integration_outbox" ADD CONSTRAINT "integration_outbox_ticket_id_fkey" FOREIGN KEY ("ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT, UPDATE ON "integration_outbox" TO sod_app;
  END IF;
END $$;
