import { dateVN } from "@/lib/format";
import { EVIDENCE_TYPE_LABEL, outcomeLabel, statusLabel, type Evidence, type EvidenceFilter } from "@/lib/tickets/evidence";

const when = (d: Date) => d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", dateStyle: "short", timeStyle: "short" });

/** Báo cáo bằng chứng dạng in được (dùng chung cho trang và bản in / PDF). */
export default function EvidenceReport({ ev, filter, by, at }: { ev: Evidence; filter: EvidenceFilter; by: string; at: string }) {
  return (
    <div className="phieu">
      <div className="ph-title">BÁO CÁO BẰNG CHỨNG PHÂN QUYỀN</div>
      <div className="ph-sub">
        Kỳ: {filter.from ? dateVN(filter.from) : "từ đầu"} – {filter.to ? dateVN(filter.to) : "nay"}
        {filter.type && ` · Loại: ${EVIDENCE_TYPE_LABEL[filter.type]}`}
        {filter.status && ` · Trạng thái: ${statusLabel(filter.status)}`}
      </div>
      <p style={{ margin: "0 0 8px" }}>
        {ev.tickets.length} phiếu, {ev.rows} quyết định. Xuất bởi {by} lúc {at}.
        {ev.truncated && " Kết quả bị cắt ở mức tối đa, hãy thu hẹp kỳ."}
      </p>
      {ev.tickets.map((t) => (
        <div key={t.id} className="avoid" style={{ margin: "10px 0" }}>
          <div className="ph-h" style={{ margin: "10px 0 4px" }}>
            {t.code} · {EVIDENCE_TYPE_LABEL[t.type as keyof typeof EVIDENCE_TYPE_LABEL] ?? t.type} · {statusLabel(t.status)}
          </div>
          <div style={{ fontSize: 12 }}>
            {t.title} · Người yêu cầu: {t.requester} · Tạo {when(t.createdAt)}
            {t.closedAt && ` · Đóng ${when(t.closedAt)}`} · Cấu hình v{t.configSeq}
            {t.exceptionId && ` · Ngoại lệ ${t.exceptionId}`}
          </div>
          <table className="ph-t grid" style={{ marginTop: 4 }}>
            <tbody>
              <tr className="hd"><th>Bước</th><th>Vai trò</th><th>Người thực hiện</th><th>Kết quả</th><th>Thời điểm</th><th>Nội dung (mã băm)</th></tr>
              {t.decisions.map((d, i) => (
                <tr key={i}>
                  <td className="c">{d.step}</td>
                  <td>{d.role}</td>
                  <td>{d.actor}{d.onBehalfOf && ` (thay mặt ${d.onBehalfOf})`}</td>
                  <td>{outcomeLabel(d.outcome)}{d.comment && <><br /><i>{d.comment}</i></>}</td>
                  <td className="c">{when(d.decidedAt)}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 10 }}>v{d.rev} · {d.formHash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {!ev.tickets.length && <p>Không có phiếu nào trong kỳ.</p>}
      <div className="ph-foot">Xuất từ SoD Flow · mỗi lần xuất được ghi vào nhật ký kiểm toán</div>
    </div>
  );
}
