import { useTranslation } from 'react-i18next';
import { AgentAvatar } from '../agents/AgentAvatar';
import { RuleProposalCard } from '../hitl/RuleProposalCard';
import { AGENTS } from '../../types';
import type { ChatMessage, RuleProposal } from '../../types';
import { Brain, Terminal, ShieldCheck } from 'lucide-react';

const AGENT_ALIASES: Record<string, keyof typeof AGENTS> = {
  'rule_proposer': 'ruleProposer',
  'rule-proposer': 'ruleProposer',
  'ruleproposer': 'ruleProposer',
  'anomaly': 'anomalyDetector',
  'anomaly_detector': 'anomalyDetector',
  'anomalydetector': 'anomalyDetector',
  'diagnostics': 'diagnosis',
  'diagnosis_agent': 'diagnosis',
};

function safeFormatTime(timestamp?: string) {
  try {
    if (!timestamp) return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const d = new Date(timestamp);
    return isNaN(d.getTime()) ? new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}

export function AgentMessage({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const rawAgentId = message.agentId || 'orchestrator';
  const agentId = (AGENT_ALIASES[rawAgentId] || (AGENTS[rawAgentId as keyof typeof AGENTS] ? rawAgentId : 'orchestrator')) as keyof typeof AGENTS;
  const agent = AGENTS[agentId] || AGENTS.orchestrator;
  const time = safeFormatTime(message.timestamp);

  const content = message.content || '';
  const isThought = content.startsWith('Thought:');
  const isObservation = content.startsWith('Observation:');
  const proposals: RuleProposal[] = Array.isArray(message.metadata?.proposals) ? message.metadata.proposals : [];

  return (
    <div id={`chat-msg-${message.id}`} className="chat-msg-entry flex gap-2.5 my-1.5 transition-all duration-500 rounded-xl">
      <AgentAvatar agentId={agentId} size="sm" />
      <div className="max-w-[88%] flex-1">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold" style={{ color: agent.color }}>
            {t(agent.nameKey)}
          </span>
          <span className="text-[10px] text-text-muted">{time}</span>
          {isThought && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.2 text-[9px] font-medium text-cyan-400 bg-cyan-950/60 border border-cyan-800/40 rounded-full">
              <Brain className="w-2.5 h-2.5" /> ReAct Reasoning
            </span>
          )}
          {isObservation && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.2 text-[9px] font-medium text-amber-400 bg-amber-950/60 border border-amber-800/40 rounded-full">
              <Terminal className="w-2.5 h-2.5" /> Tool Observation
            </span>
          )}
        </div>

        {/* Message Bubble Body */}
        {isThought ? (
          <div className="bg-cyan-950/20 border border-cyan-800/30 rounded-xl rounded-tl-md px-3.5 py-2 text-xs italic text-cyan-200/90 leading-relaxed">
            {content.replace(/^Thought:\s*/, '')}
          </div>
        ) : isObservation ? (
          <div className="bg-surface/90 border border-border/80 rounded-xl rounded-tl-md px-3.5 py-2 text-xs text-text-primary leading-relaxed shadow-inner space-y-1">
            {renderFormattedContent(content.replace(/^Observation:\s*/, ''))}
          </div>
        ) : (
          <div className="bg-chat-agent-bubble border border-border/70 rounded-2xl rounded-tl-md px-4 py-2.5 text-sm text-text-primary leading-relaxed space-y-1.5 shadow-sm">
            {renderFormattedContent(content)}
          </div>
        )}

        {/* Inline Rule Proposal Cards for HITL */}
        {proposals.length > 0 && (
          <div className="mt-3 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-agent-rule-proposer mb-1">
              <ShieldCheck className="w-3.5 h-3.5" />
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
