import Link from "next/link";
import { requireUser } from "@/lib/auth/session";
import { ACTIVITIES, CONFLICT_PAIRS, DEFAULT_MATRIX, LETTERS, MATRIX_NOTES, MATRIX_RULES, ROLES, ROLE_KEYS, TICKET_TYPES, rowNo, type Letter } from "@/lib/sod/catalog";
import { phaseSteps } from "@/lib/sod/chain";
import { activeConfig } from "@/lib/config/queries";
import { Badge } from "@/app/ui/badges";

export const metadata = { title: "Ma trận SoD · SoD Flow" };

const typesOf = (actId: number) => TICKET_TYPES.filter((t) => (t.acts as readonly number[]).includes(actId));

export default async function MatrixPage({ searchParams }: PageProps<"/ma-tran">) {
  await requireUser();
  const cfg = await activeConfig(); // ma trận của phiên bản cấu hình đang hiệu lực
  const hd = Number((await searchParams).hd);
  const sel = ACTIVITIES.find((a) => a.id === hd);
  const active = cfg.config.matrix;
  const ps = sel && phaseSteps(sel.id, {}, active);
  const psNew = sel && active[sel.id] !== DEFAULT_MATRIX[sel.id] ? phaseSteps(sel.id, {}, DEFAULT_MATRIX) : undefined;
  const short = (r: keyof typeof ROLES) => ROLES[r].short;
  // Số ô của phiên bản đang hiệu lực còn khác ma trận chuẩn (điều chỉnh chưa được duyệt áp dụng)
  const pending = ACTIVITIES.reduce((n, a) => n + [...active[a.id]].filter((l, j) => l !== DEFAULT_MATRIX[a.id][j]).length, 0);
  const chain = (seq: NonNullable<typeof ps>["seq"]) =>
    seq.length ? (
      seq.map(([r, l], i) => (
        <span key={i} className="row">
          {i > 0 && <span className="muted">→</span>}
          <span className="chip">
            <Badge l={l} /> {short(r)}
          </span>
        </span>
      ))
    ) : (
      <span className="muted">Chỉ người khởi tạo thực hiện</span>
    );

  return (
    <>
      <h1>Ma trận SoD</h1>
      <p className="sub">
        Bấm vào một hoạt động để xem thứ tự xử lý được sinh ra. Phiên bản cấu hình đang hiệu lực: <b>{cfg.seq}</b>. Phiếu đã tạo giữ ma trận lúc tạo.
      </p>
      <div className="legend" style={{ marginBottom: 12 }}>
        {(Object.entries(LETTERS) as [Letter, string][]).map(([k, v]) => (
          <span key={k}>
            <Badge l={k} /> {v}
          </span>
        ))}
      </div>
      {pending > 0 && (
        <div className="alert warn">
          Phiên bản {cfg.seq} đang hiệu lực chưa áp dụng điều chỉnh mới ({pending} ô, hiển thị dạng <i>cũ → mới</i>). Để áp dụng: Admin vào{" "}
          <Link href="/quan-tri">Quản trị</Link>, bấm “Nạp ma trận chuẩn”, gửi đề xuất; CISO duyệt thì có hiệu lực cho phiếu tạo sau.
        </div>
      )}
      <div className="card" style={{ padding: 8 }}>
        <div className="table-wrap">
          <table className="mx">
            <thead>
              <tr>
                <th className="no">#</th>
                <th className="act">Hoạt động kiểm soát</th>
                {ROLE_KEYS.map((r) => (
                  <th key={r} title={ROLES[r].name}>{short(r)}</th>
                ))}
                <th className="act">Loại phiếu dùng dòng này</th>
              </tr>
            </thead>
            <tbody>
              {ACTIVITIES.map((a) => (
                <tr key={a.id} className={a.id === sel?.id ? "sel" : undefined}>
                  <td className="no">
                    {rowNo(a.id)}
                    {MATRIX_NOTES[a.id] && <sup className="note-mark">*</sup>}
                  </td>
                  <td className="act">
                    <Link href={`/ma-tran?hd=${a.id}#chuoi`} scroll={false} style={{ color: "inherit", textDecoration: "none" }}>
                      {a.name}
                    </Link>
                  </td>
                  {ROLE_KEYS.map((r, j) => {
                    const cur = active[a.id][j] as Letter;
                    const next = DEFAULT_MATRIX[a.id][j] as Letter;
                    const noted = MATRIX_NOTES[a.id]?.roles.includes(r);
                    return (
                      <td key={r} className={noted || cur !== next ? "edited" : undefined} title={noted ? MATRIX_NOTES[a.id].text : undefined}>
                        {cur !== next ? (
                          <span className="was-now">
                            <span className="was"><Badge l={cur} /></span>→<Badge l={next} />
                          </span>
                        ) : (
                          <Badge l={cur} />
                        )}
                      </td>
                    );
                  })}
                  <td className="act small">
                    {typesOf(a.id).map((t, i) => (
                      <span key={t.id}>
                        {i > 0 && " · "}
                        {t.name}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Ghi chú điều chỉnh ma trận</h2>
        <p className="small muted" style={{ marginTop: -6 }}>Quy tắc đọc ma trận:</p>
        <ul className="small">
          {MATRIX_RULES.map((t) => <li key={t}>{t}</li>)}
        </ul>
        <p className="small muted">Các dòng đã sửa hoặc có ghi chú (ô viền vàng trên bảng, dòng có dấu *; di chuột vào ô để xem):</p>
        <ul className="small" style={{ marginBottom: 0 }}>
          {Object.entries(MATRIX_NOTES).map(([id, n]) => (
            <li key={id}>
              <Link href={`/ma-tran?hd=${id}#chuoi`} scroll={false}><b>Dòng {rowNo(Number(id))}</b></Link> · {ACTIVITIES[Number(id)].name}: {n.text}
            </li>
          ))}
        </ul>
      </div>

      {sel && ps && (
        <div id="chuoi" className="card" style={{ margin: "16px 0" }}>
          <h2>
            Dòng {rowNo(sel.id)} · {sel.name}
          </h2>
          <p className="small muted" style={{ marginTop: -6 }}>
            {sel.kind === "approval" ? "Hoạt động phê duyệt: rà soát → phê duyệt → thực thi" : "Hoạt động thực hiện: thực hiện → rà soát → nghiệm thu"}
          </p>
          {psNew && <p className="small" style={{ margin: "0 0 4px" }}><b>Đang hiệu lực (phiên bản {cfg.seq})</b></p>}
          <div className="row">{chain(ps.seq)}</div>
          {psNew && (
            <>
              <p className="small" style={{ margin: "10px 0 4px" }}><b>Sau điều chỉnh</b></p>
              <div className="row">{chain(psNew.seq)}</div>
            </>
          )}
          {MATRIX_NOTES[sel.id] && <p className="small alert warn" style={{ margin: "10px 0 0" }}>Ghi chú: {MATRIX_NOTES[sel.id].text}</p>}
          <p className="small muted" style={{ marginBottom: 0 }}>
            Tham vấn: {ps.C.map(short).join(", ") || "—"} · Thông báo: {ps.I.map(short).join(", ") || "—"}
          </p>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <details>
          <summary>Các cặp xung đột bắt buộc</summary>
          <ul>
            {CONFLICT_PAIRS.map(([a, b]) => (
              <li key={a}>
                <b>{a}</b> — {b}
              </li>
            ))}
          </ul>
        </details>
        <details>
          <summary>Quy tắc xử lý ngoại lệ</summary>
          <ol>
            <li>Chỉ cho phép khi có lý do nghiệp vụ hoặc sự cố khẩn cấp ghi nhận trong ticket.</li>
            <li>Nêu rõ phạm vi, người sử dụng, thời gian hiệu lực, rủi ro và biện pháp bù trừ.</li>
            <li>Quyền tạm thời, ưu tiên PAM/JIT và tự động thu hồi.</li>
            <li>Level 2 hoặc PII cần DPO rà soát; Level 3 cần CISO phê duyệt.</li>
            <li>Break-glass phải ghi log, giám sát phiên, hậu kiểm trong 24 giờ.</li>
            <li>Không dùng ngoại lệ để duy trì quyền lâu dài hoặc bù thiếu nhân sự.</li>
          </ol>
        </details>
        <details>
          <summary>Kiểm soát định kỳ &amp; bằng chứng</summary>
          <ul>
            <li><b>Hàng tháng</b> · IAM + CISO — rà soát tài khoản đặc quyền, dịch vụ, quyền PII</li>
            <li><b>Hàng quý</b> · Line Manager + System Owner — rà soát toàn bộ quyền user &amp; vendor</li>
            <li><b>Hàng tháng + sau mỗi thay đổi role</b> · IAM + Auditor — kiểm tra xung đột SoD</li>
            <li><b>Hàng tháng</b> · SOC/Security — log cấp &amp; thu hồi quyền</li>
            <li><b>Hàng quý</b> · DPO + CISO — đánh giá ngoại lệ</li>
            <li><b>Hàng quý</b> · bên độc lập với Auditor — lấy mẫu các request Auditor đã cho qua, đối chiếu log để tránh che giấu lỗi</li>
          </ul>
        </details>
      </div>
    </>
  );
}
