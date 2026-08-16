import { Brain, ScanSearch, ShieldCheck, AlertTriangle, Stethoscope } from 'lucide-react';
import { AGENTS } from '../../types';
import type { AgentId } from '../../types';

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Brain, ScanSearch, ShieldCheck, AlertTriangle, Stethoscope,
};

interface Props {
  agentId: AgentId;
  size?: 'sm' | 'md' | 'lg';
}

const SIZES = {
  sm: 'w-7 h-7',
  md: 'w-9 h-9',
  lg: 'w-11 h-11',
};

const ICON_SIZES = {
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
};

export function AgentAvatar({ agentId, size = 'md' }: Props) {
  const agent = AGENTS[agentId];
  const Icon = ICON_MAP[agent.icon];

  return (
    <div
      className={`${SIZES[size]} rounded-full flex items-center justify-center shrink-0`}
      style={{ backgroundColor: `${agent.color}20`, color: agent.color }}
    >
      {Icon && <Icon className={ICON_SIZES[size]} />}
    </div>
  );
}
