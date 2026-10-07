import "server-only";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { prisma, type Tx } from "@/lib/db";
import { AuditAction, writeAudit, type RequestMeta } from "@/lib/audit";
import type { CurrentUser } from "@/lib/auth/session";
import { canSubmitTicket, canViewTicket, cancelBlockers, decisionBlockers, hasRole } from "@/lib/authz/policy";
import { EXCEPTION_ACTIVITY, ROLES, ROLE_KEYS, VERB, type Priority, type RoleKey, type StepAction } from "@/lib/sod/catalog";
import { buildChain, buildChainFor, slaHours, type Chain, type Phase } from "@/lib/sod/chain";
import { conflictsFor, violations, type Person } from "@/lib/sod/conflicts";
import { notify } from "@/lib/notify/service";
import { activeDelegationsTo } from "@/lib/delegations/queries";
import { activeConfig, configById, type ConfigVersionRef } from "@/lib/config/queries";
import type { Prisma } from "@/app/generated/prisma/client";
import { RbacInputSchema, classifyRbac, isRbacForm, roleLabel, type RbacForm } from "@/lib/sod/rbac";
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
  const cfg = await activeConfig();
  const chain = buildChain(form, user.id, await activePeople(), cfg.config.matrix);
  const factor = cfg.config.priority[formPriority(form)];
  return {
    acts: chain.classification.acts,
    reasons: chain.classification.reasons,
    phases: chain.phases,
    steps: chain.steps.map((s, i) => ({
      role: s.role,
      action: s.action,
      phase: s.phase,
      merged: s.acts.length,
      slaHours: i === 0 ? null : slaHours(s, factor, cfg.config.sla),
      conflicts: i === 0 ? [] : conflictsFor(chain, i, s.assignee),
    })),
    violations: violations(chain).length,
  };
}

// ---------------------------------------------------------------- Gửi phiếu

const ticketTitle = (form: TicketForm, systems: string) =>
  `${LOAI_PHIEU[form.loaiPhieu as keyof typeof LOAI_PHIEU]} quyền – ${form.hoTen.trim()} – ${systems}`.slice(0, 300);
const systemsOf = (form: TicketForm) => [...new Set(form.rows.filter(rowFilled).map((r) => r.heThong.trim()))].join(", ");
const snapshotOf = (form: TicketForm) => ({ ...form, rows: form.rows.filter(rowFilled) });

type Created = { ok: true; id: string; code: string } | { ok: false; errors: [string, string][] };

type Persist = {
  /** Nội dung đã chuẩn hoá để lưu (và băm) */
  snapshot: Record<string, unknown>;
  title: string;
  system: string;
  priority: Priority;
  exception: boolean;
  conflicts: string[];
  waived: Set<number>;
};

/** Ghi phiếu mới (phiên bản 1), bước 0 và bước 1, nhật ký. Dùng chung cho phiếu cấp quyền và phiếu RBAC. */
async function persistTicket(tx: Tx, user: CurrentUser, chain: Chain, p: Persist, cfg: ConfigVersionRef, meta: RequestMeta): Promise<{ id: string; code: string }> {
  const cl = chain.classification;
  const [{ code }] = await tx.$queryRaw<{ code: string }[]>`SELECT next_ticket_code() AS code`;
  const formHash = sha256(JSON.stringify(p.snapshot));
  const now = new Date();

  const ticket = await tx.ticket.create({
    data: {
      code,
      requesterId: user.id,
      configVersionId: cfg.id,
      typeId: cl.type.id,
      title: p.title,
      system: p.system.slice(0, 500),
      priority: p.priority,
      level: cl.level,
      pii: cl.pii,
      breakGlass: cl.breakGlass,
      acts: cl.acts,
      reasons: cl.reasons,
      phases: chain.phases,
      form: p.snapshot as Prisma.InputJsonValue,
      formHash,
      conflicts: p.conflicts,
      exceptionId: p.exception ? `SoD-EX-${code.slice(4)}` : null,
      steps: {
        create: chain.steps.map((s, i) => ({
          idx: i,
          phase: s.phase,
          key: s.key,
          roleCode: s.role,
          action: s.action,
          acts: s.acts.map(String),
          assigneeId: s.assignee,
          sodWaived: p.waived.has(i),
          breakGlass: Boolean(s.breakGlass),
          status: i === 0 ? "CURRENT" : "WAITING",
          slaHours: i === 0 ? null : slaHours(s, cfg.config.priority[p.priority], cfg.config.sla),
          startedAt: i === 0 ? now : null,
        })),
      },
    },
    include: { steps: { orderBy: { idx: "asc" } } },
  });
  await tx.ticketRevision.create({ data: { ticketId: ticket.id, rev: 1, form: p.snapshot as Prisma.InputJsonValue, formHash, createdBy: user.id } });

  // Bước 0: người yêu cầu gửi phiếu — cũng đi qua trigger kiểm quyết định
  const [first, next] = ticket.steps;
  await tx.stepDecision.create({ data: { stepId: first.id, actorId: user.id, outcome: "SUBMIT", formHash, rev: 1 } });
  await tx.ticketStep.update({ where: { id: first.id }, data: { status: "DONE" } });
  await startStep(tx, ticket, next, 1);
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
  return { id: ticket.id, code };
}

