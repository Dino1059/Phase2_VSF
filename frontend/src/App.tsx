import { useEffect } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/datatrust/app-shell';
import { OverviewPage } from '@/components/datatrust/overview/overview-page';
import { RuleApprovalPage } from '@/components/datatrust/rules/rule-approval-page';
import { LineagePage } from '@/components/datatrust/lineage/lineage-page';
import { FindingDetail } from '@/components/datatrust/findings/finding-detail';
import { RunResultsPage } from '@/components/datatrust/results/run-results-page';
import { RunFindingsPage } from '@/components/datatrust/findings/run-findings-page';
import { LoginPage } from '@/src/components/auth/LoginPage';
import { AuthGuard } from '@/src/components/auth/AuthGuard';
import { SodWorkspace } from '@/src/components/sod/SodWorkspace';
import { useAgentStore } from '@/lib/agent-store';
import { useAuthStore } from '@/src/stores/authStore';

function RootRedirector() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const systemAccess = useAuthStore((s) => s.systemAccess);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (systemAccess === 'sod_only') {
    return <Navigate to="/sod" replace />;
  }

  return <Navigate to="/overview" replace />;
}

function SodRouteDispatcher() {
  const systemAccess = useAuthStore((s) => s.systemAccess);

  if (systemAccess === 'both') {
    return (
      <AppShell>
        <SodWorkspace mode="embedded" />
      </AppShell>
    );
  }

  return <SodWorkspace mode="standalone" />;
}

function DataTrustShellLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  useEffect(() => {
    useAgentStore.getState().syncWithBackend();
  }, []);

  return (
    <Routes>
      {/* 1. PUBLIC ROUTE: Unified Login Portal */}
      <Route path="/login" element={<LoginPage />} />

      {/* 2. ROOT SMART REDIRECTOR */}
      <Route path="/" element={<RootRedirector />} />

      {/* 3. SOD FLOW WORKSPACE (Protected by AuthGuard for sod access) */}
      <Route
        path="/sod"
        element={
          <AuthGuard requiredAccess="sod">
            <SodRouteDispatcher />
          </AuthGuard>
        }
      />
      <Route
        path="/sod/*"
        element={
          <AuthGuard requiredAccess="sod">
            <SodRouteDispatcher />
          </AuthGuard>
        }
      />

      {/* 4. DATATRUST OS ROUTES (Protected by AuthGuard for datatrust access) */}
      <Route
        element={
          <AuthGuard requiredAccess="datatrust">
            <DataTrustShellLayout />
          </AuthGuard>
        }
      >
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
      </Route>

      {/* Fallback */}
      <Route path="*" element={<RootRedirector />} />
    </Routes>
  );
}
