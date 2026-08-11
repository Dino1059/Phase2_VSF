import React from 'react';

export interface EvidenceItem {
  evidence_id: string;
  source_type: string;
  summary: string;
  provenance: string;
}

interface EvidencePanelProps {
  supporting: EvidenceItem[];
  contradicting?: EvidenceItem[];
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ supporting, contradicting = [] }) => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
        <span>🔍</span> Evidence Ledger & Provenance
      </h3>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-2">Supporting Evidence</h4>
        <div className="space-y-2">
          {supporting.map((ev) => (
            <div key={ev.evidence_id} className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded-lg text-sm text-slate-200 flex justify-between items-center">
              <span>{ev.summary}</span>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded border border-emerald-700/50">
                {ev.provenance}
              </span>
            </div>
          ))}
        </div>
      </div>

      {contradicting.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-400 mb-2">Contradicting Evidence</h4>
          <div className="space-y-2">
            {contradicting.map((ev) => (
              <div key={ev.evidence_id} className="p-3 bg-rose-950/20 border border-rose-800/40 rounded-lg text-sm text-slate-200 flex justify-between items-center">
                <span>{ev.summary}</span>
                <span className="text-xs font-mono text-rose-400 bg-rose-900/40 px-2 py-0.5 rounded border border-rose-700/50">
                  {ev.provenance}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
