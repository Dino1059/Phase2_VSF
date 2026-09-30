# Cơ sở dữ liệu SoD Flow — giải thích từng bảng, từng cột

Database **`sod`** (PostgreSQL 16, máy local). Schema `public`, **12 bảng**. Nội dung đối chiếu với DB thật ngày 29/09/2026.
Định nghĩa gốc nằm ở [prisma/schema.prisma](prisma/schema.prisma) và [prisma/migrations/](prisma/migrations/). Trigger và phân quyền là phần SQL viết tay ở cuối mỗi file migration.

**Quy ước chung:**
- `uuid`: mã định danh ngẫu nhiên 36 ký tự, ví dụ `5d304a8e-f89e-4d5f-8721-91be3a65b8a6`.
- `timestamptz`: thời điểm có múi giờ. Khi hiển thị, ứng dụng đổi sang giờ Việt Nam.
- **Bắt buộc**: cột không được để trống (NOT NULL).
- Tên cột trong DB viết `snake_case`. Trong code TypeScript cùng cột đó viết `camelCase`, ví dụ `requester_id` ↔ `requesterId`.

---

## Sơ đồ quan hệ

```
roles ──< user_roles >── users ──< sessions
                           │  └──< verification_codes
                           │
                           ├──< tickets (người nộp) ──< ticket_steps (người được giao) ──1 step_decisions (người quyết định)
                           │         │
                           └──< notifications >──┘

audit_log      (nhật ký mọi sự kiện, không nối khoá ngoại để không phụ thuộc bảng khác)
audit_chain_head (1 dòng: đầu chuỗi băm của audit_log)
_prisma_migrations (Prisma quản lý)
```
`A ──< B` nghĩa là một dòng A có nhiều dòng B. `──1` nghĩa là tối đa một.

| Nhóm | Bảng |
|---|---|
| Người dùng & đăng nhập | `roles`, `users`, `user_roles`, `sessions`, `verification_codes` |
| Ticket | `tickets`, `ticket_steps`, `step_decisions` |
| Thông báo | `notifications` |
| Nhật ký kiểm toán | `audit_log`, `audit_chain_head` |
| Hệ thống | `_prisma_migrations` |

---

## 1. Người dùng & đăng nhập

### `roles` — danh mục vai trò
11 dòng cố định: 10 vai trò theo rule.md mục 1, cộng `ADMIN`. Nạp bằng `prisma/seed.ts`.

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `code` | varchar(10) | ✔ khoá chính | Mã vai trò, dùng khắp hệ thống | `SO` |
| `name` | varchar(100) | ✔ | Tên đầy đủ | `System Owner` |
| `short_name` | varchar(30) | ✔ | Tên ngắn cho cột ma trận | `Sys Owner` |
| `description` | text | | Trách nhiệm chính | `Chịu trách nhiệm nghiệp vụ và phê duyệt quyền trong hệ thống` |

Các mã vai trò: `REQ` Người nộp · `LM` Line Manager · `DPO` DPO/Compliance · `SO` System Owner · `CISO` CISO/Security · `IAM` IAM Administrator · `DEV` Developer · `REL` Release Manager · `OPS` Production Operator · `AUD` Auditor · `ADMIN` Quản trị SoD.

### `users` — tài khoản

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `id` | uuid | ✔ khoá chính | Mã tài khoản | |
| `username` | varchar(50) | ✔ duy nhất | Tên đăng nhập. Luôn chữ thường, 3–50 ký tự `a-z 0-9 . _ -` (CHECK trong DB) | `an.nguyen` |
| `email` | varchar(254) | ✔ duy nhất | Email, luôn chữ thường. Đăng nhập được bằng email hoặc username | `an.nguyen@sod.local` |
| `full_name` | varchar(150) | ✔ | Họ tên hiển thị | `Nguyễn An` |
| `password_hash` | text | ✔ | Mật khẩu đã băm bằng scrypt, **không lưu mật khẩu gốc**. Định dạng `scrypt$N$r$p$muối$băm` | `scrypt$16384$8$1$…` |
| `status` | enum `user_status` | ✔ | `PENDING` = đã đăng ký, chưa nhập mã email · `ACTIVE` = dùng được · `DISABLED` = bị khoá hẳn | `ACTIVE` |
| `email_verified_at` | timestamptz | | Lúc xác nhận email thành công | |
| `must_change_password` | boolean | ✔ | `true` = đang dùng mật khẩu tạm, phải đổi trước khi vào hệ thống | `false` |
| `failed_login_count` | integer | ✔ | Số lần nhập sai mật khẩu liên tiếp. Tới 5 thì khoá tạm, rồi về 0 | `0` |
| `locked_until` | timestamptz | | Khoá tạm tới lúc này (15 phút sau lần sai thứ 5) | |
| `last_login_at` | timestamptz | | Lần đăng nhập thành công gần nhất | |
| `created_at` | timestamptz | ✔ | Lúc tạo tài khoản. **Thứ tự này quyết định ai được ưu tiên tự gán** khi nhiều người cùng vai trò | |
| `updated_at` | timestamptz | ✔ | Lần sửa gần nhất | |

