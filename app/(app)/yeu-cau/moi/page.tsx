import Link from "next/link";
import { requireUser } from "@/lib/auth/session";
import { canSubmitTicket } from "@/lib/authz/policy";
import { activeConfig } from "@/lib/config/queries";
import { ACTIVITIES, ROLES, ticketType } from "@/lib/sod/catalog";
import { OPS_FORM_TYPES, OPS_TYPE_HINT, OPS_TYPE_LABEL } from "@/lib/sod/ops";
import { phaseSteps } from "@/lib/sod/chain";

export const metadata = { title: "Tạo phiếu · SoD Flow" };

const card = { textDecoration: "none", color: "inherit", display: "block" } as const;

export default async function NewTicketPage() {
  const user = await requireUser();
  if (!canSubmitTicket(user)) return <div className="alert bad">Bạn chưa có vai trò Requestor nên chưa tạo được phiếu.</div>;
  const { config } = await activeConfig();
  // Chuỗi duyệt mẫu theo ma trận đang hiệu lực: chỉ để người dùng biết phiếu sẽ đi qua những ai
  const chain = (acts: readonly number[]) =>
    acts.flatMap((a) => phaseSteps(a, {}, config.matrix).seq.map(([r, l]) => `${ROLES[r].short} ${l}`)).join(" → ") || "Chỉ người lập phiếu thực hiện";
  return (
    <>
      <h1>Bạn cần làm gì?</h1>
      <p className="sub">Mỗi loại yêu cầu đi qua một chuỗi hoạt động kiểm soát trong ma trận. Người xử lý do hệ thống tự gán, không ai tự duyệt phiếu của mình.</p>
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
        <Link href="/yeu-cau/moi/cap-quyen" className="card" style={card}>
          <h3 style={{ marginTop: 0 }}>Cấp / thu hồi quyền truy cập</h3>
          <p className="small muted">Cấp mới, điều chỉnh, gia hạn, thu hồi, break-glass.</p>
          <p className="small">{chain(ticketType("access").acts)}</p>
        </Link>
        {OPS_FORM_TYPES.map((t) => (
          <Link key={t} href={`/yeu-cau/nghiep-vu/moi?loai=${t}`} className="card" style={card}>
            <h3 style={{ marginTop: 0 }}>{OPS_TYPE_LABEL[t]}</h3>
            <p className="small muted">{OPS_TYPE_HINT[t]}</p>
            <p className="small">{chain(ticketType(t).acts)}</p>
            <p className="small muted" style={{ marginBottom: 0 }}>{ticketType(t).acts.map((a) => ACTIVITIES[a].name).join(" · ")}</p>
          </Link>
        ))}
        <Link href="/yeu-cau/vai-tro/moi" className="card" style={card}>
          <h3 style={{ marginTop: 0 }}>Cấp / thu hồi vai trò SoD Flow</h3>
          <p className="small muted">Vai trò trong hệ thống này, chỉ ghi khi phiếu hoàn tất.</p>
          <p className="small">{chain(ticketType("rbac").acts)}</p>
        </Link>
      </div>
    </>
  );
}
