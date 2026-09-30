"use client";

import { useEffect, useState } from "react";
import { SOD_CONFIG } from "@/lib/sod/catalog";
import { fmtDur, fmtTime } from "@/lib/format";

/** Thanh SLA của bước đang xử lý, tự cập nhật mỗi 30 giây. */
export default function SlaBar({ startedAt, dueAt, slaHours }: { startedAt: Date; dueAt: Date; slaHours: number | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  const start = new Date(startedAt).getTime();
  const due = new Date(dueAt).getTime();
  const pct = Math.min(100, ((now - start) / Math.max(1, due - start)) * 100);
  const left = due - now;
  const cls = left < 0 ? "bad" : pct >= SOD_CONFIG.remindPct ? "warn" : "";
  return (
    <div className="sla">
      <div className="row small">
        <span className={left < 0 ? "conflict" : "muted"} suppressHydrationWarning>
          {left < 0 ? `Quá hạn ${fmtDur(left)}` : `Còn ${fmtDur(left)}`}
        </span>
        <span className="spacer" />
        <span className="muted">
          SLA {slaHours}h · hạn {fmtTime(due)}
        </span>
      </div>
      <div className={`bar ${cls}`}>
        <i style={{ width: `${pct}%` }} suppressHydrationWarning />
      </div>
    </div>
  );
}
