import React, { useState, useEffect } from 'react';
import { ProjectControlRoom } from './pages/ProjectControlRoom';
import { IncidentWorkspace } from './pages/IncidentWorkspace';
import { ExecutiveDashboard } from './pages/ExecutiveDashboard';

export const App: React.FC = () => {
  const [route, setRoute] = useState(window.location.hash || '#/control-room');

  useEffect(() => {
    const handleHashChange = () => setRoute(window.location.hash || '#/control-room');
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  return (
    <div>
      <nav className="bg-slate-900 border-b border-slate-800 px-6 py-3 flex gap-4 text-xs font-semibold">
        <a href="#/control-room" className={`px-3 py-1.5 rounded-lg ${route === '#/control-room' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
          Project Control Room
        </a>
        <a href="#/incident" className={`px-3 py-1.5 rounded-lg ${route === '#/incident' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
          Incident Workspace
        </a>
        <a href="#/dashboard" className={`px-3 py-1.5 rounded-lg ${route === '#/dashboard' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
          Executive Dashboard
        </a>
      </nav>

      {route === '#/incident' && <IncidentWorkspace />}
      {route === '#/dashboard' && <ExecutiveDashboard />}
      {(route === '#/control-room' || (route !== '#/incident' && route !== '#/dashboard')) && <ProjectControlRoom />}
    </div>
  );
};

export default App;
