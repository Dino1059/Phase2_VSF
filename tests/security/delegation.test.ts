// S1 bước 2 (BUILD_PLAN 5.1): ủy quyền vắng mặt — T03 và các kiểm tra liên quan, trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, decideStep } from "@/lib/tickets/service";
import { createDelegation, revokeDelegation } from "@/lib/delegations/service";
import { getTicket, listTickets } from "@/lib/tickets/queries";
import { asUser, assigneeOf, current, meta, newTicket, reload } from "./helpers";

async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message), `phải bị chặn: ${msg}`);
}

const DAY = 86_400_000;
const window = (days = 2) => ({ validFrom: new Date(Date.now() - 3_600_000), validTo: new Date(Date.now() + days * DAY) });
const delegate = (from: CurrentUser, to: CurrentUser, roleCode = "LM", w = window()) =>
  createDelegation(from, { roleCode, delegateId: to.id, reason: "Nghỉ phép", ...w }, meta);

let an: CurrentUser, oanh: CurrentUser, binh: CurrentUser, chi: CurrentUser;
before(async () => {
  [an, oanh, binh, chi] = await Promise.all(["an.nguyen", "oanh.mai", "binh.tran", "chi.le"].map(asUser));
  await clean();
});
after(() => prisma.$disconnect());

/** Đóng các phiếu còn mở của những người test dùng, để kiểm xung đột khi tạo ủy quyền không bị phiếu cũ làm nhiễu */
async function clean() {
  await prisma.$executeRaw`UPDATE delegations SET revoked_at = now() WHERE revoked_at IS NULL`;
  await prisma.$executeRaw`
    UPDATE tickets SET status = 'CANCELLED', closed_at = now()
    WHERE status IN ('OPEN','RETURNED')
      AND NOT EXISTS (SELECT 1 FROM ticket_steps s WHERE s.ticket_id = tickets.id AND s.idx > 0 AND s.action = 'P' AND s.status IN ('CURRENT','DONE'))`;
}

async function approveCurrent(ticketId: string) {
  const t = await reload(ticketId);
  const cur = current(t);
  await decideStep(await assigneeOf(cur), { ticketId, stepId: cur.id, version: t.version, approve: true, comment: "" }, meta);
}

/** Phiếu của an, đã duyệt xong bước SO, đang chờ LM. Trả về người LM được giao và người LM còn lại. */
async function waitingAtLm() {
  const t = await newTicket(an);
  await approveCurrent(t.id);
  const r = await reload(t.id);
  const lmStep = current(r);
  assert.equal(lmStep.roleCode, "LM");
  const owner = await assigneeOf(lmStep);
  const other = owner.id === binh.id ? oanh : binh;
  return { id: t.id, lmStep, owner, other };
}

test("T03: ủy quyền cho người khác vai trò, hoặc vai trò mình không giữ → bị chặn", async () => {
  await denied(delegate(binh, chi, "LM"), /cùng vai trò/); // chi.le là DPO, không giữ LM
  await denied(delegate(binh, oanh, "DPO"), /không giữ vai trò/); // binh không giữ DPO
  await denied(delegate(an, oanh, "REQ"), /không có bước xử lý/);
  await denied(delegate(binh, binh, "LM"), /chính mình/);
  // DB cũng chặn khi gọi thẳng, không qua service
  await assert.rejects(
    prisma.delegation.create({ data: { delegatorId: binh.id, delegateId: chi.id, roleCode: "LM", reason: "x", ...window() } }),
    /cùng vai trò/,
  );
});

test("T03: người nhận xung đột SoD với phiếu đang mở của người ủy quyền → bị chặn", async () => {
  // oanh vừa là REQ vừa là LM: phiếu của oanh có bước LM giao cho người khác (binh)
  const t = await newTicket(oanh);
  const lm = t.steps.find((s) => s.roleCode === "LM")!;
  assert.equal(lm.assigneeId, binh.id);
  await denied(delegate(binh, oanh), /xung đột SoD.*SOD-/);
  assert.equal(await prisma.delegation.count({ where: { delegatorId: binh.id, delegateId: oanh.id } }), 0);
  await clean();
});

test("T03: thời hạn: kết thúc trước bắt đầu, đã qua, hoặc dài quá mức → bị chặn", async () => {
  await denied(delegate(binh, oanh, "LM", { validFrom: new Date(Date.now() + DAY), validTo: new Date(Date.now()) }), /sau ngày bắt đầu/);
  await denied(delegate(binh, oanh, "LM", { validFrom: new Date(Date.now() - 3 * DAY), validTo: new Date(Date.now() - DAY) }), /đã qua/);
  await denied(delegate(binh, oanh, "LM", window(400)), /tối đa/i);
});

