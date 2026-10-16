import { describe, it, expect } from 'vitest';
import {
  formatAuditReasonReport,
  formatAuditReasonSummary,
} from '../lib/formatters/audit-violation-formatter';

describe('Audit Violation Formatter & Normalizer', () => {
  const sampleRawLog =
    'fare_amount (-24573.0) < min_val (1e-06); observed_value=-24573.0; invalid input type; customer_id was not hashed according to policy; driver_id was not hashed according to policy; customer_id was not hashed according to policy; pickup_latitude exceeds permitted coordinate precision (2 decimals); pickup_longitude exceeds permitted coordinate precision (2 decimals); vehicle_vin was not hashed according to policy; invalid input type';

  it('deduplicates repetitive errors like customer_id was not hashed and invalid input type', () => {
    const report = formatAuditReasonReport(sampleRawLog);

    // customer_id not hashed should only appear ONCE
    const custIdViolations = report.items.filter((i) => i.field === 'customer_id');
    expect(custIdViolations.length).toBe(1);

    // invalid input type should only appear ONCE
    const typeViolations = report.items.filter((i) => i.field === 'data_integrity');
    expect(typeViolations.length).toBe(1);
  });

  it('correctly categorizes violations into Quality, Privacy, and Location', () => {
    const report = formatAuditReasonReport(sampleRawLog);

    expect(report.byCategory.quality.length).toBeGreaterThan(0);
    expect(report.byCategory.privacy.length).toBeGreaterThan(0);
    expect(report.byCategory.location.length).toBeGreaterThan(0);

    // Verify Quality item
    const qualityItem = report.byCategory.quality.find((i) => i.field === 'fare_amount');
    expect(qualityItem).toBeDefined();
    expect(qualityItem?.title).toContain('Giá cước chuyến đi không hợp lệ');
    expect(qualityItem?.observedValue).toBe('-24573.0 VNĐ');
    expect(qualityItem?.legalBasis).toContain('IFRS 15');
    expect(qualityItem?.severity).toBe('CRITICAL');

    // Verify Privacy item
    const privacyCust = report.byCategory.privacy.find((i) => i.field === 'customer_id');
    expect(privacyCust).toBeDefined();
    expect(privacyCust?.title).toContain('băm ẩn danh');
    expect(privacyCust?.detectionPhase).toBe('POST_TREATMENT');

    // Verify Location item
    const locItem = report.byCategory.location.find((i) => i.field === 'pickup_latitude');
    expect(locItem).toBeDefined();
    expect(locItem?.title).toContain('Tọa độ GPS vĩ độ vượt quá độ chính xác cho phép');
    expect(locItem?.thresholdOrStandard).toContain('Làm tròn tối đa 2 chữ số thập phân');
  });

  it('builds executive summary answering the 3 core auditor questions', () => {
    const report = formatAuditReasonReport(sampleRawLog);

    expect(report.executiveSummary.whatViolated).toContain('lỗi chất lượng/sổ cái');
    expect(report.executiveSummary.whatViolated).toContain('lỗi bảo vệ danh tính PII');
    expect(report.executiveSummary.whatViolated).toContain('vi phạm vị trí');
    expect(report.executiveSummary.whyFlagged).toContain('CRITICAL');
    expect(report.executiveSummary.containmentStatus).toContain('TOÀN BỘ ĐÃ ĐƯỢC CÁCH LY AN TOÀN');
    expect(report.executiveSummary.isFullyContained).toBe(true);
  });

  it('generates concise business summary for table display', () => {
    const summary = formatAuditReasonSummary(sampleRawLog);
    expect(summary).toContain('Giá cước chuyến đi không hợp lệ');
    expect(summary).not.toContain('min_val');
  });
});
