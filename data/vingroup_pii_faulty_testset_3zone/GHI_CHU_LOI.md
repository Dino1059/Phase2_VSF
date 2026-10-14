# Ghi chú bộ dữ liệu lỗi 3 zone (bản duy nhất)

Thư mục này là **bộ dữ liệu thử nghiệm duy nhất** dùng để chấm điểm phát hiện lỗi dữ liệu (Lane A) và phát hiện thông tin cá nhân (Lane B) trên 3 zone. Các bộ cũ `vingroup_pii_testset_3zone/` và `vingroup_pilot_dataset_3zone copy/` đã bị xoá.

## 1. Tổng quan

| Thông tin | Giá trị |
|---|---|
| Thời gian | **10 ngày**, ngày 0–9 (01/01 – 10/01/2026) |
| Đội xe | 60 xe, chia 3 zone, mỗi zone 20 xe: EU (VF8VNF_0001–0020), VN (0021–0040), US (0041–0060) |
| Nguồn sạch | `../vingroup_clean_3zone_pilot/` (15 ngày, không lỗi), cắt còn 10 ngày |
| Hạt giống ngẫu nhiên | 42 (chạy lại cho kết quả y hệt) |
| Đáp án lỗi dữ liệu | `fault_manifest.json` (465 lỗi) |
| Đáp án thông tin cá nhân | `pii_injection_manifest.json` |
| Đáp án luật theo zone (Lane B) | `lane_b_manifest.json` (21 lần chạy, xem phần cuối) |

### Danh sách file

| File | Số dòng | Có lỗi tiêm? |
|---|---|---|
| `synthetic_ev_telemetry_ved_ref.csv` | 57.600 (60 xe × 10 ngày × 96 mẫu) | Có: F1, F2, F3, F10, F11. Thêm cột Lane B `fatigue_score` (chỉ xe EU) |
| `ride_hailing_xanh_sm_trips.csv` | 6.902 | Có: F6, F7, F8, F16, kèm cột `customer_contact` (PII) |
| `acn_charging_mapped.csv` | 983 (880 gốc + 103 dòng nhân bản do F13, F15) | Có: F5, F13, F14, F15 |
| `dim_customers.csv`, `dim_drivers.csv` | 5.106 / 60 | PII (kịch bản S3: ghép bảng lộ danh tính). Thêm cột Lane B: đồng ý, rút đồng ý, yêu cầu xoá, từ chối chia sẻ (khách); căn cứ xử lý (tài xế) |
| `synthetic_ev_telemetry_archive_2024-12.csv` | 288 (3 xe × 96 mẫu, ngày 15/12/2024) | Chỉ Lane B: phân vùng lưu trữ cũ cho lỗi quá hạn lưu |
| `feedback_pii.csv` | 30 | Chỉ có PII (kịch bản S2: thông tin cá nhân trong câu chữ) |
| `synthetic_feedback_scenario_driven.csv` | 20 | Phản hồi khách hàng theo kịch bản, không phải lỗi |
| `fleet_index.*`, `zone_manifest.json`, `provenance_manifest.json`, `ved_calibration.json` | | Không, chép nguyên từ nguồn |

## 2. Tỉ lệ lỗi

### Theo file (lỗi theo từng dòng: L1 + L3)

| File | Dòng gốc | Dòng bị lỗi | Tỉ lệ | EU / VN / US |
|---|---|---|---|---|
| Telemetry xe | 57.600 | 288 | **0,50%** | 89 / 105 / 94 |
| Chuyến đi | 6.902 | 138 | **2,00%** (1% L1 + 1% L3) | 38 / 41 / 59 |
| Phiên sạc | 880 | 30 | **3,41%** (2,5% L1 + 1% L3) | 11 / 8 / 11 |

### Theo họ lỗi

| Mã | Tầng | Mô tả | Số lượng | Luật nhận biết |
|---|---|---|---|---|
| F1 | L1 | Pin âm | 108 | `battery_soc < 0` |
| F2 | L1 | Điện áp vọt | 91 | `battery_voltage > 1000` |
| F3 | L1 | Xe đứng yên mà mô tơ quay nhanh | 89 | `speed_kmh = 0` và `motor_rpm > 12000` |
| F5 | L1 | Chi phí sạc âm | 22 | `cost_vnd < 0` |
| F7 | L1 | Cước âm | 36 | `fare_amount < 0` |
| F8 | L1 | Tổng cước không bằng cước + tiền boa | 33 | `total_fare ≠ fare_amount + tip_amount` |
| F6 | L3 | Toạ độ đón khách nằm trong vùng của zone khác | 69 | toạ độ ngoài khung của zone mình |
| F14 | L3 | Sạc lâu gấp 3 nhưng điện năng giảm một nửa | 8 | quan hệ thời gian – điện năng bị gãy |
| F13 | L3 | Nhân đôi phiên sạc của 5 xe từ ngày 5, số chuyến không đổi | 1 (33 dòng) | số lần sạc không khớp số chuyến |
| F10 | L2 | Pin hao dần ±30%, 3 xe, ngày 5→9 | 3 | lệch dần so với mốc ngày 0–4 của chính xe đó |
| F11 | L2 | Nhiệt độ pin trôi dần ±25%, 3 xe, ngày 5→9 | 3 | như trên |
| F15 | L4 | 5 xe chuyển từ sạc khoảng 1 lần/ngày lên khoảng 3 lần/ngày từ ngày 5 | 1 (70 dòng) | điểm đổi xu hướng |
| F16 | L4 | 5 tài xế có quãng đường tăng 50% từ ngày 5 | 1 | điểm đổi xu hướng |
| F9 | NLP | Chữ viết tắt kiểu teen | 0 | tắt (tỉ lệ = 0) |

