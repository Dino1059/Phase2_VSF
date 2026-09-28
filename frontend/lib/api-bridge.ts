/**
 * DataTrust OS: API Bridge
 * Connects Frontend UI with FastAPI Backend (/api/...) with Automatic Fallback.
 */

import type { ActiveRule, ProposedRule } from './agent-store';

const API_ROOT = '/api';

export interface BackendHealth {
  isLive: boolean;
  message: string;
}

export interface ComplianceCheckRule {
  rule_id: string;
  dataset_id: string;
  column_name: string;
  rule_name: string;
  rule_code: string;
  expression: string;
  description: string;
  law_ref: string;
  severity: string;
  on_fail_action: string;
  is_fixed: boolean;
  enforced_at: string;
}

export interface DataTreatmentRule {
  rule_id: string;
  dataset_id: string;
  column_name: string;
  operation_id: string;
  treatment_name: string;
  params_json: Record<string, any>;
  expression_display: string;
  description?: string;
  is_ai_proposed: boolean;
  ai_rationale?: string;
  ai_confidence?: number;
  status: 'active' | 'pending' | 'rejected' | 'paused';
  enforced_by: string;
  created_at: string;
  updated_at: string;
}

export const apiBridge = {
  /**
   * Kiểm tra tình trạng kết nối tới Backend FastAPI
   */
  async checkHealth(): Promise<boolean> {
    try {
      const res = await fetch(`${API_ROOT}/catalog/datasets`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(2000), // Timeout 2s để tránh treo UI
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  /**
   * Lấy danh sách Active Rules từ Backend
   */
  async fetchActiveRules(datasetId?: string): Promise<ActiveRule[]> {
    const url = datasetId
      ? `${API_ROOT}/rules/active?dataset_id=${encodeURIComponent(datasetId)}`
      : `${API_ROOT}/rules/active`;
    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp active rules`);
    const data = await res.json();
    return data.map((item: any): ActiveRule => ({
      id: item.config_id || item.id,
      name: item.expression_display || `${item.operation_id}(${item.column_name})`,
      expression: item.expression_display || `${item.operation_id}(${item.column_name})`,
      domain: (item.domain as any) || 'Privacy & Data Protection',
      datasetId: item.dataset_id,
      datasetName: item.dataset_id,
      severity: (item.severity as any) || 'HIGH',
      targetLane: item.execution_phase === 'post_check' ? 'Post-Check Quality Gate' : 'Dynamic Masking Engine',
      enforcedAt: item.enforced_at || new Date().toISOString(),
      enforcedBy: item.enforced_by || 'Admin',
      lawRef: item.law_ref || 'Quy chuẩn tuân thủ',
      scannedCount: 10382,
      quarantinedCount: 0,
      engine: 'Generic Dynamic Runner / Python',
      status: item.is_active ? 'active' : 'paused',
    }));
  },

  /**
   * Lấy danh sách Proposed Rules từ Backend
   */
  async fetchProposedRules(status?: string): Promise<ProposedRule[]> {
    const url = status
      ? `${API_ROOT}/rules/proposed?status=${encodeURIComponent(status)}`
      : `${API_ROOT}/rules/proposed`;
    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp proposed rules`);
    const data = await res.json();
    return data.map((item: any): ProposedRule => ({
      id: item.proposal_id || item.id,
      name: item.expression_display || `${item.operation_id}(${item.column_name})`,
      expression: item.expression_display || `${item.operation_id}(${item.column_name})`,
      rationale: item.rationale || 'AI Agent phân tích dựa trên Data Catalog và Policy.',
      domain: (item.domain as any) || 'Privacy & Data Protection',
      severity: (item.severity as any) || 'HIGH',
      status: item.status || 'pending',
      confidence: Math.round((item.confidence || 0.95) * 100),
      affectedRows: item.simulated_quarantine_rows || 0,
      evidenceId: `EVID-${(item.column_name || 'COL').toUpperCase()}`,
      passRows: item.simulated_pass_rows || 1000,
      quarantineRows: item.simulated_quarantine_rows || 0,
      compiledTarget: 'Dynamic Treatment Runner',
      lawRef: item.law_ref || 'Nghị định 13/2023 & GDPR',
      approvedAt: item.reviewed_at,
      approvedBy: item.reviewed_by,
    }));
  },

  /**
   * Phê duyệt Rule trên Backend (HITL - Admin only)
   */
  async approveRule(proposalId: string, actorName: string, actorRole: string): Promise<any> {
    const res = await fetch(`${API_ROOT}/rules/${encodeURIComponent(proposalId)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actor_name: actorName,
        actor_role: actorRole.toUpperCase(), // 'ADMIN' or 'AUDITOR'
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Lỗi duyệt rule HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Từ chối Rule trên Backend (Admin only)
   */
  async rejectRule(proposalId: string, actorName: string, actorRole: string, comments: string): Promise<any> {
    const res = await fetch(`${API_ROOT}/rules/${encodeURIComponent(proposalId)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actor_name: actorName,
        actor_role: actorRole.toUpperCase(),
        comments,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Lỗi từ chối rule HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Kích hoạt AI Agent đề xuất Rule từ Policy
   */
  async aiPropose(policyId: string, datasetId: string): Promise<ProposedRule[]> {
    const res = await fetch(
      `${API_ROOT}/ai/propose?policy_id=${encodeURIComponent(policyId)}&dataset_id=${encodeURIComponent(datasetId)}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}: Lỗi khi gọi AI Agent đề xuất Rule`);
    const data = await res.json();
    return data.map((item: any): ProposedRule => ({
      id: item.proposal_id,
      name: item.expression_display,
      expression: item.expression_display,
      rationale: item.rationale,
      domain: item.domain || 'Privacy & Data Protection',
      severity: item.severity || 'HIGH',
      status: 'pending',
      confidence: Math.round((item.confidence || 0.95) * 100),
      affectedRows: item.simulated_quarantine_rows || 0,
      evidenceId: `EVID-${item.column_name.toUpperCase()}`,
      passRows: item.simulated_pass_rows || 1000,
      quarantineRows: item.simulated_quarantine_rows || 0,
      compiledTarget: 'Dynamic Treatment Runner',
      lawRef: item.law_ref,
    }));
  },

  /**
   * Chạy Pipeline Run trên Bronze records
   */
  async runPipeline(datasetId: string, bronzeRecords: any[]): Promise<any> {
    const res = await fetch(`${API_ROOT}/pipeline/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: datasetId,
        bronze_records: bronzeRecords,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Lỗi thực thi pipeline`);
    return res.json();
  },

  /**
   * Lấy danh sách Quarantine Records
   */
  async fetchQuarantine(): Promise<any[]> {
    const res = await fetch(`${API_ROOT}/quarantine`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp quarantine`);
    return res.json();
  },

  /**
   * Lấy Audit Trail bất biến
   */
  async fetchAuditTrail(): Promise<any[]> {
    const res = await fetch(`${API_ROOT}/audit-trail`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp audit trail`);
    return res.json();
  },

  /**
   * Kiểm tra trạng thái Apache Airflow
   */
  async checkAirflowStatus(): Promise<{ is_live: boolean; status: string; dag_id?: string }> {
    try {
      const res = await fetch(`${API_ROOT}/airflow/status`, { signal: AbortSignal.timeout(2000) });
      if (!res.ok) return { is_live: false, status: 'offline' };
      return res.json();
    } catch {
      return { is_live: false, status: 'unreachable' };
    }
  },

  /**
   * Kích hoạt Airflow DAG datatrust_adaptive_pipeline qua Backend
   */
  async triggerAirflow(datasetId: string = 'ride_hailing_xanh_sm_trips.csv'): Promise<any> {
    const res = await fetch(`${API_ROOT}/airflow/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dag_id: 'datatrust_adaptive_pipeline',
        dataset_id: datasetId,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Lỗi khi kích hoạt Airflow pipeline`);
    return res.json();
  },

  /**
   * Xem trước 20-50 dòng dữ liệu thực tế từ file CSV
   */
  async fetchDatasetPreview(datasetId: string, limit: number = 20): Promise<{
    dataset_id: string;
    filename: string;
    columns: string[];
    rows: any[];
    total_records: number;
    limit: number;
  }> {
    const res = await fetch(`${API_ROOT}/datasets/${encodeURIComponent(datasetId)}/preview?limit=${limit}`, {
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp preview dữ liệu`);
    return res.json();
  },

  /**
   * Lấy thông số phân tích thực tế (3 phân vùng VN/EU/US)
   */
  async fetchDatasetStats(datasetId: string): Promise<any> {
    const res = await fetch(`${API_ROOT}/datasets/${encodeURIComponent(datasetId)}/stats`, {
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp thông số dataset`);
    return res.json();
  },

  /**
   * Lấy danh sách các lần chạy pipeline từ Airflow
   */
  async fetchLivePipelineRuns(): Promise<any[]> {
    const res = await fetch(`${API_ROOT}/runs`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp lịch sử runs`);
    return res.json();
  },

  /**
   * Lấy danh sách Compliance Check Rules (Cố định, Read-Only, AI không có quyền đề xuất)
   */
  async fetchComplianceCheckRules(datasetId?: string): Promise<ComplianceCheckRule[]> {
    const url = datasetId
      ? `${API_ROOT}/rules/compliance-checks?dataset_id=${encodeURIComponent(datasetId)}`
      : `${API_ROOT}/rules/compliance-checks`;
    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp compliance check rules`);
    return res.json();
  },

  /**
   * Lấy danh sách Data Treatment Rules (Xử lý dữ liệu chung, AI đề xuất note riêng)
   */
  async fetchDataTreatmentRules(datasetId?: string, status?: string): Promise<DataTreatmentRule[]> {
    let url = `${API_ROOT}/rules/treatments`;
    const params = new URLSearchParams();
    if (datasetId) params.append('dataset_id', datasetId);
    if (status) params.append('status', status);
    if (params.toString()) url += `?${params.toString()}`;

    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Không thể nạp data treatment rules`);
    return res.json();
  },

  /**
   * Cập nhật biểu thức xử lý trên UI (Admin)
   */
  async updateTreatmentRuleExpression(
    ruleId: string,
    expressionDisplay: string,
    paramsJson?: Record<string, any>,
    description?: string
  ): Promise<DataTreatmentRule> {
    const res = await fetch(`${API_ROOT}/rules/treatments/${encodeURIComponent(ruleId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        expression_display: expressionDisplay,
        params_json: paramsJson,
        description: description,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Lỗi cập nhật biểu thức rule HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Duyệt rule xử lý do AI đề xuất -> chuyển thành Active
   */
  async approveTreatmentRule(
    ruleId: string,
    actorName: string,
    actorRole: string
  ): Promise<DataTreatmentRule> {
    const res = await fetch(`${API_ROOT}/rules/treatments/${encodeURIComponent(ruleId)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actor_name: actorName,
        actor_role: actorRole.toUpperCase(),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Lỗi duyệt rule HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Từ chối rule xử lý do AI đề xuất -> chuyển thành Rejected
   */
  async rejectTreatmentRule(
    ruleId: string,
    actorName: string,
    actorRole: string,
    comments?: string
  ): Promise<DataTreatmentRule> {
    const res = await fetch(`${API_ROOT}/rules/treatments/${encodeURIComponent(ruleId)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actor_name: actorName,
        actor_role: actorRole.toUpperCase(),
        comments,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Lỗi từ chối rule HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Bật / Tạm dừng rule xử lý
   */
  async toggleTreatmentRule(ruleId: string): Promise<DataTreatmentRule> {
    const res = await fetch(`${API_ROOT}/rules/treatments/${encodeURIComponent(ruleId)}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Lỗi toggle rule HTTP ${res.status}`);
    }
    return res.json();
  },
};
