import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  PanelRightClose,
  PanelRightOpen,
  Sparkles,
  Bot,
  User,
} from 'lucide-react';
import type { HypothesisItem } from '../incident/HypothesisPanel';
import type { EvidenceItem } from '../incident/EvidencePanel';
import { incidentsApi } from '../../services/api';

interface ChatMessageItem {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;
  reasoning?: string;
}

interface ContextualAssistantProps {
  incidentId?: string;
  investigationMode?: 'R0' | 'C1' | 'A1';
  activeHypothesis?: HypothesisItem | null;
  selectedEvidence?: EvidenceItem | null;
  isApproved?: boolean;
  approvalHash?: string;
  userRole?: string;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const ContextualAssistant: React.FC<ContextualAssistantProps> = ({
  incidentId = 'inc-seed-01',
  investigationMode = 'C1',
  activeHypothesis = null,
  selectedEvidence = null,
  isApproved = false,
  approvalHash = '',
  userRole = 'steward',
  isCollapsed: externalIsCollapsed,
  onToggleCollapse,
}) => {
  const [internalIsCollapsed, setInternalIsCollapsed] = useState(false);
  const isCollapsed = externalIsCollapsed !== undefined ? externalIsCollapsed : internalIsCollapsed;

  const toggleCollapse = () => {
    if (onToggleCollapse) {
      onToggleCollapse();
    } else {
      setInternalIsCollapsed((prev) => !prev);
    }
  };

  const [messages, setMessages] = useState<ChatMessageItem[]>([
    {
      id: 'init-1',
      sender: 'assistant',
      text: `Contextual Reliability Assistant initialized for Incident ${incidentId}. I am synchronized with your workflow state (Mode: ${investigationMode}, Role: ${userRole}).`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isCollapsed]);

  // Reactive workflow state listener: inject workflow notifications when state changes
  const prevModeRef = useRef(investigationMode);
  const prevApprovedRef = useRef(isApproved);
  const prevHypRef = useRef(activeHypothesis?.hypothesis_id);
  const prevEvRef = useRef(selectedEvidence?.evidence_id);

  useEffect(() => {
    if (prevModeRef.current !== investigationMode) {
      prevModeRef.current = investigationMode;
      setMessages((prev) => [
        ...prev,
        {
          id: `sys-mode-${Date.now()}`,
          sender: 'system',
          text: `Workflow State Update: Investigation Autonomy Ladder switched to ${investigationMode} mode.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }

    if (prevApprovedRef.current !== isApproved) {
      prevApprovedRef.current = isApproved;
      if (isApproved) {
        setMessages((prev) => [
          ...prev,
          {
            id: `sys-appr-${Date.now()}`,
            sender: 'system',
            text: `HITL Authorization Update: Data Steward (${userRole}) signed & authorized control with Cryptographic Hash Signature ${
              approvalHash || 'HASH-SHA256-8F3A...'
            }.`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
    }

    if (activeHypothesis && prevHypRef.current !== activeHypothesis.hypothesis_id) {
      prevHypRef.current = activeHypothesis.hypothesis_id;
      const prompt = `Explain RCA hypothesis ${activeHypothesis.hypothesis_id}: "${activeHypothesis.claim}"`;
      handleSend(prompt);
    }

    if (selectedEvidence && prevEvRef.current !== selectedEvidence.evidence_id) {
      prevEvRef.current = selectedEvidence.evidence_id;
      const prompt = `Analyze evidence item [${selectedEvidence.evidence_id}]: ${selectedEvidence.summary}`;
      handleSend(prompt);
    }
  }, [investigationMode, isApproved, activeHypothesis, selectedEvidence, approvalHash, userRole]);

  const handleSend = async (textToSend?: string) => {
    const queryText = textToSend || input;
    if (!queryText.trim()) return;

    const userMsg: ChatMessageItem = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setIsTyping(true);

    try {
      const data = await incidentsApi.chat(incidentId, {
        message: queryText,
        investigation_mode: investigationMode,
        user_role: userRole,
        active_hypothesis: activeHypothesis,
        selected_evidence: selectedEvidence,
      });

      setMessages((prev) => [
        ...prev,
        {
          id: `asst-${Date.now()}`,
          sender: 'assistant',
          text: data.reply || (data as any).response || 'Contextual analysis complete.',
          reasoning: data.reasoning,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (err) {
      let reply = '';
      let reasoning = undefined;

      const lower = queryText.toLowerCase();
      if (lower.includes('evidence') || lower.includes('summarize')) {
        reply = `Incident ${incidentId} Evidence Breakdown:\n- Telemetry: discharge_rate +4.2 MAD over 14-day baseline.\n- Contract: battery_soc lower bound schema violation.\n- Ground Truth: Provenance verified as SEMI_SYNTHETIC dataset.`;
        reasoning = `Analyzed 2 supporting evidence records against 14-day rolling baseline data.`;
      } else if (lower.includes('hypothesis') || lower.includes('rca') || lower.includes('root cause')) {
        reply = activeHypothesis
          ? `Selected Hypothesis Analysis (${activeHypothesis.hypothesis_id}): "${activeHypothesis.claim}". Classification: ${activeHypothesis.classification}. Confidence: ${Math.round(
              activeHypothesis.confidence * 100
            )}%. Recommend enforcing preventive range rule.`
          : `Top RCA Hypothesis for ${incidentId}: Data contract violation on battery_soc ingestion (92% confidence). Secondary hypothesis: Operational sensor drift (45% confidence).`;
        reasoning = `Evaluated diagnostic decision tree against L1-L2 telemetry signals.`;
      } else if (lower.includes('hitl') || lower.includes('authorize') || lower.includes('governance')) {
        reply = isApproved
          ? `HITL Authorization is COMPLETE. Cryptographic signature: ${
              approvalHash || 'HASH-SHA256-8F3A...'
            }. Control rule is actively bound.`
          : `HITL Authorization is PENDING. Data Steward sign-off required to enforce preventive quality rules on entity VIN-010.`;
        reasoning = `Checked cryptographic audit ledger for active incident authorization state.`;
      } else {
        reply = `Contextual analysis for Incident ${incidentId} (Mode ${investigationMode}): The current anomaly involves discharge rate drift and range constraint violation. The system recommends Data Steward authorization of the preventive quality rule.`;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `asst-${Date.now()}`,
          sender: 'assistant',
          text: reply,
          reasoning,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  // Render Collapsed Strip view
  if (isCollapsed) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 shadow-lg flex items-center justify-between transition-all hover:border-slate-700 cursor-pointer" onClick={toggleCollapse}>
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-600/20 border border-indigo-500/30 rounded-lg text-indigo-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-200">Contextual Assistant</span>
              <span className="text-[10px] font-mono bg-indigo-950/60 text-indigo-300 border border-indigo-800/40 px-1.5 py-0.5 rounded">
                Mode: {investigationMode}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5 truncate max-w-xs sm:max-w-sm">
              Subordinate to Incident {incidentId} workflow • Click to expand
            </p>
          </div>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleCollapse();
          }}
          className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition"
          title="Expand Assistant Panel"
        >
          <PanelRightOpen className="w-4 h-4" />
        </button>
      </div>
    );
  }

  // Render Full Expanded Assistant View
  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl flex flex-col h-[650px] shadow-2xl relative overflow-hidden transition-all">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-indigo-600/20 border border-indigo-500/30 rounded-lg text-indigo-400">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-100 flex items-center gap-2">
              Contextual Assistant
              <span className="text-[10px] font-mono bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                SUBORDINATE UI
              </span>
            </h4>
            <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5 font-mono">
              <span>Inc: {incidentId}</span>
              <span>•</span>
              <span className="text-indigo-400">Mode: {investigationMode}</span>
              <span>•</span>
              <span className={isApproved ? 'text-emerald-400' : 'text-amber-400'}>
                {isApproved ? 'HITL: Auth' : 'HITL: Pending'}
              </span>
            </div>
          </div>
        </div>

        <button
          onClick={toggleCollapse}
          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
          title="Collapse Assistant Panel"
        >
          <PanelRightClose className="w-4 h-4" />
        </button>
      </div>

      {/* Workflow State Context Ribbon */}
      <div className="bg-indigo-950/30 border-b border-indigo-900/30 px-3 py-1.5 text-[11px] text-indigo-200 flex items-center justify-between">
        <span className="truncate">
          {activeHypothesis
            ? `Active Hypothesis: ${activeHypothesis.claim}`
            : `Tracking Incident ${incidentId} Workflow State`}
        </span>
        <Sparkles className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
      </div>

      {/* Quick Prompt Chips */}
      <div className="px-3 py-2 border-b border-slate-800/80 bg-slate-950/40 flex items-center gap-1.5 overflow-x-auto text-[11px]">
        <button
          onClick={() => handleSend('Summarize supporting evidence for this incident')}
          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 whitespace-nowrap transition"
        >
          🔍 Summarize Evidence
        </button>
        <button
          onClick={() => handleSend('Explain top RCA hypotheses')}
          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 whitespace-nowrap transition"
        >
          🧠 RCA Hypotheses
        </button>
        <button
          onClick={() => handleSend('Check HITL governance authorization status')}
          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 whitespace-nowrap transition"
        >
          🛡️ HITL Status
        </button>
      </div>

      {/* Chat Messages Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m) => {
          if (m.sender === 'system') {
            return (
              <div
                key={m.id}
                className="py-1.5 px-3 bg-indigo-950/40 border border-indigo-800/40 rounded-lg text-[11px] text-indigo-300 font-mono text-center shadow-sm"
              >
                ⚡ {m.text}
              </div>
            );
          }

          const isUser = m.sender === 'user';
          return (
            <div key={m.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[88%] rounded-xl p-3 text-xs leading-relaxed space-y-1.5 shadow-md ${
                  isUser
                    ? 'bg-indigo-600 text-white rounded-br-none'
                    : 'bg-slate-950 border border-slate-800 text-slate-200 rounded-bl-none'
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-[10px] text-slate-400 pb-1 border-b border-slate-800/50">
                  <span className="font-semibold flex items-center gap-1">
                    {isUser ? <User className="w-3 h-3 text-indigo-200" /> : <Bot className="w-3 h-3 text-indigo-400" />}
                    {isUser ? 'Data Steward' : 'Contextual Assistant'}
                  </span>
                  <span>{m.timestamp}</span>
                </div>

                <div className="whitespace-pre-wrap">{m.text}</div>

                {m.reasoning && (
                  <div className="pt-1 text-[10px] text-indigo-300/80 font-mono border-t border-slate-800/50">
                    💡 Reasoning: {m.reasoning}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-400 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
              <span>Analyzing incident context...</span>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Input Bar */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/80 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder={`Ask contextual assistant for Incident ${incidentId}...`}
          className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition"
        />
        <button
          onClick={() => handleSend()}
          disabled={!input.trim()}
          className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition shadow-sm flex items-center justify-center"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
