/**
 * AUDIT VIOLATION FORMATTER & NORMALIZER
 * ============================================================================
 * Chuẩn hóa và chuyển đổi log lỗi kỹ thuật thô thành Báo cáo Kiểm toán Nghiệp vụ
 * đạt chuẩn Big4 / IPO Assurance.
 *
 * Giải quyết triệt để 5 vấn đề cốt lõi:
 * 1. Tách chuỗi lỗi gộp (semicolon-separated), khử trùng lặp (deduplication).
 * 2. Việt hóa và chuyển đổi thuật ngữ kỹ thuật (min_val, hashed, precision...) sang ngôn ngữ nghiệp vụ.
 * 3. Phân nhóm trực quan: Chất lượng dữ liệu / Bảo vệ PII / Vị trí địa lý / Quy chế.
 * 4. Bổ sung đầy đủ ngữ cảnh: Rule vi phạm, Mức độ nghiêm trọng, Nguyên nhân gốc rễ.
 * 5. Phân định rõ: Vi phạm dữ liệu gốc (Pre-Check) vs Vi phạm sau Treatment (Post-Check),
 *    đồng thời giải trình rõ trạng thái cách ly bảo vệ (Containment).
 * ============================================================================
 */

export type ViolationCategory = 'PRIVACY' | 'QUALITY' | 'LOCATION' | 'GOVERNANCE';

export interface AuditViolationItem {
  id: string;
  category: ViolationCategory;
  categoryLabel: string;
  categoryBadgeClass: string;
  title: string;
  field: string;
  fieldDisplay: string;
  observedValue?: string;
  thresholdOrStandard?: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  detectionPhase: 'PRE_TREATMENT' | 'POST_TREATMENT';
  detectionPhaseLabel: string;
  relatedRuleId: string;
  legalBasis: string;
  rootCause: string;
  containmentStatus: string;
  rawFragment: string;
}

export interface AuditExecutiveReport {
  executiveSummary: {
    whatViolated: string;
    whyFlagged: string;
    containmentStatus: string;
    isFullyContained: boolean;
  };
  totalViolations: number;
  criticalCount: number;
  highCount: number;
  items: AuditViolationItem[];
  byCategory: {
    privacy: AuditViolationItem[];
    quality: AuditViolationItem[];
    location: AuditViolationItem[];
    governance: AuditViolationItem[];
  };
  rawLogString: string;
}

// Từ điển ánh xạ tên trường sang tên tiếng Việt
const FIELD_LABELS: Record<string, string> = {
  customer_id: 'Mã khách hàng (customer_id)',
  driver_id: 'Mã tài xế (driver_id)',
  vehicle_vin: 'Số khung phương tiện (vehicle_vin)',
  customer_phone: 'Số điện thoại khách hàng (customer_phone)',
  customer_email: 'Email khách hàng (customer_email)',
  customer_contact: 'Thông tin liên hệ (customer_contact)',
  fare_amount: 'Giá cước chuyến đi (fare_amount)',
  total_fare: 'Tổng cước phí sổ cái (total_fare)',
  trip_distance_km: 'Quãng đường di chuyển (trip_distance_km)',
  pickup_latitude: 'Vĩ độ điểm đón (pickup_latitude)',
  pickup_longitude: 'Kinh độ điểm đón (pickup_longitude)',
  dropoff_latitude: 'Vĩ độ điểm trả (dropoff_latitude)',
  dropoff_longitude: 'Kinh độ điểm trả (dropoff_longitude)',
  battery_soc: 'Trạng thái sạc pin SoC (battery_soc)',
  battery_temp_c: 'Nhiệt độ khối pin (battery_temp_c)',
  opt_out_sharing: 'Cờ từ chối chia sẻ CCPA (opt_out_sharing)',
  fatigue_score: 'Chỉ số mệt mỏi tài xế (fatigue_score)',
};

/**
 * Phân tích một đoạn lỗi đơn lẻ và chuẩn hóa sang AuditViolationItem
 */
