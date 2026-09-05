import { create } from 'zustand';
import type { ChatMessage, AgentId, AgentStatus, WorkspaceView, RuleProposal } from '../types';
import { fetchChatSessions, fetchChatHistory, clearChatDatabase, bindChatSession } from '../services/api';

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
  datasetKey?: string | null;
  calendarDay?: string | null;
}

interface ChatState {
  messages: ChatMessage[];
  sessions: ChatSession[];
  activeSessionId: string;
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

  // Session Actions
  fetchSessions: (datasetKey?: string, calendarDay?: string) => Promise<void>;
  bindAxis: (datasetKey?: string, calendarDay?: string) => Promise<void>;
  createSession: (title?: string, datasetKey?: string, calendarDay?: string) => string;
  switchSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, newTitle: string) => void;
  deleteSession: (sessionId: string) => Promise<void>;
}

function updateSessionList(sessions: ChatSession[], activeSessionId: string, messages: ChatMessage[]): ChatSession[] {
  const title = messages.find((m) => m.type === 'user')?.content?.slice(0, 32) || 'Chat Session';
  const exists = sessions.some((s) => s.id === activeSessionId);
  if (!exists) {
    return [
      {
        id: activeSessionId,
        title,
        createdAt: new Date().toISOString(),
        messages,
      },
      ...sessions,
    ];
  }
  return sessions.map((s) => (s.id === activeSessionId ? { ...s, messages, title: s.title === 'New Agent Chat' ? title : s.title } : s));
}

const ACTIVE_SESSION_KEY = 'dsh.chat.activeSession';

function getSavedSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(ACTIVE_SESSION_KEY);
  } catch {
    return null;
  }
}

function saveActiveSessionId(id: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (id) {
      localStorage.setItem(ACTIVE_SESSION_KEY, id);
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  } catch {}
}

const initialActiveId = getSavedSessionId() || 'default';


