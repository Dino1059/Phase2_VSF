# DataTrust OS — Phân Tích Provenance & Giải Pháp Mapping/Linkage

**Mã dự án:** DATA-02 | **Ngày:** 07/08/2026 | **Tác giả phân tích:** Ngân + Claude
**Bối cảnh:** Thay thế pipeline "fetch giả → mirror seed" bằng pipeline có cơ sở thật, minh bạch về mức độ "thật" của từng cột, có khả năng tạo kịch bản cho Incident Workspace.

---

## 1. Vấn đề cốt lõi (nhắc lại, đã xác nhận)

Pipeline cũ tự sinh tự chấm: `fetch_real_public_datasets.py` 0/4 URL hoạt động → 100% seed mirror; fault hardcode trong generator nên khi thay data thật, fault biến mất; mapper expect schema giả nên vỡ khi gặp schema thật.

Việc bạn làm — probe schema thật (`schema_analysis.md`), loại ST-EVCDP, thêm ACN-Data — là bước sửa đúng hướng. Nhưng nó tạo ra vấn đề mới: **các nguồn thật không đồng nhất về domain, quốc gia, và grain**, nên không thể dán nhãn nhị phân "real" / "seed" nữa. Cần một khung phân loại chi tiết hơn.

---

## 2. Đánh giá lại 4+ nguồn dữ liệu (sau khi bạn đổi)

| Nguồn | Grain | Domain khớp? | Vấn đề chính |
|---|---|---|---|
| **VED** (`vehicle_telemetry_raw.csv`) | Time-series CAN-bus, per-trip | Gần đúng (xe hybrid Mỹ, không phải EV thuần VN) | Có cột không áp dụng (Fuel Rate, MAF); không có battery_temp_c; tọa độ ở Michigan |
| **ACN-Data** (Caltech/JPL/office1) | Event-level, mỗi phiên sạc | Đúng grain (đây là lý do bạn thêm vào, hợp lý) | Không có station_temp_c, không có cost, không có vehicle_id |
| **archive/fact_rides + drivers/users/vouchers** | Event-level, mỗi chuyến đi, có bảng quan hệ | Đúng grain, còn giữ cấu trúc quan hệ thật (voucher join được) | Không có tip_amount, không có VIN, đơn vị/tiền tệ cần xác minh |
| **UIT-VSFC** | Câu văn độc lập, không có timestamp | **Sai domain** — feedback sinh viên về giảng viên/cơ sở vật chất, không phải feedback app gọi xe/trạm sạc | Text thật nhưng nội dung ngữ nghĩa lệch hoàn toàn |
| ST-EVCDP | Trạm tĩnh (grid-level) | Sai grain (không có phiên sạc) | **Đã loại — quyết định đúng, giữ nguyên** |

**Kết luận:** Không có nguồn nào là "hoàn toàn thật cho VinGroup" — vì VinGroup/Hà Nội không tồn tại trong bất kỳ dataset public nào bạn tiếp cận được. Điều có thể làm là: thật ở **cấp đo lường** (record-level), minh bạch ở **cấp diễn giải** (mapping/derive), và có chủ đích ở **cấp kịch bản** (linkage).

---

## 3. Khung phân loại Provenance (4 tier)

Thay vì gắn nhãn file, gắn nhãn **theo từng cột** trong manifest:

| Tier | Định nghĩa | Ví dụ |
|---|---|---|
| **R — Real-Exact** | Lấy thẳng từ nguồn thật, không biến đổi | `battery_soc` ← VED `HV Battery SOC[%]` |
| **RD — Real-Derived** | Tính từ ≥1 trường thật bằng công thức xác định, có thể kiểm chứng | `power_kw` ← ACN `kWhDelivered / (doneChargingTime − connectionTime)` |
| **RS — Real-Statistically-Parameterized** | Không có trường thật tương ứng, sinh synthetic nhưng tham số hóa từ phân phối/tài liệu thật (không phải số tùy ý) | `station_temp_c` ACN — sinh theo phân phối nhiệt độ cabinet sạc DC fast-charging từ tài liệu kỹ thuật BMS thermal, không phải `random.uniform(20,90)` vô căn cứ |
| **S — Scenario-Construct** | Dựng có chủ đích cho kịch bản kiểm thử, không có tương ứng thật, phải có lập luận bảo vệ được | Khóa nối `vehicle_vin` xuyên domain; nội dung feedback "lỗi trạm sạc Vincom Bà Triệu" |

