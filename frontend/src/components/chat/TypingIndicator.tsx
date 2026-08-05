import { useTranslation } from 'react-i18next';
import { AgentAvatar } from '../agents/AgentAvatar';
import { AGENTS } from '../../types';
import type { AgentId } from '../../types';

export function TypingIndicator({ agentId }: { agentId: AgentId }) {
  const { t } = useTranslation('chat');
  const agent = AGENTS[agentId];

  return (
    <div className="flex gap-2.5 items-start">
      <AgentAvatar agentId={agentId} size="sm" />
      <div>
        <span className="text-xs font-semibold" style={{ color: agent.color }}>
          {t(agent.nameKey)}
        </span>
        <div className="flex items-center gap-1 mt-1 px-4 py-2.5 bg-chat-agent-bubble border border-border rounded-2xl rounded-tl-md">
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-text-muted"
                style={{
                  animation: `agent-pulse 1.4s ease-in-out ${i * 0.2}s infinite`,
                }}
              />
            ))}
          </div>
          <span className="text-xs text-text-muted ml-2">{t('typing')}</span>
        </div>
      </div>
    </div>
  );
}
