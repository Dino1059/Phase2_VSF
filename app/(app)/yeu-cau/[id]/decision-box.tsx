"use client";

import { useActionState } from "react";
import { decideAction } from "@/app/actions/tickets";
import { FormAlert } from "@/app/ui/form";

type Props = { ticketId: string; stepId: string; version: number; roleName: string; isP: boolean };

/** Ô thao tác của người được giao bước đang xử lý. Server kiểm lại toàn bộ khi bấm. */
export default function DecisionBox({ ticketId, stepId, version, roleName, isP }: Props) {
  const [state, action, pending] = useActionState(decideAction, {});
  return (
    <form action={action} className="box" style={{ margin: "10px 0 0" }}>
      <div className="small muted" style={{ marginBottom: 6 }}>
        Bạn đang xử lý bước này với vai trò <b>{roleName}</b>
      </div>
      <FormAlert state={state} />
      <input type="hidden" name="ticketId" value={ticketId} />
      <input type="hidden" name="stepId" value={stepId} />
      <input type="hidden" name="version" value={version} />
      <textarea
        name="comment"
        defaultValue={state.values?.comment}
        placeholder="Ghi chú / bằng chứng (bắt buộc khi từ chối)"
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
      </div>
    </form>
  );
}
