// Phiếu cấp / thu hồi quyền truy cập — dùng chung cho trình duyệt (báo lỗi ngay) và server (kiểm lại).
// Không có trường "người yêu cầu": server lấy từ phiên đăng nhập (KE_HOACH.md 9.3, lớp 1).
import * as z from "zod";
import type { Priority } from "./catalog";

export const LOAI_PHIEU = { new: "Cấp mới", adjust: "Điều chỉnh", extend: "Gia hạn", revoke: "Thu hồi", bg: "Break-glass" };
export const MUC_KHAN = { normal: "Thường", urgent: "Gấp (nêu lý do tại mục lý do)" };
export const DLCN = { none: "Không", basic: "Có – DLCN cơ bản", sensitive: "Có – DLCN nhạy cảm" };
export const THI_TRUONG = { vn: "Việt Nam", intl: "Quốc tế (ghi rõ)" };
export const CAP_BAC = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"] as const;
export const TANG = ["1", "2", "3"] as const;
export const MUC_QUYEN = ["RO", "RW", "Full"] as const;
export const CAM_KET = [
  "Chỉ sử dụng quyền được cấp đúng mục đích và trong phạm vi chức năng, vai trò, nhiệm vụ được giao.",
  "Không chia sẻ, chuyển tiếp quyền truy cập cho người khác dưới mọi hình thức.",
  "Không xuất dữ liệu ngoài phạm vi được phê duyệt; tuân thủ quy định kiểm soát xuất dữ liệu.",
  "Chủ động đề nghị điều chỉnh hoặc thu hồi quyền khi thay đổi phòng ban, chức năng hoặc kết thúc mục đích sử dụng.",
  "Tuân thủ VSF_IT06 và Quy trình kiểm soát truy cập, phân quyền và phân tách trách nhiệm.",
];

const oneOf = <T extends Record<string, string>>(map: T) =>
  z.union([z.literal(""), z.enum(Object.keys(map) as [keyof T & string, ...(keyof T & string)[]])]);
const text = (max = 500) => z.string().max(max);

const RowSchema = z.object({
  heThong: text(200),
  taiNguyen: text(300),
  tang: z.union([z.literal(""), z.enum(TANG)]),
  mucQuyen: z.union([z.literal(""), z.enum(MUC_QUYEN)]),
  thoiHan: z.union([z.literal(""), z.iso.date()]),
});

/** Kiểu và giới hạn độ dài — server parse để chặn dữ liệu lạ trước khi kiểm luật nghiệp vụ. */
export const TicketFormSchema = z.object({
  loaiPhieu: oneOf(LOAI_PHIEU),
  khan: oneOf(MUC_KHAN),
  hoTen: text(150),
  maNV: text(50),
  email: text(254),
  phongBan: text(200),
  chucDanh: text(150),
  capBac: z.union([z.literal(""), z.enum(CAP_BAC)]),
  viTri: text(2000),
  thiTruong: oneOf(THI_TRUONG),
  thiTruongGhiRo: text(200),
  nhapThay: z.boolean(),
  ntHoTen: text(150),
  ntChucDanh: text(150),
  ntVanBan: text(1000),
  rows: z.array(RowSchema).min(1).max(20),
  mucDich: text(2000),
  dlcn: oneOf(DLCN),
  lyDo: text(2000),
  camKet: z.boolean(),
  kyTen: text(150),
  signature: z.union([z.literal(""), z.string().max(300_000).startsWith("data:image/png;base64,")]),
  exception: z.boolean(),
  exReason: text(2000),
  exFrom: text(30),
  exTo: text(30),
  exControls: text(2000),
});
export type TicketForm = z.infer<typeof TicketFormSchema>;
export type FormRow = TicketForm["rows"][number];

