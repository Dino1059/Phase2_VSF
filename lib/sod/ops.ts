// Phiếu nghiệp vụ: các loại yêu cầu ngoài cấp quyền / RBAC / DataTrust (điều chuyển, truy vấn và xuất PII, sự cố, giá, ngoại lệ).
// Mỗi loại ghép một hoặc nhiều hoạt động của ma trận thành chuỗi duyệt (TICKET_TYPES trong catalog.ts); chuỗi do ma trận đang hiệu lực sinh ra.
import * as z from "zod";
import { DEFAULT_MATRIX, letter, ticketType, type Priority } from "./catalog";
import type { Classification, Mods } from "./classify";
import { scanPersonalData } from "./datatrust";

/** Loại người dùng tự lập phiếu. "review" do hệ thống tự tạo theo quý nên không nằm ở đây */
export const OPS_FORM_TYPES = ["transfer", "pii_query", "pii_export", "incident", "pricing", "change", "exception"] as const;
export const OPS_TYPES = [...OPS_FORM_TYPES, "review"] as const;
export type OpsType = (typeof OPS_TYPES)[number];
export type OpsFormType = (typeof OPS_FORM_TYPES)[number];
export const isOpsFormType = (id: string): id is OpsFormType => (OPS_FORM_TYPES as readonly string[]).includes(id);
export const isOpsType = (id: string): id is OpsType => (OPS_TYPES as readonly string[]).includes(id);

export const OPS_TYPE_LABEL: Record<OpsType, string> = {
  transfer: "Điều chuyển / đổi vai trò",
  pii_query: "Truy vấn dữ liệu PII khách hàng",
  pii_export: "Xuất dữ liệu PII khách hàng",
  incident: "Sự cố bảo mật",
  pricing: "Thay đổi giá / khuyến mại / chính sách",
  change: "Thay đổi mã nguồn → Production",
  exception: "Phê duyệt ngoại lệ kiểm soát",
  review: "Rà soát quyền định kỳ",
};

export const OPS_TYPE_HINT: Record<OpsType, string> = {
  transfer: "Nhân sự chuyển phòng ban hoặc đổi vai trò: quyền cũ được rà lại trước khi IAM đổi.",
  pii_query: "Cần xem dữ liệu khách hàng trực tiếp. Chỉ mô tả bảng, cột, số bản ghi; không dán giá trị dữ liệu.",
  pii_export: "Cần xuất dữ liệu khách hàng ra file. Chỉ mô tả bảng, cột, nơi nhận; không dán giá trị dữ liệu.",
  incident: "Mở và xử lý sự cố bảo mật: điều tra, khắc phục, rồi đóng sự cố bởi người khác với người điều tra.",
  pricing: "Đổi giá, khuyến mại hoặc chính sách vận hành trên hệ thống đang chạy.",
  change: "Developer lập phiếu cho thay đổi mã nguồn: kiểm thử, duyệt phát hành, rồi người khác triển khai lên Production.",
  exception: "Xin miễn một kiểm soát trong thời hạn, kèm biện pháp bù trừ.",
  review: "Hệ thống tự tạo mỗi quý: System Owner rà soát toàn bộ quyền đang có, CISO rà soát, Line Manager phê duyệt, Auditor kiểm tra.",
};

type FieldKind = "text" | "textarea" | "date" | "number" | "select";
export type OpsField = { key: string; label: string; kind: FieldKind; required?: boolean; options?: Record<string, string>; max?: number };

const SEVERITY = { S1: "S1 – Nghiêm trọng", S2: "S2 – Cao", S3: "S3 – Trung bình", S4: "S4 – Thấp" };

