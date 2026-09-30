"use client";

import { Fragment, useEffect, useMemo, useState, useTransition, type ReactNode } from "react";
import { previewAction, submitAction } from "@/app/actions/tickets";
import type { Preview } from "@/lib/tickets/service";
import { ROLES, VERB, actName } from "@/lib/sod/catalog";
import { informedRoles } from "@/lib/sod/chain";
import {
  CAM_KET, CAP_BAC, DLCN, LOAI_PHIEU, MUC_KHAN, MUC_QUYEN, TANG, THI_TRUONG,
  emptyForm, emptyRow, validateForm, type FormRow, type TicketForm,
} from "@/lib/sod/form";
import { fmtDate } from "@/lib/format";
import { Badge } from "@/app/ui/badges";
import PhieuButton from "@/app/ui/phieu-button";
import Signature from "./signature";

type Errors = [string, string][];

// Khai báo ngoài component để React không tạo lại ô nhập mỗi lần gõ (mất focus)
function Row({ label, bad, children }: { label: ReactNode; bad?: boolean; children: ReactNode }) {
  return (
    <div className={`frow${bad ? " invalid" : ""}`}>
      <div className="flabel">{label}</div>
      <div className="fval">{children}</div>
    </div>
  );
}
const Req = () => <i>*</i>;

