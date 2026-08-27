// Agent types
export type AgentId = 'orchestrator' | 'profiler' | 'ruleProposer' | 'anomalyDetector' | 'diagnosis';
export type AgentStatus = 'active' | 'working' | 'done' | 'idle' | 'error';

export interface AgentInfo {
  id: AgentId;
  nameKey: string; // i18n key
  descKey: string; // i18n key
  color: string;
  icon: string; // Lucide icon name
  status: AgentStatus;
}

export const AGENTS: Record<AgentId, Omit<AgentInfo, 'status'>> = {
  orchestrator: { id: 'orchestrator', nameKey: 'agents:orchestrator', descKey: 'agents:orchestratorDesc', color: '#06b6d4', icon: 'Brain' },
  profiler: { id: 'profiler', nameKey: 'agents:profiler', descKey: 'agents:profilerDesc', color: '#3b82f6', icon: 'ScanSearch' },
  ruleProposer: { id: 'ruleProposer', nameKey: 'agents:ruleProposer', descKey: 'agents:ruleProposerDesc', color: '#22c55e', icon: 'ShieldCheck' },
  anomalyDetector: { id: 'anomalyDetector', nameKey: 'agents:anomalyDetector', descKey: 'agents:anomalyDetectorDesc', color: '#f59e0b', icon: 'AlertTriangle' },
  diagnosis: { id: 'diagnosis', nameKey: 'agents:diagnosisAgent', descKey: 'agents:diagnosisAgentDesc', color: '#a855f7', icon: 'Stethoscope' },
};

// Chat message types
export type MessageType = 'user' | 'agent' | 'system' | 'proposal' | 'handoff';

export interface ChatMessage {
  id: string;
  type: MessageType;
  content: string;
  timestamp: string;
  agentId?: AgentId;
  metadata?: Record<string, unknown>;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  model?: string;
  retrievedTables?: string[];
  retrievedRules?: string[];
}

export interface RuleProposal {
  id: string;
  type: string;
  column: string;
  expression: string;
  description: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'pending' | 'approved' | 'rejected';
  agentId: AgentId;
}

export interface ProposalMessage extends ChatMessage {
  type: 'proposal';
  proposals: RuleProposal[];
}

export interface HandoffMessage extends ChatMessage {
  type: 'handoff';
  fromAgent: AgentId;
  toAgent: AgentId;
}

// Workspace types
export type WorkspaceView = 'empty' | 'profile' | 'rules' | 'anomaly' | 'audit' | 'diff';

export interface WorkspaceState {
  activeView: WorkspaceView;
  data: unknown;
}

// WebSocket event types
export type AgentEventType =
  | 'agent.status'
  | 'agent.message'
  | 'chat.message'
  | 'agent.proposal'
  | 'agent.handoff'
  | 'workspace.update'
  | 'execution.progress'
  | 'execution.complete';

export interface AgentEvent {
  type: AgentEventType | string;
  agent?: AgentId;
  panel?: WorkspaceView | string;
  proposals?: RuleProposal[];
  data?: unknown;
  id?: string;
  delta?: string;
  timestamp?: string;
}

export type UserRole = 'admin' | 'steward' | 'viewer';

export interface DecisionRecord {
  action: string;
  evidence: string[];
  confidence: number;
  status: string;
}

// ── Pipeline / Mission types (ui_temp port) ──────────────────────────────

export type PipelineStepId = 1 | 2 | 3 | 4 | 5 | 6 | 7;
export type StepStatus = 'pending' | 'active' | 'completed' | 'waiting' | 'error';
export type PipelineRunStatus = 'idle' | 'running' | 'paused' | 'awaiting_hitl' | 'complete' | 'failed';

export interface PipelineStepDef {
  id: PipelineStepId;
  name: string;
  agent: 'orchestrator' | 'profiler' | 'anomaly' | 'proposer' | 'human' | 'executor';
  tab: 'tab-manifest' | 'tab-telemetry' | 'tab-rca' | 'tab-split';
  isReviewStep?: boolean;
  desc: string;
}

export type DomainId = 'ev_telemetry' | 'charging_sessions' | 'trips' | 'nlp_feedback' | 'vingroup_pilot' | string;

export interface DomainInfo {
  id: DomainId;
  shortcut: string; // sidebar alias: ev | vgreen | xanhsm | nlp
  name: string;
  dbName: string;
  table: string;
  rows: string;
  size: string;
  engine: string;
  topic: string;
  cleanRows: number;
  quarantineRows: number;
  anomalySummary: string;
  defaultRule: string;
}

export type TimeFilter = 'Today' | '3d' | '7d' | 'This Week' | 'This Month';

export interface TimeFilterSnapshot {
  date: string;
  quarantineCount: number;
  cleanCount: number;
  hash: string;
  pytestPass: string;
}

export interface SplitRow {
  id: string;
  timestamp: string;
  vehicleId: string;
  battTemp: string;
  vDelta: string;
  status: 'CLEAN' | 'QUARANTINED';
  code: string;
}

export interface RuleProposalBackend {
  rule_id: string;
  rule_name: string;
  rule_type: string;
  rule_expression: string;
  confidence?: number;
  status?: string;
  proposed_by?: string;
  proposed_at?: string | null;
}

export interface QuarantineRecord {
  id: string;
  source_table: string;
  source_row_id: string;
  rule_id: string;
  reason: string;
  quarantined_at?: string | null;
  lineage_hash?: string | null;
}

export interface PipelineRunInfo {
  run_id: string;
  status: string;
  table: string;
  steps?: Array<{ agent?: string; step?: number; action?: string; timestamp?: string | null }>;
}

