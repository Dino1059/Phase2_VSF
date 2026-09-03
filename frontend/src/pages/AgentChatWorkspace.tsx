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
  Plus,
  Mic,
  ArrowUp,
  CloudUpload,
  ChevronLeft,
  ChevronRight,
  Play,
  Sparkles,
  Activity,
  Brain,
  ScanSearch,
} from 'lucide-react';
import { usePipelineStore, DOMAIN_LIST } from '../stores/pipelineStore';
import { useIngestionStore } from '../stores/ingestionStore';
import { SourceIngestionRunFilter } from '../components/chat/SourceIngestionRunFilter';

import { usePipelineRun, StreamMessage } from '../hooks/usePipelineRun';
import { ChatInput } from '../components/chat/ChatInput';
import { MarkdownContent } from '../components/chat/MarkdownContent';
import { SessionSwitcher } from '../components/chat/SessionSwitcher';
import { AgentTracesTab } from '../components/workspace/AgentTracesTab';
import { DataProfilerTab } from '../components/workspace/DataProfilerTab';
import { QualityRulesTab } from '../components/workspace/QualityRulesTab';
import { SplitDbQuarantineTab } from '../components/workspace/SplitDbQuarantineTab';
import { fetchChatHistory, pipelineApi, uploadDatasetFile, sendChatMessage, resetDemoSession, ingestionApi } from '../services/api';
import { calendarDayToDayIdx, dayIdxToCalendarDay } from '../lib/calendarDay';
import { agentSocket } from '../services/websocket';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import { inTimeRange, catalogFor, formatRelativeTime } from '../demo/stewardLabels';
// import { DemoStoryBar } from '../demo/DemoStoryBar';
import { STEWARD_SESSION_BEATS, type DemoBeat } from '../demo/stewardSession';

function toolFromMessage(msg: { agentId?: string; content?: string; agent?: string }): string {
  const id = (msg.agentId || msg.agent || '').trim();
  if (id && id !== 'orchestrator' && id !== 'human') return id;
  const c = msg.content || '';
  if (c.includes('Profile Summary') || c.includes('Tóm Tắt Khảo Sát') || c.includes('profile_dataset')) return 'profile_dataset';
  if (c.includes('Quality Rule Proposals') || c.includes('Đề Xuất Luật Chất Lượng') || c.includes('propose_quality_rules')) return 'propose_quality_rules';
  if (c.includes('Cleansing & Quarantine Complete') || c.includes('clean_database')) return 'clean_database';
  return id;
}

function messagesForStory<T extends { content?: string }>(messages: T[], _story?: string | null): T[] {
  return messages.filter((m) => !(m.content || '').includes('HAPPY · clean CSVs'));
}

const HITL_STOP_PROMPT_EN =
  'Profile this dataset, detect anomalies L1-L4, and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review.';
const HITL_STOP_PROMPT_VI =
  'Khảo sát dữ liệu, phát hiện bất thường L1-L4, và đề xuất luật chất lượng. Không làm sạch, không cách ly, không thực thi. Dừng lại để steward duyệt HITL.';

type RightTab = 'tab-traces' | 'tab-profiler' | 'tab-rules' | 'tab-split';

/** Survives StrictMode remount. Tab show / remount must not POST a second HITL chat. */
const hitlBootsInFlight = new Set<string>();

