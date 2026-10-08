# DataTrust OS — Xem rules áp dụng và tra cứu policy

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 5, 18. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 5. Applied Compliance Rules


## 5.1. Rule detail drawer

Click một row:

```text
Rule Detail
────────────────────────────

Rule ID
GDPR-ART5-001

Policy
GDPR Art. 5(1)(c)

Target
customer.phone

Condition
Phone number must only be processed
for an approved purpose.

Severity
Critical

Required Treatment
PSEUDONYMIZE

Source
GDPR Policy v1.4

Description
...
```

### Business meaning

Admin/Auditor chỉ xem **các rule đang áp dụng cho dataset hiện tại** để biết phạm vi kiểm tra.

Không có thao tác chọn/bỏ chọn, approve/reject, create hoặc update rule definition tại bước này.

---

# 18. Rules & Policy

Route:

```text
/rules
```

Đây là nơi Admin/Auditor **xem** rule/policy đang áp dụng.

Không biến UI này thành nơi chọn, approve/reject, chỉnh sửa hoặc tạo rule mới.

## List

```text
Rule ID
Rule name
Policy
Version
Scope
Severity
Status
Updated
```

## Rule detail

```text
Rule ID
GDPR-ART5-001

Policy
GDPR

Version
1.4

Scope
customer.phone

Condition
...

Required Treatment
PSEUDONYMIZE

Status
Active
```

### Optional action

## 18.1. Jurisdiction applicability invariant

Policy applicability MUST be resolved for every record, not once for an entire mixed-zone dataset.

- Normalize `subject_zone` and `country` before matching.
- Apply `GLOBAL` controls to every recognized zone.
- Apply `EU`, `VN`, or `US` controls only when that jurisdiction is present in the record's resolved chain.
- A country-level control may apply only when that exact country is present in the chain.
- Precedence is country → zone → global when two controls govern the same field and operation.
- A missing or unsupported zone MUST be reported as `NO_ACTIVE_PACK`; the engine MUST NOT borrow another zone's legal basis.
- Every active rule must expose `policy_id`, `jurisdiction`, and `law_ref`. A missing legal mapping is explicit, never replaced by a combined-law fallback.
```text
[View usage]
```

Cho biết rule đang được dùng ở run nào.

---
