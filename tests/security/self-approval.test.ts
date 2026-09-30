// Test các trò lách luật ở KE_HOACH.md 9.3.4 trên DB sod_test (chạy bằng `npm run test:security`).
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, decideStep, parseForm } from "@/lib/tickets/service";
import { getTicket } from "@/lib/tickets/queries";
import { asUser, current, form, meta, newTicket, reload } from "./helpers";

/** Chờ decideStep bị chặn với thông báo khớp `msg` */
async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message));
}

let an: CurrentUser;
before(async () => {
  an = await asUser("an.nguyen");
});
after(() => prisma.$disconnect());

test("T3: người yêu cầu luôn là người đăng nhập; trường requestor gửi lên bị bỏ qua", async () => {
  const parsed = parseForm({ ...form(), requestor: "ai-do-khac", overrides: { "1-SO-R": "x" } });
  assert.equal("requestor" in parsed, false);
  assert.equal("overrides" in parsed, false);
  const t = await newTicket(an, parsed);
  assert.equal(t.requesterId, an.id);
});

test("Giờ do ứng dụng ghi khớp với now() của DB (không lệch múi giờ)", async () => {
  const t = await newTicket(an);
  const [{ diff }] = await prisma.$queryRaw<{ diff: number }[]>`
    SELECT abs(extract(epoch FROM now() - created_at))::float AS diff FROM tickets WHERE id = ${t.id}::uuid`;
  assert.ok(diff < 60, `created_at lệch ${diff} giây so với now()`);
});

test("T1/T2: người không được giao không duyệt được, kể cả khi tự gửi request", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const outsider = await asUser("minh.ngo");
  await denied(decideStep(outsider, { ticketId: t.id, stepId: step.id, version: t.version, approve: true, comment: "" }, meta), /Không tìm thấy/);
  const otherApprover = await asUser("giang.hoang"); // xem được ticket (CISO có trong chuỗi) nhưng không phải người được giao bước này
  await denied(decideStep(otherApprover, { ticketId: t.id, stepId: step.id, version: t.version, approve: true, comment: "" }, meta), /không phải người được giao/);
});

test("Người yêu cầu không tự duyệt được ticket của mình", async () => {
  // oanh.mai vừa là REQ vừa là Line Manager: hệ thống phải giao bước LM cho người khác
  const oanh = await asUser("oanh.mai");
  const t = await newTicket(oanh);
  const lmStep = t.steps.find((s) => s.roleCode === "LM")!;
  assert.notEqual(lmStep.assigneeId, oanh.id, "không được tự gán người yêu cầu làm người duyệt");
  // Đi tới bước LM rồi thử tự duyệt
  let cur = current(t);
  while (cur.roleCode !== "LM") {
    const who = await prisma.user.findUniqueOrThrow({ where: { id: cur.assigneeId! } });
    const fresh = await reload(t.id);
    await decideStep(await asUser(who.username), { ticketId: t.id, stepId: cur.id, version: fresh.version, approve: true, comment: "" }, meta);
    cur = current(await reload(t.id));
  }
  const fresh = await reload(t.id);
  await denied(decideStep(oanh, { ticketId: t.id, stepId: cur.id, version: fresh.version, approve: true, comment: "" }, meta), /không phải người được giao|Requestor/);
});

test("T8: bấm hai lần / hai tab — phiên bản cũ và bước đã xử lý đều bị chặn", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const assignee = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: step.assigneeId! } })).username);
  await denied(decideStep(assignee, { ticketId: t.id, stepId: step.id, version: t.version + 5, approve: true, comment: "" }, meta), /vừa được cập nhật/);
  await decideStep(assignee, { ticketId: t.id, stepId: step.id, version: t.version, approve: true, comment: "" }, meta);
  const fresh = await reload(t.id);
  await denied(decideStep(assignee, { ticketId: t.id, stepId: step.id, version: fresh.version, approve: true, comment: "" }, meta), /không ở trạng thái chờ/);
});

test("T9: bị rút vai trò thì không duyệt được nữa", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const assignee = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: step.assigneeId! } })).username);
  const role = await prisma.userRole.findFirstOrThrow({ where: { userId: assignee.id, roleCode: step.roleCode } });
  await prisma.userRole.update({ where: { id: role.id }, data: { validTo: new Date() } });
  try {
    // Phiên cũ vẫn nghĩ là còn vai trò → lớp service cho qua, trigger DB phải chặn
    await denied(decideStep(assignee, { ticketId: t.id, stepId: step.id, version: t.version, approve: true, comment: "" }, meta), /không còn giữ vai trò/);
  } finally {
    await prisma.userRole.update({ where: { id: role.id }, data: { validTo: null } });
  }
});

