'use client';
import { useState } from 'react';
import {
  Database,
  Eye,
  Play,
  Sparkles,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAgentStore, type DatasetItem } from '@/lib/agent-store';
import { FindingInspectorModal } from '@/components/datatrust/findings/finding-inspector-modal';
import { DatasetPreviewModal } from '@/components/datatrust/datasets/dataset-preview-modal';
import { AiChatPane } from './ai-chat-pane';
import { PipelineRunnerCanvas } from './pipeline-runner-canvas';
import { SlideDownDashboard } from './slide-down-dashboard';

export function OverviewPage() {
  const {
    homepageViewMode,
    selectDataset,
    datasets,
    startPipelineRun,
  } = useAgentStore();

  const [previewDataset, setPreviewDataset] = useState<DatasetItem | null>(null);

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
                      AI Agent tự động nạp Bronze Ingestion, chạy Profiling Engine, phân tích song song 3 Làn (Lane A L1-L4 // Lane B Chính sách Luật 91/2025/QH15 & GDPR → Lane C Router), trích xuất vi phạm và tạo chữ ký số kiểm toán IPO.
                    </p>
                  </div>
                </div>
              </div>

              {/* Dataset Selection Cards Grid with Raw Names */}
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Datasets sẵn sàng thẩm tra
                  </h3>
                  <span className="text-[11px] text-slate-500">
                    Bấm vào card để chọn và chạy Pipeline chuẩn IPO
                  </span>
                </div>

                <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
                  {Array.from(
                    new Map(
                      Object.values(datasets || {})
                        .filter((ds): ds is DatasetItem => Boolean(ds && (ds.filename || ds.id)))
                        .map((ds: DatasetItem) => [ds.filename || ds.id, ds])
                    ).values()
                  ).map((ds: DatasetItem) => {
                    return (
                      <Card
                        key={ds.filename || ds.id}
                        onClick={() => selectDataset(ds.id)}
                        className={`cursor-pointer rounded-2xl border p-4.5 transition-all duration-200 bg-white`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-[#04D3D4]/15 text-slate-950 font-mono font-bold border border-[#04D3D4]/30">
                              <Database size={15} className="text-[#04D3D4]" />
                            </span>
                            <div className="min-w-0">
                              <div className="text-xs font-mono font-bold text-slate-900 truncate" title={ds.filename || ds.id}>
                                {ds.filename || ds.id}
                              </div>
                            </div>
                          </div>
                        </div>

                        {ds.zoneCounts ? (
                          <div className="mt-2.5 flex flex-wrap gap-1">
                            {Object.entries(ds.zoneCounts).map(([zone, count]) => (
                              <span key={zone} className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-semibold text-slate-600">
                                <span className={`size-1.5 rounded-full ${zone === 'VN' ? 'bg-red-500' : zone === 'US' ? 'bg-blue-500' : 'bg-amber-500'}`} />
                                {zone}: {(count || 0).toLocaleString()}
                              </span>
                            ))}
                          </div>
                        ) : null}

                        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] border-t border-slate-100 pt-3">
                          <div>
                            <span className="text-slate-400">Số dòng:</span>
                            <div className="font-semibold text-slate-800">
                              {(ds.records || 0).toLocaleString()}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-400">Anomalies:</span>
                            {ds.isProfiled && ds.anomalies !== null ? (
                              <div className="font-bold text-rose-600">
                                {ds.anomalies} vi phạm
                              </div>
                            ) : (
                              <div className="font-medium text-slate-400 italic">
                                Chưa thẩm tra (—)
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPreviewDataset(ds);
                            }}
                            className="h-7 gap-1 px-2 text-[11px] font-semibold text-[#04D3D4] hover:bg-[#04D3D4]/10 hover:text-slate-950 transition-colors cursor-pointer"
                          >
                            <Eye size={12} />
                            <span>Xem dữ liệu thô</span>
                          </Button>

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
                            <span>Chạy pipeline</span>
                          </Button>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              </div>

              {/* 4-Task & 3-Lane Architecture Preview Card */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Kiến trúc Pipeline Kiểm soát & Tuân thủ Dữ liệu Chuẩn IPO (Airflow Adaptive 3-Lane)
                  </h4>
                  <span className="text-[10px] font-mono text-[#007460] bg-[#e6f6f2] px-2 py-0.5 rounded font-bold border border-[#b2e2d5]">
                    Airflow DAG: datatrust_adaptive_pipeline
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-4 text-xs">
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      Task 1 · Ingestion
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Bronze & Catalog</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Nạp dữ liệu thô vào schema bronze và đăng ký danh mục quản trị catalog.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      Task 2 · Profiling
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Thống kê & Health Score</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Đo lường schema, phân bổ giá trị, null-rate và tính điểm chất lượng bảng.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      Task 3 · Parallel 3-Lane
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Lane A // Lane B → Lane C</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Lane A L1-L4 chạy song song Lane B Policy (Luật 91, GDPR) và hội tụ tại Lane C Router.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-[#f8faf9] p-3.5">
                    <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-extrabold text-[#04D3D4]">
                      Task 4 · Audit Evidence
                    </span>
                    <h5 className="mt-2 font-bold text-slate-900 text-xs">Sổ cái Bất biến IPO</h5>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      Ký số SIG-AIRFLOW-3LANE & băm chuỗi SHA-256 lưu trữ chứng cứ kiểm toán.
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

      {/* Raw Data Preview Modal */}
      {previewDataset && (
        <DatasetPreviewModal
          isOpen={!!previewDataset}
          onClose={() => setPreviewDataset(null)}
          datasetId={previewDataset.id}
          datasetTitle={previewDataset.name}
          filename={previewDataset.filename || previewDataset.id}
          totalRecords={previewDataset.records}
        />
      )}
    </div>
  );
}
