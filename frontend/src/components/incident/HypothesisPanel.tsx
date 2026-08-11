import React, { useState } from 'react';
import { Brain, Sparkles, ChevronDown, ChevronUp, Tag, ArrowRight } from 'lucide-react';

export interface HypothesisItem {
  hypothesis_id: string;
  claim: string;
  classification: 'DATA' | 'OPERATIONAL' | 'MIXED' | 'UNKNOWN';
  confidence: number; // 0.0 to 1.0
  status: 'PROPOSED' | 'VALIDATED' | 'REJECTED' | 'IN_INVESTIGATION' | string;
  root_cause_summary?: string;
  affected_entities?: string[];
  supporting_evidence_ids?: string[];
  contradicting_evidence_ids?: string[];
  recommended_action?: string;
}

interface HypothesisPanelProps {
  hypotheses: HypothesisItem[];
  activeHypothesisId?: string;
  onSelectHypothesis?: (hypothesis: HypothesisItem) => void;
  onAskAssistantAboutHypothesis?: (hypothesis: HypothesisItem) => void;
}

export const HypothesisPanel: React.FC<HypothesisPanelProps> = ({
  hypotheses,
  activeHypothesisId,
  onSelectHypothesis,
  onAskAssistantAboutHypothesis,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(hypotheses[0]?.hypothesis_id || null);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const getClassificationBadge = (classification: string) => {
    switch (classification.toUpperCase()) {
      case 'DATA':
        return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30';
      case 'OPERATIONAL':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'MIXED':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'VALIDATED':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'REJECTED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
      case 'IN_INVESTIGATION':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'PROPOSED':
      default:
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    }
  };

  const sortedHypotheses = [...hypotheses].sort((a, b) => b.confidence - a.confidence);

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <span className="p-1.5 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">
            <Brain className="w-4 h-4" />
          </span>
          RCA Ranked Hypotheses
          <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
            {hypotheses.length} ranked
          </span>
        </h3>
        <span className="text-xs text-slate-400">Ranked by ML Confidence</span>
      </div>

      {/* Hypotheses Cards */}
      <div className="space-y-3">
        {sortedHypotheses.map((hyp) => {
          const isExpanded = expandedId === hyp.hypothesis_id;
          const isSelected = activeHypothesisId === hyp.hypothesis_id;
          const confidencePct = Math.round(hyp.confidence * 100);

          return (
            <div
              key={hyp.hypothesis_id}
              className={`border rounded-xl transition-all ${
                isSelected
                  ? 'bg-indigo-950/30 border-indigo-500/60 shadow-indigo-950/40 shadow-lg'
                  : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              {/* Card Header */}
              <div className="p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                      {hyp.hypothesis_id}
                    </span>

                    <span className={`px-2.5 py-0.5 text-xs font-semibold rounded border ${getClassificationBadge(hyp.classification)}`}>
                      {hyp.classification} CAUSE
                    </span>

                    <span className={`px-2 py-0.5 text-[11px] font-medium rounded border ${getStatusBadge(hyp.status)}`}>
                      {hyp.status}
                    </span>
                  </div>

                  {/* Confidence Score Badge & Bar */}
                  <div className="flex items-center gap-2">
                    <div className="w-20 bg-slate-800 h-2 rounded-full overflow-hidden hidden sm:block">
                      <div
                        className={`h-full rounded-full ${
                          confidencePct >= 80
                            ? 'bg-emerald-500'
                            : confidencePct >= 60
                            ? 'bg-indigo-500'
                            : 'bg-amber-500'
                        }`}
                        style={{ width: `${confidencePct}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono font-bold text-slate-200 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
                      {confidencePct}% Conf.
                    </span>
                  </div>
                </div>

                {/* Claim Title */}
                <div
                  onClick={() => onSelectHypothesis?.(hyp)}
                  className="cursor-pointer hover:text-indigo-300 transition"
                >
                  <p className="text-sm font-semibold text-slate-100 leading-snug">{hyp.claim}</p>
                </div>

                {/* Linked Evidence Pills */}
                {((hyp.supporting_evidence_ids && hyp.supporting_evidence_ids.length > 0) ||
                  (hyp.affected_entities && hyp.affected_entities.length > 0)) && (
                  <div className="flex items-center gap-2 text-xs flex-wrap pt-1">
                    {hyp.affected_entities && (
                      <div className="flex items-center gap-1 text-[11px] text-slate-400">
                        <Tag className="w-3 h-3 text-indigo-400" />
                        <span>Entities:</span>
                        {hyp.affected_entities.map((e) => (
                          <span key={e} className="font-mono text-indigo-300 bg-indigo-950/40 px-1.5 py-0.5 rounded border border-indigo-800/40">
                            {e}
                          </span>
                        ))}
                      </div>
                    )}

                    {hyp.supporting_evidence_ids && (
                      <div className="flex items-center gap-1 text-[11px] text-slate-400 ml-auto">
                        <span>Supporting Evidence:</span>
                        {hyp.supporting_evidence_ids.map((evId) => (
                          <span key={evId} className="font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/40">
                            {evId}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Action Bar */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onSelectHypothesis?.(hyp)}
                      className={`px-2.5 py-1 rounded text-[11px] font-semibold transition border ${
                        isSelected
                          ? 'bg-indigo-600 text-white border-indigo-500'
                          : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                      }`}
                    >
                      {isSelected ? '✓ Selected Hypothesis' : 'Select Hypothesis'}
                    </button>

                    {onAskAssistantAboutHypothesis && (
                      <button
                        onClick={() => onAskAssistantAboutHypothesis(hyp)}
                        className="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-[11px] font-medium rounded border border-purple-500/30 transition flex items-center gap-1"
                      >
                        <Sparkles className="w-3 h-3 text-purple-400" />
                        Ask Assistant
                      </button>
                    )}
                  </div>

                  <button
                    onClick={() => toggleExpand(hyp.hypothesis_id)}
                    className="text-slate-400 hover:text-slate-200 transition flex items-center gap-1 text-[11px]"
                  >
                    <span>{isExpanded ? 'Hide RCA Drilldown' : 'View RCA Drilldown'}</span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {/* Expandable Root Cause Analysis Breakdown */}
              {isExpanded && (
                <div className="p-4 bg-slate-950/80 border-t border-slate-800 space-y-3 text-xs rounded-b-xl">
                  {hyp.root_cause_summary && (
                    <div>
                      <span className="text-slate-400 font-semibold block mb-1">Diagnostic Root Cause Detail:</span>
                      <p className="text-slate-300 bg-slate-900 p-2.5 rounded border border-slate-800 text-xs leading-relaxed">
                        {hyp.root_cause_summary}
                      </p>
                    </div>
                  )}

                  {hyp.recommended_action && (
                    <div className="p-2.5 bg-indigo-950/20 border border-indigo-800/40 rounded-lg text-indigo-200 flex items-start gap-2">
                      <ArrowRight className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-indigo-300 block">Recommended Diagnostic Action:</span>
                        <span>{hyp.recommended_action}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
