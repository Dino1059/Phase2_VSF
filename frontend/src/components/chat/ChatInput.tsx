import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Layers, Activity, ShieldCheck, Sparkles } from 'lucide-react';
import { sendChatMessage, fetchChatHistory, hitlApi, getGlobalUseLlm, systemApi, isLlmProviderAvailable, LLM_PROVIDER_OFF_MSG } from '../../services/api';
import { agentSocket } from '../../services/websocket';
import { useChatStore } from '../../stores/chatStore';
import { datasetStoreKey, useWorkspaceStore } from '../../stores/workspaceStore';
import { dayIdxToCalendarDay } from '../../lib/calendarDay';

import { usePipelineStore } from '../../stores/pipelineStore';
import { useAuthStore } from '../../stores/authStore';

interface ChatInputProps {
  datasetKey?: string;
  onPipelineStarted?: () => void;
}

export function ChatInput({ datasetKey, onPipelineStarted }: ChatInputProps) {
  const { t, i18n } = useTranslation('chat');
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = useChatStore((s) => s.sessionId);
  const selectedDayIdx = usePipelineStore((s) => s.selectedDayIdx);
  const sourceIngestionRunId = usePipelineStore((s) => s.sourceIngestionRunId);
  const pipelineRunId = usePipelineStore((s) => s.runId);
  const canPropose = useAuthStore((s) => s.canPropose());
  const canExecute = useAuthStore((s) => s.canExecute());
  const canHitlWrite = useAuthStore((s) => s.canHitlWrite());

  const executePrompt = async (promptText: string) => {
    if (isSending || !promptText.trim()) return;
    setIsSending(true);
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      if (onPipelineStarted) onPipelineStarted();
      agentSocket.connect(sessionId);
      let useLlm = getGlobalUseLlm();
      if (useLlm) {
        try {
          const st = await systemApi.getLlmStatus();
          if (!isLlmProviderAvailable(st)) {
            useLlm = false;
            const lang = i18n.language === 'vi' ? 'vi' : 'en';
            useChatStore.getState().addMessage({
              id: `sys-provider-off-${Date.now()}`,
              type: 'system',
              content: LLM_PROVIDER_OFF_MSG[lang],
              timestamp: new Date().toISOString(),
            });
          }
        } catch {
          useLlm = false;
        }
      }
      await sendChatMessage(promptText, sessionId, datasetKey, i18n.language, useLlm, selectedDayIdx, ac.signal);
      const history = await fetchChatHistory(sessionId);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return;
      console.error('Failed to send message:', e instanceof Error ? e.message : 'Unable to reach the assistant.');
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleWarehouseExecute = async () => {
    if (isSending || !canHitlWrite) return;
    setIsSending(true);
    const key = datasetKey || 'ev_telemetry';
    const axisRun = sourceIngestionRunId || pipelineRunId;
    const calendarDay = axisRun && String(axisRun).includes('-')
      ? String(axisRun)
      : dayIdxToCalendarDay(selectedDayIdx);
    const storeKey = datasetStoreKey(key);
    try {
      let ruleIds: string[] = [];
      try {
        const queue = await hitlApi.queue(key, calendarDay || undefined);
        ruleIds = (queue.proposals || [])
          .filter((r) => {
            const s = (r.status || '').toLowerCase();
            return s === 'approved' || s === 'edited';
          })
          .map((r) => r.rule_id);
      } catch { /* backend still selects approved rules */ }
      const res = await hitlApi.executeWarehouse(key, ruleIds, calendarDay, selectedDayIdx);
      const c = res.warehouse_clean_rows ?? res.clean_rows ?? 0;
      const q = res.warehouse_quarantine_rows ?? res.quarantine_rows ?? 0;
      useWorkspaceStore.getState().mergeSplitRows(storeKey, {
        cleanRan: true,
        thisRun: true,
        warehouseCommitted: true,
        totalClean: c,
        totalQuarantine: q,
        snapshotId: res.snapshot_id || '',
      });
      const detail = {
        ...(res || {}),
        thisRun: true,
        cleanRan: true,
        warehouseCommitted: true,
        dataset_key: key,
        snapshot_id: res.snapshot_id,
        clean_rows: c,
        quarantine_rows: q,
        counts_kind: 'warehouse',
      };
      try {
        window.dispatchEvent(new CustomEvent('datatrust:sandbox-split', { detail }));
      } catch { /* ignore */ }
      useChatStore.getState().addMessage({
        id: `wh-exe-${Date.now()}`,
        type: 'agent',
        content: i18n.language === 'vi'
          ? `Execute kho (Steward): sạch ${c} · cách ly ${q}`
          : `Warehouse execute (Steward): clean ${c} · quarantine ${q}`,
        timestamp: new Date().toISOString(),
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'execute failed';
      useChatStore.getState().addMessage({
        id: `wh-exe-err-${Date.now()}`,
        type: 'agent',
        content: msg,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleAbort = () => {
    abortRef.current?.abort();
    setIsSending(false);
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;
    setInput('');
    await executePrompt(trimmed);
  };

  return (
    <div className="chat-input-container" style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      {/* QUICK PIPELINE SHORTCUT PILLS */}
      {(canPropose || canExecute) && (
      <div
        className="quick-actions-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          flexWrap: 'wrap',
          padding: '0 2px',
        }}
      >
        {canPropose && (
        <>
        <button
          type="button"
          disabled={isSending}
          onClick={() => executePrompt(i18n.language === 'vi' ? 'Khảo sát dữ liệu' : 'profile dataset')}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-muted)',
            padding: '4px 10px',
            borderRadius: '20px',
            fontSize: '11px',
            fontWeight: 500,
            cursor: isSending ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <Layers size={11} style={{ color: '#2563eb' }} />
          <span>{i18n.language === 'vi' ? 'Khảo sát dữ liệu' : 'Profile Dataset'}</span>
        </button>

        <button
          type="button"
          disabled={isSending}
          onClick={() => executePrompt(i18n.language === 'vi' ? 'Phát hiện dị thường L1-L4' : 'detect anomalies')}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-muted)',
            padding: '4px 10px',
            borderRadius: '20px',
            fontSize: '11px',
            fontWeight: 500,
            cursor: isSending ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <Activity size={11} style={{ color: '#ec4899' }} />
          <span>{i18n.language === 'vi' ? 'Dị thường L1–L4' : 'Anomaly L1–L4'}</span>
        </button>

        <button
          type="button"
          disabled={isSending}
          onClick={() => executePrompt(i18n.language === 'vi' ? 'Đề xuất luật chất lượng' : 'propose quality rules')}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-muted)',
            padding: '4px 10px',
            borderRadius: '20px',
            fontSize: '11px',
            fontWeight: 500,
            cursor: isSending ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <ShieldCheck size={11} style={{ color: '#d97706' }} />
          <span>{i18n.language === 'vi' ? 'Đề xuất luật chất lượng' : 'Propose Quality Rules'}</span>
        </button>
        </>
        )}

        {canHitlWrite && canExecute && (
        <button
          type="button"
          data-testid="chat-clean-chip-steward"
          disabled={isSending}
          onClick={() => void handleWarehouseExecute()}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-muted)',
            padding: '4px 10px',
            borderRadius: '20px',
            fontSize: '11px',
            fontWeight: 500,
            cursor: isSending ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <Sparkles size={11} style={{ color: '#059669' }} />
          <span>{i18n.language === 'vi' ? 'Làm sạch & Cách ly' : 'Clean & Quarantine'}</span>
        </button>
        )}
      </div>
      )}

      {/* INPUT FORM */}
      <form className="chat-input-bar" onSubmit={(e) => { e.preventDefault(); void handleSend(); }}>
        <input
          type="text"
          className="chat-input"
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('placeholder') || (i18n.language === 'vi' ? 'Nhập lệnh... (ví dụ: "Khảo sát bộ dữ liệu", "Chạy toàn bộ pipeline")' : 'Type a command or message...')}
          disabled={isSending}
        />
        {isSending ? (
          <button type="button" className="send-btn" onClick={handleAbort}>
            <span>{i18n.language === 'vi' ? 'DỪNG' : 'ABORT'}</span>
          </button>
        ) : (
          <button
            type="submit"
            className="send-btn"
            disabled={!input.trim()}
          >
            <span>{i18n.language === 'vi' ? 'Gửi' : 'Send'}</span>
            <Send className="w-4 h-4 ml-2 inline-block" />
          </button>
        )}
      </form>
    </div>
  );
}
