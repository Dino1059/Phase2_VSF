import Link from "next/link";
import { requireUser } from "@/lib/auth/session";
import { ACTIVITIES, CONFLICT_PAIRS, LETTERS, ROLES, ROLE_KEYS, type Letter } from "@/lib/sod/catalog";
import { phaseSteps } from "@/lib/sod/chain";
import { Badge } from "@/app/ui/badges";

export const metadata = { title: "Ma trận SoD · SoD Flow" };

export default async function MatrixPage({ searchParams }: PageProps<"/ma-tran">) {
  await requireUser();
  const hd = Number((await searchParams).hd);
  const sel = ACTIVITIES.find((a) => a.id === hd);
  const ps = sel && phaseSteps(sel.id);
  const short = (r: keyof typeof ROLES) => ROLES[r].short;

  return (
    <>
      <h1>Ma trận SoD</h1>
      <p className="sub">Bấm vào một hoạt động để xem thứ tự xử lý được sinh ra.</p>
      <div className="legend" style={{ marginBottom: 12 }}>
        {(Object.entries(LETTERS) as [Letter, string][]).map(([k, v]) => (
          <span key={k}>
            <Badge l={k} /> {v}
          </span>
        ))}
      </div>
      <div className="card" style={{ padding: 8 }}>
        <div className="table-wrap">
          <table className="mx">
            <thead>
              <tr>
                <th>Hoạt động kiểm soát</th>
                {ROLE_KEYS.map((r) => (
                  <th key={r} title={ROLES[r].name}>{short(r)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ACTIVITIES.map((a) => (
                <tr key={a.id} className={a.id === sel?.id ? "sel" : undefined}>
                  <td>
                    <Link href={`/ma-tran?hd=${a.id}#chuoi`} scroll={false} style={{ color: "inherit", textDecoration: "none" }}>
                      {a.name}
                    </Link>
                  </td>
                  {[...a.m].map((l, i) => (
                    <td key={i}>
                      <Badge l={l as Letter} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {sel && ps && (
        <div id="chuoi" className="card" style={{ margin: "16px 0" }}>
          <h2>{sel.name}</h2>
          <p className="small muted" style={{ marginTop: -6 }}>
            {sel.kind === "approval" ? "Hoạt động phê duyệt: rà soát → phê duyệt → thực thi" : "Hoạt động thực hiện: thực hiện → rà soát → nghiệm thu"}
          </p>
          <div className="row">
            {ps.seq.length ? (
              ps.seq.map(([r, l], i) => (
                <span key={i} className="row">
                  {i > 0 && <span className="muted">→</span>}
                  <span className="chip">
                    <Badge l={l} /> {short(r)}
                  </span>
                </span>
              ))
            ) : (
              <span className="muted">Chỉ người khởi tạo thực hiện</span>
            )}
          </div>
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
          </ul>
        </details>
      </div>
    </>
  );
}
