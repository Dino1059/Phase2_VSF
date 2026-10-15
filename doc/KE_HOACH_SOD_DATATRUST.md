# Kế hoạch nối SoD Flow ↔ DataTrust OS

> **Gộp từ:** `PLAN_NOI_SOD_DATATRUST.md` và `BUILD_PLAN_TICH_HOP.md` (bản cũ ở `luu_tru/`). Chỉ giữ nghiệp vụ, bỏ tên file, hàm, đường dẫn API vì code đã đổi.
> **Số dòng ma trận** theo `rule.md` (dòng 1 = Khởi tạo yêu cầu cấp quyền … dòng 19 = Rà soát quyền định kỳ).
> **[Còn mở]** = chờ quyết định, xem mục 12.

---

## 1. Mục tiêu và nguyên tắc

**Mục tiêu:** mọi quyền và mọi thao tác trên dữ liệu trong DataTrust đều có phiếu duyệt trong SoD Flow. Auditor trả lời được câu "ai đang truy cập dữ liệu khách hàng, ai cho phép, ai đã làm gì" trong dưới 5 phút.

| # | Nguyên tắc | Hệ quả |
|---|---|---|
| N1 | Hai hệ thống, chung trang đăng nhập, gọi qua lại nhau | SoD lo người dùng, phiếu, duyệt, quyền. DataTrust lo dữ liệu, rule, xử lý, xuất. Mỗi bên chạy độc lập |
| N2 | Không có phiếu thì không có quyền | Không còn danh sách người dùng hay vai trò khai cứng ngoài môi trường dev |
| N3 | Đề xuất, duyệt, thực thi là ba người khác nhau | Thêm vai trò Executor. Kiểm theo từng việc, không chỉ theo vai trò |
| N4 | Duyệt rule theo lô, không duyệt từng rule | Mỗi lô dữ liệu một phiếu. Phiếu xong thì Steward duyệt mọi rule của lô ngay trong DataTrust |
| N5 | Dữ liệu khách hàng không rời DataTrust | Phiếu chỉ mô tả: bảng, cột, tem PII, số dòng, thao tác, lý do. Chặn ngay lúc tạo phiếu |
| N6 | Lỗi hay quá hạn đều dẫn về trạng thái chờ | Không bao giờ tự duyệt, kể cả khi SoD không phản hồi |
| N7 | Nội dung đã duyệt là nội dung được chạy | Sửa gì sau khi duyệt thì phiếu mất hiệu lực, phải gửi lại |

---

## 2. Vai trò

| Vai trò SoD | Trong SoD | Trong DataTrust | Việc chính |
|---|---|---|---|
| REQ | Có | Analyst | Xem cảnh báo, đề xuất rule và xử lý dữ liệu, yêu cầu xuất |
| SO | Có | Steward | Duyệt rule trong lô đã có phiếu |
| OPS | Có | Executor (mới) | Chạy rule và xử lý dữ liệu **đã duyệt** |
| IAM | Có | Admin | Cấp, thu quyền. Không đọc dữ liệu khách hàng |
| AUD | Có | Auditor | Xem nhật ký, xuất báo cáo bằng chứng. Không đọc dữ liệu |
| LM, DPO, CISO | Có | **Không vào** | Duyệt phiếu trong SoD |
| DEV, REL | Có | Không vào | Chỉ phiếu thay đổi mã |

- **Ba người khác nhau cho mỗi việc:** người đề xuất, người duyệt, người thực thi. DataTrust kiểm cả ba, lấy từ phiên đăng nhập, không lấy từ dữ liệu người dùng gửi lên.
- **Việc do AI đề xuất:** người bấm nhận hoặc gửi duyệt đề xuất đó là người đề xuất. AI không bao giờ là người duyệt hay người chạy.
- **Cặp vai trò cấm giữ cùng lúc:** REQ+SO, SO+OPS, REQ+OPS, IAM+AUD, IAM+REQ, IAM+OPS. Cấp quyền tạo ra cặp cấm thì bị từ chối và báo IAM.
- Không ai duyệt phiếu, rule hay đề xuất do chính mình yêu cầu, ở mọi bước.