### `user_roles` — ai giữ vai trò gì, từ khi nào tới khi nào

Một người có thể giữ nhiều vai trò, ví dụ `oanh.mai` giữ cả `REQ` và `LM`. Vai trò chỉ **còn hiệu lực** khi `valid_from ≤ bây giờ` và `valid_to` trống hoặc sau bây giờ.

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `id` | uuid | ✔ khoá chính | | |
| `user_id` | uuid → `users` | ✔ | Người được gán | |
| `role_code` | varchar(10) → `roles` | ✔ | Vai trò | `LM` |
| `valid_from` | timestamptz | ✔ | Bắt đầu hiệu lực | |
| `valid_to` | timestamptz | | Hết hiệu lực. Trống = vô thời hạn. Phải sau `valid_from` (CHECK) | |
| `granted_by` | uuid → `users` | | Người cấp. Trống với dữ liệu seed hoặc tự cấp khi đăng ký | |
| `note` | text | | Ghi chú nguồn gốc | `Dữ liệu tạm theo bản kế hoạch`, `Tự cấp khi xác nhận email` |
| `created_at` | timestamptz | ✔ | | |

Trigger duyệt ticket kiểm bảng này **ngay lúc bấm duyệt**: bị rút vai trò thì không duyệt được nữa.

### `sessions` — phiên đăng nhập

| Cột | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `id` | uuid | ✔ khoá chính | |
| `user_id` | uuid → `users` | ✔ | Chủ phiên. Xoá tài khoản thì xoá luôn phiên |
| `token_hash` | varchar(64) | ✔ duy nhất | SHA-256 của token trong cookie `sod_session`. DB **không lưu token gốc**, nên lộ DB cũng không dùng lại được phiên |
| `created_at` | timestamptz | ✔ | Lúc đăng nhập |
| `expires_at` | timestamptz | ✔ | Hết hạn (12 giờ sau đăng nhập) |
| `revoked_at` | timestamptz | | Lúc bị thu hồi: đăng xuất, hoặc đổi mật khẩu (thu hồi mọi phiên khác) |
| `ip` | varchar(64) | | IP lúc đăng nhập |
| `user_agent` | varchar(512) | | Trình duyệt lúc đăng nhập |

### `verification_codes` — mã xác nhận email khi đăng ký

| Cột | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `id` | uuid | ✔ khoá chính | |
| `user_id` | uuid → `users` | ✔ | Tài khoản đang chờ xác nhận |
| `purpose` | enum `code_purpose` | ✔ | Mục đích. Hiện chỉ có `REGISTER` |
| `code_hash` | varchar(64) | ✔ | SHA-256 của mã 6 số, **không lưu mã gốc** |
| `expires_at` | timestamptz | ✔ | Hết hạn sau 10 phút. Gửi mã mới thì mã cũ hết hạn ngay |
| `attempts` | integer | ✔ | Số lần đã nhập. Tối đa 5 |
| `consumed_at` | timestamptz | | Lúc đã dùng thành công. Mỗi mã chỉ dùng một lần |
| `created_at` | timestamptz | ✔ | Lúc gửi. Hai lần gửi phải cách nhau ≥ 60 giây |

---

## 2. Ticket

