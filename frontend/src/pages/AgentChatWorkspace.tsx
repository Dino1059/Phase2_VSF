import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Pencil,
  Save,
  Database,
  UserShield,
  AlertTriangle,
  Lightbulb,
  ScanSearch,
  Stethoscope,
  FlaskConical,
  Brain,
  Clock,
  Plus,
  Mic,
  ArrowUp,
  CloudUpload,
  ChevronLeft,
  ChevronRight,
  Play,
  Sparkles,
} from 'lucide-react';
import { usePipelineStore, DOMAIN_LIST, TIME_FILTERS } from '../stores/pipelineStore';

import { usePipelineRun, StreamMessage } from '../hooks/usePipelineRun';
import { ChatInput } from '../components/chat/ChatInput';
import { MarkdownContent } from '../components/chat/MarkdownContent';
import { AgentTracesTab } from '../components/workspace/AgentTracesTab';
import { DataProfilerTab } from '../components/workspace/DataProfilerTab';
import { QualityRulesTab } from '../components/workspace/QualityRulesTab';
import { SplitDbQuarantineTab } from '../components/workspace/SplitDbQuarantineTab';
import { fetchChatHistory, pipelineApi, uploadDatasetFile, sendChatMessage, systemApi, ensureDemoAuth, resetDemoSession } from '../services/api';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import { agentSocket } from '../services/websocket';
import { formatSaigonTime, inTimeRange, catalogFor } from '../demo/stewardLabels';
import { DemoStoryBar } from '../demo/DemoStoryBar';
import { STEWARD_SESSION_BEATS, type DemoBeat } from '../demo/stewardSession';
import type { TimeFilter } from '../types';

const HITL_STOP_PROMPT_EN =
  'Profile this dataset and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review.';
const HITL_STOP_PROMPT_VI =
  'Khảo sát dữ liệu và đề xuất luật chất lượng. Không làm sạch, không cách ly, không thực thi. Dừng lại để steward duyệt HITL.';

const AGENT_AVATAR_CLASS: Record<string, string> = {
  orchestrator: 'agent-orchestrator',
  profiler: 'agent-profiler',
  anomaly: 'agent-anomaly',
  diagnosis: 'agent-diagnosis',
  proposer: 'agent-proposer',
  executor: 'agent-executor',
  human: 'agent-human',
};

const AGENT_ICONS: Record<string, React.ComponentType<{ size?: number | string }>> = {
  orchestrator: Brain,
  profiler: ScanSearch,
  anomaly: AlertTriangle,
  diagnosis: Stethoscope,
  proposer: Lightbulb,
  executor: FlaskConical,
  human: UserShield,
};

const AGENT_TITLES: Record<string, string> = {
  orchestrator: 'ORCHESTRATOR',
  profiler: 'C1 AI',
  profile_dataset: 'C1 AI',
  proposer: 'C1 AI',
  propose_quality_rules: 'C1 AI',
  anomaly: 'L1 DETECTOR',
  diagnosis: 'C1 AI',
  executor: 'EXECUTOR',
  clean_database: 'EXECUTOR',
  human: 'DATA STEWARD',
};

function historyAlreadyProfiled(messages: Array<{ content?: string; type?: string }> | undefined): boolean {
  return (messages || []).some((m) => {
    const c = m.content || '';
    return c.includes('Quality Rule Proposals') || c.includes('Đề Xuất Luật Chất Lượng') || c.includes('propose_quality_rules');
  });
}

function isProfileSummary(content?: string): boolean {
  const c = content || '';
  return c.includes('Profile Summary') || c.includes('Tóm Tắt Khảo Sát');
}

function messagesForStory<T extends { content?: string }>(messages: T[], story: string | null): T[] {
  const filtered = messages.filter((m) => !(m.content || '').includes('HAPPY · clean CSVs'));
  if (story !== 'unhappy') return filtered;
  let keptSummary = false;
  const out: T[] = [];
  for (let i = filtered.length - 1; i >= 0; i -= 1) {
    if (isProfileSummary(filtered[i].content)) {
      if (keptSummary) continue;
      keptSummary = true;
    }
    out.unshift(filtered[i]);
  }
  return out;
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: 'var(--text-main)',
  profiler: 'var(--royal-purple)',
  anomaly: 'var(--warning-amber)',
  diagnosis: 'var(--alert-magenta)',
  proposer: 'var(--electric-green)',
  executor: 'var(--electric-green)',
  human: 'var(--text-main)',
};

