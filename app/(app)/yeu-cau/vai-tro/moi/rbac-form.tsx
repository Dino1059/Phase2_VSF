"use client";

import { useState, useTransition } from "react";
import { submitRbacAction } from "@/app/actions/tickets";
import { RBAC_OPS, RBAC_ROLES, roleLabel } from "@/lib/sod/rbac";

type Person = { id: string; fullName: string; username: string; roles: string[] };

export default function RbacForm({ people }: { people: Person[] }) {
  const [op, setOp] = useState<"grant" | "revoke">("grant");
  const [targetUserId, setTarget] = useState("");
  const [roleCode, setRole] = useState("");
  const [validTo, setValidTo] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<[string, string][]>([]);
  const [pending, start] = useTransition();

  const target = people.find((p) => p.id === targetUserId);
  // Cấp: các vai trò người đó chưa giữ. Thu hồi: các vai trò đang giữ (trừ REQ, không thu hồi qua phiếu).
  const roles = RBAC_ROLES.filter((r) => (op === "grant" ? !target?.roles.includes(r) : !!target?.roles.includes(r)));
  const bad = (k: string) => errors.some(([e]) => e === k);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const missing: [string, string][] = [];
    if (!targetUserId) missing.push(["targetUserId", "Chọn người được cấp / bị thu hồi"]);
    if (!roleCode) missing.push(["roleCode", "Chọn vai trò"]);
    if (!reason.trim()) missing.push(["reason", "Nhập lý do"]);
    if (missing.length) return setErrors(missing);
    setErrors([]);
    start(async () => {
      const r = await submitRbacAction({ op, targetUserId, roleCode, validTo: op === "grant" ? validTo : "", reason });
      if (r?.errors.length) setErrors(r.errors);
    });
  };

  return (
    <form className="card stack" style={{ maxWidth: 640 }} noValidate onSubmit={submit}>
      {errors.length > 0 && (
        <div className="alert bad" role="alert">
          <ul style={{ margin: 0, paddingLeft: 18 }}>{errors.map(([k, m]) => <li key={k + m}>{m}</li>)}</ul>
        </div>
      )}
      <div className="field">
        <label>Thao tác</label>
        <div className="opts">
          {(Object.keys(RBAC_OPS) as (keyof typeof RBAC_OPS)[]).map((k) => (
            <label key={k} className="opt">
              <input type="radio" name="op" checked={op === k} onChange={() => { setOp(k); setRole(""); }} /> {RBAC_OPS[k]}
            </label>
          ))}
        </div>
      </div>
      <div className={`field${bad("targetUserId") ? " invalid" : ""}`}>
        <label htmlFor="f-target">Người được {op === "grant" ? "cấp" : "thu hồi"} vai trò</label>
        <select id="f-target" value={targetUserId} onChange={(e) => { setTarget(e.target.value); setRole(""); }}>
          <option value="">Chọn người</option>
          {people.map((p) => <option key={p.id} value={p.id}>{p.fullName} ({p.username})</option>)}
        </select>
      </div>
      <div className={`field${bad("roleCode") ? " invalid" : ""}`}>
        <label htmlFor="f-role">Vai trò</label>
        <select id="f-role" value={roleCode} onChange={(e) => setRole(e.target.value)} disabled={!target}>
          <option value="">{target ? (roles.length ? "Chọn vai trò" : "Không có vai trò phù hợp") : "Chọn người trước"}</option>
          {roles.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
        </select>
        {target && <p className="hint">{target.fullName} đang giữ: {target.roles.map(roleLabel).join(", ") || "chưa có vai trò nào"}.</p>}
      </div>
      {op === "grant" && (
        <div className="field">
          <label htmlFor="f-validto">Hạn của vai trò (để trống nếu không thời hạn)</label>
          <input id="f-validto" type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} />
        </div>
      )}
      <div className={`field${bad("reason") ? " invalid" : ""}`}>
        <label htmlFor="f-reason">Lý do</label>
        <textarea id="f-reason" value={reason} maxLength={1000} onChange={(e) => setReason(e.target.value)} />
      </div>
      <div><button className="btn primary" disabled={pending}>{pending ? "Đang gửi…" : "Gửi phiếu"}</button></div>
    </form>
  );
}
