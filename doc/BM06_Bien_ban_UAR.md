<div align="right"><b>BM06 – DỰ THẢO</b></div>

# BIÊN BẢN RÀ SOÁT QUYỀN TRUY CẬP ĐỊNH KỲ

**(User Access Review – UAR)**

*Ban hành kèm VSF_QT_Kiem soat truy cap phan quyen va SoD*

| | |
|---|---|
| **Kỳ rà soát** | Quý ……… / Năm 20……… |
| **Số biên bản** | ……………………………… |
| **Ngày lập biên bản** | ……… / ……… / 20……… |
| **Đơn vị thực hiện** | Bộ phận Kiểm soát Dữ liệu |
| **Người lập** | ……………………………… |
| **Ngày trích xuất dữ liệu** | ……… / ……… / 20……… |

---

## I. PHẠM VI RÀ SOÁT

*Phạm vi áp dụng cho dự án P086 (nền tảng chất lượng và tuân thủ dữ liệu). Các thành phần được liệt kê theo tài liệu [P086.md](P086.md).*

| STT | Thành phần P086 (theo Phụ lục 01) | Số tài khoản người dùng | Số tài khoản đặc quyền | Số tài khoản dịch vụ | Tổng dòng quyền |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | Giao diện web (Landing Page, Executive Dashboard, Operations Workspace, Agent Chat Workspace) | | | | |
| 2 | API và xác thực (JWT, RBAC, WebSocket) | | | | |
| 3 | Ingestion và các kho dữ liệu (landing parquet, warehouse, quarantine, kho chặn, nút reset DB) | | | | |
| 4 | Quản trị chất lượng và HITL (Quality Rules, Sandbox Diff, đề xuất / duyệt / thực thi rule) | | | | |
| 5 | Agent, LLM và bộ nhớ (Groq / OpenAI / Google, bộ nhớ hội thoại, Algolia) | | | | |
| 6 | Quan sát và vận hành (log, trace agent, scheduler, alerting, /health) | | | | |
| 7 | Eval, benchmark và dataset kiểm thử (PII testset, fault injector) | | | | |
| 8 | Lane B tuân thủ (phase 2): *chưa có runtime, chưa đưa vào kỳ rà soát này* | | | | |
| 9 | Hệ thống khác (ghi rõ) | | | | |
| | **TỔNG CỘNG** | | | | |

Xác nhận đã trích xuất 100% danh sách quyền hiện hữu trên các hệ thống trong phạm vi: ☐ Có   ☐ Không (nêu lý do): ………………………………

*Nguồn trích xuất gợi ý: bảng người dùng và vai trò của P086, cấu hình ACL theo dataset, danh sách khoá API / tài khoản dịch vụ.*

### I.b. Phân rã tài khoản theo vai trò P086

| Vai trò P086 | Số tài khoản | Dataset được ACL | Ghi chú |
|---|:--:|---|---|
| Admin | | | |
| Steward (steward_a) | | | Hiện vừa ghi HITL vừa thực thi: đối chiếu xung đột SoD |
| Steward (steward_b) | | | Như trên |
| Analyst | | | Không có nút Approve |
| Viewer | | | |
| Tài khoản dịch vụ (DB, scheduler) | | | |
| Khoá API nhà cung cấp LLM | | | Không đưa raw row vào LLM, log phải được che dữ liệu nhạy cảm |

---|:--:|:--:|:--:|:--:|
| 1 | Google Cloud Platform | | | | |
| 2 | Power BI | | | | |
| 3 | Superset | | | | |
| 4 | Báo cáo theo chu kỳ | | | | |
| 5 | GitLab | | | | |
| 6 | Airflow | | | | |
| 7 | Hệ thống khác (ghi rõ) | | | | |
| | **TỔNG CỘNG** | | | | |

Xác nhận đã trích xuất 100% danh sách quyền hiện hữu trên các hệ thống trong phạm vi: ☐ Có   ☐ Không (nêu lý do): ………………………………

---

## II. KẾT QUẢ RÀ SOÁT TỔNG HỢP

