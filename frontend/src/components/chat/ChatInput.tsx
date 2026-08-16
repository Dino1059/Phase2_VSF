import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Send } from 'lucide-react';
import { sendChatMessage, fetchChatHistory } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';

interface ChatInputProps {
  datasetKey?: string;
}

export function ChatInput({ datasetKey }: ChatInputProps) {
  const { t } = useTranslation('chat');
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sessionId = useChatStore((s) => s.sessionId);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    setInput('');
    setIsSending(true);
    inputRef.current?.focus();

    try {
      await sendChatMessage(trimmed, sessionId, datasetKey);
      const history = await fetchChatHistory(sessionId);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (e) {
      console.error('Failed to send message:', e instanceof Error ? e.message : 'Unable to reach the assistant.');
      setInput(trimmed);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  return (
    <form className="chat-input-bar" onSubmit={(e) => { e.preventDefault(); void handleSend(); }}>
      <input
        type="text"
        className="chat-input"
        ref={inputRef as any}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={t('placeholder') || 'Type a command or message...'}
      />
      <button
        type="submit"
        className="send-btn"
        disabled={!input.trim()}
      >
        <span>EXECUTE</span>
        <Send className="w-4 h-4 ml-2 inline-block" />
      </button>
    </form>
  );
}
