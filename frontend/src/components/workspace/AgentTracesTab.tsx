import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Brain,
  Clock,
  Zap,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { tracesApi, hitlApi } from '../../services/api';
import { actorChipFromTrace, actorLabel, inTimeRange, mapTraceStep, rangeStart, redactSecrets } from '../../demo/stewardLabels';
import type { DemoBeat } from '../../demo/stewardSession';
import type { TimeFilter } from '../../types';
import { useChatStore } from '../../stores/chatStore';
import { datasetStoreKey, useWorkspaceStore, type WorkspaceTraceBeat } from '../../stores/workspaceStore';

export interface TraceStep {
  step: number;
  action: string;
  stage?: string;
  tool?: string;
  tool_name?: string;
  tool_title?: string;
  tool_about?: string;
  input?: unknown;
  output?: unknown;
  observation?: string;
  summary_done?: string;
  safe_summary?: string;
  tokens?: number | null;
  input_tokens_estimated?: number | null;
  output_tokens?: number | null;
  duration_ms?: number | null;
  timestamp?: string | null;
  actor_kind?: string;
  status?: string;
  provider?: string | null;
  model?: string | null;
  fallback_depth?: number | null;
  context_items_included?: number | null;
  context_items_dropped?: number | null;
  validation_status?: string | null;
  msgId?: string;
}

interface AgentTracesTabProps {
  datasetKey?: string;
  sessionId?: string;
  timeFilter?: TimeFilter;
  replayBeats?: DemoBeat[];
  selectedStep?: number | null;
  selectedTool?: string | null;
  onSelectStep?: (step: number) => void;
  pendingRun?: boolean;
  /** Keep-mounted: GET refresh when shown. Never POST chat / Propose. */
  active?: boolean;
  dayIdx?: number | null;
  runId?: string | null;
}

function isRealAuditHash(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const t = value.trim();
  if (t.length < 16 || t.includes('...')) return false;
  if (t.toLowerCase().startsWith('e3b0c442')) return false;
  return /^[0-9a-fA-F]+$/.test(t);
}

function beatToTrace(beat: DemoBeat, index: number): TraceStep {
  const mapped = mapTraceStep(
    {
      action: beat.action || beat.type,
      tool: beat.tool?.name,
      tool_name: beat.tool?.name,
      output: beat.output,
      summary_done: beat.summary,
      duration_ms: beat.tool?.duration_ms ?? null,
      actor_kind: beat.actor_kind,
      status: beat.tool?.status || 'done',
    },
    index
  );
  return mapped;
}

const EMPTY_TRACES: WorkspaceTraceBeat[] = [];

function attachMsgIds(steps: WorkspaceTraceBeat[], messages: Array<{ id?: string; agentId?: string; content?: string }>): WorkspaceTraceBeat[] {
  return steps.map((s) => {
    if (s.msgId) return s;
    const tool = s.tool_name || s.tool || s.action || '';
    const match = messages.find((m) => m.agentId === tool || (m.content || '').includes(tool));
    return match?.id ? { ...s, msgId: match.id } : s;
  });
}

function highlightChatNode(node: Element) {
  node.scrollIntoView({ behavior: 'smooth', block: 'center' });
  node.classList.add('dt-chat-highlight');
  window.setTimeout(() => node.classList.remove('dt-chat-highlight'), 1600);
}

function statusKind(status?: string): 'running' | 'failed' | 'done' {
  const s = (status || '').toLowerCase();
  if (s === 'running' || s === 'in_progress') return 'running';
  if (s === 'failed' || s === 'error') return 'failed';
  return 'done';
}

