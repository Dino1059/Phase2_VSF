// S1 bước 5 (BUILD_PLAN 5.1): SLA chạy nền — T06, T07 trên DB sod_test. Gọi thẳng processSla (không cần pg-boss).
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, decideStep, expireTicket } from "@/lib/tickets/service";
import { processSla } from "@/lib/sla/service";
import { createDelegation } from "@/lib/delegations/service";
import { asUser, assigneeOf, current, meta, newTicket, ownerDb, reload } from "./helpers";

async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message), `phải bị chặn: ${msg}`);
}

const HOUR = 3_600_000;
const owner = ownerDb();
let an: CurrentUser, admin: CurrentUser, ciso: CurrentUser, aud: CurrentUser;
before(async () => {
  [an, admin, ciso, aud] = await Promise.all(["an.nguyen", "admin", "giang.hoang", "nam.dang"].map(asUser));
});
after(async () => {
  await owner.$disconnect();
  await prisma.$disconnect();
});

/** Đặt bước hiện tại đã dùng `pct`% SLA (giả lập thời gian trôi qua bằng tài khoản chủ sở hữu) */
async function age(ticketId: string, pct: number, slaHours = 24) {
  const step = current(await reload(ticketId));
  const due = new Date(Date.now() + ((100 - pct) / 100) * slaHours * HOUR);
  const started = new Date(due.getTime() - slaHours * HOUR);
  await owner.ticketStep.update({ where: { id: step.id }, data: { startedAt: started, dueAt: due } });
  return step;
}
const notes = (userId: string, ticketId: string, kind: string) => prisma.notification.count({ where: { userId, ticketId, kind: kind as never } });
const events = (ticketId: string) => prisma.slaEvent.findMany({ where: { ticketId }, orderBy: { createdAt: "asc" } });

test("T06: nhắc ở 75%, quá hạn ở 100%, nghiêm trọng ở 200%; mỗi mốc chỉ báo một lần dù job chạy lại nhiều lần", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const assignee = await assigneeOf(step);
  assert.equal(step.roleCode, "SO");

  await age(t.id, 50);
  await processSla();
  assert.equal((await events(t.id)).length, 0, "chưa tới 75% thì không có mốc nào");

  await age(t.id, 80);
  await processSla();
  await processSla(); // chạy lại: không báo trùng
  assert.deepEqual((await events(t.id)).map((e) => e.level), ["REMIND"]);
  assert.equal(await notes(assignee.id, t.id, "SLA_REMIND"), 1);

  await age(t.id, 110);
  await processSla();
  await processSla();
  assert.deepEqual((await events(t.id)).map((e) => e.level), ["REMIND", "OVERDUE"]);
  assert.equal(await notes(assignee.id, t.id, "SLA_OVERDUE"), 1, "người được giao được báo quá hạn một lần");
  // Người dự phòng: người còn lại giữ vai trò System Owner. Admin cũng được báo.
  const backup = await prisma.user.findFirstOrThrow({ where: { id: { not: assignee.id }, roles: { some: { roleCode: "SO" } } } });
  assert.equal(await notes(backup.id, t.id, "SLA_OVERDUE"), 1, "người dự phòng cùng vai trò được báo");
  assert.equal(await notes(admin.id, t.id, "SLA_OVERDUE"), 1, "Admin được báo");
  assert.equal(await notes(an.id, t.id, "SLA_OVERDUE"), 0, "người yêu cầu không phải người dự phòng");
  assert.equal(await notes(ciso.id, t.id, "SLA_OVERDUE"), 0, "chưa tới 200%, chưa báo CISO");

  await age(t.id, 250);
  await processSla();
  await processSla();
  assert.deepEqual((await events(t.id)).map((e) => e.level), ["REMIND", "OVERDUE", "CRITICAL"]);
  assert.equal(await notes(ciso.id, t.id, "SLA_OVERDUE"), 1, "CISO được báo ở mốc nghiêm trọng");
  assert.equal(await notes(aud.id, t.id, "SLA_OVERDUE"), 1, "Auditor được báo ở mốc nghiêm trọng");
  const log = await prisma.auditLog.count({ where: { action: "sla.critical", targetId: t.id } });
  assert.equal(log, 1, "ghi nhận vào nhật ký đúng một lần");
});

test("T06: nhảy thẳng qua nhiều mốc → ghi đủ các mốc đã qua, nhưng không báo 'sắp hết hạn' khi đã quá hạn", async () => {
  const t = await newTicket(an);
  const assignee = await assigneeOf(current(t));
  await age(t.id, 130);
  await processSla();
  assert.deepEqual((await events(t.id)).map((e) => e.level).sort(), ["OVERDUE", "REMIND"]);
  assert.equal(await notes(assignee.id, t.id, "SLA_REMIND"), 0);
  assert.equal(await notes(assignee.id, t.id, "SLA_OVERDUE"), 1);
});

