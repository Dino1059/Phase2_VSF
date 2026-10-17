import { describe, it, expect } from 'vitest';
import { formatWarningExplanation } from '../lib/formatters/audit-warning-formatter';

describe('Audit Warning Formatter (Two-Layer Architecture)', () => {
  it('correctly parses user changepoint shift warning and separates Business from Technical details', () => {
    const rawReason =
      'WINDOW Observation in changepoint transition window; change_time=2026-01-01T13:05:00+00:00; change_magnitude=-20.3849; pre_window_mean=26.3932; pre_window_std=3.6042; pre_window_count=5; post_window_mean=6.0083; post_window_std=4.1473; post_window_count=3; pelt_penalty=3.0; shift_direction=DOWN; Jurisdiction chain resolved: GLOBAL -> EU';

    const report = formatWarningExplanation({
      warning_id: 'w-test-01',
      warning_type: 'CHANGEPOINT_SHIFT',
      signal_layer: 'L4',
      warning_reason: rawReason,
      redacted_record_json: { trip_distance_km: 13.679 },
    });

    // 1. Business Layer: Metric identified
    expect(report.business.metricName).toBe('Quãng đường di chuyển');
    expect(report.business.metricField).toBe('trip_distance_km');
    expect(report.business.unit).toBe('km');

    // 2. Change summary
    expect(report.business.changeSummary).toContain('giảm từ 26.39 km xuống 6.01 km');
    expect(report.business.percentChangeStr).toBe('77.2%');
    expect(report.business.isIncrease).toBe(false);

    // 3. Sample size warning (3 post-observations)
    expect(report.business.isSmallSample).toBe(true);
    expect(report.business.sampleSizeEvaluation).toContain('Cỡ mẫu quan sát còn nhỏ (5 quan sát trước và 3 quan sát sau');
    expect(report.business.sampleSizeEvaluation).toContain('Chưa đủ cơ sở thống kê để khẳng định');

    // 4. Actionable next steps
    expect(report.business.recommendedAction).toContain('Đối soát với bản đồ hành trình GPS');

    // 5. Technical Layer: Debug parameters isolated
    expect(report.technical.peltPenalty).toBe(3.0);
    expect(report.technical.changeMagnitude).toBe(-20.3849);
    expect(report.technical.preMean).toBe(26.3932);
    expect(report.technical.postMean).toBe(6.0083);
    expect(report.technical.preCount).toBe(5);
    expect(report.technical.postCount).toBe(3);

    // 6. Exclude noise
    expect(report.technical.cleanedReason).not.toContain('Jurisdiction chain');
    expect(report.technical.cleanedReason).not.toContain('GLOBAL ->');
  });

  it('correctly handles battery temperature metric', () => {
    const rawReason =
      'change_time=2026-01-01T10:00:00+00:00; pre_window_mean=32.5; post_window_mean=48.2; pre_window_count=4; post_window_count=4;';

    const report = formatWarningExplanation({
      warning_id: 'w-battery-01',
      warning_type: 'CHANGEPOINT_PELT',
      warning_reason: rawReason,
      redacted_record_json: { battery_temp_c: 48.0 },
    });

    expect(report.business.metricName).toBe('Nhiệt độ cụm pin xe điện');
    expect(report.business.unit).toBe('°C');
    expect(report.business.isIncrease).toBe(true);
    expect(report.business.recommendedAction).toContain('BMS');
  });
});
