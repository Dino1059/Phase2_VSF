# Kế hoạch triển khai SoD Flow

Hệ thống quản lý yêu cầu (ticket) theo nguyên tắc phân tách nhiệm vụ (SoD) trong [rule.md](rule.md).
Bản web hiện có (`index.html`) là **bản mẫu để xem luồng**. Tài liệu này mô tả phiên bản dùng thật.

Ký hiệu: **P** thực hiện · **R** rà soát · **A** phê duyệt · **C** tham vấn · **I** nhận thông báo.
Các mục đánh dấu **[Cần chốt]** là giả định chưa có trong rule.md, cần người có thẩm quyền xác nhận.

---

## 1. Ai dùng hệ thống, mỗi người thấy trang nào

Tất cả dùng chung một ứng dụng. Mỗi người đăng nhập bằng tài khoản công ty và **chỉ thấy menu, dữ liệu đúng với vai trò của mình**. Một người có nhiều vai trò thì thấy gộp các menu tương ứng.

| Nhóm người dùng | Trang được thấy | Được làm | Không được làm |
|---|---|---|---|
| **Người yêu cầu** (mọi nhân viên) | Trang chủ (nút Tạo ticket) · Yêu cầu của tôi · Chi tiết ticket của mình | Tạo ticket, theo dõi, bổ sung thông tin khi bị trả lại, bình luận, huỷ khi chưa thực thi | Xem ticket của người khác, tự duyệt ticket của mình |
| **Người xử lý** (Line Manager, System Owner, DPO, CISO, Release Manager, IAM, Dev, Prod Operator) | Hộp việc (chờ tôi / sắp hết hạn / quá hạn) · Đã xử lý · Ủy quyền vắng mặt | Duyệt, từ chối, trả lại để bổ sung, đánh dấu đã thực hiện, ủy quyền | Xử lý bước mà mình đang xung đột SoD |
| **Người tham vấn / nhận thông báo** (C, I) | Thông báo · Chi tiết ticket (chỉ đọc) | Góp ý (C) | Duyệt thay |
| **Quản trị SoD** (admin) | Tất cả ticket · Cấu hình (ma trận, loại ticket, SLA, danh bạ vai trò) · Bảng theo dõi SLA · Sổ đăng ký ngoại lệ | Đề xuất thay đổi cấu hình, chuyển người xử lý khi có sự cố | Tự áp dụng thay đổi cấu hình (xem mục 1.1), duyệt ticket |
| **Auditor** | Tất cả ticket (chỉ đọc) · Nhật ký kiểm toán · Báo cáo kiểm soát định kỳ | Xuất bằng chứng, hậu kiểm, ghi nhận phát hiện | Sửa ticket, sửa cấu hình (rule.md mục 4: Auditor ↔ Control Operator) |

**Trả lời câu hỏi "trang admin có khác không":** có. Admin **không nằm trong chuỗi duyệt** và không dùng hộp việc để duyệt. Admin chỉ quản lý cấu hình và giám sát. Người duyệt chỉ thấy ticket đang có bước của mình.

### 1.1. Chính admin cũng phải tuân thủ SoD
- Mọi thay đổi ma trận, SLA hay danh bạ vai trò đều theo cơ chế **hai người**: admin đề xuất, CISO (hoặc người được chỉ định) duyệt thì mới có hiệu lực.
- Mỗi phiên bản cấu hình được đánh số. Ticket **giữ nguyên phiên bản cấu hình tại thời điểm tạo**, nên việc đổi cấu hình giữa chừng không làm thay đổi ticket đang chạy.
- Việc gán vai trò cho nhân sự (ai là System Owner, ai là CISO…) cũng là một thay đổi quyền, nên phải đi qua ticket "Tạo / sửa RBAC role".

---

## 2. Vòng đời một ticket

```
Nháp ──gửi──► Đang duyệt ──duyệt hết──► Đang thực thi ──xong──► Hậu kiểm ──► Hoàn tất
                 │   ▲                         │
     trả lại ────┘   └── bổ sung xong           ├── thất bại ──► quay lại bước trước / mở sự cố
                 │                             │
                 ├── từ chối ──► Đã từ chối    └── (quyền tạm) hết hạn ──► Tự thu hồi ──► Đóng
                 └── người yêu cầu huỷ ──► Đã huỷ
```

Trạng thái của từng bước: `Chờ` · `Đang xử lý` · `Đã duyệt / Đã thực hiện` · `Trả lại` · `Từ chối` · `Quá hạn` · `Đã ủy quyền`.

### 2.1. Quy tắc sắp thứ tự người xử lý (đang dùng trong bản mẫu)
1. Ticket được đổi ra một chuỗi **hoạt động kiểm soát** (các dòng trong ma trận rule.md mục 3).
2. Trong mỗi hoạt động, thứ tự các bước như sau:
   - **Hoạt động phê duyệt** (ví dụ: phê duyệt quyền PII): R → A → P. Phải được duyệt xong mới được thực thi.
   - **Hoạt động thực hiện** (ví dụ: phát triển mã, triển khai, cấp quyền): P → R → A. Làm xong rồi mới rà soát, nghiệm thu.
   - Trong nhóm R và nhóm A, cấp thấp đi trước, cấp cao nhất duyệt cuối: Line Manager → Release Manager → System Owner → DPO → CISO. **[Cần chốt]** Ma trận chỉ nói ai là R, ai là A, không nói ai đi trước.
   - Auditor luôn ở cuối (hậu kiểm độc lập).
3. Nếu cùng một vai trò có cùng hành động ở hai hoạt động liền nhau thì gộp thành một bước, để tránh một người duyệt hai lần.
4. Theo rule.md mục 5, quy tắc 4:
   - Level 2 hoặc có PII: tự thêm DPO rà soát.
   - Level 3: tự thêm CISO phê duyệt.

---

## 3. Luồng cho từng loại yêu cầu

