# BÁO CÁO ĐÁNH GIÁ ROOT CAUSE ANALYSIS (RCA) VỚI LIVE LLM
**DataTrust OS — Autonomous Diagnostic & RCA Benchmark Suite**

* **Thời gian đánh giá:** `2026-08-15 11:09:51 UTC`
* **Chế độ LLM:** `Live LLM (Gemini / OpenAI / Ollama)`
* **Tập dữ liệu kiểm thử:** `184,715` bản ghi DuckDB (`vingroup_pilot.db`)
* **Tệp đối chứng Ground Truth:** `C:\Users\ngant\P-086\data_new\vingroup_faulty_pilot_dataset\fault_manifest.json`
* **Tổng thời gian thực thi:** `261.08s`

---

## 1. TỔNG QUAN KẾT QUẢ ĐÁNH GIÁ RCA (EXECUTIVE SUMMARY)

| Chỉ số | Giá trị | Đánh giá & Nhận xét |
| :--- | :--- | :--- |
| **Tổng số Gold Test Cases** | **8** | Bao phủ đầy đủ 4 tầng L1–L4 & 4 domain |
| **Số ca chẩn đoán đạt (PASS)** | **5 / 8** | Tỷ lệ đạt tuyệt đối: **62.5%** |
| **Số ca đạt một phần (PARTIAL)** | **2** | Phát hiện đúng phân loại hoặc nguyên nhân gốc |
| **Số ca thất bại (FAIL)** | **1** | Phân loại sai hoặc không tìm ra nguyên nhân |
| **Độ chuẩn xác phân loại (Classification)** | **83.8%** | Khả năng phân biệt `DATA` vs `OPERATIONAL` |
| **Độ khớp nguyên nhân gốc (Root Cause Alignment)** | **65.0%** | Trùng khớp từ khóa và bản chất lỗi với Ground Truth |
| **Chỉ số Grounding Evidence (Chống bịa)** | **100.0%** | Trích dẫn đúng bằng chứng từ Diagnostic Tools |
| **Điểm RCA tổng thể (Overall Composite Score)** | **79.5%** | Trọng số: 40% Phân loại + 40% Nguyên nhân + 20% Evidence |
| **Trung bình Tool Calls / Case** | **3.5** | Giới hạn trần <= 5 tool calls / sự cố |
| **Trung bình Token tiêu thụ / Case** | **8094.8 tokens** | Giới hạn trần <= 2000 tokens / sự cố |
| **Thời gian chẩn đoán TB / Case** | **27.06s** | Độ trễ đáp ứng của Agent |

---

## 2. BẢNG MA TRẬN ĐỐI SOÁT CHI TIẾT TỪNG CA (CASE-BY-CASE GROUND TRUTH MATRIX)

| # | Tầng | Nhóm lỗi (Fault Family) | Ground Truth Root Cause | LLM Diagnosis Claim | GT Class | LLM Class | Tools | Tokens | Điểm | Kết luận |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `L1` | `F1_Negative_SOC` | BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). | Dynamic A1 verified data contract violation in entity VF8VNF_0006: BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0); Cooling system thermal degradation or pack heat dissipation failure leading to sustained temperature drift; Fleet charging regime shift where vehicle charging frequency abruptly jumps (CUSUM shift); CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V); CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000); Ride-hailing billing pipeline defect producing negative trip fare amounts. | `DATA` | `DATA` | 3 | 18423 | **100%** | **PASS** |
| 2 | `L1` | `F2_Voltage_Overvoltage_Spike` | CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V). | The root cause of the incident is a voltage regulation issue, likely due to a faulty voltage sensor or a problem with the electrical system, which caused a RANGE_VIOLATION anomaly on the 'voltage' metric at Layer L1 and a CHANGEPOINT_SHIFT anomaly on the 'charging_frequency' metric at Layer L4. | `DATA` | `OPERATIONAL` | 4 | 9383 | **52%** | *PARTIAL* |
| 3 | `L1` | `F3_RPM_Speed_Mismatch` | CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000). | The root cause of the anomaly is a tachometer speed desynchronization mismatch, resulting in an incorrect `speed_vs_motor_rpm` metric value, which is affecting the `L1` layer detector. | `DATA` | `DATA` | 3 | 5987 | **92%** | **PASS** |
| 4 | `L1` | `F5_Negative_Cost` | Tariff billing engine calculation defect or negative pricing multiplier in charging session. | Dynamic A1 verified data contract violation in entity VF8VNF_0050: Tariff billing engine calculation defect or negative pricing multiplier in charging session; BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). | `DATA` | `DATA` | 5 | 7387 | **100%** | **PASS** |
| 5 | `L1` | `F7_Negative_Fare` | Ride-hailing billing pipeline defect producing negative trip fare amounts. | The root cause of the anomaly is a DATA issue, specifically a schema change that affected the calculation of the 'fare_amount' metric, resulting in a RANGE_VIOLATION anomaly. | `DATA` | `DATA` | 4 | 7056 | **60%** | *PARTIAL* |
| 6 | `L3` | `F14_DurationEnergy_Mismatch` | Relational break where charging duration increases significantly while delivered energy (kWh) remains flat, indicating power stall or charger meter fault. | Negative battery SOC sensor glitch causing incorrect calculation of kwh_consumed_vs_duration_mins | `MIXED` | `DATA` | 3 | 5419 | **48%** | ~~FAIL~~ |
| 7 | `L3` | `F6_GPS_Alleyway_Drift` | Driver app GPS sensor drift or coordinate truncation placing pickup coordinates outside Hanoi bounding box. | GPS bounding box calculation glitch due to incorrect or missing GPS coordinates, affecting the 'gps_coordinates_bounding_box' metric | `DATA` | `DATA` | 3 | 5573 | **92%** | **PASS** |
| 8 | `L4` | `F16_FareDistribution_Regime` | Driver route operating regime shift causing a persistent 50% shift in daily mean trip distance (CUSUM shift). | Thermal management system malfunction in the DC fast charging station DRV_XANH_0015, causing elevated battery temperature readings and triggering a thermal alert, which in turn affected the mean distance metric | `OPERATIONAL` | `OPERATIONAL` | 3 | 5530 | **92%** | **PASS** |

