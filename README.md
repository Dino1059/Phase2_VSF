# SoD Flow — ứng dụng web

Bản dùng thật của hệ thống ticket SoD, theo [KE_HOACH.md](../KE_HOACH.md) mục 6 và mục 9.
Bản mẫu HTML ở thư mục gốc (`index.html`, `app.js`, `data.js`, `styles.css`) được giữ để demo luồng, và là "đáp án" cho test so sánh logic.

**Đã có:**
- Đăng nhập, đăng ký có mã xác nhận email.
- Tạo phiếu, sinh chuỗi duyệt, kiểm SoD, duyệt / từ chối theo từng bước.
- Hộp việc, ma trận SoD, nhật ký kiểm toán.
- Chuông thông báo trên thanh đầu trang (xem mục “Thông báo”).
- Chặn tự duyệt ở cả ứng dụng lẫn DB.

**Chưa có (theo lộ trình KE_HOACH.md 9.7):**
- Trả lại / bổ sung, huỷ, ủy quyền (bước 5).
- Trang quản trị, đổi cấu hình 2 người, ticket RBAC (bước 6).
- SLA chạy nền, leo thang lên cấp trên, email, thông báo cho người tham vấn / nhận thông báo (bước 7).

## Tech stack

| Tầng | Công nghệ | Phiên bản | Vai trò trong dự án | So với KE_HOACH.md 6.1 |
|---|---|---|---|---|
| Runtime | Node.js | 26.5 | Chạy server Next.js, script seed, test | — |
| Ngôn ngữ | TypeScript | 5.9 | Toàn bộ code | Đúng kế hoạch |
| Web framework | Next.js (App Router) | 16.3 | Giao diện + Server Actions, một ứng dụng duy nhất | Đúng kế hoạch |
| UI | React | 19.2 | Component giao diện | Đã chốt (câu A, mục 9.8) |
| CSS | CSS thuần `app/globals.css` | — | Lấy nguyên `../styles.css` của bản mẫu + phần cho trang đăng nhập | — |
| Font | Be Vietnam Pro qua `next/font/google` | — | Giống bản mẫu | — |
| Cơ sở dữ liệu | PostgreSQL | 16.14 | Lưu toàn bộ dữ liệu | Đúng kế hoạch |
| ORM / migration | Prisma ORM | 7.10 | Schema, migration, seed | Đúng kế hoạch |
| Driver DB | `pg` + `@prisma/adapter-pg` | 8.23 / 7.10 | Prisma 7 bắt buộc dùng driver adapter. Phiên kết nối ép `timezone=UTC` (xem “Ghi chú”) | — |
| Kiểm tra dữ liệu | Zod | 4.6 | Kiểm kiểu dữ liệu form đăng nhập, phiếu, quyết định ở server | **[Cần duyệt]** |
| Gửi email | Nodemailer (SMTP) | 10.0 | Gửi mã xác nhận. Chưa có SMTP thì in ra console | Đúng kế hoạch (SMTP giai đoạn 1) |
| Băm mật khẩu | `scrypt` của Node | — | Không thêm thư viện | **[Cần chốt D]** Kế hoạch là SSO/OIDC |
| Phiên đăng nhập | Cookie httpOnly + bảng `sessions` | — | Token ngẫu nhiên, DB chỉ lưu SHA-256 | Tạm, tới khi có SSO |
| In / PDF phiếu | Hộp thoại in của trình duyệt | — | Thay cho `html2pdf.js` tải từ CDN của bản mẫu: không cần Internet, chữ sắc nét | — |
| Test | `node:test` + tsx | tsx 4.23 | Test logic (so với bản mẫu) và test bảo mật (trên DB `sod_test`) | — |
| Lint | ESLint + eslint-config-next | 9.39 / 16.3 | — | — |
| Chưa dùng | pg-boss (SLA), S3/MinIO + Object Lock, SIEM, Docker | — | — | Làm ở các bước sau |

**Còn chờ chốt** (KE_HOACH.md 9.8):
- **B.** Gắn tài khoản với mã nhân viên.
- **C.** Xác thực lại khi duyệt Level 3 / ngoại lệ.
- **D.** Mật khẩu dùng tạm hay lâu dài.

## Cấu trúc thư mục

