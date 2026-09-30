import "server-only";
import { createHash } from "node:crypto";
import { prisma, type Tx } from "@/lib/db";
import { AuditAction, writeAudit, type RequestMeta } from "@/lib/audit";
import type { CurrentUser } from "@/lib/auth/session";
import { canSubmitTicket, canViewTicket, decisionBlockers } from "@/lib/authz/policy";
import { EXCEPTION_ACTIVITY, ROLES, ROLE_KEYS, SOD_CONFIG, VERB, type RoleKey, type StepAction } from "@/lib/sod/catalog";
import { buildChain, slaHours, type Chain, type Phase } from "@/lib/sod/chain";
import { conflictsFor, violations, type Person } from "@/lib/sod/conflicts";
import { notify } from "@/lib/notify/service";
import { LOAI_PHIEU, TicketFormSchema, formPriority, rowFilled, validateForm, type TicketForm } from "@/lib/sod/form";

/** Lỗi nghiệp vụ hiển thị được cho người dùng */
export class TicketError extends Error {}

const HOUR = 3_600_000;
const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");

/** Người dùng đang hoạt động kèm vai trò còn hiệu lực — ứng viên để tự gán. Thứ tự: tài khoản tạo trước ưu tiên trước. */
async function activePeople(tx: Tx = prisma): Promise<Person[]> {
  const now = new Date();
  const users = await tx.user.findMany({
    where: { status: "ACTIVE" },
    orderBy: { createdAt: "asc" },
    select: {
      id: true,
      fullName: true,
      roles: {
        where: { validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] },
        select: { roleCode: true },
      },
    },
  });
  const known = new Set<string>(ROLE_KEYS);
  return users.map((u) => ({
    id: u.id,
    name: u.fullName,
    roles: u.roles.map((r) => r.roleCode).filter((c): c is RoleKey => known.has(c)),
  }));
}

/** Parse dữ liệu phiếu từ trình duyệt (không tin kiểu dữ liệu gửi lên). */
export function parseForm(input: unknown): TicketForm {
  const parsed = TicketFormSchema.safeParse(input);
  if (!parsed.success) throw new TicketError("Dữ liệu phiếu không hợp lệ.");
  return parsed.data;
}

// ---------------------------------------------------------------- Xem trước

type PreviewStep = {
  role: RoleKey;
  action: Chain["steps"][number]["action"];
  phase: number;
  merged: number;
  slaHours: number | null;
  conflicts: string[];
};
export type Preview = { acts: number[]; reasons: string[]; phases: Phase[]; steps: PreviewStep[]; violations: number };

/** Chuỗi xử lý dự kiến — chỉ để xem, không lưu. Không trả về người được gán. */
export async function previewTicket(user: CurrentUser, form: TicketForm): Promise<Preview> {
  const chain = buildChain(form, user.id, await activePeople());
  const factor = SOD_CONFIG.priority[formPriority(form)];
  return {
    acts: chain.classification.acts,
    reasons: chain.classification.reasons,
    phases: chain.phases,
    steps: chain.steps.map((s, i) => ({
      role: s.role,
      action: s.action,
      phase: s.phase,
      merged: s.acts.length,
      slaHours: i === 0 ? null : slaHours(s, factor),
      conflicts: i === 0 ? [] : conflictsFor(chain, i, s.assignee),
    })),
    violations: violations(chain).length,
  };
}

// ---------------------------------------------------------------- Gửi phiếu

type SubmitResult = { ok: true; id: string } | { ok: false; errors: [string, string][] };

