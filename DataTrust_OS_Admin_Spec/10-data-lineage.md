# DataTrust OS — Đồ thị truy vết dữ liệu (Data Lineage)

> Vai trò: **Admin & Auditor**. Đọc [README.md](README.md) trước khi triển khai.
> Phần tương ứng trong spec gốc: 12. Cập nhật kiến trúc **Unified Lineage Engine** (Loại bỏ Marquez, gắn chặt với Run và Finding).

## Tài liệu liên quan

- [Phạm vi sản phẩm](01-product-scope.md)
- [App shell & Điều hướng](03-app-shell-and-navigation.md)
- [Danh sách và chi tiết Finding](08-findings.md)
- [Data model](16-data-models.md)
- [API và realtime](18-api-and-realtime.md)
- [Acceptance và bàn giao](19-acceptance-and-delivery.md)

---

# 12. Data Lineage

## 12.1. Kiến trúc Lineage Nội bộ (Unified Lineage Engine)

Hệ thống **không sử dụng Marquez** hay dịch vụ metadata bên ngoài độc lập. Toàn bộ phả hệ dữ liệu được sinh và quản lý bởi **Unified Lineage Engine nội bộ** chuẩn OpenLineage 1.0:
- **Xây dựng từ metadata thực tế của từng Run**: Graph được dựng từ dữ liệu thực thi thực tế của từng lần chạy (`source → transformation → target`), lưu vết qua các task instance của Airflow và bảng schema PostgreSQL, phản ánh chính xác dữ liệu thực tế thay vì một sơ đồ 8 stage tĩnh.
- **Ranh giới điều hướng**: Bỏ trang `/lineage` độc lập (tự động redirect về `/runs`). Lineage được truy cập tại 2 điểm ngữ cảnh rõ ràng:
  1. **Workspace Lần chạy (`/runs`, `/runs/:id`)**: Xem toàn bộ đồ thị Lineage và Schema Diff của pipeline trong lần chạy đó.
  2. **Finding Detail (`/findings/:id` - Tab Data Lineage)**: Mặc định hiển thị scoped subgraph chỉ gồm các node, edge và cột liên quan trực tiếp đến Finding.
- **Giới hạn trong lần run đó**: Dữ liệu lineage gắn chặt với `run_id` hiện tại, không cho phép chọn sai lệch dataset hay run khác bên trong canvas lineage.

---

## 12.2. Hai chế độ hiển thị (View Switcher)

Workspace Lineage cung cấp 2 chế độ xem linh hoạt:

### Chế độ 1: Sơ đồ Thực thi (DAG Lineage)
Hiển thị đồ thị tương tác của luồng xử lý:

```text
┌─────────────────────────┐
│ Source DB (PostgreSQL)  │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Task 1: Ingestion       │ (bronze.dataset · row count · duration)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Task 2: Profiling       │ (null rate · PII detection · health score)
└────────────┬────────────┘
             │
             ├────────────────────────────────┐
             ▼                                ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│ Lane A: Technical Rules │      │ Lane B: Compliance Policy│
│ (L1-L4 DQ Checks)       │      │ (Luật 91, GDPR, US PII) │
└────────────┬────────────┘      └────────────┬────────────┘
             │                                │
             └────────────────┬───────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │ Lane C: Convergence     │
                 └──────┬───────────┬──────┘
                        │           │
           (Violations) │           │ (Compliant)
                        ▼           ▼
        ┌──────────────────┐    ┌──────────────────┐
        │ Quarantine Table │    │ Silver Standard  │
        │ (Audit Evidence) │    │ (Published Lake) │
        └──────────────────┘    └──────────────────┘
```

### Chế độ 2: So sánh Schema Diff & Cột
Bảng so sánh chi tiết sự biến đổi schema giữa Source (Bronze) và Output (Silver):
- **Cột Source (Bronze)** vs **Cột Output (Silver)**.
- **Kiểu dữ liệu**: Phát hiện type coercion (VD: `VARCHAR → TIMESTAMP`, `FLOAT → INT`).
- **Phân loại PII & Masking**: Hiển thị trạng thái xử lý dữ liệu cá nhân (VD: `Plaintext → Hashed / Masked`).
- **Trạng thái**: `PASSED`, `TRANSFORMED`, `QUARANTINED`, `DROPPED`.
- **Nút [Truy vết] theo cột**: Cho phép click vào bất kỳ cột nào để chuyển ngay sang DAG Lineage với bộ lọc `?column=<col_name>`.

