import React from 'react';

export const ProjectControlRoom: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      <header className="flex justify-between items-center border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Project Control Room</h1>
          <p className="text-xs text-slate-400 mt-1">
            Project: <span className="font-mono text-slate-300">proj-vingroup-pilot</span> • Provenance: <span className="font-mono text-emerald-400">SEMI_SYNTHETIC CAUSAL DIGITAL TWIN</span>
          </p>
        </div>
        <button
          onClick={() => window.location.hash = '#/incident'}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition"
        >
          View Active Incident Workspace →
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Monitored Entities</div>
          <div className="text-2xl font-bold text-slate-100 mt-1">30 VINs</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Charging Stations</div>
          <div className="text-2xl font-bold text-slate-100 mt-1">4 Stations</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Detection Cadence</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">&lt;1s / Daily</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Open Incidents</div>
          <div className="text-2xl font-bold text-rose-400 mt-1">1 Active</div>
        </div>
      </div>
    </div>
  );
};
