"use client";

import { useActionState, useState } from "react";
import { createDelegationAction } from "@/app/actions/delegations";
import { Field, FormAlert } from "@/app/ui/form";

type Props = { roles: { code: string; name: string }[]; candidates: Record<string, { id: string; fullName: string }[]> };

export default function DelegationForm({ roles, candidates }: Props) {
  const [state, action, pending] = useActionState(createDelegationAction, {});
  const [role, setRole] = useState(state.values?.roleCode ?? roles[0].code);
  const people = candidates[role] ?? [];
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" });
  return (
    <form action={action} className="stack" style={{ maxWidth: 520 }}>
      <FormAlert state={state} />
      <div className="field">
        <label htmlFor="f-roleCode">Vai trò ủy quyền</label>
        <select id="f-roleCode" name="roleCode" value={role} onChange={(e) => setRole(e.target.value)}>
          {roles.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="f-delegateId">Người nhận (cùng vai trò)</label>
        <select id="f-delegateId" name="delegateId" key={role} defaultValue={state.values?.delegateId ?? ""} aria-invalid={state.fieldErrors?.delegateId ? true : undefined}>
          <option value="" disabled>Chọn người nhận</option>
          {people.map((p) => <option key={p.id} value={p.id}>{p.fullName}</option>)}
        </select>
        {!people.length && <p className="hint">Chưa có ai khác giữ vai trò này.</p>}
        {state.fieldErrors?.delegateId && <p className="err">{state.fieldErrors.delegateId[0]}</p>}
      </div>
      <div className="two">
        <Field name="from" label="Từ ngày" type="date" min={today} defaultValue={today} state={state} />
        <Field name="to" label="Đến hết ngày" type="date" min={today} state={state} />
      </div>
      <Field name="reason" label="Lý do" placeholder="Ví dụ: nghỉ phép 15–20/10" maxLength={500} state={state} />
      <div><button className="btn primary" disabled={pending}>{pending ? "Đang lưu…" : "Ủy quyền"}</button></div>
    </form>
  );
}
