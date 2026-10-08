# DataTrust OS — AI Explanation, RCA và phê duyệt remediation

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 11. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 11. AI Explanation / Root Cause Analysis

AI chỉ hoạt động trên context đã có:

```text
Result
+
Finding
+
Evidence
+
Lineage
+
Rule
+
Policy
```

## 11.1. UI

```text
AI Analysis

What happened
8,231 records failed GDPR-ART5-001.

Root cause
customer.phone được đưa từ Bronze
sang downstream mà không áp dụng
required treatment.

Data path
CRM
 ↓
Bronze.customer
 ↓
Policy Check
 ↓
Missing Treatment
 ↓
Quarantine

Confidence
92%
```

## 11.2. AI actions

```text
Đề xuất xử lý

1. PSEUDONYMIZE customer.phone
2. Giữ raw record trong quarantine
3. Re-run compliance check

[Reject]
[Approve]
```

### Strict HITL

AI **không tự**:

- execute remediation;
- update DB;
- release quarantine;
- change rule;
- change policy.

### Jurisdiction grounding

AI receives only the matched policy snapshot stored on the Finding, including `subject_zone`, `policy_id`, and `law_ref`. It MUST NOT add, merge, or infer a legal framework from another zone. For example, an EU Finding may cite GDPR and applicable GLOBAL controls, but must not cite Luật 91/2025/QH15 unless the persisted evidence explicitly establishes VN applicability.

Click Approve phải có confirmation:

```text
Approve AI recommendation?

Bạn đang phê duyệt:
PSEUDONYMIZE customer.phone

Scope:
8,231 quarantined records

[Cancel]
[Approve]
```

Sau approve:

```text
Status:
Approved by Admin
```

Nếu workflow có bước execution riêng thì UI chuyển sang trạng thái:

```text
Approved → Pending execution
```

Không tự giả định execution đã thành công.

---

# 12. AI Đồng hành (AI Chat Orchestrator & Conversational Agent)

## 12.1. Phạm vi & Nguyên tắc Run Isolation Bắt buộc
AI Chat Assistant tương tác trực tiếp với người dùng và phải tuân thủ nghiêm ngặt **Run Isolation**:
- `run_id` là tham số bắt buộc trong mọi yêu cầu tương tác (`POST /api/agent/chat`).
- AI chỉ được phép đọc và phân tích dữ liệu gắn với `run_id` đang chọn. Tuyệt đối không suy diễn hoặc lấy vi phạm từ các lần chạy khác.
- UI khóa khung chat khi chưa có Run hợp lệ được chọn.

## 12.2. Bảng Ma trận Điều phối 7 Nguồn Dữ liệu theo Intent
Thay vì tải toàn bộ dữ liệu gây tốn token và tăng độ trễ, AI Agent tải có chọn lọc theo Intent của người dùng:

| Intent | Nguồn cần tải | Cách liên kết | Giới hạn / An toàn |
| :--- | :--- | :--- | :--- |
| **Tổng quan Run** (`RUN_OVERVIEW`) | `orchestration.pipeline_runs`, `pipeline_run_steps`, `audit.findings` | `run_id` | Chỉ số tổng hợp (scanned, silver, quarantine, status, duration). Không tải record chi tiết. |
| **RCA Finding** (`ROOT_CAUSE_ONLY`) | `audit.findings`, `quarantine.records`, `catalog.table_profiles` | `run_id` + `finding_id`, `dataset_id` (snapshot tại `run.started_at`) | Tối đa 3–5 mẫu rút gọn qua Allowlist trường, che PII 100%. Không gửi `raw_record_json` thô. Không tự sinh remediation. |
| **Đề xuất Khắc phục** (`REMEDIATION_ONLY`) | `audit.findings`, `policy.compliance_rules`, `policy.data_treatment_rules` | `run_id` + `finding_id`, Rule/Policy có hiệu lực lúc `run.started_at` | Không tải record thô. Chỉ lấy rule expression và chính sách liên quan. |
| **Phân tích Toàn diện** (`BOTH_RCA_AND_REMEDIATION`) | `audit.findings`, `quarantine.records`, `policy.compliance_rules`, `catalog.table_profiles` | `run_id` + `finding_id`, `dataset_id` (snapshot tại `run.started_at`) | Áp dụng đầy đủ quy tắc che PII, tối đa 3 mẫu, kết hợp rule có hiệu lực tại thời điểm chạy. |
| **Tiến độ / Lỗi** (`PIPELINE_ERROR_OR_PROGRESS`) | `orchestration.pipeline_runs`, `pipeline_run_steps`, `orchestration.pipeline_run_events` | `run_id` | Tối đa 10 sự kiện gần nhất của bước bị lỗi hoặc đang chạy. Cắt ngắn stacktrace. |

## 12.3. Quy tắc Định dạng Phản hồi (5 Tiêu chí Bắt buộc)
1. **Trả lời ngắn gọn, đúng câu hỏi:** Nếu người dùng hỏi nguyên nhân thì chỉ giải thích nguyên nhân, không tự động liệt kê remediation.
2. **Đưa kết luận lên đầu:** Tóm tắt Finding trong 1–2 câu mở đầu, sau đó mới trình bày các giả thuyết RCA.
3. **Giảm trùng lặp:** Không lặp lại cùng một nội dung ở nhiều phần. Chỉ phân chia Lane A / Lane B khi bài toán thực sự là vi phạm kép (`BOTH`).
4. **Ẩn JSON và thông tin kỹ thuật:** Tuyệt đối không hiển thị `structured_analysis`, `requires_approval = True` hay JSON thô trong nội dung bong bóng chat. Backend bóc tách và gửi ngầm trong trường `data`.
5. **Chuẩn hóa Markdown:** Không để xuất hiện ký tự escape lỗi như `\####`, `1\.`, `\*`. Giảm số lượng heading sâu và làm phẳng các danh sách lồng nhau.

## 12.4. Quản lý Phiên Chat & Bảo mật
- Mỗi phiên chat (`session_id`) gắn bất biến với đúng một `run_id`. Đổi Run thì tự động chuyển hoặc tạo phiên chat mới.
- Lưu trữ cục bộ (`localStorage`) áp dụng thuật toán LRU (tối đa 20 phiên, < 2MB), schema migration v2, try-catch chống JSON hỏng và hiển thị cảnh báo bảo mật dữ liệu cục bộ.
- Ẩn hoàn toàn trường `traces` ở môi trường Production.

---
