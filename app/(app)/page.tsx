import Link from "next/link";
import { requireUser } from "@/lib/auth/session";
import { canSubmitTicket } from "@/lib/authz/policy";
import { ROLES, SOD_CONFIG, type RoleKey } from "@/lib/sod/catalog";
import { overviewCounts } from "@/lib/tickets/queries";

const FLOW = [
  ["Raise", "Requestor tạo ticket, mô tả mục đích, phạm vi, dữ liệu."],
  ["Phân loại", "Tự map sang hoạt động kiểm soát trong ma trận."],
  ["Kiểm SoD", "Chặn các cặp xung đột; vi phạm → xin ngoại lệ."],
  ["Duyệt tuần tự", "Rà soát (R) → Phê duyệt (A), cấp thấp → cao."],
  ["Thực thi", "Người P độc lập thực hiện sau khi đã duyệt."],
  ["Hậu kiểm & lưu", "Auditor xác nhận, lưu log cùng ticket."],
];

export default async function Overview() {
  const user = await requireUser();
  const c = await overviewCounts(user);
  const { sla, rank } = SOD_CONFIG;
  const ladder = (Object.entries(rank) as [RoleKey, number][])
    .filter(([r]) => !["REQ", "DEV", "OPS", "IAM", "AUD"].includes(r))
    .sort((a, b) => a[1] - b[1]);

  return (
    <>
      <div className="row" style={{ marginTop: 28, alignItems: "flex-start" }}>
        <div>
          <h1 style={{ marginTop: 0 }}>Xin chào, {user.fullName}</h1>
          <p className="sub" style={{ marginBottom: 0 }}>
            Mỗi yêu cầu có người khởi tạo, người phê duyệt và người thực thi độc lập.
          </p>
        </div>
        <span className="spacer" />
        {canSubmitTicket(user) && (
          <Link className="btn primary" href="/yeu-cau/moi" style={{ textDecoration: "none", whiteSpace: "nowrap" }}>
            + Tạo phiếu mới
          </Link>
        )}
      </div>

      <section className="grid g4" style={{ marginTop: 20 }}>
        {[
          ["Yêu cầu của tôi đang xử lý", c.mineOpen, "/yeu-cau?trang-thai=OPEN"],
          ["Chờ tôi xử lý", c.inbox, "/hop-viec"],
          ["Chờ tôi — đã quá SLA", c.inboxOverdue, "/hop-viec"],
        ].map(([label, value, href]) => (
          <Link key={label} href={href as string} className="card kpi" style={{ color: "inherit", textDecoration: "none" }}>
            <div className="v">{value}</div>
            <div className="l">{label}</div>
          </Link>
        ))}
        <div className="card kpi">
          <div className="l" style={{ marginBottom: 6 }}>Vai trò của bạn</div>
          <div className="row">
            {user.roles.map((r) => (
              <span key={r.code} className="chip blue">{r.name}</span>
            ))}
          </div>
        </div>
      </section>

      <section>
        <h2>6 bước của một ticket</h2>
        <div className="flow">
          {FLOW.map(([b, p], i) => (
            <div key={b} className="flow-step">
              <div className="n">{i + 1}</div>
              <b>{b}</b>
              <p>{p}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid g2">
        <div className="card">
          <h2>Thứ tự người duyệt</h2>
          <p className="muted small" style={{ marginTop: -6 }}>
            Trong mỗi hoạt động, người rà soát đi trước, người phê duyệt đi sau. Cấp thấp duyệt trước, cấp cao nhất chốt cuối.
          </p>
          <div className="ladder">
            <div className="rung">
              <div className="k">Bắt đầu</div>
              <b>Requestor</b>
              <span className="small muted">khởi tạo</span>
            </div>
            {ladder.map(([r, v]) => (
              <div key={r} className="rung">
                <div className="k">Cấp {v}</div>
                <b>{ROLES[r].short}</b>
              </div>
            ))}
            <div className="rung">
              <div className="k">Sau cùng</div>
              <b>Auditor</b>
              <span className="small muted">hậu kiểm</span>
            </div>
          </div>
          <p className="small muted">
            Hoạt động <b>phê duyệt</b>: R → A → P (được duyệt rồi mới thực thi). Hoạt động <b>thực hiện</b> (dev, deploy, cấp quyền): P → R → A.
          </p>
        </div>
        <div className="card">
          <h2>SLA &amp; thông báo</h2>
          <div className="sla-strip">
            <div className="sla-item" style={{ background: "var(--warn-soft)" }}>
              <b>{SOD_CONFIG.remindPct}%</b>
              <span className="small">Nhắc người đang xử lý</span>
            </div>
            <div className="sla-item" style={{ background: "var(--bad-soft)" }}>
              <b>{SOD_CONFIG.escalatePct}%</b>
              <span className="small">Quá hạn → leo thang cấp trên</span>
            </div>
            <div className="sla-item" style={{ background: "#f8dcdc" }}>
              <b>{SOD_CONFIG.criticalPct}%</b>
              <span className="small">Báo CISO + Auditor</span>
            </div>
          </div>
          <p className="small muted">
            SLA mỗi bước: thực hiện {sla.P}h · rà soát {sla.R}h · phê duyệt {sla.A}h, nhân hệ số ưu tiên. Ticket và nhật ký lưu{" "}
            {Math.round(SOD_CONFIG.retentionDays / 365)} năm.
          </p>
        </div>
      </section>
    </>
  );
}
