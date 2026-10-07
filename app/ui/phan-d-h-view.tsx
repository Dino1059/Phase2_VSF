// Phần D–H hiển thị trên trang tạo phiếu: cùng giao diện với Phần A–C, chỉ đọc.
// Bản in / PDF dùng PhanDenH trong phieu.tsx.
import type { ReactNode } from "react";
import { emptyRow, rowFilled, type TicketForm } from "@/lib/sod/form";

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

const Row = ({ label, children }: { label: ReactNode; children?: ReactNode }) => (
  <div className="frow">
    <div className="flabel">{label}</div>
    <div className="fval">{children ?? <span className="muted">—</span>}</div>
  </div>
);
/** Các lựa chọn bị khoá: người lập phiếu chỉ xem */
const Opts = ({ items }: { items: string[] }) => (
  <div className="opts">
    {items.map((l) => (
      <label key={l} className="opt" style={{ cursor: "default" }}>
        <input type="checkbox" disabled /> {l}
      </label>
    ))}
  </div>
);
const Blank = ({ text }: { text: string }) => <span className="muted">{text}</span>;

function Card({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      {note && <p className="small muted" style={{ marginTop: -4 }}>{note}</p>}
      {children}
    </div>
  );
}
const Grid = ({ head, rows }: { head: string[]; rows: ReactNode[][] }) => (
  <div className="table-wrap">
    <table className="rows">
      <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>{r.map((c, j) => <td key={j} style={{ height: 38 }}>{c}</td>)}</tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default function PhanDenHView({ form: d }: { form: TicketForm }) {
  const filled = d.rows.filter(rowFilled);
  const revokeRows = [...filled];
  while (revokeRows.length < 3) revokeRows.push(emptyRow());
  const scope = filled.map((r) => [r.heThong, r.taiNguyen, r.mucQuyen].filter(Boolean).join(" – ")).join("; ");

  return (
    <>
      <div className="alert info small" style={{ marginBottom: 0 }}>
        Phần D–H chỉ để xem, do người phê duyệt và Bộ phận Kiểm soát Dữ liệu hoàn thành. Người lập phiếu chỉ điền đến Phần C.
        {d.loaiPhieu !== "revoke" && d.loaiPhieu !== "bg" && " Phần F (Thu hồi) và G–H (Break-glass) hiện khi chọn loại phiếu tương ứng."}
      </div>

      <Card title="Phần D. Phê duyệt" note="Cấp phê duyệt áp dụng theo Phụ lục 01 của Quy trình. Trường hợp cấp A và cấp C trùng một người thì phê duyệt một lần.">
        <Grid
          head={["Cấp", "Chức danh", "Họ và tên", "Ý kiến (Đồng ý / Không đồng ý / Điều chỉnh)", "Ký, ngày"]}
          rows={CAP_DUYET.map(([cap, cd]) => [cap, cd, "", "", ""])}
        />
      </Card>

      <Card title="Phần E. Thẩm định và thực thi (Bộ phận Kiểm soát Dữ liệu)">
        <div className="ftable">
          {THAM_DINH.map((t) => <Row key={t} label={t}><Opts items={["Đạt", "Không đạt"]} /></Row>)}
          <Row label="Kết luận"><Opts items={["Chấp thuận thực thi", "Từ chối – lý do:"]} /></Row>
          <Row label="Ngày thực thi" />
          <Row label="Người thực thi" />
          <Row label="Ngày hiệu lực quyền"><Blank text="Từ ……… / ……… / 20……   đến ……… / ……… / 20………" /></Row>
          <Row label="Ghi nhận sổ phân quyền"><Opts items={["Đã ghi nhận"]} /><Blank text="Mã bản ghi: ………………" /></Row>
          <Row label="Thông báo người yêu cầu"><Opts items={["Đã thông báo ngày ……… / ……… / 20………"]} /></Row>
          <Row label="Xác nhận của người yêu cầu">
            <Opts items={["Đã đáp ứng", "Chưa đáp ứng (nêu chi tiết):"]} />
            <div className="small muted">Quá 24 giờ không phản hồi được coi là đã chấp nhận và kết thúc quy trình.</div>
          </Row>
        </div>
      </Card>

      {d.loaiPhieu === "revoke" && (
        <Card title="Phần F. Thu hồi quyền" note="Áp dụng khi loại phiếu là Thu hồi hoặc khi thực hiện thu hồi theo kết quả rà soát.">
          <div className="ftable" style={{ marginBottom: 12 }}>
            <Row label="Nguồn kích hoạt thu hồi">
              <Opts items={[
                "(a) Biến động nhân sự – nghỉ việc, điều chuyển",
                "(b) Hết thời hạn quyền hoặc kết thúc dự án, mục đích",
                "(c) Không sử dụng (idle) theo ngưỡng quy định",
                "(d) Theo kết quả UAR hoặc yêu cầu của CBLĐ / Data Owner / ANBM",
              ]} />
            </Row>
            <Row label="Thời điểm phát sinh sự kiện"><Blank text="……… / ……… / 20………   Giờ: …………" /></Row>
            <Row label="Thời hạn phải hoàn tất thu hồi">Theo SLA quy định tại mục IV.2.1 của Quy trình</Row>
            <Row label="Trường hợp rủi ro cao (khóa ngay)"><Opts items={["Có – lý do:", "Không"]} /></Row>
          </div>
          <Grid
            head={["STT", "Hệ thống", "Tài nguyên / quyền thu hồi", "Ngày thu hồi", "Người thực hiện"]}
            rows={revokeRows.map((r, i) => [i + 1, r.heThong, [r.taiNguyen, r.mucQuyen].filter(Boolean).join(" – "), "", ""])}
          />
          <div className="ftable" style={{ marginTop: 12 }}>
            <Row label="Kết quả giải trình của người được cấp quyền (nếu có)">
              <Opts items={["Chấp nhận – giữ quyền, cập nhật thời hạn đến ……… / ……… / 20………", "Không chấp nhận hoặc không giải trình đúng hạn – thực hiện thu hồi"]} />
            </Row>
            <Row label="Xác nhận hoàn tất thu hồi"><Blank text="Người thực hiện: ………………   Ngày: ……… / ……… / 20………" /></Row>
          </div>
        </Card>
      )}

      {d.loaiPhieu === "bg" && (
        <>
          <Card title="Phần G. Truy cập đặc quyền khẩn cấp (break-glass)" note="Chỉ áp dụng khi xử lý sự cố P1/P2 theo VSF_IT20 hoặc tác vụ bảo trì khẩn đã có kế hoạch được phê duyệt.">
            <div className="ftable" style={{ marginBottom: 12 }}>
              <Row label="Điều kiện kích hoạt"><Opts items={["Sự cố P1", "Sự cố P2", "Bảo trì khẩn đã có kế hoạch phê duyệt"]} /></Row>
              <Row label="Mã hồ sơ sự cố liên quan" />
              <Row label="Mô tả tình huống và lý do bắt buộc dùng quyền đặc quyền" />
              <Row label="Hệ thống và phạm vi truy cập">{scope || undefined}</Row>
              <Row label="Tài khoản đặc quyền sử dụng" />
              <Row label="Thời gian phiên đề nghị">
                <Blank text="Từ ……… giờ ……… ngày ……… đến ……… giờ ……… ngày ………" />
                <div className="small muted">Tối đa 08 giờ; gia hạn phải phê duyệt lại.</div>
              </Row>
            </div>
            <Grid
              head={["Phê duyệt", "Họ và tên", "Hình thức phê duyệt", "Thời điểm", "Ký xác nhận"]}
              rows={["Giám đốc Kiểm soát Dữ liệu", "Đại diện ANBM / VinSOC"].map((r) => [r, "", <Opts key={r} items={["Văn bản", "Kênh khẩn"]} />, "", ""])}
            />
            <p className="small muted" style={{ marginBottom: 0 }}>
              Đối với sự cố P1, cho phép phê duyệt qua kênh khẩn (điện thoại hoặc tin nhắn) và xác nhận lại bằng văn bản; hồ sơ phải hoàn tất trong 24 giờ.
            </p>
          </Card>

          <Card title="Phần H. Hậu kiểm phiên break-glass">
            <div className="ftable">
              <Row label="Thời điểm kết thúc phiên thực tế"><Blank text="……… giờ ……… ngày ……… / ……… / 20………" /></Row>
              <Row label="Quyền đã tự thu hồi khi kết thúc phiên"><Opts items={["Có", "Không – nêu lý do:"]} /></Row>
              <Row label="Tóm tắt thao tác đã thực hiện trong phiên" />
              <Row label="Đối soát nhật ký phiên">
                <Blank text="Người đối soát (ANBM): ………………   Ngày: ……… / ……… / 20………" />
                <br />
                <Blank text="Người đối soát (BP KSDL): ………………   Ngày: ……… / ……… / 20………" />
              </Row>
              <Row label="Kết quả hậu kiểm"><Opts items={["Phù hợp phạm vi phê duyệt", "Phát hiện thao tác ngoài phạm vi – mô tả:"]} /></Row>
              <Row label="Hành động khắc phục (nếu có)"><Blank text="Nội dung: ………………   Chủ trì: ………………   Thời hạn: ………………" /></Row>
            </div>
            <p className="small muted" style={{ marginBottom: 0 }}>
              Hậu kiểm phải hoàn tất trong 24 giờ kể từ khi kết thúc phiên. Kết quả được ghi nhận vào hồ sơ sự cố liên quan.
            </p>
          </Card>
        </>
      )}
    </>
  );
}
