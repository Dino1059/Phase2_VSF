import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FlaskConical,
  ShieldAlert,
  ArrowRight,
  Database,
  Columns,
  CheckCircle2,
  Lock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export interface SandboxCellDiff {
  row_id: string;
  field: string;
  source_table?: string;
  rule_id?: string;
  before_value: any;
  after_value: any;
  reason?: string;
}

export interface SandboxDiffData {
  run_id?: string;
  dataset_key?: string;
  health_before?: string | null;
  health_after?: string | null;
  counts?: {
    clean_rows?: number;
    quarantine_rows?: number;
    scoped_rows?: number;
    total_rows?: number;
    per_rule?: Record<string, number>;
    kind?: string;
  };
  clean_rows?: number;
  quarantine_rows?: number;
  scoped_rows?: number;
  sampled_rows?: number;
  counts_kind?: string;
  warehouse_clean_rows?: number;
  warehouse_quarantine_rows?: number;
  quarantine?: any[];
  cell_diffs?: SandboxCellDiff[];
  per_rule_counts?: Record<string, number>;
  tables?: string[];
  columns?: string[];
  manifest_hash?: string;
  promoted?: boolean;
  execute?: string;
}

interface SandboxDiffProps {
  diffData: SandboxDiffData;
  onPromote?: () => void;
  promoting?: boolean;
  promoted?: boolean;
}

