import { useChatStore } from '../stores/chatStore';
import type { AgentEvent, AgentId, WorkspaceView, RuleProposal, DecisionRecord } from '../types';

export function parseDecisionRecord(event: AgentEvent | any): DecisionRecord {
  const data = (event.data || event) as any;

  if (data && typeof data === 'object') {
    const action = data.action || data.next_action || data.selected_action || data.tool || event.agent || 'Agent Step';
    const rawEvidence = data.evidence || data.evidence_refs || data.observation || data.thought || data.delta || [];
    const evidence = Array.isArray(rawEvidence)
      ? rawEvidence.map(String).filter(Boolean)
      : [String(rawEvidence)].filter(Boolean);
    const confidence = typeof data.confidence === 'number' ? data.confidence : 0.95;
    const status = data.status || 'completed';

    return {
      action: String(action),
      evidence: evidence.length > 0 ? evidence : ['Baseline telemetry profile & schema rules'],
      confidence,
      status: String(status),
    };
  }

  const rawText = String(event.delta || event.data || '');
  return parseChainOfThoughtToRecord(rawText, event.agent);
}

export function parseChainOfThoughtToRecord(thoughtStr: string, agentId?: string): DecisionRecord {
  const actionMatch = thoughtStr.match(/(?:action|tool|executing|selecting|running):\s*([^\n\.,]+)/i);
  const action = actionMatch ? actionMatch[1].trim() : `${agentId || 'Agent'} Execution`;

  const confMatch = thoughtStr.match(/confidence:?\s*(0?\.\d+|\d+%\b)/i);
  let confidence = 0.95;
  if (confMatch) {
    if (confMatch[1].endsWith('%')) {
      confidence = parseFloat(confMatch[1]) / 100;
    } else {
      confidence = parseFloat(confMatch[1]);
    }
  }

  const evidenceMatch = thoughtStr.match(/(?:evidence|because|rationale|observation):\s*([^\n]+)/i);
  const evidenceStr = evidenceMatch ? evidenceMatch[1].trim() : thoughtStr.slice(0, 100).trim();
  const evidence = evidenceStr ? [evidenceStr] : ['Statistical column profiling & anomaly flags'];

  const statusMatch = thoughtStr.match(/(?:status|state):\s*([^\n\.,]+)/i);
  const status = statusMatch ? statusMatch[1].trim() : 'completed';

  return { action, evidence, confidence, status };
}

export function formatDecisionRecordSummary(record: DecisionRecord): string {
  const confPct = Math.round(record.confidence * 100);
  const evidenceSummary = record.evidence.join(' | ');
  return `⚡ [DecisionRecord] Action: ${record.action} | Confidence: ${confPct}% | Status: ${record.status}${
    evidenceSummary ? ` | Evidence: ${evidenceSummary}` : ''
  }`;
}

export class AgentWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private pingTimer: number | null = null;
  private baseDelay: number = 1000;
  private maxDelay: number = 30000;
  private backoffFactor: number = 2;
  private reconnectAttempts: number = 0;
  private pingIntervalMs: number = 15000;
  private isManuallyClosed: boolean = false;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isManuallyClosed = false;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5174' ? 'localhost:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        useChatStore.getState().setConnected(true);
        this.reconnectAttempts = 0;
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const data: AgentEvent = JSON.parse(event.data);
          if ((data as any).type === 'pong') {
            return;
          }
          this.handleEvent(data);
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };

      this.ws.onclose = () => {
        useChatStore.getState().setConnected(false);
        this.stopHeartbeat();
        this.ws = null;
        if (!this.isManuallyClosed) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        useChatStore.getState().setConnected(false);
      };
    } catch (e) {
      console.error('WebSocket connection error:', e);
      this.scheduleReconnect();
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingTimer = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' });
      }
    }, this.pingIntervalMs);
  }

  private stopHeartbeat() {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);

    const expDelay = Math.min(
      this.maxDelay,
      this.baseDelay * Math.pow(this.backoffFactor, this.reconnectAttempts)
    );
    const jitter = Math.random() * 1000;
    const delay = Math.min(this.maxDelay, expDelay + jitter);

    this.reconnectAttempts++;
    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay);
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
      case 'agent.trace':
      case 'agent.decision':
        if (event.id) {
          const record = parseDecisionRecord(event);
          const summary = formatDecisionRecordSummary(record);
          store.appendStreamThought(event.id, summary);
        }
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('datatrust:agent-trace', { detail: event.data || event }));
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
    this.isManuallyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const agentSocket = new AgentWebSocket();
export const agentWebSocket = agentSocket;
export { AgentWebSocket as AgentSocket };
