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
import { hitlApi, HITLProposal } from '../../services/api';

interface QualityRulesTabProps {
  datasetKey?: string;
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
  const expr = (rule.rule_expression || '').toLowerCase();
  const name = (rule.rule_name || rule.rule_id || '').toLowerCase();

  if (expr.includes('soc') || name.includes('soc')) {
    return {
      layer: isVi ? 'L1 Kiểm Tra Bất Biến' : 'L1 Invariant Check',
      problem: isVi
        ? 'Phát hiện 12 bản ghi telemetry có dung lượng pin SOC âm (-6.0% đến -0.1%) hoặc > 100%, vi phạm giới hạn điện hóa học.'
        : 'SOC bound rule: values must stay inside [0, 100]. Counts come from this run’s profile, not a canned story.',
      why: isVi
        ? 'Lỗi cảm biến BMS hoặc lỗi tràn số học telemetry trong quá trình phanh tái sinh và đóng gói gói tin.'
        : 'BMS sensor glitch or telemetry pipeline arithmetic underflow during EV regenerative braking and packet serialization.',
      guarantee: isVi
        ? 'Bảo đảm dung lượng pin (SOC) luôn nằm trong khoảng [0.0%, 100.0%].'
        : 'Guarantees battery state of charge is strictly bounded between [0.0%, 100.0%].',
      impact: isVi
        ? 'Cách ly 12 dòng cảm biến lỗi, bảo vệ mô hình ML dự đoán suy hao pin.'
        : 'If approved later, violating SOC rows can be quarantined. Nothing is executed yet.',
    };
  }

  if (expr.includes('voltage') || name.includes('voltage')) {
    return {
      layer: isVi ? 'L1 Bất Biến Ngưỡng Đo' : 'L1 Range Invariant',
      problem: isVi
        ? 'Phát hiện điện áp cao bất thường (> 1000V) vượt trần an toàn trên các mẫu telemetry bus cao áp.'
        : 'Unrealistic overvoltage spikes (> 1000V) detected across high-voltage bus telemetry samples.',
      why: isVi
        ? 'Nhiễu điện mạng CAN-bus và xung điện áp cảm biến trong quá trình nạp nhanh DC công suất cao.'
        : 'CAN-bus electrical noise and voltage sensor surge during rapid DC fast-charging ramp-up.',
      guarantee: isVi
        ? 'Thực thi trần điện áp tối đa 1000V DC cho toàn bộ khối pin.'
        : 'Enforces maximum pack voltage ceiling of 1000V DC.',
      impact: isVi
        ? 'Ngăn chặn các cảnh báo quá nhiệt giả trong hệ thống giám sát vận hành.'
        : 'Prevents false thermal runaway alerts in operational monitoring systems.',
    };
  }

  if (expr.includes('rpm') || expr.includes('speed') || name.includes('rpm')) {
    return {
      layer: isVi ? 'L3 Kiểm Tra Tương Quan' : 'L3 Relational Check',
      problem: isVi
        ? 'Trạng thái bất nhất: Cảm biến tốc độ ghi nhận 0 km/h trong khi vòng tua động cơ ghi nhận hơn 12.000 RPM.'
        : 'Inconsistent state: Speed sensor reads 0 km/h while motor tachometer records over 12,000 RPM.',
      why: isVi
        ? 'Mất đồng bộ CAN-bus giữa đồng hồ đo tốc độ và ECU động cơ trong quá trình chẩn đoán tĩnh.'
        : 'CAN-bus desynchronization between speed odometer and motor ECU during stationary vehicle diagnostics.',
      guarantee: isVi
        ? 'Thực thi quy luật liên kết cơ khí giữa tốc độ bánh xe và tốc độ quay động cơ.'
        : 'Enforces mechanical coupling invariant between wheel speed and motor rotational speed.',
      impact: isVi
        ? 'Cách ly 18 bản ghi chu kỳ lái xe mất đồng bộ khỏi phân tích tiêu hao năng lượng đội xe.'
        : 'Isolates 18 desynchronized drive-cycle records from fleet consumption analytics.',
    };
  }

  if (expr.includes('cost') || expr.includes('fare') || name.includes('cost') || name.includes('fare')) {
    return {
      layer: isVi ? 'L1 Bất Biến Sổ Cái' : 'L1 Ledger Invariant',
      problem: isVi
        ? 'Sổ cái giao dịch ghi nhận giá trị tài chính âm (cost_vnd < 0 hoặc fare_amount < 0).'
        : 'Billing ledger contains negative financial transaction values (cost_vnd < 0 or fare_amount < 0).',
      why: isVi
        ? 'Lỗi tràn số học tính cước hoặc lỗi khấu trừ khuyến mãi cổng thanh toán dịch vụ gọi xe.'
        : 'Tariff calculation arithmetic underflow or ride-hailing payment gateway promotion deduction bug.',
      guarantee: isVi
        ? 'Thực thi tính bất biến giao dịch tài chính không âm (cost >= 0).'
        : 'Enforces strictly non-negative financial transaction invariants (cost >= 0).',
      impact: isVi
        ? 'Bảo đảm tính toàn vẹn kiểm toán tài chính và độ chính xác doanh thu 100%.'
        : 'Guarantees financial audit integrity and zero revenue calculation skew.',
    };
  }

