# DataTrust OS — Evidence và kiểm tra tính toàn vẹn

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 15. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 15. Audit Evidence

Route:

```text
/runs/:runId/evidence
```

## 15.1. Evidence summary

```text
Audit Evidence

Run ID
RUN-2026-0106-001

Rule execution
GDPR-ART5-001

Input
bronze.customer

Output
quarantine.records

Records scanned
1,000,000

Failed
8,231

Execution timestamp
2026-10-06 14:31:12

Lineage hash
SHA-256
a83c...9d12

Evidence status
✓ Immutable
```

## 15.2. Evidence types

UI có thể chia:

```text
Overview
Rule execution
Input snapshot
Output snapshot
Lineage
Quarantine
Pipeline logs
Hash / integrity
```

## 15.3. Actions

```text
[Download evidence]
[Copy hash]
```

Không cho sửa evidence.

---