export const emptyRow = (): FormRow => ({ heThong: "", taiNguyen: "", tang: "", mucQuyen: "", thoiHan: "" });
export const emptyForm = (hoTen = "", email = ""): TicketForm => ({
  loaiPhieu: "", khan: "",
  hoTen, maNV: "", email, phongBan: "", chucDanh: "", capBac: "", viTri: "", thiTruong: "", thiTruongGhiRo: "",
  nhapThay: false, ntHoTen: "", ntChucDanh: "", ntVanBan: "",
  rows: [emptyRow()], mucDich: "", dlcn: "", lyDo: "",
  camKet: false, kyTen: "", signature: "",
  exception: false, exReason: "", exFrom: "", exTo: "", exControls: "",
});

export const rowFilled = (r: FormRow) => Object.values(r).some((v) => v.trim());
export const formLevel = (d: TicketForm) => Math.max(1, ...d.rows.map((r) => +r.tang || 0));
export const formPii = (d: TicketForm) => d.dlcn === "basic" || d.dlcn === "sensitive";
export const formPriority = (d: TicketForm): Priority => (d.khan === "urgent" ? "urgent" : "normal");

/** [tên trường, thông báo] cho mỗi lỗi. Rỗng = hợp lệ. */
export function validateForm(d: TicketForm): [string, string][] {
  const e: [string, string][] = [];
  const req = (k: keyof TicketForm, label: string) => {
    if (!String(d[k] ?? "").trim()) e.push([k, label]);
  };
  req("loaiPhieu", "Loại phiếu");
  req("khan", "Mức độ khẩn");
  req("hoTen", "Họ và tên");
  req("maNV", "Mã nhân viên");
  req("email", "Email công vụ");
  if (d.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email.trim())) e.push(["email", "Email công vụ không hợp lệ"]);
  req("phongBan", "Khối / Phòng / Bộ phận");
  req("chucDanh", "Chức danh");
  req("capBac", "Cấp bậc");
  req("viTri", "Vị trí công việc và phạm vi phụ trách");
  req("thiTruong", "Thị trường cung cấp dịch vụ");
  if (d.thiTruong === "intl") req("thiTruongGhiRo", "Ghi rõ thị trường quốc tế");
  if (d.nhapThay) {
    req("ntHoTen", "Họ tên người nhập phiếu");
    req("ntChucDanh", "Chức danh người nhập phiếu");
    req("ntVanBan", "Văn bản/email phê duyệt của CBLĐ");
  }
  if (!d.rows.some(rowFilled)) e.push(["rows.0.heThong", "Phần B: cần ít nhất một dòng đề nghị"]);
  const cols: [keyof FormRow, string][] = [["heThong", "Hệ thống"], ["taiNguyen", "Tài nguyên cụ thể"], ["tang", "Tầng dữ liệu"], ["mucQuyen", "Mức quyền"]];
  if (d.loaiPhieu !== "revoke") cols.push(["thoiHan", "Thời hạn đề nghị"]);
  d.rows.forEach((r, i) => {
    if (rowFilled(r)) cols.forEach(([k, l]) => { if (!r[k].trim()) e.push([`rows.${i}.${k}`, `Dòng ${i + 1}: ${l}`]); });
  });
  req("mucDich", "Mục đích sử dụng");
  req("dlcn", "Có liên quan dữ liệu cá nhân không?");
  if ((d.dlcn === "sensitive" || d.khan === "urgent") && !d.lyDo.trim()) {
    e.push(["lyDo", "Lý do nghiệp vụ (bắt buộc khi DLCN nhạy cảm hoặc Gấp)"]);
  }
  if (d.exception) {
    req("exReason", "Ngoại lệ: lý do nghiệp vụ");
    req("exFrom", "Ngoại lệ: hiệu lực từ");
    req("exTo", "Ngoại lệ: hiệu lực đến");
    req("exControls", "Ngoại lệ: biện pháp bù trừ");
    if (d.exFrom && d.exTo && d.exTo <= d.exFrom) e.push(["exTo", "Ngoại lệ: thời hạn kết thúc phải sau thời điểm bắt đầu"]);
  }
  if (!d.camKet) e.push(["camKet", "Xác nhận cam kết (Phần C)"]);
  req("kyTen", "Người sử dụng quyền ghi rõ họ tên (Phần C)");
  return e;
}
