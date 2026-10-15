# Kịch bản quay video demo SoD Flow

> **Trạng thái:** bản nháp, chưa chạy thử trên giao diện. Chạy thử một lượt trước khi quay thật.
> Thời lượng ước tính: khoảng 19 phút.

## Chuẩn bị trước khi quay

- Chạy `npm run dev` trong `web/`, mở `http://localhost:3000`.
- Mật khẩu chung của các tài khoản là `SEED_PASSWORD` trong `web/.env`. Không để màn hình quay lộ file này.
- Dùng 2 cửa sổ ẩn danh khác nhau để chuyển tài khoản nhanh, đỡ đăng xuất rồi đăng nhập lại.
- Chạy `npm run test:security` trước, giữ sẵn màn hình terminal để quay cảnh cuối.
- Dữ liệu phiếu: DLCN = "cơ bản", Tầng = 2, có mục đích nghiệp vụ rõ.

Tài khoản dùng trong kịch bản (xem đủ danh sách ở `BAO_CAO.md` mục 3.4):

| Tài khoản | Vai trò |
|---|---|
| `an.nguyen` | REQ (người yêu cầu) |
| `oanh.mai`, `binh.tran` | LM |
| `chi.le` | DPO |
| `dung.pham`, `son.ho` | SO |
| `giang.hoang` | CISO |
| `ha.vu` | IAM |
| `nam.dang` | AUD (Auditor) |
| `admin` | Quản trị SoD |

## Cảnh 1: Giới thiệu và ma trận (~1 phút)

- **Tài khoản:** `an.nguyen`.
- **Làm:** mở **Ma trận**, chỉ vào các khâu khởi tạo, phê duyệt, thực thi.
- **Nói:** "SoD là không ai nắm trọn một quy trình. Hệ thống sinh chuỗi duyệt từ ma trận này."

## Cảnh 2: Tạo phiếu và chuỗi duyệt tự sinh (~2 phút)

- **Tài khoản:** `an.nguyen`.
- **Làm:** **Tạo phiếu** → điền form. Dừng ở khung xem trước chuỗi duyệt, chỉ vào lý do phân loại. Ký tên, gửi.
- **Nói:** "Chọn có DLCN thì chuỗi tự thêm DPO. Tầng 3 thì thêm System Owner và CISO."
- **Kết quả đúng:** phiếu có mã `SOD-YYYYMM-NNNN`, bước đầu tiên chờ người duyệt.

## Cảnh 3: Người đề xuất không tự duyệt được (~1 phút)

- **Tài khoản:** `an.nguyen`.
- **Làm:** mở phiếu vừa tạo, chỉ ra không có nút duyệt. Mở **Hộp việc** thấy trống.
- **Nói:** "Người tạo phiếu không bao giờ duyệt được phiếu của mình. DB cũng chặn bằng trigger, không chỉ giao diện."

## Cảnh 4: Duyệt tuần tự và hoàn tất (~3 phút)

- **Tài khoản:** lần lượt từng người mà **Hộp việc** báo tới lượt. Gợi ý: `dung.pham` (SO), `binh.tran` (LM), `chi.le` (DPO), `ha.vu` (IAM).
- **Làm:** mỗi người vào Hộp việc, mở phiếu, duyệt. Sau mỗi bước, quay lại phiếu để thấy bước nhảy tiếp và người kế tiếp nhận thông báo (biểu tượng chuông).
- **Nói:** "Mỗi người chỉ thấy và duyệt đúng bước của mình. Bước cuối là IAM thực hiện, không phải người duyệt."
- **Kết quả đúng:** phiếu hoàn tất, nhật ký không đứt.

## Cảnh 5: Trả lại và bổ sung (~2 phút)

- **Tài khoản:** tạo phiếu mới bằng `an.nguyen`. Người đang tới lượt bấm **Trả lại** kèm lý do. `an.nguyen` vào **Bổ sung**, sửa mục đích rồi gửi lại.
- **Nói:** "Phiếu bị trả sang trạng thái chờ bổ sung, SLA tạm dừng. Sửa nội dung thì các bước đã duyệt phải duyệt lại."
- **Nhấn mạnh thêm:** đổi email người nhận quyền cũng bắt duyệt lại mọi bước.