/** Trường riêng của từng loại. Server kiểm lại đúng danh sách này, khoá lạ bị từ chối. */
export const OPS_FIELDS: Record<OpsType, OpsField[]> = {
  transfer: [
    { key: "nhanVien", label: "Nhân sự được điều chuyển (họ tên, mã NV)", kind: "text", required: true, max: 200 },
    { key: "tuVaiTro", label: "Phòng ban / chức danh hiện tại", kind: "text", required: true, max: 200 },
    { key: "denVaiTro", label: "Phòng ban / chức danh mới", kind: "text", required: true, max: 200 },
    { key: "ngayHieuLuc", label: "Ngày hiệu lực", kind: "date", required: true },
    { key: "heThong", label: "Hệ thống / quyền bị ảnh hưởng", kind: "textarea", required: true, max: 1000 },
  ],
  pii_query: [
    { key: "dataset", label: "Bảng / dataset", kind: "text", required: true, max: 200 },
    { key: "columns", label: "Cột cần truy vấn", kind: "text", required: true, max: 300 },
    { key: "soBanGhi", label: "Số bản ghi ước tính", kind: "number", required: true },
    { key: "thoiHan", label: "Truy cập đến ngày", kind: "date", required: true },
  ],
  pii_export: [
    { key: "dataset", label: "Bảng / dataset", kind: "text", required: true, max: 200 },
    { key: "columns", label: "Cột cần xuất", kind: "text", required: true, max: 300 },
    { key: "soBanGhi", label: "Số bản ghi ước tính", kind: "number", required: true },
    { key: "dinhDang", label: "Định dạng file", kind: "select", required: true, options: { csv: "CSV", xlsx: "Excel", json: "JSON", khac: "Khác (ghi rõ ở mục đích)" } },
    { key: "noiNhan", label: "Nơi nhận / lưu file", kind: "text", required: true, max: 300 },
    { key: "huyFile", label: "Huỷ file sau ngày", kind: "date", required: true },
  ],
  incident: [
    { key: "mucDo", label: "Mức độ", kind: "select", required: true, options: SEVERITY },
    { key: "phatHien", label: "Thời điểm phát hiện", kind: "date", required: true },
    { key: "moTa", label: "Mô tả sự cố", kind: "textarea", required: true, max: 2000 },
  ],
  pricing: [
    { key: "noiDung", label: "Nội dung thay đổi", kind: "textarea", required: true, max: 2000 },
    { key: "phamVi", label: "Phạm vi (thị trường, sản phẩm)", kind: "text", required: true, max: 300 },
    { key: "ngayHieuLuc", label: "Ngày hiệu lực", kind: "date", required: true },
  ],
  change: [
    { key: "prLink", label: "Link PR / MR / commit", kind: "text", required: true, max: 300 },
    { key: "moiTruong", label: "Môi trường đích", kind: "select", required: true, options: { staging: "Staging", prod: "Production" } },
    { key: "moTa", label: "Mô tả thay đổi", kind: "textarea", required: true, max: 2000 },
    { key: "ketQuaTest", label: "Kết quả kiểm thử (link báo cáo hoặc tóm tắt)", kind: "textarea", required: true, max: 2000 },
    { key: "rollback", label: "Kế hoạch rollback", kind: "textarea", required: true, max: 2000 },
    { key: "cuaSo", label: "Ngày dự kiến triển khai", kind: "date", required: true },
  ],
  review: [
    { key: "ky", label: "Kỳ rà soát", kind: "text", required: true, max: 20 },
    { key: "soQuyen", label: "Số quyền truy cập đang có", kind: "number", required: true },
    { key: "soVaiTro", label: "Số vai trò SoD Flow đang có", kind: "number", required: true },
  ],
  exception: [
    { key: "kiemSoat", label: "Kiểm soát được miễn", kind: "text", required: true, max: 300 },
    { key: "tuNgay", label: "Hiệu lực từ", kind: "date", required: true },
    { key: "denNgay", label: "Hiệu lực đến", kind: "date", required: true },
    { key: "bienPhap", label: "Biện pháp bù trừ", kind: "textarea", required: true, max: 2000 },
  ],
};

export const OpsInputSchema = z.object({
  type: z.enum(OPS_FORM_TYPES),
  title: z.string().trim().max(200),
  system: z.string().trim().max(300),
  urgent: z.boolean(),
  /** Có dữ liệu cá nhân → DPO rà soát (QT 5.4). Hai loại PII luôn là true */
  pii: z.boolean(),
  reason: z.string().trim().max(2000),
  fields: z.record(z.string().max(64), z.string().max(2000)),
});
export type OpsInput = z.infer<typeof OpsInputSchema>;

/** Ảnh chụp quyền đang có lúc hệ thống mở phiếu rà soát định kỳ (người duyệt xem đúng bản này, mã băm phiếu bao gồm nó) */
export type ReviewSnapshot = {
  period: string;
  generatedAt: string;
  grants: { ticket: string; user: string; email: string; system: string; resource: string; permission: string; until: string }[];
  roles: { user: string; role: string; until: string }[];
  truncated: boolean;
};

