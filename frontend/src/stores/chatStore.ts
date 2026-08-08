import { create } from 'zustand';
import type { ChatMessage, AgentId, AgentStatus, WorkspaceView, RuleProposal } from '../types';

interface ChatState {
  messages: ChatMessage[];
  isConnected: boolean;
  agentStatuses: Record<AgentId, AgentStatus>;
  activeWorkspace: WorkspaceView;
  workspaceData: unknown;
  profileData: unknown;
  anomalyData: unknown;
  auditData: unknown;
  pendingProposals: RuleProposal[];
  sessionId: string;

  // Actions
  addMessage: (message: ChatMessage) => void;
  setAgentStatus: (agentId: AgentId, status: AgentStatus) => void;
  setWorkspace: (view: WorkspaceView, data?: unknown) => void;
  setConnected: (connected: boolean) => void;
  addProposals: (proposals: RuleProposal[]) => void;
  updateProposalStatus: (id: string, status: 'approved' | 'rejected') => void;
  setMessages: (messages: ChatMessage[]) => void;
  clearMessages: () => void;
  setSessionId: (id: string) => void;
  appendStreamChunk: (id: string, delta: string) => void;
  appendStreamThought: (id: string, delta: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isConnected: false,
  agentStatuses: {
    orchestrator: 'idle',
    profiler: 'idle',
    ruleProposer: 'idle',
    anomalyDetector: 'idle',
    diagnosis: 'idle',
  },
  activeWorkspace: 'empty',
  workspaceData: null,
  profileData: null,
  anomalyData: null,
  auditData: null,
  pendingProposals: [],
  sessionId: 'default',

  setSessionId: (sessionId) => set({ sessionId }),

  addMessage: (message) =>
    set((state) => {
      if (state.messages.some((m) => m.id === message.id)) return state;
      const newMessages = [...state.messages, message];
      const updates = syncWorkspaceFromMessages(newMessages);
      return { messages: newMessages, ...updates };
    }),

  appendStreamChunk: (id, delta) =>
    set((state) => {
      const existingIndex = state.messages.findIndex((m) => m.id === id);
      let updated: ChatMessage[];
      if (existingIndex >= 0) {
        updated = [...state.messages];
        updated[existingIndex] = {
          ...updated[existingIndex],
          content: updated[existingIndex].content + delta,
        };
      } else {
        const newMsg: ChatMessage = {
          id,
          type: 'agent',
          agentId: 'orchestrator',
          content: delta,
          timestamp: new Date().toISOString(),
        };
        updated = [...state.messages, newMsg];
      }
      const updates = syncWorkspaceFromMessages(updated);
      return { messages: updated, ...updates };
    }),

  appendStreamThought: (id, delta) =>
    set((state) => {
      const existingIndex = state.messages.findIndex((m) => m.id === id);
      if (existingIndex >= 0) {
        const updated = [...state.messages];
        const prevReasoning = (updated[existingIndex].metadata as any)?.reasoning || '';
        updated[existingIndex] = {
          ...updated[existingIndex],
          metadata: {
            ...(updated[existingIndex].metadata || {}),
            reasoning: prevReasoning + delta,
          },
        };
        return { messages: updated };
      } else {
        const newMsg: ChatMessage = {
          id,
          type: 'agent',
          agentId: 'orchestrator',
          content: '',
          metadata: { reasoning: delta },
          timestamp: new Date().toISOString(),
        };
        return { messages: [...state.messages, newMsg] };
      }
    }),

  setAgentStatus: (agentId, status) =>
    set((state) => ({
      agentStatuses: { ...state.agentStatuses, [agentId]: status },
    })),

  setWorkspace: (view, data) =>
    set((state) => ({
      activeWorkspace: view,
      workspaceData: data !== undefined ? data : state.workspaceData,
    })),

  setConnected: (connected) => set({ isConnected: connected }),

  addProposals: (proposals) =>
    set((state) => ({
      pendingProposals: [...state.pendingProposals, ...proposals],
    })),

  updateProposalStatus: (id, status) =>
    set((state) => ({
      pendingProposals: state.pendingProposals.map((p) =>
        p.id === id ? { ...p, status } : p
      ),
    })),

  setMessages: (messages) =>
    set(() => {
      const updates = syncWorkspaceFromMessages(messages);
      return { messages, ...updates };
    }),

  clearMessages: () => set({ messages: [], pendingProposals: [], activeWorkspace: 'empty', workspaceData: null }),
}));

