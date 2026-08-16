# Data Pipeline — `data_new/`

Hệ thống pipeline dữ liệu đa tầng (Multi-Layer Data Pipeline) phục vụ mô phỏng, mapping, kiểm định chất lượng (EDA), tiêm lỗi có kiểm soát (Fault Injection) và nạp kho dữ liệu DuckDB cho hệ sinh thái xe điện & dịch vụ di chuyển VinGroup (VinFast, V-GREEN, Xanh SM).

---

## 1. Kiến trúc Tổng thể Pipeline

Dữ liệu di chuyển qua **5 tầng kiến trúc liên hoàn**:

```
[ Layer 1: Data Fetching ]
  data_new/raw_public/ (VED, ACN-Data, Ride Hailing, UIT-VSFC)
        │  fetch_real_public_datasets.py
        ▼
[ Layer 2: Ingest & Mapping & Timeseries ]
  data_new/vingroup_pilot_dataset/ (Clean Ground Truth + State Machine + 4-Tier Provenance)
        │  ingest_vingroup_real_data.py
        ├───► [ Layer 2.5: Quality Gate & EDA ]
        │       data_new/EDA vingroup_pilot_dataset/ (Report, Findings, Figures, Per-VIN)
        │       eda_vingroup_pilot.py
        ▼
[ Layer 3: Fault Injection Engine ]
  data_new/vingroup_faulty_pilot_dataset/ (16 Fault Families L1-L4 + Scenario Feedback)
        │  inject_vingroup_real_faults.py
        ▼
[ Layer 4: Warehouse & Analytics ]
  data_new/db/vingroup_pilot.db (DuckDB 1:1 Schema Mapping + Views + Snapshots)
        ingest_vingroup_pilot_to_duckdb.py
```

---

## 2. Cấu trúc Thư mục `data_new/`

```
data_new/
├── Ingestion/                                 # Chứa toàn bộ scripts xử lý pipeline
│   ├── fetch_real_public_datasets.py          # Layer 1: Fetch/mirror dữ liệu public
│   ├── ingest_vingroup_real_data.py           # Layer 2: Ingestion, State Machine & Mapping
│   ├── eda_vingroup_pilot.py                  # Layer 2.5: EDA kiểm định chất lượng & Go/No-Go
│   ├── inject_vingroup_real_faults.py         # Layer 3: Tiêm 16 họ lỗi L1-L4 & Scenario Feedback
│   ├── ingest_vingroup_pilot_to_duckdb.py     # Layer 4: Load dữ liệu vào DuckDB
│   └── sample_fetch_manifest.json             # Manifest mẫu kiểm tra cấu trúc fetch
├── raw_public/                                # Dữ liệu thô tải từ các nguồn public
│   ├── ACN/                                   # Phiên sạc thật từ Caltech/JPL/office1 JSON
│   ├── Ride Hailing/                          # fact_rides.csv & drivers.csv
│   ├── vehicle_telemetry_raw.csv              # Telemetry CAN-bus thật từ Michigan VED
│   ├── uit_vsfc_raw.csv                       # Sentiment corpus từ UIT (HuggingFace)
│   └── fetch_manifest.json                    # Log xuất xứ dữ liệu fetch (Real vs Seed)
├── vingroup_pilot_dataset/                    # Dữ liệu sạch chuẩn (Clean Ground Truth)
│   ├── fleet_index.csv / fleet_index.json     # 60 VIN danh mục xe và metadata
│   ├── synthetic_ev_telemetry_ved_ref.csv     # 86,400 dòng telemetry (15 ngày × 15 phút)
│   ├── acn_charging_mapped.csv                # ~1,350 phiên sạc phân bổ theo State Machine
│   ├── ride_hailing_xanh_sm_trips.csv         # Chuyến đi taxi Xanh SM chuẩn hóa cước VN
│   ├── nlp_benchmark_uit_vsfc.csv             # 500 câu chuẩn đo lường NLP model
│   ├── ved_calibration.json                   # Cache phân phối thực nghiệm từ VED
│   └── provenance_manifest.json               # Gán nhãn 4-Tier Provenance cho từng cột
├── EDA vingroup_pilot_dataset/                # Báo cáo & phân tích chất lượng Layer 2
│   ├── report.md                              # Báo cáo tổng kết Go/No-Go, phân phối, vi phạm vật lý
│   ├── findings.json                          # Phát hiện máy đọc (machine-readable metrics)
│   ├── *.csv                                  # Bảng tổng hợp schema, state, cước, sạc
│   ├── figures/                               # Biểu đồ phân phối, tương quan vật lý (.png)
│   └── per_vehicle/                           # Chi tiết kiểm tra drill-down cho từng VIN
├── vingroup_faulty_pilot_dataset/             # Dữ liệu phục vụ Benchmark (Đã tiêm lỗi)
│   ├── [Các file CSV tương tự dataset sạch]   # Bản sao có chứa lỗi được kiểm soát
│   ├── synthetic_feedback_scenario_driven.csv # 20 kịch bản phản hồi khách hàng đối soát chéo
│   └── fault_manifest.json                    # Ground truth toàn bộ lỗi (Phục vụ đo lường F1)
└── db/                                        # Kho lưu trữ cơ sở dữ liệu phân tích
    └── vingroup_pilot.db                      # DuckDB chứa đầy đủ schema raw.* và views
```