export const SandboxDiff: React.FC<SandboxDiffProps> = ({
  diffData,
  onPromote,
  promoting = false,
  promoted = false,
}) => {
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const [expanded, setExpanded] = useState(true);

  const runId = diffData.run_id || '';
  const healthBefore = diffData.health_before || '—';
  const healthAfter = diffData.health_after || '—';
  const quarantineCount = diffData.quarantine_rows ?? diffData.counts?.quarantine_rows ?? 0;
  const cleanCount = diffData.clean_rows ?? diffData.counts?.clean_rows ?? 0;
  const scopedCount = diffData.scoped_rows ?? diffData.counts?.scoped_rows ?? (cleanCount + quarantineCount);
  const sampledCount = diffData.sampled_rows ?? 0;
  const warehouseClean = diffData.warehouse_clean_rows ?? 0;
  const warehouseQ = diffData.warehouse_quarantine_rows ?? 0;
  
  const perRuleCounts = diffData.per_rule_counts || diffData.counts?.per_rule || {};
  const cellDiffs = (diffData.cell_diffs && diffData.cell_diffs.length > 0)
    ? diffData.cell_diffs
    : [];

  const tables = diffData.tables && diffData.tables.length > 0 ? diffData.tables : [diffData.dataset_key || 'data_new'];
  const cols = diffData.columns && diffData.columns.length > 0 ? diffData.columns : [];

  const isPromotedState = promoted || !!diffData.promoted;

  return (
    <div
      className="sandbox-diff-panel"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid rgba(2, 132, 199, 0.35)',
        borderRadius: '10px',
        padding: '12px 14px',
        marginBottom: '14px',
        boxShadow: '0 4px 14px rgba(2, 132, 199, 0.08)',
      }}
    >
      {/* HEADER BAR */}
      <div
        className="sandbox-diff-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
          paddingBottom: expanded ? '10px' : '0',
          borderBottom: expanded ? '1px solid var(--glass-border)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div
            style={{
              background: 'rgba(2, 132, 199, 0.15)',
              color: '#0284c7',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <FlaskConical size={16} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>
                {isVi ? 'Kết Quả Cách Ly Sandbox' : 'Sandbox Quarantine Simulation'}
              </span>
              <span
                style={{
                  fontSize: '10.5px',
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: '12px',
                  background: isPromotedState ? 'rgba(5, 150, 105, 0.15)' : 'rgba(2, 132, 199, 0.15)',
                  color: isPromotedState ? '#059669' : '#0284c7',
                  border: isPromotedState ? '1px solid rgba(5, 150, 105, 0.3)' : '1px solid rgba(2, 132, 199, 0.3)',
                }}
              >
                {isPromotedState
                  ? (isVi ? 'ĐÃ QUẢNG BÁ PROD' : 'PROMOTED TO PROD')
                  : (isVi ? 'XEM TRƯỚC CÔ LẬP' : 'ISOLATED PREVIEW')}
              </span>
              <span data-testid="hitl-warehouse-clean-zero" style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600 }}>
                {warehouseClean > 0
                  ? (isVi ? `Clean Warehouse = ${warehouseClean}` : `Clean Warehouse = ${warehouseClean}`)
                  : (isVi ? 'Clean Warehouse = 0 đến Execute' : 'Clean Warehouse = 0 until Execute')}
              </span>
            </div>
            {runId && (
              <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                <code>{runId}</code>
                {' · '}
                {isVi
                  ? `Ước lượng xem trước (bảng + ngày): ${cleanCount.toLocaleString()} sạch · ${quarantineCount.toLocaleString()} cách ly / ${scopedCount.toLocaleString()} trong phạm vi`
                  : `Preview estimate (table + day): ${cleanCount.toLocaleString()} clean · ${quarantineCount.toLocaleString()} quarantined / ${scopedCount.toLocaleString()} in-scope`}
                {sampledCount > 0
                  ? (isVi ? ` · ${sampledCount} dòng mẫu` : ` · ${sampledCount} example rows`)
                  : ''}
              </div>
            )}
          </div>
        </div>

        {/* HEALTH DELTA & EXPAND TOGGLE */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div
            className="sandbox-health-delta-chip"
            title={isVi ? 'Điểm sức khỏe trước và sau khi cô lập sandbox' : 'Dataset health score before and after sandbox quarantine isolation'}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(0, 0, 0, 0.04)',
              border: '1px solid var(--glass-border)',
              borderRadius: '6px',
              padding: '4px 8px',
              fontSize: '11.5px',
            }}
          >
            <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{isVi ? 'Sức Khỏe:' : 'Health:'}</span>
            <span style={{ color: '#f87171', fontWeight: 700 }}>{healthBefore}</span>
            <ArrowRight size={12} style={{ color: 'var(--text-muted)' }} />
            <span style={{ color: '#34d399', fontWeight: 700 }}>{healthAfter}</span>
          </div>

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: '4px',
            }}
            title={expanded ? (isVi ? 'Thu gọn' : 'Collapse') : (isVi ? 'Mở rộng' : 'Expand')}
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* TABLES & COLUMNS CHIPS */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
              {isVi ? 'Phạm vi ảnh hưởng:' : 'Affected Scope:'}
            </span>
            {tables.map((t) => (
              <span
                key={t}
                style={{
                  fontSize: '10.5px',
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: '4px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-main)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Database size={10} style={{ color: '#0284c7' }} /> {t}
              </span>
            ))}
            {cols.map((c) => (
              <span
                key={c}
                style={{
                  fontSize: '10.5px',
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: '4px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-main)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Columns size={10} style={{ color: '#34d399' }} /> {c}
              </span>
            ))}
          </div>

          {/* PER-RULE QUARANTINE COUNTS */}
          {Object.keys(perRuleCounts).length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
                {isVi ? 'Số dòng cách ly theo từng ràng buộc:' : 'Quarantine impact per rule constraint:'}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {Object.entries(perRuleCounts).map(([ruleId, count]) => (
                  <div
                    key={ruleId}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: 'rgba(220, 38, 38, 0.08)',
                      border: '1px solid rgba(220, 38, 38, 0.25)',
                      color: '#dc2626',
                      padding: '3px 8px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 600,
                    }}
                  >
                    <ShieldAlert size={12} />
                    <span><code>{ruleId}</code>:</span>
                    <strong>{count} {isVi ? 'dòng' : 'rows'}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5-10 BEFORE -> AFTER HIGHLIGHTED CELLS */}
          {cellDiffs.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}>
                <span>{isVi ? 'Bản xem trước sai khác giá trị mẫu (5–10 dòng):' : 'Sample cell diff preview (5–10 rows):'}</span>
                <span style={{ fontSize: '10.5px' }}>
                  {isVi
                    ? `${cleanCount} sạch · ${quarantineCount} cách ly (xem trước)`
                    : `${cleanCount} clean · ${quarantineCount} quarantined (preview)`}
                </span>
              </div>
              <div
                style={{
                  maxHeight: '180px',
                  overflowY: 'auto',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '6px',
                  background: 'var(--bg-input, rgba(0, 0, 0, 0.02))',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid var(--glass-border)', textAlign: 'left' }}>
                      <th style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--text-muted)' }}>{isVi ? 'Mã Dòng' : 'Row ID'}</th>
                      <th style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--text-muted)' }}>{isVi ? 'Trường' : 'Field'}</th>
                      <th style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--text-muted)' }}>{isVi ? 'Trước (Dữ Liệu Gốc)' : 'Before (Raw Value)'}</th>
                      <th style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--text-muted)' }}>{isVi ? 'Sau (Hành Động Sandbox)' : 'After (Sandbox Action)'}</th>
                      <th style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--text-muted)' }}>{isVi ? 'Lý Do Vi Phạm' : 'Violation Reason'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cellDiffs.map((diff, i) => (
                      <tr
                        key={`${diff.row_id}-${diff.field}-${i}`}
                        style={{
                          borderBottom: i < cellDiffs.length - 1 ? '1px solid var(--glass-border)' : 'none',
                        }}
                      >
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)' }}>
                          <strong>#{diff.row_id}</strong>
                        </td>
                        <td style={{ padding: '5px 8px', color: 'var(--text-main)', fontWeight: 600 }}>
                          {diff.field}
                        </td>
                        <td style={{ padding: '5px 8px' }}>
                          <span
                            style={{
                              background: 'rgba(220, 38, 38, 0.12)',
                              color: '#dc2626',
                              padding: '1px 5px',
                              borderRadius: '3px',
                              fontFamily: 'var(--font-mono)',
                              textDecoration: 'line-through',
                              fontWeight: 600,
                            }}
                          >
                            {String(diff.before_value ?? 'NULL')}
                          </span>
                        </td>
                        <td style={{ padding: '5px 8px' }}>
                          <span
                            style={{
                              background: 'rgba(5, 150, 105, 0.12)',
                              color: '#059669',
                              padding: '1px 5px',
                              borderRadius: '3px',
                              fontFamily: 'var(--font-mono)',
                              fontWeight: 700,
                            }}
                          >
                            {String(diff.after_value ?? '[QUARANTINED]')}
                          </span>
                        </td>
                        <td style={{ padding: '5px 8px', color: 'var(--text-muted)', fontSize: '10.5px' }}>
                          {diff.reason || diff.rule_id || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ACTION FOOTER BAR */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px',
              paddingTop: '6px',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {isPromotedState ? (
                <span style={{ color: '#059669', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <CheckCircle2 size={13} /> {isVi ? 'Đã quảng bá vào bảng quarantine sản xuất.' : 'Promoted into production quarantine table.'}
                </span>
              ) : (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <Lock size={12} /> {isVi
                    ? `Xem trước cô lập — execute tắt. Kho sau Execute: Sạch ${warehouseClean} · Cách ly ${warehouseQ}.`
                    : `Isolated preview — execute off. Warehouse after Execute: Clean ${warehouseClean} · Quarantine ${warehouseQ}.`}
                </span>
              )}
            </div>

            {onPromote && !isPromotedState && (
              <button
                type="button"
                onClick={onPromote}
                disabled={promoting}
                style={{
                  background: 'linear-gradient(135deg, #059669, #10b981)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '5px 12px',
                  fontSize: '11.5px',
                  fontWeight: 600,
                  cursor: promoting ? 'wait' : 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  boxShadow: '0 2px 8px rgba(5, 150, 105, 0.25)',
                }}
              >
                <CheckCircle2 size={13} />
                <span>{promoting ? (isVi ? 'Đang quảng bá…' : 'Promoting…') : (isVi ? 'Chấp nhận & Quảng bá vào Prod' : 'Accept & Promote to Prod')}</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
