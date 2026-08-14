# Data Pipeline — `data_new/`

## Tổng quan Pipeline 3 Layer

```
raw_public/          (Layer 1 - Fetch)
       │
       ▼
vingroup_pilot_dataset/          (Layer 2 - Ingest + Mapping + Timeseries)
       │
       ▼
vingroup_faulty_pilot_dataset/   (Layer 3 - Fault Injection)
```

---

## Layer 1 — Fetch (`raw_public/`)

**Script:** `scripts/Ingestion/fetch_real_public_datasets.py`

Thuận hoặc nghịch đảo các nguồn dữ liệu thật từ public repositories.

| Nguồn | Source | Grain | Domain | Ghi chú |
|---|---|---|---|---|
| **VED** | gsoh/VED (GitHub) | CAN-bus timeseries, per-trip | Gần đúng (xe hybrid Mỹ) | 55,169 rows, 3 xe |
| **ACN-Data** | Caltech/JPL/office1 JSON | Mỗi phiên sạc | Đúng grain (charging session) | 3 site |
| **Ride Hailing** | Kaggle `archive/fact_rides.csv` | Mỗi chuyến đi | Đúng domain | Có drivers/users/vouchers |
| **UIT-VSFC** | UIT (Vietnam) | Câu văn tiếng Việt | **Sai domain** | Chỉ dùng đo NLP accuracy |

**Quyết định 2026-08-08:**
- UIT-VSFC **loại bỏ** khỏi feedback content chính (feedback sinh viên ≠ taxi feedback).
- UIT-VSFC giữ lại làm **NLP benchmark set** để đo normalization accuracy / aspect extraction F1.

---

## Layer 2 — Ingest (`vingroup_pilot_dataset/`)

**Script:** `data_new/Ingestion/ingest_vingroup_real_data.py`

### 2.1 Fleet Index (`fleet_index.csv` / `fleet_index.json`)

- **60 VIN** giả định: `VF8VNF_0001` … `VF8VNF_0060`
- 3 loại xe: `VF_5_TAXI` (50%), `VF_e34_TAXI` (35%), `FELIZ_S_BIKE` (15%)
- **100%** pilot có telemetry (`telemetry_equipped = True`)
- **Tier S** (khóa join nhân tạo, gắn nhãn tường minh)

### 2.2 State Machine — Single Source of Truth (2026-08-08 v4)

**Design principle:** Trips / Charging / Telemetry cùng chia sẻ **một schedule** cho mỗi (VIN, day).

```
generate_vin_day_states(vin, day_idx)
  → List[ScheduleEvent]  (4 states MUTUALLY EXCLUSIVE theo thời gian)
```

| State | Mô tả | Thời gian |
|---|---|---|
| `CHARGING` | Overnight deep charge | [18:00 ngày trước, 06:00] + [18:00, 06:00+ ngày sau] |
| `CHARGING` | Opportunity fast charge (50%) | [10:00, 15:00] |
| `DRIVING_PASSENGER` | Trip có khách | Trong operating window [06:00, 18:00] |
| `DEADHEAD` | Chạy không khách | Giữa các trip |
| `IDLE` | Đỗ chờ | Giữa các trip |

**Disjoint guarantee:** 4 states hoàn toàn tách biệt theo thời gian → không overlap.

**Operating window:** 12 tiếng (06:00–18:00) thay vì 16 tiếng để đảm bảo disjoint với overnight charge.

### 2.3 EV Telemetry (`synthetic_ev_telemetry_ved_ref.csv`)

| Thông số | Chi tiết |
|---|---|
| **Rows** | 60 VIN × 15 ngày × 96 samples/ngày = **86,400** |
| **Interval** | 15 phút/sample |
| **Nguồn phân phối** | VED 20 xe làm per-vehicle reference (speed, RPM, SOC, voltage, current) |
| **Physical constraints** | Speed > 0 chỉ khi `DRIVING_PASSENGER/DEADHEAD`; SOC giảm khi driving, tăng khi charging |

