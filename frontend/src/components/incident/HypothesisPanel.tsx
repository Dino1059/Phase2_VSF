import React from 'react';

export interface HypothesisItem {
  hypothesis_id: string;
  claim: string;
  classification: 'DATA' | 'OPERATIONAL' | 'MIXED' | 'UNKNOWN';
  confidence: number;
  status: string;
}

interface HypothesisPanelProps {
  hypotheses: HypothesisItem[];
}

export const HypothesisPanel: React.FC<HypothesisPanelProps> = ({ hypotheses }) => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
        <span>🧠</span> RCA Ranked Hypotheses
      </h3>
      <div className="space-y-3">
        {hypotheses.map((hyp) => (
          <div key={hyp.hypothesis_id} className="p-4 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
            <div className="flex items-center justify-between">
              <span className={`px-2.5 py-0.5 text-xs font-semibold rounded ${hyp.classification === 'DATA' ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
                {hyp.classification} CAUSE
              </span>
              <span className="text-xs font-mono text-slate-400">
                Confidence: {(hyp.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-sm text-slate-200 font-medium">{hyp.claim}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
