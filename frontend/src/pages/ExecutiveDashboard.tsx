import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Atom,
  Search,
  ArrowLeft,
  Activity,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Microchip,
  Database,
  UserShield,
  CheckCircle2,
  Gavel,
  Fingerprint,
  UserCheck,
  Bot,
  BarChart3,
  Flame,
  Layers,
  Zap,
} from 'lucide-react';
import { useDashboardStore } from '../stores/dashboardStore';

export const ExecutiveDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { metrics, insights, activityFeed, signals, fetchDashboardData, loading } = useDashboardStore();

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Compute live signal layer counts
  const layerCounts = signals.reduce(
    (acc, sig) => {
      const l = sig.layer || 'L1';
      acc[l] = (acc[l] || 0) + 1;
      return acc;
    },
    { L1: 0, L2: 0, L3: 0, L4: 0 } as Record<string, number>
  );

  // Compute live signal severity counts
  const severityCounts = signals.reduce(
    (acc, sig) => {
      const s = (sig.severity || 'MEDIUM').toUpperCase();
      acc[s] = (acc[s] || 0) + 1;
      return acc;
    },
    { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 } as Record<string, number>
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 space-y-6 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header HUD */}
      <header className="flex items-center justify-between bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl px-6 py-4 shadow-lg relative z-10">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => {
              if (window.location.hash) {
                window.location.hash = '#/control-room';
              } else {
                navigate('/');
              }
            }}
            className="flex items-center space-x-2 text-slate-400 hover:text-cyan-400 transition-colors border border-slate-700 hover:border-cyan-500/50 rounded-lg px-3 py-1.5 text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Control Room</span>
          </button>
          <div className="h-6 w-px bg-slate-800" />
          <div className="flex items-center space-x-2">
            <Atom className="w-6 h-6 text-cyan-400 animate-spin-slow" />
            <span className="font-bold text-lg tracking-wider text-slate-100">
              DATATRUST OS <span className="text-cyan-400">EXECUTIVE DASHBOARD</span>
            </span>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search signals, incidents, audit logs..."
            className="w-full bg-slate-950/60 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 relative z-10">
        {/* KPI Cards Row */}
        <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-4 gap-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Total Signals & Anomalies</p>
              <h3 className="text-3xl font-extrabold text-red-400 mt-1">{loading ? '...' : metrics.totalAnomalies}</h3>
            </div>
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Anomaly Rate</p>
              <h3 className="text-3xl font-extrabold text-cyan-400 mt-1">{loading ? '...' : metrics.anomalyRate}</h3>
            </div>
            <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-lg">
              <Activity className="w-6 h-6 text-cyan-400" />
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Active Incidents</p>
              <h3 className="text-3xl font-extrabold text-amber-400 mt-1">{loading ? '...' : metrics.activeIncidentsCount}</h3>
            </div>
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <Zap className="w-6 h-6 text-amber-400" />
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Avg Detection Cadence</p>
              <h3 className="text-3xl font-extrabold text-emerald-400 mt-1">{loading ? '...' : metrics.avgResolutionTime}</h3>
            </div>
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
              <Clock className="w-6 h-6 text-emerald-400" />
            </div>
          </div>
        </div>

        {/* Anomaly Trends & Signal Layer Breakdown */}
        <div className="lg:col-span-3 bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Layers className="w-5 h-5 text-cyan-400" />
              <h2 className="font-semibold text-lg text-slate-100">Live Anomaly Trends & Signal Layer Distribution</h2>
            </div>
            <span className="text-xs text-slate-400 font-mono">Backend API: /api/v1/signals</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-lg text-center">
              <span className="text-xs font-mono text-cyan-400 uppercase">L1 Schema & Range</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">{layerCounts.L1 || 0}</div>
              <div className="text-[10px] text-slate-500 mt-1">Constraint Violations</div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-lg text-center">
              <span className="text-xs font-mono text-amber-400 uppercase">L2 Contextual Drift</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">{layerCounts.L2 || 0}</div>
              <div className="text-[10px] text-slate-500 mt-1">Statistical Outliers</div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-lg text-center">
              <span className="text-xs font-mono text-purple-400 uppercase">L3 Multi-Entity</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">{layerCounts.L3 || 0}</div>
              <div className="text-[10px] text-slate-500 mt-1">Cross-System Inconsistency</div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-lg text-center">
              <span className="text-xs font-mono text-rose-400 uppercase">L4 Causal Graph</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">{layerCounts.L4 || 0}</div>
              <div className="text-[10px] text-slate-500 mt-1">Root Cause Cascades</div>
            </div>
          </div>

          <div className="flex items-center space-x-6 text-xs text-slate-400 pt-2 border-t border-slate-800/60">
            <span>Severity Breakdown:</span>
            <span className="text-rose-400 font-medium">Critical: {severityCounts.CRITICAL || 0}</span>
            <span className="text-amber-400 font-medium">High: {severityCounts.HIGH || 0}</span>
            <span className="text-yellow-400 font-medium">Medium: {severityCounts.MEDIUM || 0}</span>
            <span className="text-slate-400 font-medium">Low: {severityCounts.LOW || 0}</span>
          </div>
        </div>

        {/* AI Diagnosis & Root Cause Section */}
        <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Microchip className="w-5 h-5 text-cyan-400" />
              <h2 className="font-semibold text-lg text-slate-100">Live Active Incidents & Root Cause Analysis</h2>
            </div>
            <span className="flex items-center space-x-1.5 text-xs bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 rounded-full px-3 py-1 font-medium">
              <span>{insights.length} Active Incident(s)</span>
            </span>
          </div>

          <div className="space-y-4 flex-1 overflow-y-auto max-h-96">
            {insights.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No active incidents reported from /api/v1/incidents endpoint.
              </div>
            ) : (
              insights.map((insight) => (
                <div key={insight.id} className="bg-slate-950/50 border border-slate-800/80 rounded-lg p-4 space-y-2 hover:border-slate-700 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-cyan-300 text-sm flex items-center space-x-2">
                      <Flame className="w-4 h-4 text-purple-400" />
                      <span>{insight.title}</span>
                    </span>
                    <span className="text-xs font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                      {insight.confidence}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    <strong className="text-slate-400">Diagnosis Detail:</strong> {insight.rootCause}
                  </p>
                  <p className="text-xs text-slate-300">
                    <strong className="text-cyan-400">Recommended Action:</strong> {insight.recommendedAction}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* AI & Audit Activity Feed */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <BarChart3 className="w-5 h-5 text-purple-400" />
              <h2 className="font-semibold text-lg text-slate-100">Live Audit & Activity</h2>
            </div>
            <span className="flex items-center space-x-1.5 text-xs text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>/api/v1/audit</span>
            </span>
          </div>

          <div className="space-y-3 flex-1 overflow-y-auto max-h-96">
            {activityFeed.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No recent activity logged in audit trail.
              </div>
            ) : (
              activityFeed.map((item) => (
                <div key={item.id} className="flex items-center space-x-3 p-2.5 rounded-lg hover:bg-slate-800/40 transition-colors border border-slate-800/40">
                  <div className="p-2 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">
                    {item.icon === 'user-check' && <UserCheck className="w-4 h-4" />}
                    {item.icon === 'microchip' && <Microchip className="w-4 h-4" />}
                    {item.icon === 'exclamation-triangle' && <AlertTriangle className="w-4 h-4" />}
                    {item.icon === 'robot' && <Bot className="w-4 h-4" />}
                    {item.icon === 'chart-bar' && <BarChart3 className="w-4 h-4" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-200 truncate">{item.title}</p>
                    <p className="text-[10px] text-slate-500 font-mono">{item.time}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Governance Summary Banner */}
        <div className="lg:col-span-3 bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <h2 className="font-semibold text-lg text-slate-100">Governance Execution Summary</h2>
            </div>
            <span className="flex items-center space-x-1 text-xs text-purple-400 font-mono bg-purple-500/10 px-3 py-1 rounded-full border border-purple-500/20">
              <Fingerprint className="w-3.5 h-3.5" />
              <span>Immutable SHA-256 Ledger</span>
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 text-center">
              <Database className="w-5 h-5 text-emerald-400 mx-auto mb-1" />
              <div className="text-xl font-bold text-slate-100">{metrics.cleanRecords.toLocaleString()}</div>
              <div className="text-xs text-slate-400 mt-1">Clean Records</div>
            </div>

            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 text-center">
              <UserShield className="w-5 h-5 text-red-400 mx-auto mb-1" />
              <div className="text-xl font-bold text-slate-100">{metrics.quarantinedRecords}</div>
              <div className="text-xs text-slate-400 mt-1">Quarantined Records</div>
            </div>

            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 text-center">
              <CheckCircle2 className="w-5 h-5 text-cyan-400 mx-auto mb-1" />
              <div className="text-xl font-bold text-slate-100">{metrics.passValidationRate}</div>
              <div className="text-xs text-slate-400 mt-1">Passed Validation</div>
            </div>

            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 text-center">
              <Gavel className="w-5 h-5 text-purple-400 mx-auto mb-1" />
              <div className="text-xl font-bold text-slate-100">{metrics.rulesExecuted}</div>
              <div className="text-xs text-slate-400 mt-1">Rules Executed</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/80 pt-3">
            <span>Latest Immutable Ledger Hash:</span>
            <code className="font-mono text-cyan-400 bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-[11px] truncate max-w-lg">
              {metrics.latestLedgerHash}
            </code>
          </div>
        </div>
      </div>
    </div>
  );
};