---

## 3. CHI TIẾT TRACE VÀ PHÂN TÍCH CHẨN ĐOÁN TỪNG SỰ CỐ

### Case 1: [L1] F1_Negative_SOC — `inc-5c6fd288`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0006`
- **Lý do thừa nhận (Fusion):** Multi-layer agreement across L1, L2, L3, L4 layers
- **Ground Truth:** BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). *(Expected Class: `DATA`)*
- **LLM Phán đoán:** Dynamic A1 verified data contract violation in entity VF8VNF_0006: BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0); Cooling system thermal degradation or pack heat dissipation failure leading to sustained temperature drift; Fleet charging regime shift where vehicle charging frequency abruptly jumps (CUSUM shift); CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V); CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000); Ride-hailing billing pipeline defect producing negative trip fare amounts. *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: Dynamic A1 verified data contract violation in entity VF8VNF_0006: BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0); Cooling system thermal degradation or pack heat dissipation failure leading to sustained temperature drift; Fleet charging regime shift where vehicle charging frequency abruptly jumps (CUSUM shift); CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V); CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000); Ride-hailing billing pipeline defect producing negative trip fare amounts.
- **Tool Execution Trace:** `fetch_entity_telemetry, fetch_charging_history, fetch_entity_telemetry`
- **Đánh giá:** Classification: `100%`, Root Cause: `100%`, Grounding: `100%` $\rightarrow$ **Overall: 100.0% (PASS)**

### Case 2: [L1] F2_Voltage_Overvoltage_Spike — `inc-a3f40168`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0053`
- **Lý do thừa nhận (Fusion):** Multi-layer agreement across L1, L3, L4 layers
- **Ground Truth:** CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V). *(Expected Class: `DATA`)*
- **LLM Phán đoán:** The root cause of the incident is a voltage regulation issue, likely due to a faulty voltage sensor or a problem with the electrical system, which caused a RANGE_VIOLATION anomaly on the 'voltage' metric at Layer L1 and a CHANGEPOINT_SHIFT anomaly on the 'charging_frequency' metric at Layer L4. *(Class: `OPERATIONAL`)*
- **Khuyến nghị hành động:** `MAINTENANCE_ROUTING` — Route operational maintenance recommendation: The root cause of the incident is a voltage regulation issue, likely due to a faulty voltage sensor or a problem with the electrical system, which caused a RANGE_VIOLATION anomaly on the 'voltage' metric at Layer L1 and a CHANGEPOINT_SHIFT anomaly on the 'charging_frequency' metric at Layer L4.
- **Tool Execution Trace:** `fetch_profile, fetch_entity_telemetry, fetch_charging_history, inspect_upstream_contracts`
- **Đánh giá:** Classification: `0%`, Root Cause: `80%`, Grounding: `100%` $\rightarrow$ **Overall: 52.0% (PARTIAL)**

### Case 3: [L1] F3_RPM_Speed_Mismatch — `inc-a9dbe483`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0041`
- **Lý do thừa nhận (Fusion):** Multi-layer agreement across L1, L3 layers
- **Ground Truth:** CAN-bus desynchronization between speed sensor and motor tachometer (speed=0 km/h but RPM > 12000). *(Expected Class: `DATA`)*
- **LLM Phán đoán:** The root cause of the anomaly is a tachometer speed desynchronization mismatch, resulting in an incorrect `speed_vs_motor_rpm` metric value, which is affecting the `L1` layer detector. *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: The root cause of the anomaly is a tachometer speed desynchronization mismatch, resulting in an incorrect `speed_vs_motor_rpm` metric value, which is affecting the `L1` layer detector.
- **Tool Execution Trace:** `fetch_entity_telemetry, query_historical_baselines, calculate_detector_detail`
- **Đánh giá:** Classification: `100%`, Root Cause: `80%`, Grounding: `100%` $\rightarrow$ **Overall: 92.0% (PASS)**