### `tickets` — mỗi phiếu đã gửi là một dòng

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ (phiếu của bạn) |
|---|---|---|---|---|
| `id` | uuid | ✔ khoá chính | Mã nội bộ, dùng trong đường dẫn `/yeu-cau/<id>` | `5d304a8e-…` |
| `code` | varchar(20) | ✔ duy nhất | Số phiếu. **DB tự cấp** qua hàm `next_ticket_code()`, dạng `SOD-năm tháng-số thứ tự` | `SOD-202609-0004` |
| `requester_id` | uuid → `users` | ✔ | Người nộp. **Luôn là người đang đăng nhập**, không lấy từ form | `an.nguyen` |
| `type_id` | varchar(20) | ✔ | Loại ticket theo KE_HOACH.md mục 3: `access` (cấp quyền) hoặc `offboard` (thu hồi) | `access` |
| `title` | varchar(300) | ✔ | Tiêu đề tự sinh: loại phiếu – họ tên – hệ thống | `Break-glass quyền – Nguyễn An – we` |
| `system` | varchar(500) | ✔ | Các hệ thống trong phần B, cách nhau dấu phẩy | `we` |
| `priority` | varchar(10) | ✔ | Ưu tiên: `urgent` / `high` / `normal` / `low` (CHECK). Nhân vào SLA: ×0.25 / ×0.5 / ×1 / ×2 | `normal` |
| `level` | smallint | ✔ | Tầng dữ liệu cao nhất trong phiếu, 1–3 (CHECK). Tầng 3 → thêm CISO phê duyệt | `2` |
| `pii` | boolean | ✔ | Có dữ liệu cá nhân không → thêm DPO | `true` |
| `break_glass` | boolean | ✔ | Phiếu khẩn cấp → thêm bước Auditor hậu kiểm | `true` |
| `acts` | integer[] | | Các hoạt động kiểm soát (số dòng trong ma trận rule.md mục 3) mà phiếu đi qua | `{0,1,2,4}` |
| `reasons` | text[] | | Lý do phân loại, hiện ở khung “Phân loại” | `{Loại phiếu “Break-glass” → Cấp quyền truy cập, …}` |
| `phases` | jsonb | ✔ | Các giai đoạn: tên, vai trò tham vấn (C), vai trò nhận thông báo (I) | `[{"act":0,"name":"Khởi tạo…","C":[],"I":[…]}]` |
| `form` | jsonb | ✔ | **Toàn bộ nội dung phiếu đã điền**, xem bảng bên dưới | |
| `form_hash` | varchar(64) | ✔ | SHA-256 của `form`. Người duyệt duyệt đúng bản nội dung này | `2797642…` |
| `conflicts` | text[] | | Xung đột SoD được chấp nhận theo ngoại lệ. Rỗng nếu không có | `{}` |
| `exception_id` | varchar(30) | duy nhất | Mã ngoại lệ SoD, dạng `SoD-EX-YYYYMM-NNNN`. Trống nếu không xin ngoại lệ | trống |
| `status` | enum `ticket_status` | ✔ | `OPEN` đang xử lý · `DONE` hoàn tất · `REJECTED` bị từ chối | `OPEN` |
| `version` | integer | ✔ | Tăng 1 sau mỗi quyết định. Chống hai người / hai tab xử lý cùng lúc | `0` |
| `created_at` | timestamptz | ✔ | Lúc gửi | |
| `closed_at` | timestamptz | | Lúc hoàn tất hoặc bị từ chối | |

**Các trường trong cột `form`** (giống phiếu giấy):

| Trường | Ý nghĩa |
|---|---|
| `loaiPhieu` | Loại phiếu: `new` Cấp mới · `adjust` Điều chỉnh · `extend` Gia hạn · `revoke` Thu hồi · `bg` Break-glass |
| `khan` | Mức độ khẩn: `normal` Thường · `urgent` Gấp |
| `hoTen`, `maNV`, `email`, `phongBan`, `chucDanh`, `capBac` (T1–T7), `viTri` | Phần A — người sử dụng quyền |
| `thiTruong` (`vn` / `intl`), `thiTruongGhiRo` | Thị trường cung cấp dịch vụ |
| `nhapThay`, `ntHoTen`, `ntChucDanh`, `ntVanBan` | Nhập thay cho người khác và căn cứ cho phép |
| `rows[]`: `heThong`, `taiNguyen`, `tang` (1/2/3), `mucQuyen` (RO/RW/Full), `thoiHan` | Phần B — từng dòng quyền đề nghị |
| `mucDich`, `dlcn` (`none` / `basic` / `sensitive`), `lyDo` | Mục đích, dữ liệu cá nhân, lý do nghiệp vụ |
| `exception`, `exReason`, `exFrom`, `exTo`, `exControls` | Xin ngoại lệ SoD (rule.md mục 8) |
| `camKet`, `kyTen`, `signature` | Phần C — cam kết, họ tên ký, chữ ký (ảnh PNG dạng `data:image/png;base64,…`) |

