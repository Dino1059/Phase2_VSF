import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Send } from 'lucide-react';
import { sendChatMessage, fetchChatHistory } from '../../services/api';
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
      const history = await fetchChatHistory(sessionId);
      if (history.messages && Array.isArray(history.messages)) {
        useChatStore.getState().setMessages(history.messages);
      }
    } catch (e) {
      console.error('Failed to send message:', e);
    }
  };


  return (
    <form className="chat-input-bar" onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
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