export function resolveSafeSummary(data: { safe_summary?: string; thought?: string; content?: string } | null | undefined): string {
  if (!data) return '';
  return String(data.safe_summary || data.thought || data.content || '');
}
export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  sessions: initialActiveId === 'default'
    ? [
        {
          id: 'default',
          title: 'Default Session',
          createdAt: new Date().toISOString(),
          messages: [],
        },
      ]
    : [
        {
          id: initialActiveId,
          title: 'Chat Session',
          createdAt: new Date().toISOString(),
          messages: [],
        },
        {
          id: 'default',
          title: 'Default Session',
          createdAt: new Date().toISOString(),
          messages: [],
        },
      ],
  activeSessionId: initialActiveId,
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
  sessionId: initialActiveId,

  setSessionId: (sessionId) =>
    set((state) => ({
      sessionId,
      activeSessionId: sessionId,
      sessions: state.sessions.some((s) => s.id === sessionId)
        ? state.sessions
        : [
            ...state.sessions,
            {
              id: sessionId,
              title: 'Chat Session',
              createdAt: new Date().toISOString(),
              messages: state.messages,
            },
          ],
    })),

  addMessage: (message) =>
    set((state) => {
      if (state.messages.some((m) => m.id === message.id)) return state;
      const newMessages = [...state.messages, message];
      const updates = syncWorkspaceFromMessages(newMessages);
      const updatedSessions = updateSessionList(state.sessions, state.activeSessionId, newMessages);
      return { messages: newMessages, sessions: updatedSessions, ...updates };
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
      const updatedSessions = updateSessionList(state.sessions, state.activeSessionId, updated);
      return { messages: updated, sessions: updatedSessions, ...updates };
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
        const updated = [...state.messages, newMsg];
        return { messages: updated };
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
    set((state) => {
      const updates = syncWorkspaceFromMessages(messages);
      const updatedSessions = updateSessionList(state.sessions, state.activeSessionId, messages);
      return { messages, sessions: updatedSessions, ...updates };
    }),

  clearMessages: () =>
    set((state) => ({
      messages: [],
      pendingProposals: [],
      activeWorkspace: 'empty',
      workspaceData: null,
      sessions: state.sessions.map((s) => (s.id === state.activeSessionId ? { ...s, messages: [] } : s)),
    })),

  fetchSessions: async (datasetKey?: string, calendarDay?: string) => {
    try {
      const res = await fetchChatSessions(datasetKey, calendarDay);
      if (res && Array.isArray(res.sessions)) {
        set(() => {
          const mapped = res.sessions.map((s: any) => ({
            id: s.session_id,
            title: s.title || 'Chat Session',
            createdAt: s.last_updated || new Date().toISOString(),
            messages: [] as ChatMessage[],
            datasetKey: s.dataset_key,
            calendarDay: s.calendar_day,
          }));
          return { sessions: mapped };
        });
      }

      const savedId = getSavedSessionId();
      if (savedId) {
        const exists = get().sessions.some((s) => s.id === savedId);
        if (exists) {
          await get().switchSession(savedId);
        } else {
          saveActiveSessionId(null);
        }
      }
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    }
  },

  bindAxis: async (datasetKey?: string, calendarDay?: string) => {
    await get().fetchSessions(datasetKey, calendarDay);
    const pair = get().sessions;
    if (pair.length > 0) {
      await get().switchSession(pair[0].id);
      return;
    }
    get().createSession(undefined, datasetKey, calendarDay);
  },

  createSession: (title, datasetKey, calendarDay) => {
    const newId = `session_${Date.now()}`;
    const newSession: ChatSession = {
      id: newId,
      title: title || 'New Agent Chat',
      createdAt: new Date().toISOString(),
      messages: [],
      datasetKey,
      calendarDay,
    };
    saveActiveSessionId(newId);
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: newId,
      sessionId: newId,
      messages: [],
    }));
    void bindChatSession(newId, datasetKey, calendarDay, title || 'New Agent Chat');
    return newId;
  },

  switchSession: async (sessionId) => {
    saveActiveSessionId(sessionId);
    set({ activeSessionId: sessionId, sessionId });
    const session = get().sessions.find((s) => s.id === sessionId);
    if (session && session.messages.length > 0) {
      set({ messages: session.messages });
      return;
    }
    try {
      const history = await fetchChatHistory(sessionId);
      if (history && Array.isArray(history.messages)) {
        set((state) => ({
          messages: history.messages,
          sessions: state.sessions.map((s) =>
            s.id === sessionId ? { ...s, messages: history.messages } : s
          ),
        }));
      }
    } catch (err) {
      console.error('Failed to fetch history for session:', sessionId, err);
    }
  },

  renameSession: (sessionId, newTitle) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId ? { ...s, title: newTitle } : s
      ),
    }));
  },

  deleteSession: async (sessionId) => {
    try {
      await clearChatDatabase(sessionId);
    } catch (err) {
      console.error('Failed to delete session:', sessionId, err);
    }
    const currentSaved = getSavedSessionId();
    if (currentSaved === sessionId) {
      saveActiveSessionId(null);
    }
    set((state) => {
      const remaining = state.sessions.filter((s) => s.id !== sessionId);
      let nextActive = state.activeSessionId;
      let nextMessages = state.messages;
      if (state.activeSessionId === sessionId) {
        if (remaining.length > 0) {
          nextActive = remaining[0].id;
          nextMessages = remaining[0].messages || [];
        } else {
          const defSession: ChatSession = {
            id: 'default',
            title: 'Default Session',
            createdAt: new Date().toISOString(),
            messages: [],
          };
          remaining.push(defSession);
          nextActive = 'default';
          nextMessages = [];
        }
        saveActiveSessionId(nextActive);
      }
      return {
        sessions: remaining,
        activeSessionId: nextActive,
        sessionId: nextActive,
        messages: nextMessages,
      };
    });
  },
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
