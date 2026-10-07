"use client";

import { useActionState } from "react";
import { expireAction } from "@/app/actions/tickets";
import { FormAlert } from "@/app/ui/form";

/** Admin đóng phiếu quá số ngày không ai xử lý. Đóng, không phải duyệt; server và DB kiểm lại số ngày chờ. */
export default function ExpireBox({ ticketId, version, days }: { ticketId: string; version: number; days: number }) {
  const [state, action, pending] = useActionState(expireAction, {});
  return (
    <details style={{ margin: "0 0 12px" }} open={Boolean(state.error)}>
      <summary style={{ color: "var(--bad)" }}>Phiếu đã quá {days} ngày không ai xử lý: đóng “hết hạn”</summary>
      <form action={action} className="box" style={{ margin: "8px 0 0" }}>
        <div className="small muted" style={{ marginBottom: 6 }}>
          Đóng phiếu không phải là duyệt: không ai được cấp quyền từ phiếu này. Người yêu cầu muốn tiếp tục phải lập phiếu mới.
        </div>
        <FormAlert state={state} />
        <input type="hidden" name="ticketId" value={ticketId} />
        <input type="hidden" name="version" value={version} />
        <textarea name="reason" defaultValue={state.values?.reason} placeholder="Lý do đóng phiếu (bắt buộc)" maxLength={2000} style={{ minHeight: 50, marginBottom: 8 }} />
        <button className="btn bad sm" disabled={pending}>{pending ? "Đang đóng…" : "Đóng phiếu hết hạn"}</button>
      </form>
    </details>
  );
}