Bảng dưới là chuỗi mà bản mẫu đang sinh ra. Mọi loại ticket đều bắt đầu bằng bước **Người yêu cầu tạo ticket**. Người yêu cầu luôn được báo khi ticket xong. Cột cuối là những vai trò chỉ nhận thông báo (I), không có bước xử lý.

| # | Loại yêu cầu | Hoạt động (theo ma trận) | Thứ tự xử lý | Khi xong thì thông báo |
|---|---|---|---|---|
| 1 | Cấp quyền truy cập | Khởi tạo → Xác nhận nhu cầu → Cấp quyền IAM/PAM | Sys Owner (R) → Line Mgr (A) → IAM (P) → CISO (R) | DPO, Dev, Rel Mgr, Auditor |
| 1a | … có PII | + Phê duyệt quyền PII | Sys Owner (R) → Line Mgr (A) → **DPO (A)** → IAM (P) → CISO (R) | như trên |
| 1b | … Level 3 / quyền DB | + Phê duyệt quyền đặc quyền | Sys Owner (R) → DPO (R) → Line Mgr (A) → Sys Owner (A) → **CISO (A)** → IAM (P) → CISO (R) | như trên |
| 2 | Thu hồi quyền khi nghỉ việc | Thu hồi quyền | Sys Owner (R) → Line Mgr (A) → IAM (P) → Auditor (R) | Requestor, DPO |
| 3 | Điều chuyển / đổi vai trò | Điều chuyển | Sys Owner (R) → Line Mgr (A) → IAM (P) → Auditor (R) | Requestor, CISO |
| 4 | Tạo / sửa RBAC role | Tạo/sửa RBAC | Rel Mgr (R) → Sys Owner (A) → CISO (A) → IAM (P) | Auditor |
| 5 | Thay đổi mã nguồn → Production | Phát triển → Kiểm thử → Duyệt phát hành → Triển khai | Dev (P) → CISO (R) → Sys Owner (R) → Rel Mgr (A, nghiệm thu test) → Rel Mgr (A, duyệt phát hành) → CISO (A) → Prod Op (P) → CISO (R) | Auditor |
| 6 | Thay đổi giá / khuyến mại / chính sách | Thay đổi giá | Rel Mgr (R) → CISO (R) → Line Mgr (A) → Sys Owner (A) → Prod Op (P) | Auditor |
| 7 | Truy vấn PII trực tiếp | Truy vấn PII | CISO (R) → Sys Owner (A) → DPO (A) → IAM (P) | Auditor |
| 8 | Xuất dữ liệu PII | Xuất PII | Sys Owner (R) → CISO (R) → Line Mgr (A) → DPO (A) → IAM (P) | Auditor |
| 9 | Ngoại lệ kiểm soát | Phê duyệt ngoại lệ | Sys Owner (A) → DPO (A) → CISO (A) | Auditor |
| 10 | Sự cố bảo mật | Điều tra → Đóng sự cố | Prod Op (P) → IAM (P) → Sys Owner (R) → CISO (A) → Prod Op (R) → Rel Mgr (R) → CISO (A, đóng) → Auditor (A) | Line Mgr, Requestor |
| 11 | Rà soát quyền định kỳ | Rà soát định kỳ | IAM (P) → Sys Owner (R) → CISO (R) → Line Mgr (A) → Auditor (A) | Requestor |

**Cần sửa ở bản dùng thật:**
- Loại 5: hai bước Rel Mgr (A) liên tiếp nên gộp thành **một bước có hai ô xác nhận**.
- Loại 9: DPO và System Owner phải là hai người khác nhau (rule.md mục 1).

---

## 4. Các tình huống đặc biệt

| Tình huống | Hệ thống xử lý thế nào |
|---|---|
| **Từ chối** | Ticket đóng ở trạng thái *Đã từ chối*, bắt buộc có lý do, báo người yêu cầu. Người yêu cầu có thể nhân bản ticket để gửi lại. |
| **Trả lại để bổ sung** | SLA **tạm dừng**, ticket quay về người yêu cầu. Nếu phần sửa làm đổi phạm vi, PII hoặc Level thì hệ thống phân loại lại, và các bước đã duyệt trong hoạt động bị ảnh hưởng phải duyệt lại. |
| **Người yêu cầu huỷ** | Chỉ được huỷ khi chưa tới bước thực thi (P). Sau đó muốn dừng thì phải mở ticket thu hồi. |
| **Quá SLA** | 75%: nhắc người đang xử lý. 100%: báo quá hạn và leo thang lên cấp trên. 200%: báo CISO và Auditor, ghi nhận vi phạm. **Không bao giờ tự động duyệt.** |
| **Người duyệt vắng mặt** | Ủy quyền cho người khác cùng vai trò, có thời hạn. Hệ thống kiểm tra SoD với người được ủy quyền và ghi nhật ký. |
| **Không tìm được người hợp lệ** (mọi ứng viên đều xung đột) | Không cho gửi. Người yêu cầu phải xin ngoại lệ, và hệ thống chèn hoạt động "Phê duyệt ngoại lệ kiểm soát" vào đầu chuỗi (rule.md mục 5 và mục 8). |
| **Khẩn cấp (break-glass)** | IAM cấp quyền tạm thời ngay qua PAM/JIT, rồi mới **duyệt sau**. Auditor hậu kiểm trong 24h. Quá 24h thì báo CISO và ghi vi phạm (rule.md mục 5, quy tắc 5). *Bản mẫu hiện vẫn duyệt trước rồi mới cấp, cần sửa.* |
| **Quyền tạm / ngoại lệ hết hạn** | Hệ thống tự tạo tác vụ thu hồi cho IAM. IAM xác nhận đã thu hồi, Auditor thấy trong báo cáo (rule.md mục 5, quy tắc 3). |
| **Thực thi thất bại** (cấp quyền lỗi, deploy lỗi) | Người thực thi đánh dấu *Thất bại* kèm lý do. Ticket quay lại bước trước, hoặc mở ticket sự cố. |
| **Người yêu cầu nghỉ việc / đổi vai trò khi ticket đang mở** | Ticket tạm dừng, Line Manager quyết định huỷ hay chuyển cho người khác. |
| **Đổi người giữ vai trò khi ticket đang chạy** | Các bước chưa bắt đầu được gán lại người mới và kiểm tra SoD lại. Bước đang xử lý giữ nguyên người cũ. |

