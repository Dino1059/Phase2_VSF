import { Fragment } from "react";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth/session";
import { decisionBlockers } from "@/lib/authz/policy";
import { PRIORITY_LABEL, ROLES, VERB, actName, type Priority, type RoleKey } from "@/lib/sod/catalog";
import { DLCN, LOAI_PHIEU } from "@/lib/sod/form";
import { dateVN, fmtTime } from "@/lib/format";
import { getTicket, ticketLog, type TicketDetail } from "@/lib/tickets/queries";
import { Badge, StatusBadge } from "@/app/ui/badges";
import SlaBar from "@/app/ui/sla-bar";
import PhieuButton from "@/app/ui/phieu-button";
import DecisionBox from "./decision-box";

export const metadata = { title: "Chi tiết ticket · SoD Flow" };

const LOG_LABEL: Record<string, string> = {
  "ticket.submitted": "Gửi phiếu",
  "ticket.step.approved": "Duyệt",
  "ticket.step.completed": "Hoàn tất bước",
  "ticket.step.rejected": "Từ chối",
  "ticket.done": "Ticket hoàn tất — lưu hồ sơ phục vụ kiểm toán",
  "ticket.decision.denied": "Thao tác bị chặn",
};
const STATUS_LABEL = { OPEN: "Đang xử lý", DONE: "Hoàn tất", REJECTED: "Từ chối" };

type Step = TicketDetail["steps"][number];
const role = (s: Step) => ROLES[s.roleCode as RoleKey];
const result = (s: Step) =>
  !s.decision ? (s.status === "CURRENT" ? "Đang xử lý" : "") : { SUBMIT: "Đã gửi", APPROVE: "Đồng ý", COMPLETE: "Đã thực hiện", REJECT: "Từ chối" }[s.decision.outcome];

const RESULT_MSG: Record<string, string> = { approve: "Đã ghi nhận quyết định của bạn.", reject: "Đã từ chối ticket." };