**Khoá bởi trigger `ticket_guard`:** sau khi gửi, không sửa được `code`, `requester_id`, `form`, `form_hash`, `type_id`, `acts`, `phases`, `exception_id`. Ticket đã đóng không mở lại được.

### `ticket_steps` — các bước xử lý của từng ticket

Mỗi ticket có nhiều bước theo thứ tự. Bước 0 luôn là người nộp gửi phiếu.

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `id` | uuid | ✔ khoá chính | | |
| `ticket_id` | uuid → `tickets` | ✔ | Thuộc ticket nào | |
| `idx` | smallint | ✔ | Thứ tự bước, bắt đầu từ 0. Duy nhất trong một ticket | `1` |
| `phase` | smallint | ✔ | Thuộc giai đoạn nào (vị trí trong `tickets.phases`) | `1` |
| `key` | varchar(30) | ✔ | Mã bước `hoạt động-vai trò-hành động` | `1-SO-R` |
| `role_code` | varchar(10) → `roles` | ✔ | Vai trò phải làm bước này | `SO` |
| `action` | enum `step_action` | ✔ | `P` thực hiện · `R` rà soát · `A` phê duyệt | `R` |
| `acts` | text[] | | Các hoạt động được gộp vào bước này | `{1,2}` |
| `assignee_id` | uuid → `users` | | Người được giao, **do hệ thống tự gán** người không xung đột SoD | `dung.pham` |
| `sod_waived` | boolean | ✔ | `true` = bước có xung đột SoD nhưng được chấp nhận theo ngoại lệ. Không bao giờ `true` ở bước duyệt ngoại lệ | `false` |
| `break_glass` | boolean | ✔ | Bước hậu kiểm break-glass của Auditor (SLA 24h) | `false` |
| `status` | enum `step_status` | ✔ | `WAITING` chưa tới lượt · `CURRENT` đang xử lý (mỗi ticket chỉ một bước) · `DONE` · `REJECTED` | `CURRENT` |
| `sla_hours` | double | | Số giờ SLA = SLA theo P/R/A (8/24/24h) × hệ số ưu tiên | `24` |
| `started_at` | timestamptz | | Lúc bước bắt đầu (chuyển sang `CURRENT`) | |
| `due_at` | timestamptz | | Hạn SLA = `started_at` + `sla_hours` | |

**Khoá bởi trigger `ticket_step_guard`:** không sửa được `ticket_id`, `idx`, `role_code`, `action`, `sod_waived`. Bước đã xong không sửa được. Không chuyển sang `DONE` / `REJECTED` nếu chưa có dòng trong `step_decisions`.

### `step_decisions` — quyết định trên từng bước

Chỉ được **ghi thêm**, không sửa, không xoá. Mỗi bước tối đa một quyết định.

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `id` | uuid | ✔ khoá chính | | |
| `step_id` | uuid → `ticket_steps` | ✔ duy nhất | Bước được quyết định | |
| `actor_id` | uuid → `users` | ✔ | Người quyết định, **lấy từ phiên đăng nhập** | |
| `outcome` | enum `decision_outcome` | ✔ | `SUBMIT` gửi phiếu (bước 0) · `APPROVE` đồng ý (R/A) · `COMPLETE` đã thực hiện (P) · `REJECT` từ chối | `APPROVE` |
| `comment` | varchar(2000) | | Ghi chú / bằng chứng. **Bắt buộc khi từ chối** | `Đã xác minh phạm vi` |
| `form_hash` | varchar(64) | ✔ | Mã băm nội dung phiếu lúc quyết định. Phải khớp `tickets.form_hash` | |
| `decided_at` | timestamptz | ✔ | Lúc quyết định. **DB tự đặt**, ứng dụng không chọn giờ được | |

**Trigger `step_decision_guard`** chặn ghi quyết định khi:
- ticket đã đóng, hoặc bước chưa tới lượt;
- người quyết định không phải người được giao;
- nội dung phiếu đã đổi;
- người quyết định không còn giữ vai trò;
- **người nộp tự duyệt phiếu của mình**;
- **một người xử lý hai vai trò khác nhau trên cùng ticket**.

Hai trường hợp cuối được bỏ qua nếu bước có `sod_waived = true`.

---

## 3. Thông báo