---

## 5. Người yêu cầu theo dõi ticket thế nào

**Trang "Yêu cầu của tôi"** là danh sách các ticket, mỗi dòng gồm:
- Mã ticket và tiêu đề.
- Trạng thái bằng lời, ví dụ: *"Đang chờ System Owner rà soát (Phạm Dũng) · còn 5 giờ"*.
- Thanh tiến độ, ví dụ: *bước 3/6*.

**Trang chi tiết ticket** có:
- **Thanh các bước** (giống bản mẫu): bước nào xong, ai làm, lúc nào, bước nào đang chờ ai, còn bao lâu tới hạn SLA.
- **Dự kiến hoàn tất**: cộng SLA của các bước còn lại.
- **Bình luận** qua lại với người xử lý. Ghi chú đánh giá rủi ro nội bộ (của CISO, DPO) có thể đặt ở chế độ *nội bộ*, người yêu cầu không thấy. **[Cần chốt]**
- **Nút thao tác:** Bổ sung thông tin (khi bị trả lại) · Nhắc người xử lý (tối đa 1 lần/ngày) · Huỷ (khi còn được huỷ).

**Thông báo cho người yêu cầu** được gửi khi: ticket được tiếp nhận, chuyển sang bước mới, bị trả lại, bị từ chối, hoàn tất, và khi quyền tạm sắp hết hạn. Kênh gửi: trong app + email, sau này thêm Teams/Slack.

---

## 6. Công nghệ và nơi lưu trữ

### 6.1. Đề xuất
| Thành phần | Công nghệ | Lý do |
|---|---|---|
| Web (giao diện + API) | **Next.js + TypeScript**, một ứng dụng duy nhất | Một codebase, dễ tuyển người, đủ cho quy mô nội bộ |
| Cơ sở dữ liệu | **PostgreSQL** | Dữ liệu quan hệ (ticket, bước, người), có transaction, backup và khôi phục theo thời điểm |
| Truy cập DB | Prisma | Quản lý migration, kiểu dữ liệu an toàn |
| Hẹn giờ SLA | **pg-boss** (hàng đợi chạy trên chính PostgreSQL) | Mỗi bước đặt sẵn các mốc 75/100/200%, không cần thêm Redis |
| Đăng nhập | **SSO qua OIDC** với hệ thống tài khoản công ty (Microsoft Entra ID / Google Workspace / Keycloak) | Không quản lý mật khẩu riêng. Nhân sự nghỉ việc thì mất quyền ngay |
| File đính kèm, bằng chứng | **Kho lưu trữ chuẩn S3** (MinIO nếu tự vận hành, hoặc S3 của nhà cung cấp cloud), bật **Object Lock** | Bằng chứng kiểm toán không sửa, không xoá được trong thời hạn lưu |
| Thông báo | Email (SMTP) giai đoạn 1, Teams/Slack webhook giai đoạn 2 | |
| Nhật ký hệ thống | Đẩy sang SIEM của công ty | rule.md mục 6 yêu cầu đối soát log bằng SIEM |
| Triển khai | Docker, đặt ở máy chủ/cloud **trong nước** **[Cần chốt với DPO]** | Ticket chứa thông tin về dữ liệu cá nhân, cần tránh chuyển dữ liệu ra nước ngoài |

### 6.2. Dữ liệu lưu những gì
- **Danh mục và cấu hình** (có phiên bản): vai trò, hoạt động, ô ma trận, loại ticket, SLA, cấp bậc, luật leo thang.
- **Người dùng:** người dùng, gán vai trò cho người (có hiệu lực từ–đến), ủy quyền.
- **Ticket:**
  - ticket (kèm số phiên bản cấu hình lúc tạo)
  - các bước (người xử lý, hạn SLA, trạng thái)
  - quyết định (ai, lúc nào, duyệt/từ chối, ghi chú)
  - bình luận, file đính kèm
  - ngoại lệ (các trường theo rule.md mục 8)
  - quyền tạm (hạn thu hồi)
- **Vận hành:** thông báo đã gửi, sự kiện SLA, vi phạm SoD.
- **Nhật ký kiểm toán:**
  - Chỉ được ghi thêm. Ứng dụng không có quyền UPDATE hay DELETE, và có trigger chặn.
  - Mỗi dòng lưu mã băm của dòng trước, nên nếu bị sửa sẽ phát hiện được.
  - Mỗi ngày xuất bản sao sang kho lưu trữ đã khoá (Object Lock).

### 6.3. Sao lưu và thời hạn lưu trữ
- Sao lưu PostgreSQL hằng ngày, bật khôi phục theo thời điểm, định kỳ diễn tập khôi phục.
- Thời hạn lưu ticket và nhật ký: **[Cần chốt]**. rule.md chỉ yêu cầu "sẵn sàng cho kiểm toán", không nêu số năm. Bản mẫu đang để 5 năm.
- Khi hết hạn lưu, dữ liệu cá nhân trong mô tả ticket được ẩn danh hoá, còn nhật ký kiểm toán vẫn giữ lại.

### 6.4. So với bản mẫu hiện tại
| | Bản mẫu | Bản dùng thật |
|---|---|---|
| Lưu trữ | Trình duyệt (localStorage), mỗi máy một bản riêng | PostgreSQL dùng chung |
| Người dùng | Chọn tên từ danh sách, ai cũng thao tác thay được | Đăng nhập SSO, chỉ người được giao mới thao tác |
| SLA | Chỉ chạy khi đang mở trang | Chạy trên máy chủ, 24/7 |
| Thông báo | Hiện trong trang | Email / Teams |

---

## 7. Lộ trình