test("T03: người nhận được ủy quyền duyệt thay, quyết định ghi 'thay mặt', người nhận thấy việc trong Hộp việc", async () => {
  await clean();
  const { id, lmStep, owner, other } = await waitingAtLm();
  const before = await listTickets(other, "inbox");
  assert.ok(!before.some((t) => t.id === id), "chưa ủy quyền thì chưa thấy việc");

  await delegate(owner, other);
  const inbox = await listTickets(other, "inbox");
  assert.ok(inbox.some((t) => t.id === id), "người nhận thấy việc của người ủy quyền");
  assert.ok(await getTicket(other, id), "người nhận xem được phiếu");

  const t = await reload(id);
  await decideStep(other, { ticketId: id, stepId: lmStep.id, version: t.version, approve: true, comment: "Duyệt thay" }, meta);
  const dec = await prisma.stepDecision.findFirstOrThrow({ where: { stepId: lmStep.id } });
  assert.equal(dec.actorId, other.id);
  assert.equal(dec.onBehalfOfId, owner.id, "trigger DB tự điền người được giao");
  assert.equal(current(await reload(id)).roleCode, "IAM", "phiếu đi tiếp");
  const log = await prisma.auditLog.findFirstOrThrow({ where: { targetId: id, action: "ticket.step.approved" }, orderBy: { id: "desc" } });
  assert.equal((log.details as { onBehalfOf?: string }).onBehalfOf, owner.id);
});

test("T03: ủy quyền đã thu hồi hoặc hết hạn thì không duyệt thay được; DB cũng chặn", async () => {
  await clean();
  const { id, lmStep, owner, other } = await waitingAtLm();
  await delegate(owner, other);
  const d = await prisma.delegation.findFirstOrThrow({ where: { delegatorId: owner.id, delegateId: other.id, revokedAt: null } });
  await revokeDelegation(owner, d.id, meta);
  const t = await reload(id);
  await denied(decideStep(other, { ticketId: id, stepId: lmStep.id, version: t.version, approve: true, comment: "" }, meta), /Không tìm thấy ticket/); // hết ủy quyền thì cũng không còn xem được phiếu
  await assert.rejects(
    prisma.stepDecision.create({ data: { stepId: lmStep.id, actorId: other.id, outcome: "APPROVE", formHash: t.formHash, rev: t.rev } }),
    /không phải người được giao/,
  );
  // Người khác không thu hồi hộ được, và ủy quyền đã thu hồi không sửa lại được
  await denied(revokeDelegation(other, d.id, meta), /Không tìm thấy ủy quyền/);
  await assert.rejects(prisma.$executeRaw`UPDATE delegations SET revoked_at = NULL WHERE id = ${d.id}::uuid`, /đã thu hồi/);
  await assert.rejects(prisma.$executeRaw`UPDATE delegations SET valid_to = valid_to + interval '30 days' WHERE id = ${d.id}::uuid`); // tài khoản ứng dụng chỉ được đặt revoked_at
  // Hết hạn: đặt valid_to về quá khứ trực tiếp không được (không sửa được), nên kiểm bằng ủy quyền chưa tới hạn
  const future = await (async () => {
    await delegate(owner, other, "LM", { validFrom: new Date(Date.now() + DAY), validTo: new Date(Date.now() + 3 * DAY) });
    return prisma.delegation.findFirstOrThrow({ where: { delegatorId: owner.id, delegateId: other.id, revokedAt: null } });
  })();
  assert.ok(future.validFrom > new Date());
  await denied(decideStep(other, { ticketId: id, stepId: lmStep.id, version: t.version, approve: true, comment: "" }, meta), /Không tìm thấy ticket/);
});

test("T03: ủy quyền không cho người nhận duyệt phiếu của chính mình (kiểm lại lúc duyệt)", async () => {
  await clean();
  // Ủy quyền binh → oanh được tạo khi chưa có phiếu nào xung đột
  await delegate(binh, oanh);
  // Sau đó oanh lập phiếu: bước LM giao cho binh. oanh giờ vừa là người lập vừa là người được ủy quyền
  const t = await newTicket(oanh);
  await approveCurrent(t.id); // SO
  const r = await reload(t.id);
  const lm = current(r);
  assert.equal(lm.roleCode, "LM");
  assert.equal(lm.assigneeId, binh.id);
  await denied(decideStep(oanh, { ticketId: t.id, stepId: lm.id, version: r.version, approve: true, comment: "" }, meta), /Requestor|tự duyệt/);
  await assert.rejects(
    prisma.stepDecision.create({ data: { stepId: lm.id, actorId: oanh.id, outcome: "APPROVE", formHash: r.formHash, rev: r.rev } }),
    /người yêu cầu không được tự/,
  );
  await clean();
});
