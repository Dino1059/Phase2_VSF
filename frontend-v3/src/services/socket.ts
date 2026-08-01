import { useChatStore } from '../stores/chatStore';
import type { AgentEvent, AgentId, WorkspaceView, RuleProposal } from '../types';

class AgentSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;

  connect() {
    if (this.ws) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5174' ? 'localhost:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        useChatStore.getState().setConnected(true);
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
      };

      this.ws.onmessage = (event) => {
        try {
          const data: AgentEvent = JSON.parse(event.data);
          this.handleEvent(data);
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };

      this.ws.onclose = () => {
        useChatStore.getState().setConnected(false);
        this.ws = null;
        this.reconnectTimer = window.setTimeout(() => this.connect(), 3000);
      };

      this.ws.onerror = () => {
        useChatStore.getState().setConnected(false);
      };
    } catch (e) {
      console.error('WebSocket connection error:', e);
    }
  }

  private handleEvent(event: AgentEvent) {
    const store = useChatStore.getState();

    switch (event.type) {
      case 'agent.status':
        if (event.agent) {
          store.setAgentStatus(event.agent as AgentId, event.data as any);
        }
        break;

      case 'chat.message':
        if (event.data) {
          store.addMessage(event.data as any);
        }
        break;

      case 'chat.stream_chunk':
        if (event.id && event.delta) {
          store.appendStreamChunk(event.id, event.delta);
        }
        break;

      case 'chat.stream_thought':
        if (event.id && event.delta) {
          store.appendStreamThought(event.id, event.delta);
        }
        break;

      case 'agent.proposal':
        if (Array.isArray(event.proposals || event.data)) {
          const props = (event.proposals || event.data) as RuleProposal[];
          store.addProposals(props);
        }
        break;

      case 'workspace.update':
        if (event.panel && event.data) {
          store.setWorkspace(event.panel as WorkspaceView, event.data);
        }
        break;
    }
  }

  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const agentSocket = new AgentSocket();
