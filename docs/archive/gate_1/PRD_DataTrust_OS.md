# Tài Liệu Yêu Cầu Sản Phẩm (PRD)

**Mã dự án: DATA-02 | Phiên bản: v3.0**

**Ngày cập nhật: 02/08/2026**

**Nhóm:**
* Thanh (Sản phẩm & Đánh giá)
* Ngân (Dữ liệu & Agent)
* Dũng (Pipeline & Công cụ)
* Huyền (Giao diện & Triển khai)

**Ngày khóa tính năng: 26/08/2026 lúc 23:59** — Sau thời điểm này, không thêm tính năng mới.

---

## 1. Tổng Quan

**Tên dự án**
AI Agent xây dựng & kiểm tra Data Quality và phát hiện bất thường

**Tầm nhìn dài hạn**
Trở thành nền tảng quản trị dữ liệu cho các doanh nghiệp Việt Nam, giúp đội ngũ dữ liệu tập trung vào phân tích và ra quyết định thay vì lãng phí thời gian làm sạch dữ liệu thủ công.

**Mục đích ngắn hạn (MVP — dự án hiện tại)**
Xây dựng DataTrust OS — một hệ thống AI tự động hóa quy trình kiểm tra và làm sạch dữ liệu, case study cho hệ sinh thái VinGroup (VinFast, Xanh SM, V-GREEN), bao gồm:

* Tự động phát hiện lỗi trong dữ liệu (giá trị bất thường, thiếu dữ liệu, mâu thuẫn logic)
* Đề xuất các quy tắc chất lượng dữ liệu bằng AI
* Cho phép người phụ trách dữ liệu xem xét và phê duyệt trước khi áp dụng
* Tạo ra bộ dữ liệu sạch có thể truy vết đầy đủ

## 2. Mục Tiêu Kinh Doanh

**Vấn đề cần giải quyết**
Hiện nay, khi một đội ngũ dữ liệu tiếp nhận một nguồn dữ liệu mới, họ phải bỏ ra 60–80% thời gian chỉ để làm các việc thủ công như: kiểm tra cột dữ liệu, viết quy tắc lọc lỗi, xử lý ngoại lệ, và ghi lại lịch sử thay đổi — trong khi đó mới là phần chuẩn bị, chưa phải phân tích thực sự.

**Chỉ số thành công đo lường được**

| Chỉ số | Mục tiêu |
| :--- | :--- |
| Giảm thời gian onboarding một nguồn dữ liệu | Từ ~3 ngày → ~3 giờ |
| Độ chính xác của quy tắc AI đề xuất | ≥ 80% (Precision) |
| Tỷ lệ phát hiện lỗi so với cách làm cũ | AI Agent (A1) phát hiện nhiều hơn ≥ 10% |
| Toàn bộ test tự động hóa vượt qua | 125/125 test cases |
| Không có dữ liệu bị mất hoặc xóa nhầm | 100% — dữ liệu lỗi được cách ly, không xóa |

## 3. Đối Tượng Người Dùng

### Người phụ trách dữ liệu (Data Steward)
Là người trực tiếp làm việc với dữ liệu và chịu trách nhiệm về chất lượng dữ liệu trong từng dự án cụ thể.

* **Nhu cầu & Quyền hạn:** Có toàn quyền thao tác các tính năng chuyên môn trong phạm vi dự án được phân công (bao gồm: tải file, xem báo cáo phân tích, phê duyệt/chỉnh sửa/từ chối các quy tắc AI đề xuất, xem biểu đồ).
* **Giới hạn:** Không thể xem hoặc can thiệp vào dữ liệu của các dự án khác, không có quyền vào trang cấu hình tài khoản.

### Quản trị viên hệ thống (System Admin)
Là người thiết lập hệ thống ban đầu và cấp phát tài nguyên cho các dự án.

* **Nhu cầu & Quyền hạn:** Tập trung quản lý danh sách tài khoản người dùng và thiết lập phân quyền người dùng vào các dự án tương ứng (Project Access Control).
* **Giới hạn:** Chỉ đóng vai trò quản lý tài khoản, không tham gia vào việc duyệt quy tắc AI hay tác động trực tiếp lên dữ liệu chuyên môn.

