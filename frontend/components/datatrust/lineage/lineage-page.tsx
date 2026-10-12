'use client';
import { useEffect, useState, useMemo, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  RotateCw,
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
  Play
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  apiBridge,
  type LineageNode,
  type LineageRunItem,
  type UnifiedLineageResponse,
} from '@/lib/api-bridge';
import { StartRunModal } from '@/components/datatrust/pipeline/start-run-modal';
import { LineageNodeDrawer } from './lineage-node-drawer';
import { buildLineageLayout } from './lineage-layout';

export function LineagePage() {
  const { id: paramId, runId: paramRunId } = useParams<{ id?: string; runId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const queryRunId = searchParams.get('run_id');
  const focusedColumn = searchParams.get('column') || '';
  const revisionParam = searchParams.get('revision');
  const revision = revisionParam && Number.isInteger(Number(revisionParam)) ? Number(revisionParam) : undefined;
  const initialRunId = paramId || paramRunId || queryRunId || '';

  const [runsList, setRunsList] = useState<LineageRunItem[]>([]);
  const [effectiveRunId, setEffectiveRunId] = useState<string>(initialRunId);
  const [lineageData, setLineageData] = useState<UnifiedLineageResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<LineageNode | null>(null);
  const selectedColumn = focusedColumn;
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    }).catch((err: Error) => {
      setError(err.message || 'Không thể nạp danh sách lineage.');
    });
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
      const data = await apiBridge.fetchRunLineage(effectiveRunId, selectedColumn || undefined, revision);
      setLineageData(data);
    } catch (err: any) {
      setError(err.message || 'Không thể tải phả hệ dữ liệu của lần chạy.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLineage();
  }, [effectiveRunId, selectedColumn, revision]);

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

  const graphLayout = useMemo(() => buildLineageLayout(
    lineageData?.nodes || [],
    lineageData?.edges || [],
  ), [lineageData]);
  const stages = graphLayout.stages;

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
      const json = await apiBridge.exportRunOpenLineage(effectiveRunId, revision);
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
    const executionStatus = node.status.toUpperCase();
    const isSelected = selectedNode?.id === node.id;
    const isUpstream = upstreamNodes.has(node.id);
    const isDownstream = downstreamNodes.has(node.id);

    if (isSelected) return 'border-teal-500 bg-teal-50 text-teal-950 ring-2 ring-teal-500 shadow-md';
    if (isUpstream) return 'border-sky-400 bg-sky-50 text-sky-950 ring-1 ring-sky-400 shadow-xs';
    if (isDownstream) return 'border-amber-400 bg-amber-50 text-amber-950 ring-1 ring-amber-400 shadow-xs';

    if (selectedNode) return 'border-slate-200 bg-slate-50/50 text-slate-400 opacity-40';
    if (executionStatus === 'FAILED') return 'border-rose-400 bg-rose-50 text-rose-900';
    if (executionStatus === 'SKIPPED') return 'border-slate-300 bg-slate-100 text-slate-500 border-dashed';
    if (executionStatus === 'RUNNING') return 'border-blue-400 bg-blue-50 text-blue-900';
    if (node.type !== 'dataset' && executionStatus === 'SUCCESS') return 'border-emerald-400 bg-emerald-50 text-emerald-950';

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

  const statusBadge = (status?: string) => {
    const tone = status === 'COMPLETE' || status === 'FINALIZED'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : status === 'UNAVAILABLE'
      ? 'border-rose-200 bg-rose-50 text-rose-700'
      : 'border-amber-200 bg-amber-50 text-amber-700';
    return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${tone}`}>{status || '—'}</span>;
  };

  const stageLabel = (stage: number) => ({
    1: 'Nguồn',
    2: 'Ingestion & Profiling',
    3: 'Kiểm tra',
    4: 'Phân tuyến',
    5: 'Evidence',
  }[stage] || `Bước ${stage}`);

  const nodeDisplayName = (node: LineageNode) => {
    if (node.type === 'dataset') return node.label || node.name;
    const task = (node.taskId || node.name).toLowerCase();
    if (task.includes('lane_a')) return 'Kiểm tra Lane A';
    if (task.includes('lane_b')) return 'Kiểm tra Lane B';
    if (task.includes('lane_c')) return 'Phân tuyến dữ liệu';
    if (task.includes('task_1_')) return 'Nạp dữ liệu';
    if (task.includes('task_2_')) return 'Lập hồ sơ dữ liệu';
    if (task.includes('task_4_')) return 'Phát hành Evidence';
    return node.label || node.name;
  };

  const nodeStatusDot = (node: LineageNode) => {
    const status = node.status.toUpperCase();
    if (node.type === 'dataset') return status === 'OBSERVED' ? 'bg-teal-500' : 'bg-sky-400';
    if (status === 'SUCCESS') return 'bg-emerald-500';
    if (status === 'FAILED') return 'bg-rose-500';
    if (status === 'SKIPPED') return 'bg-slate-400';
    if (status === 'RUNNING') return 'bg-blue-500';
    return 'bg-amber-400';
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
                  <span className="text-[10px] text-slate-500">Vòng đời</span>
                  {statusBadge(lineageData?.lifecycleStatus || lineageData?.snapshotStatus)}
                  <span className="text-[10px] text-slate-500">Chất lượng</span>
                  {statusBadge(lineageData?.dataStatus)}
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
                          {r.runId}{r.datasetId ? ` (${r.datasetId})` : ''}{(r.createdAt || r.asOf) ? ` · ${new Date((r.createdAt || r.asOf)!).toLocaleTimeString('vi-VN')}` : ''}
                        </option>
                      ))
                    ) : effectiveRunId ? (
                      <option value={effectiveRunId}>{effectiveRunId}</option>
                    ) : (
                      <option value="">Chưa có run</option>
                    )}
                  </select>
                  {lineageData?.datasetId && <span className="text-xs text-slate-400 font-mono">Dataset: <strong className="text-slate-800">{lineageData.datasetId}</strong></span>}
                  {lineageData?.revision !== undefined && <span className="text-xs text-slate-500 font-mono">Revision {lineageData.revision}{lineageData.dagVersion ? ` · DAG ${lineageData.dagVersion}` : ''}{lineageData.asOf ? ` · ${new Date(lineageData.asOf).toLocaleString('vi-VN')}` : ''}</span>}
                </div>
              </div>

              {/* Header Action Buttons */}
              <div className="flex items-center gap-2 flex-wrap">
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
                  disabled={isExporting || !effectiveRunId || lineageData?.dataStatus === 'UNAVAILABLE'}
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
              <div className="space-y-1">
                {!!lineageData?.missingMetadata?.length && (
                  <div className="text-amber-700"><strong>Metadata chưa thu thập:</strong> {lineageData.missingMetadata.join(', ')}</div>
                )}
                {!!lineageData?.sourceErrors?.length && (
                  <div className="text-rose-700"><strong>Lỗi nguồn dữ liệu:</strong> {lineageData.sourceErrors.map((item) => `${item.source}: ${item.message}`).join('; ')}</div>
                )}
                {!!lineageData?.sources?.length && (
                  <div className="flex flex-wrap items-center gap-1.5 text-slate-500">
                    <strong>Nguồn:</strong>
                    {lineageData.sources.map((item) => <span key={item.source} className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${item.status === 'AVAILABLE' ? 'border-emerald-200 text-emerald-700' : 'border-slate-200 text-slate-500'}`}>{item.source}: {item.status}</span>)}
                  </div>
                )}
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

          {/* Upstream / Downstream Trace Help Badge */}
          {selectedNode && (
            <div className="flex items-center justify-between rounded-xl border border-teal-200 bg-teal-50/70 p-2.5 px-4 text-xs shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">Đang truy vết:</span>
                <span className="font-bold font-mono text-teal-900 bg-white px-2 py-0.5 rounded border border-teal-300 truncate max-w-[280px]">
                  {selectedNode.name}
                </span>
                <span className="text-[11px] text-teal-700 hidden sm:inline">
                  (Khối xanh: Thượng nguồn · Khối hổ phách: Hạ nguồn)
                </span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-teal-700 hover:text-teal-900 text-xs font-bold underline cursor-pointer"
              >
                Bỏ chọn
              </button>
            </div>
          )}

          {/* INTERACTIVE DAG LINEAGE */}
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

              <div className="flex min-h-16 flex-wrap items-center gap-x-5 gap-y-1 border-b border-slate-200 bg-slate-950 px-5 py-3 pr-48 text-[11px] text-slate-300">
                <span><strong className="text-white">Run</strong> <span className="font-mono">{lineageData?.runId || effectiveRunId || '—'}</span></span>
                <span><strong className="text-white">DAG version</strong> <span className="font-mono">{lineageData?.dagVersion || '—'}</span></span>
                <span><strong className="text-white">Snapshot</strong> {lineageData?.lifecycleStatus || lineageData?.snapshotStatus || '—'}{lineageData?.revision !== undefined ? ` · r${lineageData.revision}` : ''}</span>
                <span><strong className="text-white">Metadata</strong> {lineageData?.dataStatus || '—'}</span>
              </div>

              {/* Canvas */}
              <div ref={graphContainerRef} className="h-[560px] overflow-auto bg-slate-50/50 p-6 relative">
                {!effectiveRunId ? (
                  <div className="flex h-full items-center justify-center text-sm text-slate-500">Chưa có lần chạy để hiển thị lineage.</div>
                ) : isLoading ? (
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
                ) : lineageData?.dataStatus === 'UNAVAILABLE' || !lineageData?.nodes?.length ? (
                  <div className="flex h-full flex-col items-center justify-center text-center text-sm text-slate-600">
                    <AlertTriangle className="mb-2 size-7 text-amber-500" />
                    <strong>Lineage chưa khả dụng</strong>
                    <span className="mt-1 max-w-md text-xs text-slate-500">Không đủ metadata đã xác minh để dựng graph cho run này.</span>
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
                      <marker id="arrow-dependency" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#94a3b8" />
                      </marker>
                      <marker id="arrow-observed" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#0d9488" />
                      </marker>
                      <marker id="arrow-declared" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#0284c7" />
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
                            {stageLabel(stageNum)}
                          </text>
                        </g>
                      );
                    })}

                    {/* Edges */}
                    {graphLayout.routedEdges.map((edge) => {
                      const isEdgeUpstream = selectedNode && upstreamNodes.has(edge.from) && (upstreamNodes.has(edge.to) || edge.to === selectedNode.id);
                      const isEdgeDownstream = selectedNode && (downstreamNodes.has(edge.to) || edge.from === selectedNode.id) && downstreamNodes.has(edge.to);
                      const isHighlighted = isEdgeUpstream || isEdgeDownstream;
                      const isObserved = edge.relationType === 'OBSERVED';
                      const isDeclared = edge.relationType === 'DECLARED';
                      const edgeColor = isHighlighted ? '#0f766e' : selectedNode ? '#cbd5e1' : isObserved ? '#0d9488' : isDeclared ? '#0284c7' : '#94a3b8';
                      const marker = isHighlighted || isObserved ? 'url(#arrow-observed)' : isDeclared ? 'url(#arrow-declared)' : 'url(#arrow-dependency)';

                      return (
                        <path
                          key={edge.key}
                          d={edge.path}
                          fill="none"
                          stroke={edgeColor}
                          strokeWidth={isHighlighted ? 2.75 : isObserved ? 2.25 : 1.5}
                          strokeOpacity={selectedNode && !isHighlighted ? 0.25 : isObserved ? 0.9 : 0.65}
                          markerEnd={marker}
                          strokeDasharray={isDeclared ? '7 5' : undefined}
                        />
                      );
                    })}

                    {/* Nodes */}
                    {graphLayout.nodes.map((node) => {
                      const pos = graphLayout.positions.get(node.id);
                      if (!pos) return null;
                      const Icon = getNodeIcon(node.layer);
                      const colorClass = getNodeColor(node);
                      const fullTechnicalName = `${node.label || node.name}${node.mapIndex !== undefined && node.mapIndex >= 0 ? ` [${node.mapIndex}]` : ''}`;
                      const displayName = nodeDisplayName(node);
                      const isDataset = node.type === 'dataset';

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
                            title={fullTechnicalName}
                            aria-label={`${isDataset ? 'Dataset' : 'Task'}: ${fullTechnicalName}; trạng thái ${node.status}`}
                            className={`group h-full w-full cursor-pointer border p-2.5 transition-all ${isDataset ? 'rounded-[28px] border-2 px-4' : 'rounded-lg border-l-4'} ${colorClass}`}
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider">
                                <Icon className="size-3 shrink-0" />
                                <span className="truncate">{isDataset ? 'DATASET' : 'TASK'}</span>
                              </span>
                              {node.duration !== undefined ? (
                                <span className="text-[10px] font-mono text-slate-500 font-semibold">{node.duration}s</span>
                              ) : node.recordCount !== undefined ? (
                                <span className="text-[10px] font-mono font-bold">{node.recordCount.toLocaleString()}</span>
                              ) : null}
                            </div>
                            <div className="mt-1 flex items-center gap-2 font-bold text-xs">
                              <span className={`size-2 shrink-0 rounded-full ${nodeStatusDot(node)}`} />
                              <span className="truncate">{displayName}{node.mapIndex !== undefined && node.mapIndex >= 0 ? ` [${node.mapIndex}]` : ''}</span>
                            </div>
                            <div className="text-[10px] text-slate-500 truncate" title={node.description}>
                              {node.status}{node.finalTryNumber ? ` · try ${node.finalTryNumber}` : ''}
                            </div>
                          </div>
                        </foreignObject>
                      );
                    })}
                  </svg>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-200 bg-white px-5 py-3 text-[11px] text-slate-600">
                <strong className="text-slate-800">Chú giải</strong>
                <span className="flex items-center gap-2"><span className="w-8 border-t-2 border-slate-400" /> Dependency giữa task</span>
                <span className="flex items-center gap-2"><span className="w-8 border-t-[3px] border-teal-600" /> OBSERVED: đọc/ghi thực tế</span>
                <span className="flex items-center gap-2"><span className="w-8 border-t-2 border-dashed border-sky-600" /> DECLARED: khai báo trong DAG</span>
                <span className="flex items-center gap-2"><span className="h-4 w-7 rounded-[10px] border-2 border-teal-300 bg-teal-50" /> Dataset</span>
                <span className="flex items-center gap-2"><span className="h-4 w-7 rounded border border-l-4 border-emerald-400 bg-emerald-50" /> Task</span>
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-emerald-500" /> SUCCESS</span>
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-rose-500" /> FAILED</span>
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-slate-400" /> SKIPPED</span>
              </div>
            </div>

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
