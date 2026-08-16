# Báo cáo Phân tích Dữ liệu (raw_public_v2) - Đã Cập Nhật

Dưới đây là các số liệu thống kê tổng quan và chi tiết sau khi điều chỉnh:

## 1. VED (Vehicle Telemetry)
*File: `vehicle_telemetry_raw.csv`*

- **Tổng số bản ghi (Total Records):** **55,169**
- **Tần số lấy mẫu (Sampling Rate):** **~1.43 Hz** (dựa trên trung vị thời gian).
- **Khoảng thời gian (Interval) giữa các timestamp (theo từng chuyến xe):**
  - **Min:** 100.0 ms
  - **Max:** 2,341,700.0 ms (~39 phút)
  - **Median:** 700.0 ms

## 2. ACN (Trạm sạc EV)
*Folder: `ACN/`*

- **Tổng số lượt sạc (Total Sessions):** **19,181**
- **Thời gian Session trung bình:** **6.48 giờ** 
- **Khoảng thời gian (Interval) giữa các lượt kết nối (ConnectionTime):**
  - **Min:** 0.0 giây
  - **Max:** 1,899,688.0 giây (~22 ngày)
  - **Median:** 421.0 giây (~7 phút)

## 3. Ride Hailing (Dữ liệu gọi xe)
*File: `Ride Hailing/fact_rides.csv`*

- **Tổng số cuốc xe (Total Records/Trips):** **25,003**
- **Số chuyến đi mỗi ngày:** **~66.67 trips/ngày** 
  *(Tổng cộng 25,003 chuyến đi rải rác trong 375 ngày).*
- **Khoảng thời gian (Interval) giữa các cuốc xe (theo từng tài xế):**
  - **Min:** 60.0 giây
  - **Max:** 11,851,440.0 giây (~137 ngày)
  - **Median:** 870,000.0 giây (~10 ngày)
