# DataTrust OS — Tạo run và theo dõi pipeline

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 6, 7. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 6. Start Run Modal

```text
Run Compliance Check

Dataset
customer_data

Policies
GDPR
NĐ 13/2023

Evidence
☑ Collect evidence

Lineage
☑ Generate lineage

AI
☑ Generate explanation after run

                    [Hủy] [Start Run]
```

## Validation

- Không chọn dataset → Start disabled.
- Dataset không có rule áp dụng → Start disabled hoặc hiển thị validation.
- Rule áp dụng được xác định sẵn theo dataset; modal không có thao tác chọn/bỏ chọn hoặc approve/reject rule.

---

# 7. Run Monitoring

Route:

```text
/runs/:runId
```

## 7.1. Header

```text
Run #RUN-2026-0106-001

customer_data

Status: Running ●
Started: 14:31:12
```

Actions:

```text
[Refresh]
[View results]
```

## 7.2. Pipeline stepper

```text
 Ingest
   ✓ Completed
       ↓
 Bronze
   ✓ Completed
       ↓
 Evaluation
   ● Running
       ↓
 Silver
   ○ Waiting
```

### Step state

- Waiting
- Running
- Completed
- Failed
- Skipped

## 7.3. Metrics card

```text
Records scanned
1,000,000

Pass
972,420

Fail
18,231

Warning
9,349

Not Evaluated
0

Quarantine
18,231
```

### Status semantics

- **PASS**: record đáp ứng rule / policy hoặc đã được xử lý theo required treatment.
- **FAIL**: vi phạm critical/high compliance hoặc reliability condition cần xử lý.
- **WARNING**: tín hiệu bất thường/advisory nhẹ hơn, không nhất thiết tạo Finding.
- **NOT EVALUATED**: thiếu input/metadata/điều kiện cần để đánh giá.
- **QUARANTINE**: record FAIL bị cách ly.

---
