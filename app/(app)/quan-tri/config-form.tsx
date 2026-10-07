"use client";

import { useState, useTransition } from "react";
import { proposeConfigAction } from "@/app/actions/config";
import { ACTIVITIES, LETTERS, ROLES, ROLE_KEYS, type Letter, type StepAction } from "@/lib/sod/catalog";
import { PRIORITY_KEYS, SLA_LABEL, diffConfig, type ConfigData } from "@/lib/config/schema";
import { PRIORITY_LABEL } from "@/lib/sod/catalog";

const num = (v: string) => (v === "" ? NaN : Number(v));

/** Form đề xuất cấu hình mới: điền sẵn giá trị đang hiệu lực. Đề xuất chưa có hiệu lực tới khi CISO duyệt. */
export default function ConfigForm({ active }: { active: ConfigData }) {
  const [c, setC] = useState<ConfigData>(active);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [pending, start] = useTransition();
  const changes = diffConfig(active, c);

  const setNum = <K extends "remindPct" | "escalatePct" | "criticalPct" | "staleCloseDays" | "delegationMaxDays">(k: K, v: string) => setC((p) => ({ ...p, [k]: num(v) }));
  const setCell = (i: number, j: number, l: string) =>
    setC((p) => ({ ...p, matrix: p.matrix.map((row, r) => (r === i ? row.slice(0, j) + l + row.slice(j + 1) : row)) }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSent(false);
    start(async () => {
      const r = await proposeConfigAction(c, reason);
      if (r.error) setError(r.error);
      else {
        setSent(true);
        setReason("");
      }
    });
  };

  const field = (label: string, value: number, onChange: (v: string) => void, step = "1") => (
    <label className="field" key={label} style={{ margin: 0 }}>
      <span>{label}</span>
      <input type="number" step={step} value={Number.isNaN(value) ? "" : value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );

  return (
    <form onSubmit={submit} className="stack" noValidate>
      {error && <div className="alert bad" role="alert">{error}</div>}
      {sent && <div className="alert ok" role="status">Đã gửi đề xuất. CISO sẽ được báo để duyệt; chưa có hiệu lực cho tới khi được duyệt.</div>}

      <h3 style={{ margin: "4px 0" }}>SLA mỗi bước (giờ)</h3>
      <div className="grid g4">
        {(Object.keys(c.sla) as StepAction[]).map((k) =>
          field(SLA_LABEL[k], c.sla[k], (v) => setC((p) => ({ ...p, sla: { ...p.sla, [k]: num(v) } }))),
        )}
      </div>
      <h3 style={{ margin: "4px 0" }}>Hệ số SLA theo mức ưu tiên</h3>
      <div className="grid g4">
        {PRIORITY_KEYS.map((k) =>
          field(PRIORITY_LABEL[k], c.priority[k], (v) => setC((p) => ({ ...p, priority: { ...p.priority, [k]: num(v) } })), "0.05"),
        )}
      </div>
      <h3 style={{ margin: "4px 0" }}>Mốc SLA và thời hạn khác</h3>
      <div className="grid g4">
        {field("Nhắc ở (% thời hạn)", c.remindPct, (v) => setNum("remindPct", v))}
        {field("Quá hạn, báo người dự phòng và Admin (%)", c.escalatePct, (v) => setNum("escalatePct", v))}
        {field("Báo CISO và Auditor (%)", c.criticalPct, (v) => setNum("criticalPct", v))}
        {field("Admin đóng phiếu “hết hạn” sau (ngày)", c.staleCloseDays, (v) => setNum("staleCloseDays", v))}
        {field("Ủy quyền tối đa (ngày)", c.delegationMaxDays, (v) => setNum("delegationMaxDays", v))}
      </div>

      <details>
        <summary>Ma trận SoD ({changes.filter((x) => x.startsWith("Ma trận")).length} ô đổi)</summary>
        <p className="small muted">
          Chọn lại ký hiệu từng ô. Requestor không được là người rà soát hoặc phê duyệt. Phiếu đã tạo giữ ma trận lúc tạo.
        </p>
        <div className="table-wrap">
          <table className="mx">
            <thead>
              <tr>
                <th>Hoạt động</th>
                {ROLE_KEYS.map((r) => <th key={r} title={ROLES[r].name}>{ROLES[r].short}</th>)}
              </tr>
            </thead>
            <tbody>
              {ACTIVITIES.map((a, i) => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  {ROLE_KEYS.map((r, j) => {
                    const l = c.matrix[i][j];
                    const changed = l !== active.matrix[i][j];
                    return (
                      <td key={r} style={changed ? { background: "var(--warn-soft)" } : undefined}>
                        <select aria-label={`${a.name}, ${ROLES[r].short}`} value={l} onChange={(e) => setCell(i, j, e.target.value)} style={{ padding: "2px 4px", width: 52 }}>
                          {(Object.keys(LETTERS) as Letter[]).map((k) => <option key={k} value={k}>{k}</option>)}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <div className="box">
        <b>{changes.length ? `${changes.length} thay đổi so với phiên bản đang hiệu lực` : "Chưa có thay đổi nào"}</b>
        {changes.length > 0 && <ul className="small" style={{ margin: "6px 0 0" }}>{changes.slice(0, 12).map((x) => <li key={x}>{x}</li>)}{changes.length > 12 && <li>… và {changes.length - 12} thay đổi nữa</li>}</ul>}
      </div>
      <label className="field" style={{ margin: 0 }}>
        <span>Lý do đề xuất (bắt buộc)</span>
        <textarea value={reason} maxLength={1000} onChange={(e) => setReason(e.target.value)} />
      </label>
      <div><button className="btn primary" disabled={pending || !changes.length}>{pending ? "Đang gửi…" : "Gửi đề xuất cho CISO duyệt"}</button></div>
    </form>
  );
}
