# DataTrust OS — Lịch sử audit

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 19. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 19. Run History

Route:

```text
/runs
```

Table:

```text
Run ID
Dataset
Started
Finished
Duration
Records
Pass
Fail
Warning
Status
```

Example:

```text
RUN-001
customer_data
14:31:12
14:34:11
2m 59s
1,000,000
972,420
18,231
9,349
Completed
```

Click row → `/runs/:runId`.

Filters:

```text
Dataset
Status
Date
Policy
```

Search:

```text
[Search Run ID / Dataset...]
```

---