test("T06: phiếu đã đóng thì không còn mốc SLA", async () => {
  const closed = await newTicket(an);
  await age(closed.id, 300);
  const t0 = await reload(closed.id);
  const assignee = await assigneeOf(current(t0));
  await decideStep(assignee, { ticketId: closed.id, stepId: current(t0).id, version: t0.version, approve: false, comment: "Từ chối" }, meta);
  await processSla();
  assert.equal((await events(closed.id)).length, 0, "phiếu đã đóng không có mốc SLA");
});

test("T07: quá hạn bao lâu cũng không tự duyệt; quá số ngày cấu hình thì chỉ báo Admin, Admin đóng 'hết hạn' có lý do", async () => {
  const t = await newTicket(an);
  const step = await age(t.id, 10000, 24); // 10000% SLA 24 giờ ≈ 100 ngày
  const before = await reload(t.id);
  const decisionsBefore = await prisma.stepDecision.count({ where: { step: { ticketId: t.id } } });
  await processSla();
  await processSla();
  const lv = (await events(t.id)).map((e) => e.level).sort();
  assert.deepEqual(lv, ["CRITICAL", "OVERDUE", "REMIND", "STALE"]);

  // Không có đường nào tự duyệt, từ chối hay chuyển bước
  const after = await reload(t.id);
  assert.equal(after.status, "OPEN");
  assert.equal(after.version, before.version);
  assert.equal(current(after).id, step.id);
  assert.equal(await prisma.stepDecision.count({ where: { step: { ticketId: t.id } } }), decisionsBefore);
  assert.ok(await prisma.notification.findFirst({ where: { userId: admin.id, ticketId: t.id, message: { contains: 'đóng phiếu "hết hạn"' } } }), "Admin được báo có thể đóng hết hạn");

  // Chỉ Admin, và phải có lý do
  const assignee = await assigneeOf(step);
  await denied(expireTicket(assignee, { ticketId: t.id, version: after.version, reason: "Quá hạn" }, meta), /Chỉ Quản trị SoD/);
  await denied(expireTicket(an, { ticketId: t.id, version: after.version, reason: "Quá hạn" }, meta), /Chỉ Quản trị SoD/);
  await denied(expireTicket(admin, { ticketId: t.id, version: after.version, reason: "  " }, meta), /Nhập lý do/);
  await expireTicket(admin, { ticketId: t.id, version: after.version, reason: "Không ai xử lý quá 7 ngày" }, meta);

  const closed = await reload(t.id);
  assert.equal(closed.status, "EXPIRED");
  assert.ok(closed.closedAt);
  assert.equal(await prisma.stepDecision.count({ where: { step: { ticketId: t.id } } }), decisionsBefore, "đóng không ghi quyết định nào");
  assert.ok(await prisma.notification.findFirst({ where: { userId: an.id, ticketId: t.id, kind: "EXPIRED" } }), "người yêu cầu được báo");
  await denied(decideStep(assignee, { ticketId: t.id, stepId: step.id, version: closed.version, approve: true, comment: "" }, meta), /đã đóng/);
  await assert.rejects(prisma.$executeRaw`UPDATE tickets SET status = 'OPEN' WHERE id = ${t.id}::uuid`, /đã đóng/);
});

test("T07: chưa đủ số ngày thì Admin chưa đóng hết hạn được, kể cả ghi thẳng DB", async () => {
  const t = await newTicket(an);
  await age(t.id, 300); // quá hạn nhưng mới chờ ≈ 3 ngày
  const r = await reload(t.id);
  await denied(expireTicket(admin, { ticketId: t.id, version: r.version, reason: "Quá hạn" }, meta), /chưa đủ 7 ngày/);
  await assert.rejects(prisma.$executeRaw`UPDATE tickets SET status = 'EXPIRED' WHERE id = ${t.id}::uuid`, /chưa đủ số ngày/);
  assert.equal((await reload(t.id)).status, "OPEN");
});

test("T06: người đang được ủy quyền cũng được nhắc và báo quá hạn", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const owner0 = await assigneeOf(step);
  const other = await asUser(owner0.username === "dung.pham" ? "son.ho" : "dung.pham");
  await createDelegation(owner0, { roleCode: "SO", delegateId: other.id, reason: "Nghỉ phép", validFrom: new Date(Date.now() - HOUR), validTo: new Date(Date.now() + 48 * HOUR) }, meta);
  await age(t.id, 80);
  await processSla();
  assert.equal(await notes(other.id, t.id, "SLA_REMIND"), 1, "người nhận ủy quyền được nhắc");
  await age(t.id, 120);
  await processSla();
  assert.equal(await notes(other.id, t.id, "SLA_OVERDUE"), 1, "người nhận ủy quyền được báo quá hạn");
});
