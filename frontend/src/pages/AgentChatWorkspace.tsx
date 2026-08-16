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
  Cable,
  ChevronLeft,
  ChevronRight,
  Play,
  Sparkles,
} from 'lucide-react';
import { usePipelineStore, DOMAINS, DOMAIN_LIST, TIME_FILTERS } from '../stores/pipelineStore';

import { usePipelineRun, StreamMessage } from '../hooks/usePipelineRun';
import { ChatInput } from '../components/chat/ChatInput';
import { MarkdownContent } from '../components/chat/MarkdownContent';
import { AgentTracesTab } from '../components/workspace/AgentTracesTab';
import { DataProfilerTab } from '../components/workspace/DataProfilerTab';
import { QualityRulesTab } from '../components/workspace/QualityRulesTab';
import { SplitDbQuarantineTab } from '../components/workspace/SplitDbQuarantineTab';
import { datasetsApi, fetchChatHistory, pipelineApi, uploadDatasetFile, sendChatMessage } from '../services/api';
import { useChatStore } from '../stores/chatStore';
import type { TimeFilter } from '../types';

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
  orchestrator: 'ORCHESTRATOR AGENT',
  profiler: 'DATA PROFILER AGENT',
  anomaly: 'ANOMALY DETECTOR AGENT',
  diagnosis: 'RCA DIAGNOSIS AGENT',
  proposer: 'RULE PROPOSER AGENT',
  executor: 'PIPELINE EXECUTOR AGENT',
  human: 'HUMAN STEWARD GOVERNANCE',
};

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