/** Dựng chuỗi, kiểm SoD và ghi phiếu mới (phiên bản 1) trong transaction `tx`. Chưa ghi gì nếu trả lỗi. */
async function createTicket(tx: Tx, user: CurrentUser, form: TicketForm, meta: RequestMeta): Promise<Created> {
  const cfg = await activeConfig(tx);
  const chain = buildChain(form, user.id, await activePeople(tx), cfg.config.matrix);
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

  const systems = systemsOf(form);
  const created = await persistTicket(
    tx,
    user,
    chain,
    {
      snapshot: snapshotOf(form),
      title: ticketTitle(form, systems),
      system: systems,
      priority: formPriority(form),
      exception: form.exception,
      conflicts: [...new Set(v.map((x) => x.c))],
      waived,
    },
    cfg,
    meta,
  );
  return { ok: true, ...created };
}

type SubmitResult = { ok: true; id: string } | { ok: false; errors: [string, string][] };

export async function submitTicket(user: CurrentUser, form: TicketForm, meta: RequestMeta): Promise<SubmitResult> {
  if (!canSubmitTicket(user)) throw new TicketError("Bạn không có vai trò Requestor để tạo phiếu.");
  const errors = validateForm(form);
  if (errors.length) return { ok: false, errors };
  return prisma.$transaction(async (tx) => {
    const r = await createTicket(tx, user, form, meta);
    return r.ok ? { ok: true as const, id: r.id } : r;
  });
}

type StepRef = { id: string; roleCode: string; action: StepAction; assigneeId: string | null; slaHours: number | null };
const roleName = (code: string) => ROLES[code as RoleKey]?.name ?? code;

/** Chuyển bước sang Đang xử lý, đặt hạn SLA và báo cho người được giao. */
async function startStep(tx: Tx, ticket: { id: string; code: string }, step: StepRef, rev: number) {
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
      dedupeKey: `task:${step.id}:${rev}`,
    }]);
    // Người đang được ủy quyền thay người này cũng được báo
    const delegations = await tx.delegation.findMany({
      where: { delegatorId: step.assigneeId, roleCode: step.roleCode, revokedAt: null, validFrom: { lte: now }, validTo: { gt: now } },
      select: { delegateId: true, delegator: { select: { fullName: true } } },
    });
    await notify(tx, delegations.map((d) => ({
      userId: d.delegateId,
      ticketId: ticket.id,
      kind: "TASK" as const,
      level: "info" as const,
      message: `${ticket.code} chờ ${VERB[step.action].toLowerCase()} (${roleName(step.roleCode)}) — bạn được ${d.delegator.fullName} ủy quyền, SLA ${step.slaHours}h`,
      dedupeKey: `task:${step.id}:${rev}`,
    })));
  }
}

// ---------------------------------------------------------------- Quyết định một bước

