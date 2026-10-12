import type { LineageEdge, LineageNode } from '@/lib/api-bridge';

export interface PositionedNode {
  x: number;
  y: number;
}

export interface RoutedEdge extends LineageEdge {
  key: string;
  path: string;
}

export interface LineageLayout {
  nodes: LineageNode[];
  edges: LineageEdge[];
  stages: Array<[number, LineageNode[]]>;
  positions: Map<string, PositionedNode>;
  routedEdges: RoutedEdge[];
  nodeWidth: number;
  nodeHeight: number;
  width: number;
  height: number;
}

const stableNodeCompare = (a: LineageNode, b: LineageNode) =>
  (a.name || a.id).localeCompare(b.name || b.id) || a.id.localeCompare(b.id);

const canonicalDatasetName = (node: LineageNode) => {
  const raw = String(node.name || node.label || node.id.replace(/^dataset:/, '')).trim();
  return raw.replace(/^airflow\./i, '');
};

/**
 * A non-mapped task has one useful visual identity. Merge its declaration into
 * its runtime node, while retaining the declaration node for mapped tasks so
 * the expanding instances still have a stable parent.
 */
export function normalizeLineageGraph(nodes: LineageNode[], edges: LineageEdge[]) {
  const datasetGroups = new Map<string, LineageNode[]>();
  nodes.forEach((node) => {
    if (node.type !== 'dataset') return;
    const canonical = canonicalDatasetName(node).toLowerCase();
    datasetGroups.set(canonical, [...(datasetGroups.get(canonical) || []), node]);
  });
  const datasetRemap = new Map<string, string>();
  const mergedDatasets = new Map<string, LineageNode>();
  datasetGroups.forEach((group, canonical) => {
    const preferred = group.find((node) => node.status?.toUpperCase() === 'OBSERVED') || group[0];
    const mergedId = `dataset:${canonical}`;
    group.forEach((node) => datasetRemap.set(node.id, mergedId));
    const metadataSources = group.map((node) => ({
      identifier: node.name || node.label || node.id.replace(/^dataset:/, ''),
      status: node.status,
    }));
    mergedDatasets.set(mergedId, {
      ...preferred,
      id: mergedId,
      name: canonical,
      label: canonical,
      status: group.some((node) => node.status?.toUpperCase() === 'OBSERVED') ? 'OBSERVED' : preferred.status,
      facets: { ...(preferred.facets || {}), metadataSources },
    });
  });

  const instances = new Map<string, LineageNode[]>();
  nodes.forEach((node) => {
    if (node.type !== 'job') return;
    const taskId = node.taskId || node.name;
    const current = instances.get(taskId) || [];
    current.push(node);
    instances.set(taskId, current);
  });

  const remap = new Map<string, string>(datasetRemap);
  nodes.forEach((node) => {
    if (node.type !== 'logicalJob') return;
    const taskId = node.taskId || node.name;
    const runtime = instances.get(taskId) || [];
    if (runtime.length === 1 && (runtime[0].mapIndex ?? -1) < 0) {
      remap.set(node.id, runtime[0].id);
    }
  });

  const normalizedNodes = [
    ...nodes.filter((node) => node.type !== 'dataset' && !remap.has(node.id)),
    ...mergedDatasets.values(),
  ]
    .sort(stableNodeCompare);
  const candidates = edges.flatMap((edge) => {
    const next = { ...edge, from: remap.get(edge.from) || edge.from, to: remap.get(edge.to) || edge.to };
    if (next.from === next.to) return [];
    return [next];
  });
  // When declared and observed evidence describe the same flow, draw one
  // observed edge. Source aliases remain available in the merged dataset.
  const observedPairs = new Set(candidates
    .filter((edge) => edge.relationType === 'OBSERVED')
    .map((edge) => `${edge.from}\u0000${edge.to}`));
  const seen = new Set<string>();
  const normalizedEdges = candidates.filter((edge) => {
    const pair = `${edge.from}\u0000${edge.to}`;
    if (edge.relationType === 'DECLARED' && observedPairs.has(pair)) return false;
    const key = `${pair}\u0000${edge.relationType || ''}\u0000${edge.direction || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return { nodes: normalizedNodes, edges: normalizedEdges };
}

function deriveRanks(nodes: LineageNode[], edges: LineageEdge[]) {
  const ids = new Set(nodes.map((node) => node.id));
  const dependencyEdges = edges.filter((edge) => edge.relationType !== 'INSTANCE_OF');
  const incoming = new Map<string, number>();
  const outgoing = new Map<string, string[]>();
  nodes.forEach((node) => { incoming.set(node.id, 0); outgoing.set(node.id, []); });
  dependencyEdges.forEach((edge) => {
    if (!ids.has(edge.from) || !ids.has(edge.to) || edge.from === edge.to) return;
    outgoing.get(edge.from)!.push(edge.to);
    incoming.set(edge.to, (incoming.get(edge.to) || 0) + 1);
  });
  const rank = new Map<string, number>();
  const queue = nodes.filter((node) => incoming.get(node.id) === 0).sort(stableNodeCompare);
  queue.forEach((node) => rank.set(node.id, 1));
  while (queue.length) {
    const node = queue.shift()!;
    for (const target of (outgoing.get(node.id) || []).sort()) {
      rank.set(target, Math.max(rank.get(target) || 1, (rank.get(node.id) || 1) + 1));
      incoming.set(target, (incoming.get(target) || 1) - 1);
      if (incoming.get(target) === 0) {
        const targetNode = nodes.find((candidate) => candidate.id === target)!;
        queue.push(targetNode);
        queue.sort(stableNodeCompare);
      }
    }
  }

  // Cycles or incomplete metadata should still spread across useful columns.
  nodes.forEach((node) => {
    if (!rank.has(node.id)) {
      const predecessors = dependencyEdges.filter((edge) => edge.to === node.id && rank.has(edge.from));
      rank.set(node.id, predecessors.length ? Math.max(...predecessors.map((edge) => rank.get(edge.from)! + 1)) : 1);
    }
  });

  // Backend stages are authoritative when supplied. A mapped runtime instance
  // belongs in its logical task's column; INSTANCE_OF is an association, not a
  // processing step in the DAG.
  nodes.forEach((node) => {
    if (Number.isInteger(node.stage) && node.stage! > 0) rank.set(node.id, node.stage!);
  });
  const logicalByTask = new Map<string, LineageNode>();
  nodes.forEach((node) => {
    if (node.type === 'logicalJob') logicalByTask.set(node.taskId || node.name, node);
  });
  const inheritedRuntime = new Set<string>();
  nodes.forEach((node) => {
    if (node.type !== 'job' || (node.mapIndex ?? -1) < 0) return;
    const logical = logicalByTask.get(node.taskId || node.name);
    if (!logical) return;
    rank.set(node.id, rank.get(logical.id) || 1);
    inheritedRuntime.add(node.id);
  });

  // Reflow derived dataset/other nodes after runtime inheritance. Explicit
  // backend stages and inherited mapped stages remain fixed.
  const fixed = new Set(nodes
    .filter((node) => (Number.isInteger(node.stage) && node.stage! > 0) || inheritedRuntime.has(node.id))
    .map((node) => node.id));
  for (let pass = 0; pass < nodes.length; pass += 1) {
    let changed = false;
    for (const edge of dependencyEdges) {
      if (fixed.has(edge.to)) continue;
      const next = (rank.get(edge.from) || 1) + 1;
      if (next > (rank.get(edge.to) || 1)) {
        rank.set(edge.to, next);
        changed = true;
      }
    }
    if (!changed) break;
  }
  return rank;
}

function orderByBarycenter(stages: LineageNode[][], edges: LineageEdge[]) {
  const order = new Map<string, number>();
  const updateOrder = () => stages.forEach((stage) => stage.forEach((node, index) => order.set(node.id, index)));
  updateOrder();
  for (let pass = 0; pass < 4; pass += 1) {
    for (let stageIndex = 1; stageIndex < stages.length; stageIndex += 1) {
      const prior = new Set(stages[stageIndex - 1].map((node) => node.id));
      stages[stageIndex].sort((a, b) => {
        const barycenter = (id: string) => {
          const positions = edges.filter((edge) => edge.to === id && prior.has(edge.from)).map((edge) => order.get(edge.from)!);
          return positions.length ? positions.reduce((sum, value) => sum + value, 0) / positions.length : Number.POSITIVE_INFINITY;
        };
        return barycenter(a.id) - barycenter(b.id) || stableNodeCompare(a, b);
      });
      updateOrder();
    }
    for (let stageIndex = stages.length - 2; stageIndex >= 0; stageIndex -= 1) {
      const next = new Set(stages[stageIndex + 1].map((node) => node.id));
      stages[stageIndex].sort((a, b) => {
        const barycenter = (id: string) => {
          const positions = edges.filter((edge) => edge.from === id && next.has(edge.to)).map((edge) => order.get(edge.to)!);
          return positions.length ? positions.reduce((sum, value) => sum + value, 0) / positions.length : Number.POSITIVE_INFINITY;
        };
        return barycenter(a.id) - barycenter(b.id) || stableNodeCompare(a, b);
      });
      updateOrder();
    }
  }
}

export function buildLineageLayout(rawNodes: LineageNode[], rawEdges: LineageEdge[]): LineageLayout {
  const { nodes, edges } = normalizeLineageGraph(rawNodes, rawEdges);
  const ranks = deriveRanks(nodes, edges);
  // Output datasets belong beside the task that produced them. This keeps the
  // audit trail local and avoids a forest of long lines into a terminal column.
  nodes.filter((node) => node.type === 'dataset').forEach((node) => {
    const producerRanks = edges
      .filter((edge) => edge.to === node.id && edge.relationType !== 'INSTANCE_OF')
      .map((edge) => ranks.get(edge.from))
      .filter((rank): rank is number => rank !== undefined);
    if (producerRanks.length) ranks.set(node.id, Math.max(...producerRanks));
  });
  const grouped = new Map<number, LineageNode[]>();
  nodes.forEach((node) => {
    const rank = ranks.get(node.id) || 1;
    if (!grouped.has(rank)) grouped.set(rank, []);
    grouped.get(rank)!.push(node);
  });
  const rankValues = Array.from(grouped.keys()).sort((a, b) => a - b);
  const stageNodes = rankValues.map((rank) => grouped.get(rank)!.sort(stableNodeCompare));
  orderByBarycenter(stageNodes, edges);
  const stages = stageNodes.map((stage, index) => [rankValues[index], stage] as [number, LineageNode[]]);

  const nodeWidth = 236;
  const nodeHeight = 84;
  const columnGap = 132;
  const rowGap = 38;
  const padding = 54;
  const maxRows = Math.max(1, ...stageNodes.map((stage) => stage.length));
  const width = Math.max(1100, padding * 2 + stages.length * nodeWidth + Math.max(0, stages.length - 1) * columnGap);
  const height = Math.max(440, padding * 2 + maxRows * nodeHeight + Math.max(0, maxRows - 1) * rowGap);
  const positions = new Map<string, PositionedNode>();
  stages.forEach(([, stage], columnIndex) => {
    const stackHeight = stage.length * nodeHeight + Math.max(0, stage.length - 1) * rowGap;
    stage.forEach((node, rowIndex) => positions.set(node.id, {
      x: padding + columnIndex * (nodeWidth + columnGap),
      y: (height - stackHeight) / 2 + rowIndex * (nodeHeight + rowGap),
    }));
  });

  const validEdges = edges.filter((edge) => positions.has(edge.from) && positions.has(edge.to));
  const outgoing = new Map<string, LineageEdge[]>();
  const incoming = new Map<string, LineageEdge[]>();
  validEdges.forEach((edge) => {
    outgoing.set(edge.from, [...(outgoing.get(edge.from) || []), edge]);
    incoming.set(edge.to, [...(incoming.get(edge.to) || []), edge]);
  });
  const edgeKey = (edge: LineageEdge) => `${edge.from}|${edge.to}|${edge.relationType || ''}|${edge.direction || ''}`;
  outgoing.forEach((list) => list.sort((a, b) => (positions.get(a.to)!.y - positions.get(b.to)!.y) || edgeKey(a).localeCompare(edgeKey(b))));
  incoming.forEach((list) => list.sort((a, b) => (positions.get(a.from)!.y - positions.get(b.from)!.y) || edgeKey(a).localeCompare(edgeKey(b))));
  const portOffset = (list: LineageEdge[], edge: LineageEdge) => (list.indexOf(edge) - (list.length - 1) / 2) * Math.min(12, 48 / Math.max(1, list.length - 1));
  const routedEdges = validEdges.map((edge) => {
    const from = positions.get(edge.from)!;
    const to = positions.get(edge.to)!;
    const startX = from.x + nodeWidth;
    const startY = from.y + nodeHeight / 2 + portOffset(outgoing.get(edge.from)!, edge);
    const endX = to.x;
    const endY = to.y + nodeHeight / 2 + portOffset(incoming.get(edge.to)!, edge);
    const distance = Math.max(36, endX - startX);
    const parallel = (edgeKey(edge).split('').reduce((sum, char) => sum + char.charCodeAt(0), 0) % 7 - 3) * 3;
    const c1X = startX + distance * 0.42 + parallel;
    const c2X = endX - distance * 0.42 + parallel;
    return { ...edge, key: edgeKey(edge), path: `M ${startX} ${startY} C ${c1X} ${startY}, ${c2X} ${endY}, ${endX} ${endY}` };
  });

  return { nodes, edges, stages, positions, routedEdges, nodeWidth, nodeHeight, width, height };
}
