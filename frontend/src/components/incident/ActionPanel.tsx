import React from 'react';

interface ActionPanelProps {
  onInvestigate: (mode: 'R0' | 'C1' | 'A1') => void;
  onApproveControl: () => void;
  actionType?: string;
  isApproved?: boolean;
}

export const ActionPanel: React.FC<ActionPanelProps> = ({
  onInvestigate,
  onApproveControl,
  actionType = 'PREVENTIVE_DQ_RULE_PROPOSAL',
  isApproved = false,
}) => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
        <span>🛡️</span> Data Steward HITL Governance Controls
      </h3>

      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold text-slate-400">Run Investigation:</span>
        <button
          onClick={() => onInvestigate('R0')}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
        >
          R0 Deterministic
        </button>
        <button
          onClick={() => onInvestigate('C1')}
          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition shadow-sm"
        >
          C1 Fixed AI
        </button>
        <button
          onClick={() => onInvestigate('A1')}
          className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition shadow-sm"
        >
          A1 Bounded AI
        </button>
      </div>

      <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
        <div>
          <div className="text-xs font-medium text-slate-300">Conditional Outcome Routing</div>
          <div className="text-xs text-slate-500">{actionType}</div>
        </div>

        {isApproved ? (
          <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-lg border border-emerald-500/30">
            ✓ Authorized & Hash-Bound
          </span>
        ) : (
          <button
            onClick={onApproveControl}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition shadow-sm"
          >
            Authorize & Execute Control
          </button>
        )}
      </div>
    </div>
  );
};
