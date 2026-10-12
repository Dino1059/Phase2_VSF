'use client';
import { useEffect, useState, useMemo, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  RotateCw,
  GitFork,
  Database,
  Layers,
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  Workflow,
  ZoomIn,
  ZoomOut,
  Maximize2,
  LocateFixed,
  Download,
  Copy,
  Check,
  Scale,
  TableProperties,
  FileText,
  ShieldAlert,
  Play
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  apiBridge,
  type LineageNode,
  type LineageRunItem,
  type UnifiedLineageResponse,
} from '@/lib/api-bridge';
import { StartRunModal } from '@/components/datatrust/pipeline/start-run-modal';
import { LineageNodeDrawer } from './lineage-node-drawer';

export function LineagePage() {
  const { id: paramId, runId: paramRunId } = useParams<{ id?: string; runId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const queryRunId = searchParams.get('run_id');
  const focusedColumn = searchParams.get('column') || '';
  const initialRunId = paramId || paramRunId || queryRunId || '';

  const [runsList, setRunsList] = useState<LineageRunItem[]>([]);
  const [effectiveRunId, setEffectiveRunId] = useState<string>(initialRunId || 'run_5b320bf9b22d');
  const [activeView, setActiveView] = useState<'graph' | 'diff'>('graph');
  const [lineageData, setLineageData] = useState<UnifiedLineageResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<LineageNode | null>(null);
  const [selectedColumn, setSelectedColumn] = useState<string>(focusedColumn);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  const [copiedHash, setCopiedHash] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [showStartModal, setShowStartModal] = useState(false);
  const graphContainerRef = useRef<HTMLDivElement>(null);

  // Fetch list of recent runs
  useEffect(() => {
    apiBridge.fetchLineageRuns().then((list) => {
      if (list && list.length > 0) {
        setRunsList(list);
        if (!initialRunId) {
          setEffectiveRunId(list[0].runId);
        }
      }
    }).catch(() => {});
  }, [initialRunId]);

  // Sync effectiveRunId when params change
  useEffect(() => {
    if (initialRunId) {
      setEffectiveRunId(initialRunId);
    }
  }, [initialRunId]);

  // Load Run Lineage
  const loadLineage = async () => {
    if (!effectiveRunId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiBridge.fetchRunLineage(effectiveRunId, selectedColumn || undefined);
      setLineageData(data);
    } catch (err: any) {
      setError(err.message || 'Không thể tải phả hệ dữ liệu của lần chạy.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLineage();
  }, [effectiveRunId, selectedColumn]);

  // Compute Upstream and Downstream reachable nodes for selectedNode
  const { upstreamNodes, downstreamNodes } = useMemo(() => {
    if (!selectedNode || !lineageData?.edges) {
      return { upstreamNodes: new Set<string>(), downstreamNodes: new Set<string>() };
    }

    const adjUp = new Map<string, string[]>();
    const adjDown = new Map<string, string[]>();

    lineageData.edges.forEach((e) => {
      if (!adjDown.has(e.from)) adjDown.set(e.from, []);
      adjDown.get(e.from)!.push(e.to);

      if (!adjUp.has(e.to)) adjUp.set(e.to, []);
      adjUp.get(e.to)!.push(e.from);
    });

    // BFS Upstream
    const upSet = new Set<string>();
    const qUp = [selectedNode.id];
    while (qUp.length > 0) {
      const curr = qUp.shift()!;
      (adjUp.get(curr) || []).forEach((prev) => {
        if (!upSet.has(prev)) {
          upSet.add(prev);
          qUp.push(prev);
        }
      });
    }

    // BFS Downstream
    const downSet = new Set<string>();
    const qDown = [selectedNode.id];
    while (qDown.length > 0) {
      const curr = qDown.shift()!;
      (adjDown.get(curr) || []).forEach((nxt) => {
        if (!downSet.has(nxt)) {
          downSet.add(nxt);
          qDown.push(nxt);
        }
      });
    }

    return { upstreamNodes: upSet, downstreamNodes: downSet };
  }, [selectedNode, lineageData]);

  // Group nodes by stage for visual layout
  const stages = useMemo(() => {
    if (!lineageData?.nodes) return [];
    const map = new Map<number, LineageNode[]>();
    lineageData.nodes.forEach((n) => {
      const s = n.stage || 1;
      if (!map.has(s)) map.set(s, []);
      map.get(s)!.push(n);
    });
    return Array.from(map.entries()).sort(([a], [b]) => a - b);
  }, [lineageData]);

  const graphLayout = useMemo(() => {
    const nodeWidth = 210;
    const nodeHeight = 84;
    const columnGap = 96;
    const rowGap = 28;
    const padding = 48;
    const maxRows = Math.max(1, ...stages.map(([, nodes]) => nodes.length));
    const width = Math.max(1100, padding * 2 + stages.length * nodeWidth + Math.max(0, stages.length - 1) * columnGap);
    const height = Math.max(400, padding * 2 + maxRows * nodeHeight + Math.max(0, maxRows - 1) * rowGap);
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

  const fitGraph = () => {
    const container = graphContainerRef.current;
    if (!container) return;
    const availableWidth = Math.max(1, container.clientWidth - 32);
    const availableHeight = Math.max(1, container.clientHeight - 32);
    const fittedZoom = Math.min(1.8, Math.max(0.4,
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

  const copyEvidenceHash = (hash?: string) => {
    if (!hash) return;
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleExportOpenLineage = async () => {
    setIsExporting(true);
    try {
      const json = await apiBridge.exportRunOpenLineage(effectiveRunId);
      const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `openlineage-${effectiveRunId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Xuất OpenLineage thất bại: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const getNodeColor = (node: LineageNode) => {
    const isSelected = selectedNode?.id === node.id;
    const isUpstream = upstreamNodes.has(node.id);
    const isDownstream = downstreamNodes.has(node.id);

    if (isSelected) return 'border-teal-500 bg-teal-50 text-teal-950 ring-2 ring-teal-500 shadow-md';
    if (isUpstream) return 'border-sky-400 bg-sky-50 text-sky-950 ring-1 ring-sky-400 shadow-xs';
    if (isDownstream) return 'border-amber-400 bg-amber-50 text-amber-950 ring-1 ring-amber-400 shadow-xs';

    if (selectedNode) return 'border-slate-200 bg-slate-50/50 text-slate-400 opacity-40';

    switch (node.layer) {
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
    <div className="page-enter mx-auto max-w-[1600px] space-y-4 pb-12">
          {/* Header & Control Bar */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-teal-800 border border-teal-200">
                    <Workflow className="size-3 text-teal-600" />
                    Workspace Phả hệ Lần chạy
                  </span>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                    COMPLETED
                  </span>
                </div>

                {/* Run Switcher Dropdown */}
                <div className="flex items-center gap-2 flex-wrap pt-0.5">
                  <span className="text-xs font-semibold text-slate-500">Mã Lần chạy:</span>
                  <select
                    value={effectiveRunId}
                    onChange={(e) => navigate(`/runs/${e.target.value}`)}
                    className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-mono font-bold text-slate-900 shadow-2xs focus:border-teal-600 focus:outline-hidden cursor-pointer"
                  >
                    {runsList.length > 0 ? (
                      runsList.map((r) => (
                        <option key={r.runId} value={r.runId}>
                          {r.runId} ({r.datasetId} · {new Date(r.createdAt).toLocaleTimeString('vi-VN')})
                        </option>
                      ))
                    ) : (
                      <option value={effectiveRunId}>{effectiveRunId}</option>
                    )}
                  </select>
                  <span className="text-xs text-slate-400 font-mono">
                    Dataset: <strong className="text-slate-800">{lineageData?.datasetId || 'ride_hailing_xanh_sm_trips'}</strong>
                  </span>
                </div>
              </div>

              {/* Header Action Buttons */}
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  onClick={() => navigate(`/runs/${effectiveRunId}/results`)}
                  className="bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-bold gap-1.5 shadow-xs"
                >
                  <FileText className="size-3.5" />
                  <span>Xem KPIs</span>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate(`/runs/${effectiveRunId}/findings`)}
                  className="gap-1.5 text-xs font-semibold border-slate-200 text-amber-700 hover:bg-amber-50 shadow-2xs"
                >
                  <ShieldAlert className="size-3.5 text-amber-600" />
                  <span>Findings ({lineageData?.metrics?.quarantineCount || 0})</span>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowStartModal(true)}
                  className="gap-1.5 text-xs font-semibold border-slate-200 text-slate-700 hover:bg-slate-50 shadow-2xs"
                >
                  <Play className="size-3.5 text-teal-600" />
                  <span>Chạy mới</span>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportOpenLineage}
                  disabled={isExporting}
                  className="gap-1.5 text-xs font-semibold border-slate-200 text-slate-700 hover:bg-slate-50 shadow-2xs"
                >
                  <Download className={`size-3.5 ${isExporting ? 'animate-bounce' : ''}`} />
                  <span>OpenLineage 1.0</span>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadLineage}
                  disabled={isLoading}
                  className="gap-1.5 text-xs border-slate-200 text-slate-700 hover:bg-slate-50 shadow-2xs"
                >
                  <RotateCw className={`size-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                  <span>Làm mới</span>
                </Button>
              </div>
            </div>

            {/* Evidence & Metrics Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-slate-500">
                  Quét thô: <strong className="text-slate-800 font-mono">{lineageData?.metrics?.scannedCount?.toLocaleString() || 1000}</strong>
                </span>
                <span>•</span>
                <span className="text-emerald-700">
                  Silver (Đạt chuẩn): <strong className="font-mono">{lineageData?.metrics?.silverCount?.toLocaleString() || 965}</strong>
                </span>
                <span>•</span>
                <span className="text-rose-700">
                  Quarantine (Cách ly): <strong className="font-mono">{lineageData?.metrics?.quarantineCount?.toLocaleString() || 25}</strong>
                </span>
                <span>•</span>
                <span className="text-amber-700">
                  Warning: <strong className="font-mono">{lineageData?.metrics?.warningCount?.toLocaleString() || 10}</strong>
                </span>
              </div>

              {lineageData?.evidenceHash && (
                <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-500 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200">
                  <ShieldCheck className="size-3.5 text-teal-600" />
                  <span>Hash: {lineageData.evidenceHash.slice(0, 16)}…</span>
                  <button
                    onClick={() => copyEvidenceHash(lineageData.evidenceHash)}
                    className="text-slate-400 hover:text-slate-700 p-0.5 cursor-pointer"
                    title="Sao chép Evidence Hash"
                  >
                    {copiedHash ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* View Switcher & Toolbar */}
          <Card className="p-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {/* 2 Modes */}
              <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
                <button
                  onClick={() => setActiveView('graph')}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                    activeView === 'graph'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <GitFork className="size-3.5" />
                  Sơ đồ Thực thi (DAG Lineage)
                </button>
                <button
                  onClick={() => setActiveView('diff')}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                    activeView === 'diff'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <TableProperties className="size-3.5" />
                  So sánh Schema Diff & Cột ({lineageData?.schemaDiff?.length || 0})
                </button>
              </div>

              {/* Upstream / Downstream Trace Help Badge */}
              {selectedNode && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500 font-medium">Đang truy vết:</span>
                  <span className="font-bold font-mono text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200 truncate max-w-[180px]">
                    {selectedNode.name}
                  </span>
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="text-slate-400 hover:text-slate-700 text-xs font-bold underline cursor-pointer"
                  >
                    Bỏ chọn
                  </button>
                </div>
              )}
            </div>
          </Card>

          {/* VIEW 1: INTERACTIVE DAG LINEAGE */}
          {activeView === 'graph' && (
            <div className="relative rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden">
              {/* Controls bar */}
              <div className="absolute right-4 top-4 z-10 flex items-center gap-1.5 rounded-xl border border-slate-200/80 bg-white/95 p-1 shadow-md backdrop-blur-xs">
                <Button variant="ghost" size="icon" className="size-7" onClick={() => setZoom((z) => Math.min(2, z + 0.15))} title="Phóng to">
                  <ZoomIn className="size-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="size-7" onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))} title="Thu nhỏ">
                  <ZoomOut className="size-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="size-7" onClick={fitGraph} title="Vừa màn hình">
                  <LocateFixed className="size-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="size-7" onClick={toggleFullscreen} title="Toàn màn hình">
                  <Maximize2 className="size-3.5" />
                </Button>
              </div>

              {/* Canvas */}
              <div ref={graphContainerRef} className="h-[560px] overflow-auto bg-slate-50/50 p-6 relative">
                {isLoading ? (
                  <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-500">
                    <RotateCw className="size-4 animate-spin text-teal-600" />
                    Đang nạp phả hệ dữ liệu thực tế của lần chạy...
                  </div>
                ) : error ? (
                  <div className="mx-auto mt-24 max-w-lg rounded-xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-800">
                    <AlertOctagon className="mx-auto mb-2 size-6" />
                    <p className="font-semibold">Không thể tải phả hệ</p>
                    <p className="mt-1 text-xs">{error}</p>
                    <Button variant="outline" size="sm" className="mt-4" onClick={loadLineage}>Thử lại</Button>
                  </div>
                ) : (
                  <svg
                    width={graphLayout.width * zoom}
                    height={graphLayout.height * zoom}
                    viewBox={`0 0 ${graphLayout.width} ${graphLayout.height}`}
                    className="block max-w-none"
                    role="img"
                    aria-label="Đồ thị phả hệ dòng dữ liệu thực tế"
                  >
                    <defs>
                      <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#94a3b8" />
                      </marker>
                      <marker id="arrow-active" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#0d9488" />
                      </marker>
                    </defs>

                    {/* Stage background guides */}
                    {stages.map(([stageNum, nodes]) => {
                      const firstNodePos = graphLayout.positions.get(nodes[0].id);
                      if (!firstNodePos) return null;
                      return (
                        <g key={`stage-bg-${stageNum}`}>
                          <rect
                            x={firstNodePos.x - 16}
                            y={16}
                            width={graphLayout.nodeWidth + 32}
                            height={graphLayout.height - 32}
                            rx="14"
                            fill="#f8fafc"
                            stroke="#e2e8f0"
                            strokeDasharray="4 4"
                          />
                          <text
                            x={firstNodePos.x + graphLayout.nodeWidth / 2}
                            y={36}
                            textAnchor="middle"
                            className="fill-slate-400 font-sans text-[10px] font-bold uppercase tracking-wider"
                          >
                            Chặng {stageNum}
                          </text>
                        </g>
                      );
                    })}

                    {/* Edges */}
                    {lineageData?.edges.map((edge, idx) => {
                      const fromPos = graphLayout.positions.get(edge.from);
                      const toPos = graphLayout.positions.get(edge.to);
                      if (!fromPos || !toPos) return null;

                      const startX = fromPos.x + graphLayout.nodeWidth;
                      const startY = fromPos.y + graphLayout.nodeHeight / 2;
                      const endX = toPos.x;
                      const endY = toPos.y + graphLayout.nodeHeight / 2;
                      const c1X = startX + (endX - startX) * 0.45;
                      const c2X = endX - (endX - startX) * 0.45;
                      const d = `M ${startX} ${startY} C ${c1X} ${startY}, ${c2X} ${endY}, ${endX} ${endY}`;

                      const isEdgeUpstream = selectedNode && upstreamNodes.has(edge.from) && (upstreamNodes.has(edge.to) || edge.to === selectedNode.id);
                      const isEdgeDownstream = selectedNode && (downstreamNodes.has(edge.to) || edge.from === selectedNode.id) && downstreamNodes.has(edge.to);
                      const isHighlighted = isEdgeUpstream || isEdgeDownstream;

                      return (
                        <path
                          key={`edge-${idx}`}
                          d={d}
                          fill="none"
                          stroke={isHighlighted ? '#0d9488' : selectedNode ? '#cbd5e1' : '#94a3b8'}
                          strokeWidth={isHighlighted ? 2.5 : 1.5}
                          strokeOpacity={selectedNode && !isHighlighted ? 0.3 : 0.8}
                          markerEnd={isHighlighted ? 'url(#arrow-active)' : 'url(#arrow)'}
                        />
                      );
                    })}

                    {/* Nodes */}
                    {lineageData?.nodes.map((node) => {
                      const pos = graphLayout.positions.get(node.id);
                      if (!pos) return null;
                      const Icon = getNodeIcon(node.layer);
                      const colorClass = getNodeColor(node);

                      return (
                        <foreignObject
                          key={node.id}
                          x={pos.x}
                          y={pos.y}
                          width={graphLayout.nodeWidth}
                          height={graphLayout.nodeHeight}
                        >
                          <div
                            onClick={() => setSelectedNode(node)}
                            className={`group h-full w-full cursor-pointer rounded-xl border p-2.5 transition-all ${colorClass}`}
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider">
                                <Icon className="size-3 shrink-0" />
                                <span className="truncate">{node.layer}</span>
                              </span>
                              {node.duration !== undefined ? (
                                <span className="text-[10px] font-mono text-slate-500 font-semibold">{node.duration}s</span>
                              ) : node.recordCount !== undefined ? (
                                <span className="text-[10px] font-mono font-bold">{node.recordCount.toLocaleString()}</span>
                              ) : null}
                            </div>
                            <div className="mt-1 font-bold text-xs truncate" title={node.name}>
                              {node.label || node.name}
                            </div>
                            <div className="text-[10px] text-slate-500 truncate" title={node.description}>
                              {node.description || 'Chặng xử lý phả hệ'}
                            </div>
                          </div>
                        </foreignObject>
                      );
                    })}
                  </svg>
                )}
              </div>
            </div>
          )}

          {/* VIEW 2: SCHEMA DIFF & COLUMN LINEAGE MATRIX */}
          {activeView === 'diff' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                      <Scale className="size-4 text-teal-600" />
                      <span>Bảng Đối Chiếu Schema Diff (Bronze vs Silver)</span>
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Phân loại toàn bộ các trường dữ liệu trước và sau khi thực thi 3-Lane Compliance Engine
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Tìm kiếm cột:</span>
                    <input
                      type="text"
                      placeholder="Lọc tên cột..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="h-8 rounded-lg border border-slate-200 px-2.5 text-xs focus:border-teal-600 focus:outline-hidden"
                    />
                  </div>
                </div>

                {/* Diff Table */}
                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-[11px] font-bold text-slate-600 uppercase tracking-wider border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-3">Cột Bronze (Nguồn)</th>
                        <th className="px-3 py-3">Kiểu Bronze</th>
                        <th className="px-4 py-3">Cột Silver (Đích)</th>
                        <th className="px-3 py-3">Kiểu Silver</th>
                        <th className="px-3 py-3">Phân Loại Diff</th>
                        <th className="px-4 py-3">Quy Tắc & Căn Cứ Pháp Lý</th>
                        <th className="px-3 py-3 text-right">Thao Tác</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(lineageData?.schemaDiff || [])
                        .filter((item) => {
                          const q = searchQuery.toLowerCase();
                          return !q || item.sourceColumn.toLowerCase().includes(q) || item.targetColumn.toLowerCase().includes(q);
                        })
                        .map((item, idx) => {
                          const isTransformed = item.diffType === 'TRANSFORMED';
                          const isQuarantined = item.diffType === 'QUARANTINED';
                          const isAdded = item.diffType === 'ADDED';
                          const isSelected = selectedColumn === item.sourceColumn;

                          return (
                            <tr
                              key={`diff-${idx}`}
                              className={`hover:bg-slate-50/80 transition-colors ${
                                isSelected ? 'bg-teal-50/60 font-semibold' : ''
                              }`}
                            >
                              <td className="px-4 py-3 font-mono font-medium text-slate-900">
                                {item.sourceColumn}
                              </td>
                              <td className="px-3 py-3 font-mono text-[11px] text-slate-500">
                                {item.sourceType}
                              </td>
                              <td className="px-4 py-3 font-mono font-medium text-slate-900">
                                {item.targetColumn}
                              </td>
                              <td className="px-3 py-3 font-mono text-[11px] text-slate-500">
                                {item.targetType}
                              </td>
                              <td className="px-3 py-3">
                                <span
                                  className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                    isTransformed
                                      ? 'bg-teal-50 text-teal-700 border border-teal-200'
                                      : isQuarantined
                                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                      : isAdded
                                      ? 'bg-sky-50 text-sky-700 border border-sky-200'
                                      : 'bg-slate-100 text-slate-600'
                                  }`}
                                >
                                  {item.diffType}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-[11px] text-slate-600">
                                {item.treatmentOperation && (
                                  <div className="font-mono text-teal-800 font-semibold">{item.treatmentOperation}</div>
                                )}
                                <div className="text-slate-500">{item.legalBasis || '—'}</div>
                              </td>
                              <td className="px-3 py-3 text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setSelectedColumn(isSelected ? '' : item.sourceColumn);
                                    setActiveView('graph');
                                  }}
                                  className="text-[11px] h-7 px-2 text-teal-700 hover:bg-teal-50 cursor-pointer"
                                >
                                  Truy vết
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

      {/* Node Inspection Drawer */}
      <LineageNodeDrawer
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
      />

      {/* Start Run Modal */}
      <StartRunModal
        isOpen={showStartModal}
        onClose={() => setShowStartModal(false)}
        onRunStarted={(newRunId) => {
          setShowStartModal(false);
          if (newRunId) {
            navigate(`/runs/${newRunId}`);
          }
        }}
      />
    </div>
  );
}