---

## 3. Đăng nhập chung và đi lại giữa hai hệ thống

1. Người dùng chỉ đăng nhập ở SoD. DataTrust không giữ mật khẩu.
2. Bấm "Mở DataTrust": SoD cấp một vé ký số, dùng một lần, hạn 60 giây. DataTrust kiểm vé, đổi lấy phiên, lấy người dùng và vai trò từ vé.
3. Mỗi lần thao tác, DataTrust kiểm người đó còn quyền còn hạn cho đúng dataset. Không có thì từ chối.
4. Trong DataTrust có nút quay về SoD (hộp phiếu, phiếu của tôi). Mã phiếu hiện ở DataTrust là đường dẫn sang phiếu bên SoD.
5. Danh tính duy nhất hai bên: tên đăng nhập của SoD.
6. Sau này công ty có SSO thì thay vé bằng SSO, phần còn lại giữ nguyên.

Đến khi xong mục này, kiểm "người chạy ≠ người duyệt" chưa đáng tin vì danh tính vẫn giả được. Đây là việc phải làm sớm.

---

## 4. Cấp và thu quyền

1. Người dùng điền form xin quyền trong SoD: Hệ thống = DataTrust, Tài nguyên = dataset, Tầng, Mức quyền, Vai trò, Thời hạn, có DLCN không.
2. SoD sinh chuỗi duyệt theo ma trận: luôn có LM (dòng 2); có DLCN thì thêm DPO (dòng 3); Tầng 3 thì thêm SO và CISO (dòng 4). IAM hoàn tất (dòng 5).
3. Phiếu hoàn tất: SoD báo DataTrust "đã cấp quyền", kèm mã phiếu, người, vai trò, dataset, hạn.
4. Thu hồi: phiếu thu hồi hoàn tất thì SoD báo "đã thu hồi". DataTrust khoá ngay ở thao tác kế tiếp. Mục tiêu dưới 24 giờ làm việc.
5. Thời hạn quyền mặc định 90 ngày; mời tạm 30 ngày. Nhắc gia hạn trước 7 ngày.

| Ô form | Quyền DataTrust |
|---|---|
| Vai trò SoD | Vai trò DataTrust theo mục 2 |
| Tài nguyên | Các dataset được vào |
| Thời hạn | Ngày hết quyền |

---

## 5. Duyệt rule theo lô

1. Một lô dữ liệu được nạp vào DataTrust.
2. DataTrust tự tạo phiếu "Duyệt rule lô" bên SoD: dataset, mã lô, số dòng, lô có cột DLCN không. Người yêu cầu là Steward trực.
3. SoD sinh chuỗi duyệt: luôn có LM; lô có DLCN thì thêm DPO; dataset Tầng 3 thì thêm SO và CISO. IAM hoàn tất.
4. Phiếu xong, SoD báo DataTrust. Steward đó được quyền duyệt rule trong đúng lô đó.
5. Trong lô, Steward duyệt mọi rule, kể cả rule AI đề xuất thêm sau khi phiếu đã duyệt. Executor (người khác) chạy rule đã duyệt.
6. Quyền tự hết khi lô đóng (mọi rule đã có quyết định) hoặc tới hạn. Rule của lô khác cần phiếu của lô đó.

**Đơn vị lô (đã chốt):** cấu hình theo từng dataset, chọn theo đợt nạp, theo ngày hoặc theo tuần; mặc định **theo ngày**. Đổi đơn vị chỉ đổi cách tính mã lô, không đổi luồng.

| Đơn vị | Số phiếu | Rủi ro |
|---|---|---|
| Theo đợt nạp | Bằng số lần nạp | Nạp liên tục thì nhiều phiếu |
| Theo ngày | 1 phiếu/ngày/dataset | Cuối tuần phải có người duyệt |
| Theo tuần | 1 phiếu/tuần/dataset | Ít phiếu nhất, nhưng rule sai sống lâu hơn trước khi bị rà soát |

---

## 6. Xử lý dữ liệu cách ly và thay đổi rule (phiếu từng việc)

