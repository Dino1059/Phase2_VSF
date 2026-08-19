import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Brain,
  Terminal,
  Clock,
  Zap,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { tracesApi } from '../../services/api';
import { actorLabel, inTimeRange, mapTraceStep, rangeStart } from '../../demo/stewardLabels';
import type { DemoBeat } from '../../demo/stewardSession';
import type { TimeFilter } from '../../types';

export interface TraceStep {
  step: number;
  action: string;
  tool?: string;
  input?: unknown;
  output?: unknown;
  observation?: string;
  summary_done?: string;
  tokens?: number | null;
  duration_ms?: number | null;
  timestamp?: string | null;
  actor_kind?: string;
  status?: string;
  thought?: string;
  msgId?: string;
}

interface AgentTracesTabProps {
  datasetKey?: string;
  sessionId?: string;
  timeFilter?: TimeFilter;
  replayBeats?: DemoBeat[];
  selectedStep?: number | null;
  onSelectStep?: (step: number) => void;
}

function beatToTrace(beat: DemoBeat, index: number): TraceStep {
  return {
    step: index + 1,
    action: beat.action || beat.type,
    tool: beat.tool?.name,
    output: beat.output,
    summary_done: beat.summary,
    duration_ms: beat.tool?.duration_ms ?? null,
    actor_kind: beat.actor_kind,
    status: beat.tool?.status || 'COMPLETED',
    timestamp: null,
  };
}

export const AgentTracesTab: React.FC<AgentTracesTabProps> = ({
  datasetKey,
  sessionId = 'default',
  timeFilter = 'Today',
  replayBeats,
  selectedStep,
  onSelectStep,
}) => {
  const [traces, setTraces] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});
  const [showThought, setShowThought] = useState(false);
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const effectiveSessionId = sessionId.startsWith('dataset:')
    ? sessionId
    : datasetKey
      ? `dataset:${datasetKey}`
      : sessionId;

  const loadTraces = useCallback(async () => {
    if (replayBeats && replayBeats.length > 0) {
      setTraces(replayBeats.filter((b) => b.type === 'workflow.step').map(beatToTrace));
      return;
    }
    setLoading(true);
    try {
      const since = rangeStart(timeFilter).toISOString();
      const res = await tracesApi.get(effectiveSessionId, since);
      const steps = Array.isArray(res?.steps) ? res.steps : [];
      setTraces(
        steps
          .map((s, idx) => mapTraceStep(s, idx))
          .filter((s) => inTimeRange(s.timestamp, timeFilter))
          .filter((s) => !!(s.action || s.tool))
      );
    } catch {
      setTraces([]);
    } finally {
      setLoading(false);
    }
  }, [effectiveSessionId, replayBeats, timeFilter]);

  useEffect(() => {
    void loadTraces();
  }, [loadTraces]);

  useEffect(() => {
    const onTrace = () => {
      void loadTraces();
    };
    window.addEventListener('datatrust:agent-trace', onTrace);
    return () => window.removeEventListener('datatrust:agent-trace', onTrace);
  }, [loadTraces]);

  const jumpToChat = (trace: TraceStep) => {
    const stream = document.querySelector('.chat-stream');
    if (!stream) return;
    if (trace.msgId) {
      const node = stream.querySelector(`[data-msgid="${trace.msgId}"]`);
      if (node) {
        node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
    }
    stream.scrollTo({ top: stream.scrollHeight, behavior: 'smooth' });
  };

  const measuredTokens = traces.reduce((acc, t) => acc + (typeof t.tokens === 'number' ? t.tokens : 0), 0);
  const measuredDuration = traces.reduce((acc, t) => acc + (typeof t.duration_ms === 'number' ? t.duration_ms : 0), 0);

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
          <input type="checkbox" checked={showThought} onChange={(e) => setShowThought(e.target.checked)} />
          {isVi ? 'Chi tiết kỹ thuật' : 'Technical detail'}
        </label>
        <button
          type="button"
          onClick={() => void loadTraces()}
          disabled={loading}
          style={{ background: 'none', border: '1px solid var(--glass-border)', borderRadius: 6, padding: '6px 8px', cursor: 'pointer' }}
        >
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
      </div>

      {traces.length === 0 ? (
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
            const selected = selectedStep === stepNum;
            const failed = (trace.status || '').toUpperCase() === 'FAILED';
            return (
              <div
                key={`trace-${idx}-${trace.action}-${trace.timestamp || ''}`}
                className="trace-step-card"
                onClick={() => onSelectStep?.(stepNum)}
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
                      {actorLabel(trace.actor_kind, isVi)}
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

                {showThought && trace.thought ? (
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                    {isVi ? 'Chi tiết kỹ thuật: ' : 'Technical detail: '}
                    {trace.thought}
                  </div>
                ) : null}

                {trace.tool ? (
                  <div style={{ marginTop: 6, padding: '6px 10px', borderRadius: 6, background: 'var(--bg-input, rgba(0,0,0,0.03))', border: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono, monospace)', fontSize: 11 }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#0284c7' }}>
                      <Terminal size={12} />
                      <code>{trace.tool}()</code>
                    </span>
                    <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: failed ? 'rgba(220,38,38,0.1)' : 'rgba(5,150,105,0.1)', color: failed ? '#dc2626' : '#059669', fontWeight: 700 }}>
                      {trace.status || 'COMPLETED'}
                    </span>
                  </div>
                ) : null}

                <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 6, background: 'rgba(5,150,105,0.05)', border: '1px solid rgba(5,150,105,0.2)', display: 'flex', gap: 8 }}>
                  {failed ? <AlertTriangle size={13} style={{ color: '#dc2626', flexShrink: 0, marginTop: 2 }} /> : <CheckCircle2 size={13} style={{ color: '#059669', flexShrink: 0, marginTop: 2 }} />}
                  <div style={{ fontSize: 11, lineHeight: 1.4 }}>
                    <strong style={{ color: '#059669', marginRight: 4 }}>{isVi ? 'Xong:' : 'Done:'}</strong>
                    {trace.summary_done || trace.observation || (isVi ? 'Không có tóm tắt đo được.' : 'No measured summary.')}
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
                            <code>{typeof trace.input === 'string' ? trace.input : JSON.stringify(trace.input, null, 2)}</code>
                          </pre>
                        )}
                        {trace.output != null && (
                          <pre style={{ fontSize: 11, maxHeight: 140, overflow: 'auto', background: 'var(--bg-input, #f8fafc)', border: '1px solid var(--glass-border)', padding: 8, borderRadius: 6, marginTop: 8 }}>
                            <code>{typeof trace.output === 'string' ? trace.output : JSON.stringify(trace.output, null, 2)}</code>
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
