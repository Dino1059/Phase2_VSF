// Nội dung phiếu in / PDF (chuyển từ phieuHTML() của bản mẫu).
import { type RoleKey, type StepAction } from "@/lib/sod/catalog";
import { CAM_KET, CAP_BAC, DLCN, LOAI_PHIEU, MUC_KHAN, emptyRow, rowFilled, type TicketForm } from "@/lib/sod/form";
import { dateVN, fmtDate } from "@/lib/format";

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
const Dots = ({ n = 1 }: { n?: number }) => <span className="dots">{"………".repeat(n)}</span>;
const Ngay = () => (
  <>
    <Dots /> / <Dots /> / 20<Dots />
  </>
);
const DAT = { y: "Đạt", n: "Không đạt" };

const CAP_DUYET: [string, string][] = [
  ["A", "PTGĐ Khối hoặc Giám đốc Điều hành thị trường (bên yêu cầu)"],
  ["B", "Giám đốc Khối / Bộ phận (bên yêu cầu)"],
  ["C", "PTGĐ Khối Kinh doanh & Vận hành GSM"],
  ["D", "Giám đốc Kiểm soát Dữ liệu"],
  ["Ý kiến chuyên môn", "DPO / Ban Pháp chế & Tuân thủ (bắt buộc khi liên quan DLCN nhạy cảm hoặc chuyển dữ liệu ra nước ngoài)"],
];
const THAM_DINH = [
  "Đúng phạm vi công việc, vai trò và phạm vi phụ trách",
  "Đúng tầng dữ liệu theo vai trò và cấp bậc",
  "Đủ cấp phê duyệt theo Phụ lục 01",
  "Không vi phạm nguyên tắc phân tách trách nhiệm (SoD)",
  "Không truy cập tầng dữ liệu thô hoặc phạm vi toàn cục trái nguyên tắc",
];

const Val = ({ v }: { v: string }) =>
  v.trim() ? <span style={{ whiteSpace: "pre-line" }}>{v}</span> : <span className="dots">…………………………</span>;

