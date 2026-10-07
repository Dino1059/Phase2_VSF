import "server-only";
import { prisma } from "@/lib/db";
import { AuditAction, writeAudit, type RequestMeta } from "@/lib/audit";
import type { CurrentUser } from "@/lib/auth/session";
import { canViewAuditLog } from "@/lib/authz/policy";
import { ROLES, VERB, type RoleKey } from "@/lib/sod/catalog";
import { TicketError } from "@/lib/tickets/service";
import type { Prisma, TicketStatus } from "@/app/generated/prisma/client";

// Bằng chứng cho Auditor: các phiếu trong một kỳ, ai duyệt, lúc nào, duyệt đúng nội dung nào (mã băm).
// Mỗi lần xem hoặc xuất đều ghi nhật ký (BUILD_PLAN 4.6, 5.1 S1).

export const EVIDENCE_MAX_TICKETS = 500;
const TYPES = ["access", "offboard", "rbac"] as const;
const STATUSES: TicketStatus[] = ["OPEN", "RETURNED", "DONE", "REJECTED", "CANCELLED", "EXPIRED"];
export const EVIDENCE_TYPE_LABEL: Record<(typeof TYPES)[number], string> = { access: "Cấp quyền", offboard: "Thu hồi quyền", rbac: "Cấp / thu hồi vai trò" };

export type EvidenceFilter = { from?: string; to?: string; status?: TicketStatus; type?: (typeof TYPES)[number] };

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);

/** Đọc bộ lọc từ query string. Giá trị không hợp lệ bị bỏ qua. */
export function parseEvidenceFilter(sp: Record<string, string | string[] | undefined>): EvidenceFilter {
  const from = one(sp.from);
  const to = one(sp.to);
  const status = one(sp.status);
  const type = one(sp.type);
  return {
    ...(from && DATE.test(from) && { from }),
    ...(to && DATE.test(to) && { to }),
    ...(status && (STATUSES as string[]).includes(status) && { status: status as TicketStatus }),
    ...(type && (TYPES as readonly string[]).includes(type) && { type: type as EvidenceFilter["type"] }),
  };
}
export const evidenceQuery = (f: EvidenceFilter) => new URLSearchParams(Object.entries(f) as [string, string][]).toString();

export type EvidenceDecision = {
  step: number;
  role: string;
  action: string;
  actor: string;
  onBehalfOf: string | null;
  outcome: string;
  comment: string | null;
  decidedAt: Date;
  rev: number;
  formHash: string;
};
export type EvidenceTicket = {
  id: string;
  code: string;
  title: string;
  type: string;
  requester: string;
  status: TicketStatus;
  createdAt: Date;
  closedAt: Date | null;
  rev: number;
  configSeq: number;
  formHash: string;
  exceptionId: string | null;
  decisions: EvidenceDecision[];
};
export type Evidence = { tickets: EvidenceTicket[]; rows: number; truncated: boolean };

const startVN = (d: string) => new Date(`${d}T00:00:00+07:00`);

/** Phiếu trong kỳ kèm mọi quyết định. Chỉ Auditor. Giới hạn EVIDENCE_MAX_TICKETS phiếu mỗi lần. */
export async function loadEvidence(user: CurrentUser, f: EvidenceFilter): Promise<Evidence> {
  if (!canViewAuditLog(user)) throw new TicketError("Chỉ Auditor mới xem và xuất bằng chứng.");
  const where: Prisma.TicketWhereInput = {
    ...((f.from || f.to) && { createdAt: { ...(f.from && { gte: startVN(f.from) }), ...(f.to && { lt: new Date(startVN(f.to).getTime() + 86_400_000) }) } }),
    ...(f.status && { status: f.status }),
    ...(f.type && { typeId: f.type }),
  };
  const rows = await prisma.ticket.findMany({
    where,
    orderBy: { createdAt: "asc" },
    take: EVIDENCE_MAX_TICKETS + 1,
    include: {
      requester: { select: { fullName: true } },
      configVersion: { select: { seq: true } },
      steps: {
        orderBy: { idx: "asc" },
        include: { decisions: { orderBy: { rev: "asc" }, include: { actor: { select: { fullName: true } }, onBehalf: { select: { fullName: true } } } } },
      },
    },
  });
  const truncated = rows.length > EVIDENCE_MAX_TICKETS;
  const tickets = rows.slice(0, EVIDENCE_MAX_TICKETS).map((t): EvidenceTicket => ({
    id: t.id,
    code: t.code,
    title: t.title,
    type: t.typeId,
    requester: t.requester.fullName,
    status: t.status,
    createdAt: t.createdAt,
    closedAt: t.closedAt,
    rev: t.rev,
    configSeq: t.configVersion.seq,
    formHash: t.formHash,
    exceptionId: t.exceptionId,
    decisions: t.steps
      .flatMap((s) =>
        s.decisions.map((d): EvidenceDecision => ({
          step: s.idx,
          role: s.idx === 0 ? "Người nhập phiếu" : (ROLES[s.roleCode as RoleKey]?.name ?? s.roleCode),
          action: s.idx === 0 ? "Gửi phiếu" : VERB[s.action],
          actor: d.actor.fullName,
          onBehalfOf: d.onBehalf?.fullName ?? null,
          outcome: d.outcome,
          comment: d.comment,
          decidedAt: d.decidedAt,
          rev: d.rev,
          formHash: d.formHash,
        })),
      )
      .sort((a, b) => a.decidedAt.getTime() - b.decidedAt.getTime()),
  }));
  return { tickets, rows: tickets.reduce((n, t) => n + t.decisions.length, 0), truncated };
}