export async function submitTicket(user: CurrentUser, form: TicketForm, meta: RequestMeta): Promise<SubmitResult> {
  if (!canSubmitTicket(user)) throw new TicketError("Bạn không có vai trò Requestor để tạo phiếu.");
  const errors = validateForm(form);
  if (errors.length) return { ok: false, errors };

  return prisma.$transaction(async (tx) => {
    const chain = buildChain(form, user.id, await activePeople(tx));
    const v = violations(chain);
    if (chain.steps.some((s, i) => i > 0 && !s.assignee)) {
      return { ok: false, errors: [["", "Không có người nào giữ vai trò cần thiết cho một bước. Liên hệ quản trị."]] };
    }
    if (v.length && !form.exception) {
      return { ok: false, errors: [["exception", "Phiếu vi phạm SoD — cần xin ngoại lệ SoD"]] };
    }
    const waived = new Set(v.map((x) => x.i));
    if (chain.steps.some((s, i) => waived.has(i) && s.acts.includes(EXCEPTION_ACTIVITY))) {
      return { ok: false, errors: [["exception", "Không thể xin ngoại lệ cho chính bước phê duyệt ngoại lệ."]] };
    }

    const cl = chain.classification;
    const [{ code }] = await tx.$queryRaw<{ code: string }[]>`SELECT next_ticket_code() AS code`;
    const systems = [...new Set(form.rows.filter(rowFilled).map((r) => r.heThong.trim()))].join(", ");
    const snapshot = { ...form, rows: form.rows.filter(rowFilled) };
    const formHash = sha256(JSON.stringify(snapshot));
    const priority = formPriority(form);
    const now = new Date();

    const ticket = await tx.ticket.create({
      data: {
        code,
        requesterId: user.id,
        typeId: cl.type.id,
        title: `${LOAI_PHIEU[form.loaiPhieu as keyof typeof LOAI_PHIEU]} quyền – ${form.hoTen.trim()} – ${systems}`.slice(0, 300),
        system: systems.slice(0, 500),
        priority,
        level: cl.level,
        pii: cl.pii,
        breakGlass: cl.breakGlass,
        acts: cl.acts,
        reasons: cl.reasons,
        phases: chain.phases,
        form: snapshot,
        formHash,
        conflicts: [...new Set(v.map((x) => x.c))],
        exceptionId: form.exception ? `SoD-EX-${code.slice(4)}` : null,
        steps: {
          create: chain.steps.map((s, i) => ({
            idx: i,
            phase: s.phase,
            key: s.key,
            roleCode: s.role,
            action: s.action,
            acts: s.acts.map(String),
            assigneeId: s.assignee,
            sodWaived: waived.has(i),
            breakGlass: Boolean(s.breakGlass),
            status: i === 0 ? "CURRENT" : "WAITING",
            slaHours: i === 0 ? null : slaHours(s, SOD_CONFIG.priority[priority]),
            startedAt: i === 0 ? now : null,
          })),
        },
      },
      include: { steps: { orderBy: { idx: "asc" } } },
    });

    // Bước 0: người yêu cầu gửi phiếu — cũng đi qua trigger kiểm quyết định
    const [first, next] = ticket.steps;
    await tx.stepDecision.create({ data: { stepId: first.id, actorId: user.id, outcome: "SUBMIT", formHash } });
    await tx.ticketStep.update({ where: { id: first.id }, data: { status: "DONE" } });
    await startStep(tx, ticket, next);
    await writeAudit(
      {
        action: AuditAction.TicketSubmitted,
        actorUserId: user.id,
        actorEmail: user.email,
        targetType: "ticket",
        targetId: ticket.id,
        details: { code, acts: cl.acts, steps: ticket.steps.length, exception: ticket.exceptionId, conflicts: ticket.conflicts },
        meta,
      },
      tx,
    );
    return { ok: true, id: ticket.id } as const;
  });
}

type StepRef = { id: string; roleCode: string; action: StepAction; assigneeId: string | null; slaHours: number | null };
const roleName = (code: string) => ROLES[code as RoleKey]?.name ?? code;

/** Chuyển bước sang Đang xử lý, đặt hạn SLA và báo cho người được giao. */
async function startStep(tx: Tx, ticket: { id: string; code: string }, step: StepRef) {
  const now = new Date();
  await tx.ticketStep.update({
    where: { id: step.id },
    data: { status: "CURRENT", startedAt: now, dueAt: new Date(now.getTime() + step.slaHours! * HOUR) },
  });
  if (step.assigneeId) {
    await notify(tx, [{
      userId: step.assigneeId,
      ticketId: ticket.id,
      kind: "TASK",
      level: "info",
      message: `${ticket.code} chờ bạn ${VERB[step.action].toLowerCase()} (${roleName(step.roleCode)}) — SLA ${step.slaHours}h`,
      dedupeKey: `task:${step.id}`,
    }]);
  }
}

// ---------------------------------------------------------------- Quyết định một bước

type Decision = { ticketId: string; stepId: string; version: number; approve: boolean; comment: string };