### `notifications` — thông báo trong chuông 🔔

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `id` | uuid | ✔ khoá chính | | |
| `user_id` | uuid → `users` | ✔ | Người nhận. Mỗi người chỉ đọc được thông báo của mình | `dung.pham` |
| `ticket_id` | uuid → `tickets` | | Ticket liên quan. Bấm thông báo sẽ mở ticket này | |
| `kind` | enum `notification_kind` | ✔ | `TASK` có việc mới · `SLA_REMIND` sắp hết SLA · `SLA_OVERDUE` quá hạn · `STEP_DONE` một bước đã duyệt · `REJECTED` bị từ chối · `DONE` hoàn tất | `TASK` |
| `level` | varchar(10) | ✔ | Màu viền: `info` xanh · `warn` vàng · `danger` đỏ · `ok` xanh lá (CHECK) | `info` |
| `message` | varchar(500) | ✔ | Nội dung | `SOD-202609-0004 chờ bạn rà soát (System Owner) — SLA 24h` |
| `dedupe_key` | varchar(100) | ✔ | Khoá chống trùng. Duy nhất theo từng người nhận | `task:<id bước>`, `sla-overdue:<id bước>` |
| `created_at` | timestamptz | ✔ | Lúc tạo | |
| `read_at` | timestamptz | | Lúc đã đọc. Trống = chưa đọc (số đỏ trên chuông). **Là cột duy nhất ứng dụng được sửa** | |

---

## 4. Nhật ký kiểm toán

### `audit_log` — mọi sự kiện quan trọng

Chỉ được **ghi thêm**. Trigger chặn `UPDATE` / `DELETE` / `TRUNCATE` với mọi tài khoản. Mỗi dòng giữ mã băm của dòng trước, nên sửa lén sẽ bị phát hiện.

| Cột | Kiểu | Bắt buộc | Ý nghĩa | Ví dụ |
|---|---|---|---|---|
| `id` | bigint | ✔ khoá chính | Số thứ tự liên tục 1, 2, 3…, **do trigger cấp**. Nhảy số = mất dòng | `101` |
| `occurred_at` | timestamptz | ✔ | Thời điểm, trigger đặt | |
| `actor_user_id` | uuid | | Người thực hiện (không nối khoá ngoại, để nhật ký đứng độc lập) | |
| `actor_email` | varchar(254) | | Email người thực hiện, hoặc email được nhập khi đăng nhập sai | `an.nguyen@sod.local` |
| `action` | varchar(64) | ✔ | Loại sự kiện, xem danh sách dưới | `ticket.submitted` |
| `target_type` | varchar(32) | | Loại đối tượng bị tác động | `ticket`, `user` |
| `target_id` | varchar(64) | | Mã đối tượng | id ticket |
| `ip` | varchar(64) | | IP | `::1` |
| `user_agent` | varchar(512) | | Trình duyệt | |
| `details` | jsonb | | Chi tiết thêm (lý do thất bại, mã ticket, ghi chú…) | `{"code":"SOD-202609-0004","steps":7}` |
| `prev_hash` | varchar(64) | ✔ | Mã băm của dòng ngay trước. Dòng đầu tiên = 64 số 0 | |
| `hash` | varchar(64) | ✔ | SHA-256 của nội dung dòng này + `prev_hash`, trigger tính | |

**Các giá trị `action`:**

| Nhóm | Giá trị |
|---|---|
| Đăng nhập | `auth.login.success`, `auth.login.failure` (details.reason: `unknown_user`, `bad_password`, `locked`, `disabled`, `email_not_verified`), `auth.account.locked`, `auth.logout` |
| Đăng ký | `auth.register`, `auth.code.sent`, `auth.verify.success`, `auth.verify.failure` |
| Tài khoản | `auth.password.changed`, `seed.user.created` |
| Ticket | `ticket.submitted`, `ticket.step.approved`, `ticket.step.completed`, `ticket.step.rejected`, `ticket.done`, `ticket.decision.denied` (thao tác bị chặn, kèm lý do) |
| Kiểm toán | `audit.viewed` (Auditor mở trang nhật ký) |

Kiểm tra toàn vẹn: `SELECT * FROM audit_log_verify();` → không trả về dòng nào nghĩa là nguyên vẹn.

### `audit_chain_head` — đầu chuỗi băm

Luôn có **đúng 1 dòng**. Trigger khoá dòng này mỗi lần ghi nhật ký, để các dòng nối nhau đúng thứ tự. Tài khoản ứng dụng không đọc, không sửa được.

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `singleton` | boolean, khoá chính | Luôn `true` (CHECK) — đảm bảo chỉ có một dòng |
| `last_id` | bigint | `id` của dòng nhật ký mới nhất |
| `last_hash` | varchar(64) | `hash` của dòng nhật ký mới nhất |

---

