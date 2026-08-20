import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Pencil,
  CheckCheck,
  RefreshCw,
  Code2,
  AlertTriangle,
  HelpCircle,
  Layers,
  Sparkles,
} from 'lucide-react';
import { approvalsApi, hitlApi, HITLProposal } from '../../services/api';

interface QualityRulesTabProps {
  datasetKey?: string;
  /** Keep-mounted tab: refetch when shown. GET queue only — never re-run Propose. */
  active?: boolean;
  onExecuteClean?: () => void;
}

interface EnrichedRuleReasoning {
  layer: string;
  problem: string;
  why: string;
  guarantee: string;
  impact: string;
}

function getRuleReasoning(rule: HITLProposal, isVi: boolean): EnrichedRuleReasoning {
  const expr = rule.rule_expression || '—';
  const col = rule.rule_name || rule.rule_id || 'column';
  return {
    layer: isVi ? 'L1 Hợp đồng dữ liệu' : 'L1 Data contract',
    problem: isVi
      ? `Luật đề xuất cho ${col}. Chưa thực thi.`
      : `Proposed constraint on ${col}. Not executed yet.`,
    why: isVi
      ? 'Sinh từ profile cột của dataset đang chọn, không dùng số liệu demo.'
      : 'Synthesized from this dataset’s column profile. No demo counts.',
    guarantee: isVi ? `Ràng buộc: ${expr}` : `Constraint: ${expr}`,
    impact: isVi
      ? 'Steward duyệt xong mới được clean/quarantine.'
      : 'Clean/quarantine runs only after steward approval.',
  };
}


/** Same status the card pill uses. Header counts MUST use this (count what you show). */
function ruleCardStatus(rule: { status?: string | null }): 'approved' | 'rejected' | 'proposed' {
  const raw = String(rule.status ?? '').trim().toLowerCase();
  if (raw === 'approved' || raw === 'edited') return 'approved';
  if (raw === 'rejected') return 'rejected';
  // unlabeled / whitespace / Proposed / pending / draft / queued → PROPOSED pill
  return 'proposed';
}

