import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  Play,
  Pause,
  SkipForward,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Pencil,
  Save,
  Database,
  UserShield,
  Lock,
  Info,
  AlertTriangle,
  Lightbulb,
  ScanSearch,
  Stethoscope,
  FlaskConical,
  Brain,
  Fingerprint,
  Clock,
} from 'lucide-react';
import { usePipelineStore, PIPELINE_STEPS, DOMAINS, DOMAIN_LIST, TIME_FILTERS, SPLIT_SAMPLES } from '../stores/pipelineStore';
import { usePipelineRun, StreamMessage } from '../hooks/usePipelineRun';
import { ChatInput } from '../components/chat/ChatInput';
import { fetchChatHistory } from '../services/api';
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

type RightTab = 'tab-rca' | 'tab-telemetry' | 'tab-split' | 'tab-manifest';

export function AgentChatWorkspace() {
  const { t } = useTranslation('pipeline');
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const datasetKey = searchParams.get('dataset_key') || undefined;
  const setChatSessionId = useChatStore((s) => s.setSessionId);
  const chatMessages = useChatStore((s) => s.messages);
  const store = usePipelineStore();
  const domainId = store.domainId;
  const currentStepIndex = store.currentStepIndex;
  const currentRuleLogic = store.currentRuleLogic;
  const setDomain = usePipelineStore((s) => s.setDomain);
  const { startAutoRun, stepNext, acceptRule, rejectRule, saveRuleEdit, clearTimers } = usePipelineRun(datasetKey);
  const [stream, setStream] = useState<StreamMessage[]>([]);
  const [rightTab, setRightTab] = useState<RightTab>('tab-rca');
  const [splitView, setSplitView] = useState<'clean' | 'quarantine'>('clean');
  const [editOpen, setEditOpen] = useState(false);
  const [editText, setEditText] = useState(currentRuleLogic);
  const [ruleCardState, setRuleCardState] = useState<'pending' | 'accepted' | 'rejected'>('pending');
  const streamRef = useRef<HTMLDivElement>(null);
  const rcaCanvasRef = useRef<HTMLCanvasElement>(null);
  const telemetryCanvasRef = useRef<HTMLCanvasElement>(null);
  const runStartedRef = useRef(false);

  // Keep the selected dataset scoped to a stable temporary chat session.
  useEffect(() => {
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
  }, [datasetKey, setChatSessionId]);

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

  // Kick off initial pipeline run once per session
  useEffect(() => {
    if (runStartedRef.current) return;
    runStartedRef.current = true;
    const domain = DOMAINS[domainId];
    pushMessage({
      id: `init-${Date.now()}`,
      agent: 'orchestrator',
      text: `Command Session Initialized for ${domain.name} (Database: ${domain.dbName}). Auto-ingesting live telemetry from Kafka topic ${domain.topic}.`,
    });
    // Auto-run first steps up to the HITL gate (step 5) then pause
    const bootstrap = async () => {
      await startAutoRun(pushMessage);
    };
    bootstrap();
    return () => clearTimers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainId]);

  // Auto-scroll stream
  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: 'smooth' });
  }, [stream.length]);

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
    const nodes = [
      { id: 1, label: 'BMS Firmware 2.4.1', x: width * 0.15, y: height * 0.5, color: isDark ? '#8B5CF6' : '#6366F1' },
      { id: 2, label: 'CAN Bus Baudrate Desync', x: width * 0.45, y: height * 0.3, color: isDark ? '#F59E0B' : '#D97706' },
      { id: 3, label: 'Temp Sensor Payload Drift', x: width * 0.45, y: height * 0.7, color: isDark ? '#F43F5E' : '#EF4444' },
      { id: 4, label: 'Thermal Runaway Alarm Spike', x: width * 0.82, y: height * 0.5, color: isDark ? '#00F0FF' : '#0284C7' },
    ];
    const links = [
      { from: 0, to: 1 }, { from: 0, to: 2 }, { from: 1, to: 3 }, { from: 2, to: 3 },
    ];
    ctx.lineWidth = 2;
    links.forEach((link) => {
      ctx.strokeStyle = isDark ? '#1F293D' : '#CBD5E1';
      ctx.beginPath();
      ctx.moveTo(nodes[link.from].x, nodes[link.from].y);
      ctx.lineTo(nodes[link.to].x, nodes[link.to].y);
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
  }, [rightTab, domainId]);

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
    const total = 20;
    const points: Array<{ x: number; y: number }> = [];
    for (let i = 0; i < total; i++) {
      const x = (width / (total - 1)) * i;
      let y = height * 0.6 + Math.sin(i * 0.5) * 15;
      if (i >= 12 && i <= 15 && store.currentStepIndex >= 2) y -= 45;
      points.push({ x, y });
    }
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, store.currentStepIndex >= 2 ? 'rgba(239,68,68,0.12)' : 'rgba(37,99,235,0.08)');
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
    ctx.strokeStyle = store.currentStepIndex >= 2 ? '#EF4444' : '#2563EB';
    ctx.lineWidth = 2;
    ctx.shadowBlur = 0;
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
    ctx.stroke();
    if (store.currentStepIndex >= 2 && points[13]) {
      ctx.fillStyle = '#EF4444';
      ctx.beginPath();
      ctx.arc(points[13].x, points[13].y, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#1E293B';
      ctx.font = '600 11px Inter, sans-serif';
      ctx.fillText('64.8°C SPIKE', points[13].x - 30, points[13].y - 12);
    }
  }, [rightTab, currentStepIndex]);

  // Split table data
  const splitSamples = SPLIT_SAMPLES[store.domainId] || SPLIT_SAMPLES.ev_telemetry;
  const splitRows = splitView === 'clean' ? splitSamples.clean : splitSamples.quarantine;

  const handleTimeFilter = (filter: TimeFilter) => {
    store.setTimeFilter(filter);
    pushMessage({
      id: `filter-${Date.now()}`,
      agent: 'orchestrator',
      text: `TIME FILTER ACTIVE: ${filter.toUpperCase()} — Loaded operational logs and rule approval audit history for ${TIME_FILTERS[filter].date}. Audit Manifest Hash: ${TIME_FILTERS[filter].hash}`,
    });
  };

  const handleToggleRun = () => {
    if (store.runStatus === 'running') {
      clearTimers();
      store.setRunStatus('paused');
    } else {
      startAutoRun(pushMessage);
    }
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

  const currentStep = PIPELINE_STEPS[store.currentStepIndex];

  return (
    <div className="agent-chat-workspace">
      {/* CENTER COLUMN: CHAT STREAM & MISSION FLOW */}
      <main className="main-chat-panel">
        {/* Top Mission Stepper Controls */}
        <div className="mission-control-bar">
          <div className="mission-bar-header">
            <div className="mission-title-group">
              <span className="mission-label">{t('mission')}</span>
              <span className="mission-db-pill">{currentStep?.name.toUpperCase()}</span>
            </div>
            <div className="pipeline-playback-controls">
              <button className="playback-btn auto-run-btn" onClick={handleToggleRun}>
                {store.runStatus === 'running' ? <Pause size={13} /> : <Play size={13} />}
                {store.runStatus === 'running' ? t('pause') : t('autoRun')}
              </button>
              <button className="playback-btn" onClick={() => stepNext(pushMessage)}>
                <SkipForward size={13} /> {t('stepNext')}
              </button>
            </div>
          </div>

          {/* Step Stepper Nodes (1 to 7) */}
          <div className="steps-pipeline-container">
            {PIPELINE_STEPS.map((step, idx) => {
              let statusClass = '';
              if (idx < store.currentStepIndex) statusClass = 'completed';
              else if (idx === store.currentStepIndex) {
                statusClass = step.isReviewStep && store.ruleStatus === 'pending' ? 'waiting' : 'active';
              }
              return (
                <div
                  key={step.id}
                  className={`step-node ${statusClass}`}
                  onClick={() => {
                    clearTimers();
                    store.setStepIndex(idx);
                    store.setRightTab(step.tab);
                    pushMessage({
                      id: `inspect-${Date.now()}`,
                      agent: step.agent,
                      text: `[STEP ${step.id} INSPECTION: ${step.name.toUpperCase()}] ${step.desc}`,
                    });
                  }}
                >
                  <div className="step-circle">
                    {idx < store.currentStepIndex ? <CheckCircle2 size={14} /> : step.id}
                  </div>
                  <div className="step-label">{step.name}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* In-Stream Time Filter Bar */}
        <div className="in-stream-filter-bar">
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

        {/* Chat Log Stream Area */}
        <div className="chat-stream" id="chatStream" ref={streamRef}>
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
                    <span dangerouslySetInnerHTML={{ __html: msg.text }} />
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
                  <div className="agent-body">{msg.content}</div>
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
        </div>

        {/* Chat Input Bar */}
        <ChatInput datasetKey={datasetKey} />
      </main>

      {/* RIGHT PANEL: VISUAL CONTROL ROOM & INSPECTION (4 TABS) */}
      <aside className="right-panel">
        <div className="right-panel-tabs">
          <button className={`panel-tab ${rightTab === 'tab-rca' ? 'active' : ''}`} onClick={() => setRightTab('tab-rca')}>
            <Fingerprint size={13} /> {t('rcaGraph')}
          </button>
          <button className={`panel-tab ${rightTab === 'tab-telemetry' ? 'active' : ''}`} onClick={() => setRightTab('tab-telemetry')}>
            <FlaskConical size={13} /> Telemetry
          </button>
          <button className={`panel-tab ${rightTab === 'tab-split' ? 'active' : ''}`} onClick={() => setRightTab('tab-split')}>
            <Database size={13} /> {t('splitDb')}
          </button>
          <button className={`panel-tab ${rightTab === 'tab-manifest' ? 'active' : ''}`} onClick={() => setRightTab('tab-manifest')}>
            <Lock size={13} /> Manifest
          </button>
        </div>

        <div className="panel-content-body">
          {/* TAB 1: RCA LINEAGE GRAPH */}
          <div className={`tab-view ${rightTab === 'tab-rca' ? 'active' : ''}`}>
            <div className="rca-container">
              <div className="rca-header">
                <span><Fingerprint size={13} /> {t('rootCauseAnalysis')}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{t('confidencePct')}</span>
              </div>
              <canvas ref={rcaCanvasRef} id="rcaCanvas" />
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: 4 }}>
              <Info size={12} style={{ color: 'var(--neon-cyan)', display: 'inline', marginRight: 4 }} />
              Node lineage dynamically traces CAN bus timing jitter to firmware thermal offset algorithm.
            </div>
          </div>

          {/* TAB 2: LIVE TELEMETRY CHARTS */}
          <div className={`tab-view ${rightTab === 'tab-telemetry' ? 'active' : ''}`}>
            <div className="telemetry-chart-card">
              <div className="chart-title">
                <span><FlaskConical size={13} /> {t('batteryTemp')}</span>
                <span style={{ color: 'var(--alert-magenta)', fontFamily: 'var(--font-mono)' }}>
                  {store.currentStepIndex >= 2 ? t('spikeDetected') : t('stable')}
                </span>
              </div>
              <div className="chart-wrapper">
                <canvas ref={telemetryCanvasRef} id="telemetryChartCanvas" />
              </div>
            </div>
          </div>

          {/* TAB 3: CLEAN DB VS QUARANTINE TABLE SPLIT VIEW */}
          <div className={`tab-view ${rightTab === 'tab-split' ? 'active' : ''}`}>
            <div className="split-view-container">
              <div className="split-toggle-bar">
                <button className={`split-tab-btn ${splitView === 'clean' ? 'active-clean' : ''}`} onClick={() => setSplitView('clean')}>
                  <Database size={13} /> <span>{store.cleanRows.toLocaleString()} {t('clean')}</span>
                </button>
                <button className={`split-tab-btn ${splitView === 'quarantine' ? 'active-quarantine' : ''}`} onClick={() => setSplitView('quarantine')}>
                  <UserShield size={13} /> <span>{store.quarantineRows.toLocaleString()} {t('quarantined')}</span>
                </button>
              </div>
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t('logId')}</th>
                      <th>{t('time')}</th>
                      <th>{t('vehicleAsset')}</th>
                      <th>{t('temp')}</th>
                      <th>{t('vDelta')}</th>
                      <th>{t('reasonCode')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {splitRows.map((row) => (
                      <tr key={row.id}>
                        <td><strong>{row.id}</strong></td>
                        <td>{row.timestamp}</td>
                        <td><code>{row.vehicleId}</code></td>
                        <td>{row.battTemp}</td>
                        <td>{row.vDelta}</td>
                        <td>
                          <span className={row.status === 'CLEAN' ? 'tag-clean' : 'tag-quarantine'}>{row.code}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* TAB 4: CRYPTOGRAPHIC {t('auditManifest')} */}
          <div className={`tab-view ${rightTab === 'tab-manifest' ? 'active' : ''}`}>
            <div className="audit-manifest-card">
              <div className="rca-header" style={{ color: 'var(--electric-green)' }}>
                <span><Lock size={13} /> {t('auditManifest')}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>SHA-256</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
                Every proposed rule and execution payload is hashed and committed to the immutable operations ledger.
              </div>
              <div className="audit-hash-code" id="manifestHashText">
                {store.manifestHash}
              </div>
            </div>
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
              Modify the SQL / Python cleaning conditions for Rule #R-8091 before signing into Pytest integration engine.
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