export const AgentTracesTab: React.FC<AgentTracesTabProps> = ({
  datasetKey,
  sessionId = 'default',
  timeFilter = 'Today',
  replayBeats,
  selectedStep,
  selectedTool,
  onSelectStep,
  pendingRun = false,
  active = false,
  dayIdx = null,
  runId = null,
}) => {
  const storeKey = `${datasetStoreKey(datasetKey, sessionId)}:${runId || dayIdx || 'all'}`;
  const traces = useWorkspaceStore((s) => s.tracesByDataset[storeKey] || EMPTY_TRACES);
  const mergeTraces = useWorkspaceStore((s) => s.mergeTraces);
  const [loading, setLoading] = useState(false);
  const [hashTrail, setHashTrail] = useState<{ latest: string; count: number } | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});
  const [showSafeSummary, setShowSafeSummary] = useState(false);
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const resolvedSessionRef = useRef<string | null>(null);

  // Live chat session is SoT (including 'default'). dataset:<key> is fallback
  // only after the live id returns no steps — never the primary bind.
  const effectiveSessionId = sessionId || (datasetKey ? `dataset:${datasetKey}` : 'default');

  const loadTraces = useCallback(async () => {
    if (replayBeats && replayBeats.length > 0) {
      mergeTraces(storeKey, replayBeats.filter((b) => b.type === 'workflow.step').map(beatToTrace));
    } else {
      setLoading(true);
      try {
        const since = rangeStart(timeFilter).toISOString();
        const tryIds: string[] = [];
        const addId = (id?: string | null) => {
          const t = (id || '').trim();
          if (t && !tryIds.includes(t)) tryIds.push(t);
        };
        addId(resolvedSessionRef.current);
        addId(effectiveSessionId);
        if (datasetKey) {
          addId(`dataset:${datasetKey}`);
          addId(datasetKey);
        }

        const applySteps = (steps: Array<Record<string, any>>) => {
          const mapped = steps
            .map((s, idx) => mapTraceStep(s, idx))
            .filter((s) => !!(s.action || s.tool || s.tool_name));
          const inRange = mapped.filter((s) => inTimeRange(s.timestamp, timeFilter));
          // tz/since mismatch must not hide beats GET already returned
          const keep = inRange.length > 0 ? inRange : mapped;
          if (keep.length > 0) {
            const withIds = attachMsgIds(keep, useChatStore.getState().messages);
            mergeTraces(storeKey, withIds);
            return true;
          }
          return false;
        };

        let applied = false;
        for (const id of tryIds) {
          const res = await tracesApi.get(id, since);
          const steps = Array.isArray(res?.steps) ? res.steps : [];
          if (applySteps(steps)) {
            resolvedSessionRef.current = res?.session_id || id;
            applied = true;
            break;
          }
        }
        if (!applied && datasetKey) {
          const listed = await tracesApi.list(50).catch(() => ({ sessions: [] as Array<{ session_id: string; steps: number }> }));
          const sessions = Array.isArray(listed?.sessions) ? listed.sessions : [];
          const hit = sessions.find((s) => {
            const sid = String(s.session_id || '');
            return (
              (s.steps || 0) > 0 &&
              (sid === effectiveSessionId || sid === `dataset:${datasetKey}` || sid === datasetKey || sid.includes(datasetKey))
            );
          });
          if (hit) {
            const res = await tracesApi.get(hit.session_id, since);
            const steps = Array.isArray(res?.steps) ? res.steps : [];
            if (applySteps(steps)) {
              resolvedSessionRef.current = res?.session_id || hit.session_id;
              applied = true;
            }
          }
        }
        // Never clobber existing steps with empty GET / wrong session.
      } catch {
        // keep existing steps — empty/error must not wipe a measured trail
      } finally {
        setLoading(false);
      }
    }
    try {
      const hist = await hitlApi.history();
      const events = Array.isArray(hist?.history) ? hist.history : [];
      const hashes: string[] = [];
      let latestEventHash: string | null = null;
      for (const ev of events) {
        if (isRealAuditHash(ev?.event_hash)) {
          hashes.push(ev.event_hash);
          latestEventHash = ev.event_hash.trim();
        }
        if (isRealAuditHash(ev?.previous_event_hash)) {
          hashes.push(ev.previous_event_hash);
        }
      }
      if (latestEventHash) setHashTrail({ latest: latestEventHash, count: hashes.length });
    } catch {
      // keep existing hash trail
    }
  }, [datasetKey, effectiveSessionId, mergeTraces, replayBeats, storeKey, timeFilter, dayIdx, runId]);

  useEffect(() => {
    void loadTraces();
  }, [loadTraces]);

  useEffect(() => {
    if (active) void loadTraces();
  }, [active, loadTraces]);

  useEffect(() => {
    const onTrace = () => {
      void loadTraces();
    };
    window.addEventListener('datatrust:agent-trace', onTrace);
    return () => window.removeEventListener('datatrust:agent-trace', onTrace);
  }, [loadTraces]);

  useEffect(() => {
    if (!active) return undefined;
    const id = window.setInterval(() => {
      void loadTraces();
    }, 2000);
    return () => window.clearInterval(id);
  }, [active, loadTraces]);

  const jumpToChat = (trace: TraceStep) => {
    const stream = document.querySelector('.chat-stream');
    if (!stream) return;
    if (trace.msgId) {
      const node = stream.querySelector(`[data-msgid="${trace.msgId}"]`);
      if (node) {
        highlightChatNode(node);
        return;
      }
    }
    const tool = trace.tool_name || trace.tool;
    if (tool) {
      const node = stream.querySelector(`[data-tool="${tool}"]`);
      if (node) {
        highlightChatNode(node);
        return;
      }
    }
    const entries = stream.querySelectorAll('.agent-entry[data-msgid], .agent-entry[data-tool]');
    if (entries.length) {
      highlightChatNode(entries[entries.length - 1]);
      return;
    }
    stream.scrollTo({ top: stream.scrollHeight, behavior: 'smooth' });
  };

  const measuredTokens = traces.reduce((acc, t) => acc + (typeof t.tokens === 'number' ? t.tokens : 0), 0);
  const measuredDuration = traces.reduce((acc, t) => acc + (typeof t.duration_ms === 'number' ? t.duration_ms : 0), 0);
  const running = traces.filter((t) => statusKind(t.status) === 'running');

  const isSelected = (stepNum: number, trace: TraceStep) => {
    if (selectedStep === stepNum) return true;
    if (selectedTool && (trace.tool_name === selectedTool || trace.tool === selectedTool || trace.action === selectedTool)) {
      return true;
    }
    return false;
  };

  return (
    <div className="agent-traces-tab" style={{ padding: 4 }}>
      <div
        className="traces-summary-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-card)',
          border: '1px solid var(--glass-border)',
          borderRadius: 8,
          padding: '10px 14px',
          marginBottom: 14,
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        <div className="traces-metric" style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            {isVi ? 'Bước đo được' : 'Measured steps'}
          </span>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{traces.length}</span>
        </div>
        <div className="traces-metric" style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            {isVi ? 'Độ trễ đo được' : 'Measured latency'}
          </span>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{measuredDuration ? `${measuredDuration}ms` : '—'}</span>
        </div>
        <div className="traces-metric" style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            {isVi ? 'Tokens đo được' : 'Measured tokens'}
          </span>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{measuredTokens || '—'}</span>
        </div>
        <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={showSafeSummary} onChange={(e) => setShowSafeSummary(e.target.checked)} />
          {isVi ? 'Tóm tắt an toàn' : 'Safe summary'}
        </label>
        <button
          type="button"
          onClick={() => void loadTraces()}
          disabled={loading}
          style={{ background: 'none', border: '1px solid var(--glass-border)', borderRadius: 6, padding: '6px 8px', cursor: 'pointer' }}
        >
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
        {hashTrail ? (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Hash trail · {hashTrail.latest.length > 16 ? `${hashTrail.latest.slice(0, 12)}…` : hashTrail.latest} · {hashTrail.count}
          </span>
        ) : null}
      </div>

      {(running.length > 0 || pendingRun) ? (
        <div className="now-running-card" style={{ marginBottom: 12, padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(2,132,199,0.35)', background: 'rgba(2,132,199,0.06)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <Loader2 size={14} className="spinning" style={{ color: '#0284c7', marginTop: 2 }} />
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: '#0284c7' }}>
              {isVi ? 'Đang chạy' : 'Now running'}
            </div>
            {running.length > 0 ? running.map((t, i) => (
              <div key={`run-${i}`} style={{ fontSize: 12, marginTop: 2 }}>
                {t.summary_done || t.tool_title || t.tool_name || t.action}
              </div>
            )) : (
              <div style={{ fontSize: 12, marginTop: 2 }}>
                {isVi ? 'Đang chạy công cụ steward…' : 'Running steward tools…'}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {traces.length === 0 && !pendingRun ? (
        <div className="empty-panel-state" style={{ textAlign: 'center', padding: '40px 16px' }}>
          <Brain size={32} style={{ opacity: 0.3, marginBottom: 8, color: 'var(--text-muted)' }} />
          <div style={{ fontWeight: 600 }}>{isVi ? 'Chưa có dấu vết đo được' : 'No measured traces'}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {isVi
              ? 'Chạy khảo sát / đề xuất luật, hoặc Replay phiên ghi. Không bịa bước.'
              : 'Run profile / propose, or Replay a recorded session. Nothing is invented here.'}
          </div>
        </div>
      ) : (
        <div className="traces-timeline" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {traces.map((trace, idx) => {
            const stepNum = idx + 1;
            const isExpanded = !!expandedSteps[stepNum];
            const selected = isSelected(stepNum, trace);
            const kind = statusKind(trace.status);
            const failed = kind === 'failed';
            const isRun = kind === 'running';
            const title = trace.tool_title || (trace.tool_name || trace.tool || trace.action || '').replace(/_/g, ' ');
            const about = trace.tool_about || '';
            const found = trace.summary_done || (isVi ? 'Không có tóm tắt đo được.' : 'No measured summary.');
            return (
              <div
                key={`trace-${idx}-${trace.action}-${trace.timestamp || ''}`}
                className="trace-step-card steward-beat"
                onClick={() => {
                  onSelectStep?.(stepNum);
                  jumpToChat(trace);
                }}
                style={{
                  background: 'var(--bg-card)',
                  border: selected ? '1px solid #0284c7' : '1px solid var(--glass-border)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 8, borderBottom: '1px solid var(--glass-border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-muted)', fontSize: 11 }}>#{stepNum}</span>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 6, background: 'rgba(2,132,199,0.08)', color: '#0284c7' }}>
                      {actorChipFromTrace(trace, isVi) || actorLabel(trace.actor_kind, isVi)}
                    </span>
                    <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, fontWeight: 700, background: failed ? 'rgba(220,38,38,0.1)' : isRun ? 'rgba(2,132,199,0.1)' : 'rgba(5,150,105,0.1)', color: failed ? '#dc2626' : isRun ? '#0284c7' : '#059669' }}>
                      {isRun ? (isVi ? 'đang chạy' : 'running') : failed ? (isVi ? 'lỗi' : 'failed') : (isVi ? 'xong' : 'done')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {typeof trace.duration_ms === 'number' ? (
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'inline-flex', gap: 3, alignItems: 'center' }}>
                        <Clock size={10} /> {trace.duration_ms}ms
                      </span>
                    ) : null}
                    {typeof trace.tokens === 'number' && trace.tokens > 0 ? (
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'inline-flex', gap: 3, alignItems: 'center' }}>
                        <Zap size={10} /> {trace.tokens}t
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        jumpToChat(trace);
                      }}
                      style={{
                        background: 'rgba(56,189,248,0.1)',
                        border: '1px solid rgba(56,189,248,0.25)',
                        color: '#0284c7',
                        borderRadius: 6,
                        padding: '3px 8px',
                        fontSize: 10,
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <ExternalLink size={10} /> {isVi ? 'Mở chat' : 'Open in chat'}
                    </button>
                  </div>
                </div>

                <div className="steward-beat-what" style={{ marginTop: 8, fontSize: 14, fontWeight: 700 }}>
                  {title}
                </div>
                {about ? (
                  <div className="steward-beat-why" style={{ marginTop: 2, fontSize: 12, color: 'var(--text-muted)' }}>
                    {isVi ? 'Vì sao: ' : 'Why this tool: '}
                    {about}
                  </div>
                ) : null}

                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(99,102,241,0.1)', color: '#6366f1', fontWeight: 600 }}>
                    {(trace.stage || trace.action || 'workflow')}
                  </span>
                  {(trace.provider || trace.model) ? (
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(14,165,233,0.1)', color: '#0284c7', fontWeight: 600 }}>
                      {[trace.provider, trace.model].filter(Boolean).join(' · ')}
                    </span>
                  ) : null}
                  {typeof trace.input_tokens_estimated === 'number' || typeof trace.output_tokens === 'number' || typeof trace.tokens === 'number' ? (
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(245,158,11,0.1)', color: '#d97706', fontWeight: 600 }}>
                      in:{trace.input_tokens_estimated ?? '—'} / out:{trace.output_tokens ?? trace.tokens ?? '—'}
                    </span>
                  ) : null}
                  {(typeof trace.context_items_included === 'number' || typeof trace.context_items_dropped === 'number') ? (
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(16,185,129,0.1)', color: '#059669', fontWeight: 600 }}>
                      evidence {trace.context_items_included ?? 0} used / {trace.context_items_dropped ?? 0} omitted
                    </span>
                  ) : null}
                  {(trace.fallback_depth ?? 0) > 0 ? (
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(234,179,8,0.15)', color: '#a16207', fontWeight: 700 }}>
                      fallback×{trace.fallback_depth}
                    </span>
                  ) : null}
                  {trace.validation_status ? (
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 700, background: String(trace.validation_status).toUpperCase().includes('FAIL') || String(trace.validation_status).toUpperCase() === 'NEEDS_REVIEW' ? 'rgba(220,38,38,0.1)' : 'rgba(5,150,105,0.1)', color: String(trace.validation_status).toUpperCase().includes('FAIL') || String(trace.validation_status).toUpperCase() === 'NEEDS_REVIEW' ? '#dc2626' : '#059669' }}>
                      validation: {trace.validation_status}
                    </span>
                  ) : null}
                </div>
                {showSafeSummary && (trace.safe_summary || trace.summary_done) ? (
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                    {isVi ? 'Tóm tắt: ' : 'Summary: '}
                    {trace.safe_summary || trace.summary_done}
                  </div>
                ) : null}

                <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 6, background: isRun ? 'rgba(2,132,199,0.06)' : failed ? 'rgba(220,38,38,0.05)' : 'rgba(5,150,105,0.05)', border: `1px solid ${isRun ? 'rgba(2,132,199,0.25)' : failed ? 'rgba(220,38,38,0.2)' : 'rgba(5,150,105,0.2)'}`, display: 'flex', gap: 8 }}>
                  {failed ? <AlertTriangle size={13} style={{ color: '#dc2626', flexShrink: 0, marginTop: 2 }} /> : isRun ? <Loader2 size={13} className="spinning" style={{ color: '#0284c7', flexShrink: 0, marginTop: 2 }} /> : <CheckCircle2 size={13} style={{ color: '#059669', flexShrink: 0, marginTop: 2 }} />}
                  <div style={{ fontSize: 11, lineHeight: 1.4 }}>
                    <strong style={{ color: isRun ? '#0284c7' : failed ? '#dc2626' : '#059669', marginRight: 4 }}>
                      {isRun ? (isVi ? 'Đang:' : 'Now:') : failed ? (isVi ? 'Lỗi:' : 'Failed:') : (isVi ? 'Tìm thấy:' : 'Found:')}
                    </strong>
                    {found}
                  </div>
                </div>

                {((trace.input != null || trace.output != null)) && (
                  <div style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedSteps((s) => ({ ...s, [stepNum]: !s[stepNum] }));
                      }}
                      style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}
                    >
                      {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      {isExpanded ? (isVi ? 'Ẩn I/O tool' : 'Hide tool I/O') : (isVi ? 'Xem I/O tool' : 'View tool I/O')}
                    </button>
                    {isExpanded && (
                      <div style={{ marginTop: 8 }}>
                        {trace.input != null && (
                          <pre style={{ fontSize: 11, maxHeight: 140, overflow: 'auto', background: 'var(--bg-input, #f8fafc)', border: '1px solid var(--glass-border)', padding: 8, borderRadius: 6 }}>
                            <code>{redactSecrets(trace.input)}</code>
                          </pre>
                        )}
                        {trace.output != null && (
                          <pre style={{ fontSize: 11, maxHeight: 140, overflow: 'auto', background: 'var(--bg-input, #f8fafc)', border: '1px solid var(--glass-border)', padding: 8, borderRadius: 6, marginTop: 8 }}>
                            <code>{redactSecrets(trace.output)}</code>
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