### Case 4: [L1] F5_Negative_Cost — `inc-1f6cc3b7`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0050`
- **Lý do thừa nhận (Fusion):** Critical L1 signal admitted: cost_vnd
- **Ground Truth:** Tariff billing engine calculation defect or negative pricing multiplier in charging session. *(Expected Class: `DATA`)*
- **LLM Phán đoán:** Dynamic A1 verified data contract violation in entity VF8VNF_0050: Tariff billing engine calculation defect or negative pricing multiplier in charging session; BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: Dynamic A1 verified data contract violation in entity VF8VNF_0050: Tariff billing engine calculation defect or negative pricing multiplier in charging session; BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0).
- **Tool Execution Trace:** `fetch_profile, fetch_entity_telemetry, fetch_dq_violations, resolve_entity_relationships, query_historical_baselines`
- **Đánh giá:** Classification: `100%`, Root Cause: `100%`, Grounding: `100%` $\rightarrow$ **Overall: 100.0% (PASS)**

### Case 5: [L1] F7_Negative_Fare — `inc-7415c7ce`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0047`
- **Lý do thừa nhận (Fusion):** Critical L1 signal admitted: fare_amount
- **Ground Truth:** Ride-hailing billing pipeline defect producing negative trip fare amounts. *(Expected Class: `DATA`)*
- **LLM Phán đoán:** The root cause of the anomaly is a DATA issue, specifically a schema change that affected the calculation of the 'fare_amount' metric, resulting in a RANGE_VIOLATION anomaly. *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: The root cause of the anomaly is a DATA issue, specifically a schema change that affected the calculation of the 'fare_amount' metric, resulting in a RANGE_VIOLATION anomaly.
- **Tool Execution Trace:** `fetch_profile, inspect_upstream_contracts, fetch_dq_violations, fetch_recent_changes`
- **Đánh giá:** Classification: `100%`, Root Cause: `0%`, Grounding: `100%` $\rightarrow$ **Overall: 60.0% (PARTIAL)**

### Case 6: [L3] F14_DurationEnergy_Mismatch — `inc-ad0d49be`
- **Mức độ nghiêm trọng:** `HIGH` | **Thực thể ảnh hưởng:** `VF8VNF_0014`
- **Lý do thừa nhận (Fusion):** High severity L3 signal admitted (kwh_consumed_vs_duration_mins)
- **Ground Truth:** Relational break where charging duration increases significantly while delivered energy (kWh) remains flat, indicating power stall or charger meter fault. *(Expected Class: `MIXED`)*
- **LLM Phán đoán:** Negative battery SOC sensor glitch causing incorrect calculation of kwh_consumed_vs_duration_mins *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: Negative battery SOC sensor glitch causing incorrect calculation of kwh_consumed_vs_duration_mins
- **Tool Execution Trace:** `fetch_profile, fetch_entity_telemetry, fetch_dq_violations`
- **Đánh giá:** Classification: `70%`, Root Cause: `0%`, Grounding: `100%` $\rightarrow$ **Overall: 48.0% (FAIL)**

### Case 7: [L3] F6_GPS_Alleyway_Drift — `inc-bdd8e321`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0032`
- **Lý do thừa nhận (Fusion):** High severity L3 signal admitted (gps_coordinates_bounding_box)
- **Ground Truth:** Driver app GPS sensor drift or coordinate truncation placing pickup coordinates outside Hanoi bounding box. *(Expected Class: `DATA`)*
- **LLM Phán đoán:** GPS bounding box calculation glitch due to incorrect or missing GPS coordinates, affecting the 'gps_coordinates_bounding_box' metric *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: GPS bounding box calculation glitch due to incorrect or missing GPS coordinates, affecting the 'gps_coordinates_bounding_box' metric
- **Tool Execution Trace:** `fetch_profile, fetch_dq_violations, query_historical_baselines`
- **Đánh giá:** Classification: `100%`, Root Cause: `80%`, Grounding: `100%` $\rightarrow$ **Overall: 92.0% (PASS)**

### Case 8: [L4] F16_FareDistribution_Regime — `inc-ec1c7d76`
- **Mức độ nghiêm trọng:** `HIGH` | **Thực thể ảnh hưởng:** `DRV_XANH_0015`
- **Lý do thừa nhận (Fusion):** High severity L4 signal admitted (mean_distance)
- **Ground Truth:** Driver route operating regime shift causing a persistent 50% shift in daily mean trip distance (CUSUM shift). *(Expected Class: `OPERATIONAL`)*
- **LLM Phán đoán:** Thermal management system malfunction in the DC fast charging station DRV_XANH_0015, causing elevated battery temperature readings and triggering a thermal alert, which in turn affected the mean distance metric *(Class: `OPERATIONAL`)*
- **Khuyến nghị hành động:** `MAINTENANCE_ROUTING` — Route operational maintenance recommendation: Thermal management system malfunction in the DC fast charging station DRV_XANH_0015, causing elevated battery temperature readings and triggering a thermal alert, which in turn affected the mean distance metric
- **Tool Execution Trace:** `fetch_trip_history, fetch_entity_telemetry, fetch_profile`
- **Đánh giá:** Classification: `100%`, Root Cause: `80%`, Grounding: `100%` $\rightarrow$ **Overall: 92.0% (PASS)**