---

## 3. Chi tiết các Tầng Kiến trúc & Scripts trong `data_new/Ingestion/`

### 3.1. Layer 1 — Fetch Public Data (`fetch_real_public_datasets.py`)

Kéo dữ liệu thật từ các nguồn mở uy tín. Nếu gặp sự cố mạng/404, script tự động fallback về **Seed Mirror** có gắn cờ cảnh báo tường minh `is_seed_mirror = 1`.

| Nguồn dữ liệu | Nguồn gốc | Grain | Domain | Vai trò trong Pipeline |
|---|---|---|---|---|
| **VED** | gsoh/VED (Univ. of Michigan) | CAN-bus 1Hz theo trip | Telemetry xe HEV/PHEV/EV | Tham số hóa phân phối tốc độ, RPM, SOC, điện áp, dòng điện |
| **ACN-Data** | Caltech / JPL / office1 | Từng phiên sạc | Trạm sạc EV thông minh | Phân phối năng lượng kWh, thời lượng sạc, công suất kW |
| **Ride Hailing** | Fact Rides / Chicago TNP | Từng cuốc xe | Dịch vụ taxi công nghệ | Khoảng cách chuyến, thời lượng di chuyển, cuốc xe |
| **UIT-VSFC** | HuggingFace (`uitnlp`) | Câu tiếng Việt | Feedback sinh viên UIT | Bộ Benchmark chuẩn để đo F1/Accuracy của NLP Pipeline |

- **Output:** `raw_public/fetch_manifest.json` ghi nhận trạng thái thật/seed của từng nguồn.

---

### 3.2. Layer 2 — Ingest, Mapping & State Machine (`ingest_vingroup_real_data.py`)

Chuyển đổi dữ liệu thô sang nghiệp vụ VinGroup với **State Machine đơn nguồn sự thật (Single Source of Truth)**.

#### 1. Constructed Fleet Index (`fleet_index.csv`, `fleet_index.json`)
- **60 VIN**: `VF8VNF_0001` → `VF8VNF_0060`.
- Cơ cấu đội xe: **50% VF 5 Taxi**, **35% VF e34 Taxi**, **15% Feliz S Bike**.
- 100% phương tiện được gắn nhãn giám sát hành trình (`telemetry_equipped = True`).

#### 2. Deterministic State Machine (Single Source of Truth)
Đảm bảo tính nhất quán vật lý giữa Trips, Sạc và Telemetry qua hàm `generate_vin_day_states(vin, day_idx)`:
- `CHARGING (Overnight)`: 18:00 (hôm trước) – 06:00 (sáng).
- `CHARGING (Opportunity)`: 10:00 – 15:00 (sạc nhanh giữa ca).
- `DRIVING_PASSENGER`: Trong khung giờ vận hành 06:00 – 18:00 (có khách).
- `DEADHEAD`: ~35% thời gian vận hành (chạy không khách tìm điểm đón).
- `IDLE`: Đỗ chờ giữa các cuốc xe.
- **Cam kết Disjoint**: Các trạng thái hoàn toàn tách biệt theo thời gian, không xảy ra xung đột vừa sạc vừa chạy.

#### 3. Bộ dữ liệu đầu ra chính:
- **EV Telemetry (`synthetic_ev_telemetry_ved_ref.csv`)**: 60 VIN × 15 ngày × 96 mẫu/ngày = **86,400 dòng** (15 phút/mẫu). VED calibration tham số hóa các dải vật lý (IEC 62660-1).
- **Charging Sessions (`acn_charging_mapped.csv`)**: ~1,350 phiên sạc, cước điện EVN chuẩn 3,100 VND/kWh, nhiệt độ trạm sạc theo IEC 61851-23.
- **Trips (`ride_hailing_xanh_sm_trips.csv`)**: Chuyến đi Xanh SM, scale cước taxi chuẩn Hà Nội (`FARE_SCALE_TO_VN_TAXI = 0.22`, ~18,000 VND/km).
- **NLP Benchmark (`nlp_benchmark_uit_vsfc.csv`)**: 500 câu chuẩn tiếng Việt.
- **VED Calibration Cache (`ved_calibration.json`)**: Lưu trữ phân phối thực nghiệm.

