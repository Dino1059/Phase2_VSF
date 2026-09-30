"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "@/app/actions/notifications";
import type { NotificationList } from "@/lib/notify/service";
import { fmtTime } from "@/lib/format";

const POLL_MS = 30_000;

/** Chuông thông báo trên thanh đầu trang. Layout không render lại khi chuyển trang nên tự tải lại định kỳ. */
export default function Bell({ initial }: { initial: NotificationList }) {
  const [data, setData] = useState(initial);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const reload = useCallback(async () => setData(await fetchNotifications()), []);

  useEffect(() => {
    const id = setInterval(reload, POLL_MS);
    return () => clearInterval(id);
  }, [reload]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("click", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const toggle = () => {
    if (!open) reload();
    setOpen(!open);
  };
  const openItem = async (id: string, ticketId: string | null) => {
    setOpen(false);
    await markNotificationRead(id);
    reload();
    if (ticketId) router.push(`/yeu-cau/${ticketId}`);
  };
  const readAll = async () => {
    await markAllNotificationsRead();
    reload();
  };

  return (
    <div ref={ref}>
      <button type="button" className="bell" onClick={toggle} title="Thông báo" aria-label={`Thông báo (${data.unread} chưa đọc)`} aria-expanded={open}>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {data.unread > 0 && <span className="bell-count">{data.unread > 99 ? "99+" : data.unread}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label="Thông báo">
          <div className="row" style={{ padding: "4px 6px 8px" }}>
            <b>Thông báo</b>
            <span className="spacer" />
            {data.unread > 0 && (
              <button type="button" className="btn sm" onClick={readAll}>
                Đánh dấu đã đọc
              </button>
            )}
          </div>
          {data.items.length ? (
            data.items.map((n) => (
              <button
                key={n.id}
                type="button"
                className={`notif ${n.level}${n.readAt ? "" : " unread"}`}
                onClick={() => openItem(n.id, n.ticketId)}
              >
                <div className="small muted">{fmtTime(n.createdAt)}</div>
                {n.message}
              </button>
            ))
          ) : (
            <div className="empty">Chưa có thông báo</div>
          )}
        </div>
      )}
    </div>
  );
}
