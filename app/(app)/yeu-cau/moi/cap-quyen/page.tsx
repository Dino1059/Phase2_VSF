import { requireUser } from "@/lib/auth/session";
import { canSubmitTicket } from "@/lib/authz/policy";
import Link from "next/link";
import CreateForm from "./create-form";

export const metadata = { title: "Tạo phiếu · SoD Flow" };

export default async function NewTicketPage() {
  const user = await requireUser();
  return (
    <>
      <h1>Phiếu cấp / thu hồi quyền truy cập</h1>
      <p className="sub">
        Và truy cập đặc quyền khẩn cấp (break-glass). Chuỗi phê duyệt tự dựng ở bên phải; người xử lý do hệ thống tự gán.
      </p>
      <p className="small muted" style={{ marginTop: -6 }}>
        Cần cấp hoặc thu hồi <b>vai trò trong SoD Flow</b> cho một người? Dùng <Link href="/yeu-cau/vai-tro/moi">phiếu cấp vai trò</Link>.
      </p>
      {canSubmitTicket(user) ? (
        <CreateForm fullName={user.fullName} email={user.email} />
      ) : (
        <div className="alert bad">Bạn chưa có vai trò Requestor nên chưa tạo được phiếu.</div>
      )}
    </>
  );
}
