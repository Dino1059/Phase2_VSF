// Định dạng dùng chung cho server và trình duyệt. Cố định múi giờ để hai bên hiển thị giống nhau.
const TZ = "Asia/Ho_Chi_Minh";

export const fmtTime = (t: Date | string | number) =>
  new Date(t).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", timeZone: TZ });

export const fmtDate = (t: Date | string | number = Date.now()) =>
  new Date(t).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: TZ });

/** "2026-10-01" → "01/10/2026" */
export const dateVN = (s: string) => (s ? s.split("-").reverse().join("/") : "");

export function fmtDur(ms: number) {
  const s = Math.abs(ms) / 1000;
  if (s < 60) return `${Math.round(s)}s`;
  // Làm tròn trên tổng số phút / giờ trước khi tách, tránh "23h 60m"
  const m = Math.round(s / 60);
  if (m < 60) return `${m} phút`;
  if (m < 24 * 60) return `${Math.floor(m / 60)}h ${m % 60}m`;
  const h = Math.round(s / 3600);
  return `${Math.floor(h / 24)} ngày ${h % 24}h`;
}
