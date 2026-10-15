"use client";

import { useState, useTransition } from "react";
import { submitOpsAction } from "@/app/actions/tickets";
import { OPS_FIELDS, type OpsFormType } from "@/lib/sod/ops";

export default function OpsFormView({ type }: { type: OpsFormType }) {
  const spec = OPS_FIELDS[type];
  const alwaysPii = type === "pii_query" || type === "pii_export";
  const [title, setTitle] = useState("");
  const [system, setSystem] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [pii, setPii] = useState(alwaysPii);
  const [reason, setReason] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<[string, string][]>([]);
  const [pending, start] = useTransition();

  const bad = (k: string) => errors.some(([e]) => e === k);
  const set = (k: string, v: string) => setFields((p) => ({ ...p, [k]: v }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors([]);
    start(async () => {
      const r = await submitOpsAction({ type, title, system, urgent, pii: alwaysPii || pii, reason, fields });
      if (r?.errors.length) setErrors(r.errors);
    });
  };

  return (
    <form className="card stack" style={{ maxWidth: 720 }} noValidate onSubmit={submit}>
      {errors.length > 0 && (
        <div className="alert bad" role="alert">
          <ul style={{ margin: 0, paddingLeft: 18 }}>{errors.map(([k, m]) => <li key={k + m}>{m}</li>)}</ul>
        </div>
      )}
      <div className={`field${bad("title") ? " invalid" : ""}`}>
        <label htmlFor="f-title">Tiêu đề</label>
        <input id="f-title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className={`field${bad("system") ? " invalid" : ""}`}>
        <label htmlFor="f-system">Hệ thống / đối tượng liên quan</label>
        <input id="f-system" value={system} maxLength={300} onChange={(e) => setSystem(e.target.value)} />
      </div>
      {spec.map((f) => {
        const id = `f-${f.key}`;
        const v = fields[f.key] ?? "";
        return (
          <div key={f.key} className={`field${bad(`fields.${f.key}`) ? " invalid" : ""}`}>
            <label htmlFor={id}>{f.label}</label>
            {f.kind === "textarea" ? (
              <textarea id={id} value={v} maxLength={f.max} onChange={(e) => set(f.key, e.target.value)} />
            ) : f.kind === "select" ? (
              <select id={id} value={v} onChange={(e) => set(f.key, e.target.value)}>
                <option value="">Chọn</option>
                {Object.entries(f.options ?? {}).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>
            ) : (
              <input id={id} type={f.kind === "date" ? "date" : "text"} inputMode={f.kind === "number" ? "numeric" : undefined} value={v} maxLength={f.max} onChange={(e) => set(f.key, e.target.value)} />
            )}
          </div>
        );
      })}
      <div className={`field${bad("reason") ? " invalid" : ""}`}>
        <label htmlFor="f-reason">Lý do / mục đích</label>
        <textarea id="f-reason" value={reason} maxLength={2000} onChange={(e) => setReason(e.target.value)} />
      </div>
      <div className="opts">
        {type !== "incident" && (
          <label className="opt"><input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} /> Gấp</label>
        )}
        <label className="opt">
          <input type="checkbox" checked={alwaysPii || pii} disabled={alwaysPii} onChange={(e) => setPii(e.target.checked)} /> Liên quan dữ liệu cá nhân (thêm DPO rà soát)
        </label>
      </div>
      <div><button className="btn primary" disabled={pending}>{pending ? "Đang gửi…" : "Gửi phiếu"}</button></div>
    </form>
  );
}
