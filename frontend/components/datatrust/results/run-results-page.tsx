'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  ShieldAlert,
  AlertTriangle,
  HelpCircle,
  ChevronRight,
  TrendingDown,
  BarChart3,
  Layers,
  Loader2,
  XCircle,
  Copy,
  Check,
  RotateCcw
} from 'lucide-react';
import { Card, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PipelineStatusBadge } from '@/components/datatrust/pipeline/pipeline-status';
import { StartRunModal } from '@/components/datatrust/pipeline/start-run-modal';
import { apiBridge, type RunResultsData } from '@/lib/api-bridge';
import { useAgentStore } from '@/lib/agent-store';

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(new Date(value));
  } catch {
    return value;
  }
};

export function RunResultsPage() {
  const { runId = '' } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [results, setResults] = useState<RunResultsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showStartModal, setShowStartModal] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchResults = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const data = await apiBridge.fetchPipelineRunResults(runId);
      setResults(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Không thể nạp kết quả phân tích');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="grid min-h-[50vh] place-items-center text-sm text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="size-8 animate-spin text-cyan-400" />
          <p className="font-medium text-slate-300">Đang tổng hợp kết quả phân tích {runId} từ PostgreSQL…</p>
        </div>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-300">
          <div className="flex items-center gap-2 font-bold text-base text-rose-200">
            <XCircle className="size-5" /> Không thể nạp kết quả phân tích
          </div>
          <p className="mt-2 text-slate-300">{error || 'Không tìm thấy dữ liệu kết quả cho lượt chạy này.'}</p>
          <div className="mt-4 flex gap-3">
            <Link
              to={`/runs/${runId}`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-400 hover:text-cyan-300"
            >
              <ArrowLeft className="size-3.5" /> Quay lại Stepper theo dõi
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const { kpis, severity_breakdown, lane_breakdown, top_violated_rules } = results;

  return (
    <section className="page-enter mx-auto max-w-[1360px] space-y-6 pb-12">
      {/* Header & Breadcrumb */}
      <div>
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-400">
          <Link to="/runs" className="hover:text-white transition-colors">
            Danh sách lượt chạy
          </Link>
          <span>/</span>
          <Link to={`/runs/${runId}`} className="hover:text-white transition-colors">
            {runId}
          </Link>
          <span>/</span>
          <span className="text-cyan-400 font-bold">Kết quả Phân tích (Step 4)</span>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
                Kết quả Kiểm toán: {results.run_id}
                <button
                  onClick={() => copyToClipboard(results.run_id)}
                  title="Sao chép Run ID"
                  className="text-slate-400 hover:text-cyan-400 transition-colors p-1"
                >
                  {copied ? <Check className="size-4 text-emerald-400" /> : <Copy className="size-4" />}
                </button>
              </h1>
              <PipelineStatusBadge status={results.status as any} />
            </div>

            <p className="text-xs text-slate-400">
              Bộ dữ liệu: <strong className="text-slate-200">{results.dataset_id}</strong>
              {' '}· Bắt đầu: <strong className="text-slate-200">{formatDateTime(results.started_at)}</strong>
              {results.ended_at && (
                <> · Kết thúc: <strong className="text-slate-200">{formatDateTime(results.ended_at)}</strong></>
              )}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:self-center">
            <Button
              variant="outline"
              onClick={() => {
                useAgentStore.getState().resetHomepageFlow();
                navigate('/overview');
              }}
              className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5"
            >
              <RotateCcw className="size-4" />
              <span>Chọn lại</span>
            </Button>
            <Button
              onClick={() => navigate(`/runs/${results.run_id}/findings`)}
              className="bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 shadow-md shadow-cyan-500/20 gap-1.5"
            >
              <ShieldAlert className="size-4" />
              <span>Xem Toàn bộ Findings (Step 5)</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(`/runs/${results.run_id}`)}
              className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5"
            >
              <Layers className="size-4" />
              <span>Xem Stepper Tiến trình</span>
            </Button>
          </div>
        </div>
      </div>

      {/* STEP 4 / SPEC 07: 4 THẺ KPI CARDS (%) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* KPI 1: PASS RATE */}
        <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Đạt Chuẩn (Silver Pass)</span>
            <span className="grid size-8 place-items-center rounded-lg bg-emerald-500/10 text-emerald-400">
              <CheckCircle2 className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-emerald-400 font-mono">
              {kpis.pass_percentage.toFixed(2)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({kpis.pass_count.toLocaleString('vi-VN')} dòng)
            </span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Dữ liệu đạt tiêu chuẩn chất lượng, sẵn sàng hợp nhất vào tầng Silver.
          </p>
          <div className="absolute bottom-0 inset-x-0 h-1 bg-emerald-500/80" />
        </Card>

        {/* KPI 2: FAIL RATE */}
        <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Vi Phạm (Quarantine Fail)</span>
            <span className="grid size-8 place-items-center rounded-lg bg-rose-500/10 text-rose-400">
              <ShieldAlert className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-rose-400 font-mono">
              {kpis.fail_percentage.toFixed(2)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({kpis.fail_count.toLocaleString('vi-VN')} dòng)
            </span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Dữ liệu vi phạm quy tắc kiểm soát hoặc pháp lý, đã bị chặn cách ly.
          </p>
          <div className="absolute bottom-0 inset-x-0 h-1 bg-rose-500/80" />
        </Card>

        {/* KPI 3: WARNING SIGNALS */}
        <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Cảnh Báo (Advisory Signals)</span>
            <span className="grid size-8 place-items-center rounded-lg bg-amber-500/10 text-amber-400">
              <AlertTriangle className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-amber-400 font-mono">
              {kpis.warning_percentage.toFixed(2)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({kpis.warning_count.toLocaleString('vi-VN')} dòng)
            </span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Dấu hiệu trôi dạt phân phối (L2 Drift, L3 Relational, L4 Changepoint).
          </p>
          <div className="absolute bottom-0 inset-x-0 h-1 bg-amber-500/80" />
        </Card>

        {/* KPI 4: NOT EVALUATED */}
        <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Chưa Đánh Giá (Not Evaluated)</span>
            <span className="grid size-8 place-items-center rounded-lg bg-slate-800 text-slate-400">
              <HelpCircle className="size-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-300 font-mono">
              {kpis.not_evaluated_percentage.toFixed(2)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({kpis.not_evaluated_count.toLocaleString('vi-VN')} dòng)
            </span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Dữ liệu thiếu trường đầu vào hoặc điều kiện đánh giá theo quy tắc.
          </p>
          <div className="absolute bottom-0 inset-x-0 h-1 bg-slate-600" />
        </Card>
      </div>

      {/* PHÂN BỔ TỔNG THỂ & THỐNG KÊ LÀN (PROPORTION SEGMENT BAR) */}
      <Card className="rounded-2xl border-slate-800 bg-slate-900/80 p-5 shadow-xl">
        <div className="flex items-center justify-between mb-3 text-xs">
          <span className="font-bold text-white flex items-center gap-2">
            <BarChart3 className="size-4 text-cyan-400" />
            Phân bổ Tỷ lệ Dữ liệu (Tổng quét: {kpis.total_scanned.toLocaleString('vi-VN')} bản ghi)
          </span>
          <span className="text-slate-400 font-mono text-[11px]">
            Công thức: Scanned = Pass ({kpis.pass_count}) + Fail ({kpis.fail_count}) + Chưa đánh giá ({kpis.not_evaluated_count})
          </span>
        </div>

        {/* Multi-segment bar */}
        <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden flex">
          <div
            style={{ width: `${Math.max(0, kpis.pass_percentage)}%` }}
            className="h-full bg-emerald-500 transition-all duration-500"
            title={`Pass: ${kpis.pass_percentage}%`}
          />
          <div
            style={{ width: `${Math.max(0, kpis.fail_percentage)}%` }}
            className="h-full bg-rose-500 transition-all duration-500"
            title={`Fail: ${kpis.fail_percentage}%`}
          />
          <div
            style={{ width: `${Math.max(0, kpis.not_evaluated_percentage)}%` }}
            className="h-full bg-slate-600 transition-all duration-500"
            title={`Not Evaluated: ${kpis.not_evaluated_percentage}%`}
          />
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs pt-3 border-t border-slate-800/80">
          <div>
            <span className="text-slate-400">Mức Nghiêm trọng CRITICAL:</span>
            <p className="text-rose-400 font-bold text-base font-mono">
              {severity_breakdown.CRITICAL || 0} vi phạm
            </p>
          </div>
          <div>
            <span className="text-slate-400">Mức Nghiêm trọng HIGH:</span>
            <p className="text-amber-400 font-bold text-base font-mono">
              {severity_breakdown.HIGH || 0} vi phạm
            </p>
          </div>
          <div>
            <span className="text-slate-400">Làn A (Reliability Defect):</span>
            <p className="text-cyan-400 font-bold text-base font-mono">
              {lane_breakdown.LANE_A || 0} bản ghi
            </p>
          </div>
          <div>
            <span className="text-slate-400">Làn B (Policy Block):</span>
            <p className="text-indigo-400 font-bold text-base font-mono">
              {lane_breakdown.LANE_B || 0} bản ghi
            </p>
          </div>
        </div>
      </Card>

      {/* TOP 5 VIOLATED RULES (BẢNG QUY TẮC VI PHẠM NHIỀU NHẤT) */}
      <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
          <div>
            <CardTitle className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              <TrendingDown className="size-4 text-rose-400" />
              Top 5 Quy tắc Vi phạm Nhiều nhất (Top Violated Rules)
            </CardTitle>
            <p className="text-xs text-slate-400 mt-0.5">
              Xếp hạng theo số lượng bản ghi bị cách ly (Quarantine Failures) từ cơ sở dữ liệu
            </p>
          </div>
          <Link
            to={`/runs/${results.run_id}/findings`}
            className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <span>Xem toàn bộ Findings</span>
            <ChevronRight className="size-3.5" />
          </Link>
        </div>

        {(!top_violated_rules || top_violated_rules.length === 0) ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-400">
            <CheckCircle2 className="size-8 mx-auto text-emerald-400 mb-2 opacity-80" />
            <p className="text-white font-medium">Không phát hiện quy tắc vi phạm nghiêm trọng nào!</p>
            <p className="text-slate-500 mt-1">100% bản ghi đều vượt qua các chốt kiểm soát chất lượng và tuân thủ.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-800/60 uppercase font-mono text-[10px] text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Xếp hạng</th>
                  <th className="py-2.5 px-3">Quy tắc / Policy</th>
                  <th className="py-2.5 px-3">Cột mục tiêu</th>
                  <th className="py-2.5 px-3">Mức độ</th>
                  <th className="py-2.5 px-3 text-right">Bản ghi vi phạm</th>
                  <th className="py-2.5 px-3 text-right">Tỷ lệ (%)</th>
                  <th className="py-2.5 px-3">Nguyên nhân điển hình</th>
                  <th className="py-2.5 px-3 text-center">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {top_violated_rules.map((rule, idx) => (
                  <tr key={`${rule.rule_id}-${idx}`} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-3 font-mono font-bold text-slate-400">
                      #{idx + 1}
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-white block">{rule.rule_id}</span>
                      <span className="text-[11px] text-slate-400 block">{rule.policy_name}</span>
                    </td>
                    <td className="py-3 px-3 font-mono text-cyan-400">
                      {rule.column_name}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          rule.severity === 'CRITICAL'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}
                      >
                        {rule.severity}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-mono font-bold text-rose-400">
                      {rule.failed_record_count.toLocaleString('vi-VN')}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-300">
                      {rule.percentage.toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-slate-300 max-w-xs truncate" title={rule.reason}>
                      {rule.reason}
                    </td>
                    <td className="py-3 px-3 text-center">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          navigate(`/runs/${results.run_id}/findings?rule_id=${encodeURIComponent(rule.rule_id)}`)
                        }
                        className="h-7 px-2.5 text-[11px] border-slate-700 hover:bg-slate-800 text-cyan-400 hover:text-cyan-300"
                      >
                        Khoan sâu (Drill-down)
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <StartRunModal
        isOpen={showStartModal}
        onClose={() => setShowStartModal(false)}
        defaultDatasetId={results.dataset_id}
      />
    </section>
  );
}