---

## 12.3. Khả năng Truy vết Upstream / Downstream (Column-Level Tracing)

- **Lọc theo cột (`?column=...`)**:
  - Khi người dùng click nút [Truy vết] tại bảng Schema Diff hoặc từ Finding:
  - Hệ thống tự động lọc và làm nổi bật (highlight) toàn bộ đường dẫn từ cột nguồn qua các bước biến đổi đến bảng đích (Silver hoặc Quarantine).
  - Các node và cạnh không liên quan được làm mờ để người dùng tập trung soi sâu vào luồng dữ liệu của cột đó.
- **Truy vết theo Node**:
  - Click vào bất kỳ node nào trong đồ thị sẽ kích hoạt chế độ Highlight liên kết:
    - **Upstream**: Chiếu sáng tất cả các node tiền nhiệm đã cấp dữ liệu cho node này.
    - **Downstream**: Chiếu sáng tất cả các node kế tiếp nhận dữ liệu từ node này.
  - Thanh toolbar hiển thị huy hiệu `Đang truy vết: <Node_Name>` kèm nút `[Bỏ chọn]`.

---

## 12.4. Phân loại Node & Màu sắc Nhất quán

Mỗi loại node được hiển thị với màu sắc và icon nhận diện chuẩn hóa:
- **SOURCE**: Bảng nguồn dữ liệu thô (Icon `Database` · Xanh lam / Slate).
- **INGEST**: Tác vụ nạp dữ liệu và catalog (Icon `Layers` · Cyan).
- **TRANSFORM**: Tác vụ làm sạch và chuẩn hóa (Icon `GitFork` · Teal).
- **POLICY / DQ CHECK**: Tác vụ kiểm tra chất lượng & tuân thủ luật (Icon `Scale` · Indigo / Amber).
- **QUARANTINE**: Khu vực cách ly bản ghi vi phạm (Icon `AlertOctagon` · Đỏ hồng).
- **SILVER / PUBLISH**: Bảng dữ liệu sạch đạt chuẩn IPO (Icon `CheckCircle2` · Xanh lục).
- **AUDIT**: Chữ ký số và băm bằng chứng kiểm toán (Icon `ShieldCheck` · Vàng kim).

---

## 12.5. Chi tiết Node (Right Drawer)

Click vào bất kỳ node nào sẽ mở Drawer trượt từ bên phải:
- **Tên node & Loại node**: Tên kỹ thuật và vai trò trong pipeline.
- **Run ID**: Mã định danh lần chạy (`run_id`).
- **Dataset**: Tên bảng / schema tương ứng.
- **Số bản ghi (Records)**: Tổng số dòng quét qua node.
- **Cảnh báo PII**: Đánh dấu có chứa dữ liệu cá nhân hay không.
- **Thời gian thực thi (Execution Duration)**: Thời lượng thực tế chạy task (tính theo giây/milis).
- **Schema cột**: Danh sách các cột thuộc node kèm kiểu dữ liệu.

---

## 12.6. Lineage Controls & Actions

Thanh công cụ điều khiển đồ thị hỗ trợ:
- **Làm mới (`RotateCw`)**: Tải lại dữ liệu lineage mới nhất từ backend.
- **Thu/Phóng (`ZoomIn` / `ZoomOut`)**: Điều chỉnh tỷ lệ từ 50% đến 200%.
- **Đặt lại góc nhìn (`Maximize2` / `Fit`)**: Đưa đồ thị về trung tâm màn hình.
- **Sao chép Evidence Hash**: Nút copy mã băm SHA-256 bất biến của lần chạy.
- **Export OpenLineage 1.0 JSON (`Download`)**: Xuất toàn bộ đặc tả graph theo định dạng chuẩn OpenLineage 1.0 để nộp hồ sơ kiểm toán độc lập.
- **Điều hướng nhanh**:
  - Nút `[Xem KPIs]`: Chuyển sang `/runs/:runId/results`.
  - Nút `[Findings]`: Chuyển sang `/runs/:runId/findings`.
  - Nút `[Chạy mới]`: Mở modal khởi tạo lượt chạy pipeline mới.