Các việc dưới đây đổi dữ liệu hoặc đổi cách xử lý dữ liệu, nên mỗi việc một phiếu.

| # | Việc trong DataTrust | Dòng ma trận | Ai duyệt |
|---|---|---|---|
| D1 | Sửa / xử lý bản ghi bị cách ly (người hoặc AI đề xuất) | 13. Thay đổi chính sách vận hành | LM A, SO A, CISO R, DPO C. Có PII thì DPO R |
| D2 | Thêm, sửa, bật, tắt rule xử lý | 13 | Như D1 |
| D3 | Gỡ cách ly cho bản ghi lỗi đi tiếp (ngoại lệ) | 16. Phê duyệt ngoại lệ kiểm soát | DPO A, SO A, CISO A |
| D4 | Truy vấn trực tiếp dữ liệu PII khách hàng | 14 + 5 | DPO A, SO A, CISO R |
| D5 | Xuất dữ liệu PII khách hàng | 15 + 5 | Mục 7 |

**Luồng một đề xuất:**

1. Người hoặc AI đề xuất (Nháp). Chạy thử trên bản sao đạt (Chạy thử đạt).
2. Người đề xuất bấm "Gửi duyệt". DataTrust chốt mã băm nội dung, tạo phiếu bên SoD, lưu mã phiếu (Chờ duyệt).
3. SoD không phản hồi thì đề xuất ở "Chờ gửi", có nút gửi lại. Không bao giờ tự duyệt.
4. Chuỗi duyệt chạy bên SoD (SLA, nhắc, leo thang có sẵn).
5. SoD báo kết quả: Được duyệt, hoặc Từ chối / Hết hạn / Huỷ.
6. Duyệt xong, SoD giao bước thực hiện cho một Prod. Op. không xung đột và báo DataTrust "đã duyệt, Executor là …". Phiếu SoD vẫn mở, chờ bước thực hiện. Executor bấm "Thực thi" trong DataTrust. DataTrust kiểm:
   - phiếu đã duyệt;
   - nội dung không đổi so với lúc gửi, và dữ liệu nguồn không đổi. Lệch thì "Lỗi thời", phải gửi lại;
   - người chạy đúng là Executor SoD đã giao, không phải người đề xuất, không nằm trong danh sách người duyệt;
   - chưa chạy lần nào (chạy lại không có tác dụng).
7. Chạy xong (Đã xử lý hoặc Đã hoàn tác), DataTrust báo SoD "đã thực hiện". SoD kiểm lại người chạy (đúng người được giao hoặc người được ủy quyền, còn vai trò OPS, không xung đột), ghi bước thực hiện nhân danh Executor, phiếu hoàn tất.
8. Prod. Op. không thực thi thì từ chối bước thực hiện trong SoD, kèm lý do; đề xuất thành "Từ chối". Trong SoD không có nút "Hoàn tất" cho bước này.
9. Phiếu duyệt theo quy trình cũ (không có bước thực hiện) không chạy được, phải gửi duyệt lại.

Đề xuất đang chờ duyệt phải còn nguyên khi DataTrust khởi động lại. Khi đề xuất đã có phiếu SoD, DataTrust không cho duyệt nội bộ nữa. Duyệt hai người nội bộ của DataTrust bỏ, thay bằng chuỗi duyệt SoD.

---

## 7. Xuất dữ liệu PII (phiếu từng lần)

1. Analyst yêu cầu xuất trong DataTrust. DataTrust tạo phiếu xuất PII (dòng 15) bên SoD, yêu cầu ở trạng thái chờ.
2. Phiếu chỉ chứa mô tả: dataset, cột và tem PII, mức che từng cột, số dòng, đích, mục đích, thời hạn, mã băm nội dung. Cần dòng mẫu thì thay giá trị bằng nhãn (`[SĐT]`, `[EMAIL]`).
3. LM và DPO duyệt trong SoD. Sau bước duyệt, IAM mở quyền tạm (dòng 5).
4. Lúc xuất, DataTrust kiểm: người xuất không nằm trong danh sách người duyệt, nội dung không đổi, chưa hết hạn. Đạt thì xuất file đã che đúng mức trên phiếu và ghi nhật ký truy cập.