Thời gian là **ước lượng cho 1–2 lập trình viên**, cần điều chỉnh khi đã chốt phạm vi.

| Giai đoạn | Nội dung | Thời gian | Kết quả |
|---|---|---|---|
| **0. Chốt quy tắc** | Trả lời các mục [Cần chốt] (mục 8). Lấy danh sách người thật cho từng vai trò. | 1 tuần | Bảng cấu hình đã được duyệt |
| **1. Bản chạy được (MVP)** | SSO · 3 trang: Người yêu cầu / Hộp việc / Admin · phân loại và sinh chuỗi · kiểm tra SoD · SLA + email · nhật ký kiểm toán · PostgreSQL + kho file | 5–6 tuần | Dùng thử với loại 1, 2, 3 (cấp, thu hồi, điều chuyển quyền) |
| **2. Đủ tình huống** | Trả lại/bổ sung · ủy quyền · break-glass · tự thu hồi quyền tạm · sổ ngoại lệ · bảng theo dõi SLA · Teams/Slack · đủ 11 loại ticket | 3–4 tuần | Dùng chính thức |
| **3. Kiểm toán & tích hợp** | Trang Auditor + xuất bằng chứng · báo cáo kiểm soát định kỳ (rule.md mục 6) · đẩy log sang SIEM · tích hợp IAM/PAM để cấp và thu hồi tự động · kiểm thử bảo mật | 3–4 tuần | Sẵn sàng kiểm toán |

### Tiêu chí nghiệm thu (lấy từ rule.md mục 7)
- [ ] Mỗi ticket có người khởi tạo, người phê duyệt, người thực thi là ba người khác nhau. Hệ thống chặn khi trùng.
- [ ] Ticket có PII bắt buộc có căn cứ xử lý, mục đích sử dụng, thời hạn.
- [ ] Quyền đặc quyền được cấp qua PAM/JIT và tự thu hồi khi hết hạn.
- [ ] Thay đổi Production có bằng chứng kiểm thử và phê duyệt trước khi triển khai.
- [ ] Mọi vi phạm SoD và SLA được ghi nhận, phân loại rủi ro, có hạn khắc phục.
- [ ] Kết quả rà soát được lưu cùng ticket, xuất được cho kiểm toán.

---

## 8. Việc cần chốt trước khi làm

| # | Câu hỏi | Giá trị bản mẫu đang dùng | Ai chốt |
|---|---|---|---|
| 1 | Định nghĩa Level 1 / 2 / 3 là gì? | L3 = quyền đặc quyền / DB | CISO |
| 2 | SLA từng bước (thực hiện / rà soát / phê duyệt) | 8h / 24h / 24h | CISO + các trưởng bộ phận |
| 3 | Tính theo giờ hành chính hay 24/7? | 24/7 | CISO |
| 4 | Thứ tự người duyệt khi có nhiều A | Line Mgr → Rel Mgr → Sys Owner → DPO → CISO | CISO |
| 5 | Leo thang lên ai khi quá hạn | Line Mgr → Sys Owner → CISO → Auditor | CISO |
| 6 | Mức ưu tiên và hệ số nhân SLA | Khẩn ×0.25 · Cao ×0.5 · TB ×1 · Thấp ×2 | CISO |
| 7 | Thời hạn lưu trữ ticket và nhật ký | 5 năm | DPO / Pháp chế |
| 8 | PII Role đi với Next action nào (Form 0D) | Direct → Pseudonymize, Contextual → Generalize… | DPO |
| 9 | Máy chủ đặt ở đâu | Chưa có | DPO + IT |
| 10 | Hệ thống tài khoản công ty (IdP) đang dùng là gì | Chưa biết | IT |
| 11 | Ghi chú nội bộ có ẩn với người yêu cầu không | Chưa có | DPO |

---

## 9. Plan: nối đăng nhập với bản mẫu và chặn tự duyệt ticket

> **Trạng thái:** đã duyệt ngày 29/09/2026, đã chốt câu A (làm lại bằng React). Đã xong bước 1–4 của mục 9.7. Chi tiết trong [README_web.md](README_web.md).

### 9.1. Hiện trạng

**Bản mẫu** (`index.html`, `app.js`, `data.js`) chạy hoàn toàn trên trình duyệt, dữ liệu lưu ở localStorage. Nó có các lỗ hổng sau, bản thật phải bịt hết:

| # | Lỗ hổng trong bản mẫu | Chỗ trong code | Hậu quả |
|---|---|---|---|
| L1 | Người tạo phiếu **chọn tên mình từ danh sách** (`requestor`) | `vCreate`, `emptyDraft` | Mạo danh bất kỳ ai |
| L2 | Nút **Duyệt / Từ chối hiện cho mọi người** mở trang, và ghi tên *người được giao* chứ không phải *người bấm* | `actionBox`, `bindDetail` → `advance(t, s.assignee)` | Ai cũng duyệt thay được, nhật ký ghi sai người |
| L3 | Dữ liệu có sẵn trường `overrides` để chỉ định người duyệt (chưa có giao diện) | `autoAssign(t, overrides)` | Người yêu cầu có thể chọn “người quen” duyệt cho mình |
| L4 | Tab **Cấu hình ai cũng sửa được**: danh bạ vai trò (tự gán mình làm CISO), SLA, nhập JSON ghi đè, xoá toàn bộ ticket | `vConfig` | Tự nâng quyền, xoá dấu vết |
| L5 | Kiểm tra SoD chạy **ở trình duyệt** | `conflictsFor`, `violations` | Sửa JS / localStorage là qua |
| L6 | Nhật ký của ticket nằm trong localStorage | `log()` | Sửa, xoá được |

**Thư mục `web/`** (dựng ngày 29/09, trước khi có plan, chi tiết ở [README_web.md](README_web.md)) đã có:
- Database PostgreSQL `sod`, gồm bảng người dùng, vai trò có hiệu lực từ–đến, phiên đăng nhập và nhật ký kiểm toán chỉ ghi thêm, có chuỗi băm.
- Đăng nhập bằng email hoặc username, đăng ký có mã xác nhận qua email, đổi mật khẩu và trang nhật ký cho Auditor.
- **Chưa có:** ticket, ma trận, SLA. Chưa nối với bản mẫu.

