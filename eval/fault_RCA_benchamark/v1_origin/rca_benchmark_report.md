# BÁO CÁO ĐÁNH GIÁ ROOT CAUSE ANALYSIS (RCA) VỚI LIVE LLM
**DataTrust OS — Autonomous Diagnostic & RCA Benchmark Suite**

* **Thời gian đánh giá:** `2026-08-15 10:50:29 UTC`
* **Chế độ LLM:** `Live LLM (Gemini / OpenAI / Ollama)`
* **Tập dữ liệu kiểm thử:** `184,715` bản ghi DuckDB (`vingroup_pilot.db`)
* **Tệp đối chứng Ground Truth:** `C:\Users\ngant\P-086\data_new\vingroup_faulty_pilot_dataset\fault_manifest.json`
* **Tổng thời gian thực thi:** `146.45s`

---

## 1. TỔNG QUAN KẾT QUẢ ĐÁNH GIÁ RCA (EXECUTIVE SUMMARY)

| Chỉ số | Giá trị | Đánh giá & Nhận xét |
| :--- | :--- | :--- |
| **Tổng số Gold Test Cases** | **2** | Bao phủ đầy đủ 4 tầng L1–L4 & 4 domain |
| **Số ca chẩn đoán đạt (PASS)** | **0 / 2** | Tỷ lệ đạt tuyệt đối: **0.0%** |
| **Số ca đạt một phần (PARTIAL)** | **2** | Phát hiện đúng phân loại hoặc nguyên nhân gốc |
| **Số ca thất bại (FAIL)** | **0** | Phân loại sai hoặc không tìm ra nguyên nhân |
| **Độ chuẩn xác phân loại (Classification)** | **100.0%** | Khả năng phân biệt `DATA` vs `OPERATIONAL` |
| **Độ khớp nguyên nhân gốc (Root Cause Alignment)** | **10.0%** | Trùng khớp từ khóa và bản chất lỗi với Ground Truth |
| **Chỉ số Grounding Evidence (Chống bịa)** | **100.0%** | Trích dẫn đúng bằng chứng từ Diagnostic Tools |
| **Điểm RCA tổng thể (Overall Composite Score)** | **64.0%** | Trọng số: 40% Phân loại + 40% Nguyên nhân + 20% Evidence |
| **Trung bình Tool Calls / Case** | **0.0** | Giới hạn trần <= 5 tool calls / sự cố |
| **Trung bình Token tiêu thụ / Case** | **4375.0 tokens** | Giới hạn trần <= 2000 tokens / sự cố |
| **Thời gian chẩn đoán TB / Case** | **63.88s** | Độ trễ đáp ứng của Agent |

---

## 2. BẢNG MA TRẬN ĐỐI SOÁT CHI TIẾT TỪNG CA (CASE-BY-CASE GROUND TRUTH MATRIX)

| # | Tầng | Nhóm lỗi (Fault Family) | Ground Truth Root Cause | LLM Diagnosis Claim | GT Class | LLM Class | Tools | Tokens | Điểm | Kết luận |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `L1` | `F1_Negative_SOC` | BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). | Dynamic A1 verified data contract violation in entity VF8VNF_0006. | `DATA` | `DATA` | 0 | 3550 | **68%** | *PARTIAL* |
| 2 | `L1` | `F2_Voltage_Overvoltage_Spike` | CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V). | Dynamic A1 verified data contract violation in entity VF8VNF_0053. | `DATA` | `DATA` | 0 | 5200 | **60%** | *PARTIAL* |

---

## 3. CHI TIẾT TRACE VÀ PHÂN TÍCH CHẨN ĐOÁN TỪNG SỰ CỐ

### Case 1: [L1] F1_Negative_SOC — `inc-92af6ec7`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0006`
- **Lý do thừa nhận (Fusion):** Multi-layer agreement across L1, L2, L3, L4 layers
- **Ground Truth:** BMS sensor glitch or telemetry pipeline corruption causing negative SOC values (battery_soc < 0). *(Expected Class: `DATA`)*
- **LLM Phán đoán:** Dynamic A1 verified data contract violation in entity VF8VNF_0006. *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: Dynamic A1 verified data contract violation in entity VF8VNF_0006.
- **Tool Execution Trace:** `None`
- **Đánh giá:** Classification: `100%`, Root Cause: `20%`, Grounding: `100%` $\rightarrow$ **Overall: 68.0% (PARTIAL)**

### Case 2: [L1] F2_Voltage_Overvoltage_Spike — `inc-9dc3301f`
- **Mức độ nghiêm trọng:** `CRITICAL` | **Thực thể ảnh hưởng:** `VF8VNF_0053`
- **Lý do thừa nhận (Fusion):** Multi-layer agreement across L1, L3, L4 layers
- **Ground Truth:** CAN-bus electrical noise or sensor surge causing unrealistic voltage spike (> 1000V). *(Expected Class: `DATA`)*
- **LLM Phán đoán:** Dynamic A1 verified data contract violation in entity VF8VNF_0053. *(Class: `DATA`)*
- **Khuyến nghị hành động:** `PREVENTIVE_DQ_RULE_PROPOSAL` — Propose preventive data control rule for: Dynamic A1 verified data contract violation in entity VF8VNF_0053.
- **Tool Execution Trace:** `None`
- **Đánh giá:** Classification: `100%`, Root Cause: `0%`, Grounding: `100%` $\rightarrow$ **Overall: 60.0% (PARTIAL)**