Trạng thái: `CHỜ GỬI` → `CHỜ DUYỆT` → `ĐƯỢC DUYỆT` → `ĐÃ XUẤT`, hoặc `TỪ CHỐI`, `HẾT HẠN`, `LỖI THỜI`.

**Mức che khi xuất:**

| Mức PII của cột | Mức che | Cách che |
|---|---|---|
| Nhạy cảm (GPS chính xác, CCCD, sức khoẻ, sinh trắc) | 100% | Thay bằng nhãn hoặc bỏ cột. GPS làm tròn tới khu vực |
| Cơ bản (họ tên, SĐT, email, biển số, mã khách hàng) | 50% | SĐT giữ 3 số cuối, email giữ tên miền, họ tên giữ chữ cái đầu, biển số giữ mã tỉnh, mã khách hàng thay bằng mã giả cố định |
| Không phải PII | 0% | Giữ nguyên |

- DataTrust tự gán mức che theo danh sách cột PII. Người yêu cầu chỉ được **tăng** mức che.
- Muốn giảm mức che phải có phiếu ngoại lệ (dòng 16: DPO, SO, CISO duyệt).
- Che 50% vẫn là dữ liệu cá nhân theo luật, nên vẫn phải có DPO. Nhiều cột che 50% ghép lại có thể đoán ra người; DPO xem tổ hợp cột trên phiếu.
- Mức che nằm trong nội dung đã duyệt. Lúc xuất, che đúng mức trên phiếu.

---

## 8. SLA khi duyệt lâu

Chạy nền, không phụ thuộc người dùng mở trang.

| Mốc | Hành động |
|---|---|
| 75% thời hạn | Nhắc người được giao |
| 100% | Báo thêm người dự phòng cùng vai trò và Admin SoD |
| 200% | Báo CISO và Auditor |
| 7 ngày không ai xử lý | Admin SoD đóng phiếu "hết hạn", có lý do |

- Thời hạn (đã chốt): thực hiện 8 giờ, rà soát 24 giờ, phê duyệt 24 giờ. Xem lại khi có số liệu thật. Mức "Khẩn cấp" còn 1/4 thời hạn.
- Mỗi mốc chỉ báo một lần. Không bao giờ tự duyệt.
- Người vắng thì ủy quyền cho người cùng vai trò, có hạn, kiểm lại xung đột.
- Sau này leo thang thêm tới quản lý trực tiếp, khi lấy được sơ đồ tổ chức từ HR.

---

## 9. Bằng chứng cho Auditor

Auditor chọn dataset và khoảng thời gian, xuất CSV hoặc PDF. Mỗi dòng ghép các nguồn qua mã phiếu:

| Câu hỏi | Nguồn |
|---|---|
| Ai đang có quyền | Danh sách quyền (DataTrust) |
| Ai đề xuất, ai duyệt, lúc nào, nội dung nào | Phiếu và quyết định duyệt (SoD) |
| Ai thực thi, ai đã đọc hoặc xuất | Nhật ký thực thi và nhật ký truy cập (DataTrust) |

- Mỗi lần thực thi ghi kèm mã phiếu và mã băm nội dung đã duyệt. Báo cáo cho thấy mã băm hai bên khớp nhau.
- Phạm vi "dữ liệu khách hàng": các dataset có cột PII (chuyến xe, khách hàng, tài xế, phản hồi có PII, telemetry có GPS).
- Nhật ký truy cập ghi người, vai trò, dataset, cột, số dòng, mục đích, đích, mã phiếu, thời điểm. Không ghi giá trị dữ liệu. Lưu 5 năm, bằng thời hạn lưu phiếu của SoD.
- Nhật ký hai bên có chuỗi băm, chứng minh được không bị sửa. Việc xuất báo cáo cũng được ghi nhật ký.
- Đối soát hằng ngày: quyền nào không có phiếu thì bị khoá và báo Auditor. Rà soát quyền hằng quý (dòng 19).

---

## 10. Hai hệ thống báo cho nhau những gì

