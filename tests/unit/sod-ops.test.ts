// Phiếu nghiệp vụ (lib/sod/ops.ts): chuỗi duyệt sinh từ ma trận, kiểm nhập liệu, chặn dữ liệu cá nhân trong phiếu PII.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_MATRIX, ticketType } from "@/lib/sod/catalog";
import { phaseSteps } from "@/lib/sod/chain";
import { OPS_FIELDS, OPS_FORM_TYPES, classifyOps, findOpsPersonalData, opsPriority, validateOps, type OpsInput, type OpsFormType } from "@/lib/sod/ops";

const sample: Record<OpsFormType, Record<string, string>> = {
  transfer: { nhanVien: "Nguyễn Văn A", tuVaiTro: "Kế toán", denVaiTro: "Kinh doanh", ngayHieuLuc: "2026-11-01", heThong: "ERP" },
  pii_query: { dataset: "trips", columns: "customer_contact", soBanGhi: "100", thoiHan: "2026-11-30" },
  pii_export: { dataset: "trips", columns: "customer_contact", soBanGhi: "100", dinhDang: "csv", noiNhan: "Kho lưu trữ nội bộ", huyFile: "2026-12-31" },
  incident: { mucDo: "S2", phatHien: "2026-10-14", moTa: "Phát hiện truy cập bất thường vào máy chủ" },
  pricing: { noiDung: "Giảm giá 10%", phamVi: "Việt Nam", ngayHieuLuc: "2026-11-01" },
  change: { prLink: "https://git.example.com/pr/12", moiTruong: "prod", moTa: "Sửa lỗi tính giá", ketQuaTest: "Đạt 100% test", rollback: "Revert commit", cuaSo: "2026-11-05" },
  exception: { kiemSoat: "Tách nhiệm vụ deploy", tuNgay: "2026-11-01", denNgay: "2026-11-30", bienPhap: "Auditor hậu kiểm hằng ngày" },
};
const input = (type: OpsFormType, over: Partial<OpsInput> = {}): OpsInput => ({
  type, title: "Tiêu đề", system: "Hệ thống X", urgent: false, pii: type === "pii_query" || type === "pii_export", reason: "Lý do", fields: sample[type], ...over,
});

test("mọi loại phiếu nghiệp vụ hợp lệ với dữ liệu mẫu và có chuỗi duyệt", () => {
  for (const t of OPS_FORM_TYPES) {
    assert.deepEqual(validateOps(input(t)), [], t);
    const cl = classifyOps(input(t));
    assert.deepEqual(cl.acts, [...ticketType(t).acts], t);
    const steps = cl.acts.flatMap((a) => phaseSteps(a, cl.mods[a]).seq);
    assert.ok(steps.length > 0, `${t}: chuỗi rỗng`);
    for (const a of cl.acts) assert.ok(phaseSteps(a, cl.mods[a]).seq.filter(([, l]) => l === "P").length <= 1, `${t}: dòng ${a + 1} quá một P`);
  }
});

test("thiếu trường bắt buộc, khoá lạ, ngày sai, số sai đều bị báo", () => {
  const e = validateOps(input("pii_export", { title: "", fields: { dataset: "t", soBanGhi: "abc", dinhDang: "exe", huyFile: "31/12/2026", la: "x" } }));
  const keys = e.map(([k]) => k);
  for (const k of ["title", "fields.columns", "fields.noiNhan", "fields.soBanGhi", "fields.dinhDang", "fields.huyFile", "fields.la"]) assert.ok(keys.includes(k), `thiếu lỗi ${k}: ${keys.join(",")}`);
});

test("ngoại lệ: hiệu lực đến phải sau hiệu lực từ; phiếu PII không được tắt cờ DLCN", () => {
  assert.ok(validateOps(input("exception", { fields: { ...sample.exception, denNgay: "2026-11-01" } })).some(([k]) => k === "fields.denNgay"));
  assert.ok(validateOps(input("pii_query", { pii: false })).some(([k]) => k === "pii"));
});

test("phiếu PII bị chặn khi chứa email, số điện thoại hoặc dãy số định danh; loại khác thì không quét", () => {
  assert.ok(findOpsPersonalData(input("pii_query", { reason: "Xem khách a@b.vn" })));
  assert.ok(findOpsPersonalData(input("pii_export", { fields: { ...sample.pii_export, noiNhan: "0912 345 678" } })));
  assert.ok(findOpsPersonalData(input("pii_query", { title: "CCCD 012345678901" })));
  assert.equal(findOpsPersonalData(input("pii_query")), null);
  assert.equal(findOpsPersonalData(input("incident", { reason: "Kẻ tấn công dùng a@b.vn" })), null);
});

test("có DLCN thì DPO rà soát ở hoạt động đầu khi ma trận chỉ cho DPO tham vấn / nhận tin", () => {
  const cl = classifyOps(input("pricing", { pii: true }));
  assert.equal(cl.mods[12]?.DPO, "R");
  assert.equal(classifyOps(input("pricing")).mods[12], undefined);
  // dòng 14 đã có DPO A: không nâng
  assert.equal(classifyOps(input("pii_query")).mods[13], undefined);
  assert.equal(classifyOps(input("pii_query"), DEFAULT_MATRIX).pii, true);
});

test("mức ưu tiên: sự cố theo mức độ, loại khác theo cờ Gấp", () => {
  assert.equal(opsPriority(input("incident", { fields: { ...sample.incident, mucDo: "S1" } })), "urgent");
  assert.equal(opsPriority(input("incident")), "high");
  assert.equal(opsPriority(input("incident", { fields: { ...sample.incident, mucDo: "S4" } })), "normal");
  assert.equal(opsPriority(input("pricing", { urgent: true })), "urgent");
  assert.equal(opsPriority(input("pricing")), "normal");
});

test("mỗi loại khai báo trường riêng đủ nhãn", () => {
  for (const t of OPS_FORM_TYPES) for (const f of OPS_FIELDS[t]) assert.ok(f.label && f.key, t);
});
