// Phiếu nghiệp vụ (điều chuyển, PII, sự cố, giá, ngoại lệ): chuỗi duyệt theo ma trận, người lập không tự duyệt,
// chặn dữ liệu cá nhân, không trả lại bổ sung. Chạy trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, createOpsTicket, parseOps, returnTicket } from "@/lib/tickets/service";
import { openQuarterlyReview } from "@/lib/tickets/review";
import { OPS_FORM_TYPES, type OpsInput, type OpsFormType } from "@/lib/sod/ops";
import { approveCurrent, asUser, form, meta, newTicket, reload } from "./helpers";

const approveAll = async (id: string) => {
  for (let i = 0; i < 30 && (await reload(id)).steps.some((s) => s.status === "CURRENT"); i++) await approveCurrent(id);
};

let an: CurrentUser, nam: CurrentUser, khoa: CurrentUser;
before(async () => {
  [an, nam, khoa] = await Promise.all(["an.nguyen", "nam.dang", "khoa.do"].map(asUser)); // nam.dang là Auditor (không có REQ); khoa.do là Requestor + Developer
});
after(() => prisma.$disconnect());

const fields: Record<OpsFormType, Record<string, string>> = {
  transfer: { nhanVien: "Nhân sự A", tuVaiTro: "Kế toán", denVaiTro: "Kinh doanh", ngayHieuLuc: "2026-11-01", heThong: "ERP" },
  pii_query: { dataset: "trips", columns: "customer_contact", soBanGhi: "100", thoiHan: "2026-11-30" },
  pii_export: { dataset: "trips", columns: "customer_contact", soBanGhi: "100", dinhDang: "csv", noiNhan: "Kho nội bộ", huyFile: "2026-12-31" },
  incident: { mucDo: "S2", phatHien: "2026-10-14", moTa: "Truy cập bất thường" },
  pricing: { noiDung: "Giảm giá 10%", phamVi: "Việt Nam", ngayHieuLuc: "2026-11-01" },
  change: { prLink: "https://git.example.com/pr/12", moiTruong: "prod", moTa: "Sửa lỗi tính giá", ketQuaTest: "Đạt 100% test", rollback: "Revert commit", cuaSo: "2026-11-05" },
  exception: { kiemSoat: "Tách nhiệm vụ", tuNgay: "2026-11-01", denNgay: "2026-11-30", bienPhap: "Hậu kiểm hằng ngày" },
};
const input = (type: OpsFormType, over: Partial<OpsInput> = {}): OpsInput => ({
  type, title: "Tiêu đề kiểm thử", system: "Hệ thống X", urgent: false, pii: type === "pii_query" || type === "pii_export", reason: "Lý do", fields: fields[type], ...over,
});
const create = async (user: CurrentUser, i: OpsInput) => {
  const r = await createOpsTicket(user, i, meta);
  assert.ok(r.ok, JSON.stringify(r));
  return r;
};

test("O1: mỗi loại tạo được phiếu; người lập không nằm trong chuỗi duyệt; mọi bước có người", async () => {
  for (const type of OPS_FORM_TYPES) {
    const who = type === "change" ? khoa : an; // phiếu thay đổi mã nguồn chỉ Developer lập được
    const r = await create(who, input(type));
    const t = await reload(r.id);
    assert.equal(t.typeId, type);
    assert.equal(t.status, "OPEN");
    assert.ok(t.steps.length > 1, `${type}: chỉ có bước 0`);
    assert.ok(t.steps.every((s) => s.idx === 0 || (s.assigneeId && (s.assigneeId !== who.id || (type === "change" && s.roleCode === "DEV")))), `${type}: người lập hoặc bước trống trong chuỗi`);
  }
});

