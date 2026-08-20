import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Play, Layers, Activity, ShieldCheck, Sparkles, RefreshCw } from 'lucide-react';
import { sendChatMessage, fetchChatHistory } from '../../services/api';
import { agentSocket } from '../../services/websocket';
import { useChatStore } from '../../stores/chatStore';

interface ChatInputProps {
  datasetKey?: string;
  onPipelineStarted?: () => void;
}

export function ChatInput({ datasetKey, onPipelineStarted }: ChatInputProps) {
  const { t, i18n } = useTranslation('chat');
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionId = useChatStore((s) => s.sessionId);

  const executePrompt = async (promptText: string) => {
    if (isSending || !promptText.trim()) return;
    setIsSending(true);

    try {
      if (onPipelineStarted) onPipelineStarted();
      agentSocket.connect(sessionId);
      await sendChatMessage(promptText, sessionId, datasetKey, i18n.language);
      const history = await fetchChatHistory(sessionId);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (e) {
      console.error('Failed to send message:', e instanceof Error ? e.message : 'Unable to reach the assistant.');
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
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
        <button
          type="button"
          disabled={isSending}
          onClick={() => executePrompt(i18n.language === 'vi' ? 'Chạy toàn bộ pipeline cho tôi' : 'run full pipeline for me')}
          title="Tự động chạy toàn bộ quy trình: Khảo sát, Phát hiện dị thường L1-L4, Đề xuất luật và Làm sạch dữ liệu"
          style={{
            background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.15), rgba(147, 51, 234, 0.15))',
            border: '1px solid rgba(2, 132, 199, 0.4)',
            color: 'var(--text-main)',
            padding: '5px 12px',
            borderRadius: '20px',
            fontSize: '11.5px',
            fontWeight: 600,
            cursor: isSending ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
            transition: 'all 0.15s ease',
          }}
        >
          {isSending ? (
            <RefreshCw size={12} className="spinning" style={{ color: '#0284c7' }} />
          ) : (
            <Play size={12} style={{ color: '#0284c7', fill: '#0284c7' }} />
          )}
          <span style={{ color: '#0284c7' }}>
            {i18n.language === 'vi' ? '🚀 Chạy toàn bộ Pipeline' : '🚀 Run Full Pipeline'}
          </span>
        </button>

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

        <button
          type="button"
          disabled={isSending}
          onClick={() => executePrompt(i18n.language === 'vi' ? 'Làm sạch dữ liệu' : 'clean database')}
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
      </div>

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
        <button
          type="submit"
          className="send-btn"
          disabled={!input.trim() || isSending}
        >
          <span>EXECUTE</span>
          <Send className="w-4 h-4 ml-2 inline-block" />
        </button>
      </form>
    </div>
  );
}
