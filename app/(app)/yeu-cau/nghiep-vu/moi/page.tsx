import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth/session";
import { canSubmitTicket } from "@/lib/authz/policy";
import { OPS_TYPE_HINT, OPS_TYPE_LABEL, isOpsFormType } from "@/lib/sod/ops";
import OpsFormView from "./ops-form";

export const metadata = { title: "Tạo phiếu nghiệp vụ · SoD Flow" };

export default async function NewOpsPage({ searchParams }: PageProps<"/yeu-cau/nghiep-vu/moi">) {
  const user = await requireUser();
  const loai = (await searchParams).loai;
  if (typeof loai !== "string" || !isOpsFormType(loai)) redirect("/yeu-cau/moi");
  return (
    <>
      <h1>{OPS_TYPE_LABEL[loai]}</h1>
      <p className="sub">{OPS_TYPE_HINT[loai]}</p>
      <p className="small muted" style={{ marginTop: -6 }}><Link href="/yeu-cau/moi">← Chọn loại khác</Link></p>
      {canSubmitTicket(user) ? <OpsFormView type={loai} /> : <div className="alert bad">Bạn chưa có vai trò Requestor nên chưa tạo được phiếu.</div>}
    </>
  );
}
