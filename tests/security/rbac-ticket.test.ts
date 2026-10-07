// S1 bước 3 (BUILD_PLAN 5.1): vai trò chỉ được ghi vào user_roles khi phiếu RBAC hoàn tất — T05, trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, createRbacTicket, decideStep } from "@/lib/tickets/service";
import { approveCurrent, asUser, assigneeOf, current, meta, reload } from "./helpers";

async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message), `phải bị chặn: ${msg}`);
}

let an: CurrentUser, minh: CurrentUser, giang: CurrentUser, ha: CurrentUser;
before(async () => {
  // Người nhận vai trò dùng riêng cho file này, để không ảnh hưởng test khác
  if (!(await prisma.user.findUnique({ where: { username: "rbac.target" } }))) {
    const u = await prisma.user.create({ data: { username: "rbac.target", email: "rbac.target@sod.local", fullName: "Người Nhận Vai Trò", passwordHash: "x", status: "ACTIVE" } });
    await prisma.userRole.create({ data: { userId: u.id, roleCode: "REQ", note: "Tự cấp khi xác nhận email" } });
  }
  [an, minh, giang, ha] = await Promise.all(["an.nguyen", "rbac.target", "giang.hoang", "ha.vu"].map(asUser));
});
after(() => prisma.$disconnect());

const request = (user: CurrentUser, target: CurrentUser, roleCode: string, op: "grant" | "revoke" = "grant", validTo = "") =>
  createRbacTicket(user, { op, targetUserId: target.id, roleCode: roleCode as never, validTo, reason: "Cần cho dự án" }, meta);

const activeRole = (userId: string, roleCode: string) =>
  prisma.userRole.findFirst({ where: { userId, roleCode, validFrom: { lte: new Date() }, OR: [{ validTo: null }, { validTo: { gt: new Date() } }] } });

/** Duyệt tới hết chuỗi, trả về người thực hiện bước cuối */
async function runToEnd(id: string) {
  let last: CurrentUser | undefined;
  for (let i = 0; i < 10; i++) {
    const t = await reload(id);
    if (t.status !== "OPEN") break;
    last = await approveCurrent(id);
  }
  return last!;
}

test("T05: phiếu RBAC có chuỗi Release Manager → System Owner → CISO → IAM, người được cấp không nằm trong chuỗi", async () => {
  const r = await request(an, ha, "REL"); // ha.vu là IAM: bị loại khỏi người xử lý
  assert.ok(r.ok, JSON.stringify(r));
  const t = await reload(r.ok ? r.id : "");
  assert.deepEqual(t.steps.map((s) => s.roleCode), ["REQ", "REL", "SO", "CISO", "IAM"]);
  assert.ok(t.steps.every((s) => s.assigneeId !== ha.id), "người được cấp không được giữ bước nào");
  assert.equal(t.typeId, "rbac");
});

test("T05: cấp vai trò chỉ có hiệu lực khi IAM hoàn tất; ghi kèm mã phiếu và người cấp", async () => {
  assert.equal(await activeRole(minh.id, "DEV"), null);
  const r = await request(an, minh, "DEV", "grant", "2099-12-31");
  assert.ok(r.ok, JSON.stringify(r));
  const id = r.ok ? r.id : "";
  // Chưa hoàn tất thì chưa có vai trò
  await approveCurrent(id);
  assert.equal(await activeRole(minh.id, "DEV"), null);
  const iam = await runToEnd(id);
  assert.equal(iam.username === "ha.vu" || iam.username === "phong.ta", true);
  const t = await reload(id);
  assert.equal(t.status, "DONE");
  const role = await activeRole(minh.id, "DEV");
  assert.ok(role, "vai trò phải được ghi khi phiếu hoàn tất");
  assert.equal(role.ticketId, id);
  assert.equal(role.grantedById, iam.id);
  assert.ok(role.validTo && role.validTo.getFullYear() === 2099);
  assert.ok(await prisma.notification.findFirst({ where: { userId: minh.id, kind: "ROLE_CHANGED" } }), "người được cấp phải được báo");
  const log = await prisma.auditLog.findFirst({ where: { action: "rbac.role.granted", targetId: minh.id } });
  assert.ok(log);

  // Đã giữ vai trò thì không xin cấp lại
  const again = await request(an, minh, "DEV");
  assert.ok(!again.ok && /đã giữ vai trò/.test(again.errors[0][1]));
});

test("T05: thu hồi vai trò qua phiếu RBAC → đặt hạn, ghi mã phiếu thu hồi", async () => {
  const r = await request(an, minh, "DEV", "revoke");
  assert.ok(r.ok, JSON.stringify(r));
  const id = r.ok ? r.id : "";
  await runToEnd(id);
  assert.equal(await activeRole(minh.id, "DEV"), null);
  const row = await prisma.userRole.findFirstOrThrow({ where: { userId: minh.id, roleCode: "DEV", revokedTicketId: id } });
  assert.ok(row.validTo);
  const again = await request(an, minh, "DEV", "revoke");
  assert.ok(!again.ok && /không giữ vai trò/.test(again.errors[0][1]));
});

