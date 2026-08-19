export interface DemoBeat {
  type: 'workflow.step' | 'steward_message' | 'hitl_pause';
  actor_kind: string;
  action?: string;
  summary: string;
  tool?: { name: string; status: string; duration_ms?: number };
  evidence_ids?: string[];
  output?: Record<string, unknown>;
  delay_ms: number;
}

export const DEMO_META = {
  demo_id: 'vingroup-soc-2026-08',
  dataset_key: 'vingroup_pilot',
  provenance: 'demo',
  duration_s: 75,
};

export const STEWARD_SESSION_BEATS: DemoBeat[] = [
  {
    type: 'workflow.step',
    actor_kind: 'SYSTEM',
    action: 'register_dataset',
    summary: 'Mounted bundled VinGroup pilot. Provenance: DEMO · bundled.',
    tool: { name: 'register_dataset', status: 'COMPLETED', duration_ms: 120 },
    output: { dataset_key: 'vingroup_pilot', provenance: 'demo' },
    delay_ms: 800,
  },
  {
    type: 'workflow.step',
    actor_kind: 'C1_AI',
    action: 'profile_dataset',
    summary: 'Sampled pilot telemetry. Findings come from this replay tape, not a live model.',
    tool: { name: 'profile_dataset', status: 'COMPLETED', duration_ms: 640 },
    evidence_ids: ['ev_demo_001'],
    output: { sample_size: 50000, columns_count: 10, flags: 14 },
    delay_ms: 10000,
  },
  {
    type: 'steward_message',
    actor_kind: 'ORCHESTRATOR',
    summary: 'Profile complete on vingroup_pilot (DEMO). 14 range flags recorded on the tape. Nothing has been written to clean or quarantine.',
    delay_ms: 2000,
  },
  {
    type: 'workflow.step',
    actor_kind: 'C1_AI',
    action: 'propose_quality_rules',
    summary: 'Drafted 3 L1 rules. Waiting for steward review.',
    tool: { name: 'propose_quality_rules', status: 'COMPLETED', duration_ms: 410 },
    output: { proposals: 3 },
    delay_ms: 10000,
  },
  {
    type: 'hitl_pause',
    actor_kind: 'DATA_STEWARD',
    summary: 'HITL gate. Review the three drafted rules. Clean/execute will not run until you authorize an exact version.',
    delay_ms: 800,
  },
];
