"use client";

import { useActionState } from "react";
import { cancelAction } from "@/app/actions/tickets";
import { FormAlert } from "@/app/ui/form";

/** Người yêu cầu huỷ phiếu. Chỉ hiện khi còn huỷ được; server và DB kiểm lại khi bấm. */
export default function CancelBox({ ticketId, version }: { ticketId: string; version: number }) {
  const [state, action, pending] = useActionState(cancelAction, {});
  return (
    <details style={{ margin: "0 0 12px" }} open={Boolean(state.error)}>
      <summary>Huỷ phiếu</summary>
      <form action={action} className="box" style={{ margin: "8px 0 0" }}>
        <div className="small muted" style={{ marginBottom: 6 }}>
          Huỷ được khi phiếu chưa tới bước thực hiện. Sau đó muốn dừng thì mở phiếu thu hồi.
        </div>
        <FormAlert state={state} />
        <input type="hidden" name="ticketId" value={ticketId} />
        <input type="hidden" name="version" value={version} />
        <textarea
          name="reason"
          defaultValue={state.values?.reason}
          placeholder="Lý do huỷ phiếu (bắt buộc)"
          maxLength={2000}
          style={{ minHeight: 50, marginBottom: 8 }}
        />
        <button className="btn bad sm" disabled={pending}>
          {pending ? "Đang huỷ…" : "Huỷ phiếu"}
        </button>
      </form>
    </details>
  );
}