```
web/
├── app/
│   ├── (auth)/          dang-nhap, dang-ky, xac-nhan, doi-mat-khau — không cần đăng nhập
│   ├── (app)/           Cần đăng nhập. layout.tsx dựng topbar + menu theo vai trò
│   │   ├── page.tsx         Tổng quan
│   │   ├── yeu-cau/         Yêu cầu của tôi (AUD/ADMIN: thêm “Tất cả”)
│   │   │   ├── moi/         Tạo phiếu: form + khung xem trước chuỗi duyệt
│   │   │   └── [id]/        Chi tiết: các bước, SLA, ô duyệt, nhật ký
│   │   ├── hop-viec/        Chờ tôi xử lý / đã xử lý
│   │   ├── ma-tran/         Ma trận SoD, chỉ đọc
│   │   └── nhat-ky/         Nhật ký kiểm toán, chỉ AUD
│   ├── actions/         Server Actions: auth.ts, tickets.ts, notifications.ts — chỉ nhận form, gọi lib/
│   └── ui/              Topbar, Nav, Bell (chuông), Badge, SlaBar, Phieu (phiếu in)…
├── lib/
│   ├── auth/            session, password, verification
│   ├── authz/policy.ts  NƠI DUY NHẤT quyết định quyền
│   ├── sod/             Chuyển từ app.js/data.js: catalog, form, classify, chain, conflicts — hàm thuần, không đọc DB
│   ├── tickets/         service.ts (ghi: gửi, duyệt, từ chối) · queries.ts (đọc, đã lọc theo quyền)
│   ├── notify/          service.ts: ghi / đọc thông báo, sinh thông báo SLA
│   └── audit.ts  db.ts  mail.ts  validation.ts  format.ts
├── prisma/              schema, migrations (có SQL viết tay cho trigger), seed
└── tests/
    ├── unit/            So lib/sod với ../app.js
    └── security/        Các trò lách luật T1–T15 (KE_HOACH.md 9.3.4) + thông báo; helpers.ts dựng dữ liệu chung
```

## Chạy

```bash
npm install
npx prisma migrate deploy   # tạo bảng, trigger, phân quyền
npx prisma db seed          # 11 vai trò + 15 người dùng tạm
npm run dev                 # http://localhost:3000

npm test                    # test logic: so với bản mẫu (1.260 tổ hợp), định dạng thời gian
npm run test:security       # tạo lại DB sod_test rồi chạy test bảo mật — không đụng DB sod
```

Chưa cấu hình `SMTP_HOST` thì mã xác nhận được **in ra console của server**.

## Chặn tự duyệt ticket

Theo KE_HOACH.md 9.3. Đã làm lớp 1–5 và 7; lớp 6 (cấp vai trò qua ticket RBAC) làm ở bước 6.

| Lớp | Ở đâu trong code |
|---|---|
| 1. Danh tính chỉ lấy từ phiên | `app/actions/tickets.ts` gọi `requireUser()`. Form không có trường người yêu cầu; `TicketFormSchema` bỏ mọi trường lạ (`requestor`, `overrides`) |
| 2. Quyền theo hành động | `lib/authz/policy.ts`: `canViewTicket`, `decisionBlockers`. Không có quyền xem → 404 |
| 3. Kiểm SoD ở server | Khi gửi phiếu (`submitTicket`) và ngay lúc bấm duyệt (`decideStep` → `decisionBlockers`) |
| 4. Ràng buộc trong DB | Trigger `step_decision_guard`, `ticket_step_guard`, `ticket_guard` (migration `…_tickets`). Mỗi bước tối đa một quyết định; quyết định chỉ ghi thêm |
| 5. Không chọn người duyệt | Bỏ `overrides`; `autoAssign` tự gán người không xung đột |
| 7. Nhật ký | Mỗi quyết định và mỗi lần bị chặn đều ghi `audit_log` |

Chống bấm hai lần / hai tab: khoá dòng ticket (`FOR UPDATE`) và so cột `version`.

## Thông báo

Chuông trên thanh đầu trang. Mỗi tài khoản chỉ thấy thông báo của mình (mọi truy vấn lọc theo người đăng nhập).

| Sự kiện | Ai nhận |
|---|---|
| Bước mới tới lượt (“SOD-… chờ bạn rà soát”) | Người được giao bước |
| Đã dùng ≥ 75% SLA / quá hạn SLA | Người được giao bước |
| Một bước được duyệt (“System Owner đã duyệt → chờ Line Manager”) | Người nộp |
| Bị từ chối (kèm lý do) / hoàn tất | Người nộp |

