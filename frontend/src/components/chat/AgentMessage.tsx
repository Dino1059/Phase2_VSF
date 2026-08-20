import { useTranslation } from 'react-i18next';
import { formatSaigonTime, catalogFor } from '../../demo/stewardLabels';
import { AgentAvatar } from '../agents/AgentAvatar';
import { RuleProposalCard } from '../hitl/RuleProposalCard';
import { AGENTS } from '../../types';
import type { ChatMessage, RuleProposal } from '../../types';
import { Wrench } from 'lucide-react';

const AGENT_ALIASES: Record<string, keyof typeof AGENTS> = {
  'rule_proposer': 'ruleProposer',
  'rule-proposer': 'ruleProposer',
  'ruleproposer': 'ruleProposer',
  'anomaly': 'anomalyDetector',
  'anomaly_detector': 'anomalyDetector',
  'anomalydetector': 'anomalyDetector',
  'diagnostics': 'diagnosis',
  'diagnosis_agent': 'diagnosis',
  'profile_dataset': 'profiler',
  'propose_quality_rules': 'ruleProposer',
  'clean_database': 'orchestrator',
  'list_datasets': 'orchestrator',
};

function safeFormatTime(timestamp?: string) {
  return formatSaigonTime(timestamp || null);
}

function toolNameFromMessage(message: ChatMessage): string {
  const meta = message.metadata || {};
  const fromMeta = typeof meta.tool_name === 'string' ? meta.tool_name : typeof meta.tool === 'string' ? meta.tool : '';
  if (fromMeta) return fromMeta;
  return message.agentId || '';
}

export function AgentMessage({
  message,
  onSelectTrace,
}: {
  message: ChatMessage;
  onSelectTrace?: (tool: string) => void;
}) {
  const { t } = useTranslation();
  const rawAgentId = message.agentId || 'orchestrator';
  const agentId = (AGENT_ALIASES[rawAgentId] || (AGENTS[rawAgentId as keyof typeof AGENTS] ? rawAgentId : 'orchestrator')) as keyof typeof AGENTS;
  const agent = AGENTS[agentId] || AGENTS.orchestrator;
  const time = safeFormatTime(message.timestamp);

  const content = message.content || '';
  const isThought = content.startsWith('Thought:');
  const isObservation = content.startsWith('Observation:');
  const proposals: RuleProposal[] = Array.isArray(message.metadata?.proposals) ? message.metadata.proposals : [];
  const toolName = toolNameFromMessage(message);
  const chip = catalogFor(toolName);

  if (isThought) {
    return null;
  }

  return (
    <div id={`chat-msg-${message.id}`} className="chat-msg-entry flex gap-2.5 my-1.5 transition-all duration-500 rounded-xl" data-msgid={message.id} data-tool={toolName || undefined}>
      <AgentAvatar agentId={agentId} size="sm" />
      <div className="max-w-[88%] flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold" style={{ color: agent.color }}>
            {t(agent.nameKey)}
          </span>
          <span className="text-[10px] text-text-muted">{time}</span>
        </div>

        {chip ? (
          <button
            type="button"
            className="used-tool-chip"
            onClick={() => onSelectTrace?.(chip.name)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: 999,
              border: '1px solid rgba(2,132,199,0.3)',
              background: 'rgba(2,132,199,0.08)',
              color: '#0284c7',
              cursor: 'pointer',
              marginBottom: 8,
            }}
          >
            <Wrench size={11} />
            Used {chip.title} — {chip.about}
          </button>
        ) : null}

        {!isObservation && content ? (
          <div className="bg-chat-agent-bubble border border-border/70 rounded-2xl rounded-tl-md px-4 py-2.5 text-sm text-text-primary leading-relaxed space-y-1.5 shadow-sm">
            {renderFormattedContent(content)}
          </div>
        ) : null}

        {proposals.length > 0 && (
          <div className="mt-3 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-agent-rule-proposer mb-1">
              <span>Pending Governance Review ({proposals.length} rules):</span>
            </div>
            {proposals.map((prop) => (
              <RuleProposalCard key={prop.id} proposal={prop} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function renderFormattedContent(text: string) {
  const lines = text.split('\n');
  return lines.map((line, idx) => {
    if (line.trim().startsWith('•') || line.trim().startsWith('*')) {
      const bulletText = line.replace(/^[•*]\s*/, '');
      return (
        <div key={idx} className="flex items-start gap-1.5 pl-1 my-0.5">
          <span className="text-agent-orchestrator text-xs mt-0.5">•</span>
          <span className="text-xs">{parseBold(bulletText)}</span>
        </div>
      );
    }
    return (
      <p key={idx} className="text-xs leading-relaxed">
        {parseBold(line)}
      </p>
    );
  });
}

function parseBold(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-text-primary">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}
