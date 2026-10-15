import "server-only";
import { PgBoss } from "pg-boss";
import { flushDatatrustOutbox } from "./outbox";

const QUEUE = "datatrust-outbox";
let started: Promise<PgBoss | null> | null = null;

/**
 * Gửi lại các sự kiện còn nằm trong outbox mỗi phút (lỡ webhook, DataTrust vừa bật lại).
 * Gửi lần đầu được làm ngay sau khi quyết định commit (flushAfterCommit), worker chỉ lo phần thử lại.
 * Tắt bằng OUTBOX_WORKER=off.
 */
export function startOutboxWorker(): Promise<PgBoss | null> {
  if (process.env.OUTBOX_WORKER === "off") return Promise.resolve(null);
  started ??= (async () => {
    const url = process.env.DATABASE_URL;
    if (!url) return null;
    try {
      const boss = new PgBoss(url);
      boss.on("error", (e) => console.error("[outbox] pg-boss:", e));
      await boss.start();
      await boss.createQueue(QUEUE);
      await boss.schedule(QUEUE, "* * * * *");
      await boss.work(QUEUE, async () => {
        const { sent, failed } = await flushDatatrustOutbox();
        if (sent || failed) console.log(`[outbox] đã gửi ${sent}, lỗi ${failed}`);
      });
      console.log("[outbox] Worker gửi sự kiện đã chạy (mỗi phút).");
      return boss;
    } catch (e) {
      console.error("[outbox] Không khởi động được worker:", e);
      return null;
    }
  })();
  return started;
}
