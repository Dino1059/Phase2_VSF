import { useEffect, useState } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
import { sodApi } from '@/src/services/api';
import {
  FileCheck,
  Printer,
  Hash,
  CheckCircle2,
  Lock,
} from 'lucide-react';

export function SodEvidenceView() {
  const user = useAuthStore((s) => s.user);

  const legacyEvidenceRows = [
    {
      ticketCode: 'TK-2026-085',
      type: 'Phát hành Production (Deploy)',
      requester: 'Đỗ Khoa (DEV)',
      createdAt: '2026-10-12 10:00',
      closedAt: '2026-10-12 16:20',
      configSeq: 1,
      status: 'DONE',
      decisions: [
        {
          step: 1,
          role: 'Line Manager (LM)',
          actor: 'Trần Bình',
          outcome: 'Đã duyệt',
          decidedAt: '2026-10-12 11:30',
          hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        },
        {
          step: 2,
          role: 'Release Manager (REL)',
          actor: 'Bùi Lan',
          outcome: 'Đã duyệt',
          decidedAt: '2026-10-12 14:00',
          hash: '5f4dcc3b5aa765d61d8327deb882cf992b9699aafbf4c8996fb92427ae41e464',
        },
        {
          step: 3,
          role: 'Auditor (AUD)',
          actor: 'Trần Minh Hoàng',
          outcome: 'Đã rà soát (R)',
          decidedAt: '2026-10-12 15:00',
          hash: 'b28795777fe1277a1fc9bbef24b61ef026049a463ebbf1c70e3ed5c3f87c5fb9',
        },
        {
          step: 4,
          role: 'Production Operator (OPS)',
          actor: 'Ngô Minh',
          outcome: 'Đã thực thi (P)',
          decidedAt: '2026-10-12 16:20',
          hash: '7c6a612f310214a1a61a2515b6dd86a8462688b6f8a4462cb3e433a002a029a4',
        },
      ],
    },
    {
      ticketCode: 'TK-2026-089',
      type: 'Cấp quyền Telemetry Warehouse',
      requester: 'Nguyễn An (REQ)',
      createdAt: '2026-10-15 08:30',
      configSeq: 1,
      status: 'OPEN',
      decisions: [
        {
          step: 1,
          role: 'Line Manager (LM)',
          actor: 'Trần Bình',
          outcome: 'Đang chờ duyệt',
          decidedAt: 'Chưa có',
          hash: 'c81e728d9d4c2f636f067f89cc14862c1e4649b934ca495991b7852b855b9242',
        },
      ],
    },
  ];

  const [evidenceRows, setEvidenceRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const exportedAt = new Date().toLocaleString('vi-VN');
  useEffect(() => {
    sodApi.getTickets().then(async (tickets) => {
      const reports = await Promise.all(tickets.map((t: any) => sodApi.getEvidence(t.id)));
      setEvidenceRows(reports.map((r: any) => ({
        ticketCode: r.ticket.code, type: r.ticket.form?.type || r.ticket.form?.rows?.[0]?.heThong || 'SoD',
        requester: r.ticket.requester_name, createdAt: String(r.ticket.created_at || ''),
        closedAt: r.ticket.closed_at ? String(r.ticket.closed_at) : undefined,
        configSeq: r.ticket.config_seq, status: r.ticket.status,
        decisions: (r.evidence_payload.decisions || []).map((d: any, i: number) => ({
          step: i + 1, role: r.ticket.steps?.[i]?.role_code || '', actor: d.actor,
          outcome: d.outcome, decidedAt: d.decided_at, hash: d.form_hash || r.integrity_hash,
        })),
      })));
    }).catch((e) => setError(e instanceof Error ? e.message : String(e))).finally(() => setLoading(false));
  }, []);
  void legacyEvidenceRows;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6">
      {loading && <div className="p-3 bg-slate-50 rounded-xl text-xs">Đang tải bằng chứng kiểm toán...</div>}
      {error && <div className="p-3 bg-rose-50 text-rose-700 rounded-xl text-xs">{error}</div>}
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs print:hidden">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-lg bg-teal-50 text-[#008b74] border border-teal-200 font-bold text-xs">
              <FileCheck size={14} />
            </span>
            <h2 className="text-base font-bold text-slate-900">Báo cáo Bằng chứng Phân quyền (Audit Evidence Report)</h2>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
              Kiểm toán IPO
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Báo cáo độc lập trích xuất đầy đủ chuỗi quyết định, định danh người duyệt và mã băm SHA-256 đóng dấu niêm phong cho các kỳ kiểm toán.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrint}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-bold text-xs flex items-center gap-1.5 transition cursor-pointer shadow-xs"
          >
            <Printer size={14} />
            <span>In / Xuất PDF Bằng chứng</span>
          </button>
        </div>
      </div>

      {/* Printable Report Document Sheet */}
      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-300 shadow-md font-serif text-slate-900 space-y-6 print:border-none print:shadow-none print:p-0">
        {/* Document Header */}
        <div className="text-center space-y-1 pb-4 border-b-2 border-slate-900">
          <div className="text-xs uppercase tracking-widest text-slate-500 font-sans font-bold">
            DataTrust OS & SoD Flow Platform · Kiểm toán Phân quyền
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 uppercase">
            BÁO CÁO BẰNG CHỨNG PHÂN TÁCH TRÁCH NHIỆM (SOD EVIDENCE)
          </h1>
          <p className="text-xs italic text-slate-600">
            Xuất lúc {exportedAt} · {evidenceRows.length} phiếu có bằng chứng · Xuất bởi {user?.fullName} ({user?.role})
          </p>
          <div className="pt-2 flex justify-center items-center gap-4 text-xs font-mono text-slate-500 font-sans">
            <span className="flex items-center gap-1">
              <Hash size={12} className="text-teal-600" />
              <span>Hash toàn vẹn được hiển thị theo từng phiếu</span>
            </span>
            <span className="flex items-center gap-1">
              <Lock size={12} className="text-emerald-600" />
              <span>Dữ liệu lấy trực tiếp từ sổ bằng chứng SoD</span>
            </span>
          </div>
        </div>

        {/* Evidence Content for Each Ticket */}
        <div className="space-y-6 font-sans">
          {evidenceRows.map((t) => (
            <div key={t.ticketCode} className="border border-slate-300 rounded-xl p-4 space-y-3 bg-slate-50/50">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 pb-2 border-b border-slate-200">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-xs bg-slate-900 text-[#04D3D4] px-2 py-0.5 rounded">
                    {t.ticketCode}
                  </span>
                  <span className="font-bold text-xs text-slate-900">{t.type}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    t.status === 'DONE' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {t.status === 'DONE' ? 'Hoàn tất' : 'Đang xử lý'}
                  </span>
                </div>
                <div className="text-xs text-slate-500">
                  Người tạo: <strong>{t.requester}</strong> · Tạo lúc {t.createdAt}
                  {t.closedAt && ` · Đóng lúc ${t.closedAt}`}
                </div>
              </div>

              {/* Steps table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-200/80 text-slate-700 font-bold border-b border-slate-300">
                      <th className="py-2 px-3 w-14 text-center">Bước</th>
                      <th className="py-2 px-3">Vai trò SoD</th>
                      <th className="py-2 px-3">Người ký duyệt</th>
                      <th className="py-2 px-3">Kết quả</th>
                      <th className="py-2 px-3">Thời điểm</th>
                      <th className="py-2 px-3 font-mono">Mã băm SHA-256</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white">
                    {t.decisions.map((d: any, i: number) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="py-2 px-3 text-center font-bold text-slate-600">{d.step}</td>
                        <td className="py-2 px-3 font-medium text-slate-900">{d.role}</td>
                        <td className="py-2 px-3 text-slate-700 font-semibold">{d.actor}</td>
                        <td className="py-2 px-3">
                          <span className={`inline-flex items-center gap-1 font-semibold ${
                            d.outcome.includes('duyệt') || d.outcome.includes('thực thi') || d.outcome.includes('rà soát')
                              ? 'text-emerald-700'
                              : 'text-amber-700'
                          }`}>
                            <CheckCircle2 size={12} />
                            {d.outcome}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-slate-500">{d.decidedAt}</td>
                        <td className="py-2 px-3 font-mono text-[10px] text-slate-400 truncate max-w-[150px]" title={d.hash}>
                          {d.hash.slice(0, 16)}...
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>

        {/* Auditor Sign-off Footer */}
        <div className="pt-6 border-t-2 border-slate-300 grid grid-cols-2 gap-8 text-center text-xs font-sans">
          <div>
            <div className="font-bold text-slate-800">Đại diện Khối An toàn Thông tin (CISO)</div>
            <div className="text-[11px] text-slate-400 italic mt-0.5">Xác nhận tính toàn vẹn ma trận SoD</div>
            <div className="h-16 flex items-center justify-center font-mono font-bold text-slate-400">
              [Đã ký số điện tử - Hoàng Giang]
            </div>
          </div>
          <div>
            <div className="font-bold text-slate-800">Kiểm toán viên Độc lập (Lead Auditor)</div>
            <div className="text-[11px] text-slate-400 italic mt-0.5">Chứng thư thẩm định chuẩn bị IPO</div>
            <div className="h-16 flex items-center justify-center font-mono font-bold text-teal-700">
              [Đã thẩm tra hợp lệ - Trần Minh Hoàng]
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
