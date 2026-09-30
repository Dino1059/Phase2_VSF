import Link from "next/link";
import { logout } from "@/app/actions/auth";
import type { CurrentUser } from "@/lib/auth/session";
import { canSubmitTicket, canViewAuditLog, hasRole, seesAllTickets } from "@/lib/authz/policy";
import { listNotifications, syncSlaNotifications } from "@/lib/notify/service";
import Bell from "./bell";
import Nav from "./nav";

/** Vai trò có thể được giao bước xử lý */
const HANDLER_ROLES = ["LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD"];

export default async function Topbar({ user }: { user: CurrentUser }) {
  // Menu theo vai trò (KE_HOACH.md mục 1). Ẩn menu chỉ để gọn — trang và action vẫn tự kiểm quyền.
  const links: [string, string][] = [["/", "Tổng quan"]];
  if (canSubmitTicket(user)) links.push(["/yeu-cau/moi", "Tạo phiếu"]);
  links.push(["/yeu-cau", seesAllTickets(user) ? "Tickets" : "Yêu cầu của tôi"]);
  if (HANDLER_ROLES.some((r) => hasRole(user, r))) links.push(["/hop-viec", "Hộp việc"]);
  links.push(["/ma-tran", "Ma trận"]);
  if (canViewAuditLog(user)) links.push(["/nhat-ky", "Nhật ký"]);

  await syncSlaNotifications(user.id);
  const notifications = await listNotifications(user.id);

  return (
    <header className="topbar">
      <div className="wrap topbar-inner">
        <Link href="/" className="brand">
          <span className="logo">S</span>SoD Flow
        </Link>
        <Nav links={links} />
        <Bell initial={notifications} />
        <Link href="/doi-mat-khau" className="user" title="Đổi mật khẩu">
          {user.fullName}
        </Link>
        <form action={logout}>
          <button type="submit" className="btn sm">Đăng xuất</button>
        </form>
      </div>
    </header>
  );
}