function autoRepairJson(str: string): any {
  if (!str) return null;
  let unescaped = str.replace(/\\"/g, '"').trim();
  try {
    return JSON.parse(unescaped);
  } catch {
    let temp = unescaped;

    // Fix single-quoted python repr json strings
    if (temp.includes("'")) {
      const doubleQuoted = temp.replace(/('(?=([^"]*"[^"]*")*[^"]*$))/g, '"');
      try {
        return JSON.parse(doubleQuoted);
      } catch {
        // continue repair
      }
    }

    if (temp.endsWith(',')) temp = temp.slice(0, -1);
    if ((temp.match(/"/g) || []).length % 2 !== 0) temp += '"';

    const openBraces = (temp.match(/\{/g) || []).length;
    const closeBraces = (temp.match(/\}/g) || []).length;
    const openBrackets = (temp.match(/\[/g) || []).length;
    const closeBrackets = (temp.match(/\]/g) || []).length;

    for (let i = 0; i < openBrackets - closeBrackets; i++) temp += ']';
    for (let i = 0; i < openBraces - closeBraces; i++) temp += '}';

    try {
      return JSON.parse(temp);
    } catch {
      return null;
    }
  }
}

function extractAllValidJsons(str: string): any[] {
  if (!str) return [];
  const cleanStr = str.replace(/\\"/g, '"');
  const results: any[] = [];
  let openBraces = 0;
  let inString = false;
  let escape = false;
  let startIdx = -1;

  for (let i = 0; i < cleanStr.length; i++) {
    const char = cleanStr[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (char === '\\') {
      escape = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (!inString) {
      if (char === '{' || char === '[') {
        if (openBraces === 0) startIdx = i;
        openBraces++;
      } else if (char === '}' || char === ']') {
        if (openBraces > 0) {
          openBraces--;
          if (openBraces === 0 && startIdx !== -1) {
            const substring = str.slice(startIdx, i + 1);
            const parsed = autoRepairJson(substring);
            if (parsed) results.push(parsed);
            startIdx = -1;
          }
        }
      }
    }
  }

  if (startIdx !== -1) {
    const substring = str.slice(startIdx);
    const parsed = autoRepairJson(substring);
    if (parsed) results.push(parsed);
  }

  return results;
}

function extractObservationJsons(text: string): any[] {
  if (!text) return [];
  const jsons: any[] = [];

  // 1. Check for markdown code blocks ```json ... ```
  const jsonCodeBlockRegex = /```(?:json)?\s*([\s\S]*?)\s*```/gi;
  let match;
  while ((match = jsonCodeBlockRegex.exec(text)) !== null) {
    const extracted = extractAllValidJsons(match[1]);
    jsons.push(...extracted);
  }

  // 2. Fallback to Observation: delimiter or raw text
  if (jsons.length === 0) {
    const obsIndex = text.indexOf('Observation:');
    if (obsIndex !== -1) {
      const parts = text.split('Observation:');
      for (let i = 1; i < parts.length; i++) {
        const extracted = extractAllValidJsons(parts[i]);
        jsons.push(...extracted);
      }
    }
  }

  if (jsons.length === 0) {
    jsons.push(...extractAllValidJsons(text));
  }

  return jsons;
}

function syncWorkspaceFromMessages(messages: ChatMessage[]) {
  let latestProfile: any = null;
  let proposalsList: RuleProposal[] = [];
  let latestAnomaly: any = null;
  let latestAudit: any = null;

  for (const msg of messages) {
    const textToScan = [msg.content, (msg.metadata as any)?.reasoning].filter(Boolean).join('\n');
    const jsons = extractObservationJsons(textToScan);

    for (const json of jsons) {
      if (!json || typeof json !== 'object') continue;
      console.log('json:', json);

      // Profile data
      if (json.profile || json.columns || json.columns_count || json.total_rows) {
        let profileObj = json.profile || json;
        if (typeof profileObj === 'string') {
          try {
            profileObj = JSON.parse(profileObj);
          } catch {}
        }
        if (typeof profileObj !== 'object' || !profileObj) profileObj = json;

        let rawCols = profileObj.columns || json.columns || profileObj.column_profiles || [];
        if (rawCols && !Array.isArray(rawCols) && typeof rawCols === 'object') {
          rawCols = Object.entries(rawCols).map(([k, v]: [string, any]) => ({
            name: k,
            ...(typeof v === 'object' ? v : { type: String(v) }),
          }));
        }

        const cols = Array.isArray(rawCols) ? rawCols.map((c: any) => ({
          name: c.name || c.column_name || c.column || 'column',
          type: c.data_type || c.type || 'STRING',
          nullRate: (c.null_count || 0) / (c.total_count || profileObj.total_rows || json.total_rows || 1),
          uniqueRate: (c.unique_count || 0) / (c.total_count || profileObj.total_rows || json.total_rows || 1),
          health: (c.null_count || 0) > 0 ? 'warning' : 'healthy',
        })) : [];

        if (cols.length > 0) {
          latestProfile = {
            totalRows: profileObj.total_rows || json.total_rows || 0,
            columns: cols,
          };
        }
      }

      // Rule Proposals
      const rawRules = json.proposals || json.proposed_rules || json.rules;
      if (Array.isArray(rawRules)) {
        proposalsList = rawRules.map((p: any) => ({
          id: p.id || Math.random().toString(),
          agentId: p.agentId || 'ruleProposer',
          type: p.rule_type || p.type || 'quality_rule',
          column: p.column || p.rule_name || '*',
          expression: p.rule_expression || p.expression || p.description || '',
          description: p.description || '',
          severity: p.severity || 'warning',
          status: p.status || 'pending',
        }));
      }

      // Anomaly Detection
      if (json.anomalies || json.anomaly_score !== undefined || json.anomalies_found !== undefined || json.anomalies_detected) {
        latestAnomaly = json;
      }

      // Audit Trail
      if (json.audit_logs || json.audit_store || json.entries || json.action === 'EXECUTE_RULE' || json.action === 'EXECUTE_DATASET_RULES') {
        latestAudit = json;
      }
    }
  }

  const updates: any = {};
  if (latestProfile) updates.profileData = latestProfile;
  if (latestAnomaly) updates.anomalyData = latestAnomaly;
  if (latestAudit) updates.auditData = latestAudit;
  if (proposalsList.length > 0) updates.pendingProposals = proposalsList;

  if (proposalsList.length > 0) {
    updates.activeWorkspace = 'rules';
  } else if (latestAnomaly) {
    updates.activeWorkspace = 'anomaly';
  } else if (latestProfile) {
    updates.activeWorkspace = 'profile';
  } else if (latestAudit) {
    updates.activeWorkspace = 'audit';
  }

  return updates;
}

if (typeof window !== 'undefined') {
  (window as any).useChatStore = useChatStore;
}
