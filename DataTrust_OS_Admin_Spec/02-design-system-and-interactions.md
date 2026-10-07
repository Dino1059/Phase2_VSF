# DataTrust OS — Nguyên tắc UX, tương tác và trạng thái hiển thị

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 1, 20, 21, 22. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 1. UX principles

## 1.1. Admin mental model

UI phải hỗ trợ đúng chuỗi:

```text
What happened?
      ↓
Why did it happen?
      ↓
Where did it happen?
      ↓
What is the evidence?
      ↓
What should be done?
      ↓
Admin approves/rejects
```

## 1.2. One-click traceability

Từ một Finding phải đi được đến:

```text
Finding
 ├── Rule
 ├── Policy
 ├── Dataset / Column
 ├── Failed records
 ├── AI explanation
 ├── Root cause
 ├── Data lineage
 ├── Evidence
 └── Quarantine
```

Không bắt Admin tự tìm context ở quá nhiều màn hình.

## 1.3. No source mutation

Toàn bộ UI phải thể hiện rõ rằng hệ thống:

```text
Source DB
   │
   └── READ ONLY
```

Các thao tác xử lý chỉ tác động vào workflow/data lane theo kiến trúc sản phẩm, không ghi trực tiếp vào source DB.

## 1.4. Visual style

- Giữ nguyên palette và font hiện tại của ứng dụng; không thay bằng một visual system mới.
- Font UI chính: `Inter`; font cho ID/code/technical values: `JetBrains Mono`. Giữ các font hiện có khác nếu component hiện tại đang dùng có chủ đích.
- Giữ các token màu hiện tại, đặc biệt cyan/teal `#04D3D4`, yellow `#FFC402`, nền trắng/light slate và text slate.
- Light mode only.
- White / very light gray background.
- Primary accent: teal/cyan.
- Secondary accent: yellow.
- Red dùng cho Critical/Fail/Quarantine.
- Purple dùng cho AI / analytical context nếu cần.
- Card bo góc vừa phải.
- Border mảnh.
- Shadow nhẹ.
- Typography rõ ràng, enterprise SaaS.
- Không dùng dark dashboard.
- Ưu tiên thông tin có thể scan nhanh.
- Action quan trọng phải nổi bật, nhưng không dùng quá nhiều màu.

## 1.5. Dual-pane AI companion

Layout chính của ứng dụng giữ cấu trúc dual-pane hiện tại:

```text
┌────────────────────────┬──────────────────────────────────────┐
│ AI Chat companion      │ Workspace theo màn hình/route       │
│ cố định bên trái       │ dataset, run, finding, lineage...   │
│ cuộn độc lập           │ cuộn độc lập                        │
└────────────────────────┴──────────────────────────────────────┘
```

- Desktop: AI Chat sticky/fixed bên trái, giữ chiều rộng hiện tại khoảng `380–420px` hoặc tỷ lệ gần `35/65`; workspace bên phải co giãn theo viewport.
- AI Chat không bị thay thế khi đổi route nghiệp vụ và duy trì conversation/context phù hợp.
- Workspace bên phải chứa toàn bộ nội dung chức năng được mô tả trong các file spec.
- Mobile/tablet hẹp: không ép hai cột; AI Chat chuyển thành drawer/pane có thể mở đóng, còn workspace giữ toàn bộ chiều rộng.
- AI Chat là bạn đồng hành: giải thích, RCA, gợi ý remediation và hỗ trợ đi tới đúng context. Chat không tự chọn dataset, khởi chạy run, approve/reject, sửa rule hay xác nhận execution thay người dùng.

---

# 20. Interaction specifications

## 20.1. Row click

Click table row:

- Mở detail drawer nếu entity đơn giản.
- Mở dedicated page nếu workflow phức tạp.

## 20.2. Drawer

Drawer mở từ bên phải.

Header:

```text
Title
Status
Close
```

Footer action sticky khi cần.

## 20.3. Confirmation dialog

Bắt buộc cho:

- Approve AI remediation.
- Reject AI remediation nếu có consequence.
- Start full-dataset run.
- Các destructive action nếu sau này được thêm.

## 20.4. Toast

Success:

```text
✓ Quyết định remediation đã được ghi nhận.
```

Error:

```text
Không thể thực hiện thao tác. Vui lòng thử lại.
```

Warning:

```text
Remediation đã được duyệt và đang chờ hệ thống thực thi.
```

Không dùng toast cho thông tin quan trọng duy nhất; thông tin quan trọng phải còn nằm trong UI.

---

# 21. Loading / Empty / Error states

## Loading

Skeleton cho:

- KPI;
- table;
- chart;
- detail drawer.

Không để màn hình trắng.

## Empty state

Ví dụ:

```text
Chưa có Finding

Run này không phát hiện vi phạm
theo các rule đã áp dụng.

[Quay lại Run]
```

## No quarantine

```text
Không có record bị cách ly.

Tất cả records đều vượt qua
các điều kiện quarantine hiện tại.
```

## Error

```text
Không tải được dữ liệu

[Thử lại]
```

---

# 22. Status system

Dùng các status thống nhất toàn app.

### Run

```text
Pending
Running
Completed
Failed
Cancelled
```

### Evaluation

```text
PASS
FAIL
WARNING
NOT_EVALUATED
```

### Finding

```text
Open
In Review
Approved
Rejected
Resolved
```

### Quarantine

```text
Quarantined
Under Review
Approved for Processing
Rejected
Released
```

### HITL remediation

```text
Suggested
Approved
Rejected
Executing
Completed
Failed
```

Không dùng nhiều tên status khác nhau cho cùng semantic.

---