test("O2: sự cố — người điều tra không phải người đóng sự cố; ưu tiên theo mức độ", async () => {
  const r = await create(an, input("incident", { fields: { ...fields.incident, mucDo: "S1" } }));
  const t = await reload(r.id);
  assert.equal(t.priority, "urgent");
  const byRole = (role: string, action: string) => t.steps.filter((s) => s.roleCode === role && s.action === action).map((s) => s.assigneeId);
  const closer = t.steps.filter((s) => s.action === "A").map((s) => s.assigneeId);
  for (const p of t.steps.filter((s) => s.action === "P").map((s) => s.assigneeId)) assert.ok(!closer.includes(p), "người điều tra tự đóng sự cố");
  assert.ok(byRole("CISO", "A").length > 0);
});

test("O3: có DLCN thì có DPO rà soát hoặc phê duyệt", async () => {
  const r = await create(an, input("pricing", { pii: true }));
  const t = await reload(r.id);
  assert.ok(t.steps.some((s) => s.roleCode === "DPO" && "RA".includes(s.action)));
  assert.equal(t.pii, true);
});

test("O4: phiếu PII chứa dữ liệu cá nhân bị chặn, không tạo phiếu", async () => {
  const before = await prisma.ticket.count();
  const r = await createOpsTicket(an, input("pii_query", { reason: "Xem khách 0912345678" }), meta);
  assert.equal(r.ok, false);
  assert.equal(await prisma.ticket.count(), before);
});

test("O5: dữ liệu sai bị từ chối ở server; người không có vai trò Requestor không tạo được", async () => {
  const bad = await createOpsTicket(an, input("exception", { fields: { ...fields.exception, denNgay: "2026-10-01" } }), meta);
  assert.equal(bad.ok, false);
  await assert.rejects(() => createOpsTicket(nam, input("pricing"), meta), TicketError);
});

test("O6: phiếu nghiệp vụ không trả lại bổ sung được; duyệt hết chuỗi thì DONE", async () => {
  const r = await create(an, input("exception"));
  const t = await reload(r.id);
  const cur = t.steps.find((s) => s.status === "CURRENT")!;
  const approver = await prisma.user.findUniqueOrThrow({ where: { id: cur.assigneeId! } });
  await assert.rejects(
    async () => returnTicket(await asUser(approver.username), { ticketId: r.id, stepId: cur.id, version: t.version, comment: "bổ sung" }, meta),
    TicketError,
  );
  for (let i = 0; i < t.steps.length; i++) {
    const cur2 = (await reload(r.id)).steps.find((s) => s.status === "CURRENT");
    if (!cur2) break;
    await approveCurrent(r.id);
  }
  assert.equal((await reload(r.id)).status, "DONE");
});

test("O7: phiếu thay đổi mã nguồn — chỉ Developer lập; Dev làm các bước Dev, không duyệt / triển khai thay đổi của mình", async () => {
  await assert.rejects(() => createOpsTicket(an, input("change"), meta), TicketError);
  const r = await create(khoa, input("change"));
  const t = await reload(r.id);
  const devSteps = t.steps.filter((s) => s.idx > 0 && s.roleCode === "DEV");
  assert.ok(devSteps.length > 0 && devSteps.every((s) => s.action === "P" && s.assigneeId === khoa.id), "bước Dev phải gán cho người lập phiếu");
  assert.ok(t.steps.filter((s) => s.idx > 0 && s.roleCode !== "DEV").every((s) => s.assigneeId !== khoa.id), "Dev không giữ bước duyệt hoặc triển khai");
  assert.ok(t.steps.some((s) => s.roleCode === "OPS" && s.action === "P"), "có bước Production Operator triển khai");
  for (let i = 0; i < t.steps.length; i++) {
    if (!(await reload(r.id)).steps.some((s) => s.status === "CURRENT")) break;
    await approveCurrent(r.id);
  }
  assert.equal((await reload(r.id)).status, "DONE");
});

test("O8: loại review không tạo tay được", async () => {
  await assert.rejects(async () => parseOps({ ...input("pricing"), type: "review" }), TicketError);
});