Mỗi file output đi kèm `provenance_manifest.json` ghi tier cho từng cột — đây chính là thứ trả lời được câu hội đồng hỏi "cái này thật hay seed" mà không cần né tránh.

---

## 4. Bảng mapping chi tiết theo domain

### 4.1 EV Telemetry (nguồn: VED `vehicle_telemetry_raw.csv`)

| Cột VinGroup | Cột nguồn VED | Tier | Ghi chú |
|---|---|---|---|
| `record_id` | sinh mới | S | ID kỹ thuật, không phải claim |
| `vehicle_vin` | — | **S** | Gán qua Fleet Linkage Layer (mục 5) |
| `timestamp` | `Timestamp(ms)` + ngày gốc giả định | RD | VED cho mốc ms tương đối trong trip, cần cộng base date để ra ISO-8601 — công thức rõ ràng, không bịa giá trị đo |
| `speed_kmh` | `Vehicle Speed[km/h]` | R | |
| `motor_rpm` | `Engine RPM[RPM]` | R | Lưu ý: VED là xe ICE/hybrid, "motor RPM" ở đây là động cơ đốt trong, không phải motor điện thuần — phải ghi chú giới hạn này trong tài liệu, không giấu |
| `battery_soc` | `HV Battery SOC[%]` | R | |
| `battery_voltage` | `HV Battery Voltage[V]` | R | |
| `battery_current` | `HV Battery Current[A]` | R | |
| `battery_temp_c` | — (VED không đo) | RS | Sinh theo phân phối nhiệt độ pin Li-ion vận hành bình thường (20–45°C) tham chiếu tài liệu kỹ thuật BMS, không phải random tùy ý |
| `latitude`, `longitude` | `Latitude[deg]`, `Longitude[deg]` | RS | Giữ **pattern di chuyển tương đối thật** (hình dạng route, tốc độ thay đổi tọa độ) nhưng dịch affine sang bounding box Hà Nội — không claim là tọa độ Hà Nội thật, chỉ claim là pattern chuyển động thật được tái định vị |
| `accel_z` | — (không có trong VED) | S | Nếu cần, sinh tương quan với `speed_kmh` derivative, gắn rõ S |

Cột phải loại bỏ khi map: `Fuel Rate[L/hr]`, `MAF[g/sec]`, `Fuel Trim*` — không áp dụng cho EV, giữ lại sẽ tạo cột rỗng/gây hiểu nhầm.

### 4.2 Charging Sessions (nguồn: ACN-Data)

| Cột VinGroup | Cột nguồn ACN | Tier | Ghi chú |
|---|---|---|---|
| `session_id` | `sessionID` | R | |
| `station_id` | `siteID` + `stationID` → prefix `VG_STA_` | RD | Đổi tên/prefix, giữ nguyên định danh gốc |
| `charger_id` | `spaceID` | R | |
| `vehicle_vin` | — | **S** | Fleet Linkage Layer |
| `start_time` | `connectionTime` | R | |
| `duration_mins` | `disconnectTime − connectionTime` | RD | |
| `power_kw` | `kWhDelivered / (doneChargingTime − connectionTime)` | RD | Đây là điểm mạnh nhất của việc chuyển sang ACN — số liệu tính được từ đo đạc thật, khác hẳn seed |
| `kwh_consumed` | `kWhDelivered` | R | |
| `station_temp_c` | — (ACN không đo) | RS | Cần cho kịch bản thermal fault (mục 1.6.5 PRD) — sinh theo phân phối nhiệt độ cabinet DC fast-charger vận hành bình thường, có literature reference |
| `cost_vnd` | `kwh_consumed × đơn giá điện VN thực tế (EVN biểu giá)` | RD | Công thức thật + đơn giá thật (tra biểu giá điện EVN hiện hành), chỉ số kWh là input thật |
| `status` | derive từ ngưỡng nghiệp vụ | S (baseline `COMPLETED`) | Trạng thái lỗi chỉ gán ở Layer 3 (fault injection), không gán sẵn |