- Thông báo sự kiện được ghi trong cùng transaction với quyết định.
- Thông báo SLA được sinh mỗi lần chuông tải dữ liệu (tự tải lại mỗi 30 giây), mỗi mốc chỉ báo một lần. Bước 7 sẽ chuyển sang job nền (pg-boss).
- `sod_app` chỉ được sửa cột `read_at`, không sửa được nội dung thông báo.

## Database

Giải thích chi tiết từng bảng, từng cột: [DATABASE.md](DATABASE.md).

| Tài khoản Postgres | Dùng cho | Quyền |
|---|---|---|
| `sod_owner` (`DATABASE_URL`) | migrate, seed | Chủ sở hữu schema |
| `sod_app` (`APP_DATABASE_URL`) | Ứng dụng khi chạy | `audit_log`, `step_decisions`: chỉ SELECT, INSERT. Không có quyền trên `audit_chain_head` |

| Bảng | Nội dung |
|---|---|
| `roles`, `users`, `user_roles` | Vai trò theo rule.md + ADMIN; người dùng; gán vai trò có hiệu lực từ–đến |
| `verification_codes`, `sessions` | Mã xác nhận email (chỉ lưu băm), phiên đăng nhập |
| `tickets` | Mã `SOD-YYYYMM-NNNN` (DB cấp), người yêu cầu, phân loại, nội dung phiếu + SHA-256, `version` |
| `ticket_steps` | Thứ tự, vai trò, P/R/A, người được giao, `sod_waived` (xung đột được chấp nhận theo ngoại lệ), hạn SLA |
| `step_decisions` | Ai quyết định, lúc nào, kết quả, ghi chú |
| `notifications` | Thông báo trong app; UNIQUE (người nhận, `dedupe_key`) chống trùng |
| `audit_log`, `audit_chain_head` | Nhật ký chỉ ghi thêm, có chuỗi băm. `SELECT * FROM audit_log_verify()` rỗng = nguyên vẹn |

Nhật ký của từng ticket được đọc từ `audit_log` (`target_type = 'ticket'`), không lưu bản riêng.

## Người dùng tạm (seed)

Lấy từ `DEFAULT_PEOPLE` trong [data.js](../data.js). Username dạng `ten.ho`, email `ten.ho@sod.local`. Mật khẩu tạm là `SEED_PASSWORD` trong `.env`, **bắt buộc đổi ở lần đăng nhập đầu**.

| Username | Vai trò | Username | Vai trò |
|---|---|---|---|
| an.nguyen | REQ | ha.vu | IAM |
| oanh.mai | REQ, LM | phong.ta | IAM, OPS |
| binh.tran | LM | khoa.do | REQ, DEV |
| chi.le | DPO | quan.ly | DEV, OPS |
| dung.pham, son.ho | SO | lan.bui | REL |
| giang.hoang | CISO | minh.ngo | REQ, OPS |
| nam.dang | AUD | admin | ADMIN |

Thứ tự tạo tài khoản quyết định ai được ưu tiên tự gán, giống thứ tự danh bạ trong bản mẫu.

## Ghi chú

- **Múi giờ:** Postgres trên máy dùng múi giờ `Asia/Ho_Chi_Minh`. Driver `adapter-pg` gửi giờ UTC không kèm múi giờ, nên nếu không ép `timezone=UTC` thì giờ do ứng dụng ghi lệch 7 tiếng so với `now()` trong trigger. Có test chặn lỗi này quay lại.
- **Dữ liệu thử trong DB `sod`:**
  - Có 2 ticket `SOD-202609-0001`, `…-0002` và vài tài khoản `test.…` từ lần chạy thử.
  - Những dòng này được ghi trước khi sửa lỗi múi giờ, nên thời điểm tạo hiển thị sớm hơn 7 tiếng.
  - Muốn xoá sạch: `npx prisma migrate reset --force` rồi `npx prisma db seed`. Lệnh này **xoá toàn bộ DB `sod`**.
- Ở chế độ dev, kết nối DB được giữ qua các lần nạp lại code. `lib/db.ts` tự tạo kết nối mới khi client Prisma được sinh lại (đổi schema) nên không cần khởi động lại `npm run dev`.
