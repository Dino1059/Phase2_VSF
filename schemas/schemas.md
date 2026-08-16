# Document: DataTrust OS - JSON Schema Contracts (`schemas/`)

Tài liệu này giải thích mục đích, giá trị cốt lõi và cách sử dụng của các file JSON Schema nằm trong thư mục `schemas/`. Các schemas này đóng vai trò là "bản vẽ kỹ thuật" (contracts) quy định cấu trúc dữ liệu giao tiếp giữa các thành phần trong hệ thống: **LLM Agent ↔ Tool Layer ↔ API ↔ Frontend**.

Trong DataTrust OS v4.0, kiến trúc đã nâng cấp thành một hệ thống **Agentic System** có HITL (Human-In-The-Loop) governance, do đó hệ thống schema này là bắt buộc để LLM, Tools và DB giao tiếp một cách chặt chẽ, an toàn theo nguyên tắc "Structured Output Only".

---

## 🎯 Mục đích chung và Giá trị của `schemas/`

1. **Giao tiếp Deterministic cho Agent:** Giới hạn đầu ra của Agent LLM. Agent chỉ được phép tương tác với hệ thống bằng cách trả về JSON đúng với các định dạng trong thư mục này.
2. **Chứng minh "Agentic Necessity":** Ghi lại từng bước suy luận, hành động, và kết quả từ tools của agent để có thể so sánh và benchmark (vd: A1 so với C1/C0).
3. **Data Lineage & Governance:** Đảm bảo mọi thay đổi dữ liệu, đề xuất luật, và kết quả thực thi đều có thể truy vết ngược (hash chain, snapshots).
4. **Human-In-The-Loop (HITL) Queue:** Đóng gói các đề xuất từ AI thành một định dạng chuẩn để Frontend có thể render cho Human Reviewer phê duyệt/từ chối.

---

## 📁 Chi tiết các file Schema

Dưới đây là danh sách và chức năng của từng Schema đang có mặt trong thư mục:

### 1. `rulespec.schema.json` (Định nghĩa Luật Chất lượng Dữ liệu)
*   **Mục đích:** Là đơn vị cốt lõi nhất. Định nghĩa một quy tắc chất lượng dữ liệu (Data Quality Rule) dưới dạng một biểu thức SQL Boolean linh hoạt (`rule_expression`).
*   **Giá trị v4:** Đã thay thế cách cấu hình cứng nhắc (family + parameters) của v3 bằng SQL Expression. Bổ sung thêm lifecycle trạng thái (`proposed` → `approved` / `rejected`) và thông tin người phê duyệt (`approved_by`) phục vụ cho HITL.
*   **Sử dụng:** Được Agent sinh ra khi phát hiện dị thường và tạo thành Rule; được hệ thống thực thi trực tiếp trên DuckDB sau khi Human approve.

### 2. `proposal.schema.json` (Đề xuất của LLM/Agent)
*   **Mục đích:** Đóng gói các suy luận (reasoning) và luật (rules) do Agent đề xuất sau quá trình "điều tra" đa luồng (cross-domain diagnosis).
*   **Giá trị v4:** Proposal bây giờ là một "báo cáo điều tra" thay vì chỉ là bảng map schema như v3. Nó chứa `rationale` giải thích lý do LLM đưa ra luật, đi kèm với reference tới Session ID của Trace và Snapshot ID của dữ liệu gốc.
*   **Sử dụng:** Nằm trong Queue chờ (HITL). Frontend sẽ load Proposal này để user có thể đánh giá và ra quyết định.

### 3. `audit-event.schema.json` (Nhật ký Kiểm toán Bất biến)
*   **Mục đích:** Ghi lại mọi hành động quan trọng thay đổi trạng thái hệ thống (approve proposal, quarantine row, sửa luật).
*   **Giá trị v4:** Ứng dụng **SHA-256 Hash Chain** (giống mini-blockchain). Mỗi sự kiện sẽ lưu mã hash của chính nó và sự kiện trước đó.
*   **Sử dụng:** Chứng minh tính toàn vẹn (Immutability). Dùng để kiểm toán (audit) hoặc cảnh báo nếu Database bị can thiệp trái phép.