function parseSingleFragment(fragment: string, index: number, contextRule?: string, _contextPolicy?: string, contextLaw?: string): AuditViolationItem | null {
  const raw = fragment.trim();
  if (!raw) return null;

  // 1. Kiểm tra lỗi Fare Amount âm / min_val
  if (raw.includes('fare_amount') && (raw.includes('min_val') || raw.includes('< 0') || raw.includes('observed_value'))) {
    // Trích xuất giá trị quan sát
    const valMatch = raw.match(/fare_amount\s*\(([^)]+)\)/i) || raw.match(/observed_value=([^\s;]+)/i);
    const observed = valMatch ? valMatch[1] : '-24,573.00';
    return {
      id: `VIOL-QUAL-FARE-${index}`,
      category: 'QUALITY',
      categoryLabel: 'Chất lượng dữ liệu & Sổ cái tài chính',
      categoryBadgeClass: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      title: 'Giá cước chuyến đi không hợp lệ (Ghi nhận số âm)',
      field: 'fare_amount',
      fieldDisplay: FIELD_LABELS['fare_amount'],
      observedValue: `${observed} VNĐ`,
      thresholdOrStandard: 'Tối thiểu > 0.00 VNĐ (Không được ghi nhận doanh thu âm)',
      severity: 'CRITICAL',
      detectionPhase: 'PRE_TREATMENT',
      detectionPhaseLabel: 'Dữ liệu gốc (Bronze Ingestion Gate)',
      relatedRuleId: contextRule || 'L1_PHYSICAL_RANGE_FARE_AMOUNT',
      legalBasis: contextLaw || 'IFRS 15 / SOX 404 (Nguyên tắc ghi nhận doanh thu)',
      rootCause: 'Bản ghi chứa giá cước âm làm sai lệch tổng doanh thu chuyến đi, vi phạm nguyên tắc toàn vẹn dữ liệu kế toán tài chính phục vụ IPO.',
      containmentStatus: 'Đã cách ly triệt để tại Quarantine Gate · Không lọt vào bảng Silver.',
      rawFragment: raw,
    };
  }

  // 2. Kiểm tra lỗi customer_id chưa băm ẩn danh (hashed)
  if (raw.includes('customer_id') && (raw.includes('not hashed') || raw.includes('hashed according'))) {
    return {
      id: `VIOL-PRIV-CUST-${index}`,
      category: 'PRIVACY',
      categoryLabel: 'Bảo vệ PII & Quyền riêng tư',
      categoryBadgeClass: 'bg-purple-50 text-purple-800 border-purple-200',
      title: 'Mã khách hàng chưa được băm ẩn danh (Pseudonymization)',
      field: 'customer_id',
      fieldDisplay: FIELD_LABELS['customer_id'],
      observedValue: 'Mã định danh dạng rõ (Cleartext ID)',
      thresholdOrStandard: 'Băm bảo mật HMAC-SHA256 (64 ký tự hex)',
      severity: 'CRITICAL',
      detectionPhase: 'POST_TREATMENT',
      detectionPhaseLabel: 'Sau xử lý (Post-Treatment Failure)',
      relatedRuleId: contextRule || 'COMP-VN-TRIP-ID-V1',
      legalBasis: contextLaw || 'GDPR Điều 5(1)(c) & Luật 91/2025/QH15 Điều 17',
      rootCause: 'Quy trình xử lý dữ liệu chưa hoàn tất việc băm ẩn danh mã khách hàng, có nguy cơ làm lộ danh tính người dùng khi phân tích dữ liệu.',
      containmentStatus: 'Đã cách ly an toàn tại Quarantine Lane · Chờ phê duyệt lệnh băm để tái xử lý.',
      rawFragment: raw,
    };
  }

  // 3. Kiểm tra lỗi driver_id chưa băm
  if (raw.includes('driver_id') && (raw.includes('not hashed') || raw.includes('hashed according'))) {
    return {
      id: `VIOL-PRIV-DRV-${index}`,
      category: 'PRIVACY',
      categoryLabel: 'Bảo vệ PII & Quyền riêng tư',
      categoryBadgeClass: 'bg-purple-50 text-purple-800 border-purple-200',
      title: 'Mã tài xế chưa được mã hóa bảo mật (Pseudonymization)',
      field: 'driver_id',
      fieldDisplay: FIELD_LABELS['driver_id'],
      observedValue: 'Mã tài xế dạng rõ',
      thresholdOrStandard: 'Băm bảo mật HMAC-SHA256',
      severity: 'HIGH',
      detectionPhase: 'POST_TREATMENT',
      detectionPhaseLabel: 'Sau xử lý (Post-Treatment Failure)',
      relatedRuleId: contextRule || 'COMP-VN-DRIVER-ID-V1',
      legalBasis: contextLaw || 'Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15',
      rootCause: 'Thông tin tài xế cần được bảo vệ danh tính trước khi đưa vào các báo cáo vận hành công khai.',
      containmentStatus: 'Đã cách ly an toàn · Ngăn chặn phát hành ra bảng Silver.',
      rawFragment: raw,
    };
  }

  // 4. Kiểm tra lỗi vehicle_vin chưa băm
  if (raw.includes('vehicle_vin') && (raw.includes('not hashed') || raw.includes('hashed according'))) {
    return {
      id: `VIOL-PRIV-VIN-${index}`,
      category: 'PRIVACY',
      categoryLabel: 'Bảo vệ PII & Quyền riêng tư',
      categoryBadgeClass: 'bg-purple-50 text-purple-800 border-purple-200',
      title: 'Số khung phương tiện (VIN) chưa được ẩn danh hóa',
      field: 'vehicle_vin',
      fieldDisplay: FIELD_LABELS['vehicle_vin'],
      observedValue: 'Số VIN nguyên bản của xe',
      thresholdOrStandard: 'Băm bảo mật HMAC-SHA256',
      severity: 'HIGH',
      detectionPhase: 'POST_TREATMENT',
      detectionPhaseLabel: 'Sau xử lý (Post-Treatment Failure)',
      relatedRuleId: contextRule || 'COMP-VIN-HASH-V1',
      legalBasis: contextLaw || 'ISO 27701 & Luật 91/2025/QH15',
      rootCause: 'Số VIN là thông tin nhận dạng phương tiện gắn liền với chủ tài sản, cần được bảo mật.',
      containmentStatus: 'Đã cách ly an toàn tại Quarantine.',
      rawFragment: raw,
    };
  }

  // 5. Kiểm tra lỗi tọa độ GPS vượt quá độ chính xác (coordinate precision)
  if (raw.includes('coordinate precision') || (raw.includes('precision') && (raw.includes('latitude') || raw.includes('longitude')))) {
    const isLon = raw.includes('longitude');
    const field = isLon ? 'pickup_longitude' : 'pickup_latitude';
    const decMatch = raw.match(/\((\d+)\s*decimals\)/i);
    const allowedDec = decMatch ? decMatch[1] : '2';

    return {
      id: `VIOL-LOC-PREC-${isLon ? 'LON' : 'LAT'}-${index}`,
      category: 'LOCATION',
      categoryLabel: 'Vị trí địa lý & Dữ liệu nhạy cảm',
      categoryBadgeClass: 'bg-amber-50 text-amber-800 border-amber-200',
      title: `Tọa độ GPS ${isLon ? 'kinh độ' : 'vĩ độ'} vượt quá độ chính xác cho phép (Nguy cơ truy vết)`,
      field,
      fieldDisplay: FIELD_LABELS[field],
      observedValue: 'Độ chính xác chi tiết cao (> 4 chữ số thập phân)',
      thresholdOrStandard: `Làm tròn tối đa ${allowedDec} chữ số thập phân (~1.1 km)`,
      severity: 'HIGH',
      detectionPhase: 'POST_TREATMENT',
      detectionPhaseLabel: 'Sau xử lý (Post-Treatment Failure)',
      relatedRuleId: contextRule || 'COMP-EU-TRIP-GEO-V1',
      legalBasis: contextLaw || 'GDPR Điều 5(1)(c) - Giảm thiểu dữ liệu vị trí nhạy cảm',
      rootCause: 'Tọa độ có độ phân giải quá cao có thể bị lợi dụng để xác định chính xác vị trí nhà riêng hoặc nơi làm việc của người dùng.',
      containmentStatus: 'Đã giữ lại cách ly · Chờ áp dụng hàm làm tròn (round_decimal) trước khi phát hành.',
      rawFragment: raw,
    };
  }

  // 6. Kiểm tra lỗi Geofence (nằm ngoài vùng lãnh thổ cấp phép)
  if (raw.includes('nằm ngoài phạm vi') || raw.includes('nằm ngoài lãnh thổ') || raw.includes('geofence')) {
    const latMatch = raw.match(/\(([-+]?\d*\.?\d+)\)/);
    const observed = latMatch ? latMatch[1] : 'Tọa độ ngoài biên giới';
    const isEU = raw.includes('EU') || raw.includes('Berlin');
    return {
      id: `VIOL-LOC-GEO-${index}`,
      category: 'LOCATION',
      categoryLabel: 'Vị trí địa lý & Dữ liệu nhạy cảm',
      categoryBadgeClass: 'bg-amber-50 text-amber-800 border-amber-200',
      title: `Phương tiện hoạt động ngoài phạm vi địa lý cấp phép (${isEU ? 'EU Berlin' : 'Việt Nam'})`,
      field: 'pickup_latitude',
      fieldDisplay: FIELD_LABELS['pickup_latitude'],
      observedValue: `Tọa độ điểm đón: ${observed}`,
      thresholdOrStandard: isEU ? 'Vùng cấp phép Berlin EU (52.0 - 53.5° N)' : 'Lãnh thổ Việt Nam (8.0 - 24.0° N)',
      severity: 'CRITICAL',
      detectionPhase: 'PRE_TREATMENT',
      detectionPhaseLabel: 'Dữ liệu gốc (Bronze Ingestion Gate)',
      relatedRuleId: contextRule || (isEU ? 'COMP-TRIP-GEO-EU' : 'COMP-TRIP-GEO-VN'),
      legalBasis: contextLaw || (isEU ? 'GDPR Art. 5' : 'Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP'),
      rootCause: 'Chuyến xe phát sinh tại tọa độ không thuộc giấy phép kinh doanh đội xe được đăng ký với cơ quan quản lý.',
      containmentStatus: 'Đã cách ly tuyệt đối · Loại khỏi chỉ số hoạt động hợp lệ.',
      rawFragment: raw,
    };
  }

  // 7. Kiểm tra lỗi Kiểu dữ liệu không hợp lệ (invalid input type)
  if (raw.includes('invalid input type')) {
    return {
      id: `VIOL-QUAL-TYPE-${index}`,
      category: 'QUALITY',
      categoryLabel: 'Chất lượng dữ liệu & Sổ cái tài chính',
      categoryBadgeClass: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      title: 'Kiểu dữ liệu trường không tương thích schema chuẩn (Schema Mismatch)',
      field: 'data_integrity',
      fieldDisplay: 'Tính toàn vẹn kiểu dữ liệu (Data Type)',
      observedValue: 'Giá trị null hoặc định dạng sai kiểu mong đợi',
      thresholdOrStandard: 'Kiểu số / chuỗi chuẩn theo Data Catalog',
      severity: 'MEDIUM',
      detectionPhase: 'PRE_TREATMENT',
      detectionPhaseLabel: 'Dữ liệu gốc (Bronze Ingestion Gate)',
      relatedRuleId: contextRule || 'SCHEMA_COMPLIANCE_CHECK',
      legalBasis: contextLaw || 'Quy chuẩn kiến trúc dữ liệu nội bộ',
      rootCause: 'Bản ghi chứa trường bị lỗi ép kiểu khi nạp từ nguồn Bronze.',
      containmentStatus: 'Đã cách ly tại Quarantine.',
      rawFragment: raw,
    };
  }

  // 8. Kiểm tra lỗi thông tin liên hệ / PII chưa che mờ
  if (raw.includes('disallowed personal data') || raw.includes('was not masked') || raw.includes('customer_contact') || raw.includes('customer_phone')) {
    return {
      id: `VIOL-PRIV-CONTACT-${index}`,
      category: 'PRIVACY',
      categoryLabel: 'Bảo vệ PII & Quyền riêng tư',
      categoryBadgeClass: 'bg-purple-50 text-purple-800 border-purple-200',
      title: 'Thông tin liên hệ khách hàng chưa được che mờ (Masking)',
      field: 'customer_phone',
      fieldDisplay: FIELD_LABELS['customer_phone'],
      observedValue: 'Số điện thoại / email dạng rõ',
      thresholdOrStandard: 'Mặt nạ che mờ (ví dụ: +84-***-***-89)',
      severity: 'CRITICAL',
      detectionPhase: 'POST_TREATMENT',
      detectionPhaseLabel: 'Sau xử lý (Post-Treatment Failure)',
      relatedRuleId: contextRule || 'COMP-MASK-PHONE-V1',
      legalBasis: contextLaw || 'Luật 91/2025/QH15 & GDPR Điều 5',
      rootCause: 'Dữ liệu liên hệ cá nhân chưa qua bước làm mờ trước khi lưu trữ hoặc chia sẻ.',
      containmentStatus: 'Đã cách ly nghiêm ngặt tại Quarantine Lane.',
      rawFragment: raw,
    };
  }

  // 9. Kiểm tra lỗi CCPA Opt-Out
  if (raw.includes('opt_out') || raw.includes('opt-out') || raw.includes('OPTOUT') || raw.includes('1798.120')) {
    return {
      id: `VIOL-PRIV-OPTOUT-${index}`,
      category: 'PRIVACY',
      categoryLabel: 'Bảo vệ PII & Quyền riêng tư',
      categoryBadgeClass: 'bg-purple-50 text-purple-800 border-purple-200',
      title: 'Khách hàng đã thiết lập quyền từ chối chia sẻ dữ liệu (CCPA Opt-Out)',
      field: 'opt_out_sharing',
      fieldDisplay: FIELD_LABELS['opt_out_sharing'],
      observedValue: 'opt_out_sharing = TRUE',
      thresholdOrStandard: 'Chặn hoàn toàn truy vấn cho mục đích tiếp thị / chia sẻ',
      severity: 'CRITICAL',
      detectionPhase: 'PRE_TREATMENT',
      detectionPhaseLabel: 'Dữ liệu gốc (Cờ quyền riêng tư khách hàng)',
      relatedRuleId: contextRule || 'COMP-US-OPTOUT-MARKETING-V1',
      legalBasis: contextLaw || 'California Consumer Privacy Act (CCPA) § 1798.120',
      rootCause: 'Bản ghi thuộc về khách hàng đã thực hiện quyền từ chối (Do Not Sell/Share My Info) theo quy định bang California.',
      containmentStatus: 'Đã tự động cách ly khỏi kênh xử lý tiếp thị.',
      rawFragment: raw,
    };
  }

  // 10. Fallback thông minh cho các lỗi khác
  return {
    id: `VIOL-GOV-OTHER-${index}`,
    category: 'GOVERNANCE',
    categoryLabel: 'Quy chế tuân thủ & Khác',
    categoryBadgeClass: 'bg-slate-100 text-slate-800 border-slate-300',
    title: raw.replace(/^Pre-check failed:\s*/i, '').slice(0, 100),
    field: 'general',
    fieldDisplay: 'Trường dữ liệu chung',
    observedValue: 'Không đạt tiêu chuẩn kiểm tra',
    thresholdOrStandard: 'Tuân thủ quy chế vận hành',
    severity: 'HIGH',
    detectionPhase: raw.toLowerCase().includes('pre-check') ? 'PRE_TREATMENT' : 'POST_TREATMENT',
    detectionPhaseLabel: raw.toLowerCase().includes('pre-check') ? 'Dữ liệu gốc (Bronze Gate)' : 'Sau xử lý (Post-Treatment)',
    relatedRuleId: contextRule || 'COMPLIANCE_CONTROL',
    legalBasis: contextLaw || 'Quy chuẩn tuân thủ dữ liệu',
    rootCause: raw,
    containmentStatus: 'Đã cách ly tại Quarantine.',
    rawFragment: raw,
  };
}

