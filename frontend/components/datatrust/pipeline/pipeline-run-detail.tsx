'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  Database,
  FileText,
  ShieldAlert,
  XCircle,
  Clock,
  Loader2,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  Activity,
  Layers,
  Copy,
  Check,
  Play
} from 'lucide-react';
import { Card, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PipelineStatusBadge } from './pipeline-status';
import { StartRunModal } from './start-run-modal';
import { apiBridge, type PipelineRunDetail as DetailType } from '@/lib/api-bridge';

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

export function PipelineRunDetail({ runId: propRunId }: { runId?: string }) {
  const { id: paramRunId } = useParams<{ id: string }>();
  const runId = propRunId || paramRunId || '';
  const navigate = useNavigate();

  const [detail, setDetail] = useState<DetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showStartModal, setShowStartModal] = useState(false);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchDetail = useCallback(async () => {
    if (!runId) return;
    try {
      const data = await apiBridge.fetchPipelineRunDetail(runId);
      setDetail(data);
      setError(null);
      return data;
    } catch (err: any) {
      setError(err.message || 'Không thể nạp thông tin lượt chạy');
      return null;
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchDetail();

    // Auto-polling nếu lượt chạy đang trong tiến trình
    const startPolling = () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(async () => {
        const d = await fetchDetail();
        if (d && (d.status === 'SUCCESS' || d.status === 'FAILED')) {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        }
      }, 3500);
    };

    startPolling();

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [fetchDetail]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading && !detail) {
    return (
      <div className="grid min-h-[50vh] place-items-center text-sm text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="size-8 animate-spin text-cyan-400" />
          <p className="font-medium text-slate-300">Đang truy vấn dữ liệu lượt chạy {runId} từ PostgreSQL…</p>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-300">
          <div className="flex items-center gap-2 font-bold text-base text-rose-200">
            <XCircle className="size-5" /> Không tìm thấy lượt chạy
          </div>
          <p className="mt-2 text-slate-300">{error || `Lượt chạy '${runId}' không tồn tại trong cơ sở dữ liệu.`}</p>
          <div className="mt-4">
            <Link
              to="/runs"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-400 hover:text-cyan-300"
            >
              <ArrowLeft className="size-3.5" /> Trở lại danh sách lượt chạy
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isCompleted = detail.status === 'SUCCESS' || detail.status === 'COMPLETED';
  const isRunning = detail.status === 'RUNNING' || detail.status === 'PENDING';

  return (
    <section className="page-enter mx-auto max-w-[1360px] space-y-6 pb-12">
      {/* Header & Breadcrumb */}
      <div>
        <Link
          to="/runs"
          className="mb-3 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="size-3.5" /> Trở lại danh sách lượt chạy
        </Link>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
                {detail.run_id}
                <button
                  onClick={() => copyToClipboard(detail.run_id)}
                  title="Sao chép Run ID"
                  className="text-slate-400 hover:text-cyan-400 transition-colors p-1"
                >
                  {copied ? <Check className="size-4 text-emerald-400" /> : <Copy className="size-4" />}
                </button>
              </h1>
              <PipelineStatusBadge status={detail.status as any} />
              {isRunning && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-xs font-medium text-cyan-400 border border-cyan-500/20 animate-pulse">
                  <Activity className="size-3" /> Đang thực thi theo thời gian thực
                </span>
              )}
            </div>

            <p className="text-xs text-slate-400">
              DAG Airflow: <strong className="text-slate-200">{detail.dag_id}</strong>
              {detail.airflow_dag_run_id && (
                <> · DagRun: <span className="font-mono text-cyan-400">{detail.airflow_dag_run_id}</span></>
              )}
              {' '}· Bắt đầu: <strong className="text-slate-200">{formatDateTime(detail.started_at)}</strong>
              {detail.ended_at && (
                <> · Kết thúc: <strong className="text-slate-200">{formatDateTime(detail.ended_at)}</strong></>
              )}
            </p>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <div className="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-2.5 py-1 text-xs font-mono font-medium text-slate-200 border border-slate-700">
                <Database className="size-3 text-cyan-400" />
                <span>Dataset: <strong>{detail.dataset_id}</strong></span>
              </div>
              <div className="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 border border-slate-700">
                <ShieldCheck className="size-3 text-emerald-400" />
                <span>Tiêu chuẩn: SOX 404 / Luật 91/2025/QH15</span>
              </div>
            </div>
          </div>

          {/* Quick Action Navigation */}
          <div className="flex flex-wrap items-center gap-2 sm:self-center">
            {isCompleted && (
              <>
                <Button
                  onClick={() => navigate(`/runs/${detail.run_id}/results`)}
                  className="bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 shadow-md shadow-cyan-500/20 gap-1.5"
                >
                  <FileText className="size-4" />
                  <span>Xem Kết quả Phân tích (KPIs)</span>
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate(`/runs/${detail.run_id}/findings`)}
                  className="border-slate-700 text-slate-200 hover:bg-slate-800 gap-1.5"
                >
                  <ShieldAlert className="size-4 text-amber-400" />
                  <span>Danh sách Findings ({detail.findings_summary?.total || 0})</span>
                </Button>
              </>
            )}
            <Button
              variant="outline"
              onClick={() => setShowStartModal(true)}
              className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5"
            >
              <Play className="size-3.5 fill-slate-300" />
              <span>Chạy lại</span>
            </Button>
          </div>
        </div>
      </div>

      {/* STEP 3 / SPEC 06: STEPPER 5 BƯỚC THỰC THI */}
      <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-6 shadow-xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
              <Layers className="size-4 text-cyan-400" />
              Tiến trình 5 Bước Kiểm toán (Pipeline Stepper)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Khớp nối chuẩn 5 nhiệm vụ tuần tự & song song của Apache Airflow DAG
            </p>
          </div>
          <span className="text-xs font-mono text-cyan-400 bg-cyan-500/10 px-2 py-1 rounded border border-cyan-500/20">
            {detail.steps?.filter((s) => s.status === 'COMPLETED').length || 0} / 5 Hoàn tất
          </span>
        </div>

        <div className="grid gap-3 md:grid-cols-5 relative">
          {(detail.steps || []).map((step) => {
            const isDone = step.status === 'COMPLETED';
            const isStepRunning = step.status === 'RUNNING';
            const isFailed = step.status === 'FAILED';

            return (
              <div
                key={step.step_name}
                className={`relative rounded-xl p-4 border transition-all ${
                  isStepRunning
                    ? 'border-cyan-500/80 bg-cyan-950/20 shadow-md shadow-cyan-500/10'
                    : isDone
                    ? 'border-emerald-500/40 bg-emerald-950/10'
                    : isFailed
                    ? 'border-rose-500/60 bg-rose-950/20'
                    : 'border-slate-800 bg-slate-800/30 opacity-70'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono font-bold text-slate-400">
                    BƯỚC 0{step.step_order}
                  </span>
                  {isStepRunning && <Loader2 className="size-4 animate-spin text-cyan-400" />}
                  {isDone && <CheckCircle2 className="size-4 text-emerald-400" />}
                  {isFailed && <XCircle className="size-4 text-rose-400" />}
                  {!isStepRunning && !isDone && !isFailed && (
                    <Clock className="size-4 text-slate-500" />
                  )}
                </div>

                <h3 className="text-xs font-bold text-white line-clamp-1">{step.title}</h3>
                <p className="text-[11px] font-mono text-cyan-400 mt-0.5">{step.step_name}</p>

                <div className="mt-3 pt-2 border-t border-slate-800/60 text-[10px] text-slate-400 flex items-center justify-between">
                  <span>Trạng thái:</span>
                  <span
                    className={`font-semibold ${
                      isDone
                        ? 'text-emerald-400'
                        : isStepRunning
                        ? 'text-cyan-400 animate-pulse'
                        : isFailed
                        ? 'text-rose-400'
                        : 'text-slate-500'
                    }`}
                  >
                    {step.status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* 6 THẺ CHỈ SỐ KIỂM TOÁN (KPI METRICS) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Card className="rounded-xl border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Tổng quét (Scanned)</p>
              <p className="mt-1 text-xl font-bold text-white font-mono">
                {(detail.metrics?.scanned || 0).toLocaleString('vi-VN')}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-lg bg-slate-800 text-slate-300">
              <Database className="size-4 text-cyan-400" />
            </span>
          </div>
        </Card>

        <Card className="rounded-xl border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Sạch (Silver Pass)</p>
              <p className="mt-1 text-xl font-bold text-emerald-400 font-mono">
                {(detail.metrics?.silver || 0).toLocaleString('vi-VN')}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-lg bg-emerald-500/10 text-emerald-400">
              <CheckCircle2 className="size-4" />
            </span>
          </div>
        </Card>

        <Card className="rounded-xl border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Cách ly (Quarantine)</p>
              <p className="mt-1 text-xl font-bold text-rose-400 font-mono">
                {(detail.metrics?.quarantine || 0).toLocaleString('vi-VN')}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-lg bg-rose-500/10 text-rose-400">
              <ShieldAlert className="size-4" />
            </span>
          </div>
        </Card>

        <Card className="rounded-xl border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Cảnh báo (Warnings)</p>
              <p className="mt-1 text-xl font-bold text-amber-400 font-mono">
                {(detail.metrics?.warning || 0).toLocaleString('vi-VN')}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-lg bg-amber-500/10 text-amber-400">
              <AlertCircle className="size-4" />
            </span>
          </div>
        </Card>

        <Card className="rounded-xl border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Chưa đánh giá</p>
              <p className="mt-1 text-xl font-bold text-slate-300 font-mono">
                {(detail.metrics?.not_evaluated || 0).toLocaleString('vi-VN')}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-lg bg-slate-800 text-slate-400">
              <HelpCircle className="size-4" />
            </span>
          </div>
        </Card>

        <Card className="rounded-xl border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Vấn đề (Findings)</p>
              <p className="mt-1 text-xl font-bold text-cyan-400 font-mono">
                {detail.findings_summary?.total || 0}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-lg bg-cyan-500/10 text-cyan-400">
              <FileText className="size-4" />
            </span>
          </div>
        </Card>
      </div>

      {/* BẰNG CHỨNG KIỂM TOÁN SỔ CÁI BẤT BIẾN (AUDIT EVIDENCE LEDGER) */}
      {detail.evidence && (
        <Card className="rounded-2xl border-cyan-500/30 bg-slate-900/90 p-5 shadow-xl">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <ShieldCheck className="size-4" />
              </span>
              <div>
                <h3 className="text-xs font-bold text-white tracking-tight">
                  Bằng chứng Kiểm toán Bất biến (SOX 404 / IPO Hash Ledger)
                </h3>
                <p className="text-[11px] text-slate-400">
                  Ghi nhận tự động vào bảng audit.evidence với SHA-256 liên kết chuỗi
                </p>
              </div>
            </div>
            <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5" /> Chữ ký Hợp lệ: {detail.evidence.digital_signature}
            </span>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 text-xs">
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-1">
              <span className="text-[11px] text-slate-400 font-semibold">Evidence SHA-256 Hash:</span>
              <p className="font-mono text-cyan-300 break-all text-[11px]">{detail.evidence.evidence_hash}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-1">
              <span className="text-[11px] text-slate-400 font-semibold">Previous Hash (Liên kết khối):</span>
              <p className="font-mono text-slate-400 break-all text-[11px]">
                {detail.evidence.previous_hash || 'GENESIS_EVIDENCE_HASH_GSM_IPO_2026'}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* EVENT TIMELINE LOG (NHẬT KÝ SỰ KIỆN THỜI GIAN THỰC) */}
      <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
          <CardTitle className="text-xs font-bold text-white tracking-tight flex items-center gap-2">
            <Activity className="size-4 text-cyan-400" />
            Nhật ký Sự kiện Lượt chạy (Pipeline Event Timeline)
          </CardTitle>
          <span className="text-[11px] text-slate-400 font-mono">
            {detail.events?.length || 0} sự kiện ghi nhận
          </span>
        </div>

        <div className="space-y-2">
          {(!detail.events || detail.events.length === 0) ? (
            <div className="rounded-xl border border-dashed border-slate-800 p-6 text-center text-xs text-slate-500">
              Chưa có sự kiện thời gian thực nào được ghi nhận cho lượt chạy này.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60 max-h-60 overflow-y-auto pr-1">
              {detail.events.map((evt) => (
                <div key={evt.event_id} className="py-2.5 flex items-start justify-between gap-4 text-xs">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-mono font-bold bg-slate-800 text-cyan-400 border border-slate-700">
                      {evt.step_name || 'SYSTEM'}
                    </span>
                    <div>
                      <p className="text-slate-200 font-medium">{evt.message}</p>
                    </div>
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono shrink-0">
                    {formatDateTime(evt.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <StartRunModal
        isOpen={showStartModal}
        onClose={() => setShowStartModal(false)}
        defaultDatasetId={detail.dataset_id}
      />
    </section>
  );
}
