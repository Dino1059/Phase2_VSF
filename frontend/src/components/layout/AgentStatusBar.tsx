import { useTranslation } from 'react-i18next';
import { Brain, ScanSearch, ShieldCheck, AlertTriangle, Stethoscope, Loader2, Check, AlertCircle } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import { AGENTS } from '../../types';
import type { AgentId, AgentStatus } from '../../types';

const ICON_MAP: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  Brain, ScanSearch, ShieldCheck, AlertTriangle, Stethoscope,
};

function StatusIndicator({ status }: { status: AgentStatus }) {
  switch (status) {
    case 'active':
    case 'working':
      return <Loader2 className="w-3 h-3 animate-spin" />;
    case 'done':
      return <Check className="w-3 h-3" />;
    case 'error':
      return <AlertCircle className="w-3 h-3 text-status-error" />;
    default:
      return null;
  }
}

export function AgentStatusBar() {
  const { t } = useTranslation();
  const { agentStatuses } = useChatStore();

  return (
    <div className="flex items-center justify-center gap-1 px-4 h-8 bg-surface border-t border-border shrink-0 overflow-x-auto">
      {(Object.keys(AGENTS) as AgentId[]).map((id) => {
        const agent = AGENTS[id];
        const status = agentStatuses[id];
        const Icon = ICON_MAP[agent.icon];
        const isActive = status === 'active' || status === 'working';

        return (
          <div
            key={id}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all duration-300 ${
              isActive
                ? 'bg-surface-hover text-text-primary'
                : status === 'done'
                ? 'text-text-secondary'
                : status === 'error'
                ? 'text-status-error bg-status-error/10'
                : 'text-text-muted'
            }`}
          >
            {Icon && (
              <Icon
                className={`w-3.5 h-3.5 ${isActive ? 'animate-agent-pulse' : ''}`}
                style={isActive ? { color: agent.color } : undefined}
              />
            )}
            <span className="max-sm:hidden">{t(agent.nameKey)}</span>
            <StatusIndicator status={status} />
          </div>
        );
      })}
    </div>
  );
}
