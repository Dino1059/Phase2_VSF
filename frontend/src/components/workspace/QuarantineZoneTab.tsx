import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert, RefreshCw, AlertTriangle, ChevronDown, ChevronRight, Eye, Database, CheckCircle2, XCircle } from 'lucide-react';
import { quarantineApi, QuarantineGroup } from '../../services/api';

interface Props {
  initialDatasetKey?: string;
}

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: '#f43f5e',
  HIGH: '#f59e0b',
  MEDIUM: '#eab308',
  LOW: '#06b6d4',
};

export const QuarantineZoneTab: React.FC<Props> = ({ initialDatasetKey = 'all' }) => {
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const [groups, setGroups] = useState<QuarantineGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [totalQuarantined, setTotalQuarantined] = useState(0);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selectedDataset, setSelectedDataset] = useState(initialDatasetKey);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ds = selectedDataset === 'all' ? undefined : selectedDataset;
      const st = selectedStatus === 'all' ? undefined : selectedStatus;
      const res = await quarantineApi.groups(ds, st);
      const fetched = res.groups || [];
      setGroups(fetched);
      setTotalQuarantined(res.total_quarantined || 0);
      if (fetched.length > 0 && Object.keys(expanded).length === 0) {
        setExpanded({ [fetched[0].group_id]: true });
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [selectedDataset, selectedStatus]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (id: string) => setExpanded((p) => ({ ...p, [id]: !p[id] }));

  const handleRemediate = async (g: QuarantineGroup) => {
    const key = `rem_${g.group_id}`;
    setActionLoading((prev) => ({ ...prev, [key]: true }));
    setError(null);
    setActionSuccess(null);
    try {
      const res = await quarantineApi.remediate({
        rule_id: g.rule_id,
        source_table: g.source_table,
        sql_query: g.ai_suggested_sql,
        group_id: g.group_id,
      });
      setActionSuccess(res.message || (isVi ? 'Đã thực thi SQL sửa lỗi và chuyển bản ghi sang Clean DB!' : 'Remediation SQL executed successfully!'));
      await load();
    } catch (e: any) {
      setError(e?.message || 'Remediation failed');
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  const handleReject = async (g: QuarantineGroup) => {
    const key = `rej_${g.group_id}`;
    setActionLoading((prev) => ({ ...prev, [key]: true }));
    setError(null);
    setActionSuccess(null);
    try {
      const res = await quarantineApi.reject({
        rule_id: g.rule_id,
        source_table: g.source_table,
        group_id: g.group_id,
        reason: 'Operator rejected automated SQL fix; retaining in isolation for manual inspection',
      });
      setActionSuccess(res.message || (isVi ? 'Đã từ chối gợi ý SQL. Nhóm vi phạm giữ ở trạng thái ĐÃ TỪ CHỐI.' : 'Remediation SQL rejected. Group marked as REJECTED_HELD.'));
      await load();
    } catch (e: any) {
      setError(e?.message || 'Reject failed');
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div style={{ padding: '16px', background: 'var(--bg-card)', borderRadius: '8px', minHeight: '500px' }}>
      {/* HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '18px', color: 'var(--text-main)' }}>
            <ShieldAlert size={18} style={{ verticalAlign: 'middle', marginRight: 8, color: '#f43f5e' }} />
            {isVi ? 'Vùng Cách Ly' : 'Quarantine Zone'}
          </h2>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {isVi ? 'Tổng bản ghi cách ly' : 'Total quarantined records'}: <strong style={{ color: 'var(--text-main)' }}>{totalQuarantined.toLocaleString()}</strong>
            {' · '}
            {isVi ? 'Cụm vi phạm' : 'Active clusters'}: <strong style={{ color: 'var(--text-main)' }}>{groups.length}</strong>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{
              padding: '6px 10px',
              background: 'var(--bg-deep)',
              color: 'var(--text-main)',
              border: '1px solid var(--glass-border)',
              borderRadius: '6px',
              fontSize: '12px',
            }}
          >
            <option value="all">{isVi ? 'Tất cả trạng thái' : 'All Statuses'}</option>
            <option value="QUARANTINED">{isVi ? 'Chờ xử lý (QUARANTINED)' : 'Pending (QUARANTINED)'}</option>
            <option value="REJECTED_HELD">{isVi ? 'Đã từ chối - Đang giữ (REJECTED_HELD)' : 'Rejected (REJECTED_HELD)'}</option>
          </select>
          <select
            value={selectedDataset}
            onChange={(e) => setSelectedDataset(e.target.value)}
            style={{
              padding: '6px 10px',
              background: 'var(--bg-deep)',
              color: 'var(--text-main)',
              border: '1px solid var(--glass-border)',
              borderRadius: '6px',
              fontSize: '12px',
            }}
          >
            <option value="all">All Tables</option>
            <option value="vinfast_ev_telemetry">VinFast EV Telemetry</option>
            <option value="vinfast_bms">VinFast BMS Telemetry</option>
            <option value="vgreen_charging_stations">VGreen Charging Stations</option>
            <option value="vgreen_telemetry">VGreen Telemetry</option>
            <option value="xanh_sm_trips">Xanh SM Trips</option>
            <option value="raw_taxi_trips">Raw Taxi Telemetry</option>
          </select>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            style={{
              padding: '6px 10px',
              background: 'transparent',
              border: '1px solid var(--glass-border)',
              borderRadius: '6px',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '12px',
            }}
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* SUCCESS / ERROR NOTIFICATIONS */}
      {actionSuccess && (
        <div style={{ padding: '12px', marginBottom: '12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid #10b981', borderRadius: '6px', color: '#10b981', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={16} />
          {actionSuccess}
        </div>
      )}
      {error && (
        <div style={{ padding: '12px', marginBottom: '12px', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid #f43f5e', borderRadius: '6px', color: '#f43f5e', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* LOADING */}
      {loading && (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <RefreshCw size={24} className="spinning" style={{ marginBottom: '12px' }} />
          <div>{isVi ? 'Đang tải...' : 'Loading...'}</div>
        </div>
      )}

      {/* EMPTY */}
      {!loading && !error && groups.length === 0 && (
        <div style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <Database size={32} style={{ marginBottom: '10px', opacity: 0.5 }} />
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
            {isVi ? 'Không Có Bản Ghi Nào' : 'No Quarantined Records Found'}
          </div>
          <div style={{ fontSize: '12px', marginTop: '4px' }}>
            {isVi ? 'Không có bản ghi nào phù hợp với bộ lọc.' : 'No records match the current filter.'}
          </div>
        </div>
      )}

      {/* GROUPS TABLE */}
      {!loading && groups.length > 0 && (
        <div style={{ border: '1px solid var(--glass-border)', borderRadius: '8px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-deep)', borderBottom: '1px solid var(--glass-border)' }}>
                <th style={{ padding: '10px', textAlign: 'left', width: '32px' }}></th>
                <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: '11px' }}>{isVi ? 'Quy Tắc' : 'RULE'}</th>
                <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: '11px' }}>{isVi ? 'Bảng Nguồn' : 'SOURCE TABLE'}</th>
                <th style={{ padding: '10px', textAlign: 'center', color: 'var(--text-muted)', fontWeight: 600, fontSize: '11px' }}>{isVi ? 'Số Dòng' : 'ROWS'}</th>
                <th style={{ padding: '10px', textAlign: 'center', color: 'var(--text-muted)', fontWeight: 600, fontSize: '11px' }}>{isVi ? 'Trạng Thái' : 'STATUS'}</th>
                <th style={{ padding: '10px', textAlign: 'center', color: 'var(--text-muted)', fontWeight: 600, fontSize: '11px' }}>{isVi ? 'Mức' : 'SEVERITY'}</th>
                <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: '11px' }}>{isVi ? 'Lý Do' : 'REASON'}</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => {
                const isExpanded = !!expanded[g.group_id];
                const sevColor = SEVERITY_COLOR[g.severity] || '#06b6d4';
                const isRejected = g.status === 'REJECTED_HELD';
                const remLoading = !!actionLoading[`rem_${g.group_id}`];
                const rejLoading = !!actionLoading[`rej_${g.group_id}`];

                return (
                  <React.Fragment key={g.group_id}>
                    {/* GROUP ROW */}
                    <tr
                      onClick={() => toggle(g.group_id)}
                      style={{
                        borderBottom: isExpanded ? 'none' : '1px solid var(--glass-border)',
                        background: isExpanded ? 'rgba(244, 63, 94, 0.04)' : 'transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <td style={{ padding: '10px', textAlign: 'center' }}>
                        {isExpanded ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
                      </td>
                      <td style={{ padding: '10px' }}>
                        <code style={{ background: 'rgba(2, 132, 199, 0.15)', color: '#06b6d4', padding: '2px 8px', borderRadius: '4px', fontSize: '12px' }}>
                          {g.rule_id}
                        </code>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{g.rule_name}</div>
                      </td>
                      <td style={{ padding: '10px', color: 'var(--text-main)' }}>
                        <code style={{ fontSize: '12px', color: 'var(--neon-cyan)' }}>{g.source_table}</code>
                      </td>
                      <td style={{ padding: '10px', textAlign: 'center', fontWeight: 600, color: sevColor }}>
                        {g.total_rows.toLocaleString()}
                      </td>
                      <td style={{ padding: '10px', textAlign: 'center' }}>
                        {isRejected ? (
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            background: 'rgba(239, 68, 68, 0.15)',
                            color: '#f87171',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                          }}>
                            {isVi ? 'ĐÃ TỪ CHỐI (ĐANG GIỮ)' : 'REJECTED (HELD)'}
                          </span>
                        ) : (
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            background: 'rgba(245, 158, 11, 0.15)',
                            color: '#f59e0b',
                            border: '1px solid rgba(245, 158, 11, 0.3)',
                          }}>
                            {isVi ? 'CHỜ XỬ LÝ' : 'PENDING'}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '10px', textAlign: 'center' }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 600,
                          background: `${sevColor}20`,
                          color: sevColor,
                          border: `1px solid ${sevColor}40`,
                        }}>
                          {g.severity}
                        </span>
                      </td>
                      <td style={{ padding: '10px', color: 'var(--text-muted)', fontSize: '12px' }}>
                        {g.reason_summary}
                      </td>
                    </tr>
                    {/* EXPANDED SECTION */}
                    {isExpanded && (
                      <tr style={{ background: 'var(--bg-deep)', borderBottom: '1px solid var(--glass-border)' }}>
                        <td colSpan={7} style={{ padding: '16px 20px' }}>
                          {/* AI SQL SUGGESTION & ACTION BUTTONS */}
                          <div style={{ marginBottom: '16px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                                <AlertTriangle size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                                {isVi ? 'Gợi ý SQL từ AI & Thao Tác Sửa Lỗi' : 'AI-Suggested Remediation SQL & HITL Actions'}
                              </div>
                              {isRejected && (
                                <div style={{ fontSize: '11px', color: '#f87171', fontStyle: 'italic' }}>
                                  * {isVi ? 'Nhóm đã bị từ chối trước đó, nhưng bạn vẫn có thể bấm "Chấp Nhận" nếu đổi ý.' : 'Group previously rejected. You can still Accept if you change your mind.'}
                                </div>
                              )}
                            </div>

                            <pre style={{
                              background: 'rgba(0,0,0,0.4)',
                              border: '1px solid var(--glass-border)',
                              borderRadius: '6px',
                              padding: '12px',
                              fontSize: '12px',
                              color: 'var(--neon-cyan)',
                              overflow: 'auto',
                              margin: 0,
                              fontFamily: 'monospace',
                            }}>
                              {g.ai_suggested_sql || 'No SQL suggestion available'}
                            </pre>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px', marginBottom: '12px' }}>
                              <strong style={{ color: 'var(--text-main)' }}>Strategy:</strong> {g.remediation_strategy}
                            </div>

                            {/* HITL ACTION BUTTONS */}
                            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRemediate(g);
                                }}
                                disabled={remLoading || rejLoading}
                                style={{
                                  padding: '8px 16px',
                                  background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                                  color: '#fff',
                                  border: 'none',
                                  borderRadius: '6px',
                                  fontWeight: 600,
                                  fontSize: '12px',
                                  cursor: remLoading || rejLoading ? 'not-allowed' : 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  boxShadow: '0 2px 6px rgba(16, 185, 129, 0.3)',
                                  opacity: remLoading || rejLoading ? 0.6 : 1,
                                }}
                              >
                                {remLoading ? (
                                  <RefreshCw size={14} className="spinning" />
                                ) : (
                                  <CheckCircle2 size={14} />
                                )}
                                {isVi ? 'Chấp Nhận & Chuẩn Hóa SQL' : 'Accept & Remediate SQL'}
                              </button>

                              {!isRejected && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleReject(g);
                                  }}
                                  disabled={remLoading || rejLoading}
                                  style={{
                                    padding: '8px 16px',
                                    background: 'transparent',
                                    color: '#f43f5e',
                                    border: '1px solid rgba(244, 63, 94, 0.5)',
                                    borderRadius: '6px',
                                    fontWeight: 600,
                                    fontSize: '12px',
                                    cursor: remLoading || rejLoading ? 'not-allowed' : 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    opacity: remLoading || rejLoading ? 0.6 : 1,
                                  }}
                                >
                                  {rejLoading ? (
                                    <RefreshCw size={14} className="spinning" />
                                  ) : (
                                    <XCircle size={14} />
                                  )}
                                  {isVi ? 'Từ Chối Gợi Ý SQL' : 'Reject SQL Suggestion'}
                                </button>
                              )}
                            </div>
                          </div>

                          {/* SAMPLE RECORDS */}
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                              <Eye size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                              {isVi ? 'Bản Ghi Mẫu' : 'Sample Records'} ({g.sample_records?.length || 0})
                            </div>
                            {g.sample_records && g.sample_records.length > 0 ? (
                              <div style={{ maxHeight: '240px', overflow: 'auto', border: '1px solid var(--glass-border)', borderRadius: '6px' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                                  <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                                    <tr>
                                      <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)' }}>#</th>
                                      <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)' }}>Reason</th>
                                      <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)' }}>Row Data</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {g.sample_records.map((r, i) => (
                                      <tr key={r.id || i} style={{ borderTop: '1px solid var(--glass-border)' }}>
                                        <td style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>{i + 1}</td>
                                        <td style={{ padding: '6px 10px', color: 'var(--text-main)' }}>{r.reason}</td>
                                        <td style={{ padding: '6px 10px', fontFamily: 'monospace', color: 'var(--neon-cyan)', fontSize: '10px', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                          {JSON.stringify(r.original_data).slice(0, 120)}
                                          {JSON.stringify(r.original_data).length > 120 ? '...' : ''}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '12px', fontStyle: 'italic' }}>
                                No sample records available
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