| Chiều | Sự kiện | Khi nào | Bên nhận làm gì |
|---|---|---|---|
| SoD → DT | Đã cấp quyền | Phiếu cấp quyền hoàn tất | Ghi quyền kèm mã phiếu, hạn |
| SoD → DT | Đã thu hồi | Phiếu thu hồi hoàn tất | Khoá quyền và phiên ngay |
| SoD → DT | Lô được duyệt | Phiếu "Duyệt rule lô" hoàn tất | Mở quyền duyệt rule của lô cho Steward |
| SoD → DT | Phiếu được duyệt | Phiếu xử lý / xuất duyệt xong, tới bước thực hiện | Đề xuất / yêu cầu sang "Được duyệt", ghi Executor được giao và danh sách người duyệt |
| SoD → DT | Phiếu đóng | Từ chối, huỷ, hết hạn | Đề xuất / yêu cầu sang "Từ chối" |
| DT → SoD | Tạo phiếu | Gửi duyệt, lô mới, yêu cầu xuất | SoD sinh chuỗi duyệt, trả mã phiếu |
| DT → SoD | Huỷ phiếu | Yêu cầu bên DT bị huỷ hoặc lỗi thời | Đóng phiếu (nếu chưa tới bước thực hiện) |
| DT → SoD | Đã thực hiện | Executor chạy xong | Kiểm người chạy, ghi bước thực hiện, phiếu hoàn tất; báo lại "Phiếu đóng (hoàn tất)" |
| DT → SoD | Hỏi trạng thái | Định kỳ, phòng khi lỡ sự kiện | Trả trạng thái, Executor được giao, danh sách người duyệt |

Quy tắc chung:
- Không có dữ liệu khách hàng trong bất kỳ thông điệp nào.
- Mọi thông điệp có chữ ký và giờ gửi; sai chữ ký hoặc quá 5 phút thì bị từ chối.
- Bên kia đang tắt thì giữ lại và gửi lại khi lên. Nhận trùng thì chỉ áp dụng một lần.
- Sự kiện thu hồi quyền luôn được gửi trước.
- Tạo phiếu trùng (cùng đề xuất, cùng nội dung) thì trả lại phiếu cũ.

---

## 11. Lộ trình

Giai đoạn sau chỉ bắt đầu khi giai đoạn trước đạt hết kịch bản kiểm thử.

| GĐ | Nội dung | Hiện trạng (15/10) |
|---|---|---|
| 0 | Chốt các mục còn mở chặn GĐ 1–2 | Đang làm |
| 1 | Luồng duyệt xử lý dữ liệu cách ly (mục 6): đề xuất lưu bền, gửi phiếu, nhận kết quả, đối soát định kỳ, chặn duyệt nội bộ, tách ba người | **Đã xong** ở cả hai bên (15/10), kể cả Executor và báo "đã thực hiện" về SoD. Áp cho D1; D2, D3 ở GĐ 3 |
| 2 | Đăng nhập chung và tách ba người (mục 2, 3); cấp, thu quyền qua phiếu (mục 4) | Chưa có. DataTrust chưa có đăng nhập thật |
| 3 | Thay đổi rule và gỡ cách ly qua phiếu (D2, D3) | Chưa có. Bật/tắt rule và gỡ cách ly hiện chưa cần duyệt |
| 4 | Duyệt rule theo lô (mục 5), xuất PII có che (mục 7) | Chưa có |
| 5 | Bằng chứng hai bên, đối soát hằng ngày, rà soát quý (mục 9) | Một phần: SoD có xuất bằng chứng phiếu; DataTrust chưa ghép |
| 6 | Chạy thử đầu-cuối, chuyển tài khoản cũ sang quyền có phiếu, bật production | Chưa |
| 7 | Mở rộng sau một quý: SSO, quản lý trực tiếp từ HR, quyền theo nhóm, Steward theo dataset và vùng, nối GitLab / GCP / Power BI, tem Lane B thay danh sách cột PII | — |

