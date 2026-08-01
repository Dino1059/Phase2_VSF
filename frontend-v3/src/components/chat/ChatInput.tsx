import { useState, useRef, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Send } from 'lucide-react';
import { sendChatMessage } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';

export function ChatInput() {
  const { t } = useTranslation('chat');
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sessionId = useChatStore((s) => s.sessionId);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    setInput('');
    inputRef.current?.focus();

    try {
      await sendChatMessage(trimmed, sessionId);
    } catch (e) {
      console.error('Failed to send message:', e);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border p-3 bg-surface shrink-0">
      <div className="flex items-end gap-2 bg-background rounded-lg border border-border focus-within:border-agent-orchestrator/50 transition-colors">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('placeholder')}
          rows={1}
          className="flex-1 bg-transparent text-text-primary text-sm px-3 py-2.5 resize-none outline-none placeholder:text-text-muted max-h-32"
          style={{ minHeight: '40px' }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim()}
          className="p-2.5 text-agent-orchestrator hover:bg-agent-orchestrator/10 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
