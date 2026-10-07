# DataTrust OS — Acceptance criteria, ưu tiên và Definition of Done

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 29, 31, 32. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 29. Acceptance criteria

## 0. Visual continuity and dual-pane shell

- Giữ palette, font và visual tokens hiện tại; không redesign giao diện.
- Trên desktop, AI Chat companion luôn nằm cố định bên trái và workspace nghiệp vụ ở bên phải.
- Hai pane có vùng cuộn độc lập; chat duy trì hội thoại/context khi chuyển màn hình.
- Trên viewport hẹp, chat có thể mở/đóng mà không che mất hoặc làm mất nội dung nghiệp vụ.
- AI Chat không tự thực hiện các quyết định hoặc mutation thuộc trách nhiệm của Admin/Auditor.

## A. Dataset selection

- Admin mở Trang chủ.
- Có thể search dataset.
- Có thể chọn dataset.
- UI hiển thị metadata cơ bản.

## B. Applied rules visibility

- Hệ thống hiển thị các rule đang áp dụng cho dataset đã chọn.
- Admin/Auditor chỉ xem để biết phạm vi kiểm tra; không chọn/bỏ chọn hoặc approve/reject rule.
- Không có UI tạo rule mới bằng AI.

## C. Run

- Admin có thể start run.
- UI hiển thị status.
- UI hiển thị pipeline steps.
- UI hiển thị progress.

## D. Result

- Hiển thị Pass / Fail / Warning / Not Evaluated.
- Có KPI.
- Có drill-down.
- Fail có thể dẫn tới Finding.

## E. Finding

- Có severity.
- Có rule.
- Có policy.
- Có dataset/column.
- Có failed record count.
- Có reason/impact.
- Có action bar.

## F. AI

- Có AI explanation.
- Có RCA.
- Có remediation suggestion.
- Có confidence.
- Có Approve/Reject.
- Không có rule-generation flow.

## G. Lineage

- Có graph.
- Có nodes + edges.
- Click node mở detail.
- Từ Finding mở được lineage.
- Có thể xem path đến Quarantine.

## H. Evidence

- Có run ID.
- Có rule execution.
- Có input/output.
- Có timestamp.
- Có lineage hash.
- Evidence immutable.
- Có export/download nếu backend hỗ trợ.

## I. Quarantine

- List quarantined records.
- Filter/search.
- Detail drawer.
- Có violation reason.
- Có rule.
- Có severity.
- Có lineage hash.
- Không có Edit Source Record.

## J. Access Control

- KPI real-time.
- Trend chart.
- Alerts.
- Access activity table.
- Filter/search.
- Status allowed/denied.

---

# 31. Coding priorities

Code theo thứ tự sau:

```text
P0
AppShell
Sidebar
Topbar
Dual-pane AI Chat + Workspace
Routing
Preserve current palette and typography
Dataset Selector

P1
Run creation
Run Monitoring
Run Results
Findings

P2
AI Explanation
HITL Remediation
Data Lineage
Quarantine
Evidence

P3
Real-time Access Control
Dashboard
Run History
Export
```

Nếu thời gian hạn chế, ưu tiên P0 → P1 → P2.

---

# 32. Definition of Done

Feature được coi là hoàn thành khi Admin có thể thực hiện đầy đủ:

```text
Login
  ↓
Chọn dataset
  ↓
Xem rules đang áp dụng
  ↓
Start Run
  ↓
Theo dõi pipeline
  ↓
Xem Pass/Fail/Warning/Not Evaluated
  ↓
Mở Finding
  ↓
Xem Rule + Policy
  ↓
AI Explain + RCA
  ↓
Trace Lineage
  ↓
Xem Evidence
  ↓
Xem Quarantine record
  ↓
Review AI remediation
  ↓
Approve / Reject
  ↓
Xem lại audit history/dashboard
```

Toàn bộ flow phải giữ nguyên nguyên tắc:

```text
AI suggests
      ↓
Human decides
      ↓
System executes
```

Và tuyệt đối không có flow:

```text
AI
 ↓
Create new rule
```
