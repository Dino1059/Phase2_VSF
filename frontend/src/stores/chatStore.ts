import { create } from 'zustand';
import type { ChatMessage, AgentId, AgentStatus, WorkspaceView, RuleProposal } from '../types';

interface ChatState {
  messages: ChatMessage[];
  isConnected: boolean;
  agentStatuses: Record<AgentId, AgentStatus>;
  activeWorkspace: WorkspaceView;
  workspaceData: unknown;
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
  pendingProposals: [],
  sessionId: 'default',

  setSessionId: (sessionId) => set({ sessionId }),

  addMessage: (message) =>
    set((state) => {
      if (state.messages.some((m) => m.id === message.id)) return state;
      return { messages: [...state.messages, message] };
    }),

  appendStreamChunk: (id, delta) =>
    set((state) => {
      const existingIndex = state.messages.findIndex((m) => m.id === id);
      if (existingIndex >= 0) {
        const updated = [...state.messages];
        updated[existingIndex] = {
          ...updated[existingIndex],
          content: updated[existingIndex].content + delta,
        };
        return { messages: updated };
      } else {
        const newMsg: ChatMessage = {
          id,
          type: 'agent',
          agentId: 'orchestrator',
          content: delta,
          timestamp: new Date().toISOString(),
        };
        return { messages: [...state.messages, newMsg] };
      }
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
    set({ activeWorkspace: view, workspaceData: data ?? null }),

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

  setMessages: (messages) => set({ messages }),

  clearMessages: () => set({ messages: [], pendingProposals: [] }),
}));