**Kịch bản chạy thử đầu-cuối (GĐ 6):**
1. Đăng nhập SoD, mở DataTrust bằng vé.
2. Chạy pipeline một dataset nhỏ, có bản ghi cách ly.
3. AI đề xuất sửa một cột, chạy thử đạt; Analyst gửi duyệt → phiếu bên SoD.
4. Lần lượt LM, DPO, SO duyệt trong SoD.
5. DataTrust thành "Được duyệt"; Executor thực thi; bản ghi sang vùng sạch; SoD ghi bước thực hiện.
6. Auditor xuất bằng chứng, đối chiếu được người đề xuất, người duyệt, người thực thi, mã băm hai bên.

**Quay lui:** lỗi ở GĐ 6 thì bật lại chế độ cũ của DataTrust bằng cấu hình. SoD giữ toàn bộ phiếu và sự kiện chưa gửi để gửi lại sau.

---

## 12. Kịch bản kiểm thử nghiệp vụ

| # | Tình huống | Kết quả đúng |
|---|---|---|
| **Danh tính và tách người** | | |
| K01 | Vào DataTrust không qua vé, hoặc tự khai tên / vai trò | Bị từ chối ngoài môi trường dev |
| K02 | Vé bị dùng lại hoặc quá 60 giây | Bị từ chối |
| K03 | Người dùng tự khai "người duyệt" khi gửi | Bị bỏ qua, nhật ký ghi người thật |
| K04 | Steward chạy rule | Bị chặn |
| K05 | Người chạy là người đề xuất hoặc một trong những người duyệt | Bị chặn, ghi nhật ký |
| K06 | Duyệt việc do chính mình đề xuất | Bị chặn |
| **Cấp quyền** | | |
| K07 | Phiếu cấp quyền hoàn tất | Vào được đúng dataset |
| K08 | Phiếu thu hồi hoàn tất | Bị khoá ở thao tác kế tiếp |
| K09 | Quyền hết hạn | Bị chặn; đã được nhắc trước 7 ngày |
| K10 | Cấp vai trò tạo cặp cấm (ví dụ OPS cho người đang là SO) | Không cấp, báo IAM |
| K11 | LM, DPO, CISO mở dữ liệu trong DataTrust | Bị chặn |
| **Xử lý dữ liệu cách ly** | | |
| K12 | Duyệt nội bộ trong DataTrust khi đã có phiếu SoD | Bị chặn |
| K13 | Thực thi khi phiếu chưa duyệt | Bị chặn |
| K14 | Sửa đề xuất sau khi duyệt, hoặc dữ liệu nguồn đổi | "Lỗi thời", không chạy, phải gửi lại |
| K15 | Phiếu bị từ chối / hết hạn / huỷ | Đề xuất "Từ chối", không thực thi được |
| K16 | Thực thi hai lần | Lần hai không có tác dụng |
| K17 | Đề xuất có cột PII | Chuỗi duyệt có DPO |
| K18 | DataTrust khởi động lại khi đề xuất đang chờ | Đề xuất còn nguyên |
| K19 | Bật / tắt rule hoặc gỡ cách ly không có phiếu | Bị chặn |
| **Duyệt lô** | | |
| K20 | Lô mới được nạp | Có phiếu "Duyệt rule lô"; lô có DLCN thì có DPO; Tầng 3 thì có SO, CISO |
| K21 | Steward duyệt rule khi phiếu lô chưa xong, hoặc rule thuộc lô khác | Bị chặn |
| K22 | AI đề xuất thêm rule sau khi phiếu lô đã duyệt | Steward duyệt được; lô đóng hoặc hết hạn thì không |
| **Xuất PII** | | |
| K23 | Xuất PII được duyệt | File che đúng mức trên phiếu, có nhật ký truy cập kèm mã phiếu |
| K24 | Người xuất cũng là người duyệt | Bị chặn |
| K25 | Phiếu xuất ghi cột nhạy cảm che 50% mà không có ngoại lệ | Không tạo phiếu; có ngoại lệ thì chuỗi thêm dòng 16 |
| **An toàn nội dung và kết nối** | | |
| K26 | Nội dung phiếu có SĐT, email, biển số hoặc trường lạ | Không tạo phiếu |
| K27 | Thông điệp sai chữ ký hoặc quá 5 phút | Bị từ chối |
| K28 | Cùng một sự kiện nhận hai lần, hoặc sai thứ tự | Áp dụng đúng một lần, theo thời điểm phát sinh |
| K29 | DataTrust tắt lúc SoD gửi | SoD giữ lại, gửi lại khi DataTrust lên |
| K30 | SoD tắt lúc gửi duyệt hoặc yêu cầu xuất | Đứng ở "Chờ gửi", không tự duyệt, không xuất |
| K31 | Có cả sự kiện cấp và thu hồi đang chờ | Thu hồi được gửi trước |
| **SLA** | | |
| K32 | Bước duyệt quá 75% / 100% / 200% | Nhắc / báo dự phòng và Admin / báo CISO và Auditor, mỗi mốc một lần |
| K33 | Quá hạn bao lâu cũng vậy | Không bao giờ tự duyệt |
| K34 | Người duyệt vắng | Ủy quyền cho người cùng vai trò, kiểm lại xung đột |
| **Bằng chứng** | | |
| K35 | Auditor xuất báo cáo một dataset | Xong dưới 5 phút; mỗi việc có người đề xuất, người duyệt kèm thời điểm, người thực thi, mã băm hai bên khớp |
| K36 | Quyền tạo tay, không có phiếu | Đối soát khoá và báo Auditor |
| K37 | Sửa nhật ký | Kiểm chuỗi băm phát hiện |
| K38 | Rà soát quyền quý | Số liệu khớp danh sách quyền |