/** Ghi nhật ký mỗi lần Auditor xem hoặc xuất bằng chứng */
export async function logEvidence(user: CurrentUser, kind: "viewed" | "csv" | "pdf", f: EvidenceFilter, ev: Pick<Evidence, "tickets" | "rows" | "truncated">, meta: RequestMeta) {
  await writeAudit({
    action: kind === "viewed" ? AuditAction.EvidenceViewed : AuditAction.EvidenceExported,
    actorUserId: user.id,
    actorEmail: user.email,
    targetType: "evidence",
    details: { format: kind, filter: { ...f }, tickets: ev.tickets.length, rows: ev.rows, truncated: ev.truncated },
    meta,
  });
}

const OUTCOME: Record<string, string> = { SUBMIT: "Gửi phiếu", APPROVE: "Đồng ý", COMPLETE: "Đã thực hiện", REJECT: "Từ chối", RETURN: "Trả lại để bổ sung" };
const STATUS: Record<string, string> = { OPEN: "Đang xử lý", RETURNED: "Chờ bổ sung", DONE: "Hoàn tất", REJECTED: "Từ chối", CANCELLED: "Đã huỷ", EXPIRED: "Hết hạn" };
export const outcomeLabel = (o: string) => OUTCOME[o] ?? o;
export const statusLabel = (s: string) => STATUS[s] ?? s;

const ts = (d: Date | null) => (d ? d.toLocaleString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" }) : "");

/** Ô CSV: bọc nháy kép; ô bắt đầu bằng = + - @ bị Excel hiểu là công thức nên thêm dấu nháy đơn phía trước */
export const csvCell = (v: string | number | null | undefined) => {
  let s = v == null ? "" : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
};

const HEADER = [
  "Mã phiếu", "Loại phiếu", "Tiêu đề", "Người yêu cầu", "Trạng thái phiếu", "Ngày tạo", "Ngày đóng", "Phiên bản nội dung hiện tại",
  "Phiên bản cấu hình", "Mã ngoại lệ", "Bước", "Vai trò", "Hành động", "Người thực hiện", "Thay mặt", "Kết quả", "Ghi chú",
  "Thời điểm", "Phiên bản nội dung đã duyệt", "Mã băm nội dung đã duyệt",
];

/** Mỗi dòng CSV là một quyết định. UTF-8 có BOM để Excel đọc đúng tiếng Việt. */
export function evidenceCsv(ev: Evidence): string {
  const lines = [HEADER.map(csvCell).join(",")];
  for (const t of ev.tickets) {
    for (const d of t.decisions) {
      lines.push(
        [
          t.code, EVIDENCE_TYPE_LABEL[t.type as keyof typeof EVIDENCE_TYPE_LABEL] ?? t.type, t.title, t.requester, statusLabel(t.status), ts(t.createdAt), ts(t.closedAt), t.rev,
          t.configSeq, t.exceptionId, d.step, d.role, d.action, d.actor, d.onBehalfOf, outcomeLabel(d.outcome), d.comment,
          ts(d.decidedAt), d.rev, d.formHash,
        ].map(csvCell).join(","),
      );
    }
  }
  return "﻿" + lines.join("\r\n") + "\r\n";
}

/** Xuất CSV: kiểm quyền, tải dữ liệu, ghi nhật ký rồi trả nội dung. */
export async function exportEvidenceCsv(user: CurrentUser, f: EvidenceFilter, meta: RequestMeta) {
  const ev = await loadEvidence(user, f);
  await logEvidence(user, "csv", f, ev, meta);
  const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" }).replaceAll("-", "");
  return { filename: `bang-chung_${day}.csv`, body: evidenceCsv(ev), tickets: ev.tickets.length, rows: ev.rows, truncated: ev.truncated };
}