| Nội dung | Số lượng | Tỷ lệ | Ghi chú |
|---|:--:|:--:|---|
| Tổng số dòng quyền đưa vào rà soát | | 100% | |
| Giữ nguyên | | | |
| Điều chỉnh mức quyền hoặc phạm vi | | | |
| Thu hồi theo xác nhận của CBLĐ / Data Owner | | | |
| Thu hồi mặc định do không được xác nhận đúng hạn | | | Theo mục IV.6 bước 2 của Quy trình |
| Tồn đọng chưa xử lý xong tại thời điểm lập biên bản | | | Nêu chi tiết tại mục IV |

| Nhóm phát hiện cần lưu ý | Số lượng | Hành động |
|---|:--:|---|
| Quyền truy cập tầng dữ liệu thô (raw) | | |
| Quyền cấp ở phạm vi toàn cục (Project / Dataset / Folder / Workspace) | | |
| Quyền không phù hợp tầng dữ liệu theo vai trò và cấp bậc | | |
| Quyền vi phạm nguyên tắc phân tách trách nhiệm (SoD) | | |
| Quyền truy cập DLCN nhạy cảm không có phê duyệt đích danh | | |
| Tài khoản dịch vụ không còn chủ sở hữu hợp lệ | | |
| Tài khoản quá thời hạn 12 tháng chưa gia hạn | | |
| Tài khoản không sử dụng vượt ngưỡng idle | | |

---

## III. KẾT QUẢ RÀ SOÁT CHI TIẾT

*Bảng chi tiết từng dòng quyền được lập thành phụ lục dữ liệu đính kèm biên bản. Mẫu cột bắt buộc như sau:*

| STT | Họ tên / Tài khoản | Khối, bộ phận | Cấp bậc | Hệ thống | Tài nguyên | Tầng DL | Mức quyền | Ngày cấp | Lần dùng gần nhất | Kết luận | Người xác nhận |
|:--:|---|---|:--:|---|---|:--:|:--:|:--:|:--:|:--:|---|
| 1 | | | | | | | | | | | |
| 2 | | | | | | | | | | | |
| … | | | | | | | | | | | |

*Cột Kết luận nhận một trong ba giá trị: Giữ nguyên / Điều chỉnh / Thu hồi.*

---

## IV. TỒN ĐỌNG VÀ HÀNH ĐỘNG KHẮC PHỤC

| STT | Nội dung tồn đọng | Mức độ | Chủ trì | Thời hạn | Trạng thái |
|:--:|---|:--:|---|:--:|:--:|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## V. KẾT QUẢ ĐỐI SOÁT MẪU CỦA ANBM

| | |
|---|---|
| **Số mẫu được chọn đối soát** | |
| **Phương pháp chọn mẫu** | ☐ Ngẫu nhiên   ☐ Theo rủi ro   ☐ Kết hợp |
| **Số mẫu phù hợp** | |
| **Số mẫu có sai lệch** | |
| **Mô tả sai lệch và hành động khắc phục** | |
| **Người thực hiện đối soát (ANBM)** | Họ tên: ……………………………   Ngày: ……… / ……… / 20……… |

---

## VI. KẾT LUẬN

| | |
|---|---|
| **Kỳ rà soát hoàn thành đúng hạn** | ☐ Có   ☐ Không – nêu lý do: ………………………………………… |
| **Phạm vi rà soát đầy đủ theo Phụ lục 01** | ☐ Có   ☐ Không – nêu lý do: ………………………………………… |
| **Toàn bộ quyền thuộc diện thu hồi đã được xử lý** | ☐ Có   ☐ Chưa – số lượng còn lại: ………… |
| **Kiến nghị của Bộ phận Kiểm soát Dữ liệu** | |

---

## VII. XÁC NHẬN VÀ PHÊ DUYỆT

| Vai trò | Chức danh – Bộ phận | Họ và tên | Ký, ngày |
|---|---|---|---|
| Người lập | Bộ phận Kiểm soát Dữ liệu | | |
| Xác nhận nghiệp vụ | CBLĐ khối, bộ phận sử dụng quyền | | |
| Xác nhận dữ liệu | Data Owner theo phân hệ | | |
| Đối soát độc lập | Ban An ninh Bảo mật (VinSOC) | | |
| Phê duyệt | Giám đốc Kiểm soát Dữ liệu | | |

*Biên bản được lưu trữ theo VSF_HC02 và là bằng chứng kiểm soát phục vụ kiểm toán ITGC nhóm Kiểm soát truy cập.*