## 5. Hệ thống

### `_prisma_migrations` — lịch sử migration
Do Prisma tự quản lý, **không sửa tay**. Mỗi dòng là một lần thay đổi cấu trúc DB đã chạy: `init` (người dùng, nhật ký), `tickets`, `notifications`.

| Cột | Ý nghĩa |
|---|---|
| `id` | Mã lần chạy |
| `checksum` | Mã băm file migration. File bị sửa sau khi chạy thì Prisma báo lỗi |
| `migration_name` | Tên thư mục trong `prisma/migrations/` |
| `started_at`, `finished_at` | Lúc bắt đầu / xong |
| `rolled_back_at` | Lúc bị huỷ (nếu có) |
| `logs` | Lỗi khi chạy (nếu có) |
| `applied_steps_count` | Số bước đã chạy |

---

## 6. Hàm và trigger trong DB

| Tên | Gắn vào | Việc làm |
|---|---|---|
| `next_ticket_code()` | mặc định của `tickets.code` | Cấp số phiếu `SOD-YYYYMM-NNNN` |
| `audit_log_chain` | trước khi thêm `audit_log` | Cấp `id`, thời điểm, tính `prev_hash` / `hash` |
| `audit_log_readonly` | trước khi sửa / xoá / truncate `audit_log` | Chặn |
| `audit_log_payload()`, `audit_log_verify()` | gọi tay | Tính nội dung được băm; kiểm tra toàn vẹn chuỗi |
| `step_decision_guard` | trước khi thêm `step_decisions` | Kiểm SoD lần cuối (xem mục 2) |
| `step_decisions_append_only` → `forbid_change()` | trước khi sửa / xoá `step_decisions` | Chặn |
| `ticket_step_guard` | trước khi sửa `ticket_steps` | Khoá định nghĩa bước, bước đã xong |
| `ticket_guard` | trước khi sửa `tickets` | Khoá nội dung đã gửi, ticket đã đóng |

## 7. Tài khoản Postgres và quyền

| Tài khoản | Dùng khi | Quyền |
|---|---|---|
| `sod_owner` | Chạy migration, seed (`DATABASE_URL`) | Chủ sở hữu mọi bảng |
| `sod_app` | Ứng dụng chạy (`APP_DATABASE_URL`) | `roles`: chỉ đọc · `users`, `user_roles`, `tickets`, `ticket_steps`: đọc/thêm/sửa · `sessions`, `verification_codes`: đọc/thêm/sửa/xoá · `step_decisions`, `audit_log`: **chỉ đọc + thêm** · `notifications`: đọc/thêm, chỉ sửa cột `read_at` · `audit_chain_head`: không có quyền |

Mật khẩu hai tài khoản nằm trong `web/.env`.

## 8. Truy vấn hay dùng

```sql
-- Các phiếu của một người
SELECT t.code, t.title, t.status, t.created_at FROM tickets t
JOIN users u ON u.id = t.requester_id WHERE u.username = 'an.nguyen' ORDER BY t.created_at;

-- Tiến độ một phiếu: từng bước, ai được giao, ai đã quyết định
SELECT s.idx, s.role_code, s.action, s.status, a.username AS duoc_giao, d.outcome, x.username AS nguoi_quyet_dinh, d.comment
FROM ticket_steps s
JOIN tickets t ON t.id = s.ticket_id
LEFT JOIN users a ON a.id = s.assignee_id
LEFT JOIN step_decisions d ON d.step_id = s.id
LEFT JOIN users x ON x.id = d.actor_id
WHERE t.code = 'SOD-202609-0004' ORDER BY s.idx;

-- Nội dung phiếu (bỏ chữ ký cho dễ đọc)
SELECT form - 'signature' FROM tickets WHERE code = 'SOD-202609-0004';

-- Việc đang chờ từng người
SELECT u.username, t.code, s.role_code, s.due_at FROM ticket_steps s
JOIN tickets t ON t.id = s.ticket_id JOIN users u ON u.id = s.assignee_id
WHERE s.status = 'CURRENT' AND s.idx > 0 ORDER BY s.due_at;

-- Nhật ký của một phiếu
SELECT l.id, l.occurred_at, l.actor_email, l.action, l.details FROM audit_log l
JOIN tickets t ON t.id::text = l.target_id WHERE t.code = 'SOD-202609-0004' ORDER BY l.id;

-- Kiểm tra nhật ký có bị sửa không (rỗng = nguyên vẹn)
SELECT * FROM audit_log_verify();
```
