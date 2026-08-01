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
  | 'agent.proposal'
  | 'agent.handoff'
  | 'workspace.update'
  | 'execution.progress'
  | 'execution.complete';

export interface AgentEvent {
  type: AgentEventType;
  agent?: AgentId;
  data: unknown;
  timestamp: string;
}

export type UserRole = 'admin' | 'steward' | 'viewer';
