import Link from "next/link";
import { LETTERS, ROLES, VERB, type Letter, type RoleKey } from "@/lib/sod/catalog";
import type { TicketListItem } from "@/lib/tickets/queries";
import SlaBar from "./sla-bar";

export const Badge = ({ l }: { l: Letter }) => (
  <span className={`badge L-${l}`} title={LETTERS[l]}>
    {l}
  </span>
);

export const roleName = (code: string) => ROLES[code as RoleKey]?.name ?? code;

type StatusInput = { status: string; overdue?: boolean };
export function StatusBadge({ status, overdue }: StatusInput) {
  if (status === "OPEN" && overdue) return <span className="status st-breach">Quá SLA</span>;
  const [cls, label] = { OPEN: ["st-open", "Đang xử lý"], DONE: ["st-done", "Hoàn tất"], REJECTED: ["st-rejected", "Từ chối"] }[status] ?? ["", status];
  return <span className={`status ${cls}`}>{label}</span>;
}

/** Danh sách ticket dạng thẻ (giống cột trái trang Tickets của bản mẫu) */
export function TicketList({ tickets, empty }: { tickets: TicketListItem[]; empty: string }) {
  if (!tickets.length) return <div className="card empty">{empty}</div>;
  return (
    <div className="tlist">
      {tickets.map((t) => {
        const s = t.steps[0];
        return (
          <Link key={t.id} href={`/yeu-cau/${t.id}`} className="titem" style={{ color: "inherit", textDecoration: "none" }}>
            <div className="top">
              <span>{t.code}</span>
              <StatusBadge status={t.status} overdue={t.overdue} />
            </div>
            <div className="t">{t.title}</div>
            <div className="small muted">
              {t.status === "OPEN" && s ? `Chờ: ${roleName(s.roleCode)} ${VERB[s.action].toLowerCase()}` : null}
            </div>
            {t.status === "OPEN" && s?.startedAt && s.dueAt && <SlaBar startedAt={s.startedAt} dueAt={s.dueAt} slaHours={s.slaHours} />}
          </Link>
        );
      })}
    </div>
  );
}

/** Thanh chọn bộ lọc dạng liên kết (thay cho radio .seg của bản mẫu) */
export function Seg({ items, current }: { items: [href: string, label: string, key: string][]; current: string }) {
  return (
    <div className="seg">
      {items.map(([href, label, key]) => (
        <Link key={key} href={href} className={key === current ? "on" : ""}>
          {label}
        </Link>
      ))}
    </div>
  );
}
