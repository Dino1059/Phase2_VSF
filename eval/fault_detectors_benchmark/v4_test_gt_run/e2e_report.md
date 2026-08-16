# BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG DETECTOR ĐA TẦNG (V3 (Toàn diện — Full-Coverage ML & Detector Pipeline))
**DataTrust OS — End-to-End Reliability & Anomaly Detection Pipeline**

* **Cấu hình phiên bản:** `V3 (Toàn diện — Full-Coverage ML & Detector Pipeline)`
* **Thời gian thực thi:** `2026-08-15 09:46:30 UTC`
* **Cơ sở dữ liệu:** `C:\Users\ngant\P-086\data_new\db\vingroup_pilot_eval.db`
* **Thư mục kết quả:** `eval\benchmarks\test_gt_run`
* **Tổng số bản ghi quét:** `184,715` dòng
* **Thời gian hoàn tất:** `8.63s`

---

## 1. TỔNG QUAN HIỆU NĂNG PHÁT HIỆN & GOM CỤM

| Chỉ số | Giá trị | Nhận xét |
| :--- | :--- | :--- |
| **Tổng số bản ghi nạp** | **184,715** | 5 bảng DuckDB (`vinfast_bms`, `vgreen_telemetry`, `vgreen_charging_sessions`, `xanhsm_trips`, `xanhsm_feedback`) |
| **Tổng tín hiệu bất thường (Signals)** | **1,147** | Phân bố: L1=444, L2=498, L3=182, L4=23 |
| **Sự cố được thừa nhận (Incidents)** | **199** | Gom cụm qua `FusionEngine` dựa trên Multi-layer Agreement |
| **Tỷ lệ giảm tải cảnh báo (Noise Reduction)** | **82.7%** | Giảm từ 1147 signals rời rạc $\rightarrow$ 199 sự cố có thể hành động |
| **Phân bố mức độ nghiêm trọng** | CRITICAL: 137, HIGH: 62, MEDIUM: 0 | Ưu tiên các sự cố đa tầng |

---

## 2. MA TRẬN PHÂN TÍCH CHI TIẾT TỪNG TẦNG DETECTOR (L1 – L4)

| Tầng | Bộ phát hiện | Tập dữ liệu | Chỉ số / Quan hệ kiểm tra | Số Signals | Đánh giá chất lượng & Trạng thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **L1** | `L1ConstraintDetector` | `vinfast_bms` | SoC $[0, 100]$, Temp $[-20, 85]$, Voltage $[200, 900]$, Nulls | **172** | Bắt vi phạm biên vật lý và hợp đồng dữ liệu. |
| **L1** | `L1ConstraintDetector` | `vgreen_telemetry` | Tương quan tốc độ vs RPM (`speed=0 & rpm>12000`) | **129** | Bắt lỗi xung nhịp động cơ (`F3_RPM_Speed_Mismatch`). |
| **L1** | `L1ConstraintDetector` | `xanhsm_trips` | Cước phí `fare_amount` $\ge 0$ | **52** | Bắt các cuốc xe âm tiền (`F7_Negative_Fare`). |
| **L1** | `L1ConstraintDetector` | `xanhsm_trips` | Bất đẳng thức số học sổ sách `total_fare == fare + tip` | **51** | Bắt sai lệch kế toán chuyến đi (`F8_Ledger_Mismatch`). |
| **L1** | `L1ConstraintDetector` | `vgreen_charging_sessions` | Tiền sạc `cost_vnd` $\ge 0$ & Năng lượng `kwh_consumed` $\ge 0$ | **40** | Bắt lỗi âm tiền sạc (`F5_Negative_Cost`). |
| **L2** | `L2ContextualDetector` | `vinfast_bms` | Trôi dạt nhiệt độ ($Z \ge 2.5$, Ngày 8–15 vs Baseline 7 ngày) | **498** | Bắt trôi dạt nhiệt độ pin và suy giảm SoC (`F10/F11`). |
| **L3** | `L3RelationalDetector` | `vinfast_bms` | Hồi quy phần dư Voltage vs Temp ($Z = 3.0$) | **45** | Bắt các điểm sai lệch nhiệt - áp bất thường. |
| **L3** | `L3RelationalDetector` | `xanhsm_trips` | Tương quan quãng đường `distance_km` vs cước phí `fare_amount` | **0** | Bắt điểm lệch tương quan cước/quãng đường. |
| **L3** | `L3RelationalDetector` | `xanhsm_trips` | Tọa độ GPS ngoài Bounding Box Hà Nội | **103** | Bắt lỗi trôi dạt GPS (`F6_GPS_Alleyway_Drift`). |
| **L3** | `L3RelationalDetector` | `vgreen_charging_sessions` | Tương quan thời gian sạc `duration_mins` vs năng lượng `kwh_consumed` | **14** | Bắt lỗi lệch tương quan sạc `F14_DurationEnergy_Mismatch`. |
| **L3** | Cross-Table Relational | `Trips × BMS × Feedback × Charging` | BMS Temp $> 65^\circ\text{C}$, Feedback rating $\le 2$, Charging vs Trips | **20** | Liên kết phản hồi tiêu cực và bất thường liên miền. |
| **L4** | `L4ChangepointDetector` | `vinfast_bms` | CUSUM Shift ($h=6.0, d=1.0, w=5$) trên nhiệt độ BMS | **15** | Khử dao động ngày/đêm. |
| **L4** | `L4ChangepointDetector` | `vgreen_charging_sessions` | CUSUM Shift trên tần suất sạc theo ngày | **4** | Bắt các xe nhảy vọt tần suất sạc (`F15`). |
| **L4** | `L4ChangepointDetector` | `xanhsm_trips` | CUSUM Shift trên quãng đường trung bình/ngày của tài xế | **4** | Bắt tài xế có phân phối cuốc xe bất thường (`F16`). |

