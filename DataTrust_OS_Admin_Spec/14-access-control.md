# DataTrust OS — Giám sát truy cập thời gian thực

> Vai trò: **Admin**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 17. Nội dung các phần này được giữ nguyên.

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [Thiết kế và tương tác dùng chung](02-design-system-and-interactions.md)
- [Điều hướng](03-app-shell-and-navigation.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 17. Real-time Access Control

Route:

```text
/access-control
```

Mục tiêu: Admin giám sát ai đang truy cập dữ liệu trong thời gian thực.

## 17.1. KPI cards

```text
Tổng yêu cầu truy cập     1,248
Yêu cầu hợp lệ            1,203
Yêu cầu bị từ chối           45
Thời gian xử lý trung bình 230 ms
```

## 17.2. Trend

Chart:

```text
X-axis: time
Y-axis: requests

Series:
- Allowed
- Denied
- Alert
```

## 17.3. Resource distribution

Donut/chart:

```text
Cơ sở dữ liệu
Hồ sơ khách hàng
Báo cáo
Hệ thống nội bộ
Khác
```

## 17.4. Real-time alerts

Example:

```text
🔴 Truy cập bất thường
user_temp từ IP ...
truy cập bảng customer_data
ngoài giờ làm việc.

🟡 Vượt quota
sales01 truy cập dữ liệu nhạy cảm
nhiều hơn bình thường.

🔵 Đăng nhập mới
Admin02 đăng nhập từ IP mới.
```

## 17.5. Real-time access table

Columns:

```text
Time
User
Role
Resource
Action
Result
Source IP
Details
```

Examples:

```text
14:32:09
user_analytics
Analyst
customer_data
SELECT
Allowed
10.12.34.56

14:31:47
sales01
Sales
customer_data
SELECT
Denied
203.0.113.45
Quota exceeded
```

---

