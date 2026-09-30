// Nội dung phiếu in / PDF (chuyển từ phieuHTML() của bản mẫu).
import { ROLES, VERB, type RoleKey, type StepAction } from "@/lib/sod/catalog";
import { CAM_KET, CAP_BAC, DLCN, LOAI_PHIEU, MUC_KHAN, emptyRow, rowFilled, type TicketForm } from "@/lib/sod/form";
import { dateVN, fmtDate, fmtTime } from "@/lib/format";

type PhieuStep = {
  role: RoleKey;
  action: StepAction;
  actor?: string;
  result?: string;
  comment?: string | null;
  doneAt?: Date | null;
};
export type PhieuProps = {
  form: TicketForm;
  steps: PhieuStep[];
  code?: string;
  createdAt?: Date;
  statusLabel?: string;
  exception?: { id: string | null; conflicts: string[] };
};

const Box = ({ on }: { on: boolean }) => <span className="cb">{on ? "☑" : "☐"}</span>;
const Opts = ({ map, cur }: { map: Record<string, string>; cur: string }) => (
  <>
    {Object.entries(map).map(([k, l]) => (
      <span key={k} className="o">
        <Box on={cur === k} /> {l}{" "}
      </span>
    ))}
  </>
);
const Val = ({ v }: { v: string }) =>
  v.trim() ? <span style={{ whiteSpace: "pre-line" }}>{v}</span> : <span className="dots">…………………………</span>;

