import { useEffect, useState } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
import { sodApi } from '@/src/services/api';
import {
  Settings,
  ShieldAlert,
  CheckCircle2,
  RotateCcw,
  UserCheck,
  History,
} from 'lucide-react';

interface ConfigVersion {
  id: string;
  seq: number;
  status: 'ACTIVE' | 'PROPOSED' | 'REJECTED' | 'SUPERSEDED';
  proposedBy: string;
  proposedRole: string;
  proposedAt: string;
  decidedBy?: string;
  decidedRole?: string;
  decidedAt?: string;
  note: string;
  changeSummary: string;
  config: any;
}

const INITIAL_CONFIG_VERSIONS: ConfigVersion[] = [
  {
    id: 'legacy-1',
    seq: 1,
    status: 'ACTIVE',
    proposedBy: 'Nguyễn Quốc Bảo',
    proposedRole: 'ADMIN',
    proposedAt: '2026-10-01 09:00',
    decidedBy: 'Hoàng Giang',
    decidedRole: 'CISO',
    decidedAt: '2026-10-01 10:30',
    note: 'Cấu hình ma trận SoD ban đầu theo chuẩn ITGC và RACIX 10 vai trò.',
    changeSummary: '19 hoạt động kiểm soát ban đầu, 10 cột vai trò.',
    config: {},
  },
  {
    id: 'legacy-2',
    seq: 2,
    status: 'PROPOSED',
    proposedBy: 'Nguyễn Quốc Bảo',
    proposedRole: 'ADMIN',
    proposedAt: '2026-10-15 11:20',
    note: 'Bổ sung bước rà soát bắt buộc của Kiểm toán viên (Auditor R) trước khi triển khai Production cho hoạt động #11.',
    changeSummary: 'Ô (11, AUD) chuyển từ I sang R (Rà soát trước khi thực thi).',
    config: {},
  },
];

