import { useTranslation } from 'react-i18next';
import { ArrowRight } from 'lucide-react';
import { AGENTS } from '../../types';
import type { ChatMessage, HandoffMessage } from '../../types';

export function SystemMessage({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();

  if (message.type === 'handoff') {
    const handoff = message as HandoffMessage;
    const from = AGENTS[handoff.fromAgent];
    const to = AGENTS[handoff.toAgent];
    return (
      <div className="flex items-center justify-center gap-2 py-2">
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <span style={{ color: from.color }}>{t(from.nameKey)}</span>
          <ArrowRight className="w-3 h-3" />
          <span style={{ color: to.color }}>{t(to.nameKey)}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center py-2">
      <div className="text-[11px] text-text-muted bg-chat-system px-3 py-1 rounded-full">
        {message.content}
      </div>
    </div>
  );
}
