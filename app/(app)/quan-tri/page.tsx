import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth/session";
import { canDecideConfig, canProposeConfig, canViewConfig } from "@/lib/authz/policy";
import { activeConfig, listConfigVersions } from "@/lib/config/queries";
import { SLA_LABEL, diffConfig } from "@/lib/config/schema";
import { PRIORITY_LABEL } from "@/lib/sod/catalog";
import { fmtDur, fmtTime } from "@/lib/format";
import { overdueTickets } from "@/lib/tickets/queries";
import { roleName } from "@/app/ui/badges";
import Link from "next/link";
import { decideConfigAction, withdrawConfigAction } from "@/app/actions/config";
import ConfigForm from "./config-form";

export const metadata = { title: "Quản trị · SoD Flow" };

const STATUS: Record<string, [string, string]> = {
  PROPOSED: ["st-open", "Chờ duyệt"],
  ACTIVE: ["st-done", "Đang hiệu lực"],
  REJECTED: ["st-rejected", "Từ chối"],
  SUPERSEDED: ["st-cancelled", "Đã thay thế"],
  CANCELLED: ["st-cancelled", "Đã rút"],
};

export default async function AdminPage() {
  const user = await requireUser();
  if (!canViewConfig(user)) redirect("/");
  const [active, versions, overdue] = await Promise.all([activeConfig(), listConfigVersions(), overdueTickets(user)]);
  const bySeq = new Map(versions.map((v) => [v.seq, v]));
  const c = active.config;

  return (
    <>
      <h1>Quản trị cấu hình</h1>
      <p className="sub">
        Admin đề xuất, CISO duyệt (hai người khác nhau) thì thay đổi mới có hiệu lực, và chỉ áp cho phiếu tạo sau. Mỗi phiếu giữ phiên bản cấu hình lúc tạo.
        {!canProposeConfig(user) && " Bạn chỉ có quyền xem" + (canDecideConfig(user) ? " và duyệt." : ".")}
      </p>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Đang hiệu lực: phiên bản {active.seq}</h2>
        <div className="grid g4 small">
          {(Object.keys(c.sla) as (keyof typeof c.sla)[]).map((k) => <div key={k}><div className="muted">SLA {SLA_LABEL[k].toLowerCase()}</div><b>{c.sla[k]} giờ</b></div>)}
          {(Object.keys(c.priority) as (keyof typeof c.priority)[]).map((k) => <div key={k}><div className="muted">Ưu tiên {PRIORITY_LABEL[k]}</div><b>×{c.priority[k]}</b></div>)}
          <div><div className="muted">Nhắc / quá hạn / báo CISO</div><b>{c.remindPct}% / {c.escalatePct}% / {c.criticalPct}%</b></div>
          <div><div className="muted">Đóng phiếu hết hạn sau</div><b>{c.staleCloseDays} ngày</b></div>
          <div><div className="muted">Ủy quyền tối đa</div><b>{c.delegationMaxDays} ngày</b></div>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>Ma trận SoD của phiên bản này xem ở trang Ma trận.</p>
      </div>

      {overdue.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>Phiếu quá hạn SLA ({overdue.length})</h2>
          <p className="small muted" style={{ marginTop: -6 }}>
            Hệ thống nhắc và leo thang tự động, không bao giờ tự duyệt. Phiếu chờ quá số ngày cấu hình thì Admin mở phiếu để đóng “hết hạn”.
          </p>
          <div className="table-wrap">
            <table className="log-table">
              <thead><tr><th>Phiếu</th><th>Bước</th><th>Người được giao</th><th>Quá hạn</th><th /></tr></thead>
              <tbody>
                {overdue.map((o) => (
                  <tr key={o.id}>
                    <td><Link href={`/yeu-cau/${o.id}`}>{o.code}</Link> <span className="muted small">{o.title}</span></td>
                    <td>{roleName(o.roleCode)}</td>
                    <td>{o.assignee ?? "—"}</td>
                    <td>{fmtDur(o.lateHours * 3_600_000)}</td>
                    <td>{o.waitedDays >= o.staleDays && <span className="status st-breach">Có thể đóng hết hạn</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {canProposeConfig(user) && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>Đề xuất thay đổi</h2>
          <ConfigForm active={c} />
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Lịch sử và đề xuất</h2>
        {versions.map((v) => {
          const [cls, label] = STATUS[v.status];
          const base = v.baseSeq ? bySeq.get(v.baseSeq) : undefined;
          const changes = base ? diffConfig(base.config, v.config) : [];
          const mine = v.proposedById === user.id;
          return (
            <div key={v.id} className="box" style={{ marginBottom: 10 }}>
              <div className="row">
                <b>Phiên bản {v.seq}</b>
                <span className={`status ${cls}`}>{label}</span>
                <span className="muted small">
                  {v.proposer ? `${v.proposer.fullName} đề xuất ${fmtTime(v.proposedAt)}` : "Hệ thống"}
                  {v.decider && v.status !== "PROPOSED" && ` · ${v.decider.fullName} ${v.status === "CANCELLED" ? "rút" : "quyết định"} ${v.decidedAt ? fmtTime(v.decidedAt) : ""}`}
                  {v.activatedAt && ` · hiệu lực từ ${fmtTime(v.activatedAt)}`}
                </span>
              </div>
              <div className="small" style={{ marginTop: 4 }}>Lý do: {v.reason}{v.decisionNote && ` · Ghi chú: ${v.decisionNote}`}</div>
              {changes.length > 0 && (
                <ul className="small" style={{ margin: "6px 0 0" }}>
                  {changes.slice(0, 10).map((x) => <li key={x}>{x}</li>)}
                  {changes.length > 10 && <li>… và {changes.length - 10} thay đổi nữa</li>}
                </ul>
              )}
              {v.status === "PROPOSED" && v.baseSeq !== active.seq && <div className="alert warn small" style={{ marginTop: 8 }}>Đề xuất dựa trên phiên bản {v.baseSeq}, nay đã cũ. Không duyệt được nữa.</div>}
              {v.status === "PROPOSED" && canDecideConfig(user) && !mine && v.baseSeq === active.seq && (
                <form action={decideConfigAction} style={{ marginTop: 8 }} className="stack">
                  <input type="hidden" name="id" value={v.id} />
                  <input name="note" placeholder="Ghi chú (bắt buộc khi từ chối)" maxLength={1000} />
                  <div className="row">
                    <button className="btn ok sm" name="decision" value="approve">Duyệt</button>
                    <button className="btn bad sm" name="decision" value="reject">Từ chối</button>
                  </div>
                </form>
              )}
              {v.status === "PROPOSED" && mine && (
                <form action={withdrawConfigAction} style={{ marginTop: 8 }}>
                  <input type="hidden" name="id" value={v.id} />
                  <button className="btn sm">Rút đề xuất</button>
                </form>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