/** Khoá dòng ticket, kiểm quyền xem và phiên bản. Hai người / hai tab bấm cùng lúc sẽ xếp hàng. */
async function lockTicket(tx: Tx, user: CurrentUser, id: string, version: number) {
  await tx.$queryRaw`SELECT id FROM tickets WHERE id = ${id}::uuid FOR UPDATE`;
  const t = await tx.ticket.findUnique({ where: { id }, include: { steps: { orderBy: { idx: "asc" } } } });
  const ticket = t && { ...t, phases: t.phases as Phase[] };
  const acting = await activeDelegationsTo(tx, user.id);
  if (!ticket || !canViewTicket(user, ticket, acting)) throw new TicketError("Không tìm thấy ticket.");
  if (ticket.version !== version) throw new TicketError("Ticket vừa được cập nhật. Tải lại trang rồi thử lại.");
  return Object.assign(ticket, { acting });
}

/**
 * TicketError: service chặn. Lỗi có "SoD: …" từ DB: trigger chặn. Lỗi khác: lỗi hệ thống, ném tiếp.
 * Hai loại đầu được ghi nhật ký "thao tác bị chặn" rồi ném lại dưới dạng TicketError.
 */
async function denied(e: unknown, user: CurrentUser, ticketId: string, details: Record<string, unknown>, meta: RequestMeta): Promise<never> {
  const reason = e instanceof TicketError ? e.message : e instanceof Error ? /SoD: [^\n"]+/.exec(e.message)?.[0] : undefined;
  if (!reason) throw e;
  await writeAudit({
    action: AuditAction.DecisionDenied,
    actorUserId: user.id,
    actorEmail: user.email,
    targetType: "ticket",
    targetId: ticketId,
    details: { ...details, reason },
    meta,
  });
  throw new TicketError(reason);
}

type Decision = { ticketId: string; stepId: string; version: number; approve: boolean; comment: string };

/**
 * Duyệt / hoàn tất / từ chối bước đang xử lý. Người quyết định LUÔN là người đăng nhập.
 * Kiểm theo thứ tự: khoá ticket → quyền xem → phiên bản → quyền quyết định + SoD → trigger DB.
 */
export async function decideStep(user: CurrentUser, d: Decision, meta: RequestMeta): Promise<void> {
  const comment = d.comment.trim().slice(0, 2000);
  try {
    await prisma.$transaction(async (tx) => {
      const ticket = await lockTicket(tx, user, d.ticketId, d.version);

      const step = ticket.steps.find((s) => s.id === d.stepId);
      const blockers = decisionBlockers(user, ticket, step, ticket.acting);
      if (blockers.length) throw new TicketError(blockers.join(" "));
      if (!d.approve && !comment) throw new TicketError("Nhập lý do từ chối.");

      const outcome = !d.approve ? "REJECT" : step!.action === "P" ? "COMPLETE" : "APPROVE";
      await tx.stepDecision.create({
        data: { stepId: step!.id, actorId: user.id, outcome, comment: comment || null, formHash: ticket.formHash, rev: ticket.rev },
      });
      await tx.ticketStep.update({ where: { id: step!.id }, data: { status: d.approve ? "DONE" : "REJECTED" } });

      const next = ticket.steps[step!.idx + 1];
      const closing = !d.approve || !next;
      if (next && d.approve) await startStep(tx, ticket, next, ticket.rev);
      // Bước cuối của phiếu RBAC (IAM thực hiện): ghi / thu hồi vai trò trong cùng transaction
      if (closing && d.approve && ticket.typeId === "rbac") await applyRbac(tx, ticket, user, meta);

      // Báo người nộp (trừ khi chính họ vừa thao tác)
      if (ticket.requesterId !== user.id) {
        const note = { userId: ticket.requesterId, ticketId: ticket.id, dedupeKey: `result:${step!.id}:${ticket.rev}` };
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
      await writeAudit({ ...base, action, details: { code: ticket.code, step: step!.idx, role: step!.roleCode, comment, onBehalfOf: step!.assigneeId !== user.id ? step!.assigneeId : undefined } }, tx);
      if (closing && d.approve) await writeAudit({ ...base, action: AuditAction.TicketDone, details: { code: ticket.code } }, tx);
    });
  } catch (e) {
    await denied(e, user, d.ticketId, { stepId: d.stepId, approve: d.approve }, meta);
  }
}

// ---------------------------------------------------------------- Trả lại để bổ sung

type ReturnInput = { ticketId: string; stepId: string; version: number; comment: string };

/**
 * Người đang xử lý bước trả phiếu về cho người yêu cầu. Phiếu sang RETURNED, SLA tạm dừng, không ai quyết định được
 * tới khi người yêu cầu gửi phiên bản nội dung mới (reviseTicket). Cần đủ điều kiện như khi duyệt.
 */
export async function returnTicket(user: CurrentUser, d: ReturnInput, meta: RequestMeta): Promise<void> {
  const comment = d.comment.trim().slice(0, 2000);
  try {
    await prisma.$transaction(async (tx) => {
      const ticket = await lockTicket(tx, user, d.ticketId, d.version);
      const step = ticket.steps.find((s) => s.id === d.stepId);
      const blockers = decisionBlockers(user, ticket, step, ticket.acting);
      if (blockers.length) throw new TicketError(blockers.join(" "));
      if (ticket.typeId === "rbac") throw new TicketError("Phiếu cấp vai trò không trả lại để bổ sung được. Hãy từ chối, người yêu cầu sẽ tạo phiếu mới.");
      if (!comment) throw new TicketError("Nhập lý do trả lại để người yêu cầu biết cần bổ sung gì.");

      await tx.stepDecision.create({
        data: { stepId: step!.id, actorId: user.id, outcome: "RETURN", comment, formHash: ticket.formHash, rev: ticket.rev },
      });
      await tx.ticketStep.update({ where: { id: step!.id }, data: { dueAt: null } }); // SLA tạm dừng
      await tx.ticket.update({ where: { id: ticket.id }, data: { status: "RETURNED", version: { increment: 1 } } });
      await notify(tx, [{
        userId: ticket.requesterId,
        ticketId: ticket.id,
        kind: "RETURNED",
        level: "warn",
        message: `${ticket.code} bị ${user.fullName} (${roleName(step!.roleCode)}) trả lại: ${comment}`,
        dedupeKey: `return:${step!.id}:${ticket.rev}`,
      }]);
      await writeAudit(
        {
          action: AuditAction.TicketReturned,
          actorUserId: user.id,
          actorEmail: user.email,
          targetType: "ticket",
          targetId: ticket.id,
          details: { code: ticket.code, step: step!.idx, role: step!.roleCode, rev: ticket.rev, comment, onBehalfOf: step!.assigneeId !== user.id ? step!.assigneeId : undefined },
          meta,
        },
        tx,
      );
    });
  } catch (e) {
    await denied(e, user, d.ticketId, { stepId: d.stepId, action: "return" }, meta);
  }
}

// ---------------------------------------------------------------- Bổ sung (phiên bản nội dung mới)

/**
 * Trường được sửa mà KHÔNG cần duyệt lại các bước đã duyệt: thông tin phòng ban và chữ ký, không đổi phạm vi quyền.
 * Không có `email`: email công vụ là danh tính tài khoản được cấp quyền (subject_email gửi sang hệ thống đích),
 * đổi email là đổi người nhận quyền nên mọi bước phải duyệt lại.
 */
const EXEMPT_FROM_REAPPROVAL = new Set<string>(["phongBan", "chucDanh", "signature", "kyTen"]);

type ChainLike = { acts: readonly number[]; phases: readonly Pick<Phase, "act" | "name" | "C" | "I">[]; keys: readonly string[] };
const sameChain = (a: ChainLike, b: ChainLike) =>
  isDeepStrictEqual([...a.acts], [...b.acts]) &&
  isDeepStrictEqual([...a.keys], [...b.keys]) &&
  a.phases.length === b.phases.length &&
  a.phases.every((p, i) => p.act === b.phases[i].act && p.name === b.phases[i].name && isDeepStrictEqual([...p.C], [...b.phases[i].C]) && isDeepStrictEqual([...p.I], [...b.phases[i].I]));

type ReviseInput = { ticketId: string; version: number; form: TicketForm };
export type ReviseResult = { ok: true; id: string; supersededCode?: string } | { ok: false; errors: [string, string][] };

/**
 * Người yêu cầu gửi phiên bản nội dung mới cho phiếu bị trả lại.
 *  - Chuỗi duyệt không đổi: lưu phiên bản mới. Đổi trường ảnh hưởng quyền thì mọi bước đã duyệt phải duyệt lại
 *    (chỉ đổi phòng ban, chức danh, chữ ký thì giữ nguyên các bước đã duyệt). Bước trả lại chạy lại với SLA mới.
 *  - Chuỗi duyệt đổi (Level, PII, ngoại lệ, break-glass, loại phiếu): phiếu cũ bị huỷ và thay bằng phiếu mới.
 */
export async function reviseTicket(user: CurrentUser, d: ReviseInput, meta: RequestMeta): Promise<ReviseResult> {
  const errors = validateForm(d.form);
  if (errors.length) return { ok: false, errors };
  try {
    return await prisma.$transaction(async (tx): Promise<ReviseResult> => {
      const ticket = await lockTicket(tx, user, d.ticketId, d.version);
      if (ticket.requesterId !== user.id) throw new TicketError("Chỉ người yêu cầu mới bổ sung được phiếu.");
      if (ticket.status !== "RETURNED" || ticket.typeId === "rbac") throw new TicketError("Phiếu không ở trạng thái chờ bổ sung.");

      const form = d.form;
      const snapshot = snapshotOf(form);
      const formHash = sha256(JSON.stringify(snapshot));
      if (formHash === ticket.formHash) throw new TicketError("Chưa có thay đổi nào so với phiên bản trước.");

      const cfg = await configById(tx, ticket.configVersionId); // so với chuỗi đã dựng theo cấu hình lúc tạo phiếu
      const chain = buildChain(form, user.id, await activePeople(tx), cfg.config.matrix);
      const unchanged = sameChain(
        { acts: chain.classification.acts, phases: chain.phases, keys: chain.steps.map((s) => s.key) },
        { acts: ticket.acts, phases: ticket.phases, keys: ticket.steps.map((s) => s.key) },
      );

      if (!unchanged) {
        if (!canSubmitTicket(user)) throw new TicketError("Bạn không có vai trò Requestor để tạo phiếu mới thay phiếu này.");
        const blockers = cancelBlockers(user, ticket);
        if (blockers.length) {
          throw new TicketError(`Nội dung mới làm đổi chuỗi duyệt nên cần phiếu mới, nhưng phiếu này không huỷ được. ${blockers.join(" ")}`);
        }
        const created = await createTicket(tx, user, form, meta);
        if (!created.ok) return created;
        await cancelInTx(tx, user, ticket, `Thay bằng ${created.code}: nội dung bổ sung làm đổi chuỗi duyệt.`, meta);
        return { ok: true, id: created.id, supersededCode: ticket.code };
      }

      const old = ticket.form as Record<string, unknown>;
      const next = snapshot as Record<string, unknown>;
      const changed = Object.keys(next).filter((k) => !isDeepStrictEqual(old[k], next[k]));
      const reset = changed.some((k) => !EXEMPT_FROM_REAPPROVAL.has(k));
      const rev = ticket.rev + 1;
      const cl = chain.classification;
      const systems = systemsOf(form);

      // Thứ tự quan trọng: bản ghi phiên bản → ticket (mở lại, rev mới) → bước. Trigger DB kiểm từng bước.
      await tx.ticketRevision.create({ data: { ticketId: ticket.id, rev, form: snapshot, formHash, createdBy: user.id } });
      await tx.ticket.update({
        where: { id: ticket.id },
        data: {
          form: snapshot,
          formHash,
          rev,
          status: "OPEN",
          version: { increment: 1 },
          title: ticketTitle(form, systems),
          system: systems.slice(0, 500),
          priority: formPriority(form),
          level: cl.level,
          pii: cl.pii,
          reasons: cl.reasons,
        },
      });
      // Mức khẩn có thể đổi (không đổi chuỗi) nên tính lại SLA cho các bước còn phải chạy
      const factor = cfg.config.priority[formPriority(form)];
      const steps = ticket.steps.map((s) => {
        if (s.idx === 0 || (!reset && s.status === "DONE")) return s;
        const sla = slaHours(s, factor, cfg.config.sla);
        const data = {
          ...(sla !== s.slaHours && { slaHours: sla }),
          ...(reset && s.status !== "WAITING" && { status: "WAITING" as const, startedAt: null, dueAt: null }),
        };
        return { ...s, slaHours: sla, data };
      });
      for (const s of steps) {
        if ("data" in s && Object.keys(s.data).length) await tx.ticketStep.update({ where: { id: s.id }, data: s.data });
      }
      const restart = reset ? steps[1] : steps.find((s) => s.status === "CURRENT" && s.idx > 0)!;
      await startStep(tx, ticket, restart, rev);
      await writeAudit(
        {
          action: AuditAction.TicketRevised,
          actorUserId: user.id,
          actorEmail: user.email,
          targetType: "ticket",
          targetId: ticket.id,
          details: { code: ticket.code, rev, reapproval: reset, changed, restartedStep: restart.idx },
          meta,
        },
        tx,
      );
      return { ok: true, id: ticket.id };
    });
  } catch (e) {
    return denied(e, user, d.ticketId, { action: "revise" }, meta);
  }
}

// ---------------------------------------------------------------- Huỷ phiếu

type CancelInput = { ticketId: string; version: number; reason: string };

async function cancelInTx(
  tx: Tx,
  user: CurrentUser,
  ticket: { id: string; code: string; steps: { idx: number; status: string; assigneeId: string | null }[] },
  reason: string,
  meta: RequestMeta,
) {
  await tx.ticket.update({ where: { id: ticket.id }, data: { status: "CANCELLED", closedAt: new Date(), version: { increment: 1 } } });
  const cur = ticket.steps.find((s) => s.status === "CURRENT" && s.idx > 0);
  if (cur?.assigneeId && cur.assigneeId !== user.id) {
    await notify(tx, [{
      userId: cur.assigneeId,
      ticketId: ticket.id,
      kind: "CANCELLED",
      level: "info",
      message: `${ticket.code} đã được người yêu cầu huỷ: ${reason}`,
      dedupeKey: `cancel:${ticket.id}`,
    }]);
  }
  await writeAudit(
    {
      action: AuditAction.TicketCancelled,
      actorUserId: user.id,
      actorEmail: user.email,
      targetType: "ticket",
      targetId: ticket.id,
      details: { code: ticket.code, reason },
      meta,
    },
    tx,
  );
}

/** Người yêu cầu huỷ phiếu khi chưa tới bước thực hiện (P). Muốn dừng sau đó thì mở phiếu thu hồi. */
export async function cancelTicket(user: CurrentUser, d: CancelInput, meta: RequestMeta): Promise<void> {
  const reason = d.reason.trim().slice(0, 2000);
  try {
    await prisma.$transaction(async (tx) => {
      const ticket = await lockTicket(tx, user, d.ticketId, d.version);
      const blockers = cancelBlockers(user, ticket);
      if (blockers.length) throw new TicketError(blockers.join(" "));
      if (!reason) throw new TicketError("Nhập lý do huỷ phiếu.");
      await cancelInTx(tx, user, ticket, reason, meta);
    });
  } catch (e) {
    await denied(e, user, d.ticketId, { action: "cancel" }, meta);
  }
}

// ---------------------------------------------------------------- Phiếu cấp / thu hồi vai trò (RBAC)

export type RbacResult = { ok: true; id: string } | { ok: false; errors: [string, string][] };

/** Parse dữ liệu phiếu RBAC từ trình duyệt */
export function parseRbac(input: unknown) {
  const parsed = RbacInputSchema.safeParse(input);
  if (!parsed.success) throw new TicketError("Dữ liệu phiếu không hợp lệ.");
  return parsed.data;
}

/**
 * Tạo phiếu cấp / thu hồi một vai trò cho người khác (hoặc cho chính mình). Chuỗi: Release Manager → System Owner → CISO → IAM.
 * Người được cấp bị loại khỏi danh sách người xử lý, nên không bao giờ nằm trong chuỗi. Không có ngoại lệ SoD cho loại phiếu này.
 * Vai trò chỉ được ghi vào user_roles khi IAM hoàn tất bước cuối (applyRbac), và trigger DB kiểm lại.
 */
export async function createRbacTicket(user: CurrentUser, input: ReturnType<typeof parseRbac>, meta: RequestMeta): Promise<RbacResult> {
  if (!canSubmitTicket(user)) throw new TicketError("Bạn không có vai trò Requestor để tạo phiếu.");
  const fail = (field: string, msg: string): RbacResult => ({ ok: false, errors: [[field, msg]] });
  if (input.op === "grant" && input.validTo && new Date(`${input.validTo}T23:59:59+07:00`) <= new Date()) return fail("validTo", "Hạn của vai trò phải sau hôm nay.");

  return prisma.$transaction(async (tx): Promise<RbacResult> => {
    const now = new Date();
    const target = await tx.user.findFirst({
      where: { id: input.targetUserId, status: "ACTIVE" },
      select: { id: true, fullName: true, roles: { where: { roleCode: input.roleCode, validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] }, select: { id: true } } },
    });
    if (!target) return fail("targetUserId", "Không tìm thấy người được cấp (hoặc tài khoản không hoạt động).");
    const holds = target.roles.length > 0;
    if (input.op === "grant" && holds) return fail("roleCode", `${target.fullName} đã giữ vai trò ${roleLabel(input.roleCode)}.`);
    if (input.op === "revoke" && !holds) return fail("roleCode", `${target.fullName} không giữ vai trò ${roleLabel(input.roleCode)}.`);
    const open = await tx.ticket.findFirst({
      where: { typeId: "rbac", status: { in: ["OPEN", "RETURNED"] }, form: { path: ["targetUserId"], equals: target.id }, AND: [{ form: { path: ["roleCode"], equals: input.roleCode } }] },
      select: { code: true },
    });
    if (open) return fail("roleCode", `Đã có phiếu ${open.code} đang xử lý cho người và vai trò này.`);

    // Người được cấp không nằm trong chuỗi xử lý
    const people = (await activePeople(tx)).filter((p) => p.id !== target.id);
    const cfg = await activeConfig(tx);
    const chain = buildChainFor(classifyRbac(), user.id, people, cfg.config.matrix);
    if (chain.steps.some((s, i) => i > 0 && !s.assignee)) {
      return fail("", "Không có người nào đủ điều kiện giữ một bước của chuỗi duyệt (ngoài người được cấp). Liên hệ quản trị.");
    }
    if (violations(chain).length) {
      return fail("", "Chuỗi duyệt phiếu cấp vai trò sẽ vi phạm SoD (ví dụ người lập phiếu là người duy nhất giữ một vai trò duyệt). Loại phiếu này không có ngoại lệ.");
    }
    const form: RbacForm = { kind: "rbac", ...input, validTo: input.op === "grant" ? input.validTo : "", targetName: target.fullName };
    const created = await persistTicket(
      tx,
      user,
      chain,
      {
        snapshot: form,
        title: `${input.op === "grant" ? "Cấp" : "Thu hồi"} vai trò ${roleLabel(input.roleCode)} – ${target.fullName}`.slice(0, 300),
        system: "SoD Flow (vai trò)",
        priority: "normal",
        exception: false,
        conflicts: [],
        waived: new Set(),
      },
      cfg,
      meta,
    );
    return { ok: true, id: created.id };
  });
}

/** IAM hoàn tất bước cuối của phiếu RBAC: ghi hoặc thu hồi vai trò, kèm mã phiếu. Trigger DB kiểm lại phiếu đã xong, đúng người, đúng vai trò. */
async function applyRbac(tx: Tx, ticket: { id: string; code: string; form: unknown }, actor: CurrentUser, meta: RequestMeta) {
  if (!isRbacForm(ticket.form)) throw new TicketError("Nội dung phiếu RBAC không hợp lệ.");
  const f = ticket.form;
  const now = new Date();
  const active = { userId: f.targetUserId, roleCode: f.roleCode, validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] };
  if (f.op === "grant") {
    if (await tx.userRole.findFirst({ where: active })) throw new TicketError(`Người được cấp đã giữ vai trò ${roleLabel(f.roleCode)}.`);
    await tx.userRole.create({
      data: {
        userId: f.targetUserId,
        roleCode: f.roleCode,
        validFrom: now,
        validTo: f.validTo ? new Date(`${f.validTo}T23:59:59+07:00`) : null,
        grantedById: actor.id,
        ticketId: ticket.id,
        note: `Phiếu ${ticket.code}`,
      },
    });
  } else {
    const r = await tx.userRole.updateMany({ where: active, data: { validTo: now, revokedTicketId: ticket.id } });
    if (r.count !== 1) throw new TicketError(`Người bị thu hồi không còn giữ đúng một bản ghi vai trò ${roleLabel(f.roleCode)}.`);
  }
  await notify(tx, [{
    userId: f.targetUserId,
    kind: "ROLE_CHANGED",
    level: f.op === "grant" ? "ok" : "warn",
    message: `Vai trò ${roleLabel(f.roleCode)} của bạn đã được ${f.op === "grant" ? "cấp" : "thu hồi"} (phiếu ${ticket.code}).`,
    dedupeKey: `role:${ticket.id}`,
  }]);
  await writeAudit(
    {
      action: f.op === "grant" ? AuditAction.RoleGranted : AuditAction.RoleRevoked,
      actorUserId: actor.id,
      actorEmail: actor.email,
      targetType: "user",
      targetId: f.targetUserId,
      details: { ticket: ticket.code, role: f.roleCode, validTo: f.validTo || null },
      meta,
    },
    tx,
  );
}