**Mapping:**
- `speed_kmh` ← VED distribution (RS)
- `motor_rpm` ← VED: `speed * 73.2 + noise` (RD)
- `battery_soc` ← State machine: giảm 92–98% → 28–42% trong operating hours (RS)
- `battery_voltage` ← Tương quan nghịch với SOC (RS)
- `battery_current` ← Discharge (+) khi driving, charge (−) khi charging (RS)
- `battery_temp_c` ← Normal(32, 5), clip [20, 45]°C (RS, ref: IEC 62660-1)
- `latitude/longitude` ← Affine transform vào bbox Hà Nội (RS)
- `state_at_sample` ← State machine lookup (RD)

### 2.4 Charging Sessions (`acn_charging_mapped.csv`)

| Thông số | Chi tiết |
|---|---|
| **Rows** | 60 VIN × 15 ngày × 1.5 session ≈ **1,350** (900 overnight + 450 opportunity) |
| **Pool** | ACN-Caltech / JPL / office1 |
| **Pattern** | `overnight_deep_charge` (>120 min) hoặc `opportunity_fast_charge` (≤90 min) |
| **Soft overlap** | Luôn `False` — state machine đảm bảo disjoint |

**Mapping:**
- `kwh_consumed` ← ACN `kWhDelivered` (R)
- `power_kw` ← `kWhDelivered / duration_hr` (RD)
- `cost_vnd` ← `kwh × 3,100 VND/kWh` (EVN tariff) (RD)
- `station_temp_c` ← Normal(45, 10), clip [20, 65]°C (RS, ref: IEC 61851-23)
- `start_time` ← State machine schedule anchor

### 2.5 Trips (`ride_hailing_xanh_sm_trips.csv`)

| Thông số | Chi tiết |
|---|---|
| **Rows** | Pool 25,003 trips từ fact_rides, phân bổ vào state machine slots |
| **Per day target** | ~14 trips/VIN/ngày |
| **pickup/dropoff** | Từ schedule (sequential + 5 min buffer) |

**Mapping:**
- `trip_miles` ← `fact_rides.ride_distance_miles` (R)
- `fare_amount` ← USD → VND × 25,400 (RD)
- `tip_amount` ← Log-normal(loc=10.5, scale=0.8), clip [5k, 200k] VND (RS)
- `total_fare` ← `fare + tip` (RD)
- `driver_id` ← `DRV_XANH_<SEQ>` deterministic từ VIN (S)
- `pickup_lat/lon` ← Synthetic trong bbox Hà Nội (S)

### 2.6 NLP Benchmark (`nlp_benchmark_uit_vsfc.csv`)

- **500 câu** từ UIT-VSFC
- **CHỈ** dùng để đo NLP normalization accuracy / aspect extraction F1
- **KHÔNG** dùng làm feedback content chính (sai domain)

---

## Layer 3 — Fault Injection (`vingroup_faulty_pilot_dataset/`)

**Script:** `data_new/Ingestion/inject_vingroup_real_faults.py`

Hoạt động trên **bản sao** — không chỉnh sửa ground truth Layer 2.

### 9 Fault Families

| ID | Fault Family | Dataset | Mô tả | Tỷ lệ |
|---|---|---|---|---|
| **F0** | GSM Underground Blackout | EV Telemetry | `latitude/longitude = NaN` (xe vào tầng hầm) | 30% |
| **F1** | Negative Sensor Value | EV Telemetry | `battery_soc < 0` (BMS lỗi) | 25% |
| **F2** | Voltage Overvoltage Outlier | EV Telemetry | `battery_voltage > 7000V` (CAN-bus spike) | 25% |
| **F3** | Motor RPM Mismatch | EV Telemetry | `speed=0` nhưng `rpm > 12000` (lỗi inverter) | 20% |
| **F4** | V-GREEN Thermal Power Drop | Charging | `power_kw=0`, `station_temp_c > 80°C`, `status=THERMAL_FAULT` | 55% |
| **F5** | Negative Cost Anomaly | Charging | `cost_vnd < 0` (lỗi billing) | 45% |
| **F6** | GPS Alleyway Drift | Trips | `pickup_lat/lon` nhảy ra NYC (ngoài bbox HN) | 35% |
| **F7** | Negative Fare Defect | Trips | `fare_amount < 0` | 30% |
| **F8** | Arithmetic Ledger Mismatch | Trips | `total_fare ≠ fare + tip` | 35% |
| **F9** | TeenCode Text Corruption | NLP Benchmark | Câu bị corrupt teen-code (30% từ) | 0% mặc định |

