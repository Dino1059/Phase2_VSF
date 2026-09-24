import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AppShell } from '@/components/datatrust/app-shell';
import { OverviewPage } from '@/components/datatrust/overview/overview-page';
import { RunsPage } from '@/components/datatrust/runs/runs-page';
import { RuleApprovalPage } from '@/components/datatrust/rules/rule-approval-page';
import { ResultsPage } from '@/components/datatrust/results/results-page';
import { FindingDetail } from '@/components/datatrust/findings/finding-detail';
import { PipelineRunDetail } from '@/components/datatrust/pipeline/pipeline-run-detail';
import { findingsDataSource } from '@/lib/data/local-findings-data';
import { pipelineDataSource } from '@/lib/data/local-pipeline-data';

function Load<T>({ load, children }: { load: () => Promise<T>; children: (data: T) => ReactNode }) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    load()
      .then((value) => {
        if (active) setData(value);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      active = false;
    };
  }, [load]);

  if (error)
    return <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">Lỗi nạp dữ liệu: {error}</div>;
  if (!data)
    return (
      <div className="grid min-h-[50vh] place-items-center text-sm text-slate-400">
        <div className="flex items-center gap-2">
          <div className="size-4 animate-spin rounded-full border-2 border-[#008b74] border-t-transparent" />
          <span>Đang nạp dữ liệu DataTrust OS…</span>
        </div>
      </div>
    );
  return children(data);
}

function Finding() {
  const { id = '' } = useParams();
  const load = useCallback(() => findingsDataSource.getFinding(id), [id]);
  return <Load load={load}>{(data) => (data ? <FindingDetail finding={data} /> : <Navigate to="/results?tab=findings" replace />)}</Load>;
}

function Run() {
  const { id = '' } = useParams();
  const load = useCallback(() => pipelineDataSource.getRun(id), [id]);
  return <Load load={load}>{(data) => (data ? <PipelineRunDetail run={data} /> : <Navigate to="/runs" replace />)}</Load>;
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:id" element={<Run />} />
        <Route path="/rules" element={<RuleApprovalPage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/findings/:id" element={<Finding />} />

        {/* Backwards compatibility aliases */}
        <Route path="/dashboard" element={<Navigate to="/results?tab=dashboard" replace />} />
        <Route path="/findings" element={<Navigate to="/results?tab=findings" replace />} />
        <Route path="/data-quality" element={<Navigate to="/results?tab=dashboard" replace />} />
        <Route path="/pipeline-runs" element={<Navigate to="/runs" replace />} />
        <Route path="/pipeline-runs/:id" element={<Run />} />
        <Route path="/evidence" element={<Navigate to="/results?tab=evidence" replace />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </AppShell>
  );
}

