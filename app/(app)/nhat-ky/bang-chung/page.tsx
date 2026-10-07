import Link from "next/link";
import { notFound } from "next/navigation";
import { requestMeta } from "@/lib/audit";
import { requireUser } from "@/lib/auth/session";
import { canViewAuditLog } from "@/lib/authz/policy";
import { fmtTime } from "@/lib/format";
import { EVIDENCE_TYPE_LABEL, EVIDENCE_MAX_TICKETS, evidenceQuery, loadEvidence, logEvidence, outcomeLabel, parseEvidenceFilter, statusLabel } from "@/lib/tickets/evidence";
import EvidencePrint from "./evidence-print";
import EvidenceReport from "./evidence-report";

export const metadata = { title: "Bằng chứng · SoD Flow" };

export default async function EvidencePage({ searchParams }: PageProps<"/nhat-ky/bang-chung">) {
  const user = await requireUser();
  if (!canViewAuditLog(user)) notFound();
  const filter = parseEvidenceFilter(await searchParams);
  const ev = await loadEvidence(user, filter);
  await logEvidence(user, "viewed", filter, ev, await requestMeta()); // xem cũng được ghi lại
  const q = evidenceQuery(filter);

  return (
    <>
      <h1>Bằng chứng phân quyền</h1>
      <p className="sub">
        Chọn kỳ để xem mọi phiếu, ai duyệt, lúc nào và duyệt đúng nội dung nào (mã băm). Xuất CSV hoặc PDF; mỗi lần xem và xuất đều được ghi vào nhật ký.
      </p>
      <form method="get" className="card row" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <label className="field" style={{ margin: 0 }}><span>Từ ngày</span><input type="date" name="from" defaultValue={filter.from} /></label>
        <label className="field" style={{ margin: 0 }}><span>Đến ngày</span><input type="date" name="to" defaultValue={filter.to} /></label>
        <label className="field" style={{ margin: 0 }}>
          <span>Loại phiếu</span>
          <select name="type" defaultValue={filter.type ?? ""}>
            <option value="">Tất cả</option>
            {Object.entries(EVIDENCE_TYPE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
        <label className="field" style={{ margin: 0 }}>
          <span>Trạng thái</span>
          <select name="status" defaultValue={filter.status ?? ""}>
            <option value="">Tất cả</option>
            {["OPEN", "RETURNED", "DONE", "REJECTED", "CANCELLED", "EXPIRED"].map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
          </select>
        </label>
        <button className="btn primary">Lọc</button>
        <span className="spacer" />
        <a className="btn sm" href={`/nhat-ky/bang-chung/csv${q ? `?${q}` : ""}`} style={{ textDecoration: "none" }}>Xuất CSV</a>
        <EvidencePrint filter={filter as Record<string, string>}>
          <EvidenceReport ev={ev} filter={filter} by={user.fullName} at={fmtTime(new Date())} />
        </EvidencePrint>
      </form>

      <p className="small muted" style={{ marginTop: 12 }}>
        {ev.tickets.length} phiếu, {ev.rows} quyết định.
        {ev.truncated && ` Chỉ hiện ${EVIDENCE_MAX_TICKETS} phiếu đầu, hãy thu hẹp kỳ.`} <Link href="/nhat-ky">Về nhật ký</Link>
      </p>
      <div className="card" style={{ padding: 8 }}>
        <div className="table-wrap">
          <table className="log-table">
            <thead><tr><th>Phiếu</th><th>Người yêu cầu</th><th>Trạng thái</th><th>Ai duyệt, lúc nào</th></tr></thead>
            <tbody>
              {ev.tickets.map((t) => (
                <tr key={t.id}>
                  <td><Link href={`/yeu-cau/${t.id}`}>{t.code}</Link><div className="muted small">{t.title}</div></td>
                  <td>{t.requester}<div className="muted small">{fmtTime(t.createdAt)}</div></td>
                  <td>{statusLabel(t.status)}{t.closedAt && <div className="muted small">{fmtTime(t.closedAt)}</div>}</td>
                  <td className="small">
                    {t.decisions.filter((d) => d.step > 0).map((d, i) => (
                      <div key={i}>
                        {d.role}: <b>{d.actor}</b>{d.onBehalfOf && ` (thay mặt ${d.onBehalfOf})`} · {outcomeLabel(d.outcome)} · {fmtTime(d.decidedAt)}
                      </div>
                    ))}
                    {!t.decisions.some((d) => d.step > 0) && <span className="muted">Chưa có quyết định</span>}
                  </td>
                </tr>
              ))}
              {!ev.tickets.length && <tr><td colSpan={4} className="muted">Không có phiếu nào trong kỳ.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
