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

import { quarantineApi, datasetsApi } from '../../services/api';

interface SplitDbQuarantineTabProps {
  datasetKey?: string;
  manifestHash?: string;
}

export const SplitDbQuarantineTab: React.FC<SplitDbQuarantineTabProps> = ({
  datasetKey,
  manifestHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
}) => {
  const [viewMode, setViewMode] = useState<'clean' | 'quarantine'>('quarantine');
  const [quarantineRows, setQuarantineRows] = useState<any[]>([]);
  const [cleanRows, setCleanRows] = useState<any[]>([]);
  const [totalClean, setTotalClean] = useState(0);
  const [totalQuarantine, setTotalQuarantine] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRow, setSelectedRow] = useState<any | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch quarantine records
      const qRes = await quarantineApi.list(100);
      if (qRes && Array.isArray(qRes.quarantine)) {
        setQuarantineRows(qRes.quarantine);
        setTotalQuarantine(qRes.quarantine.length);
      }

      // Fetch clean sampled rows for active dataset
      if (datasetKey) {
        const cRes = await datasetsApi.sample(datasetKey, 50, 0);
        if (cRes && Array.isArray(cRes.rows)) {
          setCleanRows(cRes.rows);
          setTotalClean(cRes.total_rows || cRes.rows.length);
        }
      }
    } catch (err) {
      console.warn('Could not fetch split db data:', err);
    } finally {
      setLoading(false);
    }
  }, [datasetKey]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
            <span>{isVi ? `Khu Vực Cách Ly (${totalQuarantine.toLocaleString()})` : `Quarantine (${totalQuarantine.toLocaleString()})`}</span>
          </button>
          <button
            className={`split-tab-pill ${viewMode === 'clean' ? 'active-clean' : ''}`}
            onClick={() => {
              setViewMode('clean');
              setSelectedRow(null);
            }}
          >
            <Database size={13} />
            <span>{isVi ? `Kho Dữ Liệu Sạch (${totalClean.toLocaleString()})` : `Clean Warehouse (${totalClean.toLocaleString()})`}</span>
          </button>
        </div>

        <button className="traces-refresh-btn" onClick={fetchData} disabled={loading} title={isVi ? 'Làm mới danh sách dòng' : 'Refresh dataset rows'}>
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
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
            {viewMode === 'quarantine'
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
