import { create } from 'zustand';
import type { ChatMessage, AgentId, AgentStatus, WorkspaceView, RuleProposal } from '../types';

interface ChatState {
  messages: ChatMessage[];
  isConnected: boolean;
  agentStatuses: Record<AgentId, AgentStatus>;
  activeWorkspace: WorkspaceView;
  workspaceData: unknown;
  pendingProposals: RuleProposal[];

  // Actions
  addMessage: (message: ChatMessage) => void;
  setAgentStatus: (agentId: AgentId, status: AgentStatus) => void;
  setWorkspace: (view: WorkspaceView, data?: unknown) => void;
  setConnected: (connected: boolean) => void;
  addProposals: (proposals: RuleProposal[]) => void;
  updateProposalStatus: (id: string, status: 'approved' | 'rejected') => void;
  setMessages: (messages: ChatMessage[]) => void;
  clearMessages: () => void;
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

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

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