export function AgentChatWorkspace() {
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const datasetKey = searchParams.get('dataset_key') || searchParams.get('table') || undefined;
  const canAccessDs = useAuthStore((s) => s.canAccessDataset(datasetKey));
  const isAuthed = useAuthStore((s) => s.isAuthenticated);
  const aclDenied = Boolean(isAuthed && datasetKey && !canAccessDs);
  const demoMode = searchParams.get('demo');
  const story = searchParams.get('story');
  const dayParam = searchParams.get('day') || searchParams.get('day_idx');
  const runIdParam = searchParams.get('run_id') || searchParams.get('source_ingestion_run_id');
  const isHappy = story === 'happy';
  const isReplay = demoMode === 'replay';
  const isNewChat = searchParams.has('new') || (!datasetKey && !id);
  const liveChatSessionId = useChatStore((s) => s.sessionId);
  const chatMessages = useChatStore((s) => s.messages);
  const store = usePipelineStore();
  const tabParam = searchParams.get('tab');
  const calendarDay = dayParam && dayParam.includes('-')
    ? dayParam
    : dayIdxToCalendarDay(dayParam != null ? parseInt(dayParam, 10) : store.selectedDayIdx);

  useEffect(() => {
    if (dayParam !== null && dayParam !== undefined && dayParam !== '') {
      if (dayParam.includes('-')) {
        const idx = calendarDayToDayIdx(dayParam);
        if (idx !== null) store.setSelectedDayIdx(idx);
        store.setSourceIngestionRunId(dayParam);
        store.setRunId(dayParam);
      } else {
        const parsedDay = parseInt(dayParam, 10);
        if (!isNaN(parsedDay)) {
          store.setSelectedDayIdx(parsedDay);
          const day = dayIdxToCalendarDay(parsedDay);
          if (day) {
            store.setSourceIngestionRunId(day);
            store.setRunId(day);
          }
        }
      }
    }
    if (runIdParam && !dayParam?.includes('-')) {
      store.setSourceIngestionRunId(runIdParam);
      store.setRunId(runIdParam);
    }
  }, [dayParam, runIdParam]);

  useEffect(() => {
    if (!datasetKey) return;
    void useChatStore.getState().bindAxis(datasetKey, calendarDay || undefined);
  }, [datasetKey, calendarDay]);

  useEffect(() => {
    if (tabParam === 'tab-traces' || tabParam === 'tab-profiler' || tabParam === 'tab-rules' || tabParam === 'tab-split') {
      setRightTab(tabParam);
      setRightPanelOpen(true);
    }
  }, [tabParam]);

  const executionStage = useIngestionStore((s) => s.executionStage);
  const activeDayIdx = useIngestionStore((s) => s.activeDayIdx);
  const ingestionError = useIngestionStore((s) => s.error);

  const getStageMessage = useCallback((stage: string) => {
    switch (stage) {
      case 'ingesting':
        return isVi
          ? '📥 Bước 1/4: Đang nạp Landing Data Snapshot (Parquet)...'
          : '📥 Step 1/4: Ingesting Landing Data Snapshot (Parquet)...';
      case 'batch_analyzing':
        return isVi
          ? '⚙️ Bước 2/4: Đang chạy Batch Pipeline (Profiling + Phân tích Anomaly L1–L4)...'
          : '⚙️ Step 2/4: Running Batch Pipeline (Profiling + Anomaly Detection L1-L4)...';
      case 'evaluating_rules':
        return isVi
          ? '🚨 Bước 3/4: Đang đánh giá Rules & Dispatching Alerts...'
          : '🚨 Step 3/4: Evaluating Rules & Dispatching Alerts...';
      case 'starting_realtime':
        return isVi
          ? '⚡ Bước 4/4: Đang kích hoạt Realtime Stream Telemetry...'
          : '⚡ Step 4/4: Starting Realtime Stream Telemetry...';
      case 'completed':
        return isVi
          ? '✅ Hoàn thành phân tích End-to-End Batch! Stream sẵn sàng.'
          : '✅ End-to-End Analysis Complete! Stream Active.';
      case 'failed':
        return isVi
          ? `❌ Lỗi khi thực thi Day: ${ingestionError || ''}`
          : `❌ Execution failed for Day: ${ingestionError || ''}`;
      default:
        return null;
    }
  }, [i18n.language, ingestionError]);
  const domainId = store.domainId;
  const currentStepIndex = store.currentStepIndex;
  const currentRuleLogic = store.currentRuleLogic;
  const setDomain = usePipelineStore((s) => s.setDomain);
  const resetPipeline = usePipelineStore((s) => s.resetPipeline);
  const { acceptRule, rejectRule, saveRuleEdit, clearTimers } = usePipelineRun(datasetKey);
  const [stream, setStream] = useState<StreamMessage[]>([]);
  const [rightTab, setRightTab] = useState<RightTab>(() => {
    const t = new URLSearchParams(window.location.search).get('tab');
    return (t === 'tab-traces' || t === 'tab-profiler' || t === 'tab-rules' || t === 'tab-split') ? t : 'tab-profiler';
  });
  const [rightPanelOpen, setRightPanelOpen] = useState(
    () => typeof window === 'undefined' || window.innerWidth >= 900,
  );
  const [editOpen, setEditOpen] = useState(false);

  const [editText, setEditText] = useState(currentRuleLogic);
  const [ruleCardState, setRuleCardState] = useState<'pending' | 'accepted' | 'rejected'>('pending');
  const [pipelineResult, setPipelineResult] = useState<Awaited<ReturnType<typeof pipelineApi.result>> | null>(null);
  const [waitingForBackendAgentEvents] = useState(false);
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
    if (isRunningPipeline) return;
    setIsRunningPipeline(true);
    try {
      const lang = i18n?.language || 'vi';
      const prompt = lang === 'vi' ? HITL_STOP_PROMPT_VI : HITL_STOP_PROMPT_EN;
      const currentSession = useChatStore.getState().sessionId;
      agentSocket.connect(currentSession);
      const dayIdx = usePipelineStore.getState().selectedDayIdx;
      if (dayIdx !== null && dayIdx !== undefined) {
        await ingestionApi.promote(dayIdx).catch(() => null);
      }
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
  }, [datasetKey, i18n, isRunningPipeline]);

  const [pipelineToast, setPipelineToast] = useState<{ message: string; details?: any } | null>(null);

  // Context-Aware Auto-Switch: smooth single switch when pipeline is idle/completed
  const lastSwitchKeyRef = useRef('');
  useEffect(() => {
    if (isRunningPipeline || waitingForBackendAgentEvents) return;
    if (chatMessages.length === 0) return;
    const lastMsg = chatMessages[chatMessages.length - 1];
    if (lastMsg.type === 'agent') {
      const msgId = lastMsg.id || `${chatMessages.length}-${lastMsg.content?.slice(0, 10)}`;
      if (lastSwitchKeyRef.current === msgId) return;
      lastSwitchKeyRef.current = msgId;

      const content = lastMsg.content || '';
      if (content.includes('Cleansing & Quarantine Complete') || content.includes('clean_database') || content.includes('Làm Sạch') || content.includes('Làm sạch')) {
        setRightTab('tab-split');
      } else if (content.includes('Quality Rule Proposals') || content.includes('propose_quality_rules') || content.includes('Đề Xuất Luật') || content.includes('Đề xuất luật')) {
        setRightTab('tab-rules');
      } else if (content.includes('Dị Thường') || content.includes('detect_anomalies') || content.includes('Anomaly') || content.includes('Incidents')) {
        setRightTab('tab-traces');
      } else if (content.includes('Profile Summary') || content.includes('profile_dataset') || content.includes('Khảo sát') || content.includes('Khảo Sát')) {
        setRightTab('tab-profiler');
      }
    }
  }, [chatMessages, isRunningPipeline, waitingForBackendAgentEvents, executionStage]);

  useEffect(() => {
    const handleToast = (ev: Event) => {
      const detail = (ev as CustomEvent).detail || {};
      const dayStr = detail.day_idx !== undefined && detail.day_idx !== null ? `Day ${detail.day_idx}` : '';
      const summary = detail.summary || {};
      const rows = summary.ingested_rows ?? 0;
      const incidents = summary.incidents ?? 0;
      const msg = isVi
        ? `${dayStr ? `${dayStr} — ` : ''}Phân tích hoàn tất: ${rows.toLocaleString()} dòng dữ liệu, ${incidents} sự cố phát hiện.`
        : `${dayStr ? `${dayStr} — ` : ''}Analysis complete: ${rows.toLocaleString()} rows ingested, ${incidents} incidents found.`;
      setPipelineToast({ message: msg, details: detail });
      const timer = setTimeout(() => setPipelineToast(null), 6000);
      return () => clearTimeout(timer);
    };
    window.addEventListener('datatrust:pipeline-completed-toast', handleToast);
    return () => window.removeEventListener('datatrust:pipeline-completed-toast', handleToast);
  }, [isVi]);

  useEffect(() => {
    const onSandbox = (ev: Event) => {
      const d = (ev as CustomEvent).detail || {};
      if (d.sandbox || d.cleanRan || (Array.isArray(d.quarantine) && d.quarantine.length) || (Array.isArray(d.clean) && d.clean.length)) {
        setRightTab('tab-split');
      }
    };
    window.addEventListener('datatrust:sandbox-split', onSandbox as EventListener);
    const onHitlFocus = () => setRightTab('tab-rules');
    window.addEventListener('datatrust:hitl-apply-pending', onHitlFocus);
    window.addEventListener('datatrust:hitl-edit-focus', onHitlFocus);
    window.addEventListener('datatrust:split-refresh', onSandbox as EventListener);
    return () => {
      window.removeEventListener('datatrust:sandbox-split', onSandbox as EventListener);
      window.removeEventListener('datatrust:split-refresh', onSandbox as EventListener);
      window.removeEventListener('datatrust:hitl-apply-pending', onHitlFocus);
      window.removeEventListener('datatrust:hitl-edit-focus', onHitlFocus);
    };
  }, []);

  // Live chat session (SessionSwitcher). Do not overwrite with dataset:<key>.
  useEffect(() => {
    if (isNewChat) {
      resetPipeline();
      agentSocket.connect(useChatStore.getState().sessionId || 'default');
      return;
    }
    const sessionId = liveChatSessionId || 'default';
    agentSocket.connect(sessionId);
    void fetchChatHistory(sessionId).then((history) => {
      if (Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    }).catch((error) => {
      console.error('Failed to load chat history:', error);
    });
  }, [liveChatSessionId, isNewChat, resetPipeline]);

  useEffect(() => {
    const handleDbReset = () => {
      resetPipeline();
      setStream([]);
      setPipelineResult(null);
      useChatStore.getState().clearMessages();
    };
    window.addEventListener('datatrust:db-reset', handleDbReset);
    return () => window.removeEventListener('datatrust:db-reset', handleDbReset);
  }, [resetPipeline]);

  useEffect(() => {
    const handleDayActivated = () => {
      const currentSession = useChatStore.getState().sessionId;
      fetchChatHistory(currentSession).then((history) => {
        if (Array.isArray(history.messages)) {
          useChatStore.getState().setMessages(history.messages);
        }
      }).catch(() => {});
    };
    window.addEventListener('datatrust:day-activated', handleDayActivated);
    return () => window.removeEventListener('datatrust:day-activated', handleDayActivated);
  }, []);

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
    if (isNewChat || aclDenied) return;
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

    const bootstrap = async () => {
      if (!datasetKey) return;
      try {
        const session = datasetKey ? `dataset:${datasetKey}` : useChatStore.getState().sessionId;
        const existing = await fetchChatHistory(session);
        if (Array.isArray(existing.messages) && existing.messages.length) {
          useChatStore.getState().setMessages(existing.messages);
        }
      } catch {
        /* ignore */
      }
    };
    void bootstrap();
    return () => clearTimers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainId, datasetKey, isNewChat, isReplay, isHappy, bootToken, aclDenied]);

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
        {/* <DemoStoryBar isVi={isVi} /> */}
        {/* Active E2E Stepper Banner inside Agent Chat Workspace */}
        {(executionStage !== 'idle' || activeDayIdx !== null) && (
          <div className="timeline-stepper-banner" style={{ margin: '8px 16px 8px' }}>
            <div className="tsb-header">
              {executionStage === 'completed' ? (
                <CheckCircle2 size={15} color="var(--electric-green)" />
              ) : executionStage === 'failed' ? (
                <XCircle size={15} color="var(--alert-red, #EF4444)" />
              ) : (
                <Activity size={15} className="spin" color="var(--neon-cyan)" />
              )}
              <span className="tsb-title">
                {isVi
                  ? `Luồng Thực Thi End-to-End — Day ${activeDayIdx ?? (dayParam === '-10' ? '0–9 (Warmup)' : dayParam || '')}`
                  : `End-to-End Execution Flow — Day ${activeDayIdx ?? (dayParam === '-10' ? '0–9 (Warmup)' : dayParam || '')}`}
              </span>
              {executionStage !== 'idle' && executionStage !== 'completed' && executionStage !== 'failed' && (
                <span className="l-pill l1" style={{ fontSize: 10, padding: '2px 8px', marginLeft: 'auto' }}>
                  RUNNING
                </span>
              )}
            </div>

            {executionStage !== 'idle' && (
              <>
                <div className="tsb-message">{getStageMessage(executionStage)}</div>
                <div className="tsb-steps-bar">
                  <div className={`tsb-step ${['ingesting', 'batch_analyzing', 'evaluating_rules', 'starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
                    <span className="step-num">1</span>
                    <span className="step-label">Ingest Snapshot</span>
                  </div>
                  <div className="tsb-step-divider" />
                  <div className={`tsb-step ${['batch_analyzing', 'evaluating_rules', 'starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
                    <span className="step-num">2</span>
                    <span className="step-label">Batch Profiling & Anomaly</span>
                  </div>
                  <div className="tsb-step-divider" />
                  <div className={`tsb-step ${['evaluating_rules', 'starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
                    <span className="step-num">3</span>
                    <span className="step-label">Rules & Alert Dispatch</span>
                  </div>
                  <div className="tsb-step-divider" />
                  <div className={`tsb-step ${['starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
                    <span className="step-num">4</span>
                    <span className="step-label">Realtime Stream Active</span>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
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
        {/* Day History Ingestion Control Header Bar */}
        <div className="in-stream-filter-bar">
          <div className="time-filter-left">
            <SessionSwitcher />
            <SourceIngestionRunFilter
              datasetKey={datasetKey}
              value={store.sourceIngestionRunId}
              onChange={(runId) => {
                store.setSourceIngestionRunId(runId);
                const next = new URLSearchParams(searchParams);
                if (runId) {
                  next.set('day', runId);
                  next.set('run_id', runId);
                } else {
                  next.delete('day');
                  next.delete('run_id');
                }
                setSearchParams(next, { replace: true });
              }}
            />
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
            <div className="agent-entry ai-entry">
              <div className="agent-content-box">
                <div className="agent-body">Waiting for backend agent events...</div>
              </div>
            </div>
          )}
          {stream.map((msg, i) => {
            const isRule = !!msg.isRule && ruleCardState === 'pending';
            return (
              <div key={`${msg.id}-${i}`} className="agent-entry ai-entry" data-msgid={msg.id} data-tool={toolFromMessage({ agent: msg.agent, content: msg.text })}>
                <div className="agent-content-box">
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
                        <div className="review-actions" hidden data-testid="chat-hitl-hidden">
                          <button type="button" className="btn-accept" tabIndex={-1} onClick={handleAccept}><CheckCircle2 size={14} /> {t('acceptExecute')}</button>
                          <button type="button" className="btn-edit" tabIndex={-1} onClick={() => { setEditText(store.currentRuleLogic); setEditOpen(true); }}><Pencil size={13} /> {t('editConditions')}</button>
                          <button type="button" className="btn-reject" tabIndex={-1} onClick={handleReject}><XCircle size={14} /> {t('reject')}</button>
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
              const isUser = msg.type === 'user';
              const toolName = toolFromMessage(msg);
              const chip = catalogFor(toolName);
              const isObservation = (msg.content || '').startsWith('Observation:');
              return (
                <div key={`chat-${msg.id}`} className={`agent-entry ${isUser ? 'user-entry' : 'ai-entry'}`} data-msgid={msg.id} data-tool={toolName || undefined}>
                  <div className="agent-content-box">
                    <div className="agent-body">
                      {chip ? (
                        <button
                          type="button"
                          className="used-tool-chip"
                          data-msgid={msg.id}
                          data-tool={toolName || undefined}
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
                  {isUser && msg.timestamp && (
                    <div className="user-time-stamp">{formatRelativeTime(msg.timestamp, isVi)}</div>
                  )}
                </div>
              );
            })}
          {store.runStatus === 'awaiting_hitl' && !stream.some((m) => m.isRule) && (
            <div className="agent-entry ai-entry">
              <div className="agent-content-box" style={{ borderColor: 'var(--warning-amber)' }}>
                <div className="agent-body">
                  ⏸ {t('pipelinePaused')}
                </div>
              </div>
            </div>
          )}

          {/* Quick Action CTA for uploaded/selected dataset */}
          {aclDenied && (
            <div className="pipeline-cta-card" data-testid="acl-denied" style={{ padding: '14px 18px', margin: '12px 0', border: '1px solid rgba(220,38,38,0.35)', borderRadius: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>
                {isVi ? 'Không có quyền dataset' : 'ACL denied'} <code>{datasetKey}</code>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                {isVi ? 'Steward này không được mở dataset này.' : 'This steward cannot open this dataset.'}
              </div>
            </div>
          )}
          {datasetKey && !aclDenied && (
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
                      ? 'Tự động Khảo sát + Phát hiện Anomaly L1–L4 + Đề xuất luật (dừng HITL). Không làm sạch cho đến khi steward duyệt.'
                      : 'Auto Profile + Anomaly L1–L4 + Propose (stop at HITL). Nothing is cleaned until you approve.'}
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
                <span>{isRunningPipeline ? (isVi ? 'Đang chạy...' : 'Running...') : (isVi ? 'Khảo sát + Anomaly L1–L4 + Đề xuất' : 'Profile + Anomaly L1–L4 + Propose')}</span>
              </button>
            </div>
          )}
        </div>

        {!aclDenied && (
        <div className="chat-input-wrapper">
          <ChatInput datasetKey={datasetKey} onPipelineStarted={() => setRightTab('tab-traces')} />
        </div>
        )}
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
          {aclDenied ? (
            <div style={{ padding: 16, fontSize: 13, color: 'var(--text-muted)' }}>
              {isVi ? 'Inspector ẩn — không có quyền dataset.' : 'Inspector hidden — dataset not in ACL.'}
            </div>
          ) : (
          <>
          <div hidden={rightTab !== 'tab-traces'}>
            <AgentTracesTab
              datasetKey={datasetKey}
              sessionId={liveChatSessionId || 'default'}
              timeFilter={store.timeFilter}
              replayBeats={isReplay ? replayBeats : undefined}
              selectedStep={selectedTraceStep}
              selectedTool={selectedTraceTool}
              pendingRun={waitingForBackendAgentEvents || isRunningPipeline}
              active={rightTab === 'tab-traces'}
              dayIdx={store.selectedDayIdx ?? calendarDayToDayIdx(calendarDay)}
              runId={store.sourceIngestionRunId || store.runId || calendarDay}
              onSelectStep={(n) => {
                setSelectedTraceStep(n);
                setSelectedTraceTool(null);
              }}
            />
          </div>
          <div hidden={rightTab !== 'tab-profiler'}>
            <DataProfilerTab datasetKey={datasetKey} story={story} active={rightTab === 'tab-profiler'} dayIdx={store.selectedDayIdx ?? calendarDayToDayIdx(calendarDay)} runId={store.sourceIngestionRunId || store.runId || calendarDay} />
          </div>
          <div hidden={rightTab !== 'tab-rules'}>
            <QualityRulesTab datasetKey={datasetKey} active={rightTab === 'tab-rules'} dayIdx={store.selectedDayIdx ?? calendarDayToDayIdx(calendarDay)} runId={store.sourceIngestionRunId || store.runId || calendarDay} highlightRuleId={searchParams.get('rule_id')} />
          </div>
          <div hidden={rightTab !== 'tab-split'}>
            <SplitDbQuarantineTab
              datasetKey={datasetKey}
              manifestHash={pipelineResult?.manifest?.hash || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
              active={rightTab === 'tab-split'}
              splitResult={pipelineResult?.split}
              dayIdx={store.selectedDayIdx ?? calendarDayToDayIdx(calendarDay)}
              runId={store.sourceIngestionRunId || store.runId || calendarDay}
            />
          </div>
          </>
          )}
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

      {/* PIPELINE COMPLETION TOAST */}
      {pipelineToast && (
        <div
          role="status"
          className="pipeline-completed-toast"
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 99,
            background: 'rgba(15, 23, 42, 0.92)',
            border: '1px solid var(--electric-green, #10b981)',
            backdropFilter: 'blur(8px)',
            color: '#ffffff',
            padding: '12px 18px',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.4)',
            animation: 'fadeInUp 0.3s ease-out',
          }}
        >
          <span style={{ display: 'inline-flex', width: 8, height: 8, borderRadius: '50%', background: '#10b981' }} />
          <span>{pipelineToast.message}</span>
          <button
            type="button"
            onClick={() => setPipelineToast(null)}
            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', marginLeft: 8, padding: 2 }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}

function NewChatLanding() {
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [resetToast, setResetToast] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const sessionId = useChatStore((s) => s.sessionId);
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  // Header toast is local state; navigate to ?new=1 remounts it. Re-show from sessionStorage.
  useEffect(() => {
    try {
      if (sessionStorage.getItem('dt-reset-toast')) {
        setResetToast(true);
        const timer = setTimeout(() => {
          setResetToast(false);
          try { sessionStorage.removeItem('dt-reset-toast'); } catch { /* ignore */ }
        }, 3500);
        return () => clearTimeout(timer);
      }
    } catch {
      /* ignore */
    }
    return undefined;
  }, []);

  const handleSubmit = useCallback(async (event?: React.FormEvent) => {
    if (event) event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    let targetKey = 'vinfast_ev_telemetry';
    const lower = trimmed.toLowerCase();
    if (lower.includes('vgreen') || lower.includes('v-green') || lower.includes('charg')) {
      targetKey = 'charging_sessions';
    } else if (lower.includes('xanh') || lower.includes('trip') || lower.includes('taxi')) {
      targetKey = 'trips';
    } else if (lower.includes('feedback') || lower.includes('review') || lower.includes('nlp')) {
      targetKey = 'nlp_feedback';
    }

    try {
      await sendChatMessage(trimmed, sessionId, targetKey, i18n.language);
      const history = await fetchChatHistory(sessionId);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (e) {
      console.error('Failed to send initial message:', e);
    }
    navigate(`/workspace?dataset_key=${targetKey}`);
  }, [message, sessionId, i18n.language, navigate]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }, [handleSubmit]);

  const handleUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
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
  }, [isVi]);

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
                if (!useAuthStore.getState().isAdmin()) {
                  await useAuthStore.getState().login('steward', undefined, 'steward');
                }
                await resetDemoSession();
                useChatStore.getState().clearMessages();
              } catch { /* ignore */ }
              navigate('/workspace?dataset_key=ev_telemetry');
            }}
          >
            <Play size={22} /> {isVi ? 'Phân tích Dataset VinFast EV' : 'Analyze VinFast EV Dataset'}
          </button>
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            <CloudUpload size={22} /> {uploading ? (isVi ? 'Đang tải database...' : 'Uploading database...') : (isVi ? 'Tải file dữ liệu' : 'Upload data file')}
          </button>
        </div>
        {uploadError && <div className="new-chat-upload-error" role="alert">{uploadError}</div>}
      </div>
      {resetToast && (
        <div
          role="status"
          className="reset-toast"
          style={{
            position: 'fixed',
            top: 72,
            right: 16,
            zIndex: 80,
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid var(--electric-green)',
            color: 'var(--electric-green)',
            padding: '10px 14px',
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 700,
            boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
          }}
        >
          {isVi ? 'Toast: Đã đặt lại DB · HITL 0/0 · Split 0' : 'Toast: Database reset · HITL 0/0 · Split 0'}
        </div>
      )}
    </main>
  );
}

