"use server";

import { requestMeta } from "@/lib/audit";
import { requireUser } from "@/lib/auth/session";
import { canViewAuditLog } from "@/lib/authz/policy";
import { loadEvidence, logEvidence, parseEvidenceFilter } from "@/lib/tickets/evidence";

/** Ghi nhật ký mỗi lần Auditor in / lưu PDF báo cáo bằng chứng (việc in do trình duyệt làm). */
export async function logEvidencePdfAction(filter: Record<string, string>): Promise<void> {
  const user = await requireUser();
  if (!canViewAuditLog(user)) return;
  const f = parseEvidenceFilter(filter);
  await logEvidence(user, "pdf", f, await loadEvidence(user, f), await requestMeta());
}
