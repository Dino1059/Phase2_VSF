# DataTrust OS — Danh sách và chi tiết record cách ly

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 13, 14. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 13. Quarantine

Route:

```text
/quarantine
```

## 13.1. Header

```text
Quarantine

4,862 isolated records

[Export]
```

## 13.2. Summary cards

```text
Total quarantined
4,862

Critical
1,832

High
2,117

Medium
913
```

## 13.3. Filters

```text
[Search record id...]
[Dataset ▼]
[Rule ▼]
[Severity ▼]
[Status ▼]
[Date range]
```

## 13.4. Table

```text
Time
Run ID
Dataset
Table / Column
Reason
Severity
Status
Action
```

Example:

```text
14:31:12
RUN-001
customer_data
customer.phone
Invalid phone format
High
Quarantined
View
```

---

# 14. Quarantine Record Detail

Click `View`:

```text
Quarantine Record

Record ID
CUST_784321

Original Dataset
customer_data

Column
customer.phone

Original value
+84 123 45A 6789

Violation
Invalid phone format

Rule
PHONE-FORMAT-001

Detected
2026-10-06 14:31:12

Status
QUARANTINED

Lineage hash
a83c...9d12
```

## Actions

Cho phép:

```text
[Đề xuất xử lý]
[Đánh dấu đã xem]
[Xem Evidence]
```

Không có:

```text
[Edit]
[Update source]
[Delete]
```

---

