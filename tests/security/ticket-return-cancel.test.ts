// S1 bước 1 (BUILD_PLAN 5.1): trả lại / bổ sung (T01) và huỷ phiếu (T02) trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, cancelTicket, decideStep, returnTicket, reviseTicket } from "@/lib/tickets/service";
import { assigneeOf, asUser, current, form, meta, newTicket, reload } from "./helpers";

async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message), `phải bị chặn: ${msg}`);
}

let an: CurrentUser;
before(async () => {
  an = await asUser("an.nguyen");
});
after(() => prisma.$disconnect());

/** Người được giao bước hiện tại duyệt */
async function approveCurrent(ticketId: string) {
  const t = await reload(ticketId);
  const cur = current(t);
  await decideStep(await assigneeOf(cur), { ticketId, stepId: cur.id, version: t.version, approve: true, comment: "" }, meta);
}

/** Tạo phiếu, SO (bước 1) duyệt, rồi LM (bước 2) trả lại */
async function returnedAtLm(comment = "Cần nêu rõ tài nguyên cụ thể") {
  const t = await newTicket(an);
  await approveCurrent(t.id);
  const t1 = await reload(t.id);
  const lmStep = current(t1);
  assert.equal(lmStep.roleCode, "LM");
  const lm = await assigneeOf(lmStep);
  await returnTicket(lm, { ticketId: t.id, stepId: lmStep.id, version: t1.version, comment }, meta);
  return { id: t.id, lm, lmStepId: lmStep.id, soStepId: t1.steps[1].id };
}

const reviseBy = async (user: CurrentUser, id: string, f = form()) => {
  const t = await reload(id);
  return reviseTicket(user, { ticketId: id, version: t.version, form: f }, meta);
};

test("T01: trả lại → phiếu chờ bổ sung, SLA tạm dừng, không ai quyết định được; lý do là bắt buộc", async () => {
  const t = await newTicket(an);
  await approveCurrent(t.id);
  const t1 = await reload(t.id);
  const lmStep = current(t1);
  const lm = await assigneeOf(lmStep);
  await denied(returnTicket(lm, { ticketId: t.id, stepId: lmStep.id, version: t1.version, comment: "  " }, meta), /Nhập lý do/);
  await returnTicket(lm, { ticketId: t.id, stepId: lmStep.id, version: t1.version, comment: "Thiếu tài nguyên" }, meta);

  const r = await reload(t.id);
  assert.equal(r.status, "RETURNED");
  assert.equal(current(r).dueAt, null, "SLA phải tạm dừng");
  const dec = await prisma.stepDecision.findFirstOrThrow({ where: { stepId: lmStep.id } });
  assert.equal(dec.outcome, "RETURN");
  assert.equal(dec.comment, "Thiếu tài nguyên");
  const note = await prisma.notification.findFirst({ where: { userId: an.id, ticketId: t.id, kind: "RETURNED" } });
  assert.ok(note, "người yêu cầu phải được báo");

  await denied(
    decideStep(lm, { ticketId: t.id, stepId: lmStep.id, version: r.version, approve: true, comment: "" }, meta),
    /chờ người yêu cầu bổ sung/,
  );
});

test("T01: chỉ người đang được giao bước mới trả lại được", async () => {
  const t = await newTicket(an);
  const step = current(t);
  await denied(returnTicket(an, { ticketId: t.id, stepId: step.id, version: t.version, comment: "x" }, meta), /không phải người được giao|Requestor/);
  const other = await asUser("giang.hoang"); // xem được phiếu nhưng không được giao bước này
  await denied(returnTicket(other, { ticketId: t.id, stepId: step.id, version: t.version, comment: "x" }, meta), /không phải người được giao/);
});

test("T01: bổ sung làm đổi phạm vi quyền → phiên bản mới, MỌI bước đã duyệt phải duyệt lại", async () => {
  const { id, lm, soStepId } = await returnedAtLm();
  // Người khác không bổ sung được; phiếu chưa trả lại thì không bổ sung được
  await denied(reviseBy(lm, id, form({ mucDich: "Mục đích mới" })).then((r) => assert.fail(JSON.stringify(r))), /Chỉ người yêu cầu/);

  const r = await reviseBy(an, id, form({ mucDich: "Mục đích đã làm rõ" }));
  assert.ok(r.ok, JSON.stringify(r));
  const t = await reload(id);
  assert.equal(t.status, "OPEN");
  assert.equal(t.rev, 2);
  assert.equal((t.form as { mucDich: string }).mucDich, "Mục đích đã làm rõ");
  assert.equal(await prisma.ticketRevision.count({ where: { ticketId: id } }), 2);
  // Bước 1 (SO) đã duyệt phiên bản cũ nay phải duyệt lại; các bước sau chờ
  assert.deepEqual(t.steps.map((s) => s.status), ["DONE", "CURRENT", "WAITING", "WAITING", "WAITING"]);
  assert.ok(current(t).dueAt, "bước chạy lại có SLA mới");

  // SO duyệt lại: quyết định thứ hai, thuộc rev 2; quyết định cũ vẫn còn
  await approveCurrent(id);
  const decisions = await prisma.stepDecision.findMany({ where: { stepId: soStepId }, orderBy: { rev: "asc" } });
  assert.deepEqual(decisions.map((d) => d.rev), [1, 2]);
  assert.notEqual(decisions[0].formHash, decisions[1].formHash);
});