### Thông tin cá nhân (PII)

| Kịch bản | Quy mô | Tỉ lệ |
|---|---|---|
| S1: email/số điện thoại trong cột `customer_contact`, cột này chưa đăng ký danh mục | 345 chuyến | 5% số chuyến |
| S2: thông tin cá nhân viết lẫn trong câu phản hồi | 30 câu | 100% file `feedback_pii.csv` |
| S3: ghép `trips` với `dim_customers` / `dim_drivers` làm lộ danh tính | toàn bộ chuyến | khoá `customer_id`, `driver_id` |

## 3. Vì sao chọn các tỉ lệ này

1. **Đủ thấp để giống thực tế.** Lỗi dữ liệu thật trong hệ thống vận hành thường dưới 1%. Các phương pháp phát hiện bất thường theo thống kê (độ lệch so với trung vị, rừng cô lập…) đều giả định bất thường là hiếm. Nếu tiêm quá nhiều, chính lỗi sẽ kéo lệch giá trị mốc. Khi đó bộ thử hoặc quá dễ, hoặc đo sai. Vì vậy telemetry, file lớn nhất, chỉ tiêm **0,5%**.
2. **Đủ nhiều để đo được.** Mỗi họ lỗi cần khoảng **20 trường hợp trở lên** thì tỉ lệ bắt lỗi mới có khoảng tin cậy chấp nhận được (với 20 trường hợp, sai số khoảng ±20%). File phiên sạc chỉ có 880 dòng, nếu dùng 0,5% thì F5 chỉ được khoảng 4 trường hợp. Vì thế file này dùng tỉ lệ cao hơn (**2,5%**) để F5 đạt khoảng 22.
3. **Chuyến đi 1% mỗi tầng.** Khoảng 35 trường hợp cho F7 và F8, 69 cho F6. Tức là đủ để đo, mà vẫn dưới mức có thể làm lệch phân phối cước.
4. **L2/L4 tính theo đối tượng, không theo dòng.** Chọn 3 xe (L2) hoặc 5 xe/tài xế (L4), lấy **ngày 0–4 làm mốc, ngày 5–9 có lỗi**. Có đủ 5 ngày trước và 5 ngày sau thì phương pháp tìm điểm đổi xu hướng mới có dữ liệu để so sánh. Bản cũ bắt đầu từ ngày 8 nên chỉ còn 2 ngày sau khi cắt.
5. **Rải đều 3 zone.** Dòng lỗi được chọn ngẫu nhiên trên toàn bộ file, mà mỗi zone chiếm khoảng 1/3 số dòng, nên số lỗi mỗi zone xấp xỉ nhau. Nhờ đó có thể so sánh kết quả giữa các zone.

### Hạn chế cần ghi rõ khi báo cáo

- **F14 chỉ có 8 trường hợp** (khoảng 3 mỗi zone): quá ít để kết luận chắc chắn, chỉ báo cáo kèm ghi chú.
- **L2/L4 chỉ có 1–3 mục mỗi họ**: nên báo cáo theo kiểu phát hiện được hay không, không tính tỉ lệ phần trăm.
- **F13 và F15 có thể trùng xe** (đều nhân bản phiên sạc từ ngày 5).
- **F8 không đếm đủ theo luật**: luật `total_fare ≠ fare + tip` có thể khớp cả dòng gốc do làm tròn, nên chỉ kiểm tra rằng 33 dòng trong đáp án đều vi phạm.
- **Tất cả là lỗi tự tiêm** (nhóm tự tạo đề). Đây là bộ để phát triển, chưa phải bộ kiểm định độc lập.

## 4. Cách đọc đáp án `fault_manifest.json`

| Trường | Ý nghĩa |
|---|---|
| `dataset` | Tên file (không có đuôi `.csv`) |
| `original_index` | **Số thứ tự dòng trong file này, đếm từ 0, không tính dòng tiêu đề.** Với L2/L4/F13 đây là dòng neo đại diện. |
| `column` | Cột bị tiêm lỗi |
| `fault_family`, `layer` | Mã họ lỗi, tầng L1–L4 |
| `vehicle_vin`, `subject_zone` | Xe và zone của dòng đó |
| `entity_id`, `drift_start_day`, `drift_end_day`, `drift_pct` | Chỉ có ở L2: xe nào, trôi từ ngày nào đến ngày nào, bao nhiêu % |
| `target_vins`, `target_drivers`, `affected_rows` | Chỉ có ở F13/F15/F16: danh sách xe hoặc tài xế bị ảnh hưởng, số dòng thêm vào |
| `injection_summary.checks` | Kết quả tự kiểm tra lúc sinh dữ liệu, tất cả phải là `true` |

