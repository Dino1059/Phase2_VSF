import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ExecutiveDashboard } from './pages/ExecutiveDashboard';
import { AgentChatWorkspace } from './pages/AgentChatWorkspace';
import { OperationsWorkspace } from './pages/OperationsWorkspace';
import { LandingPage } from './pages/LandingPage';
import { DataIngestionPage } from './pages/DataIngestionPage';

export const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/workspace?dataset_key=vingroup_pilot&story=happy" replace />} />
      <Route path="/landing" element={<LandingPage />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<ExecutiveDashboard />} />
        <Route path="/dashboard/ingestion" element={<DataIngestionPage />} />
        <Route path="/workspace" element={<AgentChatWorkspace />} />
        <Route path="/chat/:id" element={<AgentChatWorkspace />} />
        <Route path="/operations/:view" element={<OperationsWorkspace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};


export default App;
