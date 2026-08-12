import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ExecutiveDashboard } from './pages/ExecutiveDashboard';
import { AgentChatWorkspace } from './pages/AgentChatWorkspace';

export const App: React.FC = () => {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<ExecutiveDashboard />} />
        <Route path="/dashboard" element={<ExecutiveDashboard />} />
        <Route path="/workspace" element={<AgentChatWorkspace />} />
        <Route path="/chat/:id" element={<AgentChatWorkspace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
};

export default App;
