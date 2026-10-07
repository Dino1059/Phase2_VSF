# DataTrust OS — Phạm vi sản phẩm và ranh giới trách nhiệm

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 0, 30. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

## 0. Document purpose

Tài liệu này là đặc tả để **coding agent triển khai UI/UX cho vai trò Admin** trong DataTrust OS.

Mục tiêu là để agent có thể code trực tiếp mà không phải tự suy diễn luồng nghiệp vụ.

### Product scope

DataTrust OS hỗ trợ Admin:

- Chọn dataset cần audit.
- Xem các compliance rule **đã tồn tại và đang áp dụng cho dataset đã chọn**; không chọn/bỏ chọn hoặc approve/reject rule trước run.
- Chạy pipeline kiểm tra.
- Theo dõi run theo thời gian thực.
- Xem kết quả Pass / Fail / Warning / Not Evaluated.
- Drill-down Finding.
- Xem Rule + Policy context.
- Dùng AI để giải thích Finding và phân tích Root Cause.
- Xem Data Lineage.
- Xem Audit Evidence.
- Xem Quarantine records.
- Review và approve/reject đề xuất **remediation/treatment** của AI.
- Xem dashboard tổng hợp và lịch sử audit.

### Explicitly out of scope

AI **KHÔNG**:

- đề xuất rule mới;
- tạo policy mới;
- tự sửa/chỉnh policy;
- tạo compliance test case;
- tự sửa source database;
- tự chạy remediation mà chưa qua HITL;

Admin **KHÔNG**:

- sửa trực tiếp raw/source record;
- xóa raw evidence;
- sửa source DB;
- tạo policy/rule mới từ UI này.

> AI chỉ đóng vai trò Copilot: **Explain → RCA → Suggest Remediation**.
> Rule Engine chịu trách nhiệm evaluation.
> Airflow chịu trách nhiệm orchestration/execution.
> Admin là người quyết định cuối cùng tại các bước HITL.

---

# 30. Important product boundaries

### Rule Engine

```text
Policy + Rule
      ↓
Evaluation
      ↓
PASS / FAIL / WARNING / NOT_EVALUATED
```

### Airflow

```text
Orchestration
Ingest
Processing
Evaluation execution
Logging
Evidence generation
```

### AI Agent

```text
Context gathering
+
Explanation
+
RCA
+
Remediation suggestion
```

### Admin

```text
Select
Review
Approve / Reject
Investigate
Validate evidence
Approve / Reject remediation
```

### Source DB

```text
READ ONLY
```

---