### 4. `agent-trace.schema.json` (Nhật ký Suy luận của Agent)
*   **Mục đích:** Ghi lại từng bước chạy của ReAct loop của hệ thống Agent.
*   **Giá trị v4:** Rất quan trọng để **chứng minh Agentic Necessity**. Nó lưu trữ `thought` (Agent nghĩ gì), `action` (gọi tool gì), `observation` (kết quả tool trả về), cộng thêm tracking về `tokens_used`, `cost_usd`, `duration_ms`.
*   **Sử dụng:** Dùng cho quá trình Benchmark (ở thư mục `eval/`), render Traces timeline ở Frontend, và tracking chi phí LLM.

### 5. `raw-snapshot.schema.json` (Lineage Tracking Dữ liệu Gốc)
*   **Mục đích:** Lưu lại dấu vết (Fingerprint) của dữ liệu thô (raw data) ngay khi vừa được ingest từ các domain (Google Maps, V-GREEN, VinFast...).
*   **Giá trị v4:** Đảm bảo **Reproducibility** (khả năng tái lập). Tính SHA-256 hash của raw dataset để phát hiện nếu file gốc bị sửa đổi.
*   **Sử dụng:** Gắn kết vào Profile, Proposal và Rule để hệ thống biết chính xác luật này được sinh ra từ dataset version nào.

### 6. `profile-result.schema.json` (Thống kê Dữ liệu)
*   **Mục đích:** Bản báo cáo tóm tắt cấu trúc và phân phối của cột dữ liệu (null %, min/max, uniqueness count).
*   **Giá trị v4:** Cung cấp thông tin input số liệu chính xác để `ProfilerAgent` và `DiagnosisAgent` đưa ra quyết định mà không cần đoán mò.
*   **Sử dụng:** Tool `Profiler` trả kết quả dạng JSON này, đưa vào context prompt của LLM Agent.

### 7. `cleandb.schema.json` (Onboarding Pack / Contract Đích)
*   **Mục đích:** Định nghĩa dạng chuẩn (Data Dictionary) của một dataset sau khi được làm sạch.
*   **Giá trị v4:** Vẫn đóng vai trò là "blueprint" cho các dataset mới onboard vào hệ thống, nhưng tách biệt logic của `quality_rules` ra một table riêng thay vì nhúng trực tiếp.
*   **Sử dụng:** Dùng trong Data Onboarding. Agent dựa vào cấu trúc này kết hợp với đa dạng domain để làm root-cause analysis (vd: link giữa VIN của xe và Station ID của trạm sạc).

### 8. `run-manifest.schema.json` (Tóm tắt Lần chạy)
*   **Mục đích:** Tóm tắt (Summary) kết quả của một đợt chạy Pipeline (scan, run rules, quarantine).
*   **Giá trị v4:** Được tối giản lại (so với v3 monolithic) do các thành phần chi tiết đã được tách ra `agent-trace` hoặc `raw-snapshot`.
*   **Sử dụng:** Ghi nhận tổng quan Job Run để hiển thị trên Dashboard.

---

## 🛠 Cách Schema liên kết trong luồng chạy v4

1. Dữ liệu vào hệ thống ➡️ Lưu **`raw-snapshot`**.
2. Profiler Tool chạy ➡️ Sinh ra **`profile-result`**.
3. Agent suy luận (ReAct loop) ➡️ Sinh ra chuỗi các **`agent-trace`**.
4. Agent chốt kết luận và đề xuất ➡️ Sinh ra **`proposal`** (bao gồm nhiều **`rulespec`**).
5. Human Reviewer (HITL) phê duyệt Proposal ➡️ Ghi lại vào **`audit-event`** (có hash chain).
6. Executor chạy Luật lên DB ➡️ Báo cáo qua **`run-manifest`**.