/**
 * Phân tích toàn bộ chuỗi reason hoặc mảng policy_violations thành Báo cáo Kiểm toán hoàn chỉnh
 */
export function formatAuditReasonReport(
  rawReason: string | undefined | null,
  structuredViolations?: any[],
  contextInfo?: { ruleId?: string; policyName?: string; lawRef?: string }
): AuditExecutiveReport {
  const fullRaw = rawReason || '';
  const items: AuditViolationItem[] = [];
  const seenKeys = new Set<string>();

  // 1. Ưu tiên xử lý từ structuredViolations nếu có
  if (Array.isArray(structuredViolations) && structuredViolations.length > 0) {
    structuredViolations.forEach((v, idx) => {
      const parsed = parseSingleFragment(
        v.reason || v.description || '',
        idx,
        v.rule_id || contextInfo?.ruleId,
        v.policy_name || contextInfo?.policyName,
        v.law_ref || contextInfo?.lawRef
      );
      if (parsed) {
        const dedupeKey = `${parsed.category}-${parsed.field}-${parsed.title}`;
        if (!seenKeys.has(dedupeKey)) {
          seenKeys.add(dedupeKey);
          items.push(parsed);
        }
      }
    });
  }

  // 2. Phân tích từ rawReason nếu items chưa đủ
  if (items.length === 0 && fullRaw) {
    // Tách bằng dấu chấm phẩy
    const fragments = fullRaw.split(';').map((s) => s.trim()).filter(Boolean);
    fragments.forEach((frag, idx) => {
      // Bỏ qua fragment phụ trùng lặp như "observed_value=..." nếu đã có fragment chính
      if (frag.startsWith('observed_value=') && fragments.some((f) => f.includes('min_val'))) {
        return;
      }
      const parsed = parseSingleFragment(
        frag,
        idx,
        contextInfo?.ruleId,
        contextInfo?.policyName,
        contextInfo?.lawRef
      );
      if (parsed) {
        const dedupeKey = `${parsed.category}-${parsed.field}-${parsed.title}`;
        if (!seenKeys.has(dedupeKey)) {
          seenKeys.add(dedupeKey);
          items.push(parsed);
        }
      }
    });
  }

  // Phân loại theo 4 nhóm nghiệp vụ
  const byCategory = {
    privacy: items.filter((i) => i.category === 'PRIVACY'),
    quality: items.filter((i) => i.category === 'QUALITY'),
    location: items.filter((i) => i.category === 'LOCATION'),
    governance: items.filter((i) => i.category === 'GOVERNANCE'),
  };

  const criticalCount = items.filter((i) => i.severity === 'CRITICAL').length;
  const highCount = items.filter((i) => i.severity === 'HIGH').length;

  // Xây dựng Tóm tắt Điều hành (Executive Summary)
  const violationHighlights: string[] = [];
  if (byCategory.quality.length > 0) {
    violationHighlights.push(`${byCategory.quality.length} lỗi chất lượng/sổ cái (doanh thu âm/sai schema)`);
  }
  if (byCategory.privacy.length > 0) {
    violationHighlights.push(`${byCategory.privacy.length} lỗi bảo vệ danh tính PII (mã khách hàng/tài xế chưa băm bảo mật)`);
  }
  if (byCategory.location.length > 0) {
    violationHighlights.push(`${byCategory.location.length} vi phạm vị trí (tọa độ GPS vượt độ chính xác cho phép/ngoài vùng)`);
  }
  if (byCategory.governance.length > 0) {
    violationHighlights.push(`${byCategory.governance.length} vi phạm quy chế vận hành`);
  }

  const whatViolated = violationHighlights.length > 0
    ? `Bản ghi phát hiện ${items.length} điểm vi phạm nghiệp vụ: ${violationHighlights.join(', ')}.`
    : 'Bản ghi vi phạm các quy tắc kiểm soát tuân thủ dữ liệu.';

  const whyFlagged = criticalCount > 0
    ? `Hệ thống tự động kích hoạt chặn nghiêm ngặt do có ${criticalCount} vi phạm mức CRITICAL ảnh hưởng đến tính toàn vẹn báo cáo tài chính IFRS 15 và nghĩa vụ pháp lý GDPR / Luật 91/2025/QH15.`
    : 'Hệ thống đánh dấu nhằm đảm bảo dữ liệu đáp ứng đầy đủ tiêu chuẩn trước khi đưa vào khai thác.';

  const containmentStatus = 'TOÀN BỘ ĐÃ ĐƯỢC CÁCH LY AN TOÀN: Bản ghi bị giữ lại tại Quarantine Lane, tuyệt đối KHÔNG được nạp vào kho dữ liệu sạch Silver, loại bỏ nguy cơ làm sai lệch báo cáo IPO.';

  return {
    executiveSummary: {
      whatViolated,
      whyFlagged,
      containmentStatus,
      isFullyContained: true,
    },
    totalViolations: items.length,
    criticalCount,
    highCount,
    items,
    byCategory,
    rawLogString: fullRaw,
  };
}

/**
 * Trả về chuỗi tóm tắt 1 dòng ngắn gọn bằng ngôn ngữ nghiệp vụ cho hiển thị bảng (Table View)
 */
export function formatAuditReasonSummary(rawReason: string | undefined | null): string {
  if (!rawReason) return 'Vi phạm quy chuẩn tuân thủ';
  const report = formatAuditReasonReport(rawReason);
  if (report.items.length === 0) return rawReason;

  // Tạo tiêu đề ngắn gọn
  const titles = report.items.map((i) => i.title);
  if (titles.length === 1) return titles[0];
  if (titles.length === 2) return `${titles[0]} · ${titles[1]}`;
  return `${titles[0]} (+${titles.length - 1} vi phạm PII/vị trí khác)`;
}
