import React, { useEffect, useState, useCallback } from 'react';
import { ShieldAlert, Eye, X, CheckCircle, RefreshCw, Filter } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ingestionApi } from '../../services/api';
import type { QuarantineSummaryRule, QuarantineDetailRecord } from '../../services/api';

interface QuarantinePanelProps {
  table?: string;
}

export const QuarantinePanel: React.FC<QuarantinePanelProps> = ({ table = 'ev_telemetry' }) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';

  const [summary, setSummary] = useState<QuarantineSummaryRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerRule, setDrawerRule] = useState<QuarantineSummaryRule | null>(null);
  const [drawerRecords, setDrawerRecords] = useState<QuarantineDetailRecord[]>([]);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerViaFilter, setDrawerViaFilter] = useState<string>('');
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [openOnly, setOpenOnly] = useState(true);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    try {
      const res = await ingestionApi.getQuarantineSummary(table);
      setSummary(res.rules || []);
    } catch {
      setSummary([]);
    } finally {
      setLoading(false);
    }
  }, [table]);

  useEffect(() => {
    void fetchSummary();
  }, [fetchSummary]);

  const openDrawer = async (rule: QuarantineSummaryRule) => {
    setDrawerRule(rule);
    setDrawerViaFilter('');
    setDrawerLoading(true);
    try {
      const res = await ingestionApi.getQuarantineDetail(rule.rule_id, table);
      setDrawerRecords(res.records || []);
    } catch {
      setDrawerRecords([]);
    } finally {
      setDrawerLoading(false);
    }
  };

  const closeDrawer = () => {
    setDrawerRule(null);
    setDrawerRecords([]);
  };

  const resolveRecord = async (quarantineId: string, action: string) => {
    setResolvingId(quarantineId);
    try {
      await ingestionApi.resolveQuarantine(quarantineId, action);
      setDrawerRecords((prev) =>
        prev.map((r) =>
          r.quarantine_id === quarantineId ? { ...r, status: 'RESOLVED' as const } : r
        )
      );
    } finally {
      setResolvingId(null);
    }
  };

  const filteredRecords = drawerViaFilter
    ? drawerRecords.filter((r) => r.detected_via === drawerViaFilter)
    : drawerRecords;

  const visibleRecords = openOnly
    ? filteredRecords.filter((r) => r.status !== 'RESOLVED')
    : filteredRecords;

  const totalOpen = summary.reduce((acc, r) => acc + (r.status !== 'RESOLVED' ? r.total_records : 0), 0);

  return (
    <div className="quarantine-panel-root">
      {/* Summary header */}
      <div className="quarantine-summary-header">
        <div className="qh-left">
          <ShieldAlert size={15} color="var(--alert-magenta)" />
          <span className="qh-title">
            {isVi ? 'Sự cố chưa giải quyết' : 'Unresolved Issues'}
          </span>
          {totalOpen > 0 && (
            <span className="qh-open-badge">{totalOpen} {isVi ? 'mở' : 'open'}</span>
          )}
        </div>
        <button className="qh-refresh-btn" onClick={() => void fetchSummary()} title={isVi ? 'Làm mới' : 'Refresh'}>
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Rules list */}
      {loading ? (
        <div className="quarantine-loading">
          {[1, 2, 3].map((i) => (
            <div key={i} className="quarantine-skeleton" />
          ))}
        </div>
      ) : summary.length === 0 ? (
        <div className="quarantine-empty">
          <CheckCircle size={20} color="var(--electric-green)" />
          <span>{isVi ? 'Không có sự cố nào' : 'No issues found'}</span>
        </div>
      ) : (
        <div className="quarantine-rules-list">
          {summary.map((rule) => (
            <div
              key={`${rule.rule_id}-${rule.detected_via}`}
              className={`quarantine-rule-card ${rule.status === 'RESOLVED' ? 'resolved' : 'open'}`}
            >
              <div className="qrc-top">
                <div className="qrc-left">
                  <span className={`layer-badge ${(rule.rule_layer || 'L1').toLowerCase()}`}>
                    {rule.rule_layer || 'L1'}
                  </span>
                  <span className="qrc-rule-name">{rule.rule_name || rule.rule_id}</span>
                  <span className="qrc-via-badge">{rule.detected_via}</span>
                </div>
                <span className="qrc-count">{rule.total_records}</span>
              </div>

              <div className="qrc-reason">{rule.sample_reason || '—'}</div>

              <div className="qrc-meta">
                <span>{rule.affected_days} {isVi ? 'ngày' : 'days'}</span>
                <span>·</span>
                <span>{rule.affected_entities} {isVi ? 'thực thể' : 'entities'}</span>
                <span>·</span>
                <span>{isVi ? 'Lần cuối:' : 'Last:'} {rule.last_seen ? new Date(rule.last_seen).toLocaleString() : '—'}</span>
              </div>

              <button className="qrc-view-btn" onClick={() => void openDrawer(rule)}>
                <Eye size={12} />
                {isVi ? 'Xem chi tiết' : 'View details'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Drawer */}
      {drawerRule && (
        <div className="modal-overlay" onClick={closeDrawer}>
          <div className="quarantine-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Drawer header */}
            <div className="drawer-header">
              <div className="drawer-title-group">
                <span className={`layer-badge ${(drawerRule.rule_layer || 'L1').toLowerCase()}`}>
                  {drawerRule.rule_layer || 'L1'}
                </span>
                <div>
                  <div className="drawer-rule-name">{drawerRule.rule_name || drawerRule.rule_id}</div>
                  <div className="drawer-rule-id">{drawerRule.rule_id}</div>
                </div>
              </div>
              <button className="drawer-close" onClick={closeDrawer}>
                <X size={16} />
              </button>
            </div>

            {/* Filter bar */}
            <div className="drawer-filter-bar">
              <Filter size={12} color="var(--text-muted)" />
              <span className="filter-label">{isVi ? 'Nguồn phát hiện:' : 'Detected via:'}</span>
              {['', 'BATCH', 'REALTIME'].map((via) => (
                <button
                  key={via || 'all'}
                  className={`filter-chip ${drawerViaFilter === via ? 'active' : ''}`}
                  onClick={() => setDrawerViaFilter(via)}
                >
                  {via === '' ? (isVi ? 'Tất cả' : 'All') : via}
                </button>
              ))}

              <div className="filter-sep" />

              <label className="open-only-toggle">
                <input
                  type="checkbox"
                  checked={openOnly}
                  onChange={(e) => setOpenOnly(e.target.checked)}
                />
                <span>{isVi ? 'Chỉ OPEN' : 'OPEN only'}</span>
              </label>
            </div>

            {/* Records table */}
            <div className="drawer-records">
              {drawerLoading ? (
                <div className="drawer-loading">{isVi ? 'Đang tải...' : 'Loading...'}</div>
              ) : visibleRecords.length === 0 ? (
                <div className="drawer-empty">
                  {isVi ? 'Không có bản ghi nào phù hợp' : 'No matching records'}
                </div>
              ) : (
                visibleRecords.map((rec) => (
                  <div key={rec.quarantine_id} className={`drawer-record ${rec.status.toLowerCase()}`}>
                    <div className="dr-top">
                      <span className="dr-id">{rec.quarantine_id.slice(0, 16)}…</span>
                      <span className={`dr-status ${rec.status.toLowerCase()}`}>{rec.status}</span>
                      <span className="dr-day">D{rec.day_idx}</span>
                      {rec.vehicle_vin && <span className="dr-vin">{rec.vehicle_vin}</span>}
                    </div>
                    <div className="dr-reason">{rec.reason}</div>
                    <div className="dr-meta">
                      <span>{rec.detected_via}</span>
                      <span>·</span>
                      <span>{rec.detected_at ? new Date(rec.detected_at).toLocaleString() : '—'}</span>
                    </div>
                    {rec.status !== 'RESOLVED' && (
                      <div className="dr-actions">
                        <button
                          className="dr-action-btn accept"
                          onClick={() => void resolveRecord(rec.quarantine_id, 'ACCEPT_OVERRIDE')}
                          disabled={resolvingId === rec.quarantine_id}
                        >
                          <CheckCircle size={11} />
                          {isVi ? 'Chấp nhận' : 'Accept'}
                        </button>
                        <button
                          className="dr-action-btn baseline"
                          onClick={() => void resolveRecord(rec.quarantine_id, 'RECHARGE_BASELINE')}
                          disabled={resolvingId === rec.quarantine_id}
                        >
                          <RefreshCw size={11} />
                          {isVi ? 'Nạp lại baseline' : 'Recharge'}
                        </button>
                        <button
                          className="dr-action-btn dismiss"
                          onClick={() => void resolveRecord(rec.quarantine_id, 'DISMISS')}
                          disabled={resolvingId === rec.quarantine_id}
                        >
                          <X size={11} />
                          {isVi ? 'Bỏ qua' : 'Dismiss'}
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