#### 4. Hệ thống 4-Tier Provenance (`provenance_manifest.json`)
Mỗi cột trong toàn bộ dataset được gán 1 trong 4 nhãn minh bạch:
- **`R` (Real-Exact)**: Lấy trực tiếp từ nguồn thật (ví dụ `kwh_consumed` từ ACN).
- **`RD` (Real-Derived)**: Tính toán từ trường thật bằng công thức xác định (ví dụ `power_kw = kwh / duration_hr`, `cost_vnd = kwh × 3,100`).
- **`RS` (Real-Statistically-Parameterized)**: Sinh tổng hợp tham số hóa theo phân phối thật/tiêu chuẩn (ví dụ `battery_temp_c`, `speed_kmh`).
- **`S` (Scenario-Construct)**: Thiết kế có chủ đích cho kịch bản (ví dụ `vehicle_vin`, `driver_id`).

---

### 3.3. Layer 2.5 — Exploratory Data Analysis & Quality Gate (`eda_vingroup_pilot.py`)

Kiểm định toàn diện chất lượng dữ liệu sạch trước khi thực hiện tiêm lỗi hoặc đưa vào huấn luyện mô hình:
- **Kiểm tra Schema & Null Cells**: Đảm bảo không có trường dữ liệu thiếu ngoài ý muốn.
- **Kiểm định Khóa Join VIN**: 100% khớp nối xuyên suốt giữa Fleet, Telemetry, Sạc và Chuyến đi.
- **Kiểm định Quy luật Vật lý (Physics Sanity Check)**: Kiểm tra SOC không âm, nhiệt độ trong ngưỡng cho phép, xe đứng yên thì tốc độ bằng 0.
- **Kiểm định Cước & Năng lượng**: Tỷ lệ cước/km, chi phí sạc/kWh.
- **Output:** Thư mục `data_new/EDA vingroup_pilot_dataset/` chứa `report.md`, `findings.json`, cùng các biểu đồ trực quan `figures/` và drill-down `per_vehicle/`.

---

### 3.4. Layer 3 — Fault Injection Engine (`inject_vingroup_real_faults.py`)

