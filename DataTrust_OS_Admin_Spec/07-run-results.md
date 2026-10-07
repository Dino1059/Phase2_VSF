# DataTrust OS — Dashboard kết quả run

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 8. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 8. Run Result Dashboard

Route:

```text
/runs/:runId/results
```

## 8.1. KPI cards

```text
PASS
972,420
97.24%

WARNING
9,349
0.93%

FAIL
18,231
1.82%

NOT EVALUATED
0
0%
```

## 8.2. Finding summary

```text
Critical     2
High         7
Medium       9
Low          0
```

## 8.3. Top violated rules

```text
GDPR-ART5-001        8,231
PHONE-FORMAT-001     4,823
NĐ13-PII-002         3,921
```

Click rule → filtered Findings.

## 8.4. Result chart

Nên có:

- Pass / Warning / Fail distribution.
- Findings by severity.
- Findings by policy.
- Findings by rule.
- Quarantine count.
- Optional execution time.

---

