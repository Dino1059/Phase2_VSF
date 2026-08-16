import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import {
  approvalsApi,
  auditApi,
  authorizationsApi,
  executionsApi,
  incidentsApi,
  signalsApi,
  snapshotsApi,
  summaryApi,
  tracesApi,
} from '../services/api';

type ViewKey = 'alerts' | 'incidents' | 'signals' | 'traces' | 'governance' | 'executions' | 'snapshots';
type Row = Record<string, any>;

const TITLES: Record<ViewKey, string> = {
  alerts: 'Alert Center', incidents: 'Incidents', signals: 'Signal Explorer', traces: 'Agent Traces',
  governance: 'Governance & Admin', executions: 'Execution History', snapshots: 'Data Snapshots',
};

function value(row: Row, ...keys: string[]) {
  const found = keys.find((key) => row[key] !== undefined && row[key] !== null && row[key] !== '');
  return found ? String(row[found]) : '—';
}

function Table({ columns, rows }: { columns: string[]; rows: Row[] }) {
  return rows.length ? (
    <div className="data-table-wrapper" style={{ maxHeight: 'none' }}>
      <table className="data-table"><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={String(row.id ?? row.incident_id ?? row.signal_id ?? row.session_id ?? index)}>{columns.map((column) => <td key={column}>{value(row, column.toLowerCase().replaceAll(' ', '_'), column)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  ) : <div style={{ padding: '28px', textAlign: 'center', color: 'var(--text-muted)' }}>Chưa có dữ liệu từ backend.</div>;
}

export function OperationsWorkspace() {
  const { view } = useParams<{ view: string }>();
  const currentView = (Object.hasOwn(TITLES, view ?? '') ? view : 'alerts') as ViewKey;
  const [data, setData] = useState<Row[]>([]);
  const [summary, setSummary] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      if (currentView === 'alerts') {
        const [summaryResult, incidents, signals] = await Promise.all([summaryApi.get(), incidentsApi.list(), signalsApi.list()]);
        setSummary(summaryResult); setData([...incidents, ...signals.map((signal) => ({ ...signal, alert_type: 'signal' }))]);
      } else if (currentView === 'incidents') setData(await incidentsApi.list());
      else if (currentView === 'signals') setData(await signalsApi.list());
      else if (currentView === 'traces') setData((await tracesApi.list()).sessions);
      else if (currentView === 'governance') {
        const [approvals, authorizations, audit] = await Promise.all([approvalsApi.list(), authorizationsApi.list(), auditApi.list(50)]);
        setData([...approvals.map((row) => ({ ...row, record_type: 'approval' })), ...authorizations.map((row) => ({ ...row, record_type: 'authorization' })), ...audit.map((row) => ({ ...row, record_type: 'audit' }))]);
      } else if (currentView === 'executions') setData(await executionsApi.list());
      else setData((await snapshotsApi.list()).snapshots);
    } catch (loadError) { setError(loadError instanceof Error ? loadError.message : 'Không thể tải dữ liệu.'); setData([]); }
    finally { setLoading(false); }
  }, [currentView]);

  useEffect(() => { void load(); }, [load]);

  const columns = useMemo(() => {
    const map: Record<ViewKey, string[]> = {
      alerts: ['incident_id', 'signal_id', 'severity', 'status', 'signal_type', 'timestamp'],
      incidents: ['incident_id', 'severity', 'status', 'admission_reason', 'created_at'],
      signals: ['signal_id', 'layer', 'signal_type', 'severity', 'detector', 'score'],
      traces: ['session_id', 'agent_type', 'steps', 'total_tokens', 'started'],
      governance: ['record_type', 'id', 'status', 'actor', 'action', 'timestamp'],
      executions: ['event_type', 'actor', 'timestamp', 'details'],
      snapshots: ['id', 'source_file', 'row_count', 'column_count', 'sha256_hash', 'ingested_at'],
    };
    return map[currentView];
  }, [currentView]);

  const alertCount = data.filter((row) => row.incident_id || row.alert_type === 'signal').length;

  return <section className="dash-main" style={{ minHeight: '100%', overflowY: 'auto' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
      <div><div className="menu-label" style={{ padding: 0 }}>Operations</div><h1 style={{ margin: '6px 0 0', color: 'var(--text-main)' }}>{TITLES[currentView]}</h1></div>
      <button className="hud-btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} />Refresh</button>
    </div>
    {currentView === 'alerts' && summary && <div className="kpi-grid"><div className="kpi-card"><div className="kpi-label">Active alerts</div><div className="kpi-value">{alertCount}</div></div><div className="kpi-card"><div className="kpi-label">System status</div><div className="kpi-value" style={{ fontSize: '20px' }}>{value(summary, 'system_status')}</div></div><div className="kpi-card"><div className="kpi-label">Quarantined records</div><div className="kpi-value">{value(summary, 'quarantined_records')}</div></div></div>}
    {error && <div className="panel-card" style={{ color: 'var(--alert-magenta)' }}>{error}</div>}
    {loading ? <div className="panel-card">Đang tải dữ liệu…</div> : <div className="panel-card"><Table columns={columns} rows={data} /></div>}
  </section>;
}
