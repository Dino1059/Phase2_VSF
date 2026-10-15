# Kịch bản test: phủ 19 hoạt động kiểm soát bằng phiếu nghiệp vụ

Phạm vi: trang chọn loại phiếu, 7 loại phiếu nghiệp vụ mới, phiếu rà soát quyền định kỳ tự động, cột "Loại phiếu" ở trang Ma trận, bộ lọc Bằng chứng, và hồi quy các phiếu cũ.

Đánh dấu `[x]` khi đạt. Ghi mã phiếu (SOD-…) vào cột ghi chú để đối chiếu nhật ký.

---

## 0. Chuẩn bị (làm một lần)

| # | Việc | Kết quả mong đợi | ✓ |
|---|---|---|---|
| 0.1 | `cd web && npm test && npm run test:security` | Unit 17/17, security 83/83 đạt | [ ] |
| 0.2 | `npx prisma db seed` trên DB `sod` | Có dòng `+ system (tài khoản hệ thống, không đăng nhập được)` | [ ] |
| 0.3 | Tắt và chạy lại `npm run dev` (cần khởi động lại để nạp job rà soát) | Log có `[review] đã mở phiếu SOD-… cho 2026-Q4` | [ ] |
| 0.4 | Thử đăng nhập bằng `system` | Bị từ chối (tài khoản bị vô hiệu hoá) | [ ] |

> Lưu ý: bước 0.3 sẽ tạo thật một phiếu rà soát quý 2026-Q4 trong DB `sod`. Không muốn tạo thì đặt `REVIEW_WORKER=off` trong `.env` trước khi chạy lại, và bỏ qua mục 9.

**Tài khoản seed** (mật khẩu = `SEED_PASSWORD`):

| Tài khoản | Vai trò | Tài khoản | Vai trò |
|---|---|---|---|
| an.nguyen | REQ | ha.vu | IAM |
| oanh.mai | REQ, LM | phong.ta | IAM, OPS |
| binh.tran | LM | khoa.do | REQ, DEV |
| chi.le | DPO | quan.ly | DEV, OPS |
| dung.pham | SO | lan.bui | REL |
| son.ho | SO | minh.ngo | REQ, OPS |
| giang.hoang | CISO | nam.dang | AUD |
| admin | ADMIN | | |

---

## 1. Trang chọn loại phiếu

| # | Bước | Mong đợi | ✓ |
|---|---|---|---|
| 1.1 | Đăng nhập `an.nguyen`, bấm **Tạo phiếu** | Trang "Bạn cần làm gì?" có 9 thẻ: Cấp/thu hồi quyền, 7 loại nghiệp vụ, Cấp vai trò SoD Flow. **Không có** thẻ Rà soát định kỳ | [ ] |
| 1.2 | Đọc dòng chuỗi duyệt trên từng thẻ | Khớp cột "Chuỗi" ở mục 2 (không kể người được gán) | [ ] |
| 1.3 | Bấm thẻ **Cấp / thu hồi quyền truy cập** | Mở `/yeu-cau/moi/cap-quyen`, form cũ hoạt động như trước | [ ] |
| 1.4 | Gõ tay `/yeu-cau/nghiep-vu/moi?loai=review` và `?loai=abc` | Cả hai đều quay về trang chọn loại | [ ] |
| 1.5 | Đăng nhập `nam.dang` (không có REQ), vào Tạo phiếu | Báo "chưa có vai trò Requestor", không có thẻ nào | [ ] |

---

## 2. Luồng chuẩn cho từng loại (tạo → duyệt hết → DONE)

Với mỗi dòng: đăng nhập người lập, điền đủ form, gửi. Mở trang chi tiết và kiểm chuỗi bước cùng người được gán. Sau đó lần lượt đăng nhập từng người theo thứ tự, vào **Hộp việc** và duyệt / hoàn tất cho tới khi phiếu **Hoàn tất**.

| # | Loại (người lập) | Chuỗi bước = người được gán | ✓ |
|---|---|---|---|
| 2.1 | Điều chuyển (an.nguyen) | SO R dung.pham → LM A oanh.mai → AUD R nam.dang → IAM P ha.vu | [ ] |
| 2.2 | Điều chuyển + tick DLCN | SO R → **DPO R chi.le** → LM A → AUD R → IAM P | [ ] |
| 2.3 | Truy vấn PII (an.nguyen) | CISO R giang.hoang → SO A dung.pham → DPO A chi.le → IAM P ha.vu | [ ] |
| 2.4 | Xuất PII (an.nguyen) | SO R dung.pham → CISO R giang.hoang → LM A oanh.mai → DPO A chi.le → IAM P ha.vu | [ ] |
| 2.5 | Sự cố, mức S1 (an.nguyen) | OPS P phong.ta → SO R dung.pham → CISO A giang.hoang → OPS R phong.ta → REL R lan.bui → CISO A giang.hoang → AUD R nam.dang. Ưu tiên hiển thị **Khẩn cấp** | [ ] |
| 2.6 | Thay đổi giá (an.nguyen) | REL R lan.bui → CISO R giang.hoang → LM A oanh.mai → SO A dung.pham | [ ] |
| 2.7 | Thay đổi giá + tick DLCN | REL R → **DPO R chi.le** → CISO R → LM A → SO A | [ ] |
| 2.8 | Change → Production (**khoa.do**) | DEV P **khoa.do** → CISO R giang.hoang → SO R dung.pham → REL A lan.bui → REL A lan.bui → CISO A giang.hoang → OPS P phong.ta → CISO R giang.hoang | [ ] |
| 2.9 | Ngoại lệ kiểm soát (an.nguyen) | SO A dung.pham → DPO A chi.le → CISO A giang.hoang | [ ] |

