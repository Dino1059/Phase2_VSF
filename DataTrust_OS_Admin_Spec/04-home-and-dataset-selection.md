# DataTrust OS — Trang chủ và chọn dataset

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 4. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 4. Trang chủ — AI Admin & Assurance

## 4.1. Mục tiêu

Đây là entry point cho **Admin** (Quản trị viên) và **Auditor** (Kiểm toán viên).

Người dùng bắt đầu bằng cách chọn dataset cần kiểm tra / rà soát tuân thủ.

Trang chủ sử dụng layout dual-pane:
- **AI Chat companion (bên trái)**: Cố định bên trái (380-420px), hiển thị đầy đủ danh sách cả **8 bộ dữ liệu PostgreSQL** (`ride_hailing_xanh_sm_trips`, `dim_customers`, `dim_drivers`, `feedback_pii`, `fleet_index`, `acn_charging_mapped`, `synthetic_ev_telemetry_ved_ref`, `synthetic_feedback_scenario_driven`) qua quick action chips và gợi ý tương tác.
- **Main Workspace (bên phải)**: Trạng thái ban đầu (Initial state), modal chọn dataset và trạng thái sau khi đã chọn dataset.

## 4.2. Initial state (Chưa chọn dataset)

```text
┌──────────────────────────────────────────────────────────┐
│ Xin chào, Admin / Auditor (Viewer)                       │
│ Tôi có thể giúp bạn kiểm tra tuân thủ dữ liệu.           │
│                                                          │
│ Dataset cần kiểm tra?                                    │
│                                                          │
│ [ Chọn dataset ]                                         │
│                                                          │
│ Bộ dữ liệu sẵn có trong hệ thống (PostgreSQL):           │
│ [ride_hailing_xanh_sm_trips] [dim_customers] ...         │
└──────────────────────────────────────────────────────────┘
```

> **Ghi chú cập nhật**:
> - Đã bỏ ô tìm kiếm dataset `[ 🔍 Tìm dataset... ]` và dải phân cách `hoặc` trong thẻ chào mừng Initial State theo yêu cầu tinh gọn giao diện. Thao tác chọn dataset được thực hiện qua nút `[ Chọn dataset ]` (mở Modal) hoặc bấm trực tiếp vào các chip dataset sẵn có.
> - Đã bỏ hiển thị số lượng cột trên các chip dataset; chỉ giữ tên dataset và chấm tròn chỉ báo PII.

## 4.3. Dataset selector (Modal chọn dataset)

Modal:

```text
┌─────────────────────────────────────────────────────────────┐
│ Chọn dataset                                            ×  │
├─────────────────────────────────────────────────────────────┤
│ 🔍 Tìm dataset trong danh mục...                           │
├─────────────────────────────────────────────────────────────┤
│ ○ ride_hailing_xanh_sm_trips                               │
│   PostgreSQL (bronze.ride_hailing_xanh_sm_trips)            │
│   · 6,902 records · PII: Có (1 trường định danh)            │
│                                                             │
│ ○ dim_customers                                            │
│   PostgreSQL (bronze.dim_customers)                         │
│   · 5,106 records · PII: Có (4 trường dữ liệu cá nhân)      │
│                                                             │
│ ○ acn_charging_mapped                                      │
│   PostgreSQL (bronze.acn_charging_mapped)                   │
│   · 912 records · PII: Không                                │
├─────────────────────────────────────────────────────────────┤
│                              [Hủy] [Chọn dataset]          │
└─────────────────────────────────────────────────────────────┘
```

### Dataset item hiển thị
- `dataset name`: Tên định danh chuẩn của bảng (8 bảng thực tế trong PostgreSQL).
- `source`: Nguồn bảng lưu trữ thực tế (`bronze.<table_name>`).
- `số bản ghi (records)`: Tổng số lượng dòng dữ liệu thực tế.
- `PII indicator`: Phân loại dữ liệu cá nhân theo Luật 91/2025/QH15 & GDPR.
- `description`: Mô tả nghiệp vụ nếu có.
*(Đã loại bỏ hiển thị số lượng cột theo feedback để tránh gây nhiễu và tập trung vào chỉ số an toàn dữ liệu PII)*.

## 4.4. Dataset selected state (Đã chọn dataset)

Sau khi chọn dataset, hệ thống hoàn tất phân tích metadata và hiển thị:

```text
Tôi đã phân tích metadata của ride_hailing_xanh_sm_trips.

Dataset
ride_hailing_xanh_sm_trips
PII: Có dữ liệu cá nhân

[ Trường dữ liệu cá nhân ]   [ Định danh trực tiếp ]   [ Dữ liệu cá nhân theo ngữ cảnh ]
1 personal-data fields       1 direct identifiers      0 contextual fields

Các compliance rules hiện có:
[ Xem rule ]

[ Chạy kiểm tra ] | [ Xem kết quả kiểm toán ]
```

> **Quy tắc phân quyền và hành động**:
> 1. **Bỏ hiển thị tổng số cột**: Màn hình chỉ tập trung vào 3 chỉ số trọng yếu về dữ liệu cá nhân và bảo mật theo luật (Personal-data fields, Direct identifiers, Contextual fields).
> 2. **Xem rule**: Chỉ mở danh sách read-only các rule đang áp dụng cho dataset đã chọn. Cả Admin và Auditor không chọn/bỏ chọn, approve/reject hoặc chỉnh sửa rule tại bước này.
> 3. **Hành động chính theo Role**:
>    - Cả **Admin** và **Auditor** đều có quyền nhấn `[ Chạy kiểm tra ]` để mở Start Run Modal và kích hoạt lượt chạy kiểm tra qua Adaptive Pipeline run (`startPipelineRun`), cũng như có thể chọn `[ Xem kết quả kiểm toán ]` để xem kết quả kiểm tra gần nhất.
>    - **Ranh giới**: Khác với Admin (người có quyền can thiệp HITL, phê duyệt quy tắc và khắc phục bản ghi cách ly), lượt chạy do Auditor kích hoạt thuần túy phục vụ thẩm tra độc lập và tạo bằng chứng kiểm toán (Audit Trail ghi nhận `actor_role = 'AUDITOR'`); Auditor không có quyền can thiệp/phê duyệt rule trước và sau khi chạy.

---
