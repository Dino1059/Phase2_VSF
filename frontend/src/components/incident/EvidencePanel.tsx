import React, { useState } from 'react';
import { Search, ShieldAlert, CheckCircle2, AlertCircle, ChevronDown, ChevronUp, Database, Sparkles } from 'lucide-react';

export interface EvidenceItem {
  evidence_id: string;
  source_type: string;
  summary: string;
  provenance: string;
  confidence?: number;
  timestamp?: string;
  details?: string;
  metrics?: Record<string, string | number>;
  type?: 'SUPPORTING' | 'CONTRADICTING' | 'NEUTRAL';
}

interface EvidencePanelProps {
  supporting: EvidenceItem[];
  contradicting?: EvidenceItem[];
  onSelectEvidenceForAssistant?: (evidence: EvidenceItem) => void;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({
  supporting,
  contradicting = [],
  onSelectEvidenceForAssistant,
}) => {
  const [filterType, setFilterType] = useState<'ALL' | 'SUPPORTING' | 'CONTRADICTING'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Normalize evidence items with type flag
  const allEvidence: EvidenceItem[] = [
    ...supporting.map((item) => ({ ...item, type: item.type || ('SUPPORTING' as const) })),
    ...contradicting.map((item) => ({ ...item, type: item.type || ('CONTRADICTING' as const) })),
  ];

  const filteredEvidence = allEvidence.filter((item) => {
    const matchesType =
      filterType === 'ALL' ||
      (filterType === 'SUPPORTING' && item.type === 'SUPPORTING') ||
      (filterType === 'CONTRADICTING' && item.type === 'CONTRADICTING');

    const matchesSearch =
      searchQuery.trim() === '' ||
      item.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.evidence_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.provenance.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.source_type.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesType && matchesSearch;
  });

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const getSourceIcon = (sourceType: string) => {
    switch (sourceType.toLowerCase()) {
      case 'telemetry':
      case 'sensor_reading':
        return <Database className="w-3.5 h-3.5 text-blue-400" />;
      case 'bms_contract':
      case 'contract':
        return <ShieldAlert className="w-3.5 h-3.5 text-indigo-400" />;
      case 'baseline_stats':
        return <Sparkles className="w-3.5 h-3.5 text-amber-400" />;
      default:
        return <Database className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  const getProvenanceBadgeColor = (provenance: string) => {
    switch (provenance.toUpperCase()) {
      case 'REAL_TELEMETRY':
        return 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60';
      case 'SEMI_SYNTHETIC':
        return 'bg-blue-950/60 text-blue-300 border-blue-700/60';
      case 'AUDIT_TRAIL':
        return 'bg-purple-950/60 text-purple-300 border-purple-700/60';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <span className="p-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
            <Search className="w-4 h-4" />
          </span>
          Evidence Ledger & Provenance
          <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
            {allEvidence.length} items
          </span>
        </h3>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 bg-slate-950/80 p-1 border border-slate-800 rounded-lg text-xs">
          <button
            onClick={() => setFilterType('ALL')}
            className={`px-2.5 py-1 rounded font-medium transition ${
              filterType === 'ALL' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({allEvidence.length})
          </button>
          <button
            onClick={() => setFilterType('SUPPORTING')}
            className={`px-2.5 py-1 rounded font-medium transition flex items-center gap-1 ${
              filterType === 'SUPPORTING' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <CheckCircle2 className="w-3 h-3" />
            Supporting ({supporting.length})
          </button>
          {contradicting.length > 0 && (
            <button
              onClick={() => setFilterType('CONTRADICTING')}
              className={`px-2.5 py-1 rounded font-medium transition flex items-center gap-1 ${
                filterType === 'CONTRADICTING' ? 'bg-rose-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <AlertCircle className="w-3 h-3" />
              Contradicting ({contradicting.length})
            </button>
          )}
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter evidence by keyword, provenance, or source type..."
          className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 hover:text-slate-300"
          >
            Clear
          </button>
        )}
      </div>

      {/* Evidence Items List */}
      <div className="space-y-3">
        {filteredEvidence.length === 0 ? (
          <div className="p-6 text-center text-slate-500 text-xs border border-dashed border-slate-800 rounded-lg">
            No evidence items match your filter criteria.
          </div>
        ) : (
          filteredEvidence.map((ev) => {
            const isExpanded = expandedId === ev.evidence_id;
            const isSupporting = ev.type === 'SUPPORTING';

            return (
              <div
                key={ev.evidence_id}
                className={`border rounded-lg transition-all ${
                  isSupporting
                    ? 'bg-emerald-950/10 border-emerald-800/40 hover:border-emerald-700/60'
                    : 'bg-rose-950/10 border-rose-800/40 hover:border-rose-700/60'
                }`}
              >
                {/* Top Row */}
                <div className="p-3.5 flex items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[11px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                        {ev.evidence_id}
                      </span>

                      <span className="text-[10px] font-medium text-slate-300 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/80 flex items-center gap-1">
                        {getSourceIcon(ev.source_type)}
                        {ev.source_type}
                      </span>

                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border ${getProvenanceBadgeColor(
                          ev.provenance
                        )}`}
                      >
                        {ev.provenance}
                      </span>

                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                          isSupporting
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                        }`}
                      >
                        {isSupporting ? '✓ SUPPORTING' : '✕ CONTRADICTING'}
                      </span>
                    </div>

                    <p className="text-xs text-slate-200 font-medium leading-relaxed">{ev.summary}</p>
                  </div>

                  <div className="flex items-center gap-2">
                    {onSelectEvidenceForAssistant && (
                      <button
                        onClick={() => onSelectEvidenceForAssistant(ev)}
                        title="Send to Assistant for analysis"
                        className="px-2 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-[11px] font-medium rounded border border-indigo-500/30 transition flex items-center gap-1"
                      >
                        <Sparkles className="w-3 h-3 text-indigo-400" />
                        Analyze
                      </button>
                    )}
                    <button
                      onClick={() => toggleExpand(ev.evidence_id)}
                      className="p-1 text-slate-400 hover:text-slate-200 transition"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded Details Drawer */}
                {isExpanded && (
                  <div className="px-3.5 pb-3.5 pt-2 border-t border-slate-800/60 bg-slate-950/40 space-y-2 text-xs">
                    {ev.details && (
                      <div>
                        <span className="text-slate-400 text-[11px] font-semibold block mb-0.5">Evidence Details:</span>
                        <p className="text-slate-300 bg-slate-900 p-2 rounded border border-slate-800 text-[11px] leading-relaxed">
                          {ev.details}
                        </p>
                      </div>
                    )}

                    {ev.metrics && (
                      <div>
                        <span className="text-slate-400 text-[11px] font-semibold block mb-1">Metric Telemetry Snapshot:</span>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          {Object.entries(ev.metrics).map(([k, v]) => (
                            <div key={k} className="bg-slate-900 border border-slate-800 px-2.5 py-1.5 rounded">
                              <div className="text-[10px] text-slate-500 font-mono uppercase">{k}</div>
                              <div className="text-xs font-mono text-indigo-300 font-semibold">{String(v)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {ev.confidence !== undefined && (
                      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                        <span>Evidence Weight / Confidence Score:</span>
                        <span className="font-mono text-emerald-400 font-semibold">
                          {(ev.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
