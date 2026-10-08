'use client';
import { useEffect, useState, useMemo, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
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
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  LocateFixed,
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
  const { runId: pathRunId } = useParams<{ runId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialRunId = searchParams.get('run_id') || pathRunId || '';
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
  const [graphError, setGraphError] = useState<string | null>(null);
  const [columnError, setColumnError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  const graphContainerRef = useRef<HTMLDivElement>(null);

  // Load status and runs list on mount
  useEffect(() => {
    apiBridge.fetchLineageStatus().then(setStatus).catch(() => {});
    apiBridge.fetchLineageRuns().then(setRunsList).catch(() => {});
  }, []);

  // Load graph and column lineage when dataset or run changes
  const loadLineageData = async () => {
    setIsLoading(true);
    setGraphError(null);
    setColumnError(null);
    const [graphResult, columnResult] = await Promise.allSettled([
      apiBridge.fetchLineageGraph(selectedDataset, selectedRunId || undefined),
      apiBridge.fetchColumnLineage(selectedDataset, selectedRunId || undefined),
    ]);
    if (graphResult.status === 'fulfilled') setGraphData(graphResult.value);
    else {
      setGraphData(null);
      setGraphError(graphResult.reason instanceof Error ? graphResult.reason.message : 'Không thể tải sơ đồ dòng dữ liệu.');
    }
    if (columnResult.status === 'fulfilled') setColumnLineage(columnResult.value);
    else {
      setColumnLineage([]);
      setColumnError(columnResult.reason instanceof Error ? columnResult.reason.message : 'Không thể tải lineage cấp cột.');
    }
    setIsLoading(false);
  };

  useEffect(() => {
    loadLineageData();
  }, [selectedDataset, selectedRunId]);

  useEffect(() => {
    if (pathRunId) setSelectedRunId(pathRunId);
  }, [pathRunId]);

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

  const graphLayout = useMemo(() => {
    const nodeWidth = 210;
    const nodeHeight = 82;
    const columnGap = 100;
    const rowGap = 28;
    const padding = 56;
    const maxRows = Math.max(1, ...stages.map(([, nodes]) => nodes.length));
    const width = Math.max(1000, padding * 2 + stages.length * nodeWidth + Math.max(0, stages.length - 1) * columnGap);
    const height = Math.max(360, padding * 2 + maxRows * nodeHeight + Math.max(0, maxRows - 1) * rowGap);
    const positions = new Map<string, { x: number; y: number }>();
    stages.forEach(([, nodes], columnIndex) => {
      const stackHeight = nodes.length * nodeHeight + Math.max(0, nodes.length - 1) * rowGap;
      nodes.forEach((node, rowIndex) => positions.set(node.id, {
        x: padding + columnIndex * (nodeWidth + columnGap),
        y: (height - stackHeight) / 2 + rowIndex * (nodeHeight + rowGap),
      }));
    });
    return { nodeWidth, nodeHeight, width, height, positions };
  }, [stages]);

  const matchesSearch = (node: LineageNode) => {
    const query = searchQuery.trim().toLowerCase();
    return !query || [node.id, node.name, node.label, node.layer, node.description]
      .some((value) => value?.toLowerCase().includes(query));
  };

  const fitGraph = () => {
    const container = graphContainerRef.current;
    if (!container) return;
    const availableWidth = Math.max(1, container.clientWidth - 32);
    const availableHeight = Math.max(1, container.clientHeight - 32);
    const fittedZoom = Math.min(1.8, Math.max(0.5,
      Math.min(availableWidth / graphLayout.width, availableHeight / graphLayout.height),
    ));
    setZoom(fittedZoom);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      container.scrollTo({
        left: Math.max(0, (container.scrollWidth - container.clientWidth) / 2),
        top: Math.max(0, (container.scrollHeight - container.clientHeight) / 2),
        behavior: 'smooth',
      });
    }));
  };

  const toggleFullscreen = async () => {
    const element = graphContainerRef.current;
    if (!element) return;
    if (document.fullscreenElement) await document.exitFullscreen();
    else await element.requestFullscreen();
  };

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
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800" title={status?.modeDescription}>
              <span className="size-2 animate-pulse rounded-full bg-emerald-500" />
              PostgreSQL Catalog Lineage (Bảo chứng 3 Làn)
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            Dòng Dữ Liệu & Nguồn Gốc (Data Lineage)
          </h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Chuẩn OpenLineage 1.0 truy vết toàn diện: Nguồn thô ➔ Bronze ➔ Đánh giá 3 Làn ➔ Silver / Quarantine ➔ Ký số IPO
          </p>
        </div>

        {/* Actions */}
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
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-xs text-slate-600 backdrop-blur-xs lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-2">
              <Info className="size-4 shrink-0 text-slate-400" />
              <span>
                Nguồn đồ thị: <strong className="text-emerald-700">
                  PostgreSQL Catalog Lineage (Bảo chứng 3 Làn)
                </strong>. Kéo thanh cuộn để di chuyển và chọn một node để xem chi tiết.
              </span>
            </div>
            <span className="shrink-0 font-mono text-[11px] text-slate-400">
              {graphData?.totalNodes || 0} nodes • {graphData?.totalEdges || 0} edges
            </span>
          </div>

          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50/80 p-3">
              <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
                <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
                <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Tìm node, layer, dataset…" className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs outline-none focus:border-[#008b74]" />
              </div>
              <Button variant="outline" size="sm" onClick={() => setZoom((value) => Math.max(0.5, value - 0.1))} aria-label="Thu nhỏ"><ZoomOut className="size-3.5" /></Button>
              <span className="w-12 text-center text-[11px] font-semibold text-slate-500">{Math.round(zoom * 100)}%</span>
              <Button variant="outline" size="sm" onClick={() => setZoom((value) => Math.min(1.8, value + 0.1))} aria-label="Phóng to"><ZoomIn className="size-3.5" /></Button>
              <Button variant="outline" size="sm" onClick={fitGraph} className="gap-1.5 text-xs"><LocateFixed className="size-3.5" />Fit / Center</Button>
              <Button variant="outline" size="sm" onClick={toggleFullscreen} className="gap-1.5 text-xs"><Maximize2 className="size-3.5" />Toàn màn hình</Button>
            </div>

            <div ref={graphContainerRef} className="relative max-h-[680px] min-h-[420px] overflow-auto bg-[radial-gradient(circle_at_1px_1px,#cbd5e1_1px,transparent_0)] bg-[size:20px_20px] p-4 fullscreen:max-h-none fullscreen:bg-white">
              {isLoading && !graphData ? (
                <div className="flex min-h-[380px] items-center justify-center gap-2 text-sm text-slate-500"><RotateCw className="size-4 animate-spin" />Đang tải sơ đồ dòng dữ liệu…</div>
              ) : graphError ? (
                <div className="mx-auto mt-24 max-w-lg rounded-xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-800"><AlertOctagon className="mx-auto mb-2 size-6" /><p className="font-semibold">Không thể tải sơ đồ dòng dữ liệu</p><p className="mt-1 text-xs">{graphError}</p><Button variant="outline" size="sm" className="mt-4" onClick={loadLineageData}>Thử lại</Button></div>
              ) : !graphData?.nodes.length ? (
                <div className="flex min-h-[380px] flex-col items-center justify-center text-sm text-slate-500"><GitFork className="mb-2 size-7 text-slate-300" /><p className="font-semibold">Chưa có dữ liệu lineage</p><p className="mt-1 text-xs">Chọn dataset hoặc lần chạy khác để kiểm tra.</p></div>
              ) : (
                <svg width={graphLayout.width * zoom} height={graphLayout.height * zoom} viewBox={`0 0 ${graphLayout.width} ${graphLayout.height}`} className="block max-w-none" role="img" aria-label="Đồ thị dòng dữ liệu">
                  <defs><marker id="lineage-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#0f766e" /></marker></defs>
                  {graphData.edges.map((edge, index) => {
                    const from = graphLayout.positions.get(edge.from);
                    const to = graphLayout.positions.get(edge.to);
                    if (!from || !to) return null;
                    const startX = from.x + graphLayout.nodeWidth;
                    const startY = from.y + graphLayout.nodeHeight / 2;
                    const endX = to.x;
                    const endY = to.y + graphLayout.nodeHeight / 2;
                    const bend = (startX + endX) / 2;
                    return <path key={`${edge.from}-${edge.to}-${index}`} d={`M ${startX} ${startY} C ${bend} ${startY}, ${bend} ${endY}, ${endX} ${endY}`} fill="none" stroke="#0f766e" strokeWidth="2" strokeOpacity="0.65" markerEnd="url(#lineage-arrow)" />;
                  })}
                  {graphData.nodes.map((node) => {
                    const position = graphLayout.positions.get(node.id);
                    if (!position) return null;
                    const Icon = getNodeIcon(node.layer);
                    const matched = matchesSearch(node);
                    return <foreignObject key={node.id} x={position.x} y={position.y} width={graphLayout.nodeWidth} height={graphLayout.nodeHeight} className={matched ? 'opacity-100' : 'opacity-20'}>
                      <button type="button" onClick={() => setSelectedNode(node)} className={`flex h-full w-full items-start gap-3 rounded-xl border p-3 text-left shadow-sm transition-all ${getNodeColor(node.layer)} ${selectedNode?.id === node.id ? 'ring-2 ring-[#008b74]' : ''} ${searchQuery && matched ? 'ring-2 ring-amber-400' : ''}`}>
                        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/90"><Icon className="size-4" /></span>
                        <span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><span className="text-[9px] font-bold uppercase tracking-wider">{node.layer}</span><span className="truncate text-[9px] font-semibold text-emerald-700">{node.status}</span></span><span className="mt-1 block truncate text-xs font-bold text-slate-900" title={node.label || node.name}>{node.label || node.name}</span>{node.recordCount !== undefined && <span className="mt-1 block text-[10px]">{node.recordCount.toLocaleString('vi-VN')} dòng</span>}</span>
                      </button>
                    </foreignObject>;
                  })}
                </svg>
              )}
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

          {columnError && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
              <strong>Không thể tải lineage cấp cột.</strong> {columnError} Sơ đồ luồng vẫn khả dụng ở tab bên cạnh.
            </div>
          )}

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
                  {isLoading && columnLineage.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-12 text-center text-slate-500"><RotateCw className="mr-2 inline size-4 animate-spin" />Đang tải lineage cấp cột…</td></tr>
                  )}
                  {!isLoading && !columnError && columnLineage.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-12 text-center text-slate-500">Chưa có dữ liệu lineage cấp cột cho lựa chọn này.</td></tr>
                  )}
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