test("Từ chối bắt buộc có lý do; từ chối xong ticket đóng", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const assignee = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: step.assigneeId! } })).username);
  await denied(decideStep(assignee, { ticketId: t.id, stepId: step.id, version: t.version, approve: false, comment: "  " }, meta), /lý do/);
  await decideStep(assignee, { ticketId: t.id, stepId: step.id, version: t.version, approve: false, comment: "Không đủ căn cứ" }, meta);
  assert.equal((await reload(t.id)).status, "REJECTED");
});

test("T11: ghi thẳng vào DB bằng tài khoản ứng dụng cũng bị trigger chặn", async () => {
  const t = await newTicket(an);
  const step = current(t);
  // Người yêu cầu tự chèn quyết định cho bước đang chờ
  await assert.rejects(
    prisma.stepDecision.create({ data: { stepId: step.id, actorId: an.id, outcome: "APPROVE", formHash: t.formHash } }),
    /SoD: người quyết định không phải người được giao/,
  );
  // Đánh dấu bước xong mà không có quyết định
  await assert.rejects(prisma.ticketStep.update({ where: { id: step.id }, data: { status: "DONE" } }), /SoD: bước chưa có quyết định/);
  // Đổi người được giao thành chính mình rồi tự duyệt
  await prisma.ticketStep.update({ where: { id: step.id }, data: { assigneeId: an.id } });
  await assert.rejects(
    prisma.stepDecision.create({ data: { stepId: step.id, actorId: an.id, outcome: "APPROVE", formHash: t.formHash } }),
    /SoD: người quyết định không còn giữ vai trò|SoD: người yêu cầu không được tự/,
  );
  // Sửa nội dung phiếu sau khi gửi
  await assert.rejects(prisma.ticket.update({ where: { id: t.id }, data: { form: { hacked: true } } }), /SoD: nội dung ticket đã gửi không được sửa/);
  // Xoá / sửa quyết định đã có
  const submit = await prisma.stepDecision.findFirstOrThrow({ where: { stepId: t.steps[0].id } });
  await assert.rejects(prisma.stepDecision.delete({ where: { id: submit.id } }), /permission denied|chỉ được ghi thêm/);
});

test("T15: người không liên quan không xem được ticket", async () => {
  const t = await newTicket(an);
  assert.equal(await getTicket(await asUser("minh.ngo"), t.id), null);
  assert.ok(await getTicket(await asUser("nam.dang"), t.id), "Auditor xem được");
});

test("Luồng đầy đủ: mỗi người duyệt đúng bước của mình tới khi hoàn tất, nhật ký nguyên vẹn", async () => {
  const t = await newTicket(an, form({ dlcn: "basic", rows: [{ heThong: "CRM", taiNguyen: "KH", tang: "3", mucQuyen: "RW", thoiHan: "2026-12-31" }] }));
  const actors = new Map<string, string>();
  for (;;) {
    const fresh = await reload(t.id);
    if (fresh.status !== "OPEN") break;
    const step = current(fresh);
    const who = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: step.assigneeId! } })).username);
    assert.notEqual(who.id, an.id, `bước ${step.idx} giao cho chính người yêu cầu`);
    const prevRole = actors.get(who.id);
    assert.ok(!prevRole || prevRole === step.roleCode, `${who.username} xử lý hai vai trò ${prevRole} và ${step.roleCode}`);
    actors.set(who.id, step.roleCode);
    await decideStep(who, { ticketId: t.id, stepId: step.id, version: fresh.version, approve: true, comment: "ok" }, meta);
  }
  const done = await reload(t.id);
  assert.equal(done.status, "DONE");
  assert.ok(done.steps.every((s) => s.status === "DONE"));
  const broken = await prisma.$queryRaw<unknown[]>`SELECT * FROM audit_log_verify()`;
  assert.deepEqual(broken, []);
  const denials = await prisma.auditLog.count({ where: { action: "ticket.decision.denied" } });
  assert.ok(denials > 0, "các lần bị chặn ở test trước phải được ghi nhật ký");
});