export const QualityRulesTab: React.FC<QualityRulesTabProps> = ({ datasetKey, active = false, onExecuteClean: _onExecuteClean }) => {
  const [proposals, setProposals] = useState<HITLProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [sandboxAuthorized, setSandboxAuthorized] = useState(false);
  const [payloadHash, setPayloadHash] = useState<string | null>(null);
  const [sandboxError, setSandboxError] = useState<string | null>(null);
  const [editingRule, setEditingRule] = useState<HITLProposal | null>(null);
  const [editExpression, setEditExpression] = useState('');
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const fetchRules = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = !!opts?.silent;
    if (!silent) setLoading(true);
    try {
      const res = await hitlApi.queue(datasetKey);
      if (res && Array.isArray(res.proposals)) {
        const fromDb = res.proposals;
        setProposals((prev) => {
          // Empty queue must not wipe cards the Propose beat already put on screen.
          if (fromDb.length === 0 && prev.length > 0) {
            return prev;
          }
          const dbIds = new Set(fromDb.map((r) => r.rule_id));
          // DuckDB wins for every id it returns. Keep local APPROVED cards the queue omitted
          // so header Approved follows the pills after one Approve.
          const keptApproved = prev.filter(
            (r) => ruleCardStatus(r) === 'approved' && !dbIds.has(r.rule_id)
          );
          return [...fromDb, ...keptApproved];
        });
      }
    } catch {
      // keep existing cards — empty/error must not zero the header
    } finally {
      if (!silent) setLoading(false);
    }
  }, [datasetKey]);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  // Keep-mounted: first visit used to show the boot-time empty queue. Refetch when
  // shown, when Profile & Propose lands (agent-trace), and via GET poll. Never POST.
  useEffect(() => {
    if (active) void fetchRules({ silent: true });
  }, [active, fetchRules]);

  useEffect(() => {
    const onTrace = () => { void fetchRules({ silent: true }); };
    window.addEventListener('datatrust:agent-trace', onTrace);
    return () => window.removeEventListener('datatrust:agent-trace', onTrace);
  }, [fetchRules]);

  useEffect(() => {
    const id = window.setInterval(() => { void fetchRules({ silent: true }); }, 2000);
    return () => window.clearInterval(id);
  }, [fetchRules]);

  const handleApprove = async (ruleId: string) => {
    setActionLoading(ruleId);
    try {
      await hitlApi.approve(ruleId, 'human');
      setProposals((prev) =>
        prev.map((r) => (r.rule_id === ruleId ? { ...r, status: 'approved' } : r))
      );
      // DuckDB wins when include_active returns the approved row; keep the pill if queue lags.
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (ruleId: string) => {
    setActionLoading(ruleId);
    try {
      await hitlApi.reject(ruleId, 'human', 'Rejected via Quality Rules Workspace');
      setProposals((prev) =>
        prev.map((r) => (r.rule_id === ruleId ? { ...r, status: 'rejected' } : r))
      );
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchApprove = async () => {
    const pendingRules = proposals.filter((r) => ruleCardStatus(r) === 'proposed');
    if (pendingRules.length === 0) return;

    setActionLoading('batch');
    try {
      await Promise.all(
        pendingRules.map((r) =>
          hitlApi.approve(r.rule_id, 'human')
        )
      );
      setProposals((prev) =>
        prev.map((r) => ({ ...r, status: 'approved' }))
      );
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Batch approval error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingRule) return;
    setActionLoading(editingRule.rule_id);
    try {
      await hitlApi.edit(editingRule.rule_id, editExpression);
      setProposals((prev) =>
        prev.map((r) =>
          r.rule_id === editingRule.rule_id
            ? { ...r, rule_expression: editExpression, status: 'approved' }
            : r
        )
      );
      setEditingRule(null);
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Save edit error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSandboxExecute = async () => {
    const approved = proposals.filter((r) => ruleCardStatus(r) === 'approved');
    if (approved.length === 0) return;
    setActionLoading('sandbox');
    setSandboxError(null);
    try {
      const auth = await approvalsApi.authorize(datasetKey || 'vingroup_pilot', approved.map((r) => r.rule_id));
      for (const r of approved) {
        await hitlApi.execute(r.rule_id);
      }
      setPayloadHash(auth?.payload_hash || '');
      setSandboxAuthorized(true);
    } catch (err: any) {
      setSandboxError(err?.message || 'sandbox execute failed');
    } finally {
      setActionLoading(null);
    }
  };

  // Count the same cards that render (not a narrower API-status filter).
  const proposedCount = proposals.filter((r) => ruleCardStatus(r) === 'proposed').length;
  const approvedCount = proposals.filter((r) => ruleCardStatus(r) === 'approved').length;

  return (
    <div className="quality-rules-tab" style={{ padding: '4px' }}>
      {/* SUMMARY HEADER BAR */}
      <div
        className="rules-summary-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '14px',
          background: 'var(--bg-card)',
          border: '1px solid var(--glass-border)',
          borderRadius: '8px',
          padding: '10px 14px',
        }}
      >
        <div className="rules-stats-summary" style={{ display: 'flex', gap: '6px' }}>
          <span
            className="rules-stat-badge proposed"
            style={{
              background: 'rgba(217, 119, 6, 0.1)',
              color: '#d97706',
              border: '1px solid rgba(217, 119, 6, 0.25)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            {proposedCount} {isVi ? 'Đề Xuất' : 'Proposed'}
          </span>
          <span
            className="rules-stat-badge approved"
            style={{
              background: 'rgba(5, 150, 105, 0.1)',
              color: '#059669',
              border: '1px solid rgba(5, 150, 105, 0.25)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            {approvedCount} {isVi ? 'Đã Duyệt' : 'Approved'}
          </span>
        </div>

        {sandboxAuthorized && payloadHash ? (
          <span
            title={payloadHash}
            style={{
              background: 'rgba(5, 150, 105, 0.1)',
              border: '1px solid rgba(5, 150, 105, 0.25)',
              color: '#059669',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            {isVi ? 'Sandbox đã chạy · authorized' : 'Sandbox run · authorized'}{' '}
            <code>{payloadHash.length > 16 ? `${payloadHash.slice(0, 12)}…` : payloadHash}</code>
          </span>
        ) : approvedCount >= 1 ? (
          <button
            type="button"
            onClick={() => void handleSandboxExecute()}
            disabled={actionLoading === 'sandbox'}
            title="Sandbox execute"
            style={{
              background: 'rgba(2, 132, 199, 0.12)',
              border: '1px solid rgba(2, 132, 199, 0.3)',
              color: '#0284c7',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: actionLoading === 'sandbox' ? 'wait' : 'pointer',
            }}
          >
            {isVi ? 'Chạy sandbox' : 'Run sandbox'}
          </button>
        ) : (
          <button
            type="button"
            disabled
            title={isVi ? 'Execute tắt đến khi sandbox + authorize đúng version' : 'Execute stays off until sandbox + exact-version authorize'}
            style={{
              background: 'none',
              border: '1px dashed var(--glass-border)',
              color: 'var(--text-muted)',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'not-allowed',
            }}
          >
            {isVi ? 'Execute tắt · sandbox chưa chạy · quarantine=0' : 'Execute disabled · sandbox not run · quarantine=0'}
          </button>
        )}
        {sandboxError && <span role="alert" style={{ color: '#dc2626', fontSize: 11 }}>{sandboxError}</span>}
        <div className="rules-actions-right" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {proposedCount > 0 && (
            <button
              className="btn-batch-approve"
              onClick={handleBatchApprove}
              disabled={actionLoading === 'batch'}
              title={isVi ? 'Phê duyệt toàn bộ ràng buộc chất lượng được đề xuất' : 'Approve all proposed quality constraints'}
              style={{
                background: 'rgba(5, 150, 105, 0.15)',
                border: '1px solid rgba(5, 150, 105, 0.3)',
                color: '#059669',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <CheckCheck size={13} /> {isVi ? `Duyệt Tất Cả (${proposedCount})` : `Approve All (${proposedCount})`}
            </button>
          )}
          <button
            className="traces-refresh-btn"
            onClick={() => void fetchRules()}
            disabled={loading}
            title={isVi ? 'Làm mới danh sách bộ luật' : 'Refresh rules queue'}
            style={{
              background: 'none',
              border: '1px solid var(--glass-border)',
              color: 'var(--text-main)',
              borderRadius: '6px',
              padding: '6px 8px',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* RULES CARDS LIST */}
      {proposals.length === 0 ? (
        <div className="empty-panel-state" style={{ textAlign: 'center', padding: '40px 16px' }}>
          <ShieldCheck size={32} style={{ opacity: 0.3, marginBottom: 8, color: 'var(--text-muted)' }} />
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{isVi ? 'Không Có Bộ Luật Chất Lượng Nào' : 'No Active Quality Rules'}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {isVi ? 'Yêu cầu agent "đề xuất bộ luật chất lượng" hoặc chạy pipeline để tổng hợp ràng buộc.' : 'Ask the agent to "propose quality rules" or run the pipeline to synthesize constraints.'}
          </div>
        </div>
      ) : (
        <div className="rules-cards-list" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {[
            ...proposals.filter((r) => ruleCardStatus(r) === 'proposed'),
            ...proposals.filter((r) => ruleCardStatus(r) !== 'proposed'),
          ].map((rule) => {
            const cardStatus = ruleCardStatus(rule);
            const status = cardStatus;
            const isApproved = cardStatus === 'approved';
            const isRejected = cardStatus === 'rejected';
            const reasoning = getRuleReasoning(rule, isVi);

            return (
              <div
                key={rule.rule_id}
                className={`rule-card ${status}`}
                style={{
                  background: 'var(--bg-card)',
                  border: isApproved
                    ? '1px solid rgba(5, 150, 105, 0.35)'
                    : isRejected
                    ? '1px solid rgba(220, 38, 38, 0.25)'
                    : '1px solid rgba(217, 119, 6, 0.35)',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                }}
              >
                {/* RULE CARD HEADER */}
                <div className="rule-card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div className="rule-id-group" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="rule-id-tag" style={{ fontWeight: 700, fontSize: '12px', color: 'var(--text-main)' }}>
                      {rule.rule_name || rule.rule_id}
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: 'rgba(2, 132, 199, 0.08)',
                        color: '#0284c7',
                        border: '1px solid rgba(2, 132, 199, 0.2)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '3px',
                      }}
                    >
                      <Layers size={9} /> {reasoning.layer}
                    </span>
                  </div>

                  <span
                    className={`rule-status-pill ${status}`}
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '12px',
                      textTransform: 'uppercase',
                      background: isApproved ? 'rgba(5, 150, 105, 0.12)' : isRejected ? 'rgba(220, 38, 38, 0.12)' : 'rgba(217, 119, 6, 0.12)',
                      color: isApproved ? '#059669' : isRejected ? '#dc2626' : '#d97706',
                      border: isApproved ? '1px solid rgba(5, 150, 105, 0.3)' : isRejected ? '1px solid rgba(220, 38, 38, 0.3)' : '1px solid rgba(217, 119, 6, 0.3)',
                    }}
                  >
                    {status === 'approved' ? (isVi ? 'ĐÃ DUYỆT' : 'APPROVED') : status === 'rejected' ? (isVi ? 'TỪ CHỐI' : 'REJECTED') : (isVi ? 'ĐỀ XUẤT' : 'PROPOSED')}
                  </span>
                </div>

                {/* SQL / PYTHON CONSTRAINT EXPRESSION */}
                <div
                  className="rule-expression-box"
                  style={{
                    background: 'var(--bg-input, rgba(0, 0, 0, 0.03))',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '6px',
                    padding: '8px 10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '10px',
                    fontFamily: 'var(--font-mono, monospace)',
                    fontSize: '12px',
                  }}
                >
                  <Code2 size={14} style={{ color: '#0284c7', flexShrink: 0 }} />
                  <code style={{ color: '#0284c7', fontWeight: 600 }}>{rule.rule_expression}</code>
                </div>

                {/* STRUCTURED REASONING & JUSTIFICATION (WHY THE AI PROPOSED THIS RULE) */}
                <div
                  style={{
                    background: 'var(--pill-bg, rgba(0, 0, 0, 0.02))',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '8px',
                    padding: '10px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '7px',
                    fontSize: '11px',
                    lineHeight: 1.45,
                    marginBottom: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: '2px', color: '#dc2626' }} />
                    <div style={{ color: 'var(--text-main)' }}>
                      <strong style={{ color: '#dc2626' }}>{isVi ? 'Vấn Đề Phát Hiện:' : 'Problem Discovered:'} </strong>
                      {reasoning.problem}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <HelpCircle size={13} style={{ flexShrink: 0, marginTop: '2px', color: '#d97706' }} />
                    <div style={{ color: 'var(--text-main)' }}>
                      <strong style={{ color: '#d97706' }}>{isVi ? 'Lý Do AI Đề Xuất (Nguyên Nhân Gốc):' : 'Why AI Proposed This (Root Cause):'} </strong>
                      {reasoning.why}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <Sparkles size={13} style={{ flexShrink: 0, marginTop: '2px', color: '#059669' }} />
                    <div style={{ color: 'var(--text-main)' }}>
                      <strong style={{ color: '#059669' }}>{isVi ? 'Bảo Đảm Chất Lượng & Tác Động:' : 'Quality Guarantee & Impact:'} </strong>
                      {reasoning.guarantee} {reasoning.impact}
                    </div>
                  </div>
                </div>

                {/* RULE CARD FOOTER ACTIONS & CONFIDENCE */}
                <div className="rule-card-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <div className="rule-confidence-tag" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {isVi ? 'Độ Tin Cậy AI:' : 'AI Confidence:'} <strong style={{ color: '#0284c7' }}>{Math.round((rule.confidence || 0.95) * 100)}%</strong>
                  </div>

                  <div className="rule-actions-group" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {!isApproved && !isRejected && (
                      <button
                        className="btn-rule-accept"
                        onClick={() => handleApprove(rule.rule_id)}
                        disabled={actionLoading === rule.rule_id}
                        title={isVi ? 'Phê duyệt bộ luật để đưa vào biên dịch cách ly' : 'Approve rule for quarantine compilation'}
                        style={{
                          background: 'rgba(5, 150, 105, 0.12)',
                          border: '1px solid rgba(5, 150, 105, 0.3)',
                          color: '#059669',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <CheckCircle2 size={12} /> {isVi ? 'Phê Duyệt' : 'Approve'}
                      </button>
                    )}

                    {!isRejected && (
                      <button
                        className="btn-rule-edit"
                        onClick={() => {
                          setEditingRule(rule);
                          setEditExpression(rule.rule_expression);
                        }}
                        title={isVi ? 'Chỉnh sửa biểu thức SQL của bộ luật' : 'Edit SQL rule expression'}
                        style={{
                          background: 'none',
                          border: '1px solid var(--glass-border)',
                          color: 'var(--text-main)',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <Pencil size={11} /> {isVi ? 'Sửa' : 'Edit'}
                      </button>
                    )}

                    {!isRejected && !isApproved && (
                      <button
                        className="btn-rule-reject"
                        onClick={() => handleReject(rule.rule_id)}
                        disabled={actionLoading === rule.rule_id}
                        title={isVi ? 'Từ chối đề xuất bộ luật' : 'Reject rule proposal'}
                        style={{
                          background: 'rgba(220, 38, 38, 0.08)',
                          border: '1px solid rgba(220, 38, 38, 0.25)',
                          color: '#dc2626',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <XCircle size={12} /> {isVi ? 'Từ Chối' : 'Reject'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* EDIT RULE MODAL */}
      {editingRule && (
        <div className="modal-overlay active" onClick={() => setEditingRule(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">
                <Pencil size={15} style={{ marginRight: 6 }} /> {isVi ? 'Chỉnh Sửa Bộ Luật:' : 'Edit Rule:'} <code>{editingRule.rule_name || editingRule.rule_id}</code>
              </span>
              <button className="modal-close" onClick={() => setEditingRule(null)}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
              {isVi
                ? 'Chỉnh sửa biểu thức làm sạch SQL hoặc Python cho bộ luật này trước khi nạp vào động cơ thực thi.'
                : 'Modify the SQL or Python cleaning expression for this rule before signing into the execution engine.'}
            </div>
            <div className="modal-body">
              <textarea
                className="rule-edit-textarea"
                rows={4}
                value={editExpression}
                onChange={(e) => setEditExpression(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '6px',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-main)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '13px',
                }}
              />
            </div>
            <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button className="btn-modal-cancel" onClick={() => setEditingRule(null)}>{isVi ? 'Hủy' : 'Cancel'}</button>
              <button className="btn-modal-save" onClick={handleSaveEdit} disabled={actionLoading === editingRule.rule_id}>
                {isVi ? 'Lưu Biểu Thức' : 'Save Expression'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
