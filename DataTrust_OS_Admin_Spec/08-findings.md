# DataTrust OS — Danh sách và chi tiết Finding

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 9, 10. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 9. Findings

Route:

```text
/runs/:runId/findings
```

## 9.1. Filters

```text
[Search finding...]
[Severity ▼]
[Policy ▼]
[Rule ▼]
[Dataset ▼]
[Status ▼]
```

## 9.2. Table

### Jurisdiction isolation

The Finding aggregation key MUST include at least:

`run_id + dataset_id + rule_id + column_name + severity + subject_zone + policy_id`.

Records from EU, VN, and US MUST NOT be merged into the same Finding. `law_ref` is the immutable snapshot of the policy/control that actually failed. It must not be inferred from the dataset or replaced with a generic string combining laws from multiple jurisdictions.

The list supports a `subject_zone` filter and displays the normalized zone beside every Finding.

```text
┌─────────────────────────────────────────────────────────────┐
│ Finding ID  Rule             Severity  Records  Status     │
├─────────────────────────────────────────────────────────────┤
│ F-001       GDPR-ART5-001    Critical  8,231    Open       │
│ F-002       PHONE-FMT-001    High      4,823    Open       │
│ F-003       NĐ13-PII-002     High      3,921    Open       │
└─────────────────────────────────────────────────────────────┘
```

### Rule

Finding nên phát sinh chủ yếu từ **FAIL**.

Pass không tạo Finding.

---

# 10. Finding Detail

Finding Detail MUST return samples from the same `subject_zone` as the Finding. It displays `policy_id`, `subject_zone`, `jurisdiction_chain`, and authoritative `law_ref`. Missing mappings are shown as “Chưa xác định căn cứ pháp lý”, not as a guessed law.

Click Finding:

```text
Finding F-001

Severity
🔴 Critical

Status
Open

Rule
GDPR-ART5-001

Policy
GDPR Art. 5(1)(c)

Dataset
customer_data

Column
customer.phone

Failed records
8,231

Reason
Phone number is processed
without sufficient purpose limitation.

Impact
Direct identifier is exposed in
downstream processing.
```

## 10.1. Fixed actions

Mỗi Finding nên có nhóm action dễ thấy:

```text
[Giải thích bằng AI]
[Trace Lineage]
[Xem Evidence]
[Xem Quarantine]
[Xem Rule]
```

---
