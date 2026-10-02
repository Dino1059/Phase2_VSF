import type { FindingSeverity, FindingState } from './dashboard-types';
import type { FindingDetail, FindingListItem, FindingsDataSource } from './findings-types';
import { apiBridge } from '../api-bridge';

export class LocalCsvFindingsDataSource implements FindingsDataSource {
  async listFindings(): Promise<FindingListItem[]> {
    try {
      const [quarRes, warnRes] = await Promise.all([
        apiBridge.fetchQuarantineRecords({ limit: 100 }).catch(() => ({ records: [] })),
        apiBridge.fetchWarningRecords({ limit: 100 }).catch(() => ({ records: [] })),
      ]);

      const items: FindingListItem[] = [];

      for (const q of quarRes.records || []) {
        items.push({
          id: q.quarantine_id,
          title: `Vi phạm cách ly: ${q.violation_reason || q.violation_column}`,
          domain: 'Data Integrity & Privacy',
          severity: (q.violation_severity || 'HIGH').toUpperCase() as FindingSeverity,
          status: (q.status === 'REMEDIATED' ? 'CLOSED' : 'OPEN') as FindingState,
          createdAt: q.quarantined_at || new Date().toISOString(),
        });
      }

      for (const w of warnRes.records || []) {
        items.push({
          id: w.warning_id,
          title: `Cảnh báo thống kê: ${w.warning_reason || w.signal_layer || w.warning_type}`,
          domain: 'Statistical Quality',
          severity: 'MEDIUM' as FindingSeverity,
          status: 'OPEN' as FindingState,
          createdAt: w.detected_at || new Date().toISOString(),
        });
      }

      return items;
    } catch (e) {
      console.warn('Failed to load findings from database:', e);
      return [];
    }
  }

  async getFinding(id: string): Promise<FindingDetail | null> {
    try {
      const quarRes = await apiBridge.fetchQuarantineRecords({ limit: 100 }).catch(() => ({ records: [] }));
      const q = quarRes.records.find((r) => r.quarantine_id === id);

      if (q) {
        return {
          id: q.quarantine_id,
          title: `Vi phạm cách ly: ${q.violation_reason}`,
          domain: 'Data Integrity & Privacy',
          severity: (q.violation_severity || 'CRITICAL').toUpperCase() as FindingSeverity,
          status: (q.status === 'REMEDIATED' ? 'CLOSED' : 'OPEN') as FindingState,
          createdAt: q.quarantined_at || new Date().toISOString(),
          assignedTo: q.resolved_by || 'Nguyễn Quốc Bảo (Lead Platform)',
          control: {
            id: q.violation_rule_id || 'CTRL-QUAR',
            name: `Quy tắc kiểm soát: ${q.violation_column || 'Toàn vẹn'}`,
            evaluationMessage: q.violation_reason,
            evaluatedAt: q.quarantined_at || new Date().toISOString(),
          },
          issueDescription: `Bản ghi thuộc bộ dữ liệu ${q.dataset_id} vi phạm tính toàn vẹn tại làn ${q.failure_lane}. Đã cách ly an toàn khỏi phân vùng Silver.`,
          impact: 'Dữ liệu vi phạm không được ghi vào tầng báo cáo tài chính/BI cho đến khi khắc phục.',
          recommendedActions: [
            'Kiểm tra lại dữ liệu nguồn tại trạm thu thập',
            'Sử dụng công cụ xử lý tự động (Data Treatment Rules) để chuẩn hóa hoặc ẩn danh dữ liệu',
            'Liên hệ Lead Platform nếu cần ngoại lệ kiểm toán'
          ],
          history: [
            {
              label: 'Bản ghi bị cách ly',
              detail: q.violation_reason,
              occurredAt: q.quarantined_at || new Date().toISOString(),
              tone: 'amber',
            },
            ...(q.status === 'REMEDIATED' ? [{
              label: 'Khắc phục hoàn tất',
              detail: `Bản ghi được xử lý bởi ${q.resolved_by || 'Admin'}`,
              occurredAt: q.resolved_at || new Date().toISOString(),
              tone: 'green' as const,
            }] : []),
          ],
          related: [],
          evidence: [
            {
              id: q.lineage_hash?.slice(0, 16) || q.quarantine_id,
              type: 'Quarantine Raw Payload',
              source: 'PostgreSQL quarantine.records',
              capturedAt: q.quarantined_at || new Date().toISOString(),
              actor: 'Airflow Pipeline Task 3',
              linkedObject: q.source_row_pk || q.quarantine_id,
              reference: `Lineage Hash: ${q.lineage_hash}`,
              controlResultId: q.violation_rule_id || 'QUAR-01',
              rawEvent: q.raw_record_json,
            },
          ],
        };
      }

      // Check warning records
      const warnRes = await apiBridge.fetchWarningRecords({ limit: 100 }).catch(() => ({ records: [] }));
      const w = warnRes.records.find((r) => r.warning_id === id);
      if (w) {
        return {
          id: w.warning_id,
          title: `Cảnh báo thống kê: ${w.warning_reason}`,
          domain: 'Statistical Quality',
          severity: 'MEDIUM' as FindingSeverity,
          status: 'OPEN' as FindingState,
          createdAt: w.detected_at || new Date().toISOString(),
          assignedTo: 'Hệ thống tự động',
          control: {
            id: w.warning_type || w.signal_layer || 'WARN-CTRL',
            name: `Tín hiệu ${w.signal_layer || w.signal_lane}`,
            evaluationMessage: w.warning_reason,
            evaluatedAt: w.detected_at || new Date().toISOString(),
          },
          issueDescription: `Phát hiện dị thường tại tầng ${w.signal_layer || w.signal_lane} trong tập dữ liệu ${w.dataset_id}.`,
          impact: 'Bản ghi vẫn được chuyển tiếp vào Silver nhưng kèm nhãn cảnh báo để giám sát phân tích.',
          recommendedActions: [
            'Kiểm tra độ lệch phân phối (Z-score/drift)',
            'Điều chỉnh ngưỡng cảnh báo nếu phân phối thực tế dịch chuyển hợp lệ'
          ],
          history: [
            {
              label: 'Phát hiện tín hiệu cảnh báo',
              detail: w.warning_reason,
              occurredAt: w.detected_at || new Date().toISOString(),
              tone: 'amber',
            },
          ],
          related: [],
          evidence: [
            {
              id: w.lineage_hash?.slice(0, 16) || w.warning_id,
              type: 'Statistical Outlier / Drift Metric',
              source: 'PostgreSQL warning.records',
              capturedAt: w.detected_at || new Date().toISOString(),
              actor: 'Airflow Pipeline Task 3A',
              linkedObject: w.warning_id,
              reference: `Lineage Hash: ${w.lineage_hash}`,
              controlResultId: w.warning_type || 'WARN-01',
              rawEvent: w.evidence_json,
            },
          ],
        };
      }
    } catch (e) {
      console.warn('Failed to get finding detail:', e);
    }
    return null;
  }
}

export const findingsDataSource: FindingsDataSource = new LocalCsvFindingsDataSource();