### 9.2. Cách nối

**Nguyên tắc:** trình duyệt chỉ hiển thị và gửi yêu cầu. Việc quyết định ai được làm gì và kiểm tra SoD đều do server làm. Dữ liệu chỉ lưu ở PostgreSQL.

| Việc | Đề xuất | Lý do |
|---|---|---|
| Logic nghiệp vụ trong `app.js` (phân loại, sinh chuỗi, kiểm SoD, SLA) | **Chuyển sang TypeScript chạy ở server** (`web/lib/sod/`), giữ nguyên thuật toán, viết test cho từng hàm | Bắt buộc để chặn L2, L3, L5 |
| Dữ liệu quy tắc trong `data.js` (vai trò, ma trận, loại ticket) | Chuyển thành **bảng cấu hình có phiên bản** trong DB (mục 1.1). Seed từ `data.js` | Chặn L4, đổi cấu hình phải qua 2 người |
| Giao diện | **Làm lại từng trang bằng React trong `web/`**, dùng lại `styles.css` và bố cục của bản mẫu | Một codebase, không phải duy trì song song JS thuần và React |
| Bản mẫu ở thư mục gốc | **Giữ nguyên để demo luồng**, không nối DB | Tránh phải vá bảo mật cho code sắp bỏ |

**[Cần chốt] A.** Làm lại giao diện bằng React (đề xuất ở trên), hay giữ `app.js` và chỉ thay localStorage bằng gọi API? Cách thứ hai nhanh hơn khoảng 1 tuần, nhưng sẽ phải viết lại toàn bộ phần hiển thị khi thêm trang mới.

### 9.3. Chặn “lách luật” để tự duyệt ticket

#### 9.3.1. Bảy lớp chặn

Mỗi lớp tự đứng được. Một lớp có lỗi thì lớp sau vẫn chặn.

| Lớp | Cơ chế | Bịt lỗ |
|---|---|---|
| 1. Danh tính | Người đang thao tác **chỉ lấy từ phiên đăng nhập ở server**. Server bỏ qua mọi trường `requestor`, `by`, `assignee`, `userId` mà trình duyệt gửi lên | L1, L2 |
| 2. Quyền theo hành động | Mọi thao tác đi qua một hàm duy nhất `can(user, hành động, ticket)` (bảng 9.3.2). Không có thao tác nào bỏ qua hàm này | L2, L4 |
| 3. Kiểm SoD ở server | Kiểm **3 lần**: khi gửi ticket, khi gán hoặc đổi người, và **ngay lúc bấm duyệt** (vì vai trò có thể vừa thay đổi) | L5 |
| 4. Ràng buộc trong DB | Trigger trên bảng `step_decisions` từ chối ghi quyết định nếu vi phạm (9.3.3). Code ứng dụng có bug thì DB vẫn chặn | L2, L5 |
| 5. Không chọn người duyệt | **Bỏ `overrides`.** Hệ thống tự gán người không xung đột. Muốn đổi người thì Admin chuyển, bắt buộc có lý do, ghi nhật ký, và server kiểm SoD lại | L3 |
| 6. Cấp vai trò có kiểm soát | Vai trò chỉ được cấp qua ticket “Tạo / sửa RBAC role” đã duyệt xong. **Không có màn hình nào để tự sửa vai trò.** Admin không cấp được cho chính mình | L4 |
| 7. Nhật ký không sửa được | Mọi quyết định ghi vào `audit_log` **trong cùng transaction**. Đã có chuỗi băm và trigger chặn sửa/xoá | L6 |

#### 9.3.2. Ai được làm gì

| Hành động | Điều kiện ở server (phải thoả **tất cả**) |
|---|---|
| Xem ticket | Là người yêu cầu, người được giao một bước, người C/I của ticket, Admin (chỉ đọc) hoặc Auditor (chỉ đọc). Ngoài ra trả về **404**, không phải 403, để không lộ ticket có tồn tại |
| Tạo ticket | Có vai trò REQ còn hiệu lực. Người yêu cầu = người đăng nhập |
| Duyệt / Rà soát / Hoàn tất bước | Bước đang ở trạng thái “đang xử lý” · người đăng nhập **là người được giao** hoặc người được ủy quyền còn hạn · **đang giữ đúng vai trò** của bước tại thời điểm bấm · **không phải người yêu cầu** (trừ bước P mà ma trận cho phép) · **chưa làm bước nào xung đột** trên cùng ticket (rule.md mục 4) · ticket chưa bị sửa kể từ khi trang được mở (số phiên bản khớp) |
| Từ chối / Trả lại | Như dòng trên, cộng thêm bắt buộc có lý do |
| Bổ sung (khi bị trả lại) | Chỉ người yêu cầu. Sửa xong thì tạo **phiên bản nội dung mới**, và các bước đã duyệt bị ảnh hưởng phải duyệt lại (mục 4) |
| Huỷ | Chỉ người yêu cầu, và chỉ khi chưa tới bước thực thi (P) |
| Ủy quyền | Chỉ cho người **cùng vai trò**, có thời hạn, không cho người yêu cầu của ticket, server kiểm SoD với người nhận |
| Chuyển người xử lý | Chỉ Admin, bắt buộc lý do, kiểm SoD với người mới, Admin **không tự nhận** |
| Đổi cấu hình, ma trận | Admin đề xuất → CISO duyệt (mục 1.1). Người đề xuất ≠ người duyệt |
| Xem nhật ký kiểm toán | Chỉ Auditor. Việc xem cũng được ghi lại (đã có) |

#### 9.3.3. Ràng buộc đặt ngay trong DB

Viết bằng trigger và constraint của PostgreSQL. Tài khoản `sod_app` không tắt được trigger.