---

## 3. KẾT QUẢ ĐỐI CHIẾU THỰC NGHIỆM VỚI GROUND TRUTH (`fault_manifest.json`)

* **Tệp đối chứng Ground Truth:** `C:\Users\ngant\P-086\data_new\vingroup_faulty_pilot_dataset\fault_manifest.json`
* **Tổng số lỗi đã gài (Ground Truth Faults):** **693** lỗi
* **Tổng lỗi bắt đúng (True Positives):** **689**
* **Tổng cảnh báo ngoài Ground Truth (False Positives):** **458**
* **Tổng lỗi bị bỏ sót (False Negatives):** **4**
* **Độ phủ thực tế toàn hệ thống (Overall Recall):** **99.4%**
* **Độ chính xác toàn hệ thống (Overall Precision):** **60.1%**
* **F1-Score tổng thể:** **0.749**

### Bảng chi tiết độ phủ theo từng nhóm lỗi (F1 – F16):

| Nhóm lỗi (Fault Family) | Ground Truth (Lỗi gài) | Signals Bắt Được | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Độ phủ (Recall) | Độ chuẩn (Precision) | F1-Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `F10_SOC_Degradation_Drift` | **3** | **0** | **0** | 0 | 3 | **0.0%** | 0.0% | 0.000 |
| `F11_BatteryTemp_Drift` | **3** | **498** | **3** | 495 | 0 | **100.0%** | 0.6% | 0.012 |
| `F13_ChargingTrip_Mismatch` | **1** | **0** | **0** | 0 | 1 | **0.0%** | 0.0% | 0.000 |
| `F14_DurationEnergy_Mismatch` | **13** | **14** | **13** | 1 | 0 | **100.0%** | 92.9% | 0.963 |
| `F15_ChargingFrequency_Shift` | **1** | **4** | **1** | 3 | 0 | **100.0%** | 25.0% | 0.400 |
| `F16_FareDistribution_Regime` | **1** | **4** | **1** | 3 | 0 | **100.0%** | 25.0% | 0.400 |
| `F1_Negative_SOC` | **172** | **172** | **172** | 0 | 0 | **100.0%** | 100.0% | 1.000 |
| `F2_Voltage_Overvoltage_Spike` | **131** | **45** | **131** | 0 | 0 | **100.0%** | 100.0% | 1.000 |
| `F3_RPM_Speed_Mismatch` | **129** | **129** | **129** | 0 | 0 | **100.0%** | 100.0% | 1.000 |
| `F5_Negative_Cost` | **33** | **40** | **33** | 7 | 0 | **100.0%** | 82.5% | 0.904 |
| `F6_GPS_Alleyway_Drift` | **103** | **103** | **103** | 0 | 0 | **100.0%** | 100.0% | 1.000 |
| `F7_Negative_Fare` | **52** | **103** | **52** | 51 | 0 | **100.0%** | 50.5% | 0.671 |
| `F8_Ledger_Mismatch` | **51** | **51** | **51** | 0 | 0 | **100.0%** | 100.0% | 1.000 |

---

## 4. BẢNG SO SÁNH TIẾN HÓA DETECTOR: V1 VS V2 VS V3

| Tiêu chí đánh giá | Phiên bản V1 (Gốc) | Phiên bản V2 (Tối ưu) | Phiên bản V3 (Bao phủ toàn diện) |
| :--- | :--- | :--- | :--- |
| **Tầng L1 (Constraint Checks)** | 264 signals | 264 signals | **444 signals** *(+F3 Telemetry, +F8 Ledger)* |
| **Tầng L2 (Contextual Drift)** | 0 signals | 498 signals | **498 signals** |
| **Tầng L3 (Relational & Spatial)** | 33 signals | 79 signals | **182 signals** *(+F6 GPS Bounding Box, +Distance/Fare)* |
| **Tầng L4 (CUSUM Changepoint)** | 478 signals *(Nhiễu)* | 19 signals | **23 signals** *(+F16 Driver Distance Shift)* |
| **Tổng Signals** | 775 signals | 860 signals | **1147 signals** |
| **Sự cố thừa nhận (Incidents)** | 141 incidents | 116 incidents | **199 incidents** |
| **Tỷ lệ nén nhiễu (Noise Reduction)** | 81.8% | 86.5% | **82.7%** |

---
*Báo cáo được tạo tự động bởi `scripts/run_anomaly_pipeline_e2e.py`.*
