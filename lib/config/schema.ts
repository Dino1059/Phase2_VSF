// Cấu hình SoD có phiên bản (KE_HOACH.md 1.1, 9.5). Dùng chung cho trình duyệt (form đề xuất) và server (kiểm lại).
// Mỗi ticket giữ phiên bản cấu hình lúc tạo; đổi cấu hình chỉ ảnh hưởng ticket tạo sau.
import * as z from "zod";
import { ACTIVITIES, DEFAULT_MATRIX, ROLE_KEYS, SOD_CONFIG, type Priority, type StepAction } from "@/lib/sod/catalog";

const hours = z.number().min(1).max(720);
const factor = z.number().min(0.05).max(10);

export const ConfigSchema = z
  .object({
    /** Giờ SLA cho mỗi loại bước: P thực hiện, R rà soát, A phê duyệt */
    sla: z.object({ P: hours, R: hours, A: hours }),
    /** Hệ số nhân SLA theo mức ưu tiên */
    priority: z.object({ urgent: factor, high: factor, normal: factor, low: factor }),
    /** Mốc % thời hạn SLA: nhắc, báo quá hạn / leo thang, báo CISO và Auditor */
    remindPct: z.number().int().min(10).max(100),
    escalatePct: z.number().int().min(50).max(300),
    criticalPct: z.number().int().min(100).max(1000),
    /** Số ngày không ai xử lý thì Admin đóng phiếu "hết hạn" */
    staleCloseDays: z.number().int().min(1).max(90),
    delegationMaxDays: z.number().int().min(1).max(90),
    /** 19 hoạt động × 10 vai trò (thứ tự ROLE_KEYS), mỗi ô là một ký hiệu P A R C I X */
    matrix: z.array(z.string().regex(/^[PARCIX]{10}$/, "Mỗi dòng ma trận gồm đúng 10 ký hiệu P A R C I X")).length(ACTIVITIES.length),
  })
  .superRefine((c, ctx) => {
    const bad = (path: (string | number)[], message: string) => ctx.addIssue({ code: "custom", path, message });
    const p = c.priority;
    if (!(p.urgent <= p.high && p.high <= p.normal && p.normal <= p.low)) bad(["priority"], "Hệ số ưu tiên phải tăng dần: Khẩn cấp ≤ Cao ≤ Trung bình ≤ Thấp");
    if (!(c.remindPct < c.escalatePct && c.escalatePct <= c.criticalPct)) bad(["escalatePct"], "Mốc SLA phải tăng dần: nhắc < quá hạn ≤ báo CISO và Auditor");
    // Bất biến an toàn của ma trận (rule.md mục 4): người tạo yêu cầu không được rà soát hoặc phê duyệt
    const req = ROLE_KEYS.indexOf("REQ");
    c.matrix.forEach((row, i) => {
      if ("AR".includes(row[req])) bad(["matrix", i], `“${ACTIVITIES[i].name}”: Requestor không được là người rà soát hoặc phê duyệt`);
    });
  });

export type ConfigData = z.infer<typeof ConfigSchema>;

export const DEFAULT_CONFIG: ConfigData = {
  sla: { ...SOD_CONFIG.sla },
  priority: { ...SOD_CONFIG.priority },
  remindPct: SOD_CONFIG.remindPct,
  escalatePct: SOD_CONFIG.escalatePct,
  criticalPct: SOD_CONFIG.criticalPct,
  staleCloseDays: SOD_CONFIG.staleCloseDays,
  delegationMaxDays: SOD_CONFIG.delegationMaxDays,
  matrix: [...DEFAULT_MATRIX],
};

export const SLA_LABEL: Record<StepAction, string> = { P: "Thực hiện", R: "Rà soát", A: "Phê duyệt" };
export const PRIORITY_KEYS: Priority[] = ["urgent", "high", "normal", "low"];

/** Các điểm khác nhau giữa hai cấu hình, mô tả bằng lời, để người duyệt biết mình đang duyệt gì. */
export function diffConfig(a: ConfigData, b: ConfigData): string[] {
  const out: string[] = [];
  (Object.keys(a.sla) as StepAction[]).forEach((k) => a.sla[k] !== b.sla[k] && out.push(`SLA ${SLA_LABEL[k].toLowerCase()}: ${a.sla[k]}h → ${b.sla[k]}h`));
  PRIORITY_KEYS.forEach((k) => a.priority[k] !== b.priority[k] && out.push(`Hệ số ưu tiên ${k}: ×${a.priority[k]} → ×${b.priority[k]}`));
  (["remindPct", "escalatePct", "criticalPct", "staleCloseDays", "delegationMaxDays"] as const).forEach(
    (k) => a[k] !== b[k] && out.push(`${k}: ${a[k]} → ${b[k]}`),
  );
  b.matrix.forEach((row, i) => {
    if (row === a.matrix[i]) return;
    ROLE_KEYS.forEach((r, j) => row[j] !== a.matrix[i][j] && out.push(`Ma trận “${ACTIVITIES[i].name}”, ${r}: ${a.matrix[i][j]} → ${row[j]}`));
  });
  return out;
}
