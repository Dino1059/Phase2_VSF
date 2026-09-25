'use client';
import {
  CheckCircle2,
  FastForward,
  Layers,
  Loader2,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAgentStore, type PipelineLevelProgress } from '@/lib/agent-store';

export function PipelineRunnerCanvas() {
  const {
    pipelineLevels,
    selectedDatasetId,
    datasets,
    skipPipelineRunToResults,
  } = useAgentStore();

  const dataset = datasets[selectedDatasetId] || datasets.trips;
  const { currentLevel, l1, l2, l3, l4 } = pipelineLevels;

  const stages: {
    id: 'L1' | 'L2' | 'L3' | 'L4';
    level: string;
    title: string;
    description: string;
    spec: string;
    data: PipelineLevelProgress;
  }[] = [
    {
      id: 'L1',
      level: 'Tầng 1',
      title: 'Deterministic Validation',
      description: 'Kiểm tra schema, phạm vi số học, nulls & dữ liệu PII dạng cleartext.',
      spec: 'Cố định: fare > 0, dist >= 0.1, PII regex, bounds',
      data: l1,
    },
    {
      id: 'L2',
      level: 'Tầng 2',
      title: 'Statistical Outlier Detection',
      description: 'Phát hiện giá trị lệch đáng kể so với phân bố lịch sử.',
      spec: 'Thống kê: Median, MAD, Robust Z-score > 3.0',
      data: l2,
    },
    {
      id: 'L3',
      level: 'Tầng 3',
      title: 'Multivariate Anomaly Detection',
      description: 'Phát hiện sai lệch tương quan đa biến và phần dư hồi quy tuyến tính.',
      spec: 'Hồi quy: y = ax + b, residual error > 2.5σ',
      data: l3,
    },
    {
      id: 'L4',
      level: 'Tầng 4',
      title: 'Change Point Detection',
      description: 'Phát hiện độ trôi dòng dữ liệu và thay đổi chế độ trên chuỗi thời gian.',
      spec: 'Thời gian: CUSUM / PELT Regime Shift Gate',
      data: l4,
    },
  ];

  return (
    <div className="space-y-4">
      {/* Top Banner with Palette: 04D3D4 / FFC402 / FFFFFF */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-[#04D3D4]/30 bg-gradient-to-r from-white via-[#f0faf9] to-[#e4f7f6] p-4 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40 shadow-xs">
            <Layers size={20} className="text-[#04D3D4] animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-950">
                Đang thực thi Pipeline Kiểm Soát Dữ Liệu L1 - L4
              </h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-[#FFC402] px-2.5 py-0.5 text-[10px] font-extrabold text-slate-950 shadow-2xs">
                <Loader2 size={10} className="animate-spin" /> Đang chạy {currentLevel}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              Dataset: <strong className="font-mono text-slate-900">{dataset.id}</strong> (
              {dataset.records.toLocaleString()} records) · Kiến trúc IPO Assurance GSM V35
            </p>
          </div>
        </div>

        <Button
          onClick={skipPipelineRunToResults}
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 border-[#04D3D4]/50 bg-white text-xs font-bold text-slate-950 hover:bg-[#04D3D4] transition"
        >
          <FastForward size={14} />
          <span>Bỏ qua & Xem kết quả</span>
        </Button>
      </div>

      {/* 4 Connected Stages Cards */}
      <div className="grid gap-3 sm:grid-cols-2">
        {stages.map((stage) => {
          const isDone = stage.data.status === 'done';
          const isRunning = stage.data.status === 'running';
          const isPending = stage.data.status === 'idle';

          return (
            <Card
              key={stage.id}
              className={`relative overflow-hidden rounded-2xl border p-4.5 transition-all duration-300 bg-white ${
                isRunning
                  ? 'border-[#04D3D4] ring-2 ring-[#04D3D4]/30 shadow-sm'
                  : isDone
                  ? 'border-slate-200'
                  : 'border-slate-200/70 opacity-60'
              }`}
            >
              {/* Top Level & Status Badge */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-md px-2 py-0.5 text-[10px] font-mono font-extrabold tracking-wide uppercase ${
                      isRunning
                        ? 'bg-[#04D3D4] text-slate-950 shadow-2xs'
                        : isDone
                        ? 'bg-slate-900 text-[#04D3D4]'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {stage.id} · {stage.level}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500">{stage.spec}</span>
                </div>

                {isDone && (
                  <span className="flex items-center gap-1 text-[11px] font-bold text-[#04D3D4]">
                    <CheckCircle2 size={14} className="text-[#04D3D4]" /> Hoàn tất
                  </span>
                )}
                {isRunning && (
                  <span className="flex items-center gap-1 text-[11px] font-bold text-slate-900 animate-pulse">
                    <Loader2 size={13} className="animate-spin text-[#04D3D4]" /> Đang phân tích...
                  </span>
                )}
                {isPending && <span className="text-[11px] text-slate-400">Chờ luồng...</span>}
              </div>

              {/* Title & Description */}
              <h3 className="mt-2.5 text-xs font-bold text-slate-900">{stage.title}</h3>
              <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
                {stage.description}
              </p>

              {/* Animated Progress Bar */}
              <div className="mt-3.5">
                <div className="flex items-center justify-between text-[10px] font-semibold text-slate-500 mb-1">
                  <span>Tiến độ quét</span>
                  <span className="font-bold text-slate-900">{stage.data.progress}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full transition-all duration-500 rounded-full ${
                      isRunning
                        ? 'bg-[#04D3D4] animate-pulse'
                        : isDone
                        ? 'bg-[#04D3D4]'
                        : 'bg-slate-300'
                    }`}
                    style={{ width: `${stage.data.progress}%` }}
                  />
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="mt-3.5 grid grid-cols-3 gap-2 border-t border-slate-100 pt-2.5 text-[10px]">
                <div>
                  <span className="text-slate-400">Đã quét:</span>
                  <div className="font-bold text-slate-900">
                    {stage.data.scanned.toLocaleString()} dòng
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Hợp lệ (Pass):</span>
                  <div className="font-bold text-slate-800">
                    {stage.data.passed.toLocaleString()} dòng
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Phát hiện lỗi:</span>
                  <div
                    className={`font-bold ${
                      stage.data.failed > 0 ? 'text-rose-600' : 'text-slate-600'
                    }`}
                  >
                    {stage.data.failed} bản ghi
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Live Stream Telemetry Log Terminal */}
      <div className="rounded-2xl border border-slate-800 bg-slate-950 p-3.5 font-mono text-[11px] text-slate-300 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2 text-[10px] text-slate-400">
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-[#04D3D4] animate-ping" />
            <span>DataTrust Real-time Audit Stream (Ingestion Port :8000)</span>
          </div>
          <span className="text-[#FFC402]">TLS 1.3 / Verified</span>
        </div>
        <div className="space-y-1 text-slate-400 max-h-24 overflow-y-auto scrollbar-none">
          <p className="text-[#04D3D4]">
            [OK] Connector source stream hooked to {dataset.id} · Schema hash valid
          </p>
          <p className="text-slate-300">
            [L1] Deterministic Gate: Range checks, Null rate validation, PII Regex matching
          </p>
          {currentLevel !== 'L1' && (
            <p className="text-[#FFC402]">
              [L2] Outlier Signal emitted: MAD threshold deviation detected
            </p>
          )}
          {(currentLevel === 'L3' || currentLevel === 'L4' || currentLevel === 'COMPLETED') && (
            <p className="text-[#FFC402]">
              [L3] Multivariate Residual: Linear relation broken on outliers
            </p>
          )}
          {currentLevel === 'COMPLETED' && (
            <p className="text-[#04D3D4] font-bold">
              [L4] Change Point Detection completed · Transitioning canvas to Results Dashboard...
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