Với mỗi phiếu ở trên, kiểm thêm:

| # | Kiểm | Mong đợi | ✓ |
|---|---|---|---|
| 2.10 | Trang chi tiết | Hiện đủ: Loại, Tiêu đề, Hệ thống, các trường riêng (ngày dạng dd/mm/yyyy, ô chọn hiện nhãn), Lý do. **Không** có nút "Xem / in phiếu" | [ ] |
| 2.11 | Người lập | Không nằm ở bước duyệt nào. Riêng 2.8: khoa.do chỉ giữ bước DEV | [ ] |
| 2.12 | Thông báo | Người kế tiếp có thông báo việc mới; người lập nhận tin khi phiếu hoàn tất | [ ] |

---

## 3. Kiểm nhập liệu (phải bị chặn, không tạo phiếu)

| # | Thao tác | Mong đợi | ✓ |
|---|---|---|---|
| 3.1 | Gửi form trống (bất kỳ loại nào) | Danh sách lỗi: tiêu đề, hệ thống, lý do, các trường bắt buộc | [ ] |
| 3.2 | Truy vấn PII: Lý do ghi `gọi 0912345678` | Báo "có vẻ chứa số điện thoại" | [ ] |
| 3.3 | Xuất PII: Nơi nhận ghi `a@b.vn` | Báo "có vẻ chứa email" | [ ] |
| 3.4 | Truy vấn PII: Tiêu đề ghi `CCCD 123456789012` | Báo "dãy số dài (nghi số định danh)" | [ ] |
| 3.5 | Truy vấn PII / Xuất PII | Ô "Liên quan dữ liệu cá nhân" luôn được tick và bị khoá | [ ] |
| 3.6 | Truy vấn PII: Số bản ghi `abc` | Báo "nhập số nguyên không âm" | [ ] |
| 3.7 | Ngoại lệ: Hiệu lực đến ≤ hiệu lực từ | Báo "Hiệu lực đến phải sau hiệu lực từ" | [ ] |
| 3.8 | `an.nguyen` (không phải Dev) mở thẻ Change và gửi đủ form | Báo "Chỉ Developer mới lập được phiếu thay đổi mã nguồn" | [ ] |
| 3.9 | Sự cố, ghi `a@b.vn` vào mô tả | **Được** gửi (chỉ phiếu PII mới bị quét) | [ ] |

---

## 4. Kiểm SoD trong lúc duyệt

| # | Thao tác | Mong đợi | ✓ |
|---|---|---|---|
| 4.1 | Người lập mở phiếu của chính mình | Không có ô quyết định ở bước nào (trừ 2.8: khoa.do chỉ thấy ô ở bước DEV) | [ ] |
| 4.2 | Một người không được giao mở link phiếu | Không thấy ô quyết định; người không liên quan nhận 404 | [ ] |
| 4.3 | Ở bước bất kỳ của phiếu nghiệp vụ | **Không** có nút "Trả lại để bổ sung", chỉ có Đồng ý / Từ chối | [ ] |
| 4.4 | Từ chối không ghi lý do | Bị chặn; ghi lý do thì phiếu chuyển **Từ chối**, người lập nhận tin | [ ] |
| 4.5 | Người lập huỷ phiếu trước bước P (có lý do) | Phiếu **Đã huỷ**, người đang xử lý nhận tin | [ ] |
| 4.6 | Người lập huỷ phiếu khi đã tới bước P | Không còn nút huỷ / bị chặn | [ ] |
| 4.7 | Ủy quyền: dung.pham ủy quyền SO cho son.ho, rồi tạo phiếu 2.6 | son.ho duyệt thay được ở bước SO A, quyết định ghi "thay mặt" | [ ] |

---

## 5. Rà soát quyền định kỳ (tự động)

