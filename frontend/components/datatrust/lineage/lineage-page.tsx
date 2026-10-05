'use client';
import { useEffect, useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ExternalLink,
  RotateCw,
  GitFork,
  Database,
  Layers,
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  Columns,
  Workflow,
  Info,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  apiBridge,
  type LineageStatus,
  type LineageGraphResponse,
  type LineageNode,
  type ColumnLineageItem,
  type LineageRunItem,
} from '@/lib/api-bridge';
import { LineageNodeDrawer } from './lineage-node-drawer';

export function LineagePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialRunId = searchParams.get('run_id') || '';
  const initialDataset = searchParams.get('dataset') || 'ride_hailing_xanh_sm_trips';

  const [activeTab, setActiveTab] = useState<'graph' | 'column'>('graph');
  const [selectedDataset, setSelectedDataset] = useState<string>(initialDataset);
  const [selectedRunId, setSelectedRunId] = useState<string>(initialRunId);

  const [status, setStatus] = useState<LineageStatus | null>(null);
  const [graphData, setGraphData] = useState<LineageGraphResponse | null>(null);
  const [columnLineage, setColumnLineage] = useState<ColumnLineageItem[]>([]);
  const [runsList, setRunsList] = useState<LineageRunItem[]>([]);
  const [selectedNode, setSelectedNode] = useState<LineageNode | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Load status and runs list on mount
  useEffect(() => {
    apiBridge.fetchLineageStatus().then(setStatus).catch(() => {});
    apiBridge.fetchLineageRuns().then(setRunsList).catch(() => {});
  }, []);

  // Load graph and column lineage when dataset or run changes
  const loadLineageData = async () => {
    setIsLoading(true);
    try {
      const [graph, cols] = await Promise.all([
        apiBridge.fetchLineageGraph(selectedDataset, selectedRunId || undefined),
        apiBridge.fetchColumnLineage(selectedDataset, selectedRunId || undefined),
      ]);
      setGraphData(graph);
      setColumnLineage(cols);
    } catch (err) {
      console.warn('Failed to load lineage data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLineageData();
  }, [selectedDataset, selectedRunId]);

  // Sync params with URL
  const handleDatasetChange = (ds: string) => {
    setSelectedDataset(ds);
    setSearchParams((prev) => {
      prev.set('dataset', ds);
      return prev;
    });
  };

  const handleRunChange = (runId: string) => {
    setSelectedRunId(runId);
    setSearchParams((prev) => {
      if (runId) prev.set('run_id', runId);
      else prev.delete('run_id');
      return prev;
    });
  };

  // Group nodes by stage for layout
  const stages = useMemo(() => {
    if (!graphData?.nodes) return [];
    const map = new Map<number, LineageNode[]>();
    graphData.nodes.forEach((n) => {
      const s = n.stage || 1;
      if (!map.has(s)) map.set(s, []);
      map.get(s)!.push(n);
    });
    return Array.from(map.entries()).sort(([a], [b]) => a - b);
  }, [graphData]);

  const getNodeColor = (layer: string) => {
    switch (layer) {
      case 'RAW':
        return 'border-slate-300 bg-slate-50 text-slate-800 hover:border-slate-400';
      case 'BRONZE':
        return 'border-amber-300 bg-amber-50/80 text-amber-900 hover:border-amber-400';
      case 'SILVER':
        return 'border-emerald-300 bg-emerald-50/80 text-emerald-900 hover:border-emerald-400';
      case 'QUARANTINE':
        return 'border-rose-300 bg-rose-50/80 text-rose-900 hover:border-rose-400';
      case 'WARNING':
        return 'border-yellow-300 bg-yellow-50/80 text-yellow-900 hover:border-yellow-400';
      case 'AUDIT':
        return 'border-teal-300 bg-teal-50/80 text-teal-900 hover:border-teal-400';
      case 'CATALOG':
        return 'border-purple-300 bg-purple-50/80 text-purple-900 hover:border-purple-400';
      case 'EVALUATION':
      case 'TASK':
      default:
        return 'border-sky-300 bg-sky-50/80 text-sky-900 hover:border-sky-400';
    }
  };

  const getNodeIcon = (layer: string) => {
    switch (layer) {
      case 'RAW':
        return Database;
      case 'BRONZE':
        return Layers;
      case 'SILVER':
        return CheckCircle2;
      case 'QUARANTINE':
        return AlertOctagon;
      case 'WARNING':
        return AlertTriangle;
      case 'AUDIT':
        return ShieldCheck;
      default:
        return Workflow;
    }
  };

  return (
    <div className="page-enter mx-auto max-w-[1400px] space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              OpenLineage & Metadata Governance
            </span>
            {status?.mode === 'MARQUEZ_LIVE' ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800">
                <span className="size-2 animate-pulse rounded-full bg-emerald-500" />
                Marquez Live (Run-Level)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-[11px] font-bold text-amber-800" title={status?.modeDescription}>
                <span className="size-2 rounded-full bg-amber-500" />
                Catalog Topology Fallback (Marquez Offline)
              </span>
            )}
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            Dòng Dữ Liệu & Nguồn Gốc (Data Lineage)
          </h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Chuẩn OpenLineage 1.0 truy vết toàn diện: Nguồn thô ➔ Bronze ➔ Đánh giá 3 Làn ➔ Silver / Quarantine ➔ Ký số IPO
          </p>
        </div>

        {/* Action: Open Marquez Native Web UI */}
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={loadLineageData}
            disabled={isLoading}
            className="gap-2 text-xs"
          >
            <RotateCw className={`size-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Làm mới
          </Button>

          <Button
            size="sm"
            className="gap-2 bg-[#008b74] text-xs font-semibold text-white shadow-sm hover:bg-[#007562]"
            onClick={() => window.open(status?.marquezWebUrl || 'http://localhost:3001', '_blank')}
          >
            <span>Mở Marquez Web UI</span>
            <ExternalLink className="size-3.5" />
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Datasets được bảo vệ</span>
            <Database className="size-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">8 Bảng</div>
          <div className="mt-1 text-[11px] text-slate-500">100% Khởi tạo tại Bronze & Silver</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Airflow Pipeline Tasks</span>
            <Workflow className="size-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">6 Tasks</div>
          <div className="mt-1 text-[11px] text-slate-500">Task 1 ➔ Task 2 ➔ Làn A/B/C ➔ Task 4</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Bảo vệ trường PII</span>
            <ShieldCheck className="size-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">100% Tuân thủ</div>
          <div className="mt-1 text-[11px] text-slate-500">Luật 91/2025/QH15 & GDPR che mờ</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Bằng chứng kiểm toán</span>
            <CheckCircle2 className="size-4 text-teal-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-teal-700">SHA-256 Chuỗi</div>
          <div className="mt-1 text-[11px] text-slate-500">Chữ ký số bất biến audit.evidence</div>
        </Card>
      </div>

      {/* Filter Toolbar & Tab Switcher */}
      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          {/* Tabs: Graph vs Column Lineage */}
          <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
            <button
              onClick={() => setActiveTab('graph')}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                activeTab === 'graph'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <GitFork className="size-3.5" />
              Sơ đồ luồng (Lineage Graph)
            </button>
            <button
              onClick={() => setActiveTab('column')}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                activeTab === 'column'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Columns className="size-3.5" />
              Chuyển đổi cấp cột (Column Lineage)
            </button>
          </div>

          {/* Filters: Dataset & Run ID */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Run Filter */}
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="font-medium">Lần chạy:</span>
              <select
                value={selectedRunId}
                onChange={(e) => handleRunChange(e.target.value)}
                className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-800 shadow-2xs focus:border-[#008b74] focus:outline-hidden"
              >
                <option value="">Lần chạy gần nhất (Latest Run)</option>
                {runsList.map((r, idx) => (
                  <option key={`${r.runId}-${idx}`} value={r.runId}>
                    {r.runId.slice(0, 18)}… ({r.datasetId} - {new Date(r.createdAt).toLocaleTimeString('vi-VN')})
                  </option>
                ))}
              </select>
            </div>

            {/* Dataset Filter */}
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="font-medium">Bảng dữ liệu:</span>
              <select
                value={selectedDataset}
                onChange={(e) => handleDatasetChange(e.target.value)}
                className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-800 shadow-2xs focus:border-[#008b74] focus:outline-hidden"
              >
                <option value="ride_hailing_xanh_sm_trips">ride_hailing_xanh_sm_trips (Chuyến đi taxi điện)</option>
                <option value="synthetic_ev_telemetry_ved_ref">synthetic_ev_telemetry_ved_ref (Cảm biến pin & GPS)</option>
                <option value="acn_charging_mapped">acn_charging_mapped (Phiên sạc trụ điện)</option>
                <option value="feedback_pii">feedback_pii (Phản hồi khách hàng & PII)</option>
                <option value="dim_customers">dim_customers (Danh mục khách hàng)</option>
                <option value="dim_drivers">dim_drivers (Danh mục tài xế)</option>
                <option value="fleet_index">fleet_index (Chỉ số đoàn xe)</option>
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* Main Content Area */}
      {activeTab === 'graph' ? (
        /* ================= 1. INTERACTIVE GRAPH VIEW ================= */
        <div className="space-y-4">
          {/* Source Status Banner */}
          <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white/70 px-4 py-2.5 text-xs text-slate-600 backdrop-blur-xs">
            <div className="flex items-center gap-2">
              <Info className="size-4 text-slate-400" />
              <span>
                Nguồn đồ thị:{' '}
                <strong className={graphData?.source === 'MARQUEZ_LIVE' ? 'text-emerald-700' : 'text-amber-700'}>
                  {graphData?.source === 'MARQUEZ_LIVE' ? 'Marquez Core API (Trực tiếp)' : 'PostgreSQL Catalog (Topology Fallback)'}
                </strong>
                . Nhấp vào bất kỳ Node nào để soi chi tiết Schema, Record Count và OpenLineage Facets.
              </span>
            </div>
            <span className="font-mono text-[11px] text-slate-400">
              {graphData?.totalNodes || 0} Nodes • {graphData?.totalEdges || 0} Edges
            </span>
          </div>

          {/* Interactive DAG Stage Flow Canvas */}
          <Card className="relative overflow-x-auto p-6">
            <div className="min-w-[1000px] space-y-8">
              {stages.map(([stageNumber, nodes]) => {
                const stageLabels: Record<number, string> = {
                  1: '1. Nguồn Dữ Liệu Thô (Raw Storage)',
                  2: '2. Task 1: Ingestion & Khởi tạo Catalog',
                  3: '3. Lớp Lưu Trữ Bronze (PostgreSQL)',
                  4: '4. Task 2: Data Profiling Engine',
                  5: '5. Task 3: Đánh Giá Song Song 3 Làn (Parallel Lanes)',
                  6: '6. Khu Vực Đích 3 Hướng (Target Zones)',
                  7: '7. Task 4: Ký Số Bằng Chứng Kiểm Toán IPO',
                  8: '8. Sổ Cái Chứng Cứ Bất Biến (audit.evidence)',
                };

                return (
                  <div key={stageNumber} className="relative">
                    <div className="mb-2.5 flex items-center gap-2">
                      <span className="rounded-md bg-slate-200/80 px-2 py-0.5 text-[10px] font-bold text-slate-700">
                        Giai đoạn {stageNumber}
                      </span>
                      <span className="text-xs font-bold text-slate-800">
                        {stageLabels[stageNumber] || `Giai đoạn ${stageNumber}`}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3">
                      {nodes.map((node) => {
                        const Icon = getNodeIcon(node.layer);
                        const isSelected = selectedNode?.id === node.id;

                        return (
                          <div
                            key={node.id}
                            onClick={() => setSelectedNode(node)}
                            className={`group relative flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition-all ${getNodeColor(
                              node.layer
                            )} ${
                              isSelected
                                ? 'ring-2 ring-[#008b74] ring-offset-2 shadow-md'
                                : 'shadow-2xs hover:shadow-sm'
                            }`}
                          >
                            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/90 shadow-2xs">
                              <Icon className="size-4.5" />
                            </div>

                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-bold uppercase tracking-wider opacity-75">
                                  {node.layer}
                                </span>
                                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700">
                                  <span className="size-1 rounded-full bg-emerald-500" />
                                  {node.status}
                                </span>
                              </div>

                              <h4 className="mt-0.5 truncate text-xs font-bold text-slate-900" title={node.label || node.name}>
                                {node.label || node.name}
                              </h4>

                              {node.recordCount !== undefined && (
                                <p className="mt-1 text-[11px] font-medium opacity-85">
                                  {node.recordCount.toLocaleString('vi-VN')} dòng
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      ) : (
        /* ================= 2. COLUMN LINEAGE VIEW ================= */
        <div className="space-y-4">
          <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-4 text-xs text-blue-900">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-blue-700" />
              <span className="font-bold">
                Chứng cứ chuyển đổi cấp cột thực tế từ lần chạy (Actual Run Transformations)
              </span>
            </div>
            <p className="mt-1 leading-relaxed text-blue-800">
              Minh chứng dòng chảy cấp trường dữ liệu: Cột thô từ Bronze được biến đổi qua các quy tắc nghiệp vụ và pháp lý (Luật 91/2025/QH15, GDPR, CCPA, IFRS 15) để sinh ra bản ghi an toàn tại bảng Silver.
            </p>
          </div>

          <Card className="overflow-hidden">
            <div className="border-b border-slate-100 bg-slate-50/70 px-4 py-3 text-xs font-bold text-slate-700">
              Bảng ánh xạ nguồn gốc cấp cột (Dataset: {selectedDataset})
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/40 text-[11px] font-bold text-slate-500">
                    <th className="px-4 py-3">Cột nguồn (Bronze)</th>
                    <th className="px-4 py-3">Cơ sở pháp lý & Chuẩn</th>
                    <th className="px-4 py-3">Phép xử lý (Treatment)</th>
                    <th className="px-4 py-3">Cột đích (Silver)</th>
                    <th className="px-4 py-3">Mẫu dữ liệu Trước ➔ Sau (Thực tế)</th>
                    <th className="px-4 py-3 text-right">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {columnLineage.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3.5">
                        <div className="font-mono font-bold text-slate-900">{item.source_column}</div>
                        <div className="text-[10px] text-slate-400">{item.source_type}</div>
                      </td>
                      <td className="px-4 py-3.5 text-slate-700">
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium">
                          {item.legal_basis}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs font-semibold text-blue-700">
                          {item.treatment_operation}
                        </span>
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">{item.transformation_type}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="font-mono font-bold text-emerald-800">{item.target_column}</div>
                        <div className="text-[10px] text-slate-400">{item.target_type}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1.5 font-mono text-xs">
                          <span className="text-slate-500 line-through">{item.sample_before}</span>
                          <ArrowRight className="size-3 text-slate-400" />
                          <span className="font-bold text-emerald-700">{item.sample_after}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700">
                          <span className="size-1 rounded-full bg-emerald-500" />
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Node Inspection Slide-over Drawer */}
      <LineageNodeDrawer
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
      />
    </div>
  );
}
