import type { ChatMessage } from '../../types';
import { useChatStore } from '../../stores/chatStore';

interface MessageMetaStripProps {
  message: ChatMessage;
  flaggedPatterns?: string[];
}

const CONTEXT_CAP = 10000;

function getRealTokenCounts(message: ChatMessage): {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
} | null {
  const meta = (message.metadata || {}) as Record<string, any>;
  const tokensObj = (meta.tokens && typeof meta.tokens === 'object')
    ? (meta.tokens as Record<string, any>)
    : undefined;

  const rawPrompt =
    message.promptTokens ??
    (meta.promptTokens as number) ??
    (meta.prompt_tokens as number) ??
    (tokensObj?.prompt_tokens as number) ??
    (tokensObj?.promptTokens as number);

  const rawCompletion =
    message.completionTokens ??
    (meta.completionTokens as number) ??
    (meta.completion_tokens as number) ??
    (tokensObj?.completion_tokens as number) ??
    (tokensObj?.completionTokens as number);

  const rawTotal =
    message.totalTokens ??
    (meta.totalTokens as number) ??
    (meta.total_tokens as number) ??
    (tokensObj?.total_tokens as number) ??
    (tokensObj?.totalTokens as number) ??
    (tokensObj?.tokens_used as number);

  const hasPrompt = typeof rawPrompt === 'number' && !isNaN(rawPrompt);
  const hasCompletion = typeof rawCompletion === 'number' && !isNaN(rawCompletion);
  const hasTotal = typeof rawTotal === 'number' && !isNaN(rawTotal);

  if (!hasPrompt && !hasCompletion && !hasTotal) {
    return null;
  }

  const promptTokens = hasPrompt ? rawPrompt : 0;
  const completionTokens = hasCompletion ? rawCompletion : 0;
  const totalTokens = hasTotal ? rawTotal : promptTokens + completionTokens;

  return { promptTokens, completionTokens, totalTokens };
}

export function MessageMetaStrip({ message, flaggedPatterns }: MessageMetaStripProps) {
  const meta = (message.metadata || {}) as Record<string, any>;
  const realTokens = getRealTokenCounts(message);

  const modelName = message.model ?? (meta.model as string) ?? message.agentId ?? 'orchestrator';

  const retrievedTables: string[] = message.retrievedTables ?? (meta.retrievedTables as string[]) ?? (meta.retrieved_tables as string[]) ?? [];
  const retrievedRules: string[] = message.retrievedRules ?? (meta.retrievedRules as string[]) ?? (meta.retrieved_rules as string[]) ?? [];

  // Calculate session tokens from store using real token fields only
  const allMessages = useChatStore((s) => s.messages);
  const sessionTotalTokens = allMessages.reduce((sum, m) => {
    const real = getRealTokenCounts(m);
    return sum + (real ? real.totalTokens : 0);
  }, 0);

  const pct = Math.min(100, (sessionTotalTokens / CONTEXT_CAP) * 100);
  const barColor = pct < 70 ? '#22c55e' : pct < 90 ? '#f59e0b' : '#ef4444';

  return (
    <div
      className="message-meta-strip"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexWrap: 'wrap',
        marginTop: '6px',
        fontSize: '11px',
        maxWidth: '100%',
        overflowWrap: 'anywhere',
        color: 'var(--text-muted, #94a3b8)',
      }}
    >
      {/* Model Badge */}
      <span
        style={{
          background: 'rgba(255, 255, 255, 0.06)',
          border: '1px solid var(--glass-border, rgba(255, 255, 255, 0.1))',
          padding: '2px 7px',
          borderRadius: '4px',
          fontFamily: 'monospace',
          fontSize: '10px',
          fontWeight: 600,
          color: 'var(--text-main, #e2e8f0)',
        }}
      >
        {modelName}
      </span>

      {/* Token Usage */}
      <span style={{ fontSize: '10.5px' }}>
        {realTokens
          ? `Tokens: ${realTokens.promptTokens} in / ${realTokens.completionTokens} out (${realTokens.totalTokens} total)`
          : 'Tokens: —'}
      </span>

      {/* Retrieval Chips */}
      {retrievedTables.map((tbl, i) => (
        <span
          key={`tbl-${i}`}
          style={{
            background: 'rgba(59, 130, 246, 0.12)',
            color: '#60a5fa',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: '4px',
            padding: '1px 6px',
            fontSize: '10px',
          }}
        >
          📊 {tbl}
        </span>
      ))}

      {retrievedRules.map((rule, i) => (
        <span
          key={`rule-${i}`}
          style={{
            background: 'rgba(168, 85, 247, 0.12)',
            color: '#c084fc',
            border: '1px solid rgba(168, 85, 247, 0.3)',
            borderRadius: '4px',
            padding: '1px 6px',
            fontSize: '10px',
          }}
        >
          🛡️ {rule}
        </span>
      ))}

      {/* Flagged Pattern Chip */}
      {flaggedPatterns && flaggedPatterns.length > 0 && (
        <span
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '4px',
            padding: '1px 6px',
            fontSize: '10px',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '3px',
          }}
          title={`Flagged patterns: ${flaggedPatterns.join(', ')}`}
        >
          ⚠ flagged pattern ({flaggedPatterns.join(', ')})
        </span>
      )}

      {/* Context Window Bar */}
      {sessionTotalTokens > 0 && (
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            marginLeft: 'auto',
          }}
          title={`Session Tokens: ${sessionTotalTokens.toLocaleString()} / ${(CONTEXT_CAP / 1000)}k cap (${pct.toFixed(1)}%)`}
        >
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
            Context: {(sessionTotalTokens / 1000).toFixed(1)}k/10k
          </span>
          <div
            style={{
              width: '40px',
              height: '5px',
              background: 'rgba(255, 255, 255, 0.1)',
              borderRadius: '3px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${pct}%`,
                height: '100%',
                background: barColor,
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
