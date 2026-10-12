# DataTrust OS — Lịch sử & Workspace Lần chạy (Run Lineage Workspace)

> Vai trò: **Admin & Auditor**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 19. Cập nhật: Chuyển đổi tab Lần chạy thành **Workspace Phả hệ Lần chạy** (`/runs`).

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [App shell & Điều hướng](03-app-shell-and-navigation.md)
- [Data Lineage](10-data-lineage.md)
- [Run Result Dashboard](07-run-results.md)
- [Danh sách Findings](08-findings.md)

---

# 19. Workspace Lần chạy (Run Lineage Workspace)

Route:

```text
/runs
/runs/:id
```

## 19.1. Vai trò của Phân hệ Lần chạy trong Dual-Pane

Toàn bộ UI của tab Lần chạy được tinh gọn để đóng vai trò làm **Workspace Phả hệ chuyên biệt của từng Lần chạy**:
- Không còn bảng danh sách tĩnh rời rạc.
- Tập trung vào **DAG Lineage tương tác** và **So sánh Schema Diff** của lần chạy hiện tại.
- Giữ vững thiết kế Dual-Pane: AI Chat cố định bên trái đồng hành giải thích các bước thực thi.

## 19.2. Thanh Điều khiển & Bộ chuyển đổi Lần chạy (Run Switcher Dropdown)

Tại đỉnh của Workspace:
- **Run Switcher Dropdown**: Dropdown chọn nhanh các lần chạy gần nhất:
  - Hiển thị: `Mã Lần chạy (Dataset · Giờ chạy)`.
  - Thay đổi giá trị sẽ điều hướng ngay sang `/runs/:newRunId`.
- **Huy hiệu Trạng thái**: `COMPLETED`, `RUNNING`, `FAILED`.
- **Thanh chỉ số & Evidence Hash**:
  - Số lượng quét thô (`scannedCount`).
  - Silver chuẩn (`silverCount`).
  - Quarantine cách ly (`quarantineCount`).
  - Cảnh báo (`warningCount`).
  - Mã băm chứng cứ kiểm toán `SHA-256` bất biến kèm nút Copy.
- **Nhóm hành động nhanh (Action Buttons)**:
  - `[Xem KPIs]`: Điều hướng sang Dashboard kết quả `/runs/:runId/results`.
  - `[Findings (<count>)]`: Điều hướng sang danh sách cảnh báo vi phạm `/runs/:runId/findings`.
  - `[Chạy mới]`: Mở modal khởi chạy pipeline kiểm tra dữ liệu mới.
  - `[OpenLineage 1.0]`: Xuất file JSON phả hệ dữ liệu chuẩn mở.

---

## 19.3. Hai chế độ tương tác bên trong Workspace

1. **Sơ đồ Thực thi (DAG Lineage)**:
   - Đồ thị SVG trực quan các task thực tế (Task 1 Ingest $\to$ Task 2 Profiling $\to$ Task 3 3-Lane $\to$ Task 4 Evidence).
   - Xem chi tiết từng node qua Drawer trượt bên phải.
   - Hỗ trợ zoom in/out, fit view, truy vết theo node.

2. **So sánh Schema Diff & Cột**:
   - So sánh chi tiết các trường giữa Bronze Source và Silver Target.
   - Nút `[Truy vết]` theo từng cột chuyển ngay về đồ thị với luồng dẫn highlight.
