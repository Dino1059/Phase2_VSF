import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/datatrust/app-shell';
import { OverviewPage } from '@/components/datatrust/overview/overview-page';
import { RuleApprovalPage } from '@/components/datatrust/rules/rule-approval-page';
import { LineagePage } from '@/components/datatrust/lineage/lineage-page';
import { FindingDetail } from '@/components/datatrust/findings/finding-detail';
import { RunResultsPage } from '@/components/datatrust/results/run-results-page';
import { RunFindingsPage } from '@/components/datatrust/findings/run-findings-page';
import { useAgentStore } from '@/lib/agent-store';

export default function App() {
  useEffect(() => {
    useAgentStore.getState().syncWithBackend();
  }, []);

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/runs" element={<LineagePage />} />
        <Route path="/runs/:id" element={<LineagePage />} />
        <Route path="/runs/:runId/results" element={<RunResultsPage />} />
        <Route path="/runs/:runId/findings" element={<RunFindingsPage />} />
        <Route path="/runs/:runId/lineage" element={<LineagePage />} />
        <Route path="/lineage" element={<Navigate to="/runs" replace />} />
        <Route path="/rules" element={<RuleApprovalPage />} />
        <Route path="/results" element={<Navigate to="/runs" replace />} />
        <Route path="/findings" element={<RunFindingsPage />} />
        <Route path="/findings/:id" element={<FindingDetail />} />

        {/* Backwards compatibility aliases */}
        <Route path="/dashboard" element={<Navigate to="/runs" replace />} />
        <Route path="/data-quality" element={<Navigate to="/runs" replace />} />
        <Route path="/pipeline-runs" element={<Navigate to="/runs" replace />} />
        <Route path="/pipeline-runs/:id" element={<Navigate to="/runs" replace />} />
        <Route path="/evidence" element={<Navigate to="/runs" replace />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </AppShell>
  );
}
