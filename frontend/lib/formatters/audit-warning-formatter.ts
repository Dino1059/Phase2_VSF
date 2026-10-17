/**
 * AUDIT WARNING FORMATTER & NORMALIZER (TWO-LAYER ARCHITECTURE)
 * ============================================================================
 * Chuẩn hóa các cảnh báo thống kê (L2 Robust Drift, L3 Relational, L4 Changepoint)
 * thành Báo cáo Kiểm toán 2 lớp chuẩn mực cho Auditor:
 *
 * Lớp 1 - Business Explanation (Mặc định):
 *   1. Chỉ số nào thay đổi (Quãng đường, Nhiệt độ pin, Dung lượng pin, Cước phí...).
 *   2. Mức thay đổi & thời điểm (Giá trị trước -> sau, % tăng/giảm, thời gian).
 *   3. Ngữ cảnh nghiệp vụ thực tế (Hành vi xe, ca vận hành, pin, thời tiết...).
 *   4. Đánh giá cỡ mẫu (Cảnh báo mẫu ngắn 3/3, chưa đủ cơ sở khẳng định xu hướng bền vững).
 *   5. Hướng kiểm tra cụ thể tiếp theo cho Auditor (Actionable next steps).
 *   6. Loại bỏ nhiễu kỹ thuật không liên quan (GLOBAL -> EU/VN, ANCHOR...).
 *
 * Lớp 2 - Technical Details (Mở rộng / Collapsible):
 *   pre_window_summary, post_window_summary, pelt_penalty, change_magnitude, std, debug info.
 * ============================================================================
 */

export interface WarningRecordLike {
  warning_id: string;
  warning_type?: string;
  signal_layer?: string;
  signal_lane?: string;
  warning_reason?: string | null;
  score_or_zvalue?: number | null;
  dataset_id?: string;
  source_row_pk?: string;
  evidence_json?: any;
  redacted_record_json?: any;
  detected_at?: string;
}

export interface WarningMetricInfo {
  nameVi: string;
  field: string;
  unit: string;
  businessContext: string;
  actionVi: string;
}

export interface FormattedWarningExplanation {
  // Layer 1: Business Explanation (Mặc định cho Auditor)
  business: {
    metricName: string;
    metricField: string;
    unit: string;
    changeSummary: string;
    preValueStr: string;
    postValueStr: string;
    percentChangeStr: string;
    isIncrease: boolean;
    detectedTime: string;
    businessMeaning: string;
    sampleSizeEvaluation: string;
    isSmallSample: boolean;
    preCount: number | null;
    postCount: number | null;
    recommendedAction: string;
    conciseSummary: string;
  };

  // Layer 2: Technical Details (Mở rộng)
  technical: {
    algorithm: string;
    changeMagnitude: number | null;
    peltPenalty: number | null;
    preMean: number | null;
    preStd: number | null;
    preCount: number | null;
    postMean: number | null;
    postStd: number | null;
    postCount: number | null;
    preSummaryJson: any | null;
    postSummaryJson: any | null;
    rawEvidenceItems: string[];
    cleanedReason: string;
  };
}