export function SodConfigAdminView() {
  void INITIAL_CONFIG_VERSIONS;
  const user = useAuthStore((s) => s.user);
  const [versions, setVersions] = useState<ConfigVersion[]>([]);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const loadConfig = () => sodApi.getConfig().then((rows) => setVersions(rows.map((v: any) => ({
    id: String(v.id), seq: v.seq, status: v.status, proposedBy: v.proposer_name || v.proposed_by,
    proposedRole: 'ADMIN', proposedAt: String(v.proposed_at || v.created_at || ''),
    decidedBy: v.decider_name, decidedRole: v.decider_name ? 'CISO' : undefined,
    decidedAt: v.decided_at ? String(v.decided_at) : undefined, note: v.reason || '',
    changeSummary: v.change_summary || `Cấu hình SoD phiên bản ${v.seq}`,
    config: v.config,
  }))));
  useEffect(() => { loadConfig().catch((e) => setError(String(e))).finally(() => setLoading(false)); }, []);

  const isCiso = user?.role === 'CISO';
  const isAdmin = user?.role === 'ADMIN';

  const handleProposeConfig = async () => {
    const active = versions.find((v) => v.status === 'ACTIVE');
    if (!active) { setError('Không tìm thấy cấu hình ACTIVE để tạo phiên bản mới.'); return; }
    const reason = window.prompt('Nhập lý do đề xuất phiên bản cấu hình mới:')?.trim();
    if (!reason) return;
    try {
      await sodApi.proposeConfig(active.config, reason);
      await loadConfig();
      setActionNotice('Đã tạo đề xuất cấu hình mới và chuyển CISO phê duyệt.');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const handleCisoDecision = async (seq: number, outcome: 'ACTIVE' | 'REJECTED') => {
    const target = versions.find((v) => v.seq === seq);
    if (!target) return;
    try { await sodApi.decideConfig(target.id, outcome); await loadConfig(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return; }
    setVersions(
      versions.map((v) => {
        if (v.seq !== seq) {
          if (outcome === 'ACTIVE' && v.status === 'ACTIVE') return { ...v, status: 'SUPERSEDED' };
          return v;
        }
        return {
          ...v,
          status: outcome,
          decidedBy: user?.fullName || 'Hoàng Giang',
          decidedRole: 'CISO',
          decidedAt: new Date().toLocaleString(),
        };
      })
    );
    setActionNotice(
      outcome === 'ACTIVE'
        ? `CISO đã phê duyệt áp dụng phiên bản v${seq}! Ma trận mới có hiệu lực cho các phiếu tạo tiếp theo.`
        : `CISO đã từ chối phiên bản v${seq}.`
    );
    setTimeout(() => setActionNotice(null), 4000);
  };

  return (
    <div className="space-y-6">
      {loading && <div className="p-3 bg-slate-50 rounded-xl text-xs">Đang tải cấu hình SoD...</div>}
      {error && <div className="p-3 bg-rose-50 text-rose-700 rounded-xl text-xs">{error}</div>}
      {actionNotice && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-lg bg-teal-50 text-[#008b74] border border-teal-200 font-bold text-xs">
            <Settings size={14} />
          </span>
          <h2 className="text-base font-bold text-slate-900">Quản trị Cấu hình Phiên bản (2-Person Rule)</h2>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            Nguyên tắc Hai Người (Admin ≠ CISO)
          </span>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          Thay đổi ma trận SoD hoặc quy định SLA chỉ có hiệu lực khi tuân thủ cơ chế <strong>Maker-Checker</strong>: Quản trị viên (<code>ADMIN</code>) lập đề xuất, Giám đốc An toàn Thông tin (<code>CISO</code>) thẩm tra và duyệt kích hoạt.
        </p>
        {isAdmin && (
          <button type="button" onClick={handleProposeConfig}
            className="px-3.5 py-2 rounded-xl bg-slate-900 text-[#04D3D4] font-bold text-xs">
            Tạo đề xuất từ cấu hình ACTIVE
          </button>
        )}
      </div>

      {/* Two Person Rule Explanation Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-slate-900 text-white rounded-2xl border border-slate-800 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold text-[#04D3D4] uppercase tracking-wider">
            <UserCheck size={14} />
            <span>Vai trò 1: ADMIN (Maker / Người Đề xuất)</span>
          </div>
          <p className="text-xs text-slate-300">
            Được phép chỉnh sửa các ô trong ma trận, thay đổi thời gian cam kết SLA và nộp bản đề xuất có giải trình lý do. <strong>Không được phép tự duyệt đề xuất của mình</strong>.
          </p>
          <div className="text-[11px] text-slate-400 font-mono">Người đề xuất hiện tại: {isAdmin ? `${user?.fullName} (${user?.username})` : 'Đăng nhập vai trò ADMIN để đề xuất'}</div>
        </div>

        <div className="p-4 bg-teal-950 text-white rounded-2xl border border-teal-800 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold text-teal-300 uppercase tracking-wider">
            <ShieldAlert size={14} />
            <span>Vai trò 2: CISO (Checker / Người Phê duyệt)</span>
          </div>
          <p className="text-xs text-teal-100">
            Có thẩm quyền thẩm tra độ an toàn của cấu hình mới, so sánh diff với ma trận hiện tại và ký duyệt kích hoạt phiên bản. Quyết định sẽ được lưu vết kiểm toán vĩnh viễn.
          </p>
          <div className="text-[11px] text-teal-300 font-mono">Người duyệt hiện tại: {isCiso ? `${user?.fullName} (${user?.username})` : 'Đăng nhập vai trò CISO để duyệt'}</div>
        </div>
      </div>

      {/* Versions List */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
          <History size={14} className="text-teal-600" />
          <span>Lịch sử Phiên bản Cấu hình Ma trận SoD</span>
        </h3>

        {versions.map((v) => (
          <div
            key={v.seq}
            className={`bg-white rounded-2xl border p-5 space-y-3 shadow-xs ${
              v.status === 'ACTIVE'
                ? 'border-emerald-300 ring-2 ring-emerald-500/10'
                : v.status === 'PROPOSED'
                ? 'border-amber-300 ring-2 ring-amber-500/10'
                : 'border-slate-200'
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <span className="font-mono font-bold text-xs bg-slate-900 text-[#04D3D4] px-2 py-0.5 rounded-md">
                  Phiên bản v{v.seq}
                </span>
                <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${
                  v.status === 'ACTIVE'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : v.status === 'PROPOSED'
                    ? 'bg-amber-50 text-amber-700 border-amber-200 animate-pulse'
                    : 'bg-slate-100 text-slate-500 border-slate-200'
                }`}>
                  {v.status === 'ACTIVE' ? 'Đang hiệu lực' : v.status === 'PROPOSED' ? 'Chờ CISO duyệt' : 'Đã thay thế'}
                </span>
              </div>
              <div className="text-xs text-slate-400">
                Đề xuất bởi: <strong className="text-slate-700">{v.proposedBy}</strong> ({v.proposedRole}) lúc {v.proposedAt}
              </div>
            </div>

            <div className="space-y-1 text-xs">
              <div className="text-slate-500 font-medium">Nội dung thay đổi:</div>
              <p className="font-semibold text-slate-900">{v.changeSummary}</p>
              <p className="text-slate-600 italic">&ldquo;{v.note}&rdquo;</p>
            </div>

            {v.decidedBy && (
              <div className="text-xs text-slate-500 pt-2 border-t border-slate-100 flex items-center gap-2">
                <CheckCircle2 size={13} className="text-emerald-600" />
                <span>
                  Phê duyệt bởi: <strong className="text-slate-800">{v.decidedBy}</strong> ({v.decidedRole}) vào lúc {v.decidedAt}
                </span>
              </div>
            )}

            {/* CISO Approval Buttons for PROPOSED Version */}
            {v.status === 'PROPOSED' && (
              <div className="pt-2 border-t border-amber-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-amber-50/50 p-3 rounded-xl">
                <span className="text-xs text-amber-800 font-medium">
                  {isCiso
                    ? 'Bạn đang đăng nhập vai trò CISO: Hãy đưa ra quyết định cho đề xuất này.'
                    : 'Chỉ vai trò CISO mới có thẩm quyền phê duyệt đề xuất này.'}
                </span>
                {isCiso ? (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleCisoDecision(v.seq, 'ACTIVE')}
                      className="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <CheckCircle2 size={13} />
                      <span>CISO Phê duyệt</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCisoDecision(v.seq, 'REJECTED')}
                      className="px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <RotateCcw size={13} />
                      <span>Từ chối</span>
                    </button>
                  </div>
                ) : (
                  <span className="text-xs font-mono text-slate-500 bg-white px-2 py-1 rounded border border-slate-200">
                    Đăng nhập bằng CISO để duyệt
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
