# DataTrust OS — Dashboard tổng hợp

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 16. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 16. Dashboard

Route:

```text
/dashboard
```

Dashboard trả lời 4 câu hỏi:

### A. Đã kiểm tra bao nhiêu dữ liệu?

```text
Records scanned
12.4M
```

### B. Compliance rate?

```text
Compliance rate
97.82%
```

### C. Có bao nhiêu Finding?

```text
Critical
12

High
37

Medium
81
```

### D. Vi phạm ở đâu?

```text
Policy violations

GDPR             42%
NĐ 13/2023       31%
CCPA             17%
Internal Policy  10%
```

Click chart segment → drill down.

Ví dụ:

```text
GDPR 42%
```

→ mở Findings với filter:

```text
Policy = GDPR
```

---

