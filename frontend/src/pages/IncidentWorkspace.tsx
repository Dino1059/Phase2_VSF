import React, { useState } from 'react';
import { AnomalyTimeline, SignalItem } from '../components/timeline/AnomalyTimeline';
import { EvidencePanel, EvidenceItem } from '../components/incident/EvidencePanel';
import { HypothesisPanel, HypothesisItem } from '../components/incident/HypothesisPanel';
import { ActionPanel } from '../components/incident/ActionPanel';
import { ContextualAssistant } from '../components/chat/ContextualAssistant';

export const IncidentWorkspace: React.FC = () => {
  const [incidentId] = useState('inc-seed-01');
  const [isApproved, setIsApproved] = useState(false);

  const signals: SignalItem[] = [
    {
      signal_id: 'sig-l1-01',
      layer: 'L1',
      signal_type: 'RANGE_VIOLATION',
      metric_or_relationship: 'battery_soc',
      score: 1.0,
      severity: 'CRITICAL',
      detector: 'L1_Constraint_Detector',
      provenance: 'SEMI_SYNTHETIC'
    },
    {
      signal_id: 'sig-l2-02',
      layer: 'L2',
      signal_type: 'CONTEXTUAL_DRIFT',
      metric_or_relationship: 'discharge_rate',
      score: 4.2,
      severity: 'HIGH',
      detector: 'L2_Contextual_Detector',
      provenance: 'SEMI_SYNTHETIC'
    }
  ];

  const supportingEvidence: EvidenceItem[] = [
    {
      evidence_id: 'ev-01',
      source_type: 'telemetry',
      summary: 'VIN-010 discharge rate +4.2 MAD above 14-day rolling baseline.',
      provenance: 'SEMI_SYNTHETIC'
    },
    {
      evidence_id: 'ev-02',
      source_type: 'bms_contract',
      summary: 'Schema contract violation detected on battery_soc lower bound.',
      provenance: 'SEMI_SYNTHETIC'
    }
  ];

  const hypotheses: HypothesisItem[] = [
    {
      hypothesis_id: 'hyp-01',
      claim: 'Data contract violation: battery_soc range constraint broken during ingestion.',
      classification: 'DATA',
      confidence: 0.92,
      status: 'PROPOSED'
    }
  ];

  const handleInvestigate = (mode: 'R0' | 'C1' | 'A1') => {
    alert(`Triggered ${mode} Investigation on Incident ${incidentId}`);
  };

  const handleApproveControl = () => {
    setIsApproved(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <header className="mb-6 flex justify-between items-center border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Incident Workspace</h1>
            <span className="px-2.5 py-0.5 bg-rose-500/20 text-rose-400 text-xs font-semibold rounded-full border border-rose-500/30">
              OPEN INCIDENT
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Incident ID: <span className="font-mono text-slate-300">{incidentId}</span> • Target: <span className="font-mono text-slate-300">VIN-010</span>
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <AnomalyTimeline signals={signals} />
          <EvidencePanel supporting={supportingEvidence} />
          <HypothesisPanel hypotheses={hypotheses} />
          <ActionPanel
            onInvestigate={handleInvestigate}
            onApproveControl={handleApproveControl}
            isApproved={isApproved}
          />
        </div>

        <div>
          <ContextualAssistant incidentId={incidentId} />
        </div>
      </div>
    </div>
  );
};
