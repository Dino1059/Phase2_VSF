import React, { useState } from 'react';
import { ShieldCheck, Lock, CheckCircle2, AlertTriangle, X, FileKey, UserCheck } from 'lucide-react';

interface HITLAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmAuthorization: (rationale: string, hashSignature: string) => void;
  actionTitle?: string;
  actionType?: string;
  ruleExpression?: string;
  targetEntity?: string;
  incidentId?: string;
  userRole?: string;
}

export const HITLAuthModal: React.FC<HITLAuthModalProps> = ({
  isOpen,
  onClose,
  onConfirmAuthorization,
  actionTitle = 'Preventive Data Quality Rule Enforcement',
  actionType = 'PREVENTIVE_DQ_RULE_PROPOSAL',
  ruleExpression = 'battery_soc >= 0.0 AND battery_soc <= 100.0',
  targetEntity = 'VIN-010',
  incidentId = 'inc-seed-01',
  userRole = 'steward',
}) => {
  const [rationale, setRationale] = useState('Verified 14-day MAD drift & contract bounds; authorizing rule deployment.');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Generate deterministic hash signature for demo
  const generateHash = () => {
    const seed = `${incidentId}-${targetEntity}-${actionType}-${Date.now()}`;
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      const char = seed.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash |= 0;
    }
    const hex = Math.abs(hash).toString(16).padStart(8, '0');
    return `HASH-SHA256-${hex.toUpperCase()}-7E91B2`;
  };

  const [hashSignature] = useState(generateHash());

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      onConfirmAuthorization(rationale, hashSignature);
      setIsSubmitting(false);
      onClose();
    }, 500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6 relative">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-start gap-4 border-b border-slate-800 pb-4">
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              HITL Authorization Flow
              <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                HASH-BOUND
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Data Steward cryptographic sign-off for automated control execution.
            </p>
          </div>
        </div>

        {/* Authorization Details Payload */}
        <div className="space-y-3 bg-slate-950/70 border border-slate-800/80 rounded-xl p-4 text-xs">
          <div className="flex justify-between items-center pb-2 border-b border-slate-800/60">
            <span className="text-slate-400 font-medium">Incident Context:</span>
            <span className="font-mono text-slate-200 bg-slate-800 px-2 py-0.5 rounded">{incidentId}</span>
          </div>

          <div className="flex justify-between items-center pb-2 border-b border-slate-800/60">
            <span className="text-slate-400 font-medium">Target Entity / Dataset:</span>
            <span className="font-mono text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">
              {targetEntity}
            </span>
          </div>

          <div className="flex justify-between items-center pb-2 border-b border-slate-800/60">
            <span className="text-slate-400 font-medium">Action Title:</span>
            <span className="font-semibold text-slate-200">{actionTitle}</span>
          </div>

          <div>
            <span className="text-slate-400 font-medium block mb-1">Proposed Policy / Rule Payload:</span>
            <code className="block bg-slate-900 border border-slate-800 px-3 py-2 rounded text-emerald-300 font-mono text-[11px]">
              {ruleExpression}
            </code>
          </div>

          <div className="flex items-center gap-2 pt-2 text-[11px] text-slate-400">
            <FileKey className="w-4 h-4 text-amber-400" />
            <span>Cryptographic State Signature:</span>
            <span className="font-mono text-slate-300 bg-slate-800 px-1.5 py-0.5 rounded text-[10px]">
              {hashSignature}
            </span>
          </div>
        </div>

        {/* User Role Verification Badge */}
        <div className="flex items-center justify-between p-3 bg-slate-800/40 border border-slate-700/50 rounded-lg text-xs">
          <div className="flex items-center gap-2 text-slate-300">
            <UserCheck className="w-4 h-4 text-indigo-400" />
            <span>Steward Role Verification:</span>
            <span className="font-semibold uppercase text-indigo-300">{userRole}</span>
          </div>
          <span className="text-[10px] text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/50 flex items-center gap-1">
            <Lock className="w-3 h-3" /> VERIFIED
          </span>
        </div>

        {/* Rationale Input */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Steward Authorization Rationale & Audit Note:
            </label>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              rows={3}
              required
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition resize-none"
              placeholder="Enter justification for approving this automated control..."
            />
          </div>

          <div className="p-3 bg-amber-950/20 border border-amber-800/40 rounded-lg text-xs text-amber-300 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <span>
              Authorizing this action will immediately bind the cryptographic signature to the execution log and update dataset quality policies.
            </span>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !rationale.trim()}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition shadow-md flex items-center gap-2"
            >
              {isSubmitting ? (
                <>Processing Authorization...</>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" /> Sign & Authorize Control
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
