# DataTrust OS — App shell, routes và user journeys

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 2, 3, 28. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 2. Global application shell

## 2.1. Layout

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Logo / Env Status        | [Auditor (Viewer) | Admin] | User Profile│
├───────────────┬─────────────────────────────────────────────────────┤
│ Sidebar       │ AI Chat companion │ Main Workspace                  │
│               │ (Đủ 8 datasets)   │                                 │
│ Trang chủ     │                   │                                 │
│ Lần chạy      │                   │                                 │
│ Data Lineage  │                   │                                 │
│ Access        │                   │                                 │
│ Rules/Policy  │                   │                                 │
│ Quarantine    │                   │                                 │
│ Dashboard     │                   │                                 │
└───────────────┴─────────────────────────────────────────────────────┘
```

### 2.1.1. Topbar & Role Switcher (Auditor vs Admin)

Topbar luôn cố định trên đầu trang và cung cấp:
- **Trạng thái kết nối Backend & PostgreSQL**: Live indicator (`Live (PostgreSQL & FastAPI)` vs `Offline`).
- **Bộ chuyển đổi vai trò (Role Switcher)**: Cho phép chuyển đổi qua lại giữa 2 vai trò:
  1. **Auditor** (`Trần Minh Hoàng` — Senior Auditor Big 4 / IPO Assurance):
     - **Thẩm định & Kiểm tra độc lập**: Kiểm toán viên có toàn quyền xem xét hồ sơ dữ liệu, cấu trúc trường PII, danh mục quy tắc tuân thủ (compliance rules), bằng chứng kiểm toán (Audit Evidence, chuỗi SHA-256 bất biến, chữ ký số `SIG-AIRFLOW-3LANE`), đồ thị Lineage, báo cáo kết quả kiểm tra và **có quyền kích hoạt lượt chạy kiểm tra (`startPipelineRun`)** để độc lập kiểm chứng dữ liệu và tạo bộ bằng chứng kiểm toán mới.
     - **Ranh giới bảo vệ**: Auditor không có quyền thay đổi, phê duyệt hoặc từ chối quy tắc xử lý dữ liệu (Rule Engine), không được can thiệp vào bản ghi cách ly (Quarantine remediation/override) hay thay đổi trạng thái Finding.
  2. **Admin** (`Nguyễn Quốc Bảo` — Lead Data Platform):
     - Toàn quyền quản trị, điều hành kỹ thuật, khởi chạy pipeline kiểm tra (`[ Chạy kiểm tra ]`), xem xét cảnh báo và phê duyệt remediation tại các chốt chặn HITL.
- **User Profile & Badge**: Hiển thị avatar viết tắt (`TH` / `QB`), tên người dùng và badge vai trò (`Kiểm toán viên (Viewer)` / `Quản trị viên hệ thống`).

## 2.2. Sidebar

```text
DataTrust OS

🏠 Trang chủ
   AI Admin

▶ Lần chạy
   Run history

◇ Data Lineage
   Truy vết dữ liệu

🛡 Kiểm soát truy cập
   Real-time access

⚖ Quy tắc & Chính sách
   Applied rules

🔴 Quarantine
   Failed records

📊 Dashboard
   Compliance overview

```

### Behavior

- Active item có background teal rất nhạt + teal icon/text.
- Sidebar expanded mặc định.
- Có thể collapse.
- Khi collapsed chỉ hiển thị icon + tooltip.
- Topbar luôn sticky.

## 2.3. Dual-pane workspace

- Sau Sidebar, vùng nội dung giữ bố cục hiện tại gồm AI Chat cố định bên trái và workspace nghiệp vụ bên phải.
- AI Chat tồn tại xuyên suốt các route, không chỉ ở Trang chủ.
- Chuyển route không được tự động xóa hội thoại đang dùng; chat nhận context rõ ràng bằng `datasetId`, `runId` và `findingId` khi có.
- Nội dung và hành động chính của từng màn hình vẫn nằm trong workspace bên phải theo spec.
- Hai pane cuộn độc lập trên desktop; ở viewport hẹp, chat chuyển thành drawer/pane đóng mở được.

---

# 3. Routes

Đề xuất route structure:

```text
/
 /audit
 /runs
 /runs/:runId
 /runs/:runId/results
 /runs/:runId/findings
 /runs/:runId/lineage
 /runs/:runId/evidence
 /lineage
 /access-control
 /rules
 /quarantine
 /dashboard
```

Nếu project hiện tại đã có routing convention khác, giữ convention hiện tại nhưng mapping UI phải tương đương.

---

# 28. Navigation rules

## User journey 1 — Audit dataset

```text
Trang chủ
→ Chọn dataset
→ Xem rules đang áp dụng
→ Start Run
→ Run Monitoring
→ Run Results
```

## User journey 2 — Investigate failure

```text
Run Results
→ Fail
→ Finding
→ AI Explanation
→ RCA
→ Lineage
→ Evidence
→ Quarantine
```

## User journey 3 — Approve remediation

```text
Finding
→ AI Analysis
→ Suggested remediation
→ Review
→ Approve/Reject
```

## User journey 4 — Historical audit

```text
Lần chạy
→ Chọn Run
→ Results
→ Findings
→ Evidence
```

---
