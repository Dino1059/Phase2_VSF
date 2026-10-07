import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth/session";
import { delegationOverview } from "@/lib/delegations/queries";
import { DELEGABLE_ROLES } from "@/lib/delegations/service";
import { activeConfig } from "@/lib/config/queries";
import { fmtDate } from "@/lib/format";
import { revokeDelegationAction } from "@/app/actions/delegations";
import DelegationForm from "./delegation-form";

export const metadata = { title: "Ủy quyền · SoD Flow" };

export default async function DelegationPage() {
  const user = await requireUser();
  const mine = user.roles.filter((r) => (DELEGABLE_ROLES as readonly string[]).includes(r.code));
  if (!mine.length) redirect("/");
  const { given, received, byRole, live } = await delegationOverview(user.id, mine.map((r) => r.code));
  const maxDays = (await activeConfig()).config.delegationMaxDays;
  const status = (d: Parameters<typeof live>[0]) =>
    d.revokedAt ? "Đã thu hồi" : d.validTo <= new Date() ? "Hết hạn" : d.validFrom > new Date() ? "Chưa tới hạn" : "Đang hiệu lực";

  return (
    <>
      <h1>Ủy quyền vắng mặt</h1>
      <p className="sub">
        Giao việc của bạn cho người cùng vai trò trong lúc vắng mặt, tối đa {maxDays} ngày. Người nhận xử lý thay và mọi quyết định
        ghi “thay mặt bạn”. Hệ thống từ chối nếu người nhận gây xung đột SoD trên phiếu đang mở.
      </p>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Tạo ủy quyền</h2>
        <DelegationForm roles={mine.map((r) => ({ code: r.code, name: r.name }))} candidates={byRole} />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Tôi đã ủy quyền</h2>
        {given.length === 0 ? (
          <p className="muted">Chưa có ủy quyền nào.</p>
        ) : (
          <div className="table-wrap">
            <table className="log-table">
              <thead>
                <tr><th>Vai trò</th><th>Người nhận</th><th>Từ</th><th>Đến</th><th>Lý do</th><th>Trạng thái</th><th /></tr>
              </thead>
              <tbody>
                {given.map((d) => (
                  <tr key={d.id}>
                    <td>{d.role.name}</td>
                    <td>{d.delegate.fullName}</td>
                    <td>{fmtDate(d.validFrom)}</td>
                    <td>{fmtDate(new Date(d.validTo.getTime() - 1))}</td>
                    <td>{d.reason}</td>
                    <td>{status(d)}</td>
                    <td>
                      {live(d) && (
                        <form action={revokeDelegationAction}>
                          <input type="hidden" name="id" value={d.id} />
                          <button className="btn sm">Thu hồi</button>
                        </form>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Tôi được ủy quyền</h2>
        {received.length === 0 ? (
          <p className="muted">Chưa ai ủy quyền cho bạn.</p>
        ) : (
          <div className="table-wrap">
            <table className="log-table">
              <thead>
                <tr><th>Vai trò</th><th>Người ủy quyền</th><th>Từ</th><th>Đến</th><th>Trạng thái</th></tr>
              </thead>
              <tbody>
                {received.map((d) => (
                  <tr key={d.id}>
                    <td>{d.role.name}</td>
                    <td>{d.delegator.fullName}</td>
                    <td>{fmtDate(d.validFrom)}</td>
                    <td>{fmtDate(new Date(d.validTo.getTime() - 1))}</td>
                    <td>{status(d)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
