"use client";

import { useActionState } from "react";
import { decideAction } from "@/app/actions/tickets";
import { FormAlert } from "@/app/ui/form";

type Props = { ticketId: string; stepId: string; version: number; roleName: string; isP: boolean; onBehalfOf?: string; canReturn?: boolean };

/** Ô thao tác của người được giao bước đang xử lý. Server kiểm lại toàn bộ khi bấm. */
export default function DecisionBox({ ticketId, stepId, version, roleName, isP, onBehalfOf, canReturn = true }: Props) {
  const [state, action, pending] = useActionState(decideAction, {});
  return (
    <form action={action} className="box" style={{ margin: "10px 0 0" }}>
      <div className="small muted" style={{ marginBottom: 6 }}>
        Bạn đang xử lý bước này với vai trò <b>{roleName}</b>
        {onBehalfOf && <> · thay mặt <b>{onBehalfOf}</b> (được ủy quyền)</>}
      </div>
      <FormAlert state={state} />
      <input type="hidden" name="ticketId" value={ticketId} />
      <input type="hidden" name="stepId" value={stepId} />
      <input type="hidden" name="version" value={version} />
      <textarea
        name="comment"
        defaultValue={state.values?.comment}
        placeholder="Ghi chú / bằng chứng (bắt buộc khi từ chối hoặc trả lại)"
        maxLength={2000}
        style={{ minHeight: 50, marginBottom: 8 }}
      />
      <div className="row">
        <button className="btn ok sm" name="decision" value="approve" disabled={pending}>
          {isP ? "Hoàn tất" : "Duyệt"}
        </button>
        <button className="btn bad sm" name="decision" value="reject" disabled={pending}>
          Từ chối
        </button>
        {canReturn && (
        <button className="btn sm" name="decision" value="return" disabled={pending} title="Trả phiếu về người yêu cầu để bổ sung. SLA tạm dừng.">
          Trả lại để bổ sung
        </button>
        )}
      </div>
    </form>
  );
}
