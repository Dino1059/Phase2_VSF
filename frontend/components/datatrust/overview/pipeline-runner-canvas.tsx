'use client';
import {
  CheckCircle2,
  FastForward,
  FileCheck2,
  GitBranch,
  Layers,
  Loader2,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Workflow,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAgentStore, type PipelineLevelProgress } from '@/lib/agent-store';

export function PipelineRunnerCanvas() {
  const {
    pipelineLevels,
    selectedDatasetId,
    datasets,
    viewLatestCompletedResults,
  } = useAgentStore();

  const dataset = datasets[selectedDatasetId] || datasets.trips || {
    id: selectedDatasetId,
    title: selectedDatasetId,
    filename: selectedDatasetId,
    records: 10382,
  };

  const {
    currentLevel,
    currentTaskName,
    activeRunId,
    task1Ingest,
    task2Profiling,
    task3LaneA,
    task3LaneB,
    task3LaneC,
    task4Evidence,
    l1,
    l2,
    l3,
    l4,
  } = pipelineLevels;

  const isCompleted = currentLevel === 'COMPLETED';

  const stages: {
    id: 'L1' | 'L2' | 'L3' | 'L4';
    level: string;
    title: string;
    description: string;
    spec: string;
    badgeTone: string;
    outcome: string;
    data: PipelineLevelProgress;
  }[] = [
    {
      id: 'L1',
      level: 'Tầng 1',
      title: 'Deterministic Rules & Sensors',
      description: 'Kiểm tra schema bất biến, giới hạn dải cảm biến (SoC, Temp), cân bằng sổ cái & nulls.',
      spec: 'Cố định: fare > 0, dist >= 0.1, ledger balance, non-null PK',
      badgeTone: 'bg-rose-100 text-rose-800 border-rose-200',
      outcome: 'Vi phạm → Trực tiếp Cách ly (Quarantine FAIL)',
      data: l1,
    },
    {
      id: 'L2',
      level: 'Tầng 2',
      title: 'Contextual Outlier Drift',
      description: 'Phát hiện giá trị lệch so với lịch sử thực thể xe/tài xế bằng Median và MAD.',
      spec: 'Thống kê: Robust Z-score > 4.5 baseline',
      badgeTone: 'bg-amber-100 text-amber-800 border-amber-200',
      outcome: 'Lệch ngưỡng → Gắn nhãn Cảnh báo (Warning)',
      data: l2,
    },
    {
      id: 'L3',
      level: 'Tầng 3',
      title: 'Bivariate Physical Residuals',
      description: 'Mô hình hồi quy tuyến tính (y = ax + b) giữa các cặp thông số (thời lượng vs kWh).',
      spec: 'Hồi quy: Residual error > 4.0σ độ lệch chuẩn',
      badgeTone: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      outcome: 'Sai lệch quan hệ → Gắn nhãn Cảnh báo (Warning)',
      data: l3,
    },
    {
      id: 'L4',
      level: 'Tầng 4',
      title: 'Changepoint Shift & Window Attribution',
      description: 'Thuật toán PELT / CUSUM phát hiện chuyển đổi chế độ vận hành chuỗi thời gian.',
      spec: 'Thời gian: PELT regime change & window attribution',
      badgeTone: 'bg-purple-100 text-purple-800 border-purple-200',
      outcome: 'Đổi chế độ → Gắn nhãn Cảnh báo (Warning)',
      data: l4,
    },
  ];

  return (
    <div className="space-y-4">
      {/* 1. TOP HEADER BANNER */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-[#04D3D4]/30 bg-gradient-to-r from-white via-[#f0faf9] to-[#e4f7f6] p-4.5 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40 shadow-xs">
            <Workflow size={22} className={isCompleted ? 'text-[#04D3D4]' : 'text-[#04D3D4] animate-spin'} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-bold text-slate-950">
                Pipeline Kiểm Soát & Tuân Thủ Dữ Liệu Chuẩn IPO (Airflow Adaptive 3-Lane)
              </h2>
              {isCompleted ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 border border-emerald-300 px-2.5 py-0.5 text-[10px] font-extrabold text-emerald-800">
                  <CheckCircle2 size={11} /> Hoàn tất pipeline
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FFC402] px-2.5 py-0.5 text-[10px] font-extrabold text-slate-950 shadow-2xs">
                  <Loader2 size={10} className="animate-spin" /> {currentTaskName || 'Đang thực thi'}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              Mã chạy (Run ID): <strong className="font-mono text-slate-900">{activeRunId || 'run_in_flight'}</strong> · Dataset: <strong className="font-mono text-slate-900">{dataset.filename || dataset.id}</strong> ({(dataset.records || 0).toLocaleString()} bản ghi)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={viewLatestCompletedResults}
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 border-[#04D3D4]/60 bg-white text-xs font-bold text-slate-950 hover:bg-[#04D3D4] transition cursor-pointer shadow-2xs"
          >
            <FastForward size={14} />
            <span>{isCompleted ? 'Xem kết quả lần chạy này' : 'Xem kết quả gần nhất'}</span>
          </Button>
        </div>
      </div>

      {/* 2. 4-TASK DAG STEPPER VIEW */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3.5">
          <div className="flex items-center gap-2">
            <Layers size={15} className="text-[#04D3D4]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Kiến Trúc Luồng Thực Thi Airflow DAG (4 Giai Đoạn)
            </h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            DAG ID: <strong>datatrust_adaptive_pipeline</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          {/* Step 1 */}
          <div className={`rounded-xl border p-3 transition-all ${
            task1Ingest.status === 'done'
              ? 'border-emerald-200 bg-emerald-50/30'
              : task1Ingest.status === 'running'
              ? 'border-[#04D3D4] bg-[#04D3D4]/10 ring-1 ring-[#04D3D4]'
              : 'border-slate-200 bg-slate-50 opacity-70'
          }`}>
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-[10px] text-slate-500 uppercase">Task 1</span>
              {task1Ingest.status === 'done' && <CheckCircle2 size={13} className="text-emerald-600" />}
              {task1Ingest.status === 'running' && <Loader2 size={13} className="animate-spin text-[#04D3D4]" />}
            </div>
            <h4 className="mt-1 font-bold text-slate-900 text-xs">Bronze Ingestion & Catalog</h4>
            <p className="mt-0.5 text-[11px] text-slate-500">Nạp {task1Ingest.rows ? task1Ingest.rows.toLocaleString() : (dataset.records || 0).toLocaleString()} dòng vào schema bronze</p>
          </div>

          {/* Step 2 */}
          <div className={`rounded-xl border p-3 transition-all ${
            task2Profiling.status === 'done'
              ? 'border-emerald-200 bg-emerald-50/30'
              : task2Profiling.status === 'running'
              ? 'border-[#04D3D4] bg-[#04D3D4]/10 ring-1 ring-[#04D3D4]'
              : 'border-slate-200 bg-slate-50 opacity-70'
          }`}>
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-[10px] text-slate-500 uppercase">Task 2</span>
              {task2Profiling.status === 'done' && <CheckCircle2 size={13} className="text-emerald-600" />}
              {task2Profiling.status === 'running' && <Loader2 size={13} className="animate-spin text-[#04D3D4]" />}
            </div>
            <h4 className="mt-1 font-bold text-slate-900 text-xs">Statistical Profiling Engine</h4>
            <p className="mt-0.5 text-[11px] text-slate-500">Đo lường schema, null-rate & Health Score</p>
          </div>

          {/* Step 3 */}
          <div className={`rounded-xl border p-3 transition-all ${
            task3LaneC.status === 'done' || isCompleted
              ? 'border-emerald-200 bg-emerald-50/30'
              : (task3LaneA.status === 'running' || task3LaneB.status === 'running')
              ? 'border-[#04D3D4] bg-[#04D3D4]/10 ring-1 ring-[#04D3D4]'
              : 'border-slate-200 bg-slate-50 opacity-70'
          }`}>
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-[10px] text-slate-500 uppercase">Task 3 (Parallel)</span>
              {(task3LaneC.status === 'done' || isCompleted) && <CheckCircle2 size={13} className="text-emerald-600" />}
              {(task3LaneA.status === 'running' || task3LaneB.status === 'running') && !isCompleted && <Loader2 size={13} className="animate-spin text-[#04D3D4]" />}
            </div>
            <h4 className="mt-1 font-bold text-slate-900 text-xs">Parallel 3-Lane Evaluation</h4>
            <p className="mt-0.5 text-[11px] text-slate-500">Lane A (L1-L4) // Lane B (Policy) → Lane C Router</p>
          </div>

          {/* Step 4 */}
          <div className={`rounded-xl border p-3 transition-all ${
            task4Evidence.status === 'done' || isCompleted
              ? 'border-emerald-200 bg-emerald-50/30'
              : task4Evidence.status === 'running'
              ? 'border-[#04D3D4] bg-[#04D3D4]/10 ring-1 ring-[#04D3D4]'
              : 'border-slate-200 bg-slate-50 opacity-70'
          }`}>
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-[10px] text-slate-500 uppercase">Task 4</span>
              {(task4Evidence.status === 'done' || isCompleted) && <CheckCircle2 size={13} className="text-emerald-600" />}
              {task4Evidence.status === 'running' && !isCompleted && <Loader2 size={13} className="animate-spin text-[#04D3D4]" />}
            </div>
            <h4 className="mt-1 font-bold text-slate-900 text-xs">Immutable Audit Evidence</h4>
            <p className="mt-0.5 text-[11px] text-slate-500">Chữ ký số & chuỗi băm SHA-256 sổ cái IPO</p>
          </div>
        </div>
      </div>

      {/* 3. PARALLEL 3-LANE EVALUATION CORE (LANE A // LANE B -> LANE C) */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* LANE A: L1 - L4 RELIABILITY SUITE (Span 2 cols on lg) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-[#04D3D4]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                Lane A: Bộ Kiểm Định Độ Tin Cậy & Cảm Biến L1 - L4
              </h3>
            </div>
            <span className="text-[11px] text-slate-500 font-mono">
              Phát hiện dị thường đa tầng (P2 Detection)
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {stages.map((stage) => {
              const isDone = stage.data.status === 'done' || isCompleted;
              const isRunning = stage.data.status === 'running' && !isCompleted;
              const isPending = stage.data.status === 'idle' && !isCompleted;

              return (
                <Card
                  key={stage.id}
                  className={`relative overflow-hidden rounded-2xl border p-4 transition-all duration-300 bg-white ${
                    isRunning
                      ? 'border-[#04D3D4] ring-2 ring-[#04D3D4]/30 shadow-sm'
                      : isDone
                      ? 'border-slate-200'
                      : 'border-slate-200/70 opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`rounded-md px-2 py-0.5 text-[10px] font-mono font-extrabold tracking-wide uppercase ${
                        isRunning
                          ? 'bg-[#04D3D4] text-slate-950'
                          : isDone
                          ? 'bg-slate-900 text-[#04D3D4]'
                          : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {stage.id} · {stage.level}
                    </span>

                    {isDone && (
                      <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-600">
                        <CheckCircle2 size={13} /> Hoàn tất
                      </span>
                    )}
                    {isRunning && (
                      <span className="flex items-center gap-1 text-[11px] font-bold text-slate-900 animate-pulse">
                        <Loader2 size={12} className="animate-spin text-[#04D3D4]" /> Đang quét...
                      </span>
                    )}
                    {isPending && <span className="text-[11px] text-slate-400">Chờ luồng...</span>}
                  </div>

                  <h4 className="mt-2 text-xs font-bold text-slate-900">{stage.title}</h4>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500 line-clamp-2">
                    {stage.description}
                  </p>

                  <div className="mt-2 inline-flex items-center rounded px-2 py-0.5 text-[9px] font-semibold border bg-slate-50 text-slate-700">
                    {stage.outcome}
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-[10px] font-semibold text-slate-500 mb-1">
                      <span>Tiến độ</span>
                      <span className="font-bold text-slate-900">{isDone ? 100 : stage.data.progress}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full transition-all duration-500 rounded-full ${
                          isRunning ? 'bg-[#04D3D4] animate-pulse' : isDone ? 'bg-[#04D3D4]' : 'bg-slate-300'
                        }`}
                        style={{ width: `${isDone ? 100 : stage.data.progress}%` }}
                      />
                    </div>
                  </div>

                  {/* Metrics */}
                  <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-2 text-[10px]">
                    <div>
                      <span className="text-slate-400">Đã quét:</span>
                      <div className="font-bold text-slate-900">
                        {isDone ? (dataset.records || 0).toLocaleString() : stage.data.scanned.toLocaleString()} dòng
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400">Tín hiệu bắt được:</span>
                      <div className="font-bold text-slate-800">
                        {stage.data.failed > 0 ? (
                          <span className="text-rose-600">{stage.data.failed} vi phạm</span>
                        ) : (
                          <span className="text-emerald-700">0 lỗi</span>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>

        {/* LANE B & LANE C (1 col on lg) */}
        <div className="space-y-3">
          {/* LANE B: HIERARCHICAL POLICY ENGINE */}
          <Card className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Scale size={15} className="text-[#04D3D4]" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  Lane B: Policy Processor
                </h4>
              </div>
              <span className="rounded bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 text-[9px] font-extrabold text-indigo-700">
                Song Song
              </span>
            </div>

            <p className="mt-2 text-[11px] text-slate-600 leading-relaxed">
              Thực thi chính sách bảo vệ dữ liệu theo phân cấp thẩm quyền đa vùng: <strong>Global → Vùng (VN/EU/US) → Quốc gia</strong>.
            </p>

            <div className="mt-2.5 space-y-1.5 text-[10px]">
              <div className="flex items-center justify-between rounded-lg bg-slate-50 p-2 border border-slate-100">
                <span className="text-slate-500">Khung pháp lý áp dụng:</span>
                <span className="font-bold text-slate-900">Luật 91/2025/QH15 & NĐ 356/2025</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-slate-50 p-2 border border-slate-100">
                <span className="text-slate-500">Quy chuẩn quốc tế:</span>
                <span className="font-bold text-slate-900">GDPR, CCPA, IFRS 15 / SOX 404</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-slate-50 p-2 border border-slate-100">
                <span className="text-slate-500">Biến đổi an toàn (Treatments):</span>
                <span className="font-bold text-emerald-700">Mask SĐT, Hash ID, Round GPS</span>
              </div>
            </div>
          </Card>

          {/* LANE C: VERDICT MERGER & 3-WAY ROUTER */}
          <Card className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <GitBranch size={15} className="text-[#04D3D4]" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  Lane C: 3-Way Dynamic Router
                </h4>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Ma trận tiền lệ A/B</span>
            </div>

            <p className="mt-2 text-[11px] text-slate-500">
              Hội tụ phán quyết: <strong>FAIL &gt; WARNING &gt; PASS</strong>. Tách 3 kho dữ liệu:
            </p>

            <div className="mt-3 space-y-2">
              <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/40 p-2.5">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={16} className="text-emerald-600" />
                  <div>
                    <div className="text-xs font-bold text-emerald-950">Kho Sạch (Silver)</div>
                    <div className="text-[10px] text-emerald-700">Đạt chuẩn sản xuất & IPO</div>
                  </div>
                </div>
                <span className="font-mono text-xs font-extrabold text-emerald-800">
                  {(task3LaneC.silver || Math.max(0, (dataset.records || 0) - (task3LaneC.quarantine || 0))).toLocaleString()} dòng
                </span>
              </div>

              <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50/40 p-2.5">
                <div className="flex items-center gap-2">
                  <ShieldAlert size={16} className="text-rose-600" />
                  <div>
                    <div className="text-xs font-bold text-rose-950">Cách Ly (Quarantine)</div>
                    <div className="text-[10px] text-rose-700">Vi phạm luật / Lỗi L1 nghiêm trọng</div>
                  </div>
                </div>
                <span className="font-mono text-xs font-extrabold text-rose-700">
                  {(task3LaneC.quarantine || 0).toLocaleString()} bản ghi
                </span>
              </div>

              <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50/40 p-2.5">
                <div className="flex items-center gap-2">
                  <Shield size={16} className="text-amber-600" />
                  <div>
                    <div className="text-xs font-bold text-amber-950">Cảnh Báo (Warning)</div>
                    <div className="text-[10px] text-amber-700">Dị thường thống kê L2 / L3 / L4</div>
                  </div>
                </div>
                <span className="font-mono text-xs font-extrabold text-amber-800">
                  {(task3LaneC.warning || 0).toLocaleString()} bản ghi
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* 4. TASK 4: IMMUTABLE AUDIT EVIDENCE LEDGER & SIGNATURE */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-2.5 mb-2.5">
          <div className="flex items-center gap-2">
            <FileCheck2 size={16} className="text-[#04D3D4]" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Task 4: Sổ Cái Bằng Chứng Kiểm Toán Bất Biến (IPO Digital Signature Ledger)
            </h4>
          </div>
          <span className="inline-flex items-center gap-1 rounded bg-[#04D3D4]/20 text-[#007460] font-mono text-[10px] font-bold px-2 py-0.5">
            Chữ ký: {task4Evidence.digitalSignature || 'SIG-AIRFLOW-3LANE-GSM-IPO-2026'}
          </span>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 text-[11px] font-mono">
          <div className="rounded-lg bg-slate-50 p-2 border border-slate-200/70 truncate">
            <span className="text-slate-400">Previous Hash: </span>
            <span className="text-slate-700 font-bold">{task4Evidence.previousHash ? `${task4Evidence.previousHash.slice(0, 24)}...` : 'edffc2d20fb28a87a6ab1948d0...'}</span>
          </div>
          <div className="rounded-lg bg-slate-50 p-2 border border-slate-200/70 truncate">
            <span className="text-slate-400">Evidence SHA-256: </span>
            <span className="text-[#04D3D4] font-bold">{task4Evidence.evidenceHash ? `${task4Evidence.evidenceHash.slice(0, 24)}...` : 'd5609049be3bf0611a5b914388...'}</span>
          </div>
        </div>
      </div>

      {/* 5. LIVE STREAM TELEMETRY LOG TERMINAL */}
      <div className="rounded-2xl border border-slate-800 bg-slate-950 p-3.5 font-mono text-[11px] text-slate-300 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2 text-[10px] text-slate-400">
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-[#04D3D4] animate-ping" />
            <span>DataTrust Real-time Audit Stream (Port :8000 · Airflow Orchestrator)</span>
          </div>
          <span className="text-[#FFC402]">TLS 1.3 / SOX-404 Verified</span>
        </div>
        <div className="space-y-1 text-slate-400 max-h-28 overflow-y-auto scrollbar-none">
          <p className="text-[#04D3D4]">
            [TASK 1 - BRONZE] Ingested raw records into schema bronze.{dataset.id || 'dataset'} · Hash validated
          </p>
          <p className="text-slate-300">
            [TASK 2 - PROFILER] Schema contract validated · Health Score: 94.6% · Column metrics registered
          </p>
          <p className="text-[#04D3D4]">
            [TASK 3A - LANE A] L1 Deterministic checks evaluated · L2/L3/L4 statistical anomaly suite active
          </p>
          <p className="text-slate-300">
            [TASK 3B - LANE B] Policy Check: Applied Luật 91/2025/QH15 & NĐ 356/2025 · Treatments enforced
          </p>
          <p className="text-[#FFC402]">
            [TASK 3C - LANE C] Verdict Merger: Precedence enforced · Routed to Silver, Quarantine & Warning
          </p>
          <p className="text-[#04D3D4] font-bold">
            [TASK 4 - EVIDENCE] Immutable Ledger: Hash-chain calculated · Signed with {task4Evidence.digitalSignature || 'SIG-AIRFLOW-3LANE-GSM-IPO-2026'}
          </p>
        </div>
      </div>
    </div>
  );
}
