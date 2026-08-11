import React, { useEffect, useState, useCallback } from 'react';
import { AnomalyTimeline, SignalItem } from '../components/timeline/AnomalyTimeline';
import { EvidencePanel, EvidenceItem } from '../components/incident/EvidencePanel';
import { HypothesisPanel, HypothesisItem } from '../components/incident/HypothesisPanel';
import { ActionPanel, RecommendationActionItem } from '../components/incident/ActionPanel';
import { ContextualAssistant } from '../components/chat/ContextualAssistant';
import {
  AlertTriangle,
  AlertCircle,
  Filter,
  RefreshCw,
} from 'lucide-react';
import {
  incidentsApi,
  signalsApi,
  fetchIncident,
  IncidentInfo,
  SignalInfo,
} from '../services/api';

interface IncidentRecord {
  incident_id: string;
  title: string;
  target_entity: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'OPEN' | 'IN_INVESTIGATION' | 'RESOLVED' | string;
  time_window: string;
  provenance: string;
  signals: SignalItem[];
  supportingEvidence: EvidenceItem[];
  contradictingEvidence: EvidenceItem[];
  hypotheses: HypothesisItem[];
  recommendations: RecommendationActionItem[];
}

function normalizeIncident(
  fetchedData: IncidentInfo & Record<string, any>,
  fetchedSignals: SignalInfo[] = [],
  investigationRes?: any
): IncidentRecord {
  const incidentId = fetchedData.incident_id || 'inc-01';
  const targetEntity =
    fetchedData.target_entity ||
    fetchedData.targetEntity ||
    (fetchedData.entity_ids && fetchedData.entity_ids[0]) ||
    'VIN-010';

  const title =
    fetchedData.title ||
    fetchedData.admission_reason ||
    `Incident ${incidentId} - Telemetry Anomaly`;

  const severity = (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(fetchedData.severity)
    ? fetchedData.severity
    : 'HIGH') as 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

  const status = fetchedData.status || 'OPEN';

  let timeWindowStr = 'Last 60 Minutes';
  if (typeof fetchedData.time_window === 'string') {
    timeWindowStr = fetchedData.time_window;
  } else if (fetchedData.time_window && typeof fetchedData.time_window === 'object') {
    const start = fetchedData.time_window.start || '';
    const end = fetchedData.time_window.end || '';
    timeWindowStr = start && end ? `${start} - ${end}` : start || end || 'Last 60 Minutes';
  } else if (fetchedData.created_at) {
    timeWindowStr = `Created at ${new Date(fetchedData.created_at).toLocaleString()}`;
  }

  const provenance = fetchedData.provenance || 'REAL_TELEMETRY';

  // 1. Signals
  let signals: SignalItem[] = [];
  if (Array.isArray(fetchedData.signals) && fetchedData.signals.length > 0) {
    signals = fetchedData.signals.map((sig: any) => ({
      signal_id: sig.signal_id || `sig-${Math.random().toString(36).substr(2, 6)}`,
      layer: sig.layer || 'L1',
      signal_type: sig.signal_type || 'RANGE_VIOLATION',
      metric_or_relationship: sig.metric_or_relationship || 'battery_soc',
      score: typeof sig.score === 'number' ? sig.score : 1.0,
      severity: sig.severity || severity,
      detector: sig.detector || 'L1_Detector',
      provenance: sig.provenance || provenance,
    }));
  } else {
    const matchedSignals = fetchedSignals.filter(
      (s) =>
        (fetchedData.signal_ids && fetchedData.signal_ids.includes(s.signal_id)) ||
        (fetchedData.entity_ids && s.entity_ids && s.entity_ids.some((e) => fetchedData.entity_ids.includes(e)))
    );

    if (matchedSignals.length > 0) {
      signals = matchedSignals.map((sig) => ({
        signal_id: sig.signal_id,
        layer: (sig.layer as any) || 'L1',
        signal_type: sig.signal_type,
        metric_or_relationship: sig.metric_or_relationship,
        score: sig.score,
        severity: sig.severity,
        detector: sig.detector,
        provenance: sig.provenance,
      }));
    } else {
      const layers = fetchedData.supporting_layers && fetchedData.supporting_layers.length > 0
        ? fetchedData.supporting_layers
        : ['L1', 'L2'];

      signals = layers.map((layerStr: string, idx: number) => ({
        signal_id: fetchedData.signal_ids?.[idx] || `sig-${layerStr.toLowerCase()}-${idx + 1}`,
        layer: (['L1', 'L2', 'L3', 'L4'].includes(layerStr) ? layerStr : 'L1') as any,
        signal_type: layerStr === 'L1' ? 'RANGE_VIOLATION' : layerStr === 'L2' ? 'CONTEXTUAL_DRIFT' : 'CROSS_STREAM_DISCREPANCY',
        metric_or_relationship: fetchedData.admission_reason?.toLowerCase().includes('soc') ? 'battery_soc' : 'discharge_rate',
        score: layerStr === 'L1' ? 1.0 : 4.2,
        severity: severity,
        detector: `${layerStr}_Constraint_Detector`,
        provenance: provenance,
      }));
    }
  }

  // 2. Supporting Evidence
  let supportingEvidence: EvidenceItem[] = [];
  if (Array.isArray(fetchedData.supportingEvidence) && fetchedData.supportingEvidence.length > 0) {
    supportingEvidence = fetchedData.supportingEvidence;
  } else if (Array.isArray(fetchedData.supporting_evidence) && fetchedData.supporting_evidence.length > 0) {
    supportingEvidence = fetchedData.supporting_evidence.map((ev: any) => ({
      evidence_id: ev.evidence_id || `ev-${Math.random().toString(36).substr(2, 6)}`,
      source_type: ev.source_type || 'telemetry',
      summary: ev.summary || ev.claim || 'Observed telemetry anomaly',
      provenance: ev.provenance || provenance,
      confidence: ev.confidence ?? 0.95,
      timestamp: ev.timestamp || fetchedData.created_at || new Date().toISOString(),
      details: ev.details || ev.summary,
      metrics: ev.metrics || {},
      type: 'SUPPORTING',
    }));
  } else {
    const facts = fetchedData.confirmed_facts && fetchedData.confirmed_facts.length > 0
      ? fetchedData.confirmed_facts
      : [fetchedData.admission_reason || `Anomaly detected for entity ${targetEntity}`];

    supportingEvidence = facts.map((fact: string, idx: number) => ({
      evidence_id: `ev-supp-${idx + 1}`,
      source_type: 'telemetry',
      summary: fact,
      provenance: provenance,
      confidence: 0.95,
      timestamp: fetchedData.created_at || new Date().toISOString(),
      details: `Telemetry observation for entity ${targetEntity}: ${fact}`,
      type: 'SUPPORTING',
    }));
  }

  // 3. Contradicting Evidence
  let contradictingEvidence: EvidenceItem[] = [];
  if (Array.isArray(fetchedData.contradictingEvidence) && fetchedData.contradictingEvidence.length > 0) {
    contradictingEvidence = fetchedData.contradictingEvidence;
  } else if (Array.isArray(fetchedData.contradicting_evidence) && fetchedData.contradicting_evidence.length > 0) {
    contradictingEvidence = fetchedData.contradicting_evidence.map((ev: any) => ({
      evidence_id: ev.evidence_id || `ev-${Math.random().toString(36).substr(2, 6)}`,
      source_type: ev.source_type || 'baseline_stats',
      summary: ev.summary || ev.claim || 'Normal operating baseline maintained',
      provenance: ev.provenance || provenance,
      confidence: ev.confidence ?? 0.9,
      timestamp: ev.timestamp || fetchedData.created_at || new Date().toISOString(),
      details: ev.details || ev.summary,
      type: 'CONTRADICTING',
    }));
  }

  // 4. Hypotheses
  let hypotheses: HypothesisItem[] = [];
  if (Array.isArray(fetchedData.hypotheses) && fetchedData.hypotheses.length > 0) {
    hypotheses = fetchedData.hypotheses;
  } else if (investigationRes && investigationRes.hypothesis) {
    const h = investigationRes.hypothesis;
    hypotheses = [
      {
        hypothesis_id: h.hypothesis_id || 'hyp-01',
        claim: h.claim || `Data contract anomaly: ${fetchedData.admission_reason}`,
        classification: (['DATA', 'OPERATIONAL', 'MIXED', 'UNKNOWN'].includes(h.classification)
          ? h.classification
          : 'DATA') as any,
        confidence: typeof h.confidence === 'number' ? h.confidence : 0.92,
        status: h.status || 'PROPOSED',
        root_cause_summary: h.claim || fetchedData.admission_reason,
        affected_entities: fetchedData.entity_ids || [targetEntity],
        supporting_evidence_ids: h.supporting_evidence || supportingEvidence.map((e) => e.evidence_id),
        contradicting_evidence_ids: h.contradicting_evidence || contradictingEvidence.map((e) => e.evidence_id),
        recommended_action: 'Enforce preventive Data Quality check constraint',
      },
    ];
  } else {
    hypotheses = [
      {
        hypothesis_id: 'hyp-01',
        claim: `Data contract violation: ${fetchedData.admission_reason || 'Anomaly detected during stream ingestion.'}`,
        classification: 'DATA',
        confidence: 0.92,
        status: 'PROPOSED',
        root_cause_summary: `Schema constraint or telemetry scaling boundary broken on ${targetEntity}.`,
        affected_entities: [targetEntity],
        supporting_evidence_ids: supportingEvidence.map((e) => e.evidence_id),
        contradicting_evidence_ids: contradictingEvidence.map((e) => e.evidence_id),
        recommended_action: `Enforce preventive Data Quality check constraint on ${targetEntity}.`,
      },
    ];
  }

  // 5. Recommendations
  let recommendations: RecommendationActionItem[] = [];
  if (Array.isArray(fetchedData.recommendations) && fetchedData.recommendations.length > 0) {
    recommendations = fetchedData.recommendations;
  } else if (investigationRes && investigationRes.recommendation) {
    const r = investigationRes.recommendation;
    recommendations = [
      {
        action_id: r.recommendation_id || 'rec-01',
        title: r.summary || `Enforce Preventive Range Constraint on ${targetEntity}`,
        action_type: r.action_type || 'PREVENTIVE_DQ_RULE_PROPOSAL',
        description: r.summary || 'Inject ingestion boundary rule to prevent out-of-range telemetry readings.',
        rule_expression: r.details?.rule_expression || `ALTER TABLE vehicle_telemetry ADD CONSTRAINT check_soc_range (battery_soc >= 0.0 AND battery_soc <= 100.0)`,
        target_entity: targetEntity,
        risk_level: 'LOW',
        expected_impact: 'Prevents downstream analytics corruption; zero data loss.',
        execution_mode: (investigationRes.mode as any) || 'C1',
        status: 'PENDING_AUTHORIZATION',
      },
    ];
  } else {
    recommendations = [
      {
        action_id: 'rec-01',
        title: `Enforce Preventive Range Constraint on ${targetEntity}`,
        action_type: 'PREVENTIVE_DQ_RULE_PROPOSAL',
        description: `Inject boundary rule to prevent out-of-bounds readings for ${targetEntity}.`,
        rule_expression: `ALTER TABLE vehicle_telemetry ADD CONSTRAINT check_soc_range (battery_soc >= 0.0 AND battery_soc <= 100.0)`,
        target_entity: targetEntity,
        risk_level: 'LOW',
        expected_impact: 'Prevents downstream analytics corruption; zero data loss.',
        execution_mode: 'C1',
        status: 'PENDING_AUTHORIZATION',
      },
    ];
  }

  return {
    incident_id: incidentId,
    title,
    target_entity: targetEntity,
    severity,
    status: status as any,
    time_window: timeWindowStr,
    provenance,
    signals,
    supportingEvidence,
    contradictingEvidence,
    hypotheses,
    recommendations,
  };
}

