import { useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chatStore';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { TypingIndicator } from './TypingIndicator';
import { MessageSquare } from 'lucide-react';
import { agentSocket } from '../../services/socket';
import { fetchChatHistory } from '../../services/api';

export function ChatPanel() {
  const { t } = useTranslation('chat');
  const { messages, agentStatuses, addMessage } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const isAnyAgentWorking = Object.values(agentStatuses).some(
    (s) => s === 'active' || s === 'working'
  );
  const workingAgent = Object.entries(agentStatuses).find(
    ([_, s]) => s === 'active' || s === 'working'
  )?.[0];

  useEffect(() => {
    agentSocket.connect();
    fetchChatHistory()
      .then((res) => {
        if (res.messages && Array.isArray(res.messages) && messages.length === 0) {
          res.messages.forEach((msg: any) => addMessage(msg));
        }
      })
      .catch((err) => console.warn('Failed to load chat history:', err));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages.length]);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-muted">
            <MessageSquare className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm font-medium">{t('welcome')}</p>
            <p className="text-xs mt-1 opacity-70">{t('commandHint')}</p>
          </div>
        ) : (
          messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
        )}
        {isAnyAgentWorking && workingAgent && (
          <TypingIndicator agentId={workingAgent as any} />
        )}
      </div>

      {/* Input bar */}
      <ChatInput />
    </div>
  );
}