/** Phần D–H: do người phê duyệt / bộ phận khác điền. Dùng cho phiếu in và phần xem (chỉ đọc) ở trang tạo phiếu. */
export function PhanDenH({ form: d }: { form: TicketForm }) {
  const filled = d.rows.filter(rowFilled);
  const revokeRows = [...filled];
  while (revokeRows.length < 3) revokeRows.push(emptyRow());
  const bgScope = filled.map((r) => [r.heThong, r.taiNguyen, r.mucQuyen].filter(Boolean).join(" – ")).join("\n");
  return (
    <>
      <div className="ph-h avoid">PHẦN D. PHÊ DUYỆT</div>
      <p className="ph-note">
        Cấp phê duyệt áp dụng theo Phụ lục 01 của Quy trình. Trường hợp cấp A và cấp C trùng một người thì phê duyệt một lần.
      </p>
      <table className="ph-t grid">
        <colgroup>
          <col style={{ width: "9%" }} /><col style={{ width: "29%" }} /><col style={{ width: "17%" }} /><col style={{ width: "23%" }} /><col />
        </colgroup>
        <tbody>
          <tr className="hd"><th>Cấp</th><th>Chức danh</th><th>Họ và tên</th><th>Ý kiến (Đồng ý / Không đồng ý / Điều chỉnh)</th><th>Ký, ngày</th></tr>
          {CAP_DUYET.map(([cap, chucDanh]) => (
            <tr key={cap} className="tall"><td>{cap}</td><td>{chucDanh}</td><td /><td /><td /></tr>
          ))}
        </tbody>
      </table>

      <div className="ph-h avoid">PHẦN E. THẨM ĐỊNH VÀ THỰC THI (Bộ phận Kiểm soát Dữ liệu)</div>
      <table className="ph-t">
        <tbody>
          <tr className="hd"><th style={{ width: "53%" }}>Nội dung thẩm định</th><th>Kết quả</th></tr>
          {THAM_DINH.map((t) => (
            <tr key={t}><td>{t}</td><td><Opts map={DAT} cur="" /></td></tr>
          ))}
          <tr>
            <td>Kết luận</td>
            <td><span className="o"><Box on={false} /> Chấp thuận thực thi</span> <span className="o"><Box on={false} /> Từ chối – lý do:</span> <Dots n={3} /></td>
          </tr>
        </tbody>
      </table>
      <table className="ph-t kv" style={{ marginTop: 10 }}>
        <tbody>
          <tr><td>Ngày thực thi</td><td /></tr>
          <tr><td>Người thực thi</td><td /></tr>
          <tr><td>Ngày hiệu lực quyền</td><td>Từ <Ngay /> &nbsp;&nbsp; đến <Ngay /></td></tr>
          <tr><td>Ghi nhận sổ phân quyền</td><td><Box on={false} /> Đã ghi nhận &nbsp;&nbsp; Mã bản ghi: <Dots n={3} /></td></tr>
          <tr><td>Thông báo người yêu cầu</td><td><Box on={false} /> Đã thông báo ngày <Ngay /></td></tr>
          <tr>
            <td>Xác nhận của người yêu cầu</td>
            <td>
              <span className="o"><Box on={false} /> Đã đáp ứng</span> <span className="o"><Box on={false} /> Chưa đáp ứng (nêu chi tiết):</span>
              <br />
              <Dots n={3} /> (Quá 24 giờ không phản hồi được coi là đã chấp nhận và kết thúc quy trình)
            </td>
          </tr>
        </tbody>
      </table>

      {d.loaiPhieu === "revoke" && (
        <>
          <div className="ph-h avoid">PHẦN F. THU HỒI QUYỀN</div>
          <p className="ph-note">Áp dụng khi loại phiếu là Thu hồi hoặc khi thực hiện thu hồi theo kết quả rà soát.</p>
          <table className="ph-t kv">
            <tbody>
              <tr>
                <td>Nguồn kích hoạt thu hồi</td>
                <td>
                  <Box on={false} /> (a) Biến động nhân sự – nghỉ việc, điều chuyển <Box on={false} /> (b) Hết thời hạn quyền hoặc kết thúc dự án, mục đích{" "}
                  <Box on={false} /> (c) Không sử dụng (idle) theo ngưỡng quy định <Box on={false} /> (d) Theo kết quả UAR hoặc yêu cầu của CBLĐ / Data Owner / ANBM
                </td>
              </tr>
              <tr><td>Thời điểm phát sinh sự kiện</td><td><Ngay /> &nbsp; Giờ: <Dots /></td></tr>
              <tr><td>Thời hạn phải hoàn tất thu hồi</td><td>Theo SLA quy định tại mục IV.2.1 của Quy trình</td></tr>
              <tr>
                <td>Trường hợp rủi ro cao (khóa ngay)</td>
                <td><span className="o"><Box on={false} /> Có – lý do:</span> <Dots n={3} /> &nbsp; <span className="o"><Box on={false} /> Không</span></td>
              </tr>
            </tbody>
          </table>
          <table className="ph-t grid" style={{ marginTop: 10 }}>
            <tbody>
              <tr className="hd"><th style={{ width: "6%" }}>STT</th><th style={{ width: "22%" }}>Hệ thống</th><th>Tài nguyên / quyền thu hồi</th><th style={{ width: "16%" }}>Ngày thu hồi</th><th style={{ width: "16%" }}>Người thực hiện</th></tr>
              {revokeRows.map((r, i) => (
                <tr key={i}>
                  <td className="c">{i + 1}</td><td>{r.heThong}</td><td>{[r.taiNguyen, r.mucQuyen].filter(Boolean).join(" – ")}</td><td /><td />
                </tr>
              ))}
            </tbody>
          </table>
          <table className="ph-t kv" style={{ marginTop: 10 }}>
            <tbody>
              <tr>
                <td>Kết quả giải trình của người được cấp quyền (nếu có)</td>
                <td>
                  <Box on={false} /> Chấp nhận – giữ quyền, cập nhật thời hạn đến <Ngay /> <Box on={false} /> Không chấp nhận hoặc không giải trình đúng hạn – thực hiện thu hồi
                </td>
              </tr>
              <tr><td>Xác nhận hoàn tất thu hồi</td><td>Người thực hiện: <Dots n={3} /> &nbsp; Ngày: <Ngay /></td></tr>
            </tbody>
          </table>
        </>
      )}

      {d.loaiPhieu === "bg" && (
        <>
          <div className="ph-h avoid">PHẦN G. TRUY CẬP ĐẶC QUYỀN KHẨN CẤP (BREAK-GLASS)</div>
          <p className="ph-note">Chỉ áp dụng khi xử lý sự cố P1/P2 theo VSF_IT20 hoặc tác vụ bảo trì khẩn đã có kế hoạch được phê duyệt.</p>
          <table className="ph-t kv">
            <tbody>
              <tr>
                <td>Điều kiện kích hoạt</td>
                <td>
                  <span className="o"><Box on={false} /> Sự cố P1</span> <span className="o"><Box on={false} /> Sự cố P2</span>{" "}
                  <span className="o"><Box on={false} /> Bảo trì khẩn đã có kế hoạch phê duyệt</span>
                </td>
              </tr>
              <tr><td>Mã hồ sơ sự cố liên quan</td><td /></tr>
              <tr><td>Mô tả tình huống và lý do bắt buộc dùng quyền đặc quyền</td><td /></tr>
              <tr><td>Hệ thống và phạm vi truy cập</td><td style={{ whiteSpace: "pre-line" }}>{bgScope}</td></tr>
              <tr><td>Tài khoản đặc quyền sử dụng</td><td /></tr>
              <tr>
                <td>Thời gian phiên đề nghị</td>
                <td>Từ <Dots /> giờ <Dots /> ngày <Dots /> đến <Dots /> giờ <Dots /> ngày <Dots /> (Tối đa 08 giờ; gia hạn phải phê duyệt lại)</td>
              </tr>
            </tbody>
          </table>
          <table className="ph-t grid" style={{ marginTop: 10 }}>
            <tbody>
              <tr className="hd"><th style={{ width: "27%" }}>Phê duyệt</th><th style={{ width: "19%" }}>Họ và tên</th><th style={{ width: "20%" }}>Hình thức phê duyệt</th><th style={{ width: "15%" }}>Thời điểm</th><th>Ký xác nhận</th></tr>
              {["Giám đốc Kiểm soát Dữ liệu", "Đại diện ANBM / VinSOC"].map((r) => (
                <tr key={r} className="tall">
                  <td>{r}</td><td /><td><Box on={false} /> Văn bản <Box on={false} /> Kênh khẩn</td><td /><td />
                </tr>
              ))}
            </tbody>
          </table>
          <p className="ph-note after">
            Đối với sự cố P1, cho phép phê duyệt qua kênh khẩn (điện thoại hoặc tin nhắn) và xác nhận lại bằng văn bản; hồ sơ phải hoàn tất trong 24 giờ.
          </p>

          <div className="ph-h avoid">PHẦN H. HẬU KIỂM PHIÊN BREAK-GLASS</div>
          <table className="ph-t kv">
            <tbody>
              <tr><td>Thời điểm kết thúc phiên thực tế</td><td><Dots /> giờ <Dots /> ngày <Ngay /></td></tr>
              <tr>
                <td>Quyền đã tự thu hồi khi kết thúc phiên</td>
                <td><span className="o"><Box on={false} /> Có</span> <span className="o"><Box on={false} /> Không – nêu lý do:</span> <Dots n={3} /></td>
              </tr>
              <tr className="tall"><td>Tóm tắt thao tác đã thực hiện trong phiên</td><td /></tr>
              <tr>
                <td>Đối soát nhật ký phiên</td>
                <td>
                  Người đối soát (ANBM): <Dots n={3} /> &nbsp; Ngày: <Ngay />
                  <br />
                  Người đối soát (BP KSDL): <Dots n={3} /> &nbsp; Ngày: <Ngay />
                </td>
              </tr>
              <tr>
                <td>Kết quả hậu kiểm</td>
                <td><Box on={false} /> Phù hợp phạm vi phê duyệt <Box on={false} /> Phát hiện thao tác ngoài phạm vi – mô tả: <Dots n={3} /></td>
              </tr>
              <tr>
                <td>Hành động khắc phục (nếu có)</td>
                <td>Nội dung: <Dots n={3} /> &nbsp; Chủ trì: <Dots n={2} /> &nbsp; Thời hạn: <Dots n={2} /></td>
              </tr>
            </tbody>
          </table>
          <p className="ph-note after">
            Hậu kiểm phải hoàn tất trong 24 giờ kể từ khi kết thúc phiên. Kết quả được ghi nhận vào hồ sơ sự cố liên quan.
          </p>
        </>
      )}
    </>
  );
}

export default function Phieu({ form: d, code, createdAt, statusLabel, exception }: PhieuProps) {
  const filled = d.rows.filter(rowFilled);
  const rows = [...filled];
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

      <PhanDenH form={d} />

      <div className="ph-foot">
        {statusLabel ? `Trạng thái: ${statusLabel} · ` : "Bản nháp chưa gửi · "}Xuất từ SoD Flow
      </div>
    </div>
  );
}
