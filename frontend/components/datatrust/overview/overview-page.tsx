'use client';
import {
  ArrowRight,
  Database,
  Play,
  Sparkles,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAgentStore, type DatasetItem } from '@/lib/agent-store';
import { FindingInspectorModal } from '@/components/datatrust/findings/finding-inspector-modal';
import { AiChatPane } from './ai-chat-pane';
import { PipelineRunnerCanvas } from './pipeline-runner-canvas';
import { SlideDownDashboard } from './slide-down-dashboard';

export function OverviewPage() {
  const {
    homepageViewMode,
    selectedDatasetId,
    selectDataset,
    datasets,
    startPipelineRun,
  } = useAgentStore();

  return (
    <div className="page-enter mx-auto max-w-[1600px] space-y-4">

      {/* Main Dual-Pane Layout: Left Chat Sticky & Fixed, Right Canvas Scrollable */}
      <div className="flex flex-col lg:flex-row gap-5 items-start">
        {/* Left Pane: AI Chat (Fixed position with independent scrollbar) */}
        <aside className="shrink-0 w-full lg:sticky lg:top-[80px] lg:h-[calc(100vh-108px)] z-10 lg:w-[380px] xl:w-[420px]">
          <AiChatPane />
        </aside>

        {/* Right Pane: Dynamic Interactive Canvas (Scrolls independently) */}
        <main className="flex-1 min-w-0 w-full space-y-4">
          {homepageViewMode === 'welcome' && (
            <div className="space-y-4 animate-in fade-in-50 duration-300">
              {/* Hero Banner with Palette: 04D3D4 / FFC402 / FFFFFF */}
              <div className="rounded-2xl border border-[#04D3D4]/30 bg-gradient-to-br from-white via-[#f0faf9] to-[#e4f7f6] p-6 shadow-xs">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="max-w-2xl space-y-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#04D3D4]/20 border border-[#04D3D4]/40 px-2.5 py-0.5 text-[11px] font-extrabold text-slate-900">
                      <Sparkles size={12} className="text-[#04D3D4] fill-[#FFC402]" /> Bắt đầu luồng kiểm soát dữ liệu
                    </span>
                    <h2 className="text-xl font-bold text-slate-950 sm:text-2xl">
                      Chọn dataset. AI Agent lo toàn bộ phần còn lại.
                    </h2>
                    <p className="text-xs text-slate-700 leading-relaxed">
                      AI Agent sẽ tự động nạp dữ liệu, thực thi kiểm tra 4 tầng (L1 Deterministic → L2 Statistical Outlier → L3 Multivariate → L4 Change Point), trích xuất vi phạm và chuẩn bị các đề xuất Rule khắc phục để bạn thẩm định.
                    </p>
                  </div>

                  <Button
                    variant="xanhsm"
                    onClick={() => startPipelineRun(selectedDatasetId)}
                    size="lg"
                    className="h-11 gap-2 text-slate-950 px-5 text-xs font-bold shadow-sm border border-[#04D3D4] cursor-pointer"
                  >
                    <span>Cho Agent chạy {selectedDatasetId}</span>
                    <ArrowRight size={15} />
                  </Button>
                </div>
              </div>

              {/* Dataset Selection Cards Grid with Raw Names */}
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Datasets sẵn sàng thẩm tra (VinGroup GSM Pilot Datasets)
                  </h3>
                  <span className="text-[11px] text-slate-500">
                    Bấm vào card để chọn và chạy luồng L1-L4
                  </span>
                </div>

                <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.values(datasets).map((ds: DatasetItem) => {
                    const isSelected = ds.id === selectedDatasetId;
                    return (
                      <Card
                        key={ds.id}
                        onClick={() => selectDataset(ds.id)}
                        className={`cursor-pointer rounded-2xl border p-4.5 transition-all duration-200 bg-white ${
                          isSelected
                            ? 'border-[#04D3D4] ring-2 ring-[#04D3D4]/30 shadow-sm'
                            : 'border-slate-200 hover:border-[#04D3D4]/60 hover:shadow-xs'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <span className="grid size-8 place-items-center rounded-xl bg-[#04D3D4]/15 text-slate-950 font-mono font-bold border border-[#04D3D4]/30">
                              <Database size={15} className="text-[#04D3D4]" />
                            </span>
                            <span className="text-sm font-mono font-bold text-slate-900">
                              {ds.id}
                            </span>
                          </div>
                          {isSelected && (
                            <span className="rounded-full bg-[#04D3D4] px-2.5 py-0.5 text-[10px] font-extrabold text-slate-950 shadow-2xs">
                              Đang chọn
                            </span>
                          )}
                        </div>

                        <div className="mt-3.5 grid grid-cols-2 gap-2 text-[11px] border-t border-slate-100 pt-3">
                          <div>
                            <span className="text-slate-400">Quy mô:</span>
                            <div className="font-semibold text-slate-800">
                              {ds.records.toLocaleString()} records
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-400">Anomalies:</span>
                            <div className="font-bold text-rose-600">
                              {ds.anomalies} vi phạm
                            </div>
                          </div>
                        </div>

                        <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2.5">
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                            {ds.proposedRules.length} Rule đề xuất
                          </span>
                          <Button
                            variant="white"
                            onClick={(e) => {
                              e.stopPropagation();
                              startPipelineRun(ds.id);
                            }}
                            size="sm"
                            className="group h-7 gap-1 border border-slate-300 bg-white text-[11px] font-bold text-slate-900 hover:border-slate-950 hover:bg-slate-950 hover:text-white transition-all cursor-pointer shadow-xs"
                          >
                            <Play size={10} className="fill-current text-current transition-colors" />
                            <span>Chạy {ds.id}</span>
                          </Button>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              </div>

              {/* 4-Level Pipeline Architecture Preview Card */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3">
                  Kiến trúc luồng kiểm soát dữ liệu 4 tầng trong DataTrust OS
                </h4>
                <div className="grid gap-3 sm:grid-cols-4 text-xs">
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      L1 · Deterministic
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Quy tắc cố định</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Kiểm tra Null, Schema, giới hạn dải số học và quét PII cleartext.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      L2 · Statistical Outlier
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Phát hiện ngoại lai</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Sử dụng Median, MAD và Robust Z-score để phát hiện độ lệch chuẩn.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      L3 · Multivariate
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Tương quan đa biến</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Tính phần dư hồi quy tuyến tính giữa các trường tương quan.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      L4 · Change Point
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Độ trôi chuỗi thời gian</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      CUSUM & PELT phát hiện thay đổi chế độ và dịch chuyển dữ liệu.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {homepageViewMode === 'running_pipeline' && <PipelineRunnerCanvas />}

          {homepageViewMode === 'results_dashboard' && <SlideDownDashboard />}
        </main>
      </div>

      {/* Global Inspector Modal for deep dive into Findings */}
      <FindingInspectorModal />
    </div>
  );
}
