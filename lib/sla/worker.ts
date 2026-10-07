import "server-only";
import { PgBoss } from "pg-boss";
import { processSla } from "./service";

const QUEUE = "sla-tick";
let started: Promise<PgBoss | null> | null = null;

/**
 * Chạy `processSla` mỗi phút bằng pg-boss (hàng đợi trên chính PostgreSQL, KE_HOACH.md 6.1).
 * pg-boss tạo schema `pgboss` nên kết nối bằng tài khoản chủ sở hữu (DATABASE_URL), không phải sod_app.
 * Tắt bằng SLA_WORKER=off. Lỗi khi khởi động chỉ được ghi log, không làm sập ứng dụng.
 */
export function startSlaWorker(): Promise<PgBoss | null> {
  if (process.env.SLA_WORKER === "off") return Promise.resolve(null);
  started ??= (async () => {
    const url = process.env.DATABASE_URL;
    if (!url) {
      console.warn("[sla] Thiếu DATABASE_URL, không chạy được SLA nền.");
      return null;
    }
    try {
      const boss = new PgBoss(url);
      boss.on("error", (e) => console.error("[sla] pg-boss:", e));
      await boss.start();
      await boss.createQueue(QUEUE);
      await boss.schedule(QUEUE, "* * * * *");
      await boss.work(QUEUE, async () => {
        const { events } = await processSla();
        if (events) console.log(`[sla] ${events} mốc SLA mới`);
      });
      console.log("[sla] SLA nền đã chạy (mỗi phút).");
      return boss;
    } catch (e) {
      console.error("[sla] Không khởi động được SLA nền:", e);
      return null;
    }
  })();
  return started;
}
