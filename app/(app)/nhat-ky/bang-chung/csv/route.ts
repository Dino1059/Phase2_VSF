import { requireUser } from "@/lib/auth/session";
import { canViewAuditLog } from "@/lib/authz/policy";
import { requestMeta } from "@/lib/audit";
import { exportEvidenceCsv, parseEvidenceFilter } from "@/lib/tickets/evidence";

// Xuất CSV bằng chứng. Chỉ Auditor; người khác nhận 404 như thể trang không tồn tại. Mỗi lần xuất được ghi nhật ký.
export async function GET(request: Request) {
  const user = await requireUser();
  if (!canViewAuditLog(user)) return new Response("Not Found", { status: 404 });
  const filter = parseEvidenceFilter(Object.fromEntries(new URL(request.url).searchParams));
  const { filename, body } = await exportEvidenceCsv(user, filter, await requestMeta());
  return new Response(body, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