| # | Bước | Mong đợi | ✓ |
|---|---|---|---|
| 5.1 | Đăng nhập `admin` hoặc `nam.dang`, tìm phiếu "Rà soát quyền định kỳ – 2026-Q4" | Người yêu cầu là **Hệ thống**; ưu tiên Trung bình | [ ] |
| 5.2 | Chuỗi | AUD R nam.dang → SO P dung.pham → CISO R giang.hoang → LM A oanh.mai | [ ] |
| 5.3 | SLA | Bước SO P: **120h** (5 ngày); bước R/A: **360h** (15 ngày) | [ ] |
| 5.4 | Mở "Danh sách quyền cần rà soát" | Có các quyền cấp từ phiếu cấp quyền đã hoàn tất, còn hạn, cùng vai trò SoD Flow của mọi người | [ ] |
| 5.5 | Quyền đã thu hồi | Một quyền vừa thu hồi bằng phiếu Thu hồi (đã hoàn tất) **không** còn trong danh sách; các quyền khác của cùng người **vẫn còn** | [ ] |
| 5.6 | Tắt và chạy lại dev server | Log `[review] Quý 2026-Q4 đã có phiếu SOD-…`, **không** tạo phiếu thứ hai | [ ] |
| 5.7 | Duyệt hết chuỗi | Phiếu **Hoàn tất** | [ ] |
| 5.8 | Nhật ký (nam.dang) | Có dòng `ticket.created.scheduled` cho phiếu này | [ ] |

> Ghi chú cho 5.4–5.5: danh sách được chụp lúc phiếu rà soát được tạo. Muốn kiểm 5.5 thì phải có trước bước 0.3: một phiếu cấp quyền 2 hệ thống cho cùng một người, rồi một phiếu Thu hồi 1 trong 2 hệ thống đó, cả hai đều đã hoàn tất.

---

## 6. Trang Ma trận

| # | Kiểm | Mong đợi | ✓ |
|---|---|---|---|
| 6.1 | Cột cuối "Loại phiếu dùng dòng này" | 19/19 dòng đều có ít nhất một loại phiếu | [ ] |
| 6.2 | Các dòng 9–12 | Ghi "Thay đổi mã nguồn → Production" | [ ] |
| 6.3 | Dòng 19 | Ghi "Rà soát quyền định kỳ" | [ ] |
| 6.4 | Màn hình hẹp (điện thoại) | Bảng cuộn ngang trong khung, trang không vỡ | [ ] |

---

## 7. Bằng chứng (Auditor: nam.dang)

| # | Kiểm | Mong đợi | ✓ |
|---|---|---|---|
| 7.1 | Ô lọc "Loại phiếu" | Có thêm 8 loại mới (7 loại nghiệp vụ + Rà soát định kỳ) | [ ] |
| 7.2 | Lọc từng loại mới | Chỉ ra đúng phiếu loại đó, mỗi quyết định có người duyệt, thời điểm, mã băm | [ ] |
| 7.3 | Xuất CSV | Mở được bằng Excel, cột "Loại phiếu" ghi nhãn tiếng Việt | [ ] |
| 7.4 | Nhật ký | Có dòng xem / xuất bằng chứng | [ ] |

---

## 8. Hồi quy (các phiếu cũ không được hỏng)

| # | Kiểm | Mong đợi | ✓ |
|---|---|---|---|
| 8.1 | Phiếu cấp quyền ở `/yeu-cau/moi/cap-quyen`: xem trước chuỗi, gửi, duyệt tới DONE | Như trước khi sửa | [ ] |
| 8.2 | Phiếu cấp quyền bị **trả lại** → người lập bấm Bổ sung | Trang bổ sung mở được, gửi lại được | [ ] |
| 8.3 | Phiếu cấp vai trò SoD Flow (`/yeu-cau/vai-tro/moi`) | Như trước | [ ] |
| 8.4 | Phiếu DataTrust (nếu có kết nối) | Như trước | [ ] |
| 8.5 | Hộp việc, chuông thông báo, trang Tổng quan | Không lỗi, số đếm đúng | [ ] |

---

## 9. Điểm cần chốt nghiệp vụ (phát hiện khi test, chưa sửa)

1. **Sự cố:** cùng một Prod. Operator vừa điều tra (P, dòng 17) vừa rà soát đóng sự cố (R, dòng 18). Ma trận cho phép vì cùng vai trò, nhưng rule.md ghi "Người điều tra không tự xác nhận đóng sự cố". Có cần tách người không?
2. **Truy vấn / Xuất PII:** bước CISO R sau khi IAM mở account (dòng 5) được gộp vào bước CISO R ở đầu chuỗi, nên không ai kiểm sau khi IAM cấp account. Có cần giữ riêng không?
3. **Change:** Release Manager có hai bước A liền nhau (nghiệm thu test, duyệt phát hành). KE_HOACH.md đề xuất gộp thành một bước có hai ô xác nhận.
4. **Rà soát định kỳ:** hiện là một phiếu mỗi quý cho toàn bộ hệ thống, vì chưa có danh mục "hệ thống ↔ System Owner". Ngoài ra rule.md còn yêu cầu rà soát quyền đặc quyền / PII **hàng tháng**, việc này chưa có phiếu tự động.
5. **SLA rà soát:** P 5 ngày, R/A 15 ngày, nhưng Admin được đóng "hết hạn" sau 7 ngày không xử lý. Cần chốt hai mốc này.
