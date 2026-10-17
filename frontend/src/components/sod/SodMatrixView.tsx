import { useEffect, useState, Fragment } from 'react';
import { sodApi } from '@/src/services/api';
import {
  ACTIVITIES,
  DEFAULT_MATRIX,
  LETTERS,
  ROLES,
  ROLE_KEYS,
  type Letter,
  type RoleKey,
  type StepAction,
} from '@/src/lib/sod/catalog';
import { phaseSteps } from '@/src/lib/sod/chain';
import { Shield, ChevronRight } from 'lucide-react';

export function SodMatrixView() {
  const [selectedActivityId, setSelectedActivityId] = useState<number>(0);
  const [matrix, setMatrix] = useState<readonly string[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    sodApi.getMatrix().then((data) => setMatrix(data.matrix || []))
      .catch((e) => setError(e instanceof Error ? e.message : 'Không thể tải ma trận SoD'))
      .finally(() => setLoading(false));
  }, []);
  const selectedActivity = ACTIVITIES.find((a) => a.id === selectedActivityId) || ACTIVITIES[0];
  const activeMatrix = matrix.length === ACTIVITIES.length ? matrix : (import.meta.env.DEV ? DEFAULT_MATRIX : []);
  const steps: ReturnType<typeof phaseSteps> = activeMatrix.length
    ? phaseSteps(selectedActivity.id, {}, activeMatrix)
    : { seq: [], C: [], I: [] };

  const getLetterBadge = (l: Letter | string) => {
    const letter = l as Letter;
    const badgeClass =
      {
        P: 'bg-blue-100 text-blue-700 border-blue-300 font-bold',
        A: 'bg-emerald-100 text-emerald-800 border-emerald-300 font-bold',
        R: 'bg-amber-100 text-amber-800 border-amber-300 font-bold',
        C: 'bg-purple-100 text-purple-700 border-purple-300 font-medium',
        I: 'bg-slate-100 text-slate-600 border-slate-300 font-medium',
        X: 'bg-rose-100 text-rose-700 border-rose-300 font-bold',
      }[letter] || 'bg-slate-100 text-slate-600';

    return (
      <span
        title={LETTERS[letter] || letter}
        className={`inline-grid place-items-center size-6 rounded-md border text-[11px] font-mono select-none ${badgeClass}`}
      >
        {letter}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {loading && <div className="p-3 rounded-xl bg-slate-50 text-xs text-slate-500">Đang tải ma trận SoD...</div>}
      {error && <div className="p-3 rounded-xl bg-rose-50 text-xs text-rose-700">{error}</div>}
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 sm:p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-lg bg-teal-50 text-[#008b74] border border-teal-200 font-bold text-xs">
              <Shield size={14} />
            </span>
            <h2 className="text-base font-bold text-slate-900">Ma trận Phân tách Trách nhiệm (SoD RACIX Matrix)</h2>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
              19 Hoạt động Kiểm soát
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Quy tắc kiểm soát phân quyền chuẩn hóa 10 vai trò trên 19 hoạt động nghiệp vụ và CNTT. Bấm vào một hoạt động để xem chuỗi phê duyệt được sinh tự động.
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-2 text-xs bg-slate-50 p-2.5 rounded-xl border border-slate-200">
          {(Object.entries(LETTERS) as [Letter, string][]).map(([k, desc]) => (
            <div key={k} className="flex items-center gap-1.5" title={desc}>
              {getLetterBadge(k)}
              <span className="text-[11px] font-semibold text-slate-700">{k}: {k === 'P' ? 'Thực thi' : k === 'A' ? 'Phê duyệt' : k === 'R' ? 'Rà soát' : k === 'C' ? 'Tham vấn' : k === 'I' ? 'Thông báo' : 'Cấm'}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Dynamic Inspector for Selected Activity */}
      {selectedActivity && (
        <div className="bg-gradient-to-r from-teal-50/70 via-white to-slate-50 p-4 sm:p-5 rounded-2xl border border-teal-200/80 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-teal-900 text-[#04D3D4]">
                #{selectedActivity.id + 1}
              </span>
              <h3 className="font-bold text-slate-900 text-sm">{selectedActivity.name}</h3>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase border ${
                selectedActivity.kind === 'approval'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-blue-50 text-blue-700 border-blue-200'
              }`}>
                {selectedActivity.kind === 'approval' ? 'Duyệt trước (R → A → P)' : 'Thực thi trước (P → R → A)'}
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Chuỗi phê duyệt tuần tự sinh ra (Sequential Execution Chain):
            </div>
            {steps.seq.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                {steps.seq.map(([role, action]: [RoleKey, StepAction], idx: number) => (
                  <Fragment key={idx}>
                    {idx > 0 && <ChevronRight size={14} className="text-slate-400 shrink-0" />}
                    <div className="flex items-center gap-1.5 bg-white border border-slate-200 shadow-2xs px-2.5 py-1.5 rounded-xl">
                      {getLetterBadge(action)}
                      <div className="flex flex-col text-left leading-tight">
                        <span className="font-bold text-xs text-slate-800">{ROLES[role].name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">({role})</span>
                      </div>
                    </div>
                  </Fragment>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic">Chỉ người khởi tạo thực hiện (không qua chuỗi phê duyệt).</div>
            )}
          </div>

          {(steps.C.length > 0 || steps.I.length > 0) && (
            <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-slate-600 border-t border-teal-100">
              {steps.C.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-purple-700">Được tham vấn (C):</span>
                  <span>{steps.C.map((r: RoleKey) => ROLES[r].name).join(', ')}</span>
                </div>
              )}
              {steps.I.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-600">Được thông báo (I):</span>
                  <span>{steps.I.map((r: RoleKey) => ROLES[r].name).join(', ')}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Matrix Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50/90 border-b border-slate-200">
                <th className="py-3 px-3 text-center text-slate-400 font-mono font-semibold w-12">#</th>
                <th className="py-3 px-4 font-bold text-slate-700 min-w-[280px]">Hoạt động Kiểm soát</th>
                <th className="py-3 px-2 text-center text-slate-500 font-semibold w-24">Loại quy trình</th>
                {ROLE_KEYS.map((r: RoleKey) => (
                  <th key={r} className="py-3 px-2 text-center font-bold text-slate-800 w-16" title={ROLES[r].name}>
                    <div className="flex flex-col items-center">
                      <span className="text-xs font-mono">{r}</span>
                      <span className="text-[10px] font-normal text-slate-400 truncate max-w-[60px]">{ROLES[r].short}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {ACTIVITIES.map((act) => {
                const isSelected = act.id === selectedActivityId;
                const matrixRow = activeMatrix[act.id] || '';

                return (
                  <tr
                    key={act.id}
                    onClick={() => setSelectedActivityId(act.id)}
                    className={`transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-teal-50/60 font-medium'
                        : 'hover:bg-slate-50/80'
                    }`}
                  >
                    <td className="py-2.5 px-3 text-center text-slate-400 font-mono font-medium">
                      {act.id + 1}
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-slate-900">
                      <div className="flex items-center gap-1.5">
                        {isSelected && <span className="size-1.5 rounded-full bg-[#04D3D4] shrink-0" />}
                        <span>{act.name}</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-2 text-center">
                      <span className={`text-[10px] px-2 py-0.5 rounded-md font-semibold ${
                        act.kind === 'approval' ? 'bg-emerald-50 text-emerald-700' : 'bg-blue-50 text-blue-700'
                      }`}>
                        {act.kind === 'approval' ? 'Duyệt' : 'Thực thi'}
                      </span>
                    </td>
                    {ROLE_KEYS.map((r: RoleKey, colIdx: number) => {
                      const letter = matrixRow[colIdx] as Letter;
                      return (
                        <td key={r} className="py-2 px-1 text-center">
                          {getLetterBadge(letter)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