## 5. Bảo đảm đáp án khớp dữ liệu

Tiêm lỗi là **bước cuối cùng**, và đáp án được sinh từ chính các file cuối. Trước khi ghi đáp án, script tự kiểm tra 5 điều, sai một điều là dừng, không ghi gì:

1. Mọi `original_index` nằm trong phạm vi file.
2. Mọi dòng dữ liệu thuộc ngày 0–9.
3. Mỗi lỗi F1, F2, F3, F5, F6, F7, F8 trỏ đúng dòng vi phạm luật.
4. Với F1, F2, F3, F5, F6, F7: **số dòng vi phạm thực tế = số lỗi trong đáp án** (không thừa, không thiếu).
5. Mỗi lỗi được gắn đúng xe và zone.

Kết quả lần sinh này: tất cả đạt (pin âm 108/108, điện áp 91/91, mô tơ 89/89, cước âm 36/36, chi phí âm 22/22, toạ độ 69/69).

## 6. Cách sinh lại

Một lệnh sinh lại **cả Lane A lẫn Lane B**, giữ nguyên file ghi chú này:

```bash
uv run python data_new/Ingestion/build_testset_3zone.py
```

Lệnh này chạy lần lượt: cắt 10 ngày và thêm PII (`build_pii_testset.py`), tiêm lỗi Lane A (`inject_vingroup_real_faults.py`), tiêm lỗi Lane B (`inject_lane_b.py`), rồi xoá thư mục trung gian. Mỗi bước tự kiểm tra đáp án, sai là dừng. 3 file gốc trong `raw_public/Ride Hailing/` phải dùng dấu phân cách `;`.

---

# Phần Lane B (luật theo zone)

Lane B nằm **ngay trong các file ở trên**, không có thư mục riêng:

- **Thêm cột** vào file sẵn có: `dim_customers.csv` (5 cột đồng ý, xoá, từ chối chia sẻ), `dim_drivers.csv` (`legal_basis`), `synthetic_ev_telemetry_ved_ref.csv` (`fatigue_score`). Chỉ thêm cột, không đổi thứ tự dòng, nên `original_index` của Lane A vẫn đúng.
- **Một file dữ liệu mới:** `synthetic_ev_telemetry_archive_2024-12.csv`, là phân vùng lưu trữ cũ. Để riêng vì trộn dòng năm 2024 vào telemetry 10 ngày sẽ làm Lane A báo nhầm lỗi thời gian.
- **Một file đáp án:** `lane_b_manifest.json`, gồm tham số hợp đồng, 21 lần chạy và kết quả đúng.

## Tóm tắt

- 13 tình huống (B05–B16, B19), 21 lần chạy: 11 kết quả đúng là lỗi, 9 là đạt, 1 là "giữ pháp lý, không xoá, chặn dùng phân tích".
- Ngày chạy cố định `as_of = 2026-01-11`. Ngữ cảnh bộ lọc: zone, mục đích, vai trò, ngày chạy.
- **Không gồm** chuyển dữ liệu xuyên biên giới (PDP-009/012/020, GDPR-028/044, US-CCPA-08): hoãn.
- Mỗi tình huống chỉ có 1 đến 10 thực thể: báo cáo theo "bắt được hay không", không tính phần trăm.

Mô tả từng tình huống, quy tắc, đối chứng và giới hạn: xem [`docs/planning/legal-packs/LANE_B_TIEM_LOI.md`](../../docs/planning/legal-packs/LANE_B_TIEM_LOI.md) mục 9.

## Cách đọc đáp án `lane_b_manifest.json`

| Trường | Ý nghĩa |
|---|---|
| `contract` | Tham số bộ lọc: mục đích, hạn lưu, xe đang giữ pháp lý, vai trò được đọc, hạn xử lý |
| `runs[].run_id`, `scenario_id` | Mã lần chạy và tình huống |
| `runs[].table`, `zone`, `purpose_id`, `role` | Lần chạy dùng file nào, zone nào, mục đích nào, vai trò nào |
| `law_ref`, `control_id` | Quy tắc luật và mã kiểm soát phải bắn |
| `expected_lane_b` | `fail` (phải báo lỗi), `pass` (không được báo oan), `hold_block` (quá hạn nhưng đang giữ: không xoá, chặn phân tích) |
| `expected_entities` | Thực thể phải bị báo (khách, xe, tài xế hoặc chuyến) |
| `expected_pass_entities` | Thực thể đối chứng còn trong hạn, **không** được báo |
| `expected_lane_a` | Chỉ có ở `R-B19`: số dòng pin âm Lane A phải bắt |
| `checks` | Kết quả tính lại từ dữ liệu, mọi lần chạy phải là `true` |