1. `step_decisions`: mỗi bước **chỉ có một quyết định** (UNIQUE `step_id`), nên bấm hai lần hoặc mở hai tab không duyệt hai lần được.
2. Trước khi ghi quyết định, kiểm:
   - người quyết định ≠ người yêu cầu (với bước R/A);
   - người quyết định = người được giao, hoặc có ủy quyền còn hạn;
   - bước đang “đang xử lý”;
   - ticket đang mở.
3. Cùng một người không được có quyết định ở **hai vai trò xung đột** trên cùng ticket. Danh sách cặp xung đột lưu trong bảng cấu hình, lấy từ rule.md mục 4.
4. Ghi quyết định dùng khoá dòng ticket (`SELECT … FOR UPDATE`) và kiểm tra cột `version`, để hai người bấm cùng lúc không chen nhau.
5. Nội dung ticket lúc gửi được lưu kèm **mã băm**. Người duyệt duyệt đúng phiên bản nội dung mình đã xem. Nội dung đổi thì quyết định cũ không còn hiệu lực.

#### 9.3.4. Các trò lách luật và chỗ chặn (cũng là danh sách test bảo mật)

| # | Trò lách | Bị chặn ở |
|---|---|---|
| T1 | Sửa HTML hoặc dùng DevTools để hiện nút Duyệt rồi bấm | Lớp 2: không phải người được giao → từ chối |
| T2 | Gửi thẳng request với mã bước của ticket khác | Lớp 2 + lớp 4 |
| T3 | Gửi kèm `requestor=<người khác>` khi tạo phiếu | Lớp 1: server bỏ qua trường này |
| T4 | **Đăng ký tài khoản thứ hai** bằng email khác để tự duyệt | Tài khoản mới chỉ có vai trò REQ. Vai trò duyệt chỉ cấp qua ticket RBAC. Chỉ nhận email công ty. **[Cần chốt] B:** gắn mỗi tài khoản với mã nhân viên duy nhất |
| T5 | Nhờ Admin gán mình làm CISO / System Owner | Lớp 6: phải qua ticket RBAC, có CISO duyệt. Admin không có màn hình sửa vai trò |
| T6 | Ủy quyền cho bạn thân hoặc cho tài khoản phụ | Chỉ ủy quyền cho người cùng vai trò. Server kiểm SoD với người nhận. Có ghi nhật ký, Auditor thấy |
| T7 | Được duyệt xong rồi mới sửa phạm vi xin quyền | Nội dung bị khoá khi gửi. Sửa → phiên bản mới → duyệt lại (lớp 4, điểm 5) |
| T8 | Bấm Duyệt hai lần, hoặc hai tab cùng lúc | UNIQUE `step_id` + `version` |
| T9 | Bị rút vai trò nhưng vẫn giữ trang cũ để bấm | Lớp 3: kiểm vai trò ngay lúc bấm |
| T10 | Tự xin ngoại lệ SoD rồi tự duyệt ngoại lệ | Ngoại lệ do SO + DPO + CISO duyệt (ma trận dòng 15), cũng qua lớp 2 và 4 |
| T11 | Gọi thẳng vào DB | `sod_app` không tắt được trigger. Mật khẩu DB chỉ có ở server |
| T12 | Sửa hoặc xoá dấu vết | Lớp 7: chuỗi băm + chặn sửa/xoá (đã có) |
| T13 | Lấy cắp phiên đăng nhập | Cookie httpOnly, SameSite, Secure. Phiên hết hạn sau 12 giờ. Đổi mật khẩu thì huỷ mọi phiên (đã có). Server Actions của Next.js có sẵn kiểm tra nguồn gọi (chống CSRF) |
| T14 | Đoán mật khẩu người duyệt | Khoá tạm sau 5 lần sai (đã có). **[Cần chốt] C:** bắt nhập lại mật khẩu hoặc mã email khi duyệt Level 3 và ngoại lệ |
| T15 | Đoán mã ticket để xem ticket người khác | Mã ticket dùng UUID ở URL. Không có quyền xem thì trả về 404 |

### 9.4. Cấu trúc thư mục đề xuất (`web/`)

