-- CreateEnum
CREATE TYPE "notification_kind" AS ENUM ('TASK', 'SLA_REMIND', 'SLA_OVERDUE', 'STEP_DONE', 'REJECTED', 'DONE');

-- CreateTable
CREATE TABLE "notifications" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "ticket_id" UUID,
    "kind" "notification_kind" NOT NULL,
    "level" VARCHAR(10) NOT NULL,
    "message" VARCHAR(500) NOT NULL,
    "dedupe_key" VARCHAR(100) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "read_at" TIMESTAMPTZ,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "notifications_user_id_created_at_idx" ON "notifications"("user_id", "created_at");

-- CreateIndex
CREATE UNIQUE INDEX "notifications_user_id_dedupe_key_key" ON "notifications"("user_id", "dedupe_key");

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_ticket_id_fkey" FOREIGN KEY ("ticket_id") REFERENCES "tickets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Quyền ứng dụng: đọc, ghi thêm, và chỉ được sửa cột read_at (đánh dấu đã đọc)
ALTER TABLE "notifications"
  ADD CONSTRAINT "notifications_level_chk" CHECK (level IN ('info', 'warn', 'danger', 'ok'));

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sod_app') THEN
    GRANT SELECT, INSERT ON "notifications" TO sod_app;
    GRANT UPDATE (read_at) ON "notifications" TO sod_app;
  END IF;
END $$;
