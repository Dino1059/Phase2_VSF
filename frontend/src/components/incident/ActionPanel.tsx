import React, { useState } from 'react';
import { ShieldCheck, CheckCircle2, Lock, Cpu, Sparkles, Zap } from 'lucide-react';
import { HITLAuthModal } from '../hitl/HITLAuthModal';

export interface RecommendationActionItem {
  action_id: string;
  title: string;
  action_type: string;
  description: string;
  rule_expression?: string;
  target_entity: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  expected_impact: string;
  execution_mode: 'R0' | 'C1' | 'A1';
  status: 'DRAFT' | 'PENDING_AUTHORIZATION' | 'AUTHORIZED' | 'EXECUTED';
  hash_signature?: string;
}

interface ActionPanelProps {
  onInvestigate: (mode: 'R0' | 'C1' | 'A1') => void;
  onApproveControl: (rationale?: string, hashSignature?: string) => void;
  activeMode?: 'R0' | 'C1' | 'A1';
  actionType?: string;
  isApproved?: boolean;
  approvalHash?: string;
  incidentId?: string;
  targetEntity?: string;
  userRole?: string;
  recommendations?: RecommendationActionItem[];
}

export const ActionPanel: React.FC<ActionPanelProps> = ({
  onInvestigate,
  onApproveControl,
  activeMode = 'C1',
  actionType = 'PREVENTIVE_DQ_RULE_PROPOSAL',
  isApproved = false,
  approvalHash,
  incidentId = 'inc-seed-01',
  targetEntity = 'VIN-010',
  userRole = 'steward',
  recommendations = [
    {
      action_id: 'rec-act-01',
      title: 'Enforce Preventive Range Constraint on battery_soc',
      action_type: 'PREVENTIVE_DQ_RULE_PROPOSAL',
      description: 'Inject ingestion boundary rule to prevent negative or >100% SoC readings during stream ingestion.',
      rule_expression: 'ALTER TABLE vehicle_telemetry ADD CONSTRAINT check_soc_range (battery_soc >= 0.0 AND battery_soc <= 100.0)',
      target_entity: 'VIN-010',
      risk_level: 'LOW',
      expected_impact: 'Prevents downstream analytics corruption; zero data loss.',
      execution_mode: 'A1',
      status: 'PENDING_AUTHORIZATION',
    },
    {
      action_id: 'rec-act-02',
      title: 'Quarantine Telemetry Ingestion Circuit Breaker',
      action_type: 'CIRCUIT_BREAKER_QUARANTINE',
      description: 'Route records exceeding 4.0 MAD threshold to quarantine buffer until baseline recalibration.',
      rule_expression: 'ISOLATE_STREAM(source="VIN-010", metric="discharge_rate", threshold_mad=4.0)',
      target_entity: 'VIN-010',
      risk_level: 'MEDIUM',
      expected_impact: 'Isolates abnormal telemetry bursts while maintaining stream health.',
      execution_mode: 'C1',
      status: 'DRAFT',
    },
  ],
}) => {
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<RecommendationActionItem>(recommendations[0]);
  const [actionStatuses, setActionStatuses] = useState<Record<string, { status: string; hash?: string }>>({});

  const handleOpenAuthModal = (action: RecommendationActionItem) => {
    setSelectedAction(action);
    setIsAuthModalOpen(true);
  };

  const handleConfirmAuthorization = (rationale: string, hashSignature: string) => {
    setActionStatuses((prev) => ({
      ...prev,
      [selectedAction.action_id]: { status: 'AUTHORIZED', hash: hashSignature },
    }));
    onApproveControl(rationale, hashSignature);
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
      case 'HIGH':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
      case 'MEDIUM':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'LOW':
      default:
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <span className="p-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </span>
            Recommendation Action Panel & HITL Controls
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated recommendations ({actionType}) & Data Steward authorization gating
          </p>
        </div>

        {/* Global Authorization Status Badge */}
        {isApproved ? (
          <div className="flex items-center gap-2 bg-emerald-950/40 border border-emerald-500/40 px-3 py-1.5 rounded-lg text-xs font-medium text-emerald-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Authorized & Hash-Bound</span>
          </div>
        ) : (
          <span className="px-3 py-1 bg-amber-500/10 text-amber-400 text-xs font-semibold rounded-lg border border-amber-500/20 flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" /> Authorization Pending
          </span>
        )}
      </div>

      {/* Investigation Mode Selector */}
      <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3.5 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            Select Investigation Autonomy Ladder:
          </span>
          <span className="text-[11px] font-mono text-indigo-400">Active Mode: {activeMode}</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <button
            onClick={() => onInvestigate('R0')}
            className={`p-2.5 rounded-lg border text-left transition flex flex-col justify-between ${
              activeMode === 'R0'
                ? 'bg-slate-800 border-slate-600 text-slate-100'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-200">R0 Deterministic</span>
              <span className="text-[10px] font-mono bg-slate-950 px-1.5 py-0.5 rounded text-slate-400">Static</span>
            </div>
            <span className="text-[11px] text-slate-400">Rule-based contract checks & exact threshold matching</span>
          </button>

          <button
            onClick={() => onInvestigate('C1')}
            className={`p-2.5 rounded-lg border text-left transition flex flex-col justify-between ${
              activeMode === 'C1'
                ? 'bg-indigo-950/50 border-indigo-500 text-indigo-100 shadow-indigo-950/30'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-indigo-300 flex items-center gap-1">
                <Cpu className="w-3 h-3" /> C1 Fixed AI
              </span>
              <span className="text-[10px] font-mono bg-indigo-950 px-1.5 py-0.5 rounded text-indigo-300">Heuristic</span>
            </div>
            <span className="text-[11px] text-slate-400">Fixed heuristic workflow agents for pattern diagnosis</span>
          </button>

          <button
            onClick={() => onInvestigate('A1')}
            className={`p-2.5 rounded-lg border text-left transition flex flex-col justify-between ${
              activeMode === 'A1'
                ? 'bg-purple-950/50 border-purple-500 text-purple-100 shadow-purple-950/30'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-purple-300 flex items-center gap-1">
                <Sparkles className="w-3 h-3" /> A1 Bounded AI
              </span>
              <span className="text-[10px] font-mono bg-purple-950 px-1.5 py-0.5 rounded text-purple-300">Dynamic</span>
            </div>
            <span className="text-[11px] text-slate-400">Autonomous synthesis with hash-bound HITL gating</span>
          </button>
        </div>
      </div>

      {/* Recommended Action Cards */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Recommended Governance & Mitigation Actions
        </h4>

        {recommendations.map((action) => {
          const actionState = actionStatuses[action.action_id];
          const isActionAuthorized = actionState?.status === 'AUTHORIZED' || isApproved;
          const currentHash = actionState?.hash || approvalHash;

          return (
            <div
              key={action.action_id}
              className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3 hover:border-slate-700 transition"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono bg-slate-900 text-indigo-400 px-2 py-0.5 rounded border border-slate-800">
                      {action.action_type}
                    </span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${getRiskBadge(action.risk_level)}`}>
                      {action.risk_level} RISK
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                      Mode: {action.execution_mode}
                    </span>
                  </div>
                  <h5 className="text-sm font-bold text-slate-100">{action.title}</h5>
                </div>

                {isActionAuthorized ? (
                  <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-lg border border-emerald-500/30 flex items-center gap-1 flex-shrink-0">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Authorized
                  </span>
                ) : (
                  <button
                    onClick={() => handleOpenAuthModal(action)}
                    className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition shadow-sm flex items-center gap-1.5 flex-shrink-0"
                  >
                    <Lock className="w-3.5 h-3.5" /> Authorize Control
                  </button>
                )}
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">{action.description}</p>

              {action.rule_expression && (
                <code className="block bg-slate-900 border border-slate-800 p-2.5 rounded-lg text-emerald-400 font-mono text-[11px]">
                  {action.rule_expression}
                </code>
              )}

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-800/60 text-xs">
                <span className="text-slate-400 text-[11px]">
                  Expected Impact: <span className="text-slate-200 font-medium">{action.expected_impact}</span>
                </span>

                {isActionAuthorized && currentHash && (
                  <span className="font-mono text-[10px] text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                    Hash Signature: {currentHash}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* HITL Authorization Modal */}
      <HITLAuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onConfirmAuthorization={handleConfirmAuthorization}
        actionTitle={selectedAction?.title}
        actionType={selectedAction?.action_type}
        ruleExpression={selectedAction?.rule_expression}
        targetEntity={targetEntity}
        incidentId={incidentId}
        userRole={userRole}
      />
    </div>
  );
};
