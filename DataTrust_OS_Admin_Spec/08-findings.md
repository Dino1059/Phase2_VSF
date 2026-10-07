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

