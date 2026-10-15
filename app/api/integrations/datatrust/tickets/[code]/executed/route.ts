import { prisma } from "@/lib/db";
import { AuditAction, requestMeta, writeAudit } from "@/lib/audit";
import { verifyDatatrustRequest } from "@/lib/integrations/datatrust";
import { isDtForm } from "@/lib/sod/datatrust";

// DataTrust báo đã thực thi đề xuất sau khi phiếu DONE. Chỉ ghi nhật ký kiểm toán, không đổi trạng thái phiếu
// (dòng 13 không có bước P cho người khác: Requestor thực thi ở DataTrust).
export async function POST(request: Request, ctx: { params: Promise<{ code: string }> }) {
  const v = await verifyDatatrustRequest(request);
  if (!v.ok) return Response.json({ error: v.reason }, { status: v.status });
  const { code } = await ctx.params;

  let body: { executed_by?: unknown; proposal_hash?: unknown; evidence_ref?: unknown; affected_rows?: unknown };
  try {
    body = JSON.parse(v.body);
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 422 });
  }
  const executedBy = String(body.executed_by ?? "");
  const proposalHash = String(body.proposal_hash ?? "");
  const evidenceRef = String(body.evidence_ref ?? "").slice(0, 200);

  const t = await prisma.ticket.findUnique({ where: { code }, include: { requester: { select: { username: true, email: true } } } });
  if (!t || !isDtForm(t.form)) return Response.json({ error: "not_found" }, { status: 404 });
  if (t.status !== "DONE") return Response.json({ error: "ticket_not_done", status: t.status }, { status: 409 });
  if (t.form.proposalHash !== proposalHash) return Response.json({ error: "hash_mismatch" }, { status: 409 });
  if (executedBy !== t.requester.username) return Response.json({ error: "executor_is_not_requester" }, { status: 403 });

  const already = await prisma.auditLog.findFirst({ where: { action: AuditAction.ExternalExecuted, targetId: t.id }, select: { id: true } });
  if (already) return Response.json({ ok: true, already_recorded: true });

  await writeAudit({
    action: AuditAction.ExternalExecuted,
    actorUserId: t.requesterId,
    actorEmail: t.requester.email,
    targetType: "ticket",
    targetId: t.id,
    details: { code: t.code, via: "datatrust", executedBy, proposalHash, evidenceRef, affectedRows: Number(body.affected_rows) || 0 },
    meta: await requestMeta(),
  });
  return Response.json({ ok: true, already_recorded: false });
}
