'use client';
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Database,
  Eye,
  FileCheck2,
  Lock,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAgentStore, type DatasetItem } from '@/lib/agent-store';
import { FindingInspectorModal } from '@/components/datatrust/findings/finding-inspector-modal';
import { DatasetPreviewModal } from '@/components/datatrust/datasets/dataset-preview-modal';
import { DatasetSelectorModal } from './dataset-selector-modal';
import { AiChatPane } from './ai-chat-pane';
import { PipelineRunnerCanvas } from './pipeline-runner-canvas';
import { SlideDownDashboard } from './slide-down-dashboard';

export function OverviewPage() {
  const navigate = useNavigate();
  const {
    currentRole,
    homepageViewMode,
    selectedDatasetId,
    selectDataset,
    datasets,
    complianceCheckRules,
    dataTreatmentRules,
    getDatasetMetadataStats,
    startPipelineRun,
  } = useAgentStore();

  const [isSelectorModalOpen, setIsSelectorModalOpen] = useState(false);
  const [previewDataset, setPreviewDataset] = useState<DatasetItem | null>(null);

  // Selected dataset object
  const currentDataset = useMemo(() => {
    if (!selectedDatasetId) return null;
    const cleanId = selectedDatasetId.replace('.csv', '');
    return (
      datasets[cleanId] ||
      datasets[`${cleanId}.csv`] ||
      datasets[selectedDatasetId] ||
      null
    );
  }, [datasets, selectedDatasetId]);

  // Real metadata stats computed from PostgreSQL catalog.columns
  const metadataStats = useMemo(() => {
    return getDatasetMetadataStats(selectedDatasetId || '');
  }, [getDatasetMetadataStats, selectedDatasetId]);

  // Real applied rules count for selected dataset
  const { appliedComplianceCount, appliedTreatmentCount } = useMemo(() => {
    if (!selectedDatasetId) return { appliedComplianceCount: 0, appliedTreatmentCount: 0 };
    const cleanSelected = selectedDatasetId.replace('.csv', '');
    const compCount = complianceCheckRules.filter(
      (r) => r.dataset_id.replace('.csv', '') === cleanSelected
    ).length;
    const treatCount = dataTreatmentRules.filter(
      (r) => r.dataset_id.replace('.csv', '') === cleanSelected
    ).length;
    return { appliedComplianceCount: compCount, appliedTreatmentCount: treatCount };
  }, [complianceCheckRules, dataTreatmentRules, selectedDatasetId]);

  // 8 Unique datasets for quick badges in initial state
  const quickDatasetList = useMemo(() => {
    const map = new Map<string, DatasetItem>();
    Object.values(datasets || {}).forEach((ds) => {
      if (ds && (ds.id || ds.filename)) {
        const canonicalKey = (ds.id || ds.filename || '').replace('.csv', '');
        if (!map.has(canonicalKey)) {
          map.set(canonicalKey, ds);
        }
      }
    });
    return Array.from(map.values()).slice(0, 8);
  }, [datasets]);

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
              {/* ========================================================================= */}
              {/* STATE 1: INITIAL STATE (CHƯA CHỌN DATASET) - SPEC 4.2                     */}
              {/* ========================================================================= */}
              {!selectedDatasetId ? (
                <div className="space-y-4">
                  {/* Greeting & Selection Card matching ASCII Mockup in Spec 4.2 */}
                  <div className="rounded-2xl border border-slate-200/90 bg-white p-7 sm:p-9 shadow-xs">
                    <div className="max-w-xl space-y-4">
                      {/* Badge */}
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#04D3D4]/15 border border-[#04D3D4]/35 px-3 py-1 text-[11px] font-extrabold text-slate-900">
                        <Sparkles size={12} className="text-[#04D3D4] fill-[#FFC402]" /> AI Admin
                        Assurance
                      </span>

                      {/* Header & Prompt */}
                      <div>
                        <h2 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
                          Xin chào, {currentRole === 'auditor' ? 'Auditor (Viewer)' : 'Admin'}
                        </h2>
                        <p className="mt-1.5 text-sm font-medium text-slate-600">
                          {currentRole === 'auditor'
                            ? 'Hệ thống kiểm toán dữ liệu độc lập chuẩn IPO (Chế độ xem).'
                            : 'Tôi có thể giúp bạn kiểm tra tuân thủ dữ liệu.'}
                        </p>
                      </div>

                      <div className="pt-2">
                        <p className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                          Dataset cần kiểm tra?
                        </p>
                      </div>

                      {/* Primary Button [ Chọn dataset ] */}
                      <div className="pt-1">
                        <Button
                          size="lg"
                          onClick={() => setIsSelectorModalOpen(true)}
                          className="h-11 px-6 text-sm font-bold bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9] shadow-sm hover:shadow transition-all cursor-pointer rounded-xl flex items-center gap-2"
                        >
                          <Database size={16} />
                          <span>Chọn dataset</span>
                        </Button>
                      </div>
                    </div>

                    {/* Quick Access Pills for 8 PostgreSQL datasets */}
                    <div className="mt-8 border-t border-slate-100 pt-5">
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block mb-2.5">
                        Bộ dữ liệu sẵn có trong hệ thống (PostgreSQL):
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {quickDatasetList.map((ds) => {
                          const canonicalId = (ds.id || ds.filename || '').replace('.csv', '');
                          const stats = getDatasetMetadataStats(canonicalId);
                          return (
                            <button
                              key={canonicalId}
                              onClick={() => selectDataset(canonicalId)}
                              className="group flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/70 hover:bg-[#04D3D4]/10 hover:border-[#04D3D4]/60 px-3 py-1.5 text-xs transition cursor-pointer"
                            >
                              <span className="font-mono font-bold text-slate-800 group-hover:text-slate-950">
                                {canonicalId}
                              </span>
                              {stats.hasPii ? (
                                <span className="size-1.5 rounded-full bg-amber-500" title="Chứa PII" />
                              ) : null}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* ========================================================================= */
                /* STATE 2: DATASET SELECTED STATE - SPEC 4.4                                */
                /* ========================================================================= */
                <div className="space-y-4">
                  {/* Analysis Confirmation Header */}
                  <div className="rounded-2xl border border-[#04D3D4]/35 bg-gradient-to-r from-[#04D3D4]/10 via-[#FFC402]/5 to-white p-5 shadow-2xs">
                    <div className="flex items-start gap-3">
                      <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-950 text-[#04D3D4] font-bold shadow-xs">
                        <Sparkles size={16} />
                      </div>
                      <div className="flex-1">
                        <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#008b74]">
                          Metadata Analysis Complete
                        </span>
                        <h3 className="text-base font-bold text-slate-900 mt-0.5">
                          Tôi đã phân tích metadata của{' '}
                          <span className="font-mono text-slate-950 underline decoration-[#04D3D4] decoration-2">
                            {selectedDatasetId.replace('.csv', '')}
                          </span>
                          .
                        </h3>
                        <p className="text-xs text-slate-600 mt-1">
                          Hệ thống đã nhận diện cấu trúc các trường, phân loại dữ liệu cá nhân theo Luật
                          91/2025/QH15 & GDPR, và sẵn sàng thực thi kiểm tra tuân thủ.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsSelectorModalOpen(true)}
                        className="h-8 gap-1.5 text-xs font-semibold text-slate-700 hover:text-slate-950 hover:bg-slate-100 border-slate-200 shrink-0"
                      >
                        <RotateCcw size={12} />
                        <span>Đổi dataset</span>
                      </Button>
                    </div>
                  </div>

                  {/* Dataset Metadata Card matching Spec 4.4 */}
                  <Card className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                      <div>
                        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                          Dataset
                        </span>
                        <h4 className="text-xl font-mono font-bold text-slate-950 mt-0.5">
                          {selectedDatasetId.replace('.csv', '')}
                        </h4>
                        {currentDataset?.description && (
                          <p className="text-xs text-slate-500 mt-1">
                            {currentDataset.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {metadataStats.hasPii ? (
                          <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-bold text-amber-900">
                            <ShieldAlert size={13} className="text-amber-600" />
                            PII: Có dữ liệu cá nhân
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-bold text-emerald-900">
                            <ShieldCheck size={13} className="text-emerald-600" />
                            PII: Không
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 3 PII Metadata Metrics Grid from PostgreSQL catalog.columns (Luật 91/2025/QH15 & GDPR) */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                      {/* Metric 1: Personal-data fields */}
                      <div className="rounded-xl border border-amber-200/60 bg-amber-50/40 p-4">
                        <span className="text-[11px] font-semibold text-amber-700 block">
                          Trường dữ liệu cá nhân
                        </span>
                        <div className="mt-1 text-2xl font-bold font-mono text-amber-950">
                          {metadataStats.personalDataCount}
                        </div>
                        <span className="mt-0.5 text-[11px] font-bold text-amber-800">
                          personal-data fields
                        </span>
                      </div>

                      {/* Metric 2: Direct identifiers */}
                      <div className="rounded-xl border border-rose-200/60 bg-rose-50/40 p-4">
                        <span className="text-[11px] font-semibold text-rose-700 block">
                          Định danh trực tiếp
                        </span>
                        <div className="mt-1 text-2xl font-bold font-mono text-rose-950">
                          {metadataStats.directIdCount}
                        </div>
                        <span className="mt-0.5 text-[11px] font-bold text-rose-800">
                          direct identifiers
                        </span>
                      </div>

                      {/* Metric 3: Contextual personal-data fields */}
                      <div className="rounded-xl border border-blue-200/60 bg-blue-50/40 p-4">
                        <span className="text-[11px] font-semibold text-blue-700 block">
                          Dữ liệu cá nhân theo ngữ cảnh
                        </span>
                        <div className="mt-1 text-2xl font-bold font-mono text-blue-950">
                          {metadataStats.contextualCount}
                        </div>
                        <span className="mt-0.5 text-[11px] font-bold text-blue-800">
                          contextual personal-data fields
                        </span>
                      </div>
                    </div>

                    {/* Compliance Rules Available Section */}
                    <div className="rounded-xl border border-slate-200/80 bg-slate-50/40 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                      <div>
                        <span className="text-xs font-bold text-slate-900 block">
                          Các compliance rules hiện có:
                        </span>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          {appliedComplianceCount} rule kiểm tra tuân thủ (cố định pháp lý) ·{' '}
                          {appliedTreatmentCount} rule xử lý dữ liệu đang áp dụng cho bảng này
                        </p>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate('/rules')}
                        className="h-8 gap-1.5 text-xs font-bold border-slate-300 hover:border-slate-900 text-slate-800 hover:text-slate-950 cursor-pointer shadow-2xs shrink-0"
                      >
                        <FileCheck2 size={13} className="text-[#04D3D4]" />
                        <span>Xem rule</span>
                        <ArrowRight size={12} className="text-slate-400" />
                      </Button>
                    </div>

                    {/* Primary Action Buttons */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (currentDataset) setPreviewDataset(currentDataset);
                        }}
                        className="h-9 gap-1.5 px-3 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 cursor-pointer"
                      >
                        <Eye size={13} />
                        <span>Xem dữ liệu thô (Bronze Sample)</span>
                      </Button>

                      <div className="flex items-center gap-2.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate('/rules')}
                          className="h-9 gap-1.5 px-4 text-xs font-bold border-slate-300 text-slate-800 hover:bg-slate-100 cursor-pointer"
                        >
                          <Lock size={13} className="text-slate-500" />
                          <span>Xem rule</span>
                        </Button>

                        {currentRole === 'admin' ? (
                          <Button
                            size="sm"
                            onClick={() => startPipelineRun(selectedDatasetId)}
                            className="h-9 gap-1.5 px-5 text-xs font-bold bg-slate-950 text-[#04D3D4] hover:bg-slate-900 hover:text-white shadow-xs cursor-pointer transition-all"
                          >
                            <Play size={12} className="fill-current text-[#04D3D4]" />
                            <span>Chạy kiểm tra</span>
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() => navigate('/results')}
                            className="h-9 gap-1.5 px-5 text-xs font-bold bg-slate-950 text-[#04D3D4] hover:bg-slate-900 hover:text-white shadow-xs cursor-pointer transition-all"
                          >
                            <FileCheck2 size={13} className="text-[#04D3D4]" />
                            <span>Xem kết quả kiểm toán</span>
                          </Button>
                        )}
                      </div>
                    </div>
                  </Card>
                </div>
              )}

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

      {/* Modal Chọn Dataset theo Spec 4.3 */}
      <DatasetSelectorModal
        isOpen={isSelectorModalOpen}
        onClose={() => setIsSelectorModalOpen(false)}
        initialSelectedId={selectedDatasetId}
      />

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