---

## 13. Đã chốt / Còn mở

**Đã chốt**

| Nội dung | Giá trị |
|---|---|
| Kiến trúc | Hai hệ thống, chung đăng nhập (qua SoD), gọi qua lại |
| Người thực thi | Executor (OPS), khác người đề xuất và người duyệt. Phiếu DataTrust nâng Prod. Op. lên P ở dòng 13 (cùng cách nâng DPO khi có PII), không thêm dòng ma trận. Duyệt xong, SoD giao bước thực hiện cho một OPS không xung đột; bước này chỉ hoàn tất khi DataTrust báo Executor đã chạy |
| Danh tính hai bên | Tên đăng nhập SoD |
| Duyệt hai người nội bộ DataTrust | Bỏ, dùng chuỗi duyệt SoD |
| Đơn vị lô | Cấu hình theo dataset, mặc định theo ngày |
| Thời hạn quyền | 90 ngày; mời tạm 30 ngày |
| SLA | 8 / 24 / 24 giờ; xem lại khi có số liệu thật |
| Leo thang | Người dự phòng cùng vai trò và Admin SoD; sau thêm quản lý trực tiếp |
| Danh sách cột PII | Lập từ `data-field-legal-scope.md`, DPO duyệt |

**Còn mở**

| # | Câu hỏi | Đề xuất | Chặn GĐ |
|---|---|---|---|
| 1 | Ánh xạ việc → dòng ma trận (bảng mục 6) | Như bảng | 1, 3 |
| 2 | Xuất PII ra nước ngoài có cho làm gấp (break-glass) không | Không | 4 |
| 3 | Ai giữ khoá ký, xoay khi nào | IAM, xoay hằng quý | 2 |
| 4 | Cột nào thuộc mức "nhạy cảm" và quy tắc che 50% từng loại | Như bảng mục 7, DPO duyệt | 4 |
| 5 | Phiếu và tài khoản cũ có phải chuyển không | Tạo phiếu cấp quyền cho tài khoản đang dùng; phiếu đã đóng giữ nguyên | 6 |
| 6 | Bản demo cho Auditor có cần đăng nhập thật không | Có, nếu demo cho Auditor; không, nếu chỉ demo luồng | 2 |

---

## 14. Ngoài phạm vi

- Lỗi XCom của telemetry và luật Lane B cho các cột mới: độc lập, làm song song.
- SoD không chứa SCC, đánh giá rủi ro chuyển giao, hợp đồng xử lý, DPIA. Các giấy tờ này nằm ở sổ đăng ký của DPO / pháp chế.