```
web/
├── app/
│   ├── (auth)/                  ← chưa đăng nhập (ĐÃ CÓ, chỉ gom vào nhóm)
│   │   ├── dang-nhap/  dang-ky/  xac-nhan/
│   ├── (app)/                   ← bắt buộc đăng nhập; layout kiểm phiên + menu theo vai trò
│   │   ├── layout.tsx
│   │   ├── page.tsx             Trang chủ: số liệu nhanh + nút Tạo phiếu   (từ vOverview)
│   │   ├── yeu-cau/             Người yêu cầu
│   │   │   ├── page.tsx         Yêu cầu của tôi
│   │   │   ├── moi/page.tsx     Tạo phiếu (form + xem trước chuỗi duyệt)   (từ vCreate)
│   │   │   └── [id]/page.tsx    Chi tiết: các bước, SLA, bình luận, nút thao tác   (từ ticketDetail)
│   │   ├── hop-viec/            Người xử lý: chờ tôi / sắp hết hạn / quá hạn / đã xử lý
│   │   ├── uy-quyen/            Ủy quyền vắng mặt
│   │   ├── ma-tran/             Xem ma trận SoD, chỉ đọc   (từ vMatrix)
│   │   ├── quan-tri/            Chỉ ADMIN
│   │   │   ├── cau-hinh/        Đề xuất đổi SLA, ma trận → chờ CISO duyệt   (từ vConfig)
│   │   │   ├── nguoi-dung/      Xem danh bạ, khoá tài khoản (KHÔNG sửa vai trò)
│   │   │   ├── sla/             Bảng theo dõi SLA
│   │   │   └── ngoai-le/        Sổ đăng ký ngoại lệ
│   │   ├── kiem-toan/           Chỉ AUD: mọi ticket (chỉ đọc), xuất bằng chứng
│   │   ├── nhat-ky/             Chỉ AUD (ĐÃ CÓ)
│   │   └── doi-mat-khau/        (ĐÃ CÓ)
│   ├── actions/                 Server Actions: chỉ nhận form, gọi lib/, không chứa luật
│   │   ├── auth.ts              (ĐÃ CÓ)
│   │   ├── tickets.ts           tạo, bổ sung, huỷ
│   │   ├── decisions.ts         duyệt, từ chối, trả lại, hoàn tất
│   │   ├── delegation.ts
│   │   └── admin.ts
│   └── ui/                      Component dùng chung: StepList, SlaBar, Badge, Topbar…
├── lib/
│   ├── auth/                    session, password, verification (ĐÃ CÓ, chuyển vào đây)
│   ├── authz/
│   │   └── policy.ts            can(user, action, ticket): NƠI DUY NHẤT quyết định quyền
│   ├── sod/                     Chuyển từ app.js / data.js; hàm thuần, không đụng DB
│   │   ├── catalog.ts           vai trò, hoạt động, ma trận, cặp xung đột
│   │   ├── classify.ts          classify()
│   │   ├── chain.ts             phaseSteps(), buildTicket()
│   │   └── conflicts.ts         conflictsFor(), violations()
│   ├── tickets/
│   │   ├── service.ts           nghiệp vụ: submit, decide, reject, return, cancel (transaction + audit)
│   │   └── queries.ts           truy vấn đã lọc theo quyền xem
│   ├── sla/                     hẹn giờ 75/100/200% bằng pg-boss
│   ├── notify/                  thông báo trong app + email
│   ├── audit.ts  db.ts  mail.ts  validation.ts   (ĐÃ CÓ)
├── prisma/
│   ├── schema.prisma
│   ├── migrations/              mỗi bước một migration; trigger SoD viết tay như audit_log
│   └── seed.ts                  + seed ma trận / loại ticket từ data.js
└── tests/
    ├── unit/sod/                so kết quả với bản mẫu cho cả 11 loại ticket (bảng mục 3)
    ├── security/                T1–T15 ở mục 9.3.4, mỗi dòng ít nhất một test
    └── e2e/                     luồng đầy đủ trên trình duyệt
```

**Quy tắc phân tầng:**
- `app/` chỉ lo hiển thị và nhận form.
- `lib/tickets/service.ts` là nơi duy nhất ghi ticket.
- `lib/authz/policy.ts` là nơi duy nhất quyết định quyền.
- `lib/sod/` không đọc DB, nên test được độc lập.

### 9.5. Dữ liệu thêm vào DB

| Bảng | Nội dung chính | Ràng buộc quan trọng |
|---|---|---|
| `config_versions` | Phiên bản cấu hình (ma trận, SLA, thứ tự duyệt, cặp xung đột) dạng JSON, người đề xuất, người duyệt | Người đề xuất ≠ người duyệt. Đã duyệt thì không sửa |
| `tickets` | Mã, loại, người yêu cầu, trạng thái, Level, PII, ưu tiên, `config_version_id`, `version` | Người yêu cầu lấy từ phiên đăng nhập |
| `ticket_revisions` | Nội dung phiếu mỗi lần gửi hoặc bổ sung, kèm mã băm | Chỉ ghi thêm |
| `ticket_steps` | Thứ tự, hoạt động, vai trò, P/R/A, người được giao, hạn SLA, trạng thái | Chỉ một bước “đang xử lý” mỗi ticket |
| `step_decisions` | Ai, lúc nào, duyệt/từ chối/trả lại, ghi chú, duyệt trên phiên bản nội dung nào, có phải người được ủy quyền không | UNIQUE bước + trigger SoD (9.3.3) |
| `ticket_comments` | Bình luận, cờ nội bộ | Cờ nội bộ chờ mục 8, câu 11 |
| `delegations` | Người ủy quyền, người nhận, vai trò, từ–đến, lý do | Người nhận cùng vai trò |
| `sod_exceptions` | Các trường theo rule.md mục 8 | Có hạn, tự nhắc thu hồi |
| `notifications`, `sla_events`, `sod_violations` | Vận hành, theo mục 6.2 | |

### 9.6. Luồng nghiệp vụ chi tiết

**Luồng 1: Vào hệ thống**
1. Mở bất kỳ trang nào trong `(app)`. Không có phiên hợp lệ → chuyển tới `/dang-nhap`.
2. Đăng nhập bằng email hoặc username. Mật khẩu tạm → buộc đổi mật khẩu trước. Tài khoản chưa xác nhận email → trang nhập mã.
3. Server đọc **vai trò còn hiệu lực** (`valid_from ≤ hôm nay < valid_to`) và dựng menu. Một người nhiều vai trò thấy gộp menu (mục 1).

**Luồng 2: Tạo và gửi phiếu**
1. Người yêu cầu điền form (giống `vCreate`). Ô “Người yêu cầu” **không còn**: server tự điền theo người đăng nhập.
2. Khung xem trước gọi server để lấy chuỗi duyệt dự kiến. Kết quả chỉ để xem, chưa lưu.
3. Khi bấm Gửi, server làm tuần tự trong **một transaction**:
   1. Kiểm dữ liệu form.
   2. Lấy phiên bản cấu hình đang hiệu lực.
   3. `classify` → `buildTicket` → tự gán người **không xung đột**.
   4. Kiểm SoD.
   5. Nếu không còn ai hợp lệ:
      - chưa xin ngoại lệ → từ chối gửi, báo cần xin ngoại lệ (mục 4);
      - đã xin ngoại lệ → chèn bước “Phê duyệt ngoại lệ kiểm soát” vào đầu chuỗi.
   6. Lưu ticket, phiên bản nội dung kèm mã băm, và các bước.
   7. Bước 1 chuyển sang “đang xử lý”, đặt hẹn SLA.
   8. Ghi nhật ký kiểm toán, gửi thông báo cho người xử lý bước 1 và người C.