export default async function TicketPage({ params, searchParams }: PageProps<"/yeu-cau/[id]">) {
  const user = await requireUser();
  const done = RESULT_MSG[String((await searchParams)["ket-qua"])];
  const t = await getTicket(user, (await params).id);
  if (!t) notFound(); // không có hoặc không được xem: cùng một phản hồi
  const log = await ticketLog(user, t.id);
  const f = t.form;
  const cur = t.steps.find((s) => s.status === "CURRENT" && s.idx > 0);
  const canDecide = cur && decisionBlockers(user, t, cur).length === 0;

  return (
    <div className="card" style={{ marginTop: 28 }}>
      {done && <div className="alert ok" role="status">{done}</div>}
      <div className="row">
        <span className="muted">{t.code}</span>
        <StatusBadge status={t.status} overdue={t.overdue} />
        {t.breakGlass && <span className="chip" style={{ background: "var(--bad-soft)", color: "var(--bad)" }}>Break-glass</span>}
        {t.exceptionId && <span className="chip" style={{ background: "var(--warn-soft)", color: "var(--warn)" }}>{t.exceptionId}</span>}
      </div>
      <h2 style={{ margin: "6px 0 4px", fontSize: 18 }}>{t.title}</h2>
      <p className="muted small" style={{ margin: "0 0 12px" }}>
        {t.requester.fullName} · {fmtTime(t.createdAt)} · {t.system || "—"} · Ưu tiên {PRIORITY_LABEL[t.priority as Priority]} · Level {t.level}
      </p>

      <div className="row" style={{ margin: "0 0 12px" }}>
        <PhieuButton
          label="Xem / in phiếu"
          form={f}
          code={t.code}
          createdAt={t.createdAt}
          statusLabel={STATUS_LABEL[t.status]}
          exception={{ id: t.exceptionId, conflicts: t.conflicts }}
          steps={t.steps.map((s) => ({
            role: s.roleCode as RoleKey,
            action: s.action,
            actor: s.decision?.actor.fullName,
            result: result(s),
            comment: s.decision?.comment,
            doneAt: s.decision?.decidedAt,
          }))}
        />
      </div>
      <div className="small" style={{ margin: "0 0 12px" }}>
        <div><b>Người sử dụng quyền:</b> {f.hoTen} ({f.maNV}) · {f.chucDanh} {f.capBac} · {f.phongBan}</div>
        <div>
          <b>Loại phiếu:</b> {LOAI_PHIEU[f.loaiPhieu as keyof typeof LOAI_PHIEU]} · <b>Mức khẩn:</b> {f.khan === "urgent" ? "Gấp" : "Thường"} ·{" "}
          <b>DLCN:</b> {DLCN[f.dlcn as keyof typeof DLCN]}
        </div>
        <table className="mini">
          <tbody>
            {f.rows.map((r, i) => (
              <tr key={i}>
                <td>{r.heThong}</td><td>{r.taiNguyen}</td><td>Tầng {r.tang}</td><td>{r.mucQuyen}</td><td>{r.thoiHan && `đến ${dateVN(r.thoiHan)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div><b>Mục đích:</b> {f.mucDich}</div>
        {f.lyDo && <div><b>Lý do:</b> {f.lyDo}</div>}
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        {t.acts.map((a) => <span key={a} className="chip blue">{actName(a)}</span>)}
      </div>
      {t.exceptionId && (
        <div className="alert info small">
          <b>Ngoại lệ {t.exceptionId}</b> · {f.exFrom.replace("T", " ")} → {f.exTo.replace("T", " ")}
          <br />Xung đột: {t.conflicts.join("; ") || "—"}
          <br />Lý do: {f.exReason}
          <br />Bù trừ: {f.exControls}
        </div>
      )}

      <ol className="steps">
        {t.steps.map((s, i) => {
          const head = i > 0 && s.phase !== t.steps[i - 1].phase;
          const isCur = t.status === "OPEN" && s.id === cur?.id;
          const state = isCur ? "current" : s.status.toLowerCase();
          return (
            <Fragment key={s.id}>
              {head && <li className="phase-label">{t.phases[s.phase].name}</li>}
              <li className={`step ${state}`}>
                <div className="dot">{s.status === "DONE" ? "✓" : s.status === "REJECTED" ? "✕" : s.idx + 1}</div>
                <div>
                  <div className="step-title">
                    <Badge l={s.action} /> {s.idx === 0 ? "Người nhập phiếu" : role(s).name}
                    {s.decision && <span className="muted small" style={{ fontWeight: 400 }}>· {s.decision.actor.fullName}</span>}
                  </div>
                  <div className="step-meta">
                    {VERB[s.action]}
                    {s.decision && ` · ${s.status === "REJECTED" ? "từ chối" : "xong"} ${fmtTime(s.decision.decidedAt)}`}
                    {s.decision?.comment && ` — “${s.decision.comment}”`}
                    {s.sodWaived && <span className="conflict"> · xung đột SoD theo ngoại lệ</span>}
                  </div>
                  {isCur && s.startedAt && s.dueAt && <SlaBar startedAt={s.startedAt} dueAt={s.dueAt} slaHours={s.slaHours} />}
                  {isCur && canDecide && (
                    <DecisionBox ticketId={t.id} stepId={s.id} version={t.version} roleName={role(s).name} isP={s.action === "P"} />
                  )}
                </div>
              </li>
            </Fragment>
          );
        })}
      </ol>

      <details style={{ marginTop: 12 }}>
        <summary>Nhật ký kiểm toán ({log.length})</summary>
        <div className="log">
          {log.map((l) => {
            const d = (l.details ?? {}) as { comment?: string; reason?: string; role?: string };
            return (
              <div key={l.id.toString()}>
                <span className="muted">{fmtTime(l.occurredAt)}</span> · <b>{l.actorEmail ?? "Hệ thống"}</b> — {LOG_LABEL[l.action] ?? l.action}
                {d.role && ` (${ROLES[d.role as RoleKey]?.name ?? d.role})`}
                {(d.comment || d.reason) && `: ${d.comment || d.reason}`}
              </div>
            );
          })}
        </div>
      </details>
    </div>
  );
}
