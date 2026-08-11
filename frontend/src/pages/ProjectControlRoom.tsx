import React, { useEffect, useState } from 'react';
import {
  projectsApi,
  incidentsApi,
  signalsApi,
  summaryApi,
  ProjectInfo,
  IncidentInfo,
  SignalInfo,
  SummaryInfo,
} from '../services/api';
import {
  ShieldAlert,
  Activity,
  Zap,
  Radio,
  Layers,
  ArrowRight,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Database,
  AlertTriangle,
} from 'lucide-react';

export const ProjectControlRoom: React.FC = () => {
  const [project, setProject] = useState<ProjectInfo | null>(null);
  const [summary, setSummary] = useState<SummaryInfo | null>(null);
  const [incidents, setIncidents] = useState<IncidentInfo[]>([]);
  const [signals, setSignals] = useState<SignalInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLayer, setSelectedLayer] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectsData, incidentsData, signalsData, summaryData] = await Promise.all([
        projectsApi.list(),
        incidentsApi.list('proj-vingroup-pilot'),
        signalsApi.list('proj-vingroup-pilot'),
        summaryApi.get().catch(() => null),
      ]);

      if (projectsData && projectsData.length > 0) {
        setProject(projectsData[0]);
      } else {
        setProject(null);
      }

      setSummary(summaryData);
      setIncidents(incidentsData || []);
      setSignals(signalsData || []);
    } catch (err: any) {
      console.error('Error loading Control Room data:', err);
      setError(err.message || 'Failed to fetch telemetry data from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openIncidents = incidents.filter(
    (i) => i.status !== 'CLOSED' && i.status !== 'RESOLVED'
  );

  const filteredSignals = selectedLayer
    ? signals.filter((s) => s.layer === selectedLayer)
    : signals;

  const layerCounts = signals.reduce(
    (acc, sig) => {
      const l = sig.layer || 'L1';
      acc[l] = (acc[l] || 0) + 1;
      return acc;
    },
    { L1: 0, L2: 0, L3: 0, L4: 0 } as Record<string, number>
  );

  const criticalSignalsCount = signals.filter(
    (s) => (s.severity || '').toUpperCase() === 'CRITICAL'
  ).length;

  const activeProvenance = (project?.provenance || summary?.provenance || 'SEMI_SYNTHETIC').toUpperCase();

  const getProvenanceBadge = (provenance: string) => {
    switch (provenance) {
      case 'REAL_OPERATIONAL':
        return {
          colorClass: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
          dotClass: 'bg-emerald-400',
          label: 'REAL_OPERATIONAL',
        };
      case 'PUBLIC_PROXY':
        return {
          colorClass: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
          dotClass: 'bg-blue-400',
          label: 'PUBLIC_PROXY',
        };
      case 'SEMI_SYNTHETIC':
        return {
          colorClass: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
          dotClass: 'bg-amber-400',
          label: 'SEMI_SYNTHETIC',
        };
      case 'SYNTHETIC':
      default:
        return {
          colorClass: 'bg-purple-500/10 border-purple-500/30 text-purple-400',
          dotClass: 'bg-purple-400',
          label: 'SYNTHETIC',
        };
    }
  };

  const provBadge = getProvenanceBadge(activeProvenance);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Top Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-4 gap-4">
        <div>
          <div className="flex items-center space-x-3 flex-wrap gap-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              {project ? project.name : 'Project Control Room'}
            </h1>
            <span className="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-400 text-xs font-mono font-semibold rounded-full border border-emerald-500/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {project?.status || 'ACTIVE'}
            </span>
          </div>

          <div className="flex items-center space-x-3 mt-2 flex-wrap gap-2 text-xs">
            <span className="text-slate-400">
              Project ID: <span className="font-mono text-slate-300">{project?.project_id || 'proj-vingroup-pilot'}</span>
            </span>
            <span className="text-slate-600">•</span>
            {/* PROVENANCE NOTICE Badge */}
            <span className={`px-2.5 py-0.5 rounded font-mono font-bold border flex items-center space-x-1.5 ${provBadge.colorClass}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${provBadge.dotClass} animate-pulse`} />
              <span>PROVENANCE NOTICE: {provBadge.label}</span>
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-medium rounded-lg flex items-center space-x-1.5 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => (window.location.hash = '#/incident')}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center space-x-2 transition shadow-lg shadow-indigo-600/20"
          >
            <span>View Active Incident Workspace</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-xs text-red-400 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Overview Grid connected directly to /api/v1 endpoints */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl backdrop-blur flex justify-between items-center">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Monitored Fleet Entities
            </div>
            <div className="text-2xl font-extrabold text-slate-100 mt-1">
              {loading ? '...' : `${project?.entities_count ?? 0} VINs`}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">/api/v1/projects</div>
          </div>
          <div className="p-2.5 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl backdrop-blur flex justify-between items-center">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Charging Infrastructure
            </div>
            <div className="text-2xl font-extrabold text-slate-100 mt-1">
              {loading ? '...' : `${project?.stations_count ?? 0} Stations`}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Fast DC Hubs</div>
          </div>
          <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
            <Zap className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl backdrop-blur flex justify-between items-center">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Detected Signals
            </div>
            <div className="text-2xl font-extrabold text-cyan-400 mt-1">
              {loading ? '...' : `${signals.length} Signals`}
            </div>
            <div className="text-[10px] text-cyan-500/80 mt-0.5">
              {criticalSignalsCount} Critical Severity (/api/v1/signals)
            </div>
          </div>
          <div className="p-2.5 bg-cyan-500/10 border border-cyan-500/20 rounded-lg text-cyan-400">
            <Radio className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl backdrop-blur flex justify-between items-center">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Open Incidents
            </div>
            <div className="text-2xl font-extrabold text-rose-400 mt-1">
              {loading ? '...' : `${openIncidents.length} Active`}
            </div>
            <div className="text-[10px] text-rose-500/80 mt-0.5">
              {incidents.length} Total Registered (/api/v1/incidents)
            </div>
          </div>
          <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Control Panel: Anomaly Trends & Signal Layers + Active Incidents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signals & Anomaly Layer Breakdown (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Anomaly Trend Layer Buttons */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 backdrop-blur space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 flex-wrap gap-2">
              <div className="flex items-center space-x-2">
                <Layers className="w-5 h-5 text-cyan-400" />
                <h2 className="font-semibold text-slate-100">
                  Telemetry Anomaly Layers (/api/v1/signals)
                </h2>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <button
                  onClick={() => setSelectedLayer(null)}
                  className={`px-2.5 py-1 rounded border transition ${
                    selectedLayer === null
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  All ({signals.length})
                </button>
                {['L1', 'L2', 'L3', 'L4'].map((l) => (
                  <button
                    key={l}
                    onClick={() => setSelectedLayer(selectedLayer === l ? null : l)}
                    className={`px-2.5 py-1 rounded border font-mono transition ${
                      selectedLayer === l
                        ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                        : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    {l} ({layerCounts[l] || 0})
                  </button>
                ))}
              </div>
            </div>

            {/* Signal List or Clean Empty State */}
            <div className="space-y-3">
              {filteredSignals.length === 0 ? (
                <div className="text-center py-10 bg-slate-950/40 rounded-lg border border-slate-800/60 space-y-2">
                  <AlertTriangle className="w-8 h-8 text-slate-600 mx-auto" />
                  <h4 className="text-sm font-semibold text-slate-300">No monitoring results yet</h4>
                  <p className="text-xs text-slate-500">
                    No anomaly signals detected for the selected filter from /api/v1/signals.
                  </p>
                </div>
              ) : (
                filteredSignals.map((sig) => (
                  <div
                    key={sig.signal_id}
                    className="bg-slate-950/70 border border-slate-800 rounded-lg p-3.5 flex items-center justify-between hover:border-slate-700 transition"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="px-2 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded font-mono text-xs font-bold">
                        {sig.layer}
                      </span>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-semibold text-slate-200">
                            {sig.signal_type}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                            {sig.metric_or_relationship}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-1 flex items-center space-x-3">
                          <span>Detector: {sig.detector}</span>
                          <span>Entities: {sig.entity_ids?.join(', ') || 'N/A'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                          (sig.severity || '').toUpperCase() === 'CRITICAL'
                            ? 'bg-red-500/10 text-red-400 border-red-500/30'
                            : (sig.severity || '').toUpperCase() === 'HIGH'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                            : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                        }`}
                      >
                        {sig.severity} (Score: {sig.score})
                      </span>
                      <div className="text-[10px] text-slate-500 font-mono mt-1">
                        ID: {sig.signal_id}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Connected Datasets */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 backdrop-blur space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2">
                <Database className="w-4 h-4 text-emerald-400" />
                <h3 className="font-semibold text-sm text-slate-100">
                  Bound Project Datasets (/api/v1/projects)
                </h3>
              </div>
              <span className="text-xs text-slate-500 font-mono">
                {project?.datasets?.length || 0} Registered Sources
              </span>
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              {(project?.datasets || []).map((ds) => (
                <span
                  key={ds}
                  className="px-3 py-1 bg-slate-950 text-slate-300 border border-slate-800 rounded-lg text-xs font-mono flex items-center space-x-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{ds}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Active Incidents & Reliability Status (1 col) */}
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 backdrop-blur space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-5 h-5 text-rose-400" />
                <h2 className="font-semibold text-slate-100">
                  Live Active Incidents (/api/v1/incidents)
                </h2>
              </div>
            </div>

            <div className="space-y-3">
              {incidents.length === 0 ? (
                <div className="text-center py-10 bg-slate-950/40 rounded-lg border border-slate-800/60 space-y-2">
                  <ShieldAlert className="w-8 h-8 text-slate-600 mx-auto" />
                  <h4 className="text-sm font-semibold text-slate-300">No monitoring results yet</h4>
                  <p className="text-xs text-slate-500">
                    No open incidents listed for this project from /api/v1/incidents.
                  </p>
                </div>
              ) : (
                incidents.map((inc) => (
                  <div
                    key={inc.incident_id}
                    className="bg-slate-950/80 border border-slate-800 rounded-lg p-3.5 space-y-2 hover:border-slate-700 transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-indigo-400 font-bold">
                        {inc.incident_id}
                      </span>
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                          inc.status === 'OPEN'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        }`}
                      >
                        {inc.status}
                      </span>
                    </div>

                    <p className="text-xs text-slate-200 font-medium">{inc.admission_reason}</p>

                    <div className="text-[11px] text-slate-400 space-y-1 pt-1 border-t border-slate-800/60">
                      <div>
                        Target Entities:{' '}
                        <span className="font-mono text-slate-300">
                          {inc.entity_ids?.join(', ') || 'N/A'}
                        </span>
                      </div>
                      <div>
                        Linked Signals:{' '}
                        <span className="font-mono text-cyan-400">
                          {inc.signal_ids?.join(', ') || 'None'}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => (window.location.hash = '#/incident')}
                      className="w-full mt-2 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded text-xs font-medium transition flex items-center justify-center space-x-1"
                    >
                      <span>Investigate in Workspace</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