Lưu ý license: ACN-Data (Caltech) thường yêu cầu trích dẫn học thuật — cần kiểm tra điều khoản trước khi dùng trong sản phẩm, kể cả demo.

### 4.3 Trips (nguồn: `archive/fact_rides.csv` + `drivers.csv` + `vouchers.csv`)

| Cột VinGroup | Cột nguồn | Tier | Ghi chú |
|---|---|---|---|
| `trip_id` | `ride_id` | R | |
| `vehicle_vin` | — (nguồn chỉ có `car_make`/`car_model`/`license_plate` qua join `drivers.csv`, không có VIN) | **S** | Fleet Linkage Layer; `car_make`/`car_model`/`license_plate` có thể giữ làm cột phụ ở tier R nếu cần |
| `driver_id` | `driver_id` | R | |
| `pickup_datetime` | `ride_date` + `ride_time` | R | |
| `trip_miles` | `ride_distance_miles` | R | |
| `fare_amount` | `fare_amount` | RD | Cần xác minh đơn vị tiền tệ gốc trước — nếu không phải VND, quy đổi bằng tỷ giá thật tại thời điểm dữ liệu, ghi rõ tỷ giá dùng |
| `tip_amount` | — (fact_rides **không có** trường này) | RS | Sinh theo tỷ lệ tip/fare trung bình tham chiếu từ nghiên cứu thị trường ride-hailing thật, không phải số tùy chọn |
| `discount_amount` | join `vouchers.csv` qua `voucher` code, dùng `discount_amount`/`discount_perc` | RD | |
| `total_fare` | `fare + tip − discount` | RD | Công thức xác định, dùng để tạo fault #8 (ledger mismatch) một cách có kiểm soát |
| `pickup_latitude/longitude` | `start_location` | RS | Cần xác minh `start_location` là tọa độ hay tên địa điểm text; nếu là text, phải geocode hoặc remap sang bounding box Hà Nội — claim rõ là "vị trí pattern thật, tọa độ tái định vị" |
| `vehicle_type` | — | S | Gán theo enum VinGroup, không có tương ứng thật |

### 4.4 Customer Feedback (nguồn: UIT-VSFC)

**Cảnh báo quan trọng, không né:** UIT-VSFC lệch domain nghiêm trọng — nội dung nói về giảng viên/cơ sở vật chất đại học, không phải app gọi xe hay trạm sạc. Đây không phải vấn đề mapping có thể sửa bằng công thức.

| Cột VinGroup | Cột nguồn | Tier | Ghi chú |
|---|---|---|---|
| `raw_comment_text` | `sentence` | R (nhưng lệch domain) | **Chỉ nên dùng để validate module chuẩn hóa teen-code/NLP pipeline** — vì slang, chính tả, cấu trúc câu tiếng Việt là hiện tượng ngôn ngữ xuyên domain, đo accuracy trên đây là hợp lý. **Không nên** dùng làm "nguồn feedback về V-GREEN/Xanh SM" |
| `extracted_location`, `extracted_component`, `extracted_error_type` | — | S | Phải dựng kịch bản riêng (câu feedback tiếng Việt tự viết mô phỏng đúng domain, có teen-code chèn có chủ đích) thay vì gán nhãn giả lên câu UIT-VSFC |
| `severity_level` | — | S | |

