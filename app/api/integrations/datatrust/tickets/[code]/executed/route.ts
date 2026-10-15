import { requestMeta } from "@/lib/audit";
import { verifyDatatrustRequest } from "@/lib/integrations/datatrust";
import { completeDatatrustExecution } from "@/lib/tickets/service";

// DataTrust báo Executor đã thực thi đề xuất. Ghi bước thực hiện (P, Prod. Op.) nhân danh người thực thi, phiếu sang DONE.
// Người thực thi phải là người được giao bước P (hoặc người được ủy quyền), không phải người đề xuất hay người duyệt.
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
  const r = await completeDatatrustExecution(
    code,
    {
      executedBy: String(body.executed_by ?? ""),
      proposalHash: String(body.proposal_hash ?? ""),
      evidenceRef: String(body.evidence_ref ?? "").slice(0, 200),
      affectedRows: Number(body.affected_rows) || 0,
    },
    await requestMeta(),
  );
  if (!r.ok) return Response.json({ error: r.error, detail: r.detail }, { status: r.status });
  return Response.json({ ok: true, already_recorded: r.alreadyRecorded });
}