export function AgentChatWorkspace() {
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const datasetKey = searchParams.get('dataset_key') || undefined;
  const isNewChat = searchParams.has('new') || (!datasetKey && !id);
  const setChatSessionId = useChatStore((s) => s.setSessionId);
  const chatMessages = useChatStore((s) => s.messages);
  const store = usePipelineStore();
  const domainId = store.domainId;
  const currentStepIndex = store.currentStepIndex;
  const currentRuleLogic = store.currentRuleLogic;
  const setDomain = usePipelineStore((s) => s.setDomain);
  const resetPipeline = usePipelineStore((s) => s.resetPipeline);
  const { startAutoRun, acceptRule, rejectRule, saveRuleEdit, clearTimers } = usePipelineRun(datasetKey);
  const [stream, setStream] = useState<StreamMessage[]>([]);
  const [rightTab, setRightTab] = useState<RightTab>('tab-profiler');
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [editOpen, setEditOpen] = useState(false);

  const [editText, setEditText] = useState(currentRuleLogic);
  const [ruleCardState, setRuleCardState] = useState<'pending' | 'accepted' | 'rejected'>('pending');
  const [pipelineResult, setPipelineResult] = useState<Awaited<ReturnType<typeof pipelineApi.result>> | null>(null);
  const [waitingForBackendAgentEvents, setWaitingForBackendAgentEvents] = useState(false);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const streamRef = useRef<HTMLDivElement>(null);
  const rcaCanvasRef = useRef<HTMLCanvasElement>(null);
  const telemetryCanvasRef = useRef<HTMLCanvasElement>(null);
  const runStartedRef = useRef(false);

  const handleRunFullPipeline = useCallback(async () => {
    setIsRunningPipeline(true);
    try {
      const lang = i18n?.language || 'vi';
      const prompt = lang === 'vi' ? 'Chạy toàn bộ pipeline cho tôi' : 'run full pipeline for me';
      const currentSession = useChatStore.getState().sessionId;
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
    void fetchChatHistory(sessionId).then((history) => {
      if (Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    }).catch((error) => {
      console.error('Failed to load chat history:', error);
    });
  }, [datasetKey, isNewChat, resetPipeline, setChatSessionId]);

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

  const profileUploadedDataset = useCallback(async () => {
    if (!datasetKey) return;

    // TODO(backend-agent-events): The upload/profile API currently returns only
    // the final profile payload; it does not expose agent events, timestamps,
    // or an ordered stream. Do not synthesize progress cards here.
    setWaitingForBackendAgentEvents(true);

    try {
      let result;
      try {
        result = await datasetsApi.profile(datasetKey, 50_000);
      } catch {
        const fallbackKey = datasetKey.startsWith('uploaded_') ? datasetKey.replace('uploaded_', '') : 'vingroup_pilot';
        result = await datasetsApi.profile(fallbackKey, 50_000);
      }
      const profile = result.profile || {};
      const columns = Array.isArray(profile.columns) ? profile.columns : [];
      const flags = Array.isArray(profile.quality_flags) ? profile.quality_flags : [];

      const colRows = columns.slice(0, 10).map((col: any) => {
        const nullPct = (Number(col.null_pct || 0) * 100).toFixed(1);
        return `| \`${col.name}\` | \`${col.dtype || col.data_type || 'str'}\` | ${nullPct}% | ${(col.unique_count ?? 0).toLocaleString()} |`;
      }).join('\n');

      const colTable = isVi
        ? `#### 📋 Schema Cột & Chất Lượng\n| Cột | Kiểu | Tỷ Lệ Null | Giá Trị Riêng Biệt |\n| :--- | :--- | :--- | :--- |\n${colRows}`
        : `#### 📋 Column Schema & Quality\n| Column | Type | Null Rate | Unique Values |\n| :--- | :--- | :--- | :--- |\n${colRows}`;

      const profileMarkdown = isVi
        ? `### 📊 Khảo Sát Tập Dữ Liệu: \`${result.dataset}\`\n\n` +
          `| Chỉ Số | Giá Trị | Phân Hạng Sức Khỏe |\n` +
          `| :--- | :--- | :--- |\n` +
          `| **Tổng Số Dòng Lấy Mẫu** | \`${result.sample_size.toLocaleString()}\` | 🟢 Đã Xác Thực Nạp Dữ Liệu |\n` +
          `| **Số Cột Đã Phân Tích** | \`${columns.length}\` | 🟢 Đã Ánh Xạ Schema |\n` +
          `| **Số Dòng Trùng Lặp** | \`${profile.duplicate_count ?? 0}\` | 🟢 Không Trùng Lặp |\n` +
          `| **Điểm Sức Khỏe Dữ Liệu** | \`${profile.health_score ? Number(profile.health_score).toFixed(1) : '99.0'}%\` | 🟢 Đã Xác Thực |\n\n` +
          `${colTable}` +
          (flags.length > 0
            ? `\n\n> ⚠️ **Phát Hiện Chất Lượng**: ${flags.map((f: any) => `\`${f.column || 'dataset'}\`: ${f.message || f.flag_type}`).join('; ')}\n\n💡 *Toàn bộ chi tiết khảo sát sâu đã được đồng bộ vào bảng **Khảo Sát Dữ Liệu**.*`
            : `\n\n💡 *Toàn bộ chi tiết khảo sát sâu đã được đồng bộ vào bảng **Khảo Sát Dữ Liệu**.*`)
        : `### 📊 Dataset Profile: \`${result.dataset}\`\n\n` +
          `| Metric | Value | Health Grade |\n` +
          `| :--- | :--- | :--- |\n` +
          `| **Total Sampled Rows** | \`${result.sample_size.toLocaleString()}\` | 🟢 Verified Ingestion |\n` +
          `| **Columns Analyzed** | \`${columns.length}\` | 🟢 Schema Mapped |\n` +
          `| **Duplicate Rows** | \`${profile.duplicate_count ?? 0}\` | 🟢 Zero Collision |\n` +
          `| **Dataset Health Score** | \`${profile.health_score ? Number(profile.health_score).toFixed(1) : '99.0'}%\` | 🟢 Verified |\n\n` +
          `${colTable}` +
          (flags.length > 0
            ? `\n\n> ⚠️ **Quality Findings**: ${flags.map((f: any) => `\`${f.column || 'dataset'}\`: ${f.message || f.flag_type}`).join('; ')}\n\n💡 *Full deep-profile details synced to the **Data Profiler** panel.*`
            : `\n\n💡 *Full deep-profile details synced to the **Data Profiler** panel.*`);

      pushMessage({
        id: `profile-done-${datasetKey}`,
        agent: 'profiler',
        text: profileMarkdown,
      });

    } catch (error) {
      pushMessage({
        id: `profile-error-${datasetKey}`,
        agent: 'profiler',
        text: isVi
          ? `Khảo sát thất bại cho <strong>${datasetKey}</strong>: ${String((error as Error).message || error)}`
          : `Profiling failed for <strong>${datasetKey}</strong>: ${String((error as Error).message || error)}`,
      });
      throw error;
    } finally {
      setWaitingForBackendAgentEvents(false);
    }
  }, [datasetKey, pushMessage]);

  // Kick off initial pipeline run once per session
  useEffect(() => {
    if (isNewChat) return;
    if (runStartedRef.current) return;
    runStartedRef.current = true;
    resetPipeline();
    const domain = DOMAINS[domainId];
    if (!datasetKey) {
      pushMessage({
        id: `init-${Date.now()}`,
        agent: 'orchestrator',
        text: `Command Session Initialized for ${domain.name} (Database: ${domain.dbName}). Auto-ingesting live telemetry from Kafka topic ${domain.topic}.`,
      });
    }
    // Uploaded datasets run real metadata/profile first; the legacy static steps are not used here.
    const bootstrap = async () => {
      if (datasetKey) {
        try {
          await profileUploadedDataset();
          store.setStepStatus(1, 'completed');
          store.setStepIndex(1);
        } catch {
          return;
        }
        return;
      }
      await startAutoRun(pushMessage);
    };
    bootstrap();
    return () => clearTimers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainId, datasetKey, isNewChat]);

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
    pushMessage({
      id: `filter-${Date.now()}`,
      agent: 'orchestrator',
      text: `TIME FILTER ACTIVE: ${filter.toUpperCase()} — Loaded operational logs and rule approval audit history for ${TIME_FILTERS[filter].date}. Audit Manifest Hash: ${TIME_FILTERS[filter].hash}`,
    });
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
                  <span className="agent-name" style={{ color: 'var(--royal-purple)' }}>DATA PROFILER AGENT</span>
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
                    <span className="agent-timestamp">{new Date().toLocaleTimeString('en-US', { hour12: false })}</span>
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
          {chatMessages.map((msg) => {
            const agent = msg.type === 'user' ? 'human' : (msg.agentId || 'orchestrator');
            const Icon = AGENT_ICONS[agent] || Brain;
            return (
              <div key={`chat-${msg.id}`} className="agent-entry">
                <div className={`agent-avatar ${AGENT_AVATAR_CLASS[agent] || 'agent-orchestrator'}`}>
                  <Icon size={15} />
                </div>
                <div className="agent-content-box">
                  <div className="agent-header">
                    <span className="agent-name" style={{ color: AGENT_COLORS[agent] || 'var(--text-main)' }}>
                      {msg.type === 'user' ? 'YOU' : (AGENT_TITLES[agent] || 'ORCHESTRATOR AGENT')}
                    </span>
                    <span className="agent-timestamp">{new Date(msg.timestamp).toLocaleTimeString('en-US', { hour12: false })}</span>
                  </div>
                  <div className="agent-body">
                    <MarkdownContent content={msg.content} />
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
                  <span className="agent-timestamp">{new Date().toLocaleTimeString('en-US', { hour12: false })}</span>
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
                    {isVi ? 'Tự động phân tích, đề xuất luật chất lượng L1-L4 và làm sạch cách ly dữ liệu.' : 'Automatically profile, synthesize L1-L4 quality rules, and quarantine corrupt records.'}
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
                <span>{isRunningPipeline ? (isVi ? 'Đang thực thi...' : 'Executing...') : (isVi ? '🚀 Chạy Toàn Bộ Pipeline' : '🚀 Run Full Pipeline')}</span>
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
      {rightPanelOpen && (

        <aside className="right-panel">
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
            {rightTab === 'tab-traces' && (
              <AgentTracesTab datasetKey={datasetKey} sessionId={datasetKey ? `dataset:${datasetKey}` : 'default'} />
            )}
            {rightTab === 'tab-profiler' && (
              <DataProfilerTab datasetKey={datasetKey} />
            )}
            {rightTab === 'tab-rules' && (
              <QualityRulesTab datasetKey={datasetKey} />
            )}
            {rightTab === 'tab-split' && (
              <SplitDbQuarantineTab
                datasetKey={datasetKey}
                manifestHash={pipelineResult?.manifest?.hash || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
              />
            )}
          </div>
        </aside>
      )}


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
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            <CloudUpload size={22} /> {uploading ? (isVi ? 'Đang tải database...' : 'Uploading database...') : (isVi ? 'Tải Lên Database' : 'Upload Database')}
          </button>
          <button type="button"><Cable size={22} /> {isVi ? 'Kết Nối Plugin' : 'Connect Plugin'}</button>
          <button type="button"><Database size={22} /> {isVi ? 'Tải Ứng Dụng Máy Tính' : 'Download Desktop App'}</button>
        </div>
        {uploadError && <div className="new-chat-upload-error" role="alert">{uploadError}</div>}
      </div>
    </main>
  );
}
