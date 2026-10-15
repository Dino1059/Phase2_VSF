import "server-only";
import { PgBoss } from "pg-boss";
import { openQuarterlyReview } from "./review";

const QUEUE = "review-quarterly";
let started: Promise<PgBoss | null> | null = null;

/**
 * Mỗi ngày kiểm tra một lần và mở phiếu rà soát quyền của quý hiện tại nếu chưa có (openQuarterlyReview chống trùng).
 * Chạy hằng ngày thay vì đúng ngày đầu quý để máy chủ tắt đúng hôm đó vẫn mở phiếu khi chạy lại. Tắt bằng REVIEW_WORKER=off.
 */
export function startReviewWorker(): Promise<PgBoss | null> {
  if (process.env.REVIEW_WORKER === "off") return Promise.resolve(null);
  started ??= (async () => {
    const url = process.env.DATABASE_URL;
    if (!url) return null;
    try {
      const boss = new PgBoss(url);
      boss.on("error", (e) => console.error("[review] pg-boss:", e));
      await boss.start();
      await boss.createQueue(QUEUE);
      await boss.schedule(QUEUE, "0 0 * * *"); // 07:00 giờ Việt Nam
      await boss.work(QUEUE, async () => {
        const r = await openQuarterlyReview();
        if (r.created) console.log(`[review] đã mở phiếu ${r.code} cho ${r.period}`);
        else console.log(`[review] ${r.reason}`);
      });
      // Chạy ngay một lần lúc khởi động để không phải chờ tới 07:00
      const first = await openQuarterlyReview();
      console.log(first.created ? `[review] đã mở phiếu ${first.code} cho ${first.period}` : `[review] ${first.reason}`);
      return boss;
    } catch (e) {
      console.error("[review] Không khởi động được rà soát định kỳ:", e);
      return null;
    }
  })();
  return started;
}