**Luồng 3: Xử lý một bước** (duyệt, rà soát, hoàn tất, từ chối, trả lại)
1. Người xử lý mở ticket từ Hộp việc. Nút thao tác **chỉ hiện** khi `can()` cho phép. Việc ẩn nút chỉ để tiện, không phải lớp bảo vệ.
2. Người xử lý bấm nút. Server làm trong một transaction:
   1. Khoá ticket.
   2. Kiểm `version`.
   3. Kiểm lại đủ điều kiện ở bảng 9.3.2.
   4. Ghi `step_decisions`. Trigger DB kiểm lại lần cuối.
   5. Cập nhật bước.
   6. Ghi nhật ký.
3. Sau khi ghi:
   - **Duyệt / hoàn tất** → sang bước kế tiếp. Nếu là bước cuối → Hậu kiểm hoặc Hoàn tất, thông báo người yêu cầu và người I.
   - **Từ chối** → ticket đóng, bắt buộc có lý do.
   - **Trả lại** → tạm dừng SLA, ticket về người yêu cầu (luồng 4).
   - **Thực thi thất bại** → về bước trước hoặc mở ticket sự cố (mục 4).

**Luồng 4: Bổ sung sau khi bị trả lại**
1. Người yêu cầu sửa phiếu → tạo phiên bản nội dung mới.
2. Server phân loại lại. Nếu Level, PII hoặc phạm vi đổi, các bước đã duyệt trong hoạt động bị ảnh hưởng quay về “chờ” và người mới phải duyệt lại.
3. Chạy tiếp SLA.

**Luồng 5: Ủy quyền vắng mặt**
1. Người xử lý tạo ủy quyền: chọn người cùng vai trò, thời gian, lý do.
2. Server kiểm SoD giữa người nhận và từng ticket đang chờ người ủy quyền. Ticket nào xung đột thì báo Admin để chuyển người.
3. Quyết định do người nhận ủy quyền đưa ra ghi rõ “thay mặt cho …”.

**Luồng 6: Cấp hoặc đổi vai trò** (ticket RBAC, loại 4)
1. Tạo ticket RBAC → Rel Mgr (R) → Sys Owner (A) → CISO (A) → IAM (P).
2. Khi IAM bấm hoàn tất, server mới ghi `user_roles`, với `granted_by` là IAM và kèm mã ticket.
3. Kiểm tra: người được cấp không nằm trong chuỗi duyệt ticket đó.

**Luồng 7: Đổi cấu hình**
1. Admin đề xuất. Hệ thống hiển thị so sánh cũ/mới.
2. CISO duyệt → phiên bản mới có hiệu lực cho **ticket tạo sau**. Ticket đang chạy giữ phiên bản cũ.

**Luồng 8: SLA** (chạy ở server, 24/7)
- Hẹn sẵn các mốc 75%, 100% và 200% bằng pg-boss.
- Tới mốc: gửi thông báo, leo thang, ghi `sla_events`.
- Không bao giờ tự động duyệt.

**Luồng 9: Kiểm toán**
- Auditor xem mọi ticket (chỉ đọc), nhật ký, sổ ngoại lệ, vi phạm.
- Xuất bằng chứng theo ticket hoặc theo kỳ.
- Mọi lần xem và xuất đều được ghi lại.

### 9.7. Thứ tự làm (mỗi bước xong có test và demo)

**Tiến độ (29/09/2026):**
- **Bước 1–4 xong:** logic đã chuyển sang `web/lib/sod/`, có bảng ticket và trigger DB, có service và phân quyền.
- **Giao diện đã có:** Tổng quan, Tạo phiếu, Yêu cầu của tôi, Hộp việc, Chi tiết, Ma trận.
- **Đã test:** T1–T3, T8, T9, T11, T15.
- **Còn lại:** bước 5–8.

| Bước | Nội dung | Kết quả nghiệm thu |
|---|---|---|
| 0 | Chốt các mục [Cần chốt] A–D. Commit phần `web/` hiện có (sau khi duyệt) | Plan được duyệt |
| 1 | Chuyển `lib/sod/` từ `app.js` + test so sánh với bản mẫu cho 11 loại ticket | Test đạt, kết quả giống bản mẫu |
| 2 | Migration: `config_versions`, `tickets`, `ticket_revisions`, `ticket_steps`, `step_decisions` + trigger SoD. Seed cấu hình từ `data.js` | Test trigger: T2, T8, T11 bị chặn ngay ở DB |
| 3 | `lib/authz/policy.ts` + `lib/tickets/service.ts` (gửi, duyệt, từ chối) | Test bảo mật T1–T3, T9, T15 |
| 4 | Giao diện: layout có menu theo vai trò, Tạo phiếu, Yêu cầu của tôi, Chi tiết, Hộp việc | Demo luồng 1–3 với loại 1, 2, 3 (đúng MVP mục 7) |
| 5 | Trả lại/bổ sung, huỷ, ủy quyền (luồng 4, 5) | Test T6, T7 |
| 6 | Trang quản trị + đổi cấu hình 2 người, ticket RBAC ghi vai trò (luồng 6, 7) | Test T4, T5, T10 |
| 7 | SLA bằng pg-boss + email (luồng 8) | Demo quá hạn → leo thang |
| 8 | Trang kiểm toán + xuất bằng chứng (luồng 9) | Chạy toàn bộ T1–T15 |

### 9.8. Cần chốt thêm

| # | Câu hỏi | Đề xuất |
|---|---|---|
| A | Làm lại giao diện bằng React hay giữ `app.js` rồi nối API | **Đã chốt: React** |
| B | Mỗi tài khoản gắn với mã nhân viên duy nhất (chống tài khoản phụ, T4)? | Có. Cần danh sách mã NV từ HR |
| C | Bắt xác thực lại khi duyệt Level 3 / ngoại lệ (T14)? | Có, nhập mã gửi qua email |
| D | Đăng nhập bằng mật khẩu dùng tạm hay lâu dài (mục 6.1 chọn SSO)? | Dùng tạm, chuyển sang SSO khi có IdP (mục 8, câu 10) |