export const IncidentWorkspace: React.FC = () => {
  const [incidentsList, setIncidentsList] = useState<IncidentInfo[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [investigationMode, setInvestigationMode] = useState<'R0' | 'C1' | 'A1'>('C1');
  const [isApproved, setIsApproved] = useState(false);
  const [approvalHash, setApprovalHash] = useState<string>('');
  const [activeHypothesis, setActiveHypothesis] = useState<HypothesisItem | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [userRole] = useState<string>(localStorage.getItem('datatrust-role') || 'steward');
  const [isAssistantCollapsed, setIsAssistantCollapsed] = useState(false);

  const loadIncidentData = useCallback(async (targetId?: string) => {
    setLoading(true);
    setError(null);
    try {
      let list = incidentsList;
      if (list.length === 0) {
        list = await incidentsApi.list('proj-vingroup-pilot');
        setIncidentsList(list || []);
      }

      const activeId = targetId || selectedIncidentId || (list && list.length > 0 ? list[0].incident_id : '');

      if (!activeId) {
        setIncident(null);
        setLoading(false);
        return;
      }

      if (activeId !== selectedIncidentId) {
        setSelectedIncidentId(activeId);
      }

      // Fetch incident details using fetchIncident(id) from api.ts
      const fetchedData = await fetchIncident(activeId);

      const [fetchedSignals, invRes] = await Promise.all([
        signalsApi.list('proj-vingroup-pilot').catch(() => []),
        incidentsApi.investigate(activeId, investigationMode).catch(() => null),
      ]);

      const normalized = normalizeIncident(fetchedData, fetchedSignals, invRes);
      setIncident(normalized);
      if (normalized.hypotheses.length > 0) {
        setActiveHypothesis(normalized.hypotheses[0]);
      }
    } catch (err: any) {
      console.error('Error fetching incident data:', err);
      setError(err.message || `Failed to fetch incident details from /api/v1/incidents endpoint.`);
    } finally {
      setLoading(false);
    }
  }, [incidentsList, selectedIncidentId, investigationMode]);

  useEffect(() => {
    loadIncidentData();
  }, []);

  const handleSelectIncident = (id: string) => {
    setSelectedIncidentId(id);
    setIsApproved(false);
    setApprovalHash('');
    setActiveHypothesis(null);
    setSelectedEvidence(null);
    loadIncidentData(id);
  };

  const handleInvestigate = async (mode: 'R0' | 'C1' | 'A1') => {
    setInvestigationMode(mode);
    if (!selectedIncidentId || !incident) return;
    try {
      const invRes = await incidentsApi.investigate(selectedIncidentId, mode);
      if (invRes) {
        const updatedHypotheses: HypothesisItem[] = invRes.hypothesis
          ? [
              {
                hypothesis_id: invRes.hypothesis.hypothesis_id || `hyp-${mode}`,
                claim: invRes.hypothesis.claim || incident.title,
                classification: (['DATA', 'OPERATIONAL', 'MIXED', 'UNKNOWN'].includes(invRes.hypothesis.classification)
                  ? invRes.hypothesis.classification
                  : 'DATA') as any,
                confidence: typeof invRes.hypothesis.confidence === 'number' ? invRes.hypothesis.confidence : 0.92,
                status: invRes.hypothesis.status || 'PROPOSED',
                root_cause_summary: invRes.hypothesis.claim || incident.title,
                affected_entities: [incident.target_entity],
                supporting_evidence_ids: invRes.hypothesis.supporting_evidence || [],
                contradicting_evidence_ids: invRes.hypothesis.contradicting_evidence || [],
                recommended_action: 'Enforce preventive Data Quality check constraint',
              },
            ]
          : incident.hypotheses;

        const updatedRecs: RecommendationActionItem[] = invRes.recommendation
          ? [
              {
                action_id: invRes.recommendation.recommendation_id || `rec-${mode}`,
                title: invRes.recommendation.summary || 'Enforce Preventive Range Constraint',
                action_type: invRes.recommendation.action_type || 'PREVENTIVE_DQ_RULE_PROPOSAL',
                description: invRes.recommendation.summary || 'Inject boundary rule',
                rule_expression: invRes.recommendation.details?.rule_expression || 'ALTER TABLE vehicle_telemetry ADD CONSTRAINT check_soc_range (battery_soc >= 0.0 AND battery_soc <= 100.0)',
                target_entity: incident.target_entity,
                risk_level: 'LOW',
                expected_impact: 'Prevents downstream analytics corruption; zero data loss.',
                execution_mode: mode,
                status: 'PENDING_AUTHORIZATION',
              },
            ]
          : incident.recommendations;

        setIncident({
          ...incident,
          hypotheses: updatedHypotheses,
          recommendations: updatedRecs,
        });

        if (updatedHypotheses.length > 0) {
          setActiveHypothesis(updatedHypotheses[0]);
        }
      }
    } catch (err) {
      console.error('Failed to trigger investigation mode:', err);
    }
  };

  const handleApproveControl = (_rationale?: string, hashSignature?: string) => {
    setIsApproved(true);
    if (hashSignature) setApprovalHash(hashSignature);
  };

  // Loading State UI
  if (loading && !incident) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-6 flex flex-col items-center justify-center font-sans">
        <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
          <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin" />
          <div>
            <div className="text-sm font-semibold text-slate-200">Loading Incident Workspace...</div>
            <div className="text-xs text-slate-400 mt-0.5">Fetching telemetry from /api/v1/incidents endpoint</div>
          </div>
        </div>
      </div>
    );
  }

  // Error State UI
  if (error && !incident) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-6 flex flex-col items-center justify-center font-sans">
        <div className="max-w-md w-full bg-slate-900 border border-rose-500/30 p-6 rounded-2xl shadow-xl text-center space-y-4">
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-full w-12 h-12 flex items-center justify-center mx-auto text-rose-400">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">Failed to Load Incident</h2>
            <p className="text-xs text-slate-400 mt-1">{error}</p>
          </div>
          <button
            onClick={() => loadIncidentData()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-lg transition flex items-center gap-2 mx-auto cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" /> Retry Fetching
          </button>
        </div>
      </div>
    );
  }

  // Empty State UI
  if (!incident) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-6 flex flex-col items-center justify-center font-sans">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl text-center space-y-4">
          <div className="p-3 bg-slate-800 rounded-full w-12 h-12 flex items-center justify-center mx-auto text-slate-400">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">No Incident Available</h2>
            <p className="text-xs text-slate-400 mt-1">No active incidents were returned from /api/v1/incidents endpoint.</p>
          </div>
          <button
            onClick={() => loadIncidentData()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-lg transition flex items-center gap-2 mx-auto cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" /> Refresh Incidents
          </button>
        </div>
      </div>
    );
  }

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
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 p-1.5 rounded-xl flex-wrap">
          <span className="text-xs font-semibold text-slate-400 px-2 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Incident:
          </span>
          {incidentsList.length === 0 ? (
            <span className="text-xs text-slate-500 font-mono px-2 py-1">
              {selectedIncidentId || incident.incident_id}
            </span>
          ) : (
            incidentsList.map((inc) => (
              <button
                key={inc.incident_id}
                onClick={() => handleSelectIncident(inc.incident_id)}
                className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-lg transition cursor-pointer ${
                  selectedIncidentId === inc.incident_id
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {inc.incident_id}
              </button>
            ))
          )}
          <button
            onClick={() => loadIncidentData()}
            title="Refresh Incidents"
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
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
            onSelectEvidenceForAssistant={(ev) => {
              setSelectedEvidence(ev);
              setIsAssistantCollapsed(false);
            }}
          />

          {/* 3. RCA Ranked Hypotheses */}
          <HypothesisPanel
            hypotheses={incident.hypotheses}
            activeHypothesisId={activeHypothesis?.hypothesis_id}
            onSelectHypothesis={(hyp) => setActiveHypothesis(hyp)}
            onAskAssistantAboutHypothesis={(hyp) => {
              setActiveHypothesis(hyp);
              setIsAssistantCollapsed(false);
            }}
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

