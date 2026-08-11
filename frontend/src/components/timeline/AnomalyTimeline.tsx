import React from 'react';

export interface SignalItem {
  signal_id: string;
  layer: 'L1' | 'L2' | 'L3' | 'L4';
  signal_type: string;
  metric_or_relationship: string;
  score: number;
  severity: string;
  detector: string;
  provenance: string;
}

interface AnomalyTimelineProps {
  signals: SignalItem[];
}

export const AnomalyTimeline: React.FC<AnomalyTimelineProps> = ({ signals }) => {
  const getLayerBadgeColor = (layer: string) => {
    switch (layer) {
      case 'L1': return 'bg-red-900/50 text-red-300 border-red-700';
      case 'L2': return 'bg-amber-900/50 text-amber-300 border-amber-700';
      case 'L3': return 'bg-blue-900/50 text-blue-300 border-blue-700';
      case 'L4': return 'bg-purple-900/50 text-purple-300 border-purple-700';
      default: return 'bg-gray-800 text-gray-300 border-gray-700';
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg">
      <h3 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
        <span>⚡</span> 4-Layer Reliability Detection Timeline (L1-L4)
      </h3>
      <div className="space-y-3">
        {signals.map((sig) => (
          <div
            key={sig.signal_id}
            className="flex items-center justify-between p-3.5 bg-slate-950/60 border border-slate-800 rounded-lg hover:border-slate-700 transition"
          >
            <div className="flex items-center gap-3">
              <span className={`px-2.5 py-1 text-xs font-mono font-bold rounded-md border ${getLayerBadgeColor(sig.layer)}`}>
                {sig.layer}
              </span>
              <div>
                <div className="text-sm font-medium text-slate-200">{sig.metric_or_relationship}</div>
                <div className="text-xs text-slate-400">{sig.signal_type} • {sig.detector}</div>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">
                Score: {sig.score}
              </span>
              <span className={`px-2 py-0.5 text-xs font-semibold rounded ${sig.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
                {sig.severity}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
