import { Fragment } from "react";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth/session";
import Link from "next/link";
import { cancelBlockers, decisionBlockers, hasRole } from "@/lib/authz/policy";
import { PRIORITY_LABEL, ROLES, VERB, actName, type Priority, type RoleKey } from "@/lib/sod/catalog";
import { DLCN, LOAI_PHIEU } from "@/lib/sod/form";
import { RBAC_OPS, isRbacForm, roleLabel } from "@/lib/sod/rbac";
import { DT_TYPE_LABEL, isDtForm, isDtType } from "@/lib/sod/datatrust";
import { OPS_FIELDS, OPS_TYPE_LABEL, isOpsForm, isOpsType } from "@/lib/sod/ops";
import { dateVN, fmtTime } from "@/lib/format";
import { getTicket, ticketLog, type TicketDetail } from "@/lib/tickets/queries";
import { Badge, StatusBadge } from "@/app/ui/badges";
import SlaBar from "@/app/ui/sla-bar";
import PhieuButton from "@/app/ui/phieu-button";
import DecisionBox from "./decision-box";
import CancelBox from "./cancel-box";
import ExpireBox from "./expire-box";

export const metadata = { title: "Chi tiết ticket · SoD Flow" };

const LOG_LABEL: Record<string, string> = {
  "ticket.submitted": "Gửi phiếu",
  "ticket.step.approved": "Duyệt",
  "ticket.step.completed": "Hoàn tất bước",
  "ticket.step.rejected": "Từ chối",
  "ticket.done": "Ticket hoàn tất — lưu hồ sơ phục vụ kiểm toán",
  "ticket.returned": "Trả lại để bổ sung",
  "ticket.revised": "Bổ sung phiên bản mới",
  "ticket.cancelled": "Huỷ phiếu",
  "ticket.expired": "Đóng phiếu hết hạn",
  "ticket.submitted.via_integration": "Phiếu được gửi từ DataTrust OS",
  "ticket.executed.external": "DataTrust báo đã thực thi sau khi được duyệt",
  "sla.critical": "Quá mốc SLA nghiêm trọng",
  "ticket.decision.denied": "Thao tác bị chặn",
};
const STATUS_LABEL = { OPEN: "Đang xử lý", RETURNED: "Chờ bổ sung", DONE: "Hoàn tất", REJECTED: "Từ chối", CANCELLED: "Đã huỷ", EXPIRED: "Hết hạn" };

type Step = TicketDetail["steps"][number];
const role = (s: Step) => ROLES[s.roleCode as RoleKey];
const result = (s: Step) =>
  !s.decision ? (s.status === "CURRENT" ? "Đang xử lý" : "") : { SUBMIT: "Đã gửi", APPROVE: "Đồng ý", COMPLETE: "Đã thực hiện", REJECT: "Từ chối", RETURN: "Trả lại" }[s.decision.outcome];

const RESULT_MSG: Record<string, string> = {
  approve: "Đã ghi nhận quyết định của bạn.",
  reject: "Đã từ chối ticket.",
  return: "Đã trả phiếu về cho người yêu cầu. SLA tạm dừng tới khi có bản bổ sung.",
  revised: "Đã gửi bản bổ sung. Phiếu quay lại hàng chờ xử lý.",
  superseded: "Nội dung bổ sung làm đổi chuỗi duyệt nên hệ thống đã tạo phiếu mới và huỷ phiếu cũ.",
  cancelled: "Đã huỷ phiếu.",
  expired: "Đã đóng phiếu hết hạn.",
};

