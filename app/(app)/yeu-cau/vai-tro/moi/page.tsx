import { requireUser } from "@/lib/auth/session";
import { canSubmitTicket } from "@/lib/authz/policy";
import { rbacCandidates } from "@/lib/tickets/queries";
import RbacForm from "./rbac-form";

export const metadata = { title: "Phiếu cấp vai trò · SoD Flow" };

export default async function NewRbacPage() {
  const user = await requireUser();
  return (
    <>
      <h1>Phiếu cấp / thu hồi vai trò</h1>
      <p className="sub">
        Vai trò trong SoD Flow chỉ được ghi khi phiếu hoàn tất: Release Manager rà soát, System Owner và CISO phê duyệt, IAM thực hiện.
        Người được cấp không tham gia chuỗi duyệt.
      </p>
      {canSubmitTicket(user) ? <RbacForm people={await rbacCandidates()} /> : <div className="alert bad">Bạn chưa có vai trò Requestor nên chưa tạo được phiếu.</div>}
    </>
  );
}
