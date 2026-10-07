# DataTrust OS — Đồ thị truy vết dữ liệu

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 12. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 12. Data Lineage

Route:

```text
/lineage
```

Có thể mở từ sidebar hoặc từ Finding.

## 12.1. Overview

```text
CRM
 │
 ▼
Ingest
 │
 ▼
Bronze.customer
 │
 ├───────────────┐
 ▼               ▼
DQ Check      Policy Check
                   │
                   ▼
             ❌ GDPR-ART5-001
                   │
                   ▼
             Quarantine
                   │
                   ▼
              Silver
                   │
                   ▼
               Publish
```

## 12.2. Node categories

- Source
- Ingest
- Transform
- Bronze
- Silver
- Policy Check
- Data Quality Check
- Quarantine
- Publish / Output

Màu node phải nhất quán.

## 12.3. Node click

Click node → right drawer:

```text
Dataset information

Dataset
bronze.customer

Source
PostgreSQL / CRM

Run ID
RUN-001

Records
1,000,000

PII
Yes

Created
23:52:13

Schema
24 columns
```

## 12.4. Policy step click

```text
Process
Policy Evaluation

Policy
GDPR v1.4

Rules executed
18

Passed
15

Failed
3

Execution time
2.3 sec
```

## 12.5. Lineage controls

```text
[Search]
[-]
[+]
[Fit]
[Full screen]
```

Có thể hỗ trợ:

- zoom;
- pan;
- center;
- expand/collapse;
- filter by run;
- filter by dataset;
- filter by column nếu backend hỗ trợ column-level lineage.

---

