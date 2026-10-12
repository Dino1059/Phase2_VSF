# DataTrust OS — App shell, routes và user journeys

> Vai trò: **Admin & Auditor**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 2, 3, 28. Cập nhật theo chuẩn **Dual-Pane toàn cục** (`example/base_UI.png`).

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Data Lineage](10-data-lineage.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 2. Global application shell

## 2.1. Layout Dual-Pane Toàn cục (Chuẩn `example/base_UI.png`)

Toàn bộ ứng dụng chạy trên layout 3 cột cố định theo chiều ngang (`h-screen w-screen overflow-hidden`):

```text
┌───────┬──────────────────────────────┬────────────────────────────────────────────────────────┐
│ Rail  │ Persistent AI Chat Pane      │ Dynamic Workspace Canvas                               │
│ (68px)│ (w-[380px]-w-[430px])        │                                                        │
├───────┼──────────────────────────────┼────────────────────────────────────────────────────────┤
│  ⚡   │ DataTrust AI Orchestrator 💬 │ [Icon] TIÊU ĐỀ PHÂN HỆ      [Auditor|Admin] [User Pill]│
│  Logo │ ● đang trực tuyến    Chat mới├────────────────────────────────────────────────────────┤
│       │                              │ {children} Dynamic Content                             │
│  🏠   │ Hội thoại xuyên suốt         │ - /overview: Greeting, Dataset Select, 4 Task Arch     │
│  Home │ Context chips (8 datasets)   │ - /runs: Workspace Phả hệ (DAG Lineage & Schema Diff)  │
│       │ Message bubbles & quick acts │ - /rules: Ma trận Quy tắc & Chính sách                 │
│  🔀   │                              │ - /findings/:id: Finding Detail & Lineage Tab          │
│  Runs │                              │                                                        │
│       │                              │                                                        │
│  📋   │                              │                                                        │
│ Rules │ [ Nhắn cho Orchestrator... ↑]│                                                        │
│       ├──────────────────────────────┤                                                        │
│  GSM  │ < / > (Toggle Chevron)       │                                                        │
└───────┴──────────────────────────────┴────────────────────────────────────────────────────────┘
```

### 2.1.1. Topbar & Role Switcher (Auditor vs Admin)

Topbar nằm ở đỉnh của Dynamic Workspace Canvas:
- **Tiêu đề khu vực (Breadcrumb Title)**: Biểu tượng cyan + Tên phân hệ viết hoa (`TRANG CHỦ`, `LẦN CHẠY & LINEAGE`, `QUY TẮC & CHÍNH SÁCH`, `VẤN ĐỀ PHÁT HIỆN`).
- **Nút bật/tắt AI Chat trên di động**: `[✨ AI Chat]` (hiển thị khi viewport `< lg`).
- **Bộ chuyển đổi vai trò (Role Switcher)**: Cho phép chuyển đổi qua lại giữa 2 vai trò:
  1. **Auditor** (`Trần Minh Hoàng` — Senior Auditor Big 4 / IPO Assurance):
     - **Thẩm định & Kiểm tra độc lập**: Toàn quyền xem xét hồ sơ dữ liệu, cấu trúc trường PII, danh mục quy tắc tuân thủ, bằng chứng kiểm toán (Audit Evidence, SHA-256 bất biến, chữ ký số `SIG-AIRFLOW-3LANE`), đồ thị Lineage và **có quyền kích hoạt lượt chạy kiểm tra (`startPipelineRun`)** để độc lập kiểm chứng dữ liệu.
     - **Ranh giới bảo vệ**: Auditor không có quyền sửa/phê duyệt quy tắc xử lý, không can thiệp cách ly (Quarantine override).
  2. **Admin** (`Nguyễn Quốc Bảo` — Lead Data Platform):
     - Toàn quyền quản trị, điều hành kỹ thuật, khởi chạy pipeline kiểm tra (`[ Chạy kiểm tra ]`), xem xét cảnh báo và phê duyệt remediation tại các chốt chặn HITL.
- **User Profile Pill**: Hiển thị avatar viết tắt (`TH` / `QB`), tên người dùng và badge vai trò.

---

## 2.2. Slim Vertical Icon Rail (`w-[68px]`)

Thanh điều hướng biểu tượng siêu gọn đặt tại bìa trái (`w-[68px] shrink-0 border-r border-[#e2ece8] bg-white`):
- **Logo Brand**: Khối bo tròn màu đen với biểu tượng tia chớp cyan (`size-11 rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40`).
- **Danh mục Điều hướng Cốt lõi** (Đã bỏ tab "Kết quả"):
  1. **Trang chủ:** `/overview` (icon `LayoutGrid`)
  2. **Lần chạy & Lineage:** `/runs` (icon `Workflow`)
  3. **Quy tắc & Chính sách:** `/rules` (icon `CheckSquare`)
- **Footer Rail**:
  - Nút bật nhanh AI Chat trên di động (icon `Sparkles`).
  - Huy hiệu `GSM` Global (Chiến dịch V35 · 24 thị trường).

### Accessibility (a11y) & Bàn phím:
- Mỗi icon link có `aria-label`, native `title`, và floating tooltip `role="tooltip"` khi hover/focus.
- Trạng thái trang hiện tại mang thuộc tính `aria-current="page"` và styling active `bg-[#04D3D4]/15 border border-[#04D3D4]/40 text-[#04D3D4]`.
- Vùng focus bàn phím rõ nét: `focus-visible:ring-2 focus-visible:ring-[#04D3D4] focus-visible:ring-offset-2`.
- Cấu trúc ngữ nghĩa: bọc trong `<nav aria-label="Điều hướng chính">`.

---

## 2.3. Persistent AI Chat Pane (Companion Xuyên suốt)

- **Cố định cấp Shell**: Nhúng trực tiếp trong `AppShell`. Giữ nguyên phiên làm việc, lịch sử hội thoại và nội dung ô nhập liệu khi người dùng chuyển tab/trang.
- **Chiều rộng**: `w-[380px] lg:w-[410px] xl:w-[430px]` khi mở, `w-0 overflow-hidden` khi thu gọn.
- **Nút Chevron Toggle `<` / `>`**:
  - Đặt tại ranh giới giữa AI Chat và Workspace.
  - Phím tắt bàn phím: `Alt + [`.
  - Hỗ trợ đầy đủ `aria-label` ("Thu gọn khung AI Chat" / "Mở rộng khung AI Chat") và `aria-expanded`.
- **Responsive trên Màn hình nhỏ (`< 1024px`)**:
  - Khi màn hình nhỏ hơn `lg`, AI Chat tự động chuyển thành **slide-over drawer** kèm backdrop làm mờ `bg-slate-950/40`.
  - Workspace giữ trọn 100% diện tích mà không bị co ép layout.
- **Hỗ trợ `prefers-reduced-motion`**:
  - Tất cả các hiệu ứng thu/mở áp dụng `motion-reduce:transition-none motion-reduce:transform-none`.

---

## 2.4. Dynamic Workspace Canvas

- Chiếm toàn bộ phần còn lại bên phải (`flex-1 min-w-0 h-full overflow-hidden flex flex-col`).
- Header Topbar cố định ở đỉnh.
- Vùng nội dung `<main id="main-content" aria-label="Không gian làm việc" className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-7">` cuộn độc lập.

---

# 3. Routes & Redirects

Cấu trúc URL chuẩn hóa:

```text
/                      → Redirect /overview
/overview              → Trang chủ (Dashboard chào mừng & Kiến trúc 4 Tasks)
/runs                  → Workspace Phả hệ Lần chạy (DAG Lineage & Schema Diff)
/runs/:id              → Workspace Phả hệ của Run cụ thể
/runs/:runId/results   → Bảng tổng hợp KPIs của Run
/runs/:runId/findings  → Danh sách Findings của Run
/runs/:runId/lineage   → View Lineage của Run
/rules                 → Phê duyệt Quy tắc & Quản lý Chính sách
/findings              → Danh sách Findings
/findings/:id          → Finding Detail (kèm Tab Data Lineage thu gọn)

Redirects & Backwards Compatibility:
/results               → Redirect /runs (Đã loại bỏ tab Kết quả độc lập)
/lineage               → Redirect /runs (Lineage tích hợp trong Run Workspace)
/dashboard             → Redirect /runs
/data-quality          → Redirect /runs
/evidence              → Redirect /runs
/pipeline-runs         → Redirect /runs
/pipeline-runs/:id     → Redirect /runs/:id
```

---

# 28. Navigation rules & User journeys

## User journey 1 — Audit dataset & View Lineage
```text
Trang chủ (/overview)
→ Chọn dataset
→ Chạy kiểm tra (Start Run)
→ Workspace Lần chạy (/runs/:id)
→ Xem DAG Lineage thực tế & Schema Diff
```

## User journey 2 — Investigate Finding with Scoped Lineage
```text
Run Workspace (/runs/:id)
→ Nhấn [Findings]
→ Chọn Finding (/findings/:id)
→ Tab Data Lineage (Xem subgraph truy vết theo cột/lỗi của Finding)
→ Xem Root Cause & AI Explanation
→ Duyệt Đề xuất Remediation (HITL)
```

## User journey 3 — Trace Column Upstream / Downstream
```text
Run Workspace (/runs/:id)
→ Chuyển tab So sánh Schema Diff & Cột
→ Chọn cột nghi vấn (VD: phone, national_id)
→ Nhấn [Truy vết] (?column=phone)
→ DAG Lineage tự động highlight luồng đi của cột qua các node chuyển đổi
```