export default function Phieu({ form: d, steps, code, createdAt, statusLabel, exception }: PhieuProps) {
  const rows = d.rows.filter(rowFilled);
  while (rows.length < 4) rows.push(emptyRow());
  const date = fmtDate(createdAt);
  return (
    <div className="phieu">
      <div className="ph-title">
        PHIẾU CẤP / THU HỒI QUYỀN TRUY CẬP
        <br />
        VÀ TRUY CẬP ĐẶC QUYỀN KHẨN CẤP (BREAK-GLASS)
      </div>
      <div className="ph-sub">Ban hành kèm VSF_QT_Kiem soat truy cap phan quyen va SoD</div>
      <table className="ph-t kv">
        <tbody>
          <tr><th>Số phiếu</th><td>{code ? <b>{code}</b> : <span className="dots">……………………</span>} (do Bộ phận Kiểm soát Dữ liệu cấp)</td></tr>
          <tr><th>Ngày lập phiếu</th><td>{date}</td></tr>
          <tr><th>Loại phiếu</th><td><Opts map={LOAI_PHIEU} cur={d.loaiPhieu} /></td></tr>
          <tr><th>Mức độ khẩn</th><td><Opts map={MUC_KHAN} cur={d.khan} /></td></tr>
        </tbody>
      </table>

      <div className="ph-h avoid">PHẦN A. THÔNG TIN NGƯỜI SỬ DỤNG QUYỀN</div>
      <table className="ph-t kv">
        <tbody>
          <tr><th className="hd">Trường thông tin</th><th className="hd c">Nội dung khai báo</th></tr>
          <tr><td>Họ và tên</td><td><Val v={d.hoTen} /></td></tr>
          <tr><td>Mã nhân viên</td><td><Val v={d.maNV} /></td></tr>
          <tr><td>Email công vụ</td><td><Val v={d.email} /></td></tr>
          <tr><td>Khối / Phòng / Bộ phận</td><td><Val v={d.phongBan} /></td></tr>
          <tr>
            <td>Chức danh và cấp bậc</td>
            <td>
              Chức danh: <Val v={d.chucDanh} />
              <br />
              Cấp bậc: <Opts map={Object.fromEntries(CAP_BAC.map((c) => [c, c]))} cur={d.capBac} />
            </td>
          </tr>
          <tr><td>Vị trí công việc và phạm vi phụ trách</td><td><Val v={d.viTri} /></td></tr>
          <tr>
            <td>Thị trường cung cấp dịch vụ</td>
            <td>
              <span className="o"><Box on={d.thiTruong === "vn"} /> Việt Nam</span>{" "}
              <span className="o"><Box on={d.thiTruong === "intl"} /> Quốc tế (ghi rõ):</span>{" "}
              {d.thiTruong === "intl" && <Val v={d.thiTruongGhiRo} />}
            </td>
          </tr>
          <tr>
            <td>Người nhập phiếu (nếu khác người sử dụng quyền)</td>
            <td>
              {d.nhapThay ? (
                <>
                  Họ tên: <Val v={d.ntHoTen} /> &nbsp; Chức danh: <Val v={d.ntChucDanh} />
                  <br />
                  Văn bản/email phê duyệt của CBLĐ đơn vị cho phép nhập thay: <Val v={d.ntVanBan} />
                </>
              ) : (
                "Không (người sử dụng quyền tự nhập)"
              )}
            </td>
          </tr>
        </tbody>
      </table>

      <div className="ph-h avoid">PHẦN B. NỘI DUNG ĐỀ NGHỊ</div>
      <table className="ph-t grid">
        <tbody>
          <tr className="hd">
            <th>STT</th><th>Hệ thống (theo Phụ lục 01)</th><th>Tài nguyên cụ thể</th><th>Tầng dữ liệu (1/2/3)</th><th>Mức quyền (RO/RW/Full)</th><th>Thời hạn đề nghị</th>
          </tr>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="c">{i + 1}</td><td>{r.heThong}</td><td>{r.taiNguyen}</td><td className="c">{r.tang}</td><td className="c">{r.mucQuyen}</td><td className="c">{dateVN(r.thoiHan)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <table className="ph-t kv" style={{ marginTop: 10 }}>
        <tbody>
          <tr><td>Mục đích sử dụng (gắn với nhiệm vụ hoặc dự án cụ thể)</td><td><Val v={d.mucDich} /></td></tr>
          <tr>
            <td>Có liên quan dữ liệu cá nhân không?</td>
            <td>
              <Opts map={DLCN} cur={d.dlcn} />
              <br />
              <i>(Trường hợp DLCN nhạy cảm: bắt buộc nêu lý do nghiệp vụ và có ý kiến DPO/Ban Pháp chế &amp; Tuân thủ)</i>
            </td>
          </tr>
          <tr><td>Lý do nghiệp vụ đối với DLCN nhạy cảm hoặc yêu cầu gấp</td><td>{d.lyDo.trim() ? <Val v={d.lyDo} /> : "—"}</td></tr>
        </tbody>
      </table>

      {d.exception && (
        <>
          <div className="ph-h avoid">NGOẠI LỆ SoD</div>
          <table className="ph-t kv">
            <tbody>
              <tr><td>Mã ngoại lệ</td><td>{exception?.id ?? "(cấp khi gửi)"}</td></tr>
              <tr><td>Xung đột phát hiện</td><td>{exception?.conflicts.join("; ") || "—"}</td></tr>
              <tr><td>Lý do nghiệp vụ</td><td><Val v={d.exReason} /></td></tr>
              <tr><td>Thời hạn hiệu lực</td><td>{d.exFrom.replace("T", " ")} đến {d.exTo.replace("T", " ")}</td></tr>
              <tr><td>Biện pháp kiểm soát bù trừ</td><td><Val v={d.exControls} /></td></tr>
            </tbody>
          </table>
        </>
      )}

      <div className="ph-h avoid">PHẦN C. CAM KẾT CỦA NGƯỜI SỬ DỤNG QUYỀN</div>
      <ul className="ph-ul">
        {CAM_KET.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <p style={{ margin: "6px 0" }}>
        <Box on={d.camKet} /> Tôi đã đọc và cam kết thực hiện các nội dung trên.
      </p>
      <table className="ph-t kv avoid">
        <tbody>
          <tr>
            <td style={{ width: "50%", verticalAlign: "top" }}>
              Người sử dụng quyền (Ký, ghi rõ họ tên)
              {/* eslint-disable-next-line @next/next/no-img-element -- chữ ký là data URL */}
              <div className="sign">{d.signature && <img src={d.signature} alt="Chữ ký" />}</div>
              <b><Val v={d.kyTen} /></b>
            </td>
            <td style={{ verticalAlign: "top" }}>Ngày {date}</td>
          </tr>
        </tbody>
      </table>

      <div className="ph-h avoid">
        PHẦN D. XÁC NHẬN / PHÊ DUYỆT THEO LUỒNG SoD <span className="note">(hệ thống ghi nhận)</span>
      </div>
      <table className="ph-t grid">
        <tbody>
          <tr className="hd"><th>STT</th><th>Vai trò</th><th>Nội dung</th><th>Người thực hiện</th><th>Kết quả</th><th>Thời gian</th></tr>
          {steps.map((s, i) => (
            <tr key={i}>
              <td className="c">{i + 1}</td>
              <td>{i === 0 ? "Người nhập phiếu" : ROLES[s.role].name}</td>
              <td>{i === 0 ? "Khởi tạo phiếu" : VERB[s.action]}</td>
              <td>{s.actor}</td>
              <td>
                {s.result}
                {s.comment && <><br /><i>{s.comment}</i></>}
              </td>
              <td className="c">{s.doneAt ? fmtTime(s.doneAt) : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ph-foot">
        {statusLabel ? `Trạng thái: ${statusLabel} · ` : "Bản nháp chưa gửi · "}Xuất từ SoD Flow
      </div>
    </div>
  );
}
