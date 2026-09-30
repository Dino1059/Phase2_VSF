// Thông báo trong app: đúng người nhận, không trùng, không đọc được của người khác.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { decideStep } from "@/lib/tickets/service";
import { listNotifications, markRead, syncSlaNotifications } from "@/lib/notify/service";
import { asUser, assigneeOf, current, meta, newTicket, reload } from "./helpers";

const kinds = async (userId: string, ticketId: string) =>
  (await prisma.notification.findMany({ where: { userId, ticketId }, orderBy: { createdAt: "asc" } })).map((n) => n.kind);

let an: CurrentUser;
before(async () => {
  an = await asUser("an.nguyen");
});
after(() => prisma.$disconnect());

test("gửi phiếu → người được giao bước 1 có việc mới, người nộp không nhận gì", async () => {
  const t = await newTicket(an);
  const step = current(t);
  assert.deepEqual(await kinds(step.assigneeId!, t.id), ["TASK"]);
  assert.deepEqual(await kinds(an.id, t.id), []);
  const [n] = (await listNotifications(step.assigneeId!)).items;
  assert.match(n.message, new RegExp(`${t.code} chờ bạn rà soát \\(System Owner\\)`));
});

test("duyệt → người nộp biết đã duyệt tới đâu, người kế tiếp có việc mới; hoàn tất → báo hoàn tất", async () => {
  const t = await newTicket(an);
  const first = current(t);
  await decideStep(await assigneeOf(first), { ticketId: t.id, stepId: first.id, version: t.version, approve: true, comment: "" }, meta);
  const next = current(await reload(t.id));
  assert.deepEqual(await kinds(an.id, t.id), ["STEP_DONE"]);
  assert.deepEqual(await kinds(next.assigneeId!, t.id), ["TASK"]);
  const [n] = (await listNotifications(an.id)).items.filter((x) => x.ticketId === t.id);
  assert.match(n.message, /System Owner đã duyệt → chờ Line Manager/);

  // Duyệt hết các bước còn lại
  for (let fresh = await reload(t.id); fresh.status === "OPEN"; fresh = await reload(t.id)) {
    const s = current(fresh);
    await decideStep(await assigneeOf(s), { ticketId: t.id, stepId: s.id, version: fresh.version, approve: true, comment: "" }, meta);
  }
  assert.equal((await kinds(an.id, t.id)).at(-1), "DONE");
});

test("từ chối → người nộp nhận thông báo kèm lý do", async () => {
  const t = await newTicket(an);
  const s = current(t);
  await decideStep(await assigneeOf(s), { ticketId: t.id, stepId: s.id, version: t.version, approve: false, comment: "Thiếu căn cứ" }, meta);
  const n = await prisma.notification.findFirstOrThrow({ where: { userId: an.id, ticketId: t.id } });
  assert.equal(n.kind, "REJECTED");
  assert.match(n.message, /bị từ chối bởi .+: Thiếu căn cứ/);
});

test("SLA: sắp hết hạn / quá hạn chỉ báo một lần mỗi mốc", async () => {
  const t = await newTicket(an);
  const s = current(t);
  const hour = 3_600_000;
  // Đã dùng 80% thời gian SLA
  await prisma.ticketStep.update({ where: { id: s.id }, data: { startedAt: new Date(Date.now() - 8 * hour), dueAt: new Date(Date.now() + 2 * hour) } });
  await syncSlaNotifications(s.assigneeId!);
  await syncSlaNotifications(s.assigneeId!);
  assert.deepEqual(await kinds(s.assigneeId!, t.id), ["TASK", "SLA_REMIND"]);
  // Quá hạn
  await prisma.ticketStep.update({ where: { id: s.id }, data: { dueAt: new Date(Date.now() - hour) } });
  await syncSlaNotifications(s.assigneeId!);
  await syncSlaNotifications(s.assigneeId!);
  assert.deepEqual(await kinds(s.assigneeId!, t.id), ["TASK", "SLA_REMIND", "SLA_OVERDUE"]);
  // Người nộp không nhận thông báo SLA của người duyệt
  await syncSlaNotifications(an.id);
  assert.deepEqual(await kinds(an.id, t.id), []);
});

test("không đọc / đánh dấu được thông báo của người khác; ứng dụng không sửa được nội dung", async () => {
  const t = await newTicket(an);
  const s = current(t);
  const [theirs] = await prisma.notification.findMany({ where: { userId: s.assigneeId!, ticketId: t.id } });

  assert.ok(!(await listNotifications(an.id)).items.some((n) => n.id === theirs.id));
  await markRead(an.id, theirs.id);
  assert.equal((await prisma.notification.findUniqueOrThrow({ where: { id: theirs.id } })).readAt, null);

  await markRead(s.assigneeId!, theirs.id);
  assert.ok((await prisma.notification.findUniqueOrThrow({ where: { id: theirs.id } })).readAt);

  await assert.rejects(prisma.notification.update({ where: { id: theirs.id }, data: { message: "giả mạo" } }), /permission denied/);
});

test("tài khoản không có việc (admin) không có thông báo", async () => {
  const admin = await asUser("admin");
  await syncSlaNotifications(admin.id);
  assert.equal((await listNotifications(admin.id)).items.length, 0);
});