export default function CreateForm({ fullName, email }: { fullName: string; email: string }) {
  const [d, setD] = useState<TicketForm>(() => emptyForm(fullName, email));
  const [errors, setErrors] = useState<Errors>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [pending, startTransition] = useTransition();
  const invalid = new Set(errors.map(([k]) => k));

  // Xem trước chuỗi xử lý: server tính (cần danh bạ thật), chờ người dùng ngừng gõ 300ms. Không gửi chữ ký.
  const previewKey = useMemo(() => JSON.stringify({ ...d, signature: "" }), [d]);
  useEffect(() => {
    let alive = true;
    const id = setTimeout(async () => {
      const p = await previewAction(JSON.parse(previewKey));
      if (alive) setPreview(p);
    }, 300);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [previewKey]);

  const clearError = (k: string) => invalid.has(k) && setErrors((es) => es.filter(([e]) => e !== k));
  const set = <K extends keyof TicketForm>(k: K, v: TicketForm[K]) => {
    setD((p) => ({ ...p, [k]: v }));
    clearError(k);
  };
  const setRow = (i: number, k: keyof FormRow, v: string) => {
    setD((p) => ({ ...p, rows: p.rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)) }));
    clearError(`rows.${i}.${k}`);
  };

  const showErrors = (errs: Errors) => {
    setErrors(errs);
    requestAnimationFrame(() =>
      document.querySelector(".invalid, #errBox")?.scrollIntoView({ behavior: "smooth", block: "center" }),
    );
  };
  const checkForm = () => {
    const errs = validateForm(d);
    showErrors(errs);
    return errs.length === 0;
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkForm()) return;
    startTransition(async () => {
      const r = await submitAction(d); // thành công thì server chuyển sang trang chi tiết
      if (r?.errors.length) showErrors(r.errors);
    });
  };

  // ---- Các ô nhập (cùng cấu trúc bảng .ftable của bản mẫu)
  const radios = <K extends keyof TicketForm>(name: K, map: Record<string, string>) => (
    <div className="opts">
      {Object.entries(map).map(([v, l]) => (
        <label key={v} className="opt">
          <input type="radio" name={name} value={v} checked={d[name] === v} onChange={() => set(name, v as TicketForm[K])} /> {l}
        </label>
      ))}
    </div>
  );
  const text = (name: keyof TicketForm, placeholder = "") => (
    <input type="text" name={name} value={d[name] as string} placeholder={placeholder} onChange={(e) => set(name, e.target.value)} />
  );
  const area = (name: keyof TicketForm, placeholder = "") => (
    <textarea name={name} value={d[name] as string} placeholder={placeholder} onChange={(e) => set(name, e.target.value)} />
  );
  const showException = Boolean(preview?.violations) || d.exception;
  const draftSteps = preview?.steps.map((s) => ({ role: s.role, action: s.action })) ?? [];
  const draftConflicts = [...new Set(preview?.steps.flatMap((s) => s.conflicts) ?? [])];

  return (
    <div className="grid g2">
      <form className="stack" autoComplete="off" noValidate onSubmit={submit}>
        <div className="card">
          <div className="row small muted" style={{ marginBottom: 12 }}>
            Người nhập phiếu: <b>{fullName}</b> (tài khoản đang đăng nhập)
          </div>
          <div className="ftable">
            <Row label="Số phiếu"><span className="muted">Cấp tự động khi gửi (Bộ phận Kiểm soát Dữ liệu)</span></Row>
            <Row label="Ngày lập phiếu">{fmtDate()}</Row>
            <Row label={<>Loại phiếu <Req /></>} bad={invalid.has("loaiPhieu")}>{radios("loaiPhieu", LOAI_PHIEU)}</Row>
            <Row label={<>Mức độ khẩn <Req /></>} bad={invalid.has("khan")}>{radios("khan", MUC_KHAN)}</Row>
          </div>
        </div>

        <div className="card">
          <h2>Phần A. Thông tin người sử dụng quyền</h2>
          <div className="ftable">
            <Row label={<>Họ và tên <Req /></>} bad={invalid.has("hoTen")}>{text("hoTen")}</Row>
            <Row label={<>Mã nhân viên <Req /></>} bad={invalid.has("maNV")}>{text("maNV")}</Row>
            <Row label={<>Email công vụ <Req /></>} bad={invalid.has("email")}>
              <input type="email" name="email" value={d.email} placeholder="ten@congty.vn" onChange={(e) => set("email", e.target.value)} />
            </Row>
            <Row label={<>Khối / Phòng / Bộ phận <Req /></>} bad={invalid.has("phongBan")}>{text("phongBan")}</Row>
            <Row label={<>Chức danh và cấp bậc <Req /></>} bad={invalid.has("chucDanh") || invalid.has("capBac")}>
              {text("chucDanh", "Chức danh")}
              <div className="small muted" style={{ margin: "8px 0 4px" }}>Cấp bậc</div>
              {radios("capBac", Object.fromEntries(CAP_BAC.map((c) => [c, c])))}
            </Row>
            <Row label={<>Vị trí công việc và phạm vi phụ trách <Req /></>} bad={invalid.has("viTri")}>{area("viTri")}</Row>
            <Row label={<>Thị trường cung cấp dịch vụ <Req /></>} bad={invalid.has("thiTruong") || invalid.has("thiTruongGhiRo")}>
              {radios("thiTruong", THI_TRUONG)}
              {d.thiTruong === "intl" && <div style={{ marginTop: 8 }}>{text("thiTruongGhiRo", "Ghi rõ thị trường")}</div>}
            </Row>
            <Row label="Người nhập phiếu" bad={["ntHoTen", "ntChucDanh", "ntVanBan"].some((k) => invalid.has(k))}>
              <label className="check" style={{ margin: 0 }}>
                <input type="checkbox" checked={d.nhapThay} onChange={(e) => set("nhapThay", e.target.checked)} />
                <span>Nhập thay cho người sử dụng quyền</span>
              </label>
              {d.nhapThay && (
                <div className="stack" style={{ marginTop: 10 }}>
                  {text("ntHoTen", "Họ tên người nhập *")}
                  {text("ntChucDanh", "Chức danh *")}
                  {text("ntVanBan", "Văn bản/email phê duyệt của CBLĐ đơn vị cho phép nhập thay *")}
                </div>
              )}
            </Row>
          </div>
        </div>

        <div className="card">
          <h2>Phần B. Nội dung đề nghị</h2>
          <div className="table-wrap">
            <table className="rows">
              <thead>
                <tr><th>STT</th><th>Hệ thống (theo Phụ lục 01) *</th><th>Tài nguyên cụ thể *</th><th>Tầng dữ liệu *</th><th>Mức quyền *</th><th>Thời hạn đề nghị</th><th /></tr>
              </thead>
              <tbody>
                {d.rows.map((r, i) => {
                  const cls = (k: keyof FormRow) => (invalid.has(`rows.${i}.${k}`) ? "invalid" : undefined);
                  return (
                    <tr key={i}>
                      <td>{i + 1}</td>
                      <td className={cls("heThong")}><input type="text" value={r.heThong} onChange={(e) => setRow(i, "heThong", e.target.value)} /></td>
                      <td className={cls("taiNguyen")}><input type="text" value={r.taiNguyen} onChange={(e) => setRow(i, "taiNguyen", e.target.value)} /></td>
                      <td className={cls("tang")}>
                        <select value={r.tang} onChange={(e) => setRow(i, "tang", e.target.value)}>
                          <option value="">—</option>
                          {TANG.map((x) => <option key={x} value={x}>{x}</option>)}
                        </select>
                      </td>
                      <td className={cls("mucQuyen")}>
                        <select value={r.mucQuyen} onChange={(e) => setRow(i, "mucQuyen", e.target.value)}>
                          <option value="">—</option>
                          {MUC_QUYEN.map((x) => <option key={x} value={x}>{x}</option>)}
                        </select>
                      </td>
                      <td className={cls("thoiHan")}><input type="date" value={r.thoiHan} onChange={(e) => setRow(i, "thoiHan", e.target.value)} /></td>
                      <td>
                        {d.rows.length > 1 && (
                          <button type="button" className="icon-btn" title="Xoá dòng" onClick={() => setD((p) => ({ ...p, rows: p.rows.filter((_, j) => j !== i) }))}>
                            ✕
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <button type="button" className="btn sm" style={{ margin: "10px 0 16px" }} onClick={() => setD((p) => ({ ...p, rows: [...p.rows, emptyRow()] }))}>
            + Thêm dòng
          </button>
          <div className="ftable">
            <Row label={<>Mục đích sử dụng (gắn với nhiệm vụ hoặc dự án cụ thể) <Req /></>} bad={invalid.has("mucDich")}>{area("mucDich")}</Row>
            <Row label={<>Có liên quan dữ liệu cá nhân không? <Req /></>} bad={invalid.has("dlcn")}>
              {radios("dlcn", DLCN)}
              <div className="small muted" style={{ marginTop: 6 }}>
                DLCN nhạy cảm: bắt buộc nêu lý do nghiệp vụ và có ý kiến DPO/Ban Pháp chế &amp; Tuân thủ.
              </div>
            </Row>
            <Row label="Lý do nghiệp vụ đối với DLCN nhạy cảm hoặc yêu cầu gấp" bad={invalid.has("lyDo")}>
              {area("lyDo")}
              <div className="small muted" style={{ marginTop: 4 }}>Bắt buộc khi chọn DLCN nhạy cảm hoặc mức độ Gấp.</div>
            </Row>
          </div>
        </div>

        {showException && (
          <div className="card">
            <h2>Ngoại lệ SoD</h2>
            <p className="small muted" style={{ marginTop: -6 }}>
              Phiếu đang có xung đột SoD (xem bên phải). Nếu không đổi được người xử lý thì xin ngoại lệ theo rule.md mục 5 và mục 8.
            </p>
            <label className={`check${invalid.has("exception") ? " invalid" : ""}`}>
              <input type="checkbox" checked={d.exception} onChange={(e) => set("exception", e.target.checked)} />
              <span><b>Xin ngoại lệ SoD</b></span>
            </label>
            {d.exception && (
              <>
                <label className={`f${invalid.has("exReason") ? " invalid" : ""}`}><span>Lý do nghiệp vụ *</span>{area("exReason")}</label>
                <div className="two">
                  <label className={`f${invalid.has("exFrom") ? " invalid" : ""}`}>
                    <span>Hiệu lực từ *</span>
                    <input type="datetime-local" value={d.exFrom} onChange={(e) => set("exFrom", e.target.value)} />
                  </label>
                  <label className={`f${invalid.has("exTo") ? " invalid" : ""}`}>
                    <span>Đến *</span>
                    <input type="datetime-local" value={d.exTo} onChange={(e) => set("exTo", e.target.value)} />
                  </label>
                </div>
                <label className={`f${invalid.has("exControls") ? " invalid" : ""}`} style={{ margin: 0 }}>
                  <span>Biện pháp kiểm soát bù trừ *</span>
                  {area("exControls", "Giám sát phiên, log SIEM, tự thu hồi...")}
                </label>
              </>
            )}
          </div>
        )}

        <div className="card">
          <h2>Phần C. Cam kết của người sử dụng quyền</h2>
          <ul className="camket">{CAM_KET.map((c) => <li key={c}>{c}</li>)}</ul>
          <label className={`check${invalid.has("camKet") ? " invalid" : ""}`}>
            <input type="checkbox" checked={d.camKet} onChange={(e) => set("camKet", e.target.checked)} />
            <span><b>Tôi đã đọc và cam kết thực hiện các nội dung trên</b> <i className="req">*</i></span>
          </label>
          <div className="two" style={{ marginTop: 8 }}>
            <label className={`f${invalid.has("kyTen") ? " invalid" : ""}`}>
              <span>Người sử dụng quyền (ghi rõ họ tên) <i className="req">*</i></span>
              {text("kyTen")}
            </label>
            <label className="f"><span>Ngày</span><input type="text" value={fmtDate()} disabled /></label>
          </div>
          <div className="small muted" style={{ marginBottom: 6 }}>Chữ ký (vẽ bằng chuột hoặc ngón tay, không bắt buộc)</div>
          <Signature onChange={(v) => set("signature", v)} />
        </div>

        <div id="errBox">
          {errors.length > 0 && (
            <div className="alert bad" role="alert">
              <b>Còn {errors.length} mục cần điền / sửa:</b>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{errors.map(([k, m]) => <li key={k + m}>{m}</li>)}</ul>
            </div>
          )}
        </div>
        <div className="row">
          <button type="submit" className="btn primary" disabled={pending}>{pending ? "Đang gửi…" : "Gửi phiếu"}</button>
          <PhieuButton
            label="Xem trước & in phiếu"
            before={checkForm}
            form={d}
            steps={draftSteps}
            exception={{ id: null, conflicts: draftConflicts }}
          />
          <span className="spacer" />
          <button type="button" className="btn" onClick={() => confirm("Xoá toàn bộ nội dung đã điền?") && (setD(emptyForm(fullName, email)), setErrors([]))}>
            Làm lại
          </button>
        </div>
      </form>

      <PreviewPanel preview={preview} exception={d.exception} />
    </div>
  );
}

/** Khung phân loại + chuỗi xử lý dự kiến (renderPreview của bản mẫu) */
function PreviewPanel({ preview: p, exception }: { preview: Preview | null; exception: boolean }) {
  if (!p) return <div className="card muted">Đang dựng chuỗi xử lý…</div>;
  return (
    <div className="card" style={{ position: "sticky", top: 16, alignSelf: "start" }}>
      <h2>Phân loại</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        {p.acts.map((a) => <span key={a} className="chip blue">{actName(a)}</span>)}
      </div>
      <ul className="small muted" style={{ margin: "0 0 16px", paddingLeft: 18 }}>
        {p.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>
      {p.violations ? (
        <div className="alert bad">
          <b>Vi phạm SoD ({p.violations})</b> — không đủ người độc lập cho vai trò bên dưới{exception ? "" : ", cần xin ngoại lệ SoD"}.
        </div>
      ) : (
        <div className="alert ok"><b>Không có xung đột SoD</b> — khởi tạo, phê duyệt, thực thi độc lập.</div>
      )}
      <h2>Chuỗi xử lý ({p.steps.length} bước)</h2>
      <ol className="steps">
        {p.steps.map((s, i) => {
          const ph = p.phases[s.phase];
          const head = i > 0 && s.phase !== p.steps[i - 1].phase;
          return (
            <Fragment key={i}>
              {head && (
                <li className="phase-label">
                  {ph.name}
                  {ph.C.length > 0 && ` · tham vấn ${ph.C.map((r) => ROLES[r].short).join(", ")}`}
                </li>
              )}
              <li className="step">
                <div className="dot">{i + 1}</div>
                <div>
                  <div className="step-title">
                    <Badge l={s.action} /> {i === 0 ? "Người nhập phiếu" : ROLES[s.role].name}
                    <span className="muted small" style={{ fontWeight: 400 }}>
                      {i === 0 ? "Gửi phiếu" : VERB[s.action]}
                      {s.merged > 1 && ` · gộp ${s.merged} hoạt động`}
                    </span>
                  </div>
                  {s.slaHours !== null && <div className="small muted" style={{ marginTop: 2 }}>SLA {s.slaHours}h</div>}
                  {s.conflicts.map((c) => <div key={c} className="conflict">⚠ {c}</div>)}
                </div>
              </li>
            </Fragment>
          );
        })}
      </ol>
      <p className="small muted" style={{ marginBottom: 0 }}>
        Thông báo khi hoàn tất: {informedRoles(p.phases).map((r) => ROLES[r].short).join(", ") || "—"}
      </p>
    </div>
  );
}
