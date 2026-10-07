// Chạy một lần khi máy chủ Next.js khởi động: bật SLA nền (pg-boss). Không chạy trên Edge runtime.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  const { startSlaWorker } = await import("@/lib/sla/worker");
  void startSlaWorker(); // không chờ: máy chủ phải sẵn sàng phục vụ ngay cả khi pg-boss khởi động chậm
}