type RightTab = 'tab-traces' | 'tab-profiler' | 'tab-rules' | 'tab-split';

/** Survives StrictMode remount. Tab show / remount must not POST a second HITL chat. */
const hitlBootsInFlight = new Set<string>();

export function AgentChatWorkspace() {
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const datasetKey = searchParams.get('dataset_key') || undefined;
  const demoMode = searchParams.get('demo');
  const story = searchParams.get('story');
  const isHappy = story === 'happy';
  const isReplay = demoMode === 'replay';
  const isNewChat = searchParams.has('new') || (!datasetKey && !id);
  const setChatSessionId = useChatStore((s) => s.setSessionId);
  const chatMessages = useChatStore((s) => s.messages);
  const store = usePipelineStore();
  const domainId = store.domainId;
  const currentStepIndex = store.currentStepIndex;
  const currentRuleLogic = store.currentRuleLogic;
  const setDomain = usePipelineStore((s) => s.setDomain);
  const resetPipeline = usePipelineStore((s) => s.resetPipeline);
  const { acceptRule, rejectRule, saveRuleEdit, clearTimers } = usePipelineRun(datasetKey);
  const [stream, setStream] = useState<StreamMessage[]>([]);
  const [rightTab, setRightTab] = useState<RightTab>('tab-profiler');
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [editOpen, setEditOpen] = useState(false);

  const [editText, setEditText] = useState(currentRuleLogic);
  const [ruleCardState, setRuleCardState] = useState<'pending' | 'accepted' | 'rejected'>('pending');
  const [pipelineResult, setPipelineResult] = useState<Awaited<ReturnType<typeof pipelineApi.result>> | null>(null);
  const [waitingForBackendAgentEvents, setWaitingForBackendAgentEvents] = useState(false);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [replayBeats, setReplayBeats] = useState<DemoBeat[]>([]);
  const [selectedTraceStep, setSelectedTraceStep] = useState<number | null>(null);
  const [selectedTraceTool, setSelectedTraceTool] = useState<string | null>(null);
  const proposeStartedRef = useRef(false);
  const streamRef = useRef<HTMLDivElement>(null);
  const rcaCanvasRef = useRef<HTMLCanvasElement>(null);
  const telemetryCanvasRef = useRef<HTMLCanvasElement>(null);
  const runStartedRef = useRef<string | false>(false);
  const bootToken = `${datasetKey || 'none'}:${story || 'none'}:${demoMode || 'none'}`;

  const handleRunFullPipeline = useCallback(async () => {
    setIsRunningPipeline(true);
    try {
      const lang = i18n?.language || 'vi';
      const prompt = lang === 'vi' ? HITL_STOP_PROMPT_VI : HITL_STOP_PROMPT_EN;
      const currentSession = useChatStore.getState().sessionId;
      await ensureDemoAuth();
      await sendChatMessage(prompt, currentSession, datasetKey, lang);
      const history = await fetchChatHistory(currentSession);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (err) {
      console.error('Failed to trigger pipeline:', err);
    } finally {
      setIsRunningPipeline(false);
    }
  }, [datasetKey, i18n]);

  // Context-Aware Auto-Switch: sync right panel to latest agent step
  useEffect(() => {
    if (chatMessages.length === 0) return;
    const lastMsg = chatMessages[chatMessages.length - 1];
    if (lastMsg.type === 'agent' || lastMsg.agentId === 'orchestrator') {
      const content = lastMsg.content || '';
      if (content.includes('Profile Summary') || content.includes('profile_dataset')) {
        setRightTab('tab-profiler');
      } else if (content.includes('Quality Rule Proposals') || content.includes('propose_quality_rules')) {
        setRightTab('tab-rules');
      } else if (content.includes('Cleansing & Quarantine Complete') || content.includes('clean_database')) {
        setRightTab('tab-split');
      }
    }
  }, [chatMessages]);


  // Keep the selected dataset scoped to a stable temporary chat session.
  useEffect(() => {
    if (isNewChat) {
      resetPipeline();
      setChatSessionId('default');
      useChatStore.getState().clearMessages();
      return;
    }
    const sessionId = datasetKey ? `dataset:${datasetKey}` : 'default';
    setChatSessionId(sessionId);
    useChatStore.getState().clearMessages();
    if (story) return;
    void fetchChatHistory(sessionId).then((history) => {
      if (Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    }).catch((error) => {
      console.error('Failed to load chat history:', error);
    });
  }, [datasetKey, isNewChat, story, resetPipeline, setChatSessionId]);

  // Poll the persisted backend result so all right-panel tabs share one run_id.
  useEffect(() => {
    if (isNewChat) return;
    if (!store.runId) {
      setPipelineResult(null);
      return;
    }
    let active = true;
    let timer: number | undefined;
    const loadResult = async () => {
      try {
        const result = await pipelineApi.result(store.runId!);
        if (!active) return;
        setPipelineResult(result);
        if (result.status === 'running') {
          timer = window.setTimeout(() => void loadResult(), 1500);
        }
      } catch (error) {
        if (active) {
          console.error('Failed to load pipeline result:', error);
          timer = window.setTimeout(() => void loadResult(), 2500);
        }
      }
    };
    void loadResult();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [isNewChat, store.runId]);

  // Sync with sidebar domain selection (shortcut aliases)
  useEffect(() => {
    if (!id) return;
    const normalized = DOMAIN_LIST.find((d) => d.shortcut === id || d.id === id);
    if (normalized && normalized.id !== domainId) {
      setDomain(normalized.id);
    }
  }, [id, domainId, setDomain]);

  const pushMessage = useCallback((m: StreamMessage) => {
    setStream((prev) => [...prev, m]);
  }, []);

  useEffect(() => {
    agentSocket.connect();
  }, []);

  // Re-run when story/demo flips (Happy → Unhappy must start a real LLM profile).
  useEffect(() => {
    if (isNewChat) return;
    if (runStartedRef.current === bootToken) return;
    if (hitlBootsInFlight.has(bootToken)) {
      runStartedRef.current = bootToken;
      return;
    }
    hitlBootsInFlight.add(bootToken);
    runStartedRef.current = bootToken;
    proposeStartedRef.current = false;
    resetPipeline();
    setStream([]);
    useChatStore.getState().clearMessages();
    void resetDemoSession();

    if (isHappy) {
      setRightTab('tab-profiler');
      pushMessage({
        id: 'happy-snapshot',
        agent: 'orchestrator',
        text: '**HAPPY · clean CSVs** — `data_new/vingroup_pilot_dataset` (fault_injected=False). 86,400 / 1,331 / 10,382. SoC<0 = 0. OPEN = 0. Nothing to approve. Batch window ends 2026-01-15 — not a live stream.',
      });
      return () => clearTimers();
    }

    if (isReplay) {
      setReplayBeats(STEWARD_SESSION_BEATS);
      STEWARD_SESSION_BEATS.forEach((beat, i) => {
        if (beat.type === 'workflow.step') return;
        pushMessage({
          id: `replay-${i}`,
          agent: beat.actor_kind === 'DATA_STEWARD' ? 'human' : 'orchestrator',
          text: `**DEMO · simulation** — ${beat.summary}`,
        });
      });
      setRightTab('tab-traces');
      return () => clearTimers();
    }

    const forceLive = demoMode === 'live' || story === 'unhappy';
    const bootstrap = async () => {
      if (!datasetKey) return;
      const bootKey = `dt-hitl-boot:${datasetKey}:${story || 'none'}:${demoMode || 'none'}`;
      try {
        const lang = i18n?.language || 'vi';
        const session = datasetKey ? `dataset:${datasetKey}` : useChatStore.getState().sessionId;
        const existing = forceLive ? { messages: [] } : await fetchChatHistory(session);
        if (!forceLive && Array.isArray(existing.messages) && existing.messages.length) {
          useChatStore.getState().setMessages(existing.messages);
        }
        if (!forceLive) {
          const already =
            historyAlreadyProfiled(existing.messages) ||
            proposeStartedRef.current ||
            (typeof sessionStorage !== 'undefined' && sessionStorage.getItem(bootKey));
          if (already) {
            proposeStartedRef.current = true;
            try { sessionStorage.setItem(bootKey, '1'); } catch { /* ignore */ }
            setRightTab('tab-rules');
            return;
          }
        }
        // forceLive / Unhappy: hitlBootsInFlight (sync, effect entry) blocks
        // StrictMode remount. Do not use leftover sessionStorage — Happy→Unhappy
        // must still Profile & Propose once. Tab show never reaches here.
        proposeStartedRef.current = true;
        try { sessionStorage.setItem(bootKey, '1'); } catch { /* ignore */ }
        store.setStepIndex(1);
        setRightTab('tab-traces');
        setWaitingForBackendAgentEvents(true);
        await ensureDemoAuth();
        await sendChatMessage(lang === 'vi' ? HITL_STOP_PROMPT_VI : HITL_STOP_PROMPT_EN, session, datasetKey, lang);
        const history = await fetchChatHistory(session);
        if (Array.isArray(history.messages)) {
          useChatStore.getState().setMessages(history.messages);
        }
        window.dispatchEvent(new CustomEvent('datatrust:agent-trace'));
        setRightTab('tab-traces');
      } catch {
        return;
      } finally {
        setWaitingForBackendAgentEvents(false);
      }
    };
    void bootstrap();
    return () => clearTimers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainId, datasetKey, isNewChat, isReplay, isHappy, bootToken]);

  // Auto-scroll stream
  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTo({ top: streamRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [stream.length, chatMessages.length]);


  // RCA canvas render
  useEffect(() => {
    const canvas = rcaCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width = canvas.clientWidth || 380;
    const height = canvas.clientHeight || 190;
    canvas.width = width;
    canvas.height = height;
    const isDark = (document.documentElement.getAttribute('data-theme') || 'tech-dark') !== 'tech-light';
    ctx.clearRect(0, 0, width, height);
    const sourceNodes = pipelineResult?.rca?.nodes || [];
    const sourceEdges = pipelineResult?.rca?.edges || [];
    const nodes = sourceNodes.map((node: any, index: number) => ({
      ...node,
      x: width * (0.16 + (index % 3) * 0.34),
      y: height * (0.25 + (Math.floor(index / 3) % 2) * 0.5),
      color: node.type === 'incident'
        ? (isDark ? '#F59E0B' : '#D97706')
        : node.type === 'hypothesis'
          ? (isDark ? '#F43F5E' : '#EF4444')
          : (isDark ? '#00F0FF' : '#0284C7'),
      label: String(node.label || node.id),
    }));
    const nodeById = new Map(nodes.map((node: any) => [String(node.id), node]));
    ctx.lineWidth = 2;
    sourceEdges.forEach((link: any) => {
      const from = nodeById.get(String(link.source));
      const to = nodeById.get(String(link.target));
      if (!from || !to) return;
      ctx.strokeStyle = isDark ? '#1F293D' : '#CBD5E1';
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();
    });
    nodes.forEach((n) => {
      ctx.save();
      ctx.shadowBlur = isDark ? 8 : 0;
      ctx.shadowColor = isDark ? n.color : 'transparent';
      ctx.fillStyle = isDark ? '#111827' : '#FFFFFF';
      ctx.strokeStyle = n.color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 14, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = isDark ? '#F8FAFC' : '#0F172A';
      ctx.font = '600 11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(n.label, n.x, n.y + 30);
      ctx.restore();
    });
  }, [rightTab, domainId, pipelineResult]);

  // Telemetry chart render
  useEffect(() => {
    const canvas = telemetryCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width = canvas.clientWidth || 380;
    const height = canvas.clientHeight || 180;
    canvas.width = width;
    canvas.height = height;
    const isDark = (document.documentElement.getAttribute('data-theme') || 'tech-dark') !== 'tech-light';
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = isDark ? '#1F293D' : '#E2E8F0';
    ctx.lineWidth = 1;
    for (let y = 20; y < height; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    const series = pipelineResult?.telemetry?.series || [];
    if (series.length < 2) return;
    const values = series.map((point) => point.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const points = series.map((point, index) => ({
      x: (width / (series.length - 1)) * index,
      y: height - 20 - ((point.value - min) / span) * (height - 40),
    }));
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, 'rgba(37,99,235,0.12)');
    grad.addColorStop(1, 'rgba(255,255,255,0.0)');
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.beginPath();
    ctx.strokeStyle = '#2563EB';
    ctx.lineWidth = 2;
    ctx.shadowBlur = 0;
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
    ctx.stroke();
  }, [rightTab, currentStepIndex, pipelineResult]);



  const handleTimeFilter = (filter: TimeFilter) => {
    store.setTimeFilter(filter);
    const next = new URLSearchParams(searchParams);
    next.set('range', filter);
    setSearchParams(next, { replace: true });
  };

  const handleAccept = () => {
    setRuleCardState('accepted');
    acceptRule(pushMessage);
  };
  const handleReject = () => {
    setRuleCardState('rejected');
    rejectRule(pushMessage);
  };
  const handleSaveEdit = () => {
    saveRuleEdit(editText);
    setEditOpen(false);
    pushMessage({
      id: `edit-${Date.now()}`,
      agent: 'human',
      text: `Rule conditions updated by Steward: ${editText}`,
    });
  };

  if (isNewChat) return <NewChatLanding />;

  return (
    <div className={`agent-chat-workspace ${rightPanelOpen ? '' : 'right-panel-collapsed'}`}>
      {/* CENTER COLUMN: CHAT STREAM */}
      <div className="center-chat-pane">
        <DemoStoryBar isVi={isVi} />
        {demoMode && (
          <div
            role="status"
            style={{
              margin: '8px 16px 0',
              padding: '8px 12px',
              borderRadius: 8,
              background: 'rgba(217,119,6,0.12)',
              border: '1px solid rgba(217,119,6,0.35)',
              color: 'var(--text-main)',
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            {demoMode === 'replay'
              ? (isVi ? 'DEMO · simulation — băng ghi, không phải số liệu production.' : 'DEMO · simulation — recorded tape, not production metrics.')
              : (isVi ? 'DEMO · bundled — chạy trên vingroup_pilot có sẵn trong repo.' : 'DEMO · bundled — live run on the repo VinGroup pilot.')}
          </div>
        )}
        {/* In-Stream Time Filter Bar */}
        <div className="in-stream-filter-bar">
          <div className="time-filter-left">
            <div className="time-filter-label"><Clock size={13} /> {t('telemetryWindow')}</div>
            <div className="time-filter-pills">
              {(Object.keys(TIME_FILTERS) as TimeFilter[]).map((filter) => (
                <button
                  key={filter}
                  className={`time-pill ${store.timeFilter === filter ? 'active' : ''}`}
                  onClick={() => handleTimeFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          {!rightPanelOpen && (
            <button
              type="button"
              className="btn-expand-inspector"
              onClick={() => setRightPanelOpen(true)}
              aria-label="Expand inspection panel"
              title="Expand inspection panel"
            >
              <ChevronLeft size={13} />
              <span>Inspector</span>
            </button>
          )}
        </div>


        {/* Chat Log Stream Area */}
        <div className="chat-stream" id="chatStream" ref={streamRef}>
          {datasetKey && waitingForBackendAgentEvents && (
            <div className="agent-entry">
              <div className="agent-avatar agent-profiler">
                <ScanSearch size={15} />
              </div>
              <div className="agent-content-box">
                <div className="agent-header">
                  <span className="agent-name" style={{ color: 'var(--royal-purple)' }}>C1 AI</span>
                  <span className="agent-timestamp">—</span>
                </div>
                <div className="agent-body">Waiting for backend agent events...</div>
              </div>
            </div>
          )}
          {stream.map((msg, i) => {
            const Icon = AGENT_ICONS[msg.agent] || Brain;
            const isRule = !!msg.isRule && ruleCardState === 'pending';
            return (
              <div key={`${msg.id}-${i}`} className="agent-entry">
                <div className={`agent-avatar ${AGENT_AVATAR_CLASS[msg.agent] || 'agent-orchestrator'}`}>
                  <Icon size={15} />
                </div>
                <div className="agent-content-box">
                  <div className="agent-header">
                    <span className="agent-name" style={{ color: AGENT_COLORS[msg.agent] || 'var(--text-main)' }}>
                      {AGENT_TITLES[msg.agent] || 'AGENT'}
                    </span>
                    <span className="agent-timestamp">{formatSaigonTime()}</span>
                  </div>
                  <div className="agent-body">
                    <MarkdownContent content={msg.text} />
                    {msg.codeSnippet && (
                      <div className="terminal-block"><span className="log-cyan">{msg.codeSnippet}</span></div>
                    )}
                    {isRule && (
                      <div className="review-card">
                        <div className="review-header">
                          <span className="review-badge"><ShieldCheck size={12} /> {t('governanceCheckpoint')}</span>
                          <span className="review-impact"><Database size={12} /> Impact: {store.quarantineRows} {t('rowsCount')}</span>
                        </div>
                        <div className="review-logic-box">{store.currentRuleLogic}</div>
                        <div className="review-actions">
                          <button className="btn-accept" onClick={handleAccept}><CheckCircle2 size={14} /> {t('acceptExecute')}</button>
                          <button className="btn-edit" onClick={() => { setEditText(store.currentRuleLogic); setEditOpen(true); }}><Pencil size={13} /> {t('editConditions')}</button>
                          <button className="btn-reject" onClick={handleReject}><XCircle size={14} /> {t('reject')}</button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {messagesForStory(chatMessages.filter((msg) => inTimeRange(msg.timestamp, store.timeFilter)), story)
            .filter((msg) => !(msg.content || '').trim().startsWith('Thought:'))
            .map((msg) => {
            const agent = msg.type === 'user' ? 'human' : (msg.agentId || 'orchestrator');
            const Icon = AGENT_ICONS[agent] || Brain;
            const toolName = typeof msg.agentId === 'string' ? msg.agentId : '';
            const chip = catalogFor(toolName);
            const isObservation = (msg.content || '').startsWith('Observation:');
            return (
              <div key={`chat-${msg.id}`} className="agent-entry" data-msgid={msg.id} data-tool={toolName || undefined}>
                <div className={`agent-avatar ${AGENT_AVATAR_CLASS[agent] || 'agent-orchestrator'}`}>
                  <Icon size={15} />
                </div>
                <div className="agent-content-box">
                  <div className="agent-header">
                    <span className="agent-name" style={{ color: AGENT_COLORS[agent] || 'var(--text-main)' }}>
                      {msg.type === 'user' ? 'YOU' : (AGENT_TITLES[agent] || agent.replace(/_/g, ' ').toUpperCase())}
                    </span>
                    <span className="agent-timestamp">{formatSaigonTime(msg.timestamp)}</span>
                  </div>
                  <div className="agent-body">
                    {chip ? (
                      <button
                        type="button"
                        className="used-tool-chip"
                        onClick={() => {
                          setRightTab('tab-traces');
                          setSelectedTraceTool(toolName);
                          setRightPanelOpen(true);
                        }}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          fontSize: 11,
                          fontWeight: 600,
                          padding: '4px 10px',
                          borderRadius: 999,
                          border: '1px solid rgba(2,132,199,0.3)',
                          background: 'rgba(2,132,199,0.08)',
                          color: '#0284c7',
                          cursor: 'pointer',
                          marginBottom: 8,
                        }}
                      >
                        Used {chip.title} — {chip.about}
                      </button>
                    ) : null}
                    {!isObservation && msg.content ? <MarkdownContent content={msg.content} /> : null}
                  </div>
                </div>
              </div>
            );
          })}
          {store.runStatus === 'awaiting_hitl' && !stream.some((m) => m.isRule) && (
            <div className="agent-entry">
              <div className="agent-avatar agent-human"><UserShield size={15} /></div>
              <div className="agent-content-box" style={{ borderColor: 'var(--warning-amber)' }}>
                <div className="agent-header">
                  <span className="agent-name" style={{ color: 'var(--warning-amber)' }}>{t('governanceGate')}</span>
                  <span className="agent-timestamp">{formatSaigonTime()}</span>
                </div>
                <div className="agent-body">
                  ⏸ {t('pipelinePaused')}
                </div>
              </div>
            </div>
          )}

          {/* Quick Action CTA for uploaded/selected dataset */}
          {datasetKey && (
            <div
              className="pipeline-cta-card"
              style={{
                background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.08), rgba(147, 51, 234, 0.08))',
                border: '1px solid rgba(2, 132, 199, 0.25)',
                borderRadius: '12px',
                padding: '14px 18px',
                margin: '12px 0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
                boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ background: 'rgba(2, 132, 199, 0.12)', color: '#0284c7', padding: '9px', borderRadius: '8px' }}>
                  <Sparkles size={18} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>
                    {isVi ? 'Dataset Đã Sẵn Sàng:' : 'Dataset Ready:'} <code>{datasetKey}</code>
                  </div>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {isVi
                      ? 'Tự động khảo sát + đề xuất luật, rồi dừng HITL. Không làm sạch cho đến khi steward duyệt.'
                      : 'Auto profile + propose, then stop at HITL. Nothing is cleaned until you approve.'}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={handleRunFullPipeline}
                disabled={isRunningPipeline}
                style={{
                  background: 'linear-gradient(135deg, #0284c7, #7c3aed)',
                  color: '#ffffff',
                  border: 'none',
                  padding: '8px 18px',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  cursor: isRunningPipeline ? 'not-allowed' : 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 14px rgba(2, 132, 199, 0.25)',
                }}
              >
                <Play size={13} style={{ fill: '#ffffff' }} />
                <span>{isRunningPipeline ? (isVi ? 'Đang chạy...' : 'Running...') : (isVi ? 'Khảo sát + đề xuất (dừng HITL)' : 'Profile & Propose (stop at HITL)')}</span>
              </button>
            </div>
          )}
        </div>

        {/* Chat Input Bar */}
        <div className="chat-input-wrapper">
          <ChatInput datasetKey={datasetKey} onPipelineStarted={() => setRightTab('tab-traces')} />
        </div>
      </div>

      {/* RIGHT PANEL: VISUAL CONTROL ROOM & INSPECTION (4 TABS) */}
      {/* Keep mounted when collapsed — CSS width/transform, do not unmount tab state. */}
      <aside className="right-panel" aria-hidden={!rightPanelOpen}>
          <div className="right-panel-tabs">
            <button
              className={`panel-tab ${rightTab === 'tab-traces' ? 'active' : ''}`}
              onClick={() => setRightTab('tab-traces')}
            >
              <Brain size={13} /> {isVi ? 'Dấu Vết' : 'Traces'}
            </button>
            <button
              className={`panel-tab ${rightTab === 'tab-profiler' ? 'active' : ''}`}
              onClick={() => setRightTab('tab-profiler')}
            >
              <ScanSearch size={13} /> {isVi ? 'Khảo Sát' : 'Profiler'}
            </button>
            <button
              className={`panel-tab ${rightTab === 'tab-rules' ? 'active' : ''}`}
              onClick={() => setRightTab('tab-rules')}
            >
              <ShieldCheck size={13} /> {isVi ? 'Bộ Luật & HITL' : 'Rules & HITL'}
            </button>
            <button
              className={`panel-tab ${rightTab === 'tab-split' ? 'active' : ''}`}
              onClick={() => setRightTab('tab-split')}
            >
              <Database size={13} /> {isVi ? 'Phân Tách DB' : 'Split DB'}
            </button>
            <button
              type="button"
              className="panel-tab-collapse-btn"
              onClick={() => setRightPanelOpen(false)}
              title={isVi ? 'Thu gọn bảng kiểm tra' : 'Collapse Inspector Panel'}
              aria-label="Collapse Inspector Panel"
            >
              <ChevronRight size={14} />
            </button>
          </div>


          <div className="panel-content-body">
            <div hidden={rightTab !== 'tab-traces'}>
              <AgentTracesTab
                datasetKey={datasetKey}
                sessionId={datasetKey ? `dataset:${datasetKey}` : 'default'}
                timeFilter={store.timeFilter}
                replayBeats={isReplay ? replayBeats : undefined}
                selectedStep={selectedTraceStep}
                selectedTool={selectedTraceTool}
                pendingRun={waitingForBackendAgentEvents || isRunningPipeline}
                active={rightTab === 'tab-traces'}
                onSelectStep={(n) => {
                  setSelectedTraceStep(n);
                  setSelectedTraceTool(null);
                }}
              />
            </div>
            <div hidden={rightTab !== 'tab-profiler'}>
              <DataProfilerTab datasetKey={datasetKey} story={story} />
            </div>
            <div hidden={rightTab !== 'tab-rules'}>
              <QualityRulesTab datasetKey={datasetKey} active={rightTab === 'tab-rules'} />
            </div>
            <div hidden={rightTab !== 'tab-split'}>
              <SplitDbQuarantineTab
                datasetKey={datasetKey}
                manifestHash={pipelineResult?.manifest?.hash || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
              />
            </div>
          </div>
        </aside>


      {/* RULE EDIT MODAL */}
      {editOpen && (
        <div className="modal-overlay active" onClick={() => setEditOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title"><Pencil size={16} style={{ display: 'inline', marginRight: 6 }} /> {t('editRuleTitle')}</span>
              <button className="modal-close" onClick={() => setEditOpen(false)}><XCircle size={16} /></button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
              {isVi ? 'Chỉnh sửa điều kiện làm sạch SQL / Python trước khi nạp vào động cơ Pytest.' : 'Modify the SQL / Python cleaning conditions for Rule before signing into Pytest integration engine.'}
            </div>
            <textarea className="modal-textarea" value={editText} onChange={(e) => setEditText(e.target.value)} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="hud-btn" onClick={() => setEditOpen(false)}>{t('cancel')}</button>
              <button className="btn-accept" onClick={handleSaveEdit}><Save size={14} /> {t('applyModifiedRule')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NewChatLanding() {
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const sessionId = useChatStore((s) => s.sessionId);
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const handleSubmit = async (event?: React.FormEvent) => {
    if (event) event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    let targetKey = 'vinfast_ev_telemetry';
    const lower = trimmed.toLowerCase();
    if (lower.includes('vgreen') || lower.includes('v-green') || lower.includes('charg')) {
      targetKey = 'vgreen_charging_stations';
    } else if (lower.includes('xanh') || lower.includes('trip') || lower.includes('taxi')) {
      targetKey = 'xanh_sm_trips';
    } else if (lower.includes('feedback') || lower.includes('review') || lower.includes('nlp')) {
      targetKey = 'xanh_sm_customer_feedback';
    }

    try {
      await sendChatMessage(trimmed, sessionId, targetKey);
      const history = await fetchChatHistory(sessionId);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (e) {
      console.error('Failed to send initial message:', e);
    }
    navigate(`/workspace?dataset_key=${targetKey}`);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.csv', '.db', '.json'].includes(extension)) {
      setUploadError(isVi ? 'Chỉ hỗ trợ file CSV, DB và JSON.' : 'Only CSV, DB, and JSON files are supported.');
      return;
    }
    setUploadError(null);
    setUploading(true);
    try {
      const result = await uploadDatasetFile(file);
      window.dispatchEvent(new CustomEvent('datatrust:dataset-uploaded', { detail: result }));
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : (isVi ? 'Không thể upload database.' : 'Failed to upload database.'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="dash-main new-chat-landing">
      <div className="new-chat-content">
        <div className="panel-title-group new-chat-title">
          <h2>{isVi ? 'Ta nên bắt đầu việc gì?' : 'What would you like to start with?'}</h2>
        </div>
        <form className="new-chat-composer" onSubmit={handleSubmit}>
          <textarea
            className="chat-input new-chat-textarea"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isVi ? 'Làm việc với bất kỳ nội dung nào...' : 'Ask anything or start a workflow...'}
            aria-label="Chat message"
            rows={3}
          />
          <div className="chat-input-bar new-chat-composer-footer">
            <button type="button" className="hud-btn" aria-label="Attach" title="Attach">
              <Plus size={28} strokeWidth={1.8} />
            </button>
            <div className="new-chat-model">DataTrust Agent <span>⌄</span></div>
            <button type="button" className="hud-btn" aria-label="Voice input" title="Voice input">
              <Mic size={24} strokeWidth={1.8} />
            </button>
            <button type="submit" className="send-btn" disabled={!message.trim()} aria-label="Send message" title="Send message">
              <ArrowUp size={26} strokeWidth={2} />
            </button>
          </div>
        </form>
        <div className="new-chat-shortcuts">
          <input ref={fileInputRef} type="file" accept=".csv,.db,.json" hidden onChange={handleUpload} />
          <button
            type="button"
            onClick={async () => {
              try {
                await useAuthStore.getState().login('steward', undefined, 'steward');
                await systemApi.loadSnapshot('happy');
                await resetDemoSession();
                useChatStore.getState().clearMessages();
              } catch { /* still open the story */ }
              navigate('/workspace?dataset_key=vingroup_pilot&story=happy');
            }}
          >
            <ShieldCheck size={22} /> {isVi ? 'HAPPY — bản sạch' : 'HAPPY — clean snapshot'}
          </button>
          <button
            type="button"
            onClick={async () => {
              try {
                await useAuthStore.getState().login('steward', undefined, 'steward');
                await systemApi.loadSnapshot('unhappy');
                await resetDemoSession();
                useChatStore.getState().clearMessages();
              } catch { /* still open the story */ }
              navigate('/workspace?dataset_key=vingroup_pilot&demo=live&story=unhappy');
            }}
          >
            <Play size={22} /> {isVi ? 'UNHAPPY — 172 / 8 OPEN' : 'UNHAPPY — 172 SoC / 8 OPEN'}
          </button>
          <button type="button" onClick={() => navigate('/workspace?dataset_key=vingroup_pilot&demo=replay')}>
            <Sparkles size={22} /> {isVi ? 'Replay phiên ghi' : 'Replay recorded session'}
          </button>
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            <CloudUpload size={22} /> {uploading ? (isVi ? 'Đang tải database...' : 'Uploading database...') : (isVi ? 'Tải file của bạn' : 'Upload your file')}
          </button>
        </div>
        {uploadError && <div className="new-chat-upload-error" role="alert">{uploadError}</div>}
      </div>
    </main>
  );
}