// ---------------------------------------------------------------- Đóng phiếu "hết hạn" (BUILD_PLAN 4.5)

type ExpireInput = { ticketId: string; version: number; reason: string };

/**
 * Admin đóng phiếu mà bước hiện tại đã quá `staleCloseDays` ngày không ai xử lý. Đây là đóng, KHÔNG phải duyệt:
 * không quyết định nào được ghi, người yêu cầu muốn tiếp tục phải lập phiếu mới. DB kiểm lại số ngày chờ.
 */
export async function expireTicket(user: CurrentUser, d: ExpireInput, meta: RequestMeta): Promise<void> {
  const reason = d.reason.trim().slice(0, 2000);
  try {
    await prisma.$transaction(async (tx) => {
      if (!hasRole(user, "ADMIN")) throw new TicketError("Chỉ Quản trị SoD mới đóng phiếu hết hạn.");
      const ticket = await lockTicket(tx, user, d.ticketId, d.version);
      if (ticket.status !== "OPEN") throw new TicketError("Chỉ phiếu đang xử lý mới đóng hết hạn được.");
      if (!reason) throw new TicketError("Nhập lý do đóng phiếu.");
      const cur = ticket.steps.find((s) => s.status === "CURRENT" && s.idx > 0);
      const days = (await configById(tx, ticket.configVersionId)).config.staleCloseDays;
      if (!cur?.startedAt || Date.now() - cur.startedAt.getTime() < days * 86_400_000) {
        throw new TicketError(`Phiếu chưa đủ ${days} ngày không ai xử lý nên chưa đóng hết hạn được.`);
      }
      await tx.ticket.update({ where: { id: ticket.id }, data: { status: "EXPIRED", closedAt: new Date(), version: { increment: 1 } } });
      const notice = (userId: string, message: string): NewNotificationInput => ({ userId, ticketId: ticket.id, kind: "EXPIRED", level: "warn", message, dedupeKey: `expired:${ticket.id}:${userId}` });
      const people = new Set([ticket.requesterId, cur.assigneeId].filter((x): x is string => !!x && x !== user.id));
      await notify(tx, [...people].map((id) => notice(id, `${ticket.code} đã bị đóng vì quá ${days} ngày không ai xử lý: ${reason}`)));
      await writeAudit(
        {
          action: AuditAction.TicketExpired,
          actorUserId: user.id,
          actorEmail: user.email,
          targetType: "ticket",
          targetId: ticket.id,
          details: { code: ticket.code, step: cur.idx, role: cur.roleCode, assignee: cur.assigneeId, reason },
          meta,
        },
        tx,
      );
    });
  } catch (e) {
    await denied(e, user, d.ticketId, { action: "expire" }, meta);
  }
}
type NewNotificationInput = Parameters<typeof notify>[1][number];