const METRIC_CATALOG: Record<string, WarningMetricInfo> = {
  trip_distance_km: {
    nameVi: 'Quãng đường di chuyển',
    field: 'trip_distance_km',
    unit: 'km',
    businessContext: 'Ghi nhận bước nhảy cự ly chuyến đi trung bình của xe. Hiện tượng này thường xảy ra khi xe chuyển địa bàn hoạt động (từ ngoại thành cự ly dài sang nội đô cự ly ngắn), chuyển đổi tài xế/ca làm việc, hoặc cảm biến GPS gặp sự cố mất tín hiệu ngắt quãng.',
    actionVi: 'Đối soát với bản đồ hành trình GPS chi tiết của xe và các chuyến đi liền kề trong cùng khung giờ để xác nhận cự ly thực tế trước khi xác nhận bất thường.',
  },
  battery_temp_c: {
    nameVi: 'Nhiệt độ cụm pin xe điện',
    field: 'battery_temp_c',
    unit: '°C',
    businessContext: 'Nhiệt độ cell pin xe điện dịch chuyển đột ngột ngoài dải ổn định thông thường. Có thể do xe vừa thực hiện sạc nhanh DC công suất lớn, vận hành liên tục dưới tải cao, hoặc hệ thống tản nhiệt làm mát pin BMS bị suy giảm hiệu suất.',
    actionVi: 'Yêu cầu kỹ thuật viên BMS trích xuất log nhiệt độ chi tiết từng module pin và kiểm tra cảnh báo quá nhiệt tại thời điểm ghi nhận.',
  },
  battery_soc: {
    nameVi: 'Dung lượng pin khả dụng (SoC)',
    field: 'battery_soc',
    unit: '%',
    businessContext: 'Mức dung lượng pin khả dụng sụt giảm bất thường không tương xứng với quãng đường lăn bánh thực tế.',
    actionVi: 'Kiểm tra chu kỳ sạc/xả gần nhất và xác minh trạng thái suy hao pin (SOH) của phương tiện.',
  },
  fare_amount: {
    nameVi: 'Giá cước chuyến đi',
    field: 'fare_amount',
    unit: 'VND',
    businessContext: 'Giá cước bình quân của nhóm chuyến xe dịch chuyển lớn so với mức nền. Cần đánh giá xem có áp dụng mã khuyến mại, thay đổi biểu giá giờ cao điểm hoặc lỗi làm tròn công thức tính cước.',
    actionVi: 'Kiểm tra chính sách giá cước áp dụng tại thời điểm chuyến đi và đối soát bảng kê thu hộ / thanh toán ví.',
  },
  total_fare: {
    nameVi: 'Tổng cước phí sổ cái',
    field: 'total_fare',
    unit: 'VND',
    businessContext: 'Tổng cước phí sổ cái kế toán ghi nhận thay đổi đáng kể giữa các chu kỳ đo kiểm.',
    actionVi: 'Đối chiếu chéo giữa dữ liệu cước đo lường thực tế (fare_amount + tips + phụ phí) với số liệu ghi nhận trên cổng thanh toán.',
  },
  motor_rpm: {
    nameVi: 'Vòng tua động cơ xe điện',
    field: 'motor_rpm',
    unit: 'RPM',
    businessContext: 'Vòng tua động cơ xe ghi nhận bước nhảy lệch pha so với dải tốc độ vận hành bình thường.',
    actionVi: 'Đối soát dữ liệu CAN bus động cơ và kiểm tra cảm biến tốc độ trục quay.',
  },
};

/**
 * Phân tích và chuyển đổi warning_reason kỹ thuật thô thành Báo cáo 2 lớp cho Auditor
 */