**Đề xuất cụ thể:** Tách UIT-VSFC ra khỏi luồng "feedback data" chính. Dùng nó làm **test set riêng cho NLP benchmark** (đo normalization accuracy, aspect extraction F1 theo đúng tiêu chí PRD mục 5.4), báo cáo kết quả này minh bạch là "đo trên corpus tiếng Việt thật, khác domain, dùng để kiểm định năng lực xử lý ngôn ngữ chung". Feedback nội dung V-GREEN/Xanh SM cụ thể thì viết tay/dựng có kiểm soát (S), không giả danh UIT-VSFC.

---

## 5. Fleet Linkage Layer — nối vehicle_id xuyên domain (điểm bạn yêu cầu bổ sung)

### Vấn đề
VED (Michigan, xe A), ACN (California, phiên sạc B), fact_rides (driver C) là ba thực thể không có liên hệ thật nào. Nhưng Incident Workspace (PRD 5.5) cần kể được chuỗi sự kiện của "một xe" để tạo hypothesis có ý nghĩa.

### Giải pháp: Constructed Fleet Index — tầng S tường minh, tách biệt khỏi dữ liệu đo lường

1. Sinh một danh sách N VIN giả định (`VF8VNF_0001` … `VF8VNF_00{N}`) — đây là **khóa join nhân tạo**, gắn tier S ngay từ định nghĩa.
2. Với mỗi VIN, **gán ngẫu nhiên có kiểm soát** (stratified sampling, có seed cố định để tái lập) một tập bản ghi thật từ mỗi domain: một số trip từ `fact_rides`, một số session từ ACN, một đoạn trip từ VED.
3. Ràng buộc hợp lý khi gán (để kịch bản không vô lý): trình tự thời gian trong ngày phải hợp logic (sạc → sau đó mới có trip), nhưng **không claim** đây là hành vi thật của một xe thật — ghi rõ trong metadata: `linkage_type: "constructed_for_scenario_testing"`.
4. Mọi kết quả benchmark Precision/Recall/F1 tính trên fault đã biết (đến từ Layer 3 injection) — **không** tính "độ chính xác phát hiện mối liên hệ xuyên domain", vì mối liên hệ đó là do ta dựng, không phải pattern cần agent khám phá. Việc này giữ cho benchmark A1 vs C1 không bị lẫn giữa "agent giỏi" và "agent đoán đúng thứ ta tự bịa".

Nói ngắn gọn: bạn được phép nối, miễn là nối ở lớp kịch bản riêng, có nhãn, và không lẫn vào lớp đo lường/benchmark.

---

## 6. Kết luận & rủi ro còn lại cần bạn quyết định

- **Layer 1 (Fetch):** VED + ACN + fact_rides fetch được thật (kiểm tra lại URL/license ACN). UIT-VSFC dùng riêng cho NLP benchmark, không trộn vào feedback content chính.
- **Layer 2 (Mapping):** Theo bảng tier ở mục 4, ghi provenance_manifest.json theo cột.
- **Layer 2.5 (mới — Fleet Linkage):** Tầng nối vehicle_id, tách biệt, gắn nhãn S, seed cố định để tái lập.
- **Layer 3 (Fault Injection):** Giữ nguyên logic cũ, nhưng inject trên nền RD/RS ở trên thay vì random hoàn toàn.

**Câu hỏi mở cần bạn quyết:**
1. `tip_amount` và `station_temp_c` không có trong nguồn thật — bạn có tài liệu/paper cụ thể nào để tham số hóa phân phối (RS) không, hay tạm thời chấp nhận baseline ước lượng có ghi chú rõ?
2. fact_rides — cần xác minh đơn vị tiền tệ gốc trước khi tính RD cho `fare_amount`.
3. License ACN-Data — cần xác nhận trước khi dùng trong sản phẩm nộp hội đồng.