/** Nội dung lưu trong tickets.form của phiếu nghiệp vụ. */
export type OpsForm = Omit<OpsInput, "type"> & { kind: "ops"; type: OpsType; snapshot?: ReviewSnapshot };
export const isOpsForm = (f: unknown): f is OpsForm => !!f && typeof f === "object" && (f as { kind?: unknown }).kind === "ops";

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Lỗi nhập liệu dạng [tên trường, thông báo]. Rỗng = hợp lệ. */
export function validateOps(d: Pick<OpsInput, "type" | "title" | "system" | "reason" | "fields" | "pii">): [string, string][] {
  const e: [string, string][] = [];
  const spec = OPS_FIELDS[d.type];
  if (!d.title) e.push(["title", "Nhập tiêu đề"]);
  if (!d.system) e.push(["system", "Nhập hệ thống / đối tượng liên quan"]);
  if (!d.reason) e.push(["reason", "Nhập lý do / mục đích"]);
  for (const k of Object.keys(d.fields)) if (!spec.some((f) => f.key === k)) e.push([`fields.${k}`, `Trường “${k}” không thuộc loại phiếu này`]);
  for (const f of spec) {
    const v = (d.fields[f.key] ?? "").trim();
    const name = `fields.${f.key}`;
    if (!v) {
      if (f.required) e.push([name, `${f.label}: bắt buộc`]);
      continue;
    }
    if (f.max && v.length > f.max) e.push([name, `${f.label}: tối đa ${f.max} ký tự`]);
    if (f.kind === "date" && (!DATE.test(v) || Number.isNaN(Date.parse(v)))) e.push([name, `${f.label}: ngày không hợp lệ`]);
    if (f.kind === "number" && !/^\d{1,8}$/.test(v)) e.push([name, `${f.label}: nhập số nguyên không âm`]);
    if (f.kind === "select" && !(v in (f.options ?? {}))) e.push([name, `${f.label}: giá trị không hợp lệ`]);
  }
  const f = d.fields;
  if (d.type === "exception" && f.tuNgay && f.denNgay && f.denNgay <= f.tuNgay) e.push(["fields.denNgay", "Hiệu lực đến phải sau hiệu lực từ"]);
  if ((d.type === "pii_query" || d.type === "pii_export") && !d.pii) e.push(["pii", "Loại phiếu này luôn có dữ liệu cá nhân"]);
  return e;
}

/** Phiếu PII không được chứa dữ liệu khách hàng (như phiếu DataTrust): chỉ mô tả dữ liệu, không kèm giá trị. */
export function findOpsPersonalData(d: OpsInput): [string, string] | null {
  if (d.type !== "pii_query" && d.type !== "pii_export") return null;
  return scanPersonalData([["title", d.title], ["system", d.system], ["reason", d.reason], ...Object.entries(d.fields).map(([k, v]): [string, string] => [`fields.${k}`, v])]);
}

export function opsPriority(d: { type: OpsType; urgent: boolean; fields: Record<string, string> }): Priority {
  if (d.type === "incident") return d.fields.mucDo === "S1" ? "urgent" : d.fields.mucDo === "S2" ? "high" : "normal";
  return d.urgent ? "urgent" : "normal";
}

/** Phân loại phiếu → chuỗi hoạt động. Có DLCN thì DPO rà soát ở hoạt động đầu nếu ma trận chỉ cho DPO tham vấn / nhận tin (QT 5.4). */
export function classifyOps(input: { type: OpsType; pii: boolean }, matrix: readonly string[] = DEFAULT_MATRIX): Classification {
  const type = ticketType(input.type);
  const acts: number[] = [...type.acts];
  const mods: Mods = {};
  const reasons = [`Loại phiếu “${OPS_TYPE_LABEL[input.type]}” → ${acts.length} hoạt động trong ma trận, theo thứ tự trong phiếu`];
  if (input.pii) {
    const first = acts[0];
    const l = letter(first, "DPO", matrix);
    if (l === "C" || l === "I") {
      mods[first] = { DPO: "R" };
      reasons.push("Có DLCN → DPO rà soát (QT 5.4)");
    }
  }
  return { type, acts, mods, reasons, level: input.pii ? 2 : 1, pii: input.pii, breakGlass: false };
}
