# DataTrust OS — API boundaries và realtime behavior

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 26, 27. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 26. API boundaries

UI không tự implement compliance logic.

### Dataset APIs

```text
GET /datasets
GET /datasets/:id
```

### Rules

```text
GET /rules
GET /rules/:id
```

### Runs

```text
POST /runs
GET /runs
GET /runs/:id
GET /runs/:id/status
GET /runs/:id/results
```

### Findings

`GET /api/findings` accepts `subject_zone`. List and detail responses include `subject_zone`, `jurisdiction_chain`, `policy_id`, and `law_ref`.

`policy_id` and `law_ref` are authoritative snapshots produced during evaluation. Clients MUST NOT manufacture legal defaults when either value is absent. Detail sample records are restricted to the Finding's zone.
```text
GET /runs/:id/findings
GET /findings/:id
```

### AI

```text
POST /findings/:id/ai-explanation
GET /findings/:id/ai-analysis
POST /findings/:id/remediation/approve
POST /findings/:id/remediation/reject
```

### Lineage

```text
GET /runs/:id/lineage
GET /datasets/:id/lineage
```

### Evidence

```text
GET /runs/:id/evidence
GET /findings/:id/evidence
```

### Quarantine

```text
GET /quarantine
GET /quarantine/:id
```

### Access

```text
GET /access/events
GET /access/alerts
GET /access/metrics
```

Nếu backend chưa tồn tại, tạo typed mock service layer với đúng contracts trên để UI có thể chạy độc lập.

---

# 27. Realtime behavior

Các màn hình sau cần refresh/realtime polling hoặc WebSocket/SSE nếu backend hỗ trợ:

- Run Monitoring.
- Real-time Access Control.
- Alerts.
- Pipeline status.

Fallback nếu chưa có WebSocket:

```text
polling interval = 3–5 seconds
```

Không hard-refresh toàn trang.

Chỉ update state liên quan.

---