## 4. Phạm Vi Sản Phẩm (Scope)

**✅ Trong phạm vi dự án**
* Nhận dữ liệu từ file CSV hoặc Parquet (các định dạng phổ biến)
* Tự động phân tích cấu trúc và thống kê mô tả của dữ liệu
* Phát hiện bất thường: giá trị thiếu, trùng lặp, ngoài khoảng cho phép, mâu thuẫn logic, định dạng sai
* Đề xuất quy tắc chất lượng dữ liệu có kèm lý do giải thích
* Giao diện phê duyệt để người phụ trách chấp nhận, chỉnh sửa hoặc từ chối từng đề xuất
* Tạo bộ dữ liệu sạch (CleanDB) và bảng cách ly dữ liệu lỗi (Quarantine)
* Lưu đầy đủ lịch sử thay đổi với mã xác thực (SHA-256)
* Xử lý phản hồi tiếng Việt (bao gồm teen-code như "ko sạc dc")
* So sánh hiệu quả giữa 3 phương pháp: chatbot đơn giản (C0) vs pipeline cố định (C1) vs AI Agent thông minh (A1)

**❌ Ngoài phạm vi (không làm trong dự án này)**
* Lập lịch chạy tự động định kỳ theo Airflow/Dagster
* Cho phép AI tự ý thay đổi dữ liệu mà không có người duyệt
* Xử lý dữ liệu phân tán quy mô lớn (Spark/Flink)

## 5. Tính Năng Cốt Lõi

### 5.1 Phân tích dữ liệu tự động (Profiler)
Khi người dùng tải lên file dữ liệu, hệ thống tự động quét và tạo báo cáo tổng quan: số lượng hàng/cột, tỷ lệ giá trị thiếu, phân bố thống kê, các trường bắt buộc, kiểu dữ liệu. Toàn bộ dữ liệu gốc được "đóng dấu" mã SHA-256 để đảm bảo không ai thay đổi lén.

**Yêu cầu giao diện:** Hiển thị báo cáo dạng bảng trực quan, dễ đọc, có thể mở rộng xem chi tiết từng cột.

### 5.2 Phát hiện bất thường (Anomaly Detection)
Hệ thống sử dụng hai thuật toán kết hợp để tính điểm bất thường:
* Phương pháp thống kê (Z-Score): Phát hiện giá trị lạ dựa trên phân phối chuẩn
* Machine Learning (Isolation Forest): Phát hiện các điểm bất thường phức tạp hơn theo nhiều chiều

Kết quả được tổng hợp thành một điểm bất thường duy nhất, dễ hiểu.
**Yêu cầu giao diện:** Hiển thị timeline bất thường, cho phép lọc theo mức độ nghiêm trọng (Thấp / Vừa / Cao / Nghiêm trọng).

### 5.3 Đề xuất quy tắc bằng AI (Rule Proposer)
Dựa trên kết quả phân tích, mô hình AI (Gemma 4 26b) đề xuất các quy tắc chất lượng dữ liệu cụ thể. Ví dụ: Cột `trip_miles` không được âm, Nếu điểm đón và trả trùng nhau thì quãng đường phải bằng 0, Nhiệt độ trạm sạc không được vượt quá 80°C.

Mỗi đề xuất kèm theo lý do giải thích bằng ngôn ngữ tự nhiên và mức độ tin cậy.

**Yêu cầu giao diện:** Thẻ đề xuất dạng card, hiển thị quy tắc + lý do + nút Đồng ý / Chỉnh sửa / Từ chối. Hỗ trợ phê duyệt hàng loạt.

### 5.4 Xử lý tiếng Việt (Vietnamese NLP)
Với dữ liệu phản hồi khách hàng bằng tiếng Việt, hệ thống tự động:
* Chuẩn hóa teen-code: “ko sac dc” → “không sạc được”
* Trích xuất thực thể: địa điểm (*Vincom Bà Triệu*), thiết bị (*Trạm sạc V-GREEN*), loại lỗi
* Đối chiếu với dữ liệu cảm biến thực tế để xác nhận khiếu nại