/**
 * Duyệt / hoàn tất / từ chối bước đang xử lý. Người quyết định LUÔN là người đăng nhập.
 * Kiểm theo thứ tự: khoá ticket → quyền xem → phiên bản → quyền quyết định + SoD → trigger DB.
 */
export async function decideStep(user: CurrentUser, d: Decision, meta: RequestMeta): Promise<void> {
  const comment = d.comment.trim().slice(0, 2000);
  try {
    await prisma.$transaction(async (tx) => {
      // Khoá dòng ticket: hai người / hai tab bấm cùng lúc sẽ xếp hàng
      await tx.$queryRaw`SELECT id FROM tickets WHERE id = ${d.ticketId}::uuid FOR UPDATE`;
      const t = await tx.ticket.findUnique({ where: { id: d.ticketId }, include: { steps: { orderBy: { idx: "asc" } } } });
      const ticket = t && { ...t, phases: t.phases as Phase[] };
      if (!ticket || !canViewTicket(user, ticket)) throw new TicketError("Không tìm thấy ticket.");
      if (ticket.version !== d.version) throw new TicketError("Ticket vừa được cập nhật. Tải lại trang rồi thử lại.");

      const step = ticket.steps.find((s) => s.id === d.stepId);
      const blockers = decisionBlockers(user, ticket, step);
      if (blockers.length) throw new TicketError(blockers.join(" "));
      if (!d.approve && !comment) throw new TicketError("Nhập lý do từ chối.");

      const outcome = !d.approve ? "REJECT" : step!.action === "P" ? "COMPLETE" : "APPROVE";
      await tx.stepDecision.create({
        data: { stepId: step!.id, actorId: user.id, outcome, comment: comment || null, formHash: ticket.formHash },
      });
      await tx.ticketStep.update({ where: { id: step!.id }, data: { status: d.approve ? "DONE" : "REJECTED" } });

      const next = ticket.steps[step!.idx + 1];
      const closing = !d.approve || !next;
      if (next && d.approve) await startStep(tx, ticket, next);

      // Báo người nộp (trừ khi chính họ vừa thao tác)
      if (ticket.requesterId !== user.id) {
        const note = { userId: ticket.requesterId, ticketId: ticket.id, dedupeKey: `result:${step!.id}` };
        await notify(tx, [
          !d.approve
            ? { ...note, kind: "REJECTED", level: "danger", message: `${ticket.code} bị từ chối bởi ${user.fullName}: ${comment}` }
            : !next
              ? { ...note, kind: "DONE", level: "ok", message: `${ticket.code} đã hoàn tất` }
              : {
                  ...note,
                  kind: "STEP_DONE",
                  level: "info",
                  message: `${ticket.code}: ${roleName(step!.roleCode)} đã ${step!.action === "P" ? "thực hiện" : "duyệt"} → chờ ${roleName(next.roleCode)}`,
                },
        ]);
      }
      await tx.ticket.update({
        where: { id: ticket.id },
        data: {
          version: { increment: 1 },
          ...(closing && { status: d.approve ? "DONE" : "REJECTED", closedAt: new Date() }),
        },
      });

      const base = { actorUserId: user.id, actorEmail: user.email, targetType: "ticket", targetId: ticket.id, meta };
      const action = { REJECT: AuditAction.StepRejected, COMPLETE: AuditAction.StepCompleted, APPROVE: AuditAction.StepApproved }[outcome];
      await writeAudit({ ...base, action, details: { code: ticket.code, step: step!.idx, role: step!.roleCode, comment } }, tx);
      if (closing && d.approve) await writeAudit({ ...base, action: AuditAction.TicketDone, details: { code: ticket.code } }, tx);
    });
  } catch (e) {
    // TicketError: service chặn. Lỗi có "SoD: …" từ DB: trigger chặn. Lỗi khác: lỗi hệ thống, ném tiếp.
    const reason =
      e instanceof TicketError ? e.message : e instanceof Error ? /SoD: [^\n"]+/.exec(e.message)?.[0] : undefined;
    if (!reason) throw e;
    await writeAudit({
      action: AuditAction.DecisionDenied,
      actorUserId: user.id,
      actorEmail: user.email,
      targetType: "ticket",
      targetId: d.ticketId,
      details: { stepId: d.stepId, approve: d.approve, reason },
      meta,
    });
    throw new TicketError(reason);
  }
}