Hoạt động trên **bản sao dữ liệu**, tuyệt đối không can thiệp vào dataset gốc. Tiêm **16 họ lỗi (Fault Families)** phân theo 4 cấp độ bài toán phát hiện bất thường (L1–L4) + NLP + Scenario Feedback:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       16 FAULT FAMILIES TAXONOMY                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1: Point & Deterministic Rules (Rule-based / dbt)                          │
│   • F1: Negative SOC (BMS error, SOC < 0)                                   │
│   • F2: Voltage Spike (CAN-bus overvoltage > 1000V)                         │
│   • F5: Negative Charging Cost (Billing error, cost_vnd < 0)                │
│   • F7: Negative Trip Fare (fare_amount < 0)                                │
│   • F8: Ledger Mismatch (total_fare ≠ fare + tip)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ L2: Contextual & Univariate Drift (Rolling z-score / 14-day baseline)       │
│   • F10: SOC Degradation Drift (Suy giảm dung lượng pin bất thường qua ngày)│
│   • F11: Battery Temp Drift (Nhiệt độ pin trôi lệch > 2σ so với baseline)  │
│   • F12: Trip Duration Surge (Khoảng cách/thời gian chuyến tăng đột biến)   │
├─────────────────────────────────────────────────────────────────────────────┤
│ L3: Relational & Collective Mismatches (IsolationForest / Residuals)        │
│   • F3: RPM & Speed Mismatch (speed = 0 nhưng rpm > 12,000 do lỗi inverter) │
│   • F6: GPS Alleyway Drift (Tọa độ đón khách nhảy vọt ra ngoài Hà Nội)      │
│   • F13: Charging-Trip Mismatch (Sạc nhiều lần nhưng số chuyến đi bằng 0)   │
│   • F14: Duration-Energy Mismatch (Thời gian cắm sạc tăng nhưng kWh đứng yên│
├─────────────────────────────────────────────────────────────────────────────┤
│ L4: Sequential & Regime Change-Point (CUSUM / PELT)                         │
│   • F15: Charging Frequency Shift (Chuyển đột ngột từ 1 lần/ngày -> 3 lần)  │
│   • F16: Cost Distribution Regime (Shift phân phối cước của tài xế +30-50%) │
├─────────────────────────────────────────────────────────────────────────────┤
│ NLP & Scenario-Driven Corroboration                                         │
│   • F9: TeenCode Text Corruption (Nhiễu teencode trên benchmark NLP)        │
│   • Synthetic Feedback (20 kịch bản phản hồi tiêu cực tương ứng với lỗi VIN)│
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Output:**
  - Bộ file CSV lỗi trong `data_new/vingroup_faulty_pilot_dataset/`.
  - `synthetic_feedback_scenario_driven.csv`: 20 kịch bản đối soát chéo phản hồi khách hàng.
  - `fault_manifest.json`: Ground truth lưu chi tiết từng dòng, cột, loại lỗi, phục vụ tính toán chính xác Precision / Recall / F1.

---

### 3.5. Layer 4 — DuckDB Warehouse Ingestion (`ingest_vingroup_pilot_to_duckdb.py`)

Nạp toàn bộ dữ liệu vào DuckDB (`data_new/db/vingroup_pilot.db`) với độ chuẩn xác 1:1, hỗ trợ truy vấn phân tích hiệu năng cao.

#### Các Bảng dữ liệu chính (`raw.*`):
- `raw.ev_telemetry`: Dữ liệu telemetry chi tiết (86,400 dòng).
- `raw.charging_sessions`: Lịch sử các phiên sạc pin.
- `raw.trips`: Toàn bộ dữ liệu chuyến đi của Xanh SM.
- `raw.fleet_index`: Danh mục 60 phương tiện.
- `raw.nlp_benchmark`: Bộ câu benchmark xử lý ngôn ngữ tự nhiên.
- `raw.synthetic_feedback`: Phản hồi người dùng theo kịch bản.
- `raw.fault_manifest`: Toàn bộ metadata ground truth lỗi đã tiêm.
- `raw.provenance_manifest`: Nguồn gốc xuất xứ từng cột dữ liệu.
- `raw.raw_snapshots` & `raw.datasets`: Registry quản lý snapshot và phiên bản dữ liệu.

#### Backwards Compatibility Views:
- `vinfast_bms`: View chuẩn hóa cho hệ thống quản lý pin VinFast.
- `vgreen_telemetry`: View phân tích trạng thái trạm sạc & xe V-GREEN.
- `xanhsm_trips`: View phân tích hoạt động kinh doanh vận tải Xanh SM.

---

## 4. Hướng dẫn Chạy Pipeline

Khuyến nghị chạy tuần tự theo các bước từ thư mục gốc của project:

```bash
# ----------------------------------------------------------------------------
# Bước 1: Fetch dữ liệu thô từ public repositories (Layer 1)
# ----------------------------------------------------------------------------
python data_new/Ingestion/fetch_real_public_datasets.py

# ----------------------------------------------------------------------------
# Bước 2: Ingestion, Mapping & sinh dữ liệu sạch chuẩn VinGroup (Layer 2)
# ----------------------------------------------------------------------------
python data_new/Ingestion/ingest_vingroup_real_data.py

# ----------------------------------------------------------------------------
# Bước 3: Chạy kiểm định chất lượng EDA & tạo báo cáo Go/No-Go (Layer 2.5)
# ----------------------------------------------------------------------------
python data_new/Ingestion/eda_vingroup_pilot.py

# ----------------------------------------------------------------------------
# Bước 4: Tiêm 16 họ lỗi L1-L4 & sinh Feedback đối soát chéo (Layer 3)
# ----------------------------------------------------------------------------
python data_new/Ingestion/inject_vingroup_real_faults.py

# ----------------------------------------------------------------------------
# Bước 5: Nạp dữ liệu vào DuckDB Analytics Database (Layer 4)
# ----------------------------------------------------------------------------
# Nạp dataset đã tiêm lỗi (mặc định cho benchmark)
python data_new/Ingestion/ingest_vingroup_pilot_to_duckdb.py

# Hoặc nạp dataset sạch (Clean ground truth):
python data_new/Ingestion/ingest_vingroup_pilot_to_duckdb.py --source-dir data_new/vingroup_pilot_dataset
```

---

## 5. Nguyên tắc Thiết kế & Quyết định Kỹ thuật (Design Principles)

1. **Tính bất biến của Ground Truth**: Layer 2 sinh dữ liệu sạch chuẩn, Layer 3 chỉ tiêm lỗi trên bản sao (`vingroup_faulty_pilot_dataset`), không làm sai lệch ground truth gốc.
2. **State Machine Đơn nguồn sự thật**: Trips, Sạc và Telemetry tuân thủ chặt chẽ cùng một lịch trình phân bổ thời gian thực, triệt tiêu hiện tượng mâu thuẫn trạng thái.
3. **Phân cấp Lỗi rõ ràng (L1 → L4)**: Đầy đủ các họ lỗi từ vi phạm luật cứng (L1), trôi dạt phân phối (L2), bất thường quan hệ đa bảng (L3) đến chuyển đổi chế độ vận hành (L4).
4. **Minh bạch Nguồn gốc (Provenance)**: Mỗi trường dữ liệu đều có metadata xác thực rõ ràng thuộc nhóm `R`, `RD`, `RS` hay `S`.
5. **Khả năng tái lập (Reproducibility)**: Cố định Random Seed (`RANDOM_SEED = 42`) xuyên suốt toàn bộ pipeline để đảm bảo kết quả nhất quán.
