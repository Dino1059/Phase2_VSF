import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { requireUser } from "@/lib/auth/session";
import { canViewAuditLog } from "@/lib/authz/policy";
import { AuditAction, requestMeta, writeAudit } from "@/lib/audit";
import type { Prisma } from "@/app/generated/prisma/client";

export const metadata = { title: "Nhật ký kiểm toán · SoD Flow" };

const LABELS: Record<string, string> = {
  [AuditAction.LoginSuccess]: "Đăng nhập thành công",
  [AuditAction.LoginFailure]: "Đăng nhập thất bại",
  [AuditAction.Logout]: "Đăng xuất",
  [AuditAction.AccountLocked]: "Khoá tài khoản tạm thời",
  [AuditAction.Register]: "Đăng ký",
  [AuditAction.CodeSent]: "Gửi mã xác nhận",
  [AuditAction.VerifySuccess]: "Xác nhận email",
  [AuditAction.VerifyFailure]: "Xác nhận email thất bại",
  [AuditAction.PasswordChanged]: "Đổi mật khẩu",
  [AuditAction.AuditViewed]: "Xem nhật ký",
  [AuditAction.TicketSubmitted]: "Gửi phiếu",
  [AuditAction.StepApproved]: "Duyệt bước",
  [AuditAction.StepCompleted]: "Hoàn tất bước",
  [AuditAction.StepRejected]: "Từ chối",
  [AuditAction.TicketDone]: "Ticket hoàn tất",
  [AuditAction.DecisionDenied]: "Thao tác bị chặn",
};
const BAD = new Set<string>([AuditAction.LoginFailure, AuditAction.AccountLocked, AuditAction.VerifyFailure, AuditAction.DecisionDenied]);

const GROUPS: Record<string, string[] | undefined> = {
  all: undefined,
  login: [AuditAction.LoginSuccess, AuditAction.LoginFailure, AuditAction.AccountLocked, AuditAction.Logout],
  failed: [AuditAction.LoginFailure, AuditAction.AccountLocked, AuditAction.VerifyFailure, AuditAction.DecisionDenied],
  register: [AuditAction.Register, AuditAction.CodeSent, AuditAction.VerifySuccess, AuditAction.VerifyFailure],
  ticket: [AuditAction.TicketSubmitted, AuditAction.StepApproved, AuditAction.StepCompleted, AuditAction.StepRejected, AuditAction.TicketDone, AuditAction.DecisionDenied],
};

const fmt = (d: Date) =>
  d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", dateStyle: "short", timeStyle: "medium" });

export default async function AuditPage({ searchParams }: PageProps<"/nhat-ky">) {
  const user = await requireUser();
  if (!canViewAuditLog(user)) notFound();

  const sp = await searchParams;
  const email = typeof sp.email === "string" ? sp.email.trim().toLowerCase() : "";
  const group = typeof sp.group === "string" && sp.group in GROUPS ? sp.group : "login";

  const where: Prisma.AuditLogWhereInput = {
    ...(email && { actorEmail: { contains: email } }),
    ...(GROUPS[group] && { action: { in: GROUPS[group] } }),
  };
  const [rows, broken] = await Promise.all([
    prisma.auditLog.findMany({ where, orderBy: { id: "desc" }, take: 200 }),
    prisma.$queryRaw<{ id: bigint; problem: string }[]>`SELECT * FROM audit_log_verify() LIMIT 5`,
  ]);

  // Việc xem nhật ký cũng được ghi lại
  await writeAudit({
    action: AuditAction.AuditViewed,
    actorUserId: user.id,
    actorEmail: user.email,
    details: { email, group, rows: rows.length },
    meta: await requestMeta(),
  });

  return (
    <>
      <h1>Nhật ký kiểm toán</h1>
      <p className="muted">Chỉ đọc. Mỗi dòng giữ mã băm của dòng trước, sửa hay xoá sẽ bị phát hiện.</p>

      {broken.length === 0 ? (
        <div className="alert ok">Chuỗi nhật ký nguyên vẹn.</div>
      ) : (
        <div className="alert bad">
          Phát hiện nhật ký bị can thiệp: {broken.map((b) => `#${b.id} (${b.problem})`).join(", ")}
        </div>
      )}

      <form className="filters" method="get">
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" name="email" defaultValue={email} placeholder="Lọc theo email" />
        </div>
        <div className="field">
          <label htmlFor="group">Loại sự kiện</label>
          <select id="group" name="group" defaultValue={group}>
            <option value="login">Đăng nhập / đăng xuất</option>
            <option value="failed">Chỉ thất bại</option>
            <option value="register">Đăng ký / xác nhận</option>
            <option value="ticket">Ticket</option>
            <option value="all">Tất cả</option>
          </select>
        </div>
        <button className="btn" type="submit">Lọc</button>
      </form>

      <div className="card table-wrap" style={{ padding: 0 }}>
        <table className="log-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Thời điểm</th>
              <th>Sự kiện</th>
              <th>Email</th>
              <th>IP</th>
              <th>Chi tiết</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id.toString()}>
                <td className="muted">{r.id.toString()}</td>
                <td style={{ whiteSpace: "nowrap" }}>{fmt(r.occurredAt)}</td>
                <td className={BAD.has(r.action) ? "tag-bad" : r.action === AuditAction.LoginSuccess ? "tag-ok" : ""}>
                  {LABELS[r.action] ?? r.action}
                </td>
                <td>{r.actorEmail ?? <span className="muted">—</span>}</td>
                <td className="muted">{r.ip ?? "—"}</td>
                <td>{r.details ? <code>{JSON.stringify(r.details)}</code> : <span className="muted">—</span>}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="muted" style={{ textAlign: "center", padding: 24 }}>
                  Không có sự kiện nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="muted small">Hiển thị tối đa 200 dòng mới nhất.</p>
    </>
  );
}