export default async function TicketPage({ params, searchParams }: PageProps<"/yeu-cau/[id]">) {
  const user = await requireUser();
  const done = RESULT_MSG[String((await searchParams)["ket-qua"])];
  const t = await getTicket(user, (await params).id);
  if (!t) notFound(); // không có hoặc không được xem: cùng một phản hồi
  const log = await ticketLog(user, t.id);
  const rbac = isRbacForm(t.form) ? t.form : null;
  const dt = isDtForm(t.form) ? t.form : null;
  const ops = isOpsForm(t.form) ? t.form : null;
  const f = t.form;
  const cur = t.steps.find((s) => s.status === "CURRENT" && s.idx > 0);
  const canDecide = cur && decisionBlockers(user, t, cur, t.acting).length === 0;
  const returned = t.status === "RETURNED" ? t.steps.find((s) => s.decision?.outcome === "RETURN") : undefined;
  const canRevise = t.status === "RETURNED" && t.requesterId === user.id;
  const canCancel = cancelBlockers(user, t).length === 0;
  // Admin đóng phiếu "hết hạn" khi bước hiện tại đã chờ quá số ngày cấu hình (theo cấu hình lúc tạo phiếu)
  const canExpire = hasRole(user, "ADMIN") && t.status === "OPEN" && t.waitedDays >= t.staleDays;

  return (
    <div className="card" style={{ marginTop: 28 }}>
      {done && <div className="alert ok" role="status">{done}</div>}
      <div className="row">
        <span className="muted">{t.code}</span>
        <StatusBadge status={t.status} overdue={t.overdue} />
        {t.breakGlass && <span className="chip" style={{ background: "var(--bad-soft)", color: "var(--bad)" }}>Break-glass</span>}
        {t.exceptionId && <span className="chip" style={{ background: "var(--warn-soft)", color: "var(--warn)" }}>{t.exceptionId}</span>}
      </div>
      {t.status === "RETURNED" && (
        <div className="alert warn" role="status" style={{ marginTop: 10 }}>
          <b>Phiếu đang chờ bổ sung.</b>{" "}
          {returned?.decision && (
            <>
              {returned.decision.actor.fullName} ({role(returned)?.name}) trả lại lúc {fmtTime(returned.decision.decidedAt)}: “{returned.decision.comment}”.
            </>
          )}{" "}
          SLA tạm dừng.
          {canRevise ? (
            <div style={{ marginTop: 8 }}>
              <Link className="btn primary sm" href={`/yeu-cau/${t.id}/bo-sung`} style={{ textDecoration: "none" }}>
                Bổ sung phiếu
              </Link>
            </div>
          ) : (
            <> Chỉ người yêu cầu bổ sung được.</>
          )}
        </div>
      )}
      <h2 style={{ margin: "6px 0 4px", fontSize: 18 }}>{t.title}</h2>
      <p className="muted small" style={{ margin: "0 0 12px" }}>
        {t.requester.fullName} · {fmtTime(t.createdAt)} · {t.system || "—"} · Ưu tiên {PRIORITY_LABEL[t.priority as Priority]} · Level {t.level}
        {t.rev > 1 && ` · Phiên bản nội dung ${t.rev} (bổ sung lần cuối ${fmtTime(t.revisions[t.revisions.length - 1].createdAt)})`}
      </p>

      {canCancel && <CancelBox ticketId={t.id} version={t.version} />}
      {canExpire && <ExpireBox ticketId={t.id} version={t.version} days={t.staleDays} />}
      {!rbac && !dt && !ops && (
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
              actor: s.decision ? (s.decision.onBehalf ? `${s.decision.actor.fullName} (thay mặt ${s.decision.onBehalf.fullName})` : s.decision.actor.fullName) : undefined,
              result: result(s),
              comment: s.decision?.comment,
              doneAt: s.decision?.decidedAt,
            }))}
          />
        </div>
      )}
      {ops ? (
        <div className="small" style={{ margin: "0 0 12px" }}>
          <div><b>Loại:</b> {isOpsType(t.typeId) ? OPS_TYPE_LABEL[t.typeId] : t.typeId} · <b>Mức khẩn:</b> {ops.urgent ? "Gấp" : "Thường"}{ops.pii && " · có dữ liệu cá nhân"}</div>
          <div><b>Tiêu đề:</b> {ops.title} · <b>Hệ thống:</b> {ops.system}</div>
          {OPS_FIELDS[ops.type].map((fd) => {
            const v = ops.fields[fd.key];
            return v ? <div key={fd.key}><b>{fd.label}:</b> {fd.kind === "select" ? (fd.options?.[v] ?? v) : fd.kind === "date" ? dateVN(v) : v}</div> : null;
          })}
          <div><b>Lý do / mục đích:</b> {ops.reason}</div>
          {ops.snapshot && (
            <details style={{ marginTop: 8 }}>
              <summary>Danh sách quyền cần rà soát ({ops.snapshot.grants.length} quyền truy cập, {ops.snapshot.roles.length} vai trò){ops.snapshot.truncated && " · đã cắt bớt"}</summary>
              <table className="mini">
                <tbody>
                  {ops.snapshot.grants.map((g, i) => (
                    <tr key={`g${i}`}><td>{g.user}</td><td>{g.system}</td><td>{g.resource}</td><td>{g.permission}</td><td>{g.until ? `đến ${dateVN(g.until)}` : "không thời hạn"}</td><td className="muted">{g.ticket}</td></tr>
                  ))}
                  {ops.snapshot.roles.map((r, i) => (
                    <tr key={`r${i}`}><td>{r.user}</td><td>Vai trò SoD Flow</td><td>{roleLabel(r.role)}</td><td></td><td>{r.until ? `đến ${dateVN(r.until)}` : "không thời hạn"}</td><td></td></tr>
                  ))}
                </tbody>
              </table>
              <div className="muted">Chụp lúc {fmtTime(new Date(ops.snapshot.generatedAt))}. Mã băm phiếu bao gồm danh sách này.</div>
            </details>
          )}
        </div>
      ) : dt ? (
        <div className="small" style={{ margin: "0 0 12px" }}>
          <div><b>Loại:</b> {isDtType(t.typeId) ? DT_TYPE_LABEL[t.typeId] : t.typeId} · <b>Mã đề xuất DataTrust:</b> {dt.externalRef}</div>
          <div><b>Dữ liệu:</b> {dt.dataset}{dt.column && `.${dt.column}`} · <b>Thao tác:</b> {dt.operation} · <b>Số dòng:</b> {dt.expectedRows} · <b>Rủi ro:</b> {dt.riskLevel}{dt.pii && " · có dữ liệu cá nhân"}</div>
          <div><b>Lý do:</b> {dt.reason}</div>
          <div className="muted" style={{ wordBreak: "break-all" }}>Mã băm nội dung đề xuất: {dt.proposalHash}</div>
          <div className="muted">Ba người khác nhau: người gửi duyệt ({t.requester.fullName}) đề xuất, các bước duyệt ở dưới, Prod. Op. thực thi ở DataTrust. Bước thực hiện được ghi khi DataTrust báo đã chạy. Phiếu chỉ mô tả dữ liệu, không chứa giá trị dữ liệu.</div>
        </div>
      ) : rbac ? (
        <div className="small" style={{ margin: "0 0 12px" }}>
          <div><b>Thao tác:</b> {RBAC_OPS[rbac.op]} · <b>Vai trò:</b> {roleLabel(rbac.roleCode)}</div>
          <div><b>Người được {rbac.op === "grant" ? "cấp" : "thu hồi"}:</b> {rbac.targetName}{rbac.op === "grant" && ` · ${rbac.validTo ? `hạn đến ${dateVN(rbac.validTo)}` : "không thời hạn"}`}</div>
          <div><b>Lý do:</b> {rbac.reason}</div>
          <div className="muted">Vai trò chỉ được ghi vào hệ thống khi IAM hoàn tất bước cuối. Người được cấp không tham gia chuỗi duyệt.</div>
        </div>
      ) : (
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
      )}
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
                    {s.decision && (
                      <span className="muted small" style={{ fontWeight: 400 }}>
                        · {s.decision.actor.fullName}
                        {s.decision.onBehalf && ` (thay mặt ${s.decision.onBehalf.fullName})`}
                      </span>
                    )}
                    {!s.decision && s.assignee && s.idx > 0 && s.status !== "WAITING" && (
                      <span className="muted small" style={{ fontWeight: 400 }}>· giao cho {s.assignee.fullName}</span>
                    )}
                  </div>
                  <div className="step-meta">
                    {VERB[s.action]}
                    {s.decision && ` · ${s.decision.outcome === "RETURN" ? "trả lại" : s.status === "REJECTED" ? "từ chối" : "xong"} ${fmtTime(s.decision.decidedAt)}`}
                    {s.decision?.comment && ` — “${s.decision.comment}”`}
                    {s.sodWaived && <span className="conflict"> · xung đột SoD theo ngoại lệ</span>}
                  </div>
                  {isCur && s.startedAt && s.dueAt && <SlaBar startedAt={s.startedAt} dueAt={s.dueAt} slaHours={s.slaHours} />}
                  {isCur && canDecide && (
                    <DecisionBox
                      ticketId={t.id}
                      stepId={s.id}
                      version={t.version}
                      roleName={role(s).name}
                      isP={s.action === "P"}
                      canReturn={!rbac && !dt && !ops}
                      executeElsewhere={dt && s.action === "P" ? "Thực thi trong DataTrust (mã đề xuất " + dt.externalRef + "). Bước này tự hoàn tất khi DataTrust báo đã chạy. Không thực thi thì bấm Từ chối kèm lý do." : undefined}
                      onBehalfOf={s.assigneeId !== user.id ? s.assignee?.fullName : undefined}
                    />
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
