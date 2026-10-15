// Phiếu do DataTrust gửi sang SoD Flow: duyệt một bước xử lý dữ liệu (sửa dữ liệu cách ly, đổi rule, gỡ cách ly).
// Chuỗi duyệt lấy từ ma trận: dòng 13 (id 12) cho sửa dữ liệu / đổi rule; dòng 16 (id 15) rồi dòng 13 cho gỡ cách ly.
// Dòng 13 không có bước P cho người khác: Requestor thực thi ở DataTrust sau khi phiếu DONE.
// Phiếu chỉ mô tả dữ liệu (bảng, cột, số dòng, thao tác), không bao giờ chứa giá trị dữ liệu khách hàng.
import * as z from "zod";
import { ticketType, type RoleKey } from "./catalog";
import type { Classification, Mods } from "./classify";

export const DT_TYPES = ["dt_remediation", "dt_rule_change", "dt_override"] as const;
export type DtType = (typeof DT_TYPES)[number];
export const isDtType = (id: string): id is DtType => (DT_TYPES as readonly string[]).includes(id);

export const DT_TYPE_LABEL: Record<DtType, string> = {
  dt_remediation: "Xử lý dữ liệu cách ly",
  dt_rule_change: "Đổi rule xử lý dữ liệu",
  dt_override: "Gỡ cách ly (ngoại lệ)",
};

export const DtInputSchema = z.object({
  type: z.enum(DT_TYPES),
  /** username của người gửi duyệt bên DataTrust, khớp users.username của SoD */
  requesterUsername: z.string().trim().min(1).max(64),
  /** Mã đề xuất bên DataTrust (PROP-REM-...) */
  externalRef: z.string().trim().min(1).max(100),
  /** SHA-256 nội dung đề xuất: người duyệt duyệt đúng bản này, DataTrust kiểm lại trước khi thực thi */
  proposalHash: z.string().regex(/^[a-f0-9]{64}$/),
  dataset: z.string().trim().min(1).max(100),
  column: z.string().trim().max(100),
  operation: z.string().trim().min(1).max(100),
  expectedRows: z.number().int().min(0).max(10_000_000),
  riskLevel: z.enum(["LOW", "MEDIUM", "HIGH"]),
  /** Dữ liệu có cột dữ liệu cá nhân → thêm DPO vào chuỗi duyệt */
  pii: z.boolean(),
  reason: z.string().trim().min(1).max(1000),
});
export type DtInput = z.infer<typeof DtInputSchema>;

/** Nội dung lưu trong tickets.form của phiếu DataTrust. */
export type DtForm = DtInput & { kind: "datatrust" };
export const isDtForm = (f: unknown): f is DtForm => !!f && typeof f === "object" && (f as { kind?: unknown }).kind === "datatrust";

/** Phân loại phiếu → chuỗi hoạt động. Có DLCN thì DPO rà soát (QT 5.4), cùng cách classify.ts nâng vai trò. */
export function classifyDt(input: Pick<DtInput, "type" | "pii">): Classification {
  const type = ticketType(input.type);
  const mods: Mods = {};
  const reasons = [
    input.type === "dt_override"
      ? "Gỡ cách ly ngoại lệ → “Phê duyệt ngoại lệ kiểm soát” (dòng 16) rồi “Thay đổi chính sách vận hành” (dòng 13). Requestor thực thi ở DataTrust."
      : "Xử lý / đổi rule dữ liệu → “Thay đổi chính sách vận hành” (dòng 13). Requestor thực thi ở DataTrust sau khi phiếu hoàn tất.",
  ];
  if (input.pii && input.type !== "dt_override") {
    // dòng 13: DPO là C → nâng lên R khi có DLCN
    mods[12] = { DPO: "R" as const } satisfies Partial<Record<RoleKey, "R">>;
    reasons.push("Có DLCN → DPO rà soát ở “Thay đổi chính sách vận hành” (QT 5.4)");
  }
  return { type, acts: [...type.acts], mods, reasons, level: input.pii ? 2 : 1, pii: input.pii, breakGlass: false };
}

// Phiếu không được chứa dữ liệu khách hàng (N5): chặn số điện thoại, email, biển số trong mọi trường văn bản.
const LEAK_PATTERNS: [string, RegExp][] = [
  ["email", /[^\s@]+@[^\s@]+\.[^\s@]+/],
  ["số điện thoại", /(?:\+?84|0)[\s.-]?\d(?:[\s.-]?\d){8,9}/],
  ["dãy số dài (nghi số định danh)", /\d{9,}/],
  ["biển số xe", /\b\d{2}[A-Z]{1,2}[\s-]?\d{3}[.]?\d{2}\b/],
];

/** Trả về [tên trường, loại dữ liệu] của giá trị đầu tiên có vẻ chứa dữ liệu cá nhân, hoặc null. */
export function scanPersonalData(fields: [name: string, value: string][]): [string, string] | null {
  for (const [name, value] of fields) {
    for (const [label, re] of LEAK_PATTERNS) if (re.test(value)) return [name, label];
  }
  return null;
}

/** Trả về [trường, loại dữ liệu] của trường đầu tiên có vẻ chứa dữ liệu cá nhân, hoặc null. */
export function findPersonalData(input: DtInput): [string, string] | null {
  const fields: (keyof DtInput)[] = ["externalRef", "dataset", "column", "operation", "reason"];
  return scanPersonalData(fields.map((f) => [f, String(input[f] ?? "")]));
}
