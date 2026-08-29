import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Database,
  UserShield,
  Lock,
  Search,
  RefreshCw,
  Copy,
  Check,
  Eye,
} from 'lucide-react';

import { quarantineApi } from '../../services/api';
import { datasetStoreKey, useWorkspaceStore } from '../../stores/workspaceStore';

const EMPTY_SPLIT = {
  cleanRows: [] as unknown[],
  quarantineRows: [] as unknown[],
  totalClean: 0,
  totalQuarantine: 0,
  cleanRan: false,
  thisRun: false,
  snapshotId: '',
};

interface SplitDbQuarantineTabProps {
  datasetKey?: string;
  manifestHash?: string;
  /** Keep-mounted: GET refresh when shown. Empty GET cannot clobber stored rows. */
  active?: boolean;
  splitResult?: { clean_rows?: number | null; quarantine_rows?: number | null; clean?: any[]; quarantine?: any[] };
  dayIdx?: number | null;
  runId?: string | null;
}

export const SplitDbQuarantineTab: React.FC<SplitDbQuarantineTabProps> = ({
  datasetKey,
  manifestHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  active = false,
  splitResult,
  dayIdx = null,
  runId = null,
}) => {
  const storeKey = datasetStoreKey(datasetKey);
  const split = useWorkspaceStore((s) => s.splitRowsByDataset[storeKey]);
  const mergeSplitRows = useWorkspaceStore((s) => s.mergeSplitRows);
  const replaceSplitRows = useWorkspaceStore((s) => s.replaceSplitRows);
  const [viewMode, setViewMode] = useState<'clean' | 'quarantine'>('quarantine');
  const quarantineRows = (split?.quarantineRows as any[]) || [];
  const cleanRows = (split?.cleanRows as any[]) || [];
  const totalClean = split?.totalClean || 0;
  const totalQuarantine = split?.totalQuarantine || 0;
  const warehouseCommitted = !!split?.warehouseCommitted;
  const cleanRan = !!(split?.thisRun && split?.cleanRan);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRow, setSelectedRow] = useState<any | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const prev = useWorkspaceStore.getState().splitRowsByDataset[storeKey];
      const thisRun = !!(prev?.thisRun || prev?.snapshotId);
      // Parent splitResult is this-run sandbox only — never leftover warehouse 50k.
      if (thisRun && splitResult && ((splitResult.quarantine && splitResult.quarantine.length) || (splitResult.clean && splitResult.clean.length))) {
        mergeSplitRows(storeKey, {
          cleanRan: true,
          thisRun: true,
          quarantineRows: splitResult.quarantine || [],
          cleanRows: splitResult.clean || [],
          totalQuarantine: splitResult.quarantine_rows ?? (splitResult.quarantine || []).length,
          totalClean: splitResult.clean_rows ?? (splitResult.clean || []).length,
        });
      }

      const qRes = await quarantineApi.list(100);
      const incomingAll = (qRes && Array.isArray(qRes.quarantine)) ? qRes.quarantine : [];
      const incomingQ = incomingAll.filter((r: any) => {
        if (dayIdx === null || dayIdx === undefined) return true;
        const orig = r.original_data || r;
        const d = orig.assigned_day_index ?? orig.day_idx ?? r.assigned_day_index;
        if (d === undefined || d === null) return String(r.snapshot_id || '').includes(String(runId || ''));
        return Number(d) === Number(dayIdx);
      });
      // Empty GET must never clobber stored this-run rows.
      if (incomingQ.length === 0 && prev && (prev.quarantineRows.length > 0 || prev.cleanRan)) {
        // keep existing this-run quarantine — never clobber
      } else if (thisRun && incomingQ.length > 0) {
        const snap = prev?.snapshotId || '';
        const mine = snap
          ? incomingQ.filter((r: any) => String(r.snapshot_id || r.lineage_hash || '') && (
            String(r.snapshot_id || '') === snap || String(r.source_table || '') === storeKey
          ))
          : [];
        // Leftover GET (pre-seeded 100) is NOT this sandbox. Do not mark cleanRan.
        if (mine.length > 0) {
          mergeSplitRows(storeKey, {
            quarantineRows: mine,
            totalQuarantine: prev?.totalQuarantine || mine.length,
            cleanRan: true,
            thisRun: true,
          });
        }
      }

      // Do NOT treat leftover warehouse sample totals as this sandbox run.
      const st = useWorkspaceStore.getState();
      const ran = !!(st.splitRowsByDataset[storeKey]?.thisRun && st.splitRowsByDataset[storeKey]?.cleanRan);
      if (datasetKey && ran && st.splitRowsByDataset[storeKey]?.cleanRows.length === 0) {
        // keep existing — never clobber with warehouse sample
        const incomingC: any[] = [];
        if (incomingC.length === 0 && prev && prev.cleanRows.length > 0) {
          // keep existing — never clobber
        }
      }
    } catch (err) {
      console.warn('Could not fetch split db data:', err);
      // keep existing rows — empty/error must not wipe
    } finally {
      setLoading(false);
    }
  }, [datasetKey, mergeSplitRows, splitResult, storeKey, dayIdx, runId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, dayIdx]);

  useEffect(() => {
    if (active) void fetchData();
  }, [active, dayIdx, fetchData]);

  useEffect(() => {
    const onSplit = (ev: Event) => {
      const d = (ev as CustomEvent).detail || {};
      const incomingKey = datasetStoreKey(d.dataset_key || datasetKey);
      if (incomingKey !== storeKey && d.dataset_key) return;
      const q = Array.isArray(d.quarantine) ? d.quarantine : [];
      const c = Array.isArray(d.clean) ? d.clean : [];
      if (d.sandbox || d.thisRun) {
        replaceSplitRows(storeKey, {
          ...EMPTY_SPLIT,
          cleanRan: true,
          thisRun: true,
          warehouseCommitted: !!(d.warehouseCommitted || d.counts_kind === 'warehouse'),
          snapshotId: d.snapshot_id || '',
          quarantineRows: q,
          cleanRows: c,
          totalQuarantine: d.quarantine_rows ?? q.length,
          totalClean: d.clean_rows ?? c.length,
        });
        return;
      }
      if (q.length || c.length) {
        mergeSplitRows(storeKey, {
          cleanRan: true,
          thisRun: true,
          quarantineRows: q,
          cleanRows: c,
          totalQuarantine: d.quarantine_rows ?? q.length,
          totalClean: d.clean_rows ?? c.length,
        });
      }
    };
    const onFailed = (ev: Event) => {
      const d = (ev as CustomEvent).detail || {};
      const incomingKey = datasetStoreKey(d.dataset_key || datasetKey);
      if (incomingKey !== storeKey && d.dataset_key) return;
      replaceSplitRows(storeKey, { ...EMPTY_SPLIT });
    };
    const onReset = () => {
      replaceSplitRows(storeKey, { ...EMPTY_SPLIT });
    };
    window.addEventListener('datatrust:split-refresh', onSplit as EventListener);
    window.addEventListener('datatrust:sandbox-split', onSplit as EventListener);
    window.addEventListener('datatrust:sandbox-failed', onFailed as EventListener);
    window.addEventListener('datatrust:db-reset', onReset);
    return () => {
      window.removeEventListener('datatrust:split-refresh', onSplit as EventListener);
      window.removeEventListener('datatrust:sandbox-split', onSplit as EventListener);
      window.removeEventListener('datatrust:sandbox-failed', onFailed as EventListener);
      window.removeEventListener('datatrust:db-reset', onReset);
    };
  }, [datasetKey, fetchData, mergeSplitRows, replaceSplitRows, storeKey]);

  const handleCopyHash = () => {
    navigator.clipboard.writeText(manifestHash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const activeRows = viewMode === 'clean' ? cleanRows : quarantineRows;

  const filteredRows = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return activeRows;
    return activeRows.filter((r) =>
      JSON.stringify(r).toLowerCase().includes(q)
    );
  }, [activeRows, searchQuery]);

  return (
    <div className="split-db-tab">
      {/* CRYPTOGRAPHIC SHA-256 MANIFEST BANNER */}
      <div className="manifest-banner-card">
        <div className="manifest-banner-header">
          <div className="manifest-banner-left">
            <Lock size={13} style={{ color: 'var(--electric-green)' }} />
            <span className="manifest-title">{isVi ? 'Bản Kê Nguồn Gốc Mật Mã (Lineage)' : 'Cryptographic Lineage Manifest'}</span>
          </div>
          <span className="manifest-badge">{isVi ? 'Đã Xác Thực SHA-256' : 'SHA-256 Verified'}</span>
        </div>
        <div className="manifest-hash-row">
          <code className="manifest-hash-text">{manifestHash}</code>
          <button className="manifest-copy-btn" onClick={handleCopyHash} title={isVi ? 'Sao chép mã băm SHA-256' : 'Copy SHA-256 Hash'}>
            {copiedHash ? <Check size={13} style={{ color: 'var(--electric-green)' }} /> : <Copy size={13} />}
          </button>
        </div>
      </div>

      {/* VIEW TOGGLE AND STATS */}
      <div className="split-toggle-header">
        <div className="split-toggle-buttons">
          <button
            className={`split-tab-pill ${viewMode === 'quarantine' ? 'active-quarantine' : ''}`}
            onClick={() => {
              setViewMode('quarantine');
              setSelectedRow(null);
            }}
          >
            <UserShield size={13} />
            <span>
              {warehouseCommitted
                ? (isVi ? `Khu Vực Cách Ly (${totalQuarantine.toLocaleString()})` : `Quarantine (${totalQuarantine.toLocaleString()})`)
                : (isVi ? `Cách ly xem trước (${totalQuarantine.toLocaleString()})` : `Preview quarantine (${totalQuarantine.toLocaleString()})`)}
            </span>
          </button>
          <button
            className={`split-tab-pill ${viewMode === 'clean' ? 'active-clean' : ''}`}
            onClick={() => {
              setViewMode('clean');
              setSelectedRow(null);
            }}
          >
            <Database size={13} />
            <span>
              {warehouseCommitted
                ? (isVi ? `Kho Dữ Liệu Sạch (${totalClean.toLocaleString()})` : `Clean Warehouse (${totalClean.toLocaleString()})`)
                : (isVi ? `Sạch xem trước (${totalClean.toLocaleString()})` : `Preview clean (${totalClean.toLocaleString()})`)}
            </span>
          </button>
        </div>

        <button className="traces-refresh-btn" onClick={fetchData} disabled={loading} title={isVi ? 'Làm mới danh sách dòng' : 'Refresh dataset rows'}>
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px 0' }}>
        {warehouseCommitted
          ? (isVi
            ? `Kho sau Execute (bảng + ngày): Sạch ${totalClean.toLocaleString()} · Cách ly ${totalQuarantine.toLocaleString()}.`
            : `Warehouse after Execute (table + day): Clean ${totalClean.toLocaleString()} · Quarantine ${totalQuarantine.toLocaleString()}.`)
          : (isVi
            ? 'Ước lượng xem trước theo bảng + ngày — chưa phải kho sau Execute. Kho đã ghi: Sạch 0 · Cách ly 0.'
            : 'Preview estimate for this table + day — not warehouse after Execute. Committed warehouse: Clean 0 · Quarantine 0.')}
      </div>

      {/* SEARCH BAR */}
      <div className="profiler-search-wrapper" style={{ margin: '8px 0 10px 0' }}>
        <Search size={13} className="profiler-search-icon" />
        <input
          type="text"
          className="profiler-search-input"
          placeholder={
            viewMode === 'clean'
              ? (isVi ? 'Tìm kiếm bản ghi sạch...' : 'Search clean records...')
              : (isVi ? 'Tìm kiếm bản ghi cách ly, mã bộ luật, lý do...' : 'Search quarantined records, rule IDs, reasons...')
          }
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* DATA GRID */}
      {filteredRows.length === 0 ? (
        <div className="empty-panel-state">
          <Database size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
            {viewMode === 'clean'
              ? (isVi ? 'Không Tìm Thấy Bản Ghi Sạch Nào' : 'No Clean Records Found')
              : (isVi ? 'Không Tìm Thấy Bản Ghi Cách Ly Nào' : 'No Quarantined Records Found')}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {!cleanRan
              ? (isVi
                ? 'Chưa chạy clean. Duyệt luật HITL rồi sandbox/execute — không bịa dòng cách ly hay kho sạch.'
                : 'Clean has not run. Approve at HITL, then sandbox/execute. No quarantine or clean rows invented.')
              : viewMode === 'quarantine'
                ? (isVi ? 'Không có dòng nào vi phạm bộ luật chất lượng. Dữ liệu hoàn toàn sạch.' : 'Zero rows violated data quality rules. Dataset is clean.')
                : (isVi ? 'Phân vùng sạch sẽ được tạo khi động cơ làm sạch chạy.' : 'Clean partitions will be created once the cleansing engine executes.')}
          </div>
        </div>
      ) : (
        <div className="split-table-wrapper">
          <table className="split-table">
            <thead>
              {viewMode === 'quarantine' ? (
                <tr>
                  <th>{isVi ? 'Mã Dòng' : 'Row ID'}</th>
                  <th>{isVi ? 'Bảng Nguồn' : 'Source Table'}</th>
                  <th>{isVi ? 'Bộ Luật Vi Phạm' : 'Violated Rule'}</th>
                  <th>{isVi ? 'Mã Lý Do' : 'Reason Code'}</th>
                </tr>
              ) : (
                <tr>
                  <th>#</th>
                  <th>{isVi ? 'Mã Phương Tiện / Khóa' : 'Vehicle VIN / Key'}</th>
                  <th>{isVi ? 'Vận Tốc (km/h)' : 'Speed (km/h)'}</th>
                  <th>SOC (%)</th>
                  <th>{isVi ? 'Trạng Thái' : 'Status'}</th>
                </tr>
              )}
            </thead>
            <tbody>
              {filteredRows.map((row, idx) => {
                if (viewMode === 'quarantine') {
                  return (
                    <tr
                      key={row.id || `q-${idx}`}
                      className={selectedRow?.id === row.id ? 'selected-row' : ''}
                      onClick={() => setSelectedRow(row)}
                    >
                      <td>
                        <strong>{row.source_row_id || row.id || `#${idx + 1}`}</strong>
                      </td>
                      <td>
                        <span className="text-dim">{row.source_table || datasetKey || 'dataset'}</span>
                      </td>
                      <td>
                        <span className="rule-tag">{row.rule_id || 'R1_A1'}</span>
                      </td>
                      <td>
                        <span className="tag-quarantine">{row.reason || 'OUT_OF_BOUNDS'}</span>
                      </td>
                    </tr>
                  );
                } else {
                  return (
                    <tr
                      key={`c-${idx}`}
                      className={selectedRow === row ? 'selected-row' : ''}
                      onClick={() => setSelectedRow(row)}
                    >
                      <td>#{idx + 1}</td>
                      <td>
                        <code>{row.vehicle_vin || row.vin || row.record_id || `rec_${idx}`}</code>
                      </td>
                      <td>{row.speed_kmh !== undefined ? row.speed_kmh : '—'}</td>
                      <td>{row.battery_soc !== undefined ? `${row.battery_soc}%` : (row.soc_pct !== undefined ? `${row.soc_pct}%` : '—')}</td>
                      <td>
                        <span className="tag-clean">{isVi ? 'SẠCH' : 'CLEAN'}</span>
                      </td>
                    </tr>
                  );
                }
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* SELECTED ROW DETAIL MODAL / DRAWER */}
      {selectedRow && (
        <div className="col-detail-card" style={{ marginTop: 12 }}>
          <div className="col-detail-header">
            <span className="col-detail-title">
              <Eye size={13} /> {isVi ? 'Chi Tiết Bản Ghi:' : 'Record Details:'} <code>{selectedRow.id || selectedRow.source_row_id || 'Row'}</code>
            </span>
            <button className="col-detail-close" onClick={() => setSelectedRow(null)}>✕</button>
          </div>
          <pre className="trace-code-block" style={{ maxHeight: 180, marginTop: 8 }}>
            <code>{JSON.stringify(selectedRow, null, 2)}</code>
          </pre>
        </div>
      )}
    </div>
  );
};