export function formatWarningExplanation(w: WarningRecordLike): FormattedWarningExplanation {
  const reason = w.warning_reason || '';
  const evidenceList: string[] = Array.isArray(w.evidence_json?.evidence)
    ? w.evidence_json.evidence
    : [];

  // Trích xuất các tham số từ text
  const matchValue = (pattern: RegExp): string | null => {
    const m = reason.match(pattern);
    if (m) return m[1];
    for (const ev of evidenceList) {
      const em = ev.match(pattern);
      if (em) return em[1];
    }
    return null;
  };

  const preMeanStr = matchValue(/pre_window_mean=([-\d.]+)/);
  const postMeanStr = matchValue(/post_window_mean=([-\d.]+)/);
  const preStdStr = matchValue(/pre_window_std=([-\d.]+)/);
  const postStdStr = matchValue(/post_window_std=([-\d.]+)/);
  const preCountStr = matchValue(/pre_window_count=(\d+)/);
  const postCountStr = matchValue(/post_window_count=(\d+)/);
  const changeMagStr = matchValue(/change_magnitude=([-\d.]+)/);
  const peltPenStr = matchValue(/pelt_penalty=([-\d.]+)/);
  const changeTimeStr = matchValue(/change_time=([^;]+)/);

  // Parse số
  const preMean = preMeanStr !== null ? parseFloat(preMeanStr) : null;
  const postMean = postMeanStr !== null ? parseFloat(postMeanStr) : null;
  const preStd = preStdStr !== null ? parseFloat(preStdStr) : null;
  const postStd = postStdStr !== null ? parseFloat(postStdStr) : null;
  const preCount = preCountStr !== null ? parseInt(preCountStr, 10) : null;
  const postCount = postCountStr !== null ? parseInt(postCountStr, 10) : null;
  const changeMagnitude = changeMagStr !== null ? parseFloat(changeMagStr) : null;
  const peltPenalty = peltPenStr !== null ? parseFloat(peltPenStr) : null;

  // Trích xuất summary JSON nếu có
  let preSummaryJson: any = null;
  let postSummaryJson: any = null;
  try {
    const preJsonStr = matchValue(/pre_window_summary=({.*?})/);
    if (preJsonStr) preSummaryJson = JSON.parse(preJsonStr);
  } catch {}
  try {
    const postJsonStr = matchValue(/post_window_summary=({.*?})/);
    if (postJsonStr) postSummaryJson = JSON.parse(postJsonStr);
  } catch {}

  // 1. Xác định Metric bị bất thường
  let detectedMetricKey = 'trip_distance_km'; // Mặc định L4 changepoint trong DataTrust
  const lowerAll = (reason + ' ' + (w.warning_type || '') + ' ' + JSON.stringify(w.redacted_record_json || {})).toLowerCase();

  if (lowerAll.includes('battery_temp') || lowerAll.includes('nhiệt độ pin')) {
    detectedMetricKey = 'battery_temp_c';
  } else if (lowerAll.includes('battery_soc') || lowerAll.includes('dung lượng pin')) {
    detectedMetricKey = 'battery_soc';
  } else if (lowerAll.includes('fare_amount') || lowerAll.includes('total_fare') || lowerAll.includes('cước')) {
    detectedMetricKey = 'fare_amount';
  } else if (lowerAll.includes('motor_rpm') || lowerAll.includes('vòng tua')) {
    detectedMetricKey = 'motor_rpm';
  } else if (lowerAll.includes('trip_distance') || lowerAll.includes('quãng đường')) {
    detectedMetricKey = 'trip_distance_km';
  }

  const metricDef = METRIC_CATALOG[detectedMetricKey] || METRIC_CATALOG.trip_distance_km;

  // 2. Định dạng thời điểm
  let detectedTimeFormatted = 'N/A';
  if (changeTimeStr) {
    try {
      detectedTimeFormatted = new Intl.DateTimeFormat('vi-VN', {
        dateStyle: 'medium',
        timeStyle: 'medium',
      }).format(new Date(changeTimeStr));
    } catch {
      detectedTimeFormatted = changeTimeStr;
    }
  } else if (w.detected_at) {
    try {
      detectedTimeFormatted = new Intl.DateTimeFormat('vi-VN', {
        dateStyle: 'medium',
        timeStyle: 'medium',
      }).format(new Date(w.detected_at));
    } catch {
      detectedTimeFormatted = w.detected_at;
    }
  }

  // 3. Tính toán độ lệch và phần trăm
  let isIncrease = false;
  let percentChangeStr = '';
  let preValueStr = preMean !== null ? `${preMean.toFixed(2)} ${metricDef.unit}` : 'N/A';
  let postValueStr = postMean !== null ? `${postMean.toFixed(2)} ${metricDef.unit}` : 'N/A';
  let changeSummary = '';

  if (preMean !== null && postMean !== null) {
    const delta = postMean - preMean;
    isIncrease = delta > 0;
    const pct = preMean !== 0 ? Math.abs((delta / preMean) * 100) : 0;
    percentChangeStr = `${pct.toFixed(1)}%`;
    const dirWord = isIncrease ? 'tăng' : 'giảm';
    const prepWord = isIncrease ? 'lên' : 'xuống';
    changeSummary = `Giá trị trung bình ${dirWord} từ ${preMean.toFixed(2)} ${metricDef.unit} ${prepWord} ${postMean.toFixed(2)} ${metricDef.unit} (${dirWord} ${percentChangeStr})`;
  } else if (changeMagnitude !== null) {
    isIncrease = changeMagnitude > 0;
    const dirWord = isIncrease ? 'tăng' : 'giảm';
    changeSummary = `Ghi nhận bước nhảy ${dirWord} ${Math.abs(changeMagnitude).toFixed(2)} ${metricDef.unit}`;
  } else {
    changeSummary = 'Ghi nhận bước dịch chuyển dữ liệu bất thường giữa các cửa sổ quan sát';
  }

  // 4. Đánh giá cỡ mẫu (Sample size evaluation)
  const isSmallSample = (preCount !== null && preCount <= 5) || (postCount !== null && postCount <= 5);
  let sampleSizeEvaluation = '';
  if (preCount !== null && postCount !== null) {
    if (isSmallSample) {
      sampleSizeEvaluation = `Cỡ mẫu quan sát còn nhỏ (${preCount} quan sát trước và ${postCount} quan sát sau bước nhảy). Chưa đủ cơ sở thống kê để khẳng định đây là xu hướng suy giảm bền vững dài hạn; nhiều khả năng là biến động tức thời hoặc thời điểm chuyển giao ca làm việc.`;
    } else {
      sampleSizeEvaluation = `Cỡ mẫu bao gồm ${preCount} quan sát trước và ${postCount} quan sát sau bước nhảy, ghi nhận sự phân tách rõ rệt giữa hai chuỗi số liệu.`;
    }
  } else {
    sampleSizeEvaluation = 'Cần thu thập thêm quan sát tiếp theo để xác định đây có phải xu hướng biến động lâu dài hay không.';
  }

  // 5. Tóm tắt súc tích cho bảng danh sách
  const sampleNote = isSmallSample
    ? ` [Cỡ mẫu nhỏ ${preCount ?? '?'}/${postCount ?? '?'}]`
    : '';
  const conciseSummary = preMean !== null && postMean !== null
    ? `${metricDef.nameVi} ${isIncrease ? 'tăng' : 'giảm'} ${percentChangeStr} (${preMean.toFixed(1)} → ${postMean.toFixed(1)} ${metricDef.unit})${sampleNote}`
    : `${metricDef.nameVi}: ${changeSummary}`;

  // 6. Làm sạch raw string (Lọc bỏ thông tin không liên quan như Jurisdiction chain)
  const cleanedFragments = reason
    .split(';')
    .map((s) => s.trim())
    .filter((s) => s && !s.toLowerCase().includes('jurisdiction chain') && !s.toLowerCase().includes('global ->'));

  return {
    business: {
      metricName: metricDef.nameVi,
      metricField: metricDef.field,
      unit: metricDef.unit,
      changeSummary,
      preValueStr,
      postValueStr,
      percentChangeStr,
      isIncrease,
      detectedTime: detectedTimeFormatted,
      businessMeaning: metricDef.businessContext,
      sampleSizeEvaluation,
      isSmallSample,
      preCount,
      postCount,
      recommendedAction: metricDef.actionVi,
      conciseSummary,
    },
    technical: {
      algorithm: (w.warning_type || '').includes('PELT') ? 'PELT (Pruned Exact Linear Time)' : 'CUSUM / Changepoint Shift',
      changeMagnitude,
      peltPenalty,
      preMean,
      preStd,
      preCount,
      postMean,
      postStd,
      postCount,
      preSummaryJson,
      postSummaryJson,
      rawEvidenceItems: evidenceList,
      cleanedReason: cleanedFragments.join('; '),
    },
  };
}