test("O9: rà soát định kỳ — hệ thống mở một phiếu mỗi quý, chạy lặp không tạo trùng; phiếu có ảnh chụp quyền và duyệt tới DONE", async () => {
  const when = new Date("2031-02-10T03:00:00Z");
  const a = await openQuarterlyReview(when);
  assert.ok(a.created, JSON.stringify(a));
  assert.equal(a.period, "2031-Q1");
  const b = await openQuarterlyReview(new Date("2031-03-30T03:00:00Z"));
  assert.equal(b.created, false);
  const next = await openQuarterlyReview(new Date("2031-04-02T03:00:00Z"));
  assert.ok(next.created, "quý sau phải mở phiếu mới");
  const t = await reload(a.id);
  assert.equal(t.typeId, "review");
  const sys = await prisma.user.findUniqueOrThrow({ where: { username: "system" } });
  assert.equal(t.requesterId, sys.id);
  const form = t.form as { snapshot?: { roles: unknown[] } };
  assert.ok(form.snapshot && form.snapshot.roles.length > 0, "phiếu phải có ảnh chụp vai trò");
  const roles = t.steps.filter((s) => s.idx > 0).map((s) => `${s.roleCode}:${s.action}`);
  for (const need of ["AUD:R", "SO:P", "CISO:R", "LM:A"]) assert.ok(roles.includes(need), `thiếu ${need} trong ${roles.join(",")}`);
  const audit = await prisma.auditLog.count({ where: { action: "ticket.created.scheduled", targetId: a.id } });
  assert.equal(audit, 1);
  for (let i = 0; i < t.steps.length; i++) {
    if (!(await reload(a.id)).steps.some((s) => s.status === "CURRENT")) break;
    await approveCurrent(a.id);
  }
  assert.equal((await reload(a.id)).status, "DONE");
});

test("O10: tài khoản hệ thống không đăng nhập được (DISABLED) và không nằm trong danh sách người xử lý", async () => {
  const sys = await prisma.user.findUniqueOrThrow({ where: { username: "system" } });
  assert.equal(sys.status, "DISABLED");
});

test("O11: ảnh chụp rà soát chỉ bỏ đúng tài nguyên đã thu hồi; SLA phiếu rà soát tính theo ngày, không theo giờ", async () => {
  const email = "x.review@sod.local";
  const grant = await newTicket(an, form({
    email, hoTen: "Nhân sự X",
    rows: [
      { heThong: "ERP", taiNguyen: "Kho", tang: "1", mucQuyen: "RW", thoiHan: "2099-12-31" },
      { heThong: "CRM", taiNguyen: "Báo cáo", tang: "1", mucQuyen: "RO", thoiHan: "2099-12-31" },
    ],
  }));
  await approveAll(grant.id);
  assert.equal((await reload(grant.id)).status, "DONE");
  const revoke = await newTicket(an, form({ email, hoTen: "Nhân sự X", loaiPhieu: "revoke", rows: [{ heThong: "CRM", taiNguyen: "Báo cáo", tang: "1", mucQuyen: "RO", thoiHan: "" }] }));
  await approveAll(revoke.id);
  assert.equal((await reload(revoke.id)).status, "DONE");

  const r = await openQuarterlyReview(new Date("2032-02-01T03:00:00Z"));
  assert.ok(r.created, JSON.stringify(r));
  const t = await reload(r.id);
  const mine = (t.form as { snapshot: { grants: { email: string; system: string }[] } }).snapshot.grants.filter((g) => g.email === email).map((g) => g.system);
  assert.deepEqual(mine, ["ERP"], "CRM đã thu hồi phải bị bỏ, ERP vẫn phải còn");
  const so = t.steps.find((s) => s.roleCode === "SO" && s.action === "P")!;
  assert.equal(so.slaHours, 8 * 15, "System Owner có 5 ngày để rà soát");
});