### 5.5 Tạo dữ liệu sạch (CleanDB & Quarantine)
Sau khi người phụ trách phê duyệt, hệ thống thực thi các quy tắc một cách xác định (không có AI can thiệp):
* Hàng đạt chuẩn → CleanDB (dữ liệu sạch để dùng tiếp)
* Hàng vi phạm → Quarantine (bảng cách ly, kèm lý do cụ thể)

Toàn bộ kết quả được ghi vào manifest có mã SHA-256 để kiểm toán sau này.

## 6. Yêu Cầu Phi Chức Năng

| Tiêu chí | Mức yêu cầu |
| :--- | :--- |
| Tốc độ phản hồi AI | Mỗi lần gọi AI tối đa 60 giây, tự thử lại 3 lần nếu lỗi |
| Độ tin cậy | AI chỉ đề xuất, không tự thực thi; mọi thay đổi cần người duyệt |
| Bảo mật dữ liệu | AI chỉ nhìn thấy thống kê tổng hợp, không bao giờ nhìn thấy dữ liệu thô |
| Kiểm toán | Mọi hành động đều được ghi lại, không thể xóa lịch sử |
| Khả năng phục hồi | Nếu hệ thống gặp lỗi, dữ liệu gốc luôn được bảo toàn nguyên vẹn |
| Phân quyền | 2 cấp độ:<br>1. Admin (System-level): Quản trị tài khoản và phân quyền dự án.<br>2. User/Steward (Project-level): Toàn quyền sử dụng tính năng (view/edit/approve) trong dự án được giao. |

## 7. Tiêu Chí Hoàn Thành (Acceptance Criteria)

| Tính năng | Điều kiện được coi là hoàn tất |
| :--- | :--- |
| Phân tích dữ liệu | Upload file → nhận báo cáo thống kê đầy đủ trong vòng 30 giây đối với các tập dữ liệu nhỏ/vừa (ví dụ: dưới 100MB hoặc < 1 triệu dòng) |
| Phát hiện bất thường | Tỷ lệ phát hiện đúng ≥ 80% trên bộ dữ liệu test có lỗi đã biết |
| Đề xuất quy tắc AI | ≥ 80% quy tắc đề xuất là hợp lệ và có thể thực thi được |
| HITL phê duyệt | Người dùng có thể Đồng ý / Chỉnh sửa / Từ chối từng quy tắc; hành động được lưu lại |
| Tạo CleanDB | Sau khi duyệt, dữ liệu sạch và quarantine được tạo ra đúng, không mất hàng nào |
| Kiểm toán | Mọi thao tác đều xuất hiện trong audit log kèm thời gian và người thực hiện |
| Xử lý tiếng Việt | Teen-code được chuẩn hóa đúng; thực thể (địa điểm, thiết bị) được trích xuất chính xác |
| So sánh A1 vs C1 | A1 phát hiện nhiều lỗi hơn C1 ≥ 10% VÀ độ chính xác ≥ 80% |

## 8. Timeline và Mốc Quan Trọng

| Giai đoạn | Thời gian | Mục tiêu chính |
| :--- | :--- | :--- |
| Sprint 1 — Nền tảng | 30/07 – 05/08 | Tài liệu dữ liệu, kiến trúc hệ thống, wireframe giao diện |
| Sprint 2 — Pipeline | 06/08 – 12/08 | Profiler, validator, compiler, state machine hoạt động end-to-end |
| Sprint 3 — Agent & HITL | 13/08 – 19/08 | AI Agent (A1), giao diện phê duyệt, tích hợp đầy đủ |
| Sprint 4 — Đánh giá | 20/08 – 26/08 | Benchmark C0 vs C1 vs A1, kiểm tra Agentic Gate, khóa tính năng |
| Sprint 5 — Hoàn thiện | 27/08 – 03/09 | Docker deployment, test toàn diện, 3 lần diễn thử, sẵn sàng demo |
