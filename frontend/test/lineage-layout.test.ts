import { describe, expect, it } from 'vitest';
import type { LineageEdge, LineageNode } from '../lib/api-bridge';
import { buildLineageLayout, normalizeLineageGraph } from '../components/datatrust/lineage/lineage-layout';

const node = (id: string, type = 'logicalJob', mapIndex?: number): LineageNode => ({
  id,
  name: id.replace(/^logical-job:|^job:/, '').split(':')[0],
  label: id,
  type,
  layer: 'TASK',
  status: 'SUCCESS',
  mapIndex,
});

describe('lineage layout', () => {
  it('derives stages from dependencies instead of putting missing stages in stage one', () => {
    const nodes = [node('logical-job:a'), node('logical-job:b'), node('logical-job:c')];
    const edges: LineageEdge[] = [
      { from: 'logical-job:a', to: 'logical-job:b', relationType: 'LOGICAL_DEPENDENCY' },
      { from: 'logical-job:b', to: 'logical-job:c', relationType: 'LOGICAL_DEPENDENCY' },
    ];
    const layout = buildLineageLayout(nodes, edges);
    expect(layout.stages.map(([, stage]) => stage.map((item) => item.id))).toEqual([
      ['logical-job:a'], ['logical-job:b'], ['logical-job:c'],
    ]);
    expect(layout.positions.get('logical-job:a')!.x).toBeLessThan(layout.positions.get('logical-job:b')!.x);
  });

  it('collapses a singleton unmapped runtime task but preserves mapped instances', () => {
    const nodes = [
      node('logical-job:a'), node('job:a:-1', 'job', -1),
      node('logical-job:b'), node('job:b:0', 'job', 0), node('job:b:1', 'job', 1),
    ];
    const edges: LineageEdge[] = [
      { from: 'job:a:-1', to: 'logical-job:a', relationType: 'INSTANCE_OF' },
      { from: 'logical-job:a', to: 'logical-job:b', relationType: 'LOGICAL_DEPENDENCY' },
      { from: 'job:b:0', to: 'logical-job:b', relationType: 'INSTANCE_OF' },
      { from: 'job:b:1', to: 'logical-job:b', relationType: 'INSTANCE_OF' },
    ];
    const normalized = normalizeLineageGraph(nodes, edges);
    expect(normalized.nodes.map((item) => item.id)).not.toContain('logical-job:a');
    expect(normalized.nodes.map((item) => item.id)).toEqual(expect.arrayContaining(['job:a:-1', 'logical-job:b', 'job:b:0', 'job:b:1']));
    expect(normalized.edges).toContainEqual(expect.objectContaining({ from: 'job:a:-1', to: 'logical-job:b' }));
    expect(normalized.edges.some((edge) => edge.from === edge.to)).toBe(false);

    const layout = buildLineageLayout(nodes, [...edges].reverse());
    const stageOf = (id: string) => layout.stages.find(([_, stage]) => stage.some((item) => item.id === id))?.[0];
    expect(stageOf('job:b:0')).toBe(stageOf('logical-job:b'));
    expect(stageOf('job:b:1')).toBe(stageOf('logical-job:b'));
  });

  it('prefers a valid backend logical stage and deterministically inherits it for mapped instances', () => {
    const nodes = [
      { ...node('logical-job:a'), stage: 2 },
      { ...node('logical-job:b'), stage: 5 },
      node('job:b:1', 'job', 1),
      node('job:b:0', 'job', 0),
    ];
    const edges: LineageEdge[] = [
      { from: 'job:b:1', to: 'logical-job:b', relationType: 'INSTANCE_OF' },
      { from: 'logical-job:a', to: 'logical-job:b', relationType: 'LOGICAL_DEPENDENCY' },
      { from: 'job:b:0', to: 'logical-job:b', relationType: 'INSTANCE_OF' },
    ];
    const stages = buildLineageLayout(nodes, edges).stages;
    const stageOf = (id: string) => stages.find(([_, stage]) => stage.some((item) => item.id === id))?.[0];
    expect(stageOf('job:b:0')).toBe(stageOf('logical-job:b'));
    expect(stageOf('job:b:1')).toBe(stageOf('logical-job:b'));
    expect(stages.flatMap(([, stage]) => stage.map((item) => item.id))).toEqual(
      buildLineageLayout([...nodes].reverse(), [...edges].reverse()).stages.flatMap(([, stage]) => stage.map((item) => item.id)),
    );
  });

  it('uses separate ports and paths for multiple relationships between nodes', () => {
    const nodes = [node('logical-job:a'), node('logical-job:b'), node('logical-job:c')];
    const edges: LineageEdge[] = [
      { from: 'logical-job:a', to: 'logical-job:c', relationType: 'DECLARED' },
      { from: 'logical-job:a', to: 'logical-job:c', relationType: 'OBSERVED' },
      { from: 'logical-job:b', to: 'logical-job:c', relationType: 'LOGICAL_DEPENDENCY' },
    ];
    const layout = buildLineageLayout(nodes, edges);
    expect(new Set(layout.routedEdges.map((edge) => edge.path)).size).toBe(2);
    expect(layout.routedEdges.find((edge) => edge.relationType === 'DECLARED')).toBeFalsy();
    expect(layout.routedEdges.find((edge) => edge.relationType === 'OBSERVED')).toBeTruthy();
  });

  it('merges Airflow dataset aliases and prefers one observed flow', () => {
    const task = { ...node('job:ingest:-1', 'job', -1), stage: 2 };
    const datasets: LineageNode[] = [
      { ...node('dataset:bronze.all_tables', 'dataset'), name: 'bronze.all_tables', label: 'bronze.all_tables', layer: 'BRONZE', status: 'DECLARED', stage: 2 },
      { ...node('dataset:airflow.bronze.all_tables', 'dataset'), name: 'airflow.bronze.all_tables', label: 'airflow.bronze.all_tables', layer: 'BRONZE', status: 'OBSERVED', stage: 3 },
    ];
    const edges: LineageEdge[] = [
      { from: task.id, to: datasets[0].id, relationType: 'DECLARED' },
      { from: task.id, to: datasets[1].id, relationType: 'OBSERVED' },
    ];
    const layout = buildLineageLayout([task, ...datasets], edges);
    const merged = layout.nodes.filter((item) => item.type === 'dataset');
    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ id: 'dataset:bronze.all_tables', status: 'OBSERVED' });
    expect((merged[0].facets?.metadataSources as unknown[])).toHaveLength(2);
    expect(layout.edges).toEqual([expect.objectContaining({ relationType: 'OBSERVED' })]);
    expect(layout.stages.find(([, items]) => items.some((item) => item.id === merged[0].id))?.[0]).toBe(2);
  });
});
