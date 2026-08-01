import { useTranslation } from 'react-i18next';
import { AgentAvatar } from '../agents/AgentAvatar';
import { AGENTS } from '../../types';
import type { ChatMessage } from '../../types';

export function AgentMessage({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const agentId = message.agentId || 'orchestrator';
  const agent = AGENTS[agentId];
  const time = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="flex gap-2.5">
      <AgentAvatar agentId={agentId} size="sm" />
      <div className="max-w-[85%]">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold" style={{ color: agent.color }}>
            {t(agent.nameKey)}
          </span>
          <span className="text-[10px] text-text-muted">{time}</span>
        </div>
        <div className="bg-chat-agent-bubble border border-border rounded-2xl rounded-tl-md px-4 py-2.5 text-sm text-text-primary">
          {message.content}
        </div>
      </div>
    </div>
  );
}