test("T05: người được cấp là người duy nhất giữ một vai trò duyệt → không có chuỗi hợp lệ, không có ngoại lệ", async () => {
  const r = await request(an, giang, "AUD"); // giang.hoang là CISO duy nhất
  assert.ok(!r.ok && /Không có người nào đủ điều kiện/.test(r.errors[0][1]), JSON.stringify(r));
});

test("T05: IAM tự hoàn tất phiếu cấp vai trò cho chính mình → bị chặn ở service và ở DB", async () => {
  const r = await request(an, ha, "DPO");
  assert.ok(r.ok, JSON.stringify(r));
  const id = r.ok ? r.id : "";
  // Giả lập bị tấn công: ai đó đổi người được giao bước IAM thành chính người được cấp
  const t0 = await reload(id);
  const iamStep = t0.steps.find((s) => s.roleCode === "IAM")!;
  await prisma.ticketStep.update({ where: { id: iamStep.id }, data: { assigneeId: ha.id } });
  while (current(await reload(id)).roleCode !== "IAM") await approveCurrent(id);
  const t = await reload(id);
  await denied(decideStep(ha, { ticketId: id, stepId: iamStep.id, version: t.version, approve: true, comment: "" }, meta), /không được xử lý phiếu/);
  await assert.rejects(
    prisma.stepDecision.create({ data: { stepId: iamStep.id, actorId: ha.id, outcome: "COMPLETE", formHash: t.formHash, rev: t.rev } }),
    /người được cấp vai trò không được xử lý/,
  );
  assert.equal(await activeRole(ha.id, "DPO"), null, "không được ghi vai trò");
});

test("T05: ghi thẳng user_roles bằng tài khoản ứng dụng → trigger DB chặn nếu không có phiếu hợp lệ", async () => {
  const roleFor = (data: object) => prisma.userRole.create({ data: { userId: minh.id, roleCode: "CISO", ...data } as never });
  // Không có phiếu
  await assert.rejects(roleFor({}), /chỉ được cấp qua phiếu RBAC/);
  // Phiếu chưa hoàn tất
  const open = await request(an, minh, "AUD");
  assert.ok(open.ok);
  const openId = open.ok ? open.id : "";
  await assert.rejects(prisma.userRole.create({ data: { userId: minh.id, roleCode: "AUD", ticketId: openId, grantedById: ha.id } }), /chưa hoàn tất/);
  // Phiếu đã hoàn tất cho người / vai trò khác, hoặc cấp lại bằng phiếu cũ cho vai trò khác
  const done = await request(an, minh, "DEV");
  assert.ok(done.ok);
  const doneId = done.ok ? done.id : "";
  const executor = await runToEnd(doneId);
  await assert.rejects(prisma.userRole.create({ data: { userId: minh.id, roleCode: "CISO", ticketId: doneId, grantedById: executor.id } }), /không khớp/);
  await assert.rejects(prisma.userRole.create({ data: { userId: an.id, roleCode: "DEV", ticketId: doneId, grantedById: executor.id } }), /không khớp/);
  // Phiếu đã dùng rồi: DB chỉ cho một bản ghi mỗi phiếu
  await assert.rejects(prisma.userRole.create({ data: { userId: minh.id, roleCode: "DEV", ticketId: doneId, grantedById: executor.id } }));
  // Thu hồi không phiếu, sửa trường khác
  const row = await prisma.userRole.findFirstOrThrow({ where: { userId: minh.id, roleCode: "DEV", ticketId: doneId } });
  await assert.rejects(prisma.userRole.update({ where: { id: row.id }, data: { validTo: new Date() } }), /chỉ được thu hồi qua phiếu RBAC/);
  await assert.rejects(prisma.userRole.update({ where: { id: row.id }, data: { roleCode: "CISO" } }), /không được sửa bản ghi vai trò/);
  // Thu hồi dọn lại cho các test sau
  const rev = await request(an, minh, "DEV", "revoke");
  assert.ok(rev.ok);
  await runToEnd(rev.ok ? rev.id : "");
  assert.equal(await activeRole(minh.id, "DEV"), null);
});

test("T05: REQ vẫn tự có khi xác nhận email (không cần phiếu); các vai trò khác thì không", async () => {
  const u = await prisma.user.create({ data: { username: "reg.test", email: "reg.test@sod.local", fullName: "Reg Test", passwordHash: "x", status: "ACTIVE" } });
  await prisma.userRole.create({ data: { userId: u.id, roleCode: "REQ", note: "Tự cấp khi xác nhận email" } });
  await assert.rejects(prisma.userRole.create({ data: { userId: u.id, roleCode: "LM", note: "tự cấp" } }), /chỉ được cấp qua phiếu RBAC/);
  await assert.rejects(prisma.userRole.create({ data: { userId: u.id, roleCode: "REQ", grantedById: ha.id } }), /chỉ được cấp qua phiếu RBAC/);
});

test("T05: phiếu RBAC không trả lại để bổ sung được", async () => {
  const r = await request(an, minh, "REL");
  assert.ok(r.ok);
  const t = await reload(r.ok ? r.id : "");
  const step = current(t);
  const who = await assigneeOf(step);
  const { returnTicket } = await import("@/lib/tickets/service");
  await denied(returnTicket(who, { ticketId: t.id, stepId: step.id, version: t.version, comment: "x" }, meta), /không trả lại để bổ sung được/);
});