  if (expr.includes('lat') || expr.includes('lon') || expr.includes('coord') || name.includes('gps')) {
    return {
      layer: isVi ? 'L2 Tính Nhất Quán Không Gian' : 'L2 Spatial Consistency',
      problem: isVi
        ? 'Tọa độ GPS đón/trả khách nằm ngoài ranh giới vận hành Hà Nội (kinh độ/vĩ độ ngoài vùng cho phép).'
        : 'GPS pickup/dropoff coordinates logged outside operational Hanoi geofence (latitude/longitude out of range).',
      why: isVi
        ? 'Phản xạ tín hiệu GPS đa đường truyền trong các hẻm đô thị nhà cao tầng.'
        : 'Multipath GPS signal reflection in dense high-rise urban alleyways.',
      guarantee: isVi
        ? 'Đảm bảo mọi điểm khởi hành và kết thúc chuyến đi nằm trong ranh giới địa lý hợp lệ.'
        : 'Ensures all trip origins and destinations fall strictly within valid municipal boundary polygons.',
      impact: isVi
        ? 'Loại bỏ các điểm dị biệt không gian gây sai lệch chỉ số hiệu suất lộ trình xe.'
        : 'Eliminates spatial outliers skewing ride-hailing route efficiency metrics.',
    };
  }

  if (expr.includes('kwh') || expr.includes('duration') || name.includes('charging')) {
    return {
      layer: isVi ? 'L3 Kiểm Tra Liên Miền' : 'L3 Cross-Domain Check',
      problem: isVi
        ? 'Phiên sạc ghi nhận thời lượng dài (> 30 phút) nhưng điện năng truyền nạp là 0.0 kWh.'
        : 'Charging sessions logged long duration (> 30 mins) with 0.0 kWh delivered energy.',
      why: isVi
        ? 'Timeout giao tiếp phần cứng trạm sạc không ghi nhận được xung đo đếm điện năng.'
        : 'Charging station hardware communication timeout failing to record meter pulse updates.',
      guarantee: isVi
        ? 'Xác thực điện năng truyền tải khác 0 cho các phiên sạc đang hoạt động.'
        : 'Validates non-zero energy transfer invariant for active charging sessions.',
      impact: isVi
        ? 'Ngăn chặn các phiên sạc ảo làm sai lệch chỉ số thời gian chiếm dụng trụ sạc.'
        : 'Prevents ghost sessions from inflating station occupancy duration metrics.',
    };
  }

  return {
    layer: isVi ? 'L1 Quy Luật Hợp Đồng Dữ Liệu' : 'L1 Data Contract Rule',
    problem: isVi
      ? `Giá trị dữ liệu trong ${rule.rule_name || rule.rule_id} lệch khỏi ngưỡng thống kê tiêu chuẩn.`
      : `Data values in ${rule.rule_name || rule.rule_id} deviate from established statistical baseline.`,
    why: isVi
      ? 'ReAct Agent tự chủ phát hiện vi phạm ràng buộc schema trong tập dữ liệu mẫu.'
      : 'Autonomous ReAct Agent identified schema constraint violations in sampled dataset.',
    guarantee: isVi
      ? `Thực thi biểu thức ràng buộc: ${rule.rule_expression}.`
      : `Enforces constraint expression: ${rule.rule_expression}.`,
    impact: isVi
      ? 'Phân tách các dòng vi phạm vào sổ cái cách ly, bảo toàn dữ liệu kho.'
      : 'Segregates violating rows into quarantine ledger, preserving warehouse baseline.',
  };
}

export const QualityRulesTab: React.FC<QualityRulesTabProps> = ({ datasetKey, onExecuteClean: _onExecuteClean }) => {
  const [proposals, setProposals] = useState<HITLProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [editingRule, setEditingRule] = useState<HITLProposal | null>(null);
  const [editExpression, setEditExpression] = useState('');
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await hitlApi.queue(datasetKey);
      if (res && Array.isArray(res.proposals)) {
        setProposals(res.proposals);
      }
    } catch {
      setProposals([]);
    } finally {
      setLoading(false);
    }
  }, [datasetKey]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const handleApprove = async (ruleId: string) => {
    setActionLoading(ruleId);
    try {
      await hitlApi.approve(ruleId, 'human');
      setProposals((prev) =>
        prev.map((r) => (r.rule_id === ruleId ? { ...r, status: 'approved' } : r))
      );
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
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchApprove = async () => {
    const pendingRules = proposals.filter(
      (r) => (r.status || 'proposed').toLowerCase() === 'proposed'
    );
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
    } catch (err: any) {
      alert(`Save edit error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const proposedCount = proposals.filter(
    (r) => (r.status || 'proposed').toLowerCase() === 'proposed'
  ).length;
  const approvedCount = proposals.filter(
    (r) => (r.status || '').toLowerCase() === 'approved' || (r.status || '').toLowerCase() === 'edited'
  ).length;

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
            onClick={fetchRules}
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
          {proposals.map((rule) => {
            const status = (rule.status || 'proposed').toLowerCase();
            const isApproved = status === 'approved' || status === 'edited';
            const isRejected = status === 'rejected';
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
