import React, { useState } from 'react';
import { AnomalyTimeline, SignalItem } from '../components/timeline/AnomalyTimeline';
import { EvidencePanel, EvidenceItem } from '../components/incident/EvidencePanel';
import { HypothesisPanel, HypothesisItem } from '../components/incident/HypothesisPanel';
import { ActionPanel, RecommendationActionItem } from '../components/incident/ActionPanel';
import { ContextualAssistant } from '../components/chat/ContextualAssistant';
import {
  AlertTriangle,
  Filter,
} from 'lucide-react';

interface IncidentRecord {
  incident_id: string;
  title: string;
  target_entity: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'OPEN' | 'IN_INVESTIGATION' | 'RESOLVED';
  time_window: string;
  provenance: string;
  signals: SignalItem[];
  supportingEvidence: EvidenceItem[];
  contradictingEvidence: EvidenceItem[];
  hypotheses: HypothesisItem[];
  recommendations: RecommendationActionItem[];
}

const SEED_INCIDENTS: Record<string, IncidentRecord> = {
  'inc-seed-01': {
    incident_id: 'inc-seed-01',
    title: 'Battery SoC Boundary Violation & Discharge Rate Context Drift',
    target_entity: 'VIN-010',
    severity: 'CRITICAL',
    status: 'OPEN',
    time_window: 'Last 60 Minutes (2026-08-11 15:00:00 UTC)',
    provenance: 'SEMI_SYNTHETIC',
    signals: [
      {
        signal_id: 'sig-l1-01',
        layer: 'L1',
        signal_type: 'RANGE_VIOLATION',
        metric_or_relationship: 'battery_soc',
        score: 1.0,
        severity: 'CRITICAL',
        detector: 'L1_Constraint_Detector',
        provenance: 'SEMI_SYNTHETIC',
      },
      {
        signal_id: 'sig-l2-02',
        layer: 'L2',
        signal_type: 'CONTEXTUAL_DRIFT',
        metric_or_relationship: 'discharge_rate',
        score: 4.2,
        severity: 'HIGH',
        detector: 'L2_Contextual_Detector',
        provenance: 'SEMI_SYNTHETIC',
      },
      {
        signal_id: 'sig-l3-03',
        layer: 'L3',
        signal_type: 'CROSS_STREAM_DISCREPANCY',
        metric_or_relationship: 'bms_vs_telemetry_power',
        score: 3.1,
        severity: 'HIGH',
        detector: 'L3_CrossStream_Detector',
        provenance: 'SEMI_SYNTHETIC',
      },
    ],
    supportingEvidence: [
      {
        evidence_id: 'ev-01',
        source_type: 'telemetry',
        summary: 'VIN-010 discharge rate +4.2 MAD above 14-day rolling baseline during rapid acceleration.',
        provenance: 'SEMI_SYNTHETIC',
        confidence: 0.96,
        timestamp: '2026-08-11 15:12:04 UTC',
        details: 'Observed discharge rate of 88.4 kW versus baseline expectation of 42.1 kW (±11.0 kW).',
        metrics: { observed_discharge_kw: 88.4, baseline_kw: 42.1, mad_score: 4.2 },
      },
      {
        evidence_id: 'ev-02',
        source_type: 'bms_contract',
        summary: 'Schema contract violation detected on battery_soc lower bound (-12.4% out of range).',
        provenance: 'SEMI_SYNTHETIC',
        confidence: 0.98,
        timestamp: '2026-08-11 15:12:10 UTC',
        details: 'Column battery_soc reported negative value -12.4, breaking [0.0, 100.0] invariant contract.',
        metrics: { raw_soc_value: -12.4, expected_min: 0.0, expected_max: 100.0 },
      },
      {
        evidence_id: 'ev-03',
        source_type: 'audit_log',
        summary: 'Ingestion pipeline firmware update deployed 15 mins prior to anomaly onset.',
        provenance: 'AUDIT_TRAIL',
        confidence: 0.88,
        timestamp: '2026-08-11 14:55:00 UTC',
        details: 'Firmware release v2.4.1 modified scale factor multiplier on BMS CANbus byte array.',
      },
    ],
    contradictingEvidence: [
      {
        evidence_id: 'ev-04',
        source_type: 'baseline_stats',
        summary: 'Physical battery temperature sensors remain within normal operating thermal band (31.2°C).',
        provenance: 'REAL_TELEMETRY',
        confidence: 0.92,
        timestamp: '2026-08-11 15:14:00 UTC',
        details: 'Thermal readings rule out catastrophic physical cell degradation or thermal runaway.',
        metrics: { pack_temp_c: 31.2, max_safe_temp_c: 55.0 },
      },
    ],
    hypotheses: [
      {
        hypothesis_id: 'hyp-01',
        claim: 'Data contract violation: battery_soc range constraint broken during stream ingestion byte scaling.',
        classification: 'DATA',
        confidence: 0.92,
        status: 'PROPOSED',
        root_cause_summary:
          'Firmware v2.4.1 byte scaling offset caused signed 16-bit integer wraparound in battery_soc telemetry payload.',
        affected_entities: ['VIN-010', 'vehicle_telemetry', 'battery_soc'],
        supporting_evidence_ids: ['ev-02', 'ev-03'],
        recommended_action: 'Enforce preventive Data Quality check constraint: battery_soc BETWEEN 0.0 AND 100.0.',
      },
      {
        hypothesis_id: 'hyp-02',
        claim: 'Operational physical degradation: high internal resistance causing rapid voltage sag.',
        classification: 'OPERATIONAL',
        confidence: 0.34,
        status: 'IN_INVESTIGATION',
        root_cause_summary:
          'Possible battery pack degradation under heavy load; partially contradicted by stable pack temperature.',
        affected_entities: ['VIN-010', 'bms_pack_cell_04'],
        supporting_evidence_ids: ['ev-01'],
        contradicting_evidence_ids: ['ev-04'],
        recommended_action: 'Perform physical cell diagnostic test at next maintenance window.',
      },
    ],
    recommendations: [
      {
        action_id: 'rec-01',
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
        action_id: 'rec-02',
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
  },
  'inc-seed-02': {
    incident_id: 'inc-seed-02',
    title: 'Charging Station EVSE Current Telemetry Drop & Schema Mismatch',
    target_entity: 'EVSE-ST-042',
    severity: 'HIGH',
    status: 'OPEN',
    time_window: 'Last 30 Minutes (2026-08-11 15:30:00 UTC)',
    provenance: 'REAL_TELEMETRY',
    signals: [
      {
        signal_id: 'sig-l1-04',
        layer: 'L1',
        signal_type: 'NULL_SPIKE',
        metric_or_relationship: 'charging_current_a',
        score: 0.95,
        severity: 'HIGH',
        detector: 'L1_Null_Detector',
        provenance: 'REAL_TELEMETRY',
      },
    ],
    supportingEvidence: [
      {
        evidence_id: 'ev-05',
        source_type: 'telemetry',
        summary: 'EVSE-ST-042 charging current dropped to NULL across 45 consecutive heartbeat ticks.',
        provenance: 'REAL_TELEMETRY',
        confidence: 0.94,
        timestamp: '2026-08-11 15:32:00 UTC',
        details: 'Heartbeat received but charging_current_a field set to null value.',
      },
    ],
    contradictingEvidence: [],
    hypotheses: [
      {
        hypothesis_id: 'hyp-03',
        claim: 'Vendor API schema change: missing charging_current_a field mapping in JSON serializer.',
        classification: 'DATA',
        confidence: 0.89,
        status: 'PROPOSED',
        root_cause_summary: 'Upstream charger vendor API updated JSON payload schema key name.',
        affected_entities: ['EVSE-ST-042', 'st_evcdp_raw'],
        supporting_evidence_ids: ['ev-05'],
        recommended_action: 'Apply schema patch and non-null default rule on charging_current_a.',
      },
    ],
    recommendations: [
      {
        action_id: 'rec-03',
        title: 'Enforce Non-Null Policy on EVSE Telemetry',
        action_type: 'SCHEMA_CONTRACT_ENFORCEMENT',
        description: 'Enforce NOT NULL check with fallback default value of 0.0 Amps.',
        rule_expression: 'COALESCE(charging_current_a, 0.0) AS charging_current_a',
        target_entity: 'EVSE-ST-042',
        risk_level: 'LOW',
        expected_impact: 'Prevents null pointer errors in billing calculator.',
        execution_mode: 'C1',
        status: 'PENDING_AUTHORIZATION',
      },
    ],
  },
};

export const IncidentWorkspace: React.FC = () => {
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('inc-seed-01');
  const [investigationMode, setInvestigationMode] = useState<'R0' | 'C1' | 'A1'>('C1');
  const [isApproved, setIsApproved] = useState(false);
  const [approvalHash, setApprovalHash] = useState<string>('');
  const [activeHypothesis, setActiveHypothesis] = useState<HypothesisItem | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [userRole] = useState<string>(localStorage.getItem('datatrust-role') || 'steward');
  const [isAssistantCollapsed, setIsAssistantCollapsed] = useState(false);

  const incident = SEED_INCIDENTS[selectedIncidentId] || SEED_INCIDENTS['inc-seed-01'];

  const handleInvestigate = (mode: 'R0' | 'C1' | 'A1') => {
    setInvestigationMode(mode);
  };

  const handleApproveControl = (_rationale?: string, hashSignature?: string) => {
    setIsApproved(true);
    if (hashSignature) setApprovalHash(hashSignature);
  };

  const handleSelectIncident = (id: string) => {
    setSelectedIncidentId(id);
    setIsApproved(false);
    setApprovalHash('');
    setActiveHypothesis(null);
    setSelectedEvidence(null);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-6 font-sans">
      {/* Incident Header & Selector */}
      <header className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
                Incident Workspace
                <span className="px-2.5 py-0.5 bg-rose-500/20 text-rose-400 text-xs font-bold rounded-full border border-rose-500/30">
                  {incident.status} INCIDENT
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Multi-layer data reliability triage, RCA hypotheses ranking & HITL control authorization
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 mt-3 text-xs text-slate-400 flex-wrap">
            <div>
              Incident ID: <span className="font-mono text-slate-200 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">{incident.incident_id}</span>
            </div>
            <div>•</div>
            <div>
              Target Entity: <span className="font-mono text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">{incident.target_entity}</span>
            </div>
            <div>•</div>
            <div>
              Provenance: <span className="font-mono text-emerald-400">{incident.provenance}</span>
            </div>
            <div>•</div>
            <div>Time Window: <span className="text-slate-300">{incident.time_window}</span></div>
          </div>
        </div>

        {/* Incident Selector Dropdown / Pills */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 p-1.5 rounded-xl">
          <span className="text-xs font-semibold text-slate-400 px-2 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Incident:
          </span>
          {Object.keys(SEED_INCIDENTS).map((id) => (
            <button
              key={id}
              onClick={() => handleSelectIncident(id)}
              className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-lg transition ${
                selectedIncidentId === id
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {id}
            </button>
          ))}
        </div>
      </header>

      {/* Main Grid Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left 2 Columns: Main Incident Workflow Panels */}
        <div className="lg:col-span-2 space-y-6">
          {/* 1. Anomaly Timeline */}
          <AnomalyTimeline signals={incident.signals} />

          {/* 2. Evidence Ledger & Provenance */}
          <EvidencePanel
            supporting={incident.supportingEvidence}
            contradicting={incident.contradictingEvidence}
            onSelectEvidenceForAssistant={(ev) => setSelectedEvidence(ev)}
          />

          {/* 3. RCA Ranked Hypotheses */}
          <HypothesisPanel
            hypotheses={incident.hypotheses}
            activeHypothesisId={activeHypothesis?.hypothesis_id}
            onSelectHypothesis={(hyp) => setActiveHypothesis(hyp)}
            onAskAssistantAboutHypothesis={(hyp) => setActiveHypothesis(hyp)}
          />

          {/* 4. Recommendation Action Panel & HITL Authorization */}
          <ActionPanel
            onInvestigate={handleInvestigate}
            onApproveControl={handleApproveControl}
            activeMode={investigationMode}
            actionType={incident.recommendations[0]?.action_type || 'PREVENTIVE_DQ_RULE_PROPOSAL'}
            isApproved={isApproved}
            approvalHash={approvalHash}
            incidentId={incident.incident_id}
            targetEntity={incident.target_entity}
            userRole={userRole}
            recommendations={incident.recommendations}
          />
        </div>

        {/* Right 1 Column: Collapsible Contextual Assistant Subordinate to Workflow State */}
        <div className="lg:col-span-1 sticky top-6">
          <ContextualAssistant
            incidentId={incident.incident_id}
            investigationMode={investigationMode}
            activeHypothesis={activeHypothesis}
            selectedEvidence={selectedEvidence}
            isApproved={isApproved}
            approvalHash={approvalHash}
            userRole={userRole}
            isCollapsed={isAssistantCollapsed}
            onToggleCollapse={() => setIsAssistantCollapsed((prev) => !prev)}
          />
        </div>
      </div>
    </div>
  );
};