test("T01: bổ sung chỉ đổi phòng ban / chức danh → giữ các bước đã duyệt, bước trả lại chạy lại", async () => {
  const { id, lm } = await returnedAtLm();
  const r = await reviseBy(an, id, form({ phongBan: "Phòng khác" }));
  assert.ok(r.ok, JSON.stringify(r));
  const t = await reload(id);
  assert.equal(t.rev, 2);
  assert.deepEqual(t.steps.map((s) => s.status), ["DONE", "DONE", "CURRENT", "WAITING", "WAITING"]);
  // LM duyệt tiếp bình thường với phiên bản mới
  await decideStep(lm, { ticketId: id, stepId: current(t).id, version: t.version, approve: true, comment: "" }, meta);
  assert.equal(current(await reload(id)).roleCode, "IAM");
});

test("T01: bổ sung đổi email công vụ (người nhận quyền) → MỌI bước đã duyệt phải duyệt lại", async () => {
  const { id } = await returnedAtLm();
  const r = await reviseBy(an, id, form({ email: "nguoi.khac@company.vn" }));
  assert.ok(r.ok, JSON.stringify(r));
  const t = await reload(id);
  assert.equal(t.rev, 2);
  assert.deepEqual(t.steps.map((s) => s.status), ["DONE", "CURRENT", "WAITING", "WAITING", "WAITING"]);
});

test("T01: gửi lại nội dung y hệt, hoặc bổ sung khi phiếu chưa bị trả lại → bị chặn", async () => {
  const { id } = await returnedAtLm();
  await denied(reviseBy(an, id, form()).then((r) => assert.fail(JSON.stringify(r))), /Chưa có thay đổi/);

  const open = await newTicket(an);
  await denied(reviseBy(an, open.id, form({ mucDich: "Khác" })).then((r) => assert.fail(JSON.stringify(r))), /không ở trạng thái chờ bổ sung/);
});

test("T01: bổ sung làm đổi chuỗi duyệt (thêm DLCN) → phiếu cũ bị huỷ, tạo phiếu mới", async () => {
  const { id } = await returnedAtLm();
  const old = await reload(id);
  const r = await reviseBy(an, id, form({ dlcn: "sensitive", lyDo: "Cần dữ liệu cá nhân để đối soát" }));
  assert.ok(r.ok, JSON.stringify(r));
  assert.ok(r.ok && r.supersededCode);
  assert.notEqual(r.ok && r.id, id);
  const after = await reload(id);
  assert.equal(after.status, "CANCELLED");
  assert.ok(after.closedAt);
  const fresh = await reload(r.ok ? r.id : "");
  assert.equal(fresh.status, "OPEN");
  assert.ok(fresh.steps.some((s) => s.roleCode === "DPO"), "chuỗi mới phải có DPO");
  assert.notEqual(fresh.code, old.code);
});

test("T01: trigger DB — không sửa nội dung phiếu nếu không có bản ghi phiên bản; quyết định cũ không ghi lại được", async () => {
  const { id } = await returnedAtLm();
  await assert.rejects(
    prisma.$executeRaw`UPDATE tickets SET form = jsonb_set(form, '{mucDich}', '"lén sửa"'), form_hash = 'x' WHERE id = ${id}::uuid`,
    /không được sửa/,
  );
  // Phiếu đang chờ bổ sung: DB không nhận thêm quyết định nào, kể cả khi gọi thẳng
  const t = await reload(id);
  const lm = await assigneeOf(current(t));
  await assert.rejects(
    prisma.stepDecision.create({ data: { stepId: current(t).id, actorId: lm.id, outcome: "APPROVE", formHash: t.formHash, rev: 1 } }),
    /chờ người yêu cầu bổ sung/,
  );
});

test("T02: huỷ khi đã tới bước thực hiện → bị chặn ở service và ở DB", async () => {
  const t = await newTicket(an);
  await approveCurrent(t.id); // SO
  await approveCurrent(t.id); // LM → tới IAM (P)
  const r = await reload(t.id);
  assert.equal(current(r).action, "P");
  await denied(cancelTicket(an, { ticketId: t.id, version: r.version, reason: "Đổi ý" }, meta), /đã tới bước thực hiện/);
  await assert.rejects(prisma.$executeRaw`UPDATE tickets SET status = 'CANCELLED' WHERE id = ${t.id}::uuid`, /không huỷ được/);
  assert.equal((await reload(t.id)).status, "OPEN");
});

test("T02: huỷ trước bước thực hiện → đóng phiếu, báo người đang xử lý; người khác hoặc thiếu lý do thì bị chặn", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const assignee = await assigneeOf(step);
  await denied(cancelTicket(assignee, { ticketId: t.id, version: t.version, reason: "Tôi huỷ" }, meta), /Chỉ người yêu cầu/);
  await denied(cancelTicket(an, { ticketId: t.id, version: t.version, reason: " " }, meta), /Nhập lý do/);
  await cancelTicket(an, { ticketId: t.id, version: t.version, reason: "Không còn cần quyền" }, meta);

  const r = await reload(t.id);
  assert.equal(r.status, "CANCELLED");
  assert.ok(r.closedAt);
  const note = await prisma.notification.findFirst({ where: { userId: assignee.id, ticketId: t.id, kind: "CANCELLED" } });
  assert.ok(note, "người đang xử lý phải được báo");
  await denied(decideStep(assignee, { ticketId: t.id, stepId: step.id, version: r.version, approve: true, comment: "" }, meta), /đã đóng/);
  await assert.rejects(prisma.$executeRaw`UPDATE tickets SET status = 'OPEN' WHERE id = ${t.id}::uuid`, /đã đóng/);
});

test("T02: phiếu đang chờ bổ sung vẫn huỷ được nếu chưa tới bước thực hiện", async () => {
  const { id } = await returnedAtLm();
  const t = await reload(id);
  await cancelTicket(an, { ticketId: id, version: t.version, reason: "Bỏ yêu cầu này" }, meta);
  assert.equal((await reload(id)).status, "CANCELLED");
});
