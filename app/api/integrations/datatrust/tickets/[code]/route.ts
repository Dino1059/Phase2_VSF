import { ticketSummary, verifyDatatrustRequest } from "@/lib/integrations/datatrust";

// DataTrust hỏi trạng thái một phiếu (đối soát khi lỡ webhook, và lấy người duyệt cho bằng chứng).
export async function GET(request: Request, ctx: { params: Promise<{ code: string }> }) {
  const v = await verifyDatatrustRequest(request);
  if (!v.ok) return Response.json({ error: v.reason }, { status: v.status });
  const { code } = await ctx.params;
  const summary = await ticketSummary(code);
  if (!summary || !summary.type.startsWith("dt_")) return Response.json({ error: "not_found" }, { status: 404 });
  return Response.json(summary, { headers: { "Cache-Control": "no-store" } });
}
