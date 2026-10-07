# DataTrust OS — AI Explanation, RCA và phê duyệt remediation

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 11. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 11. AI Explanation / Root Cause Analysis

AI chỉ hoạt động trên context đã có:

```text
Result
+
Finding
+
Evidence
+
Lineage
+
Rule
+
Policy
```

## 11.1. UI

```text
AI Analysis

What happened
8,231 records failed GDPR-ART5-001.

Root cause
customer.phone được đưa từ Bronze
sang downstream mà không áp dụng
required treatment.

Data path
CRM
 ↓
Bronze.customer
 ↓
Policy Check
 ↓
Missing Treatment
 ↓
Quarantine

Confidence
92%
```

## 11.2. AI actions

```text
Đề xuất xử lý

1. PSEUDONYMIZE customer.phone
2. Giữ raw record trong quarantine
3. Re-run compliance check

[Reject]
[Approve]
```

### Strict HITL

AI **không tự**:

- execute remediation;
- update DB;
- release quarantine;
- change rule;
- change policy.

Click Approve phải có confirmation:

```text
Approve AI recommendation?

Bạn đang phê duyệt:
PSEUDONYMIZE customer.phone

Scope:
8,231 quarantined records

[Cancel]
[Approve]
```

Sau approve:

```text
Status:
Approved by Admin
```

Nếu workflow có bước execution riêng thì UI chuyển sang trạng thái:

```text
Approved → Pending execution
```

Không tự giả định execution đã thành công.

---