## Cảnh 6: Huỷ phiếu (~1 phút)

- **Tài khoản:** `an.nguyen`, trên phiếu mới chưa tới bước thực hiện.
- **Làm:** bấm **Huỷ** kèm lý do. Với phiếu đã tới bước IAM, nút huỷ bị chặn.

## Cảnh 7: Ủy quyền vắng mặt (~2 phút)

- **Tài khoản:** `binh.tran` (LM) vào **Ủy quyền**, ủy cho `oanh.mai` (cùng vai trò LM), có hạn. Sau đó thử ủy cho người khác vai trò thì bị chặn.
- **Làm:** `oanh.mai` mở Hộp việc thấy việc của `binh.tran`, duyệt. Chỉ vào dòng ghi "thay mặt …".

## Cảnh 8: Đổi cấu hình cần hai người (~2 phút)

- **Tài khoản:** `admin` vào **Quản trị**, đề xuất đổi SLA. Thử tự duyệt thì bị chặn.
- **Làm:** đăng nhập `giang.hoang` (CISO) duyệt, phiên bản mới mới có hiệu lực.
- **Nói:** "Người đề xuất không tự duyệt thay đổi cấu hình của mình. Phiếu đang chạy giữ cấu hình cũ."

## Cảnh 9: Phiếu cấp vai trò (RBAC) (~1 phút)

- **Tài khoản:** `an.nguyen` tạo phiếu **cấp vai trò**. Nói rõ chuỗi: Release Manager → System Owner, CISO → IAM. Người được cấp không nằm trong chuỗi.
- **Nói:** "Vai trò chỉ được ghi vào hệ thống khi IAM hoàn tất phiếu. Ghi tay vào DB bị trigger chặn."

## Cảnh 10: Auditor tra cứu bằng chứng (~3 phút)

- **Tài khoản:** `nam.dang` (AUD).
- **Làm:**
  1. Mở **Nhật ký**: thấy các thao tác ở các cảnh trước, kể cả thao tác bị chặn.
  2. Mở **Bằng chứng**: lọc theo kỳ, chỉ vào người duyệt, thời điểm và mã băm.
  3. Bấm **Xuất CSV** và **In / lưu PDF**.
  4. Quay lại **Nhật ký**: thấy dòng "Xem" và "Xuất" bằng chứng.
- **Làm thêm:** mở `/nhat-ky` bằng `an.nguyen` thì ra 404.
- **Nói:** "Auditor xem được mọi phiếu nhưng chỉ đọc. Mỗi lần xem và xuất đều ghi nhật ký."

## Cảnh 11: Test tự động (~1 phút)

- **Làm:** chuyển sang terminal đã chạy `npm run test:security`. Cuộn qua danh sách test và dừng ở dòng tổng.
- **Kết quả đúng:** `59 pass, 0 fail` (tại thời điểm viết kịch bản).
- **Nói:** "Các kiểm soát vừa demo đều có test chạy trên DB thật."

## Phần SLA (T06, T07): không quay trực tiếp

Mốc SLA là 75%, 100%, 200% của 8 đến 24 giờ nên không chờ được lúc quay. Cho xem các dòng test T06, T07 ở cảnh 11 và nói bằng lời: "Quá hạn bao lâu hệ thống cũng không tự duyệt, chỉ nhắc và leo thang."

## Hai chỗ chưa kiểm chứng

1. **Chuỗi duyệt cụ thể** của phiếu (ai là bước 1, 2, 3…) phụ thuộc form. Gợi ý SO, LM, DPO, IAM chưa chạy thật. Khi quay, theo Hộp việc báo ai tới lượt.
2. **Tên nút** ("Trả lại", "Huỷ", "Bổ sung"…) lấy theo code và ghi chú, chưa thấy trên màn hình thật nên có thể lệch chữ.