### Synthetic Feedback Scenario-Driven

**Thay thế UIT-VSFC** (Hướng 2, quyết định 2026-08-08).

- **20 scenarios** × VIN + ngày
- Topic: `vehicle` (35%) | `charging` (30%) | `app` (20%) | `driver` (15%)
- Sentiment: 60% negative | 25% neutral | 15% positive
- Hỗ trợ cross-domain corroboration (fault → negative feedback cùng VIN/ngày)

**Output:** `synthetic_feedback_scenario_driven.csv`

---

## Provenance Tracking

### 4-Tier Provenance System

Mỗi cột trong manifest được gắn **1 trong 4 tier**:

| Tier | Định nghĩa | Ví dụ |
|---|---|---|
| **R** | Real-Exact — lấy thẳng từ nguồn, không biến đổi | `kwh_consumed` ← ACN `kWhDelivered` |
| **RD** | Real-Derived — tính từ ≥1 trường thật bằng công thức xác định | `power_kw` ← `kWh / duration_hr` |
| **RS** | Real-Statistically-Parameterized — synthetic nhưng tham số hóa từ phân phối thật | `station_temp_c` ← Normal(45, 10) ref IEC 61851-23 |
| **S** | Scenario-Construct — dựng có chủ đích, không có tương ứng thật | `vehicle_vin` ← khóa join nhân tạo |

### Manifest Files

| File | Layer | Nội dung |
|---|---|---|
| `provenance_manifest.json` | Layer 2 | Tier của từng cột trong 4 dataset output |
| `fault_manifest.json` | Layer 3 | Ground truth tất cả fault đã inject (dataset, row_idx, column, family, description) |
| `fleet_index.json` | Layer 2 | Metadata fleet: linkage_type, pilot size, design decisions |

---

## Chạy Pipeline

```bash
# Layer 1: Fetch dữ liệu thật
python scripts/Ingestion/fetch_real_public_datasets.py

# Layer 2: Ingest + Mapping + Timeseries
python data_new/Ingestion/ingest_vingroup_real_data.py

# Layer 3: Fault Injection
python data_new/Ingestion/inject_vingroup_real_faults.py
```

**Output sau Layer 2:**
```
data_new/vingroup_pilot_dataset/
├── fleet_index.csv
├── fleet_index.json
├── synthetic_ev_telemetry_ved_ref.csv  (86,400 rows)
├── acn_charging_mapped.csv             (~1,350 rows)
├── ride_hailing_xanh_sm_trips.csv       (~18,000 rows)
├── nlp_benchmark_uit_vsfc.csv           (500 rows)
└── provenance_manifest.json
```

**Output sau Layer 3:**
```
data_new/vingroup_faulty_pilot_dataset/
├── fleet_index.csv
├── synthetic_ev_telemetry_ved_ref.csv   (+ faults)
├── acn_charging_mapped.csv             (+ faults)
├── ride_hailing_xanh_sm_trips.csv       (+ faults)
├── nlp_benchmark_uit_vsfc.csv
├── synthetic_feedback_scenario_driven.csv  (20 scenarios)
├── provenance_manifest.json
└── fault_manifest.json                  (ground truth faults)
```

---

## Design Decisions (2026-08-08 v4)

1. **State machine thống nhất** — trips/charging/telemetry cùng consume `generate_vin_day_states()`, đảm bảo disjoint guarantee.
2. **VED 20 xe cover 60 VIN** — cycling 20 VED vehicle IDs cho 60 pilot VIN.
3. **Operating window 06:00–18:00** — tách biệt với overnight charge 18:00–06:00.
4. **UIT-VSFC loại bỏ** khỏi feedback content → thay bằng synthetic scenario-driven.
5. **Deterministic seed** (`hash((vin, day_idx)) % 2^31`) — reproducibility cross-function.
6. **VED calibration cached** trong `ved_calibration.json` — decouple khỏi raw CSV.
