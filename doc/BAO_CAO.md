# BÁO CÁO

## Xây dựng hệ thống quản lý yêu cầu cấp quyền theo nguyên tắc phân tách trách nhiệm (SoD Flow)

| | |
|---|---|
| Sinh viên thực hiện | [Họ tên – MSSV] |
| Nhóm | [Tên nhóm / danh sách thành viên] |
| Giảng viên / người hướng dẫn | [Họ tên] |
| Thời gian | [từ … đến …] |

Tài liệu liên quan trong cùng thư mục: [rule.md](rule.md) (quy tắc SoD gốc), [KE_HOACH.md](KE_HOACH.md) (kế hoạch triển khai), [README_web.md](README_web.md) (mô tả ứng dụng), [DATABASE.md](DATABASE.md) (mô tả cơ sở dữ liệu).

---

## 1. Yêu cầu bài toán

### 1.1. Bài toán lớn

Trong doanh nghiệp, quyền truy cập vào hệ thống và dữ liệu (đặc biệt là dữ liệu cá nhân – DLCN và quyền quản trị cơ sở dữ liệu) phải được kiểm soát chặt chẽ. Nguyên tắc **phân tách trách nhiệm** (Segregation of Duties – SoD) yêu cầu: không một cá nhân nào được nắm trọn một quy trình nhạy cảm từ đầu đến cuối. Ví dụ, người xin quyền không được tự phê duyệt, người phê duyệt không được tự cấp quyền, người cấp quyền không được tự rà soát quyền của chính mình.

Quy định nội bộ ([rule.md](rule.md)) đã định nghĩa:

- **10 vai trò**: Requestor, Line Manager, DPO/Compliance, System Owner, CISO/Security, IAM Administrator, Developer, Release Manager, Production Operator, Auditor.
- **Ma trận SoD** gồm 19 hoạt động kiểm soát × 10 vai trò, mỗi ô mang một ký hiệu: P (thực hiện), A (phê duyệt), R (rà soát), C (tham vấn), I (nhận thông báo), X (cấm).
- **8 cặp vai trò xung đột** không được giao cho cùng một người trên cùng một giao dịch.
- **Quy tắc ngoại lệ** (tầng dữ liệu 2 hoặc có DLCN phải có DPO rà soát; tầng 3 phải có CISO phê duyệt; break-glass phải hậu kiểm trong 24 giờ…).
- **Biểu mẫu "Phiếu cấp / thu hồi quyền truy cập và truy cập đặc quyền khẩn cấp"**.

Hiện tại quy trình chạy bằng phiếu giấy/Word và email, nên có các vấn đề:

- Khó biết phiếu đang chờ ai, đã quá hạn hay chưa.
- Việc chọn người duyệt phụ thuộc vào người lập phiếu, dễ chọn "người quen".
- Không có cơ chế kỹ thuật ngăn một người đảm nhận hai vai trò xung đột.
- Bằng chứng cho kiểm toán nằm rải rác, có thể bị sửa.

**Mục tiêu của bài toán lớn:** xây dựng một hệ thống ticket nội bộ số hoá toàn bộ quy trình trên, trong đó máy tự xác định chuỗi người xử lý từ ma trận SoD, tự chặn các vi phạm và lưu nhật ký không sửa được để phục vụ kiểm toán.

### 1.2. Phạm vi đã giải quyết trong đề tài

Bài toán lớn được chia thành 4 giai đoạn ([KE_HOACH.md](KE_HOACH.md) mục 7). Đề tài này giải quyết **giai đoạn 1 (MVP)** với hai loại phiếu chính: **cấp quyền truy cập** (cấp mới, điều chỉnh, gia hạn, break-glass) và **thu hồi quyền**. Cụ thể:

1. **Bản mẫu (prototype)** chạy hoàn toàn trên trình duyệt (`index.html`, `app.js`, `data.js`) để thống nhất luồng nghiệp vụ với người dùng.
2. **Thuật toán sinh chuỗi xử lý**: từ nội dung phiếu → phân loại → danh sách hoạt động trong ma trận → chuỗi bước có thứ tự → tự gán người không xung đột.
3. **Ứng dụng web dùng thật** (thư mục `web/`): đăng nhập, tạo phiếu, hộp việc, duyệt / từ chối theo bước, ma trận SoD, nhật ký kiểm toán, thông báo, in phiếu PDF.
4. **Cơ chế chống "lách luật" tự duyệt** gồm nhiều lớp, ở cả tầng ứng dụng và tầng cơ sở dữ liệu.
5. **Bộ test**: test so sánh logic với bản mẫu và test bảo mật cho các kịch bản tấn công.

Các phần **chưa thuộc phạm vi** (để ở giai đoạn sau): trả lại / bổ sung, ủy quyền vắng mặt, trang quản trị cấu hình hai người duyệt, SLA chạy nền và leo thang, tích hợp SSO và IAM/PAM.

### 1.3. Phân công trong nhóm

> *Phần này nhóm tự điền.*

| Thành viên | Công việc chính | Kết quả bàn giao |
|---|---|---|
| [Thành viên 1] | [ví dụ: phân tích quy trình, chuẩn hoá ma trận SoD, biểu mẫu phiếu] | [ ] |
| [Thành viên 2] | [ví dụ: thiết kế CSDL, trigger, test bảo mật] | [ ] |
| [Thành viên 3] | [ví dụ: giao diện, in phiếu] | [ ] |

**Công việc của tôi:** [mô tả cụ thể phần sinh viên trực tiếp thực hiện, ví dụ: thuật toán sinh chuỗi và kiểm SoD trong `web/lib/sod/`, lớp phân quyền `web/lib/authz/policy.ts`, …]

---

## 2. Tóm tắt lý thuyết, giải pháp, thuật toán

### 2.1. Các lý thuyết và giải pháp liên quan

**a) Nguyên tắc phân tách trách nhiệm (SoD).** Đây là một kiểm soát nội bộ cơ bản trong khung COSO và ISO/IEC 27001 (Annex A – "Segregation of duties"). SoD chia một giao dịch thành các khâu *khởi tạo – phê duyệt – thực thi – rà soát* và giao mỗi khâu cho một người khác nhau, để gian lận hoặc sai sót phải có ít nhất hai người cùng tham gia mới xảy ra được.

**b) Nguyên tắc bốn mắt (four-eyes / maker–checker).** Đây là dạng đơn giản nhất của SoD: mọi thao tác của người làm (maker) phải được một người khác kiểm tra (checker). Nguyên tắc này phổ biến trong ngân hàng.

**c) Ma trận trách nhiệm RACI.** Ma trận này mô tả với mỗi hoạt động thì ai thực hiện, ai chịu trách nhiệm cuối, ai được tham vấn, ai được thông báo. Ma trận trong rule.md mở rộng RACI thành **P/A/R/C/I/X**: R ở đây là "rà soát", và có thêm X nghĩa là "cấm kết hợp".

**d) Kiểm soát truy cập dựa trên vai trò (RBAC) – chuẩn NIST / ANSI INCITS 359.** Chuẩn định nghĩa hai dạng ràng buộc SoD:
- **SoD tĩnh (SSD):** cấm gán cùng lúc hai vai trò xung đột cho một người.
- **SoD động (DSD):** một người có thể giữ hai vai trò, nhưng không được dùng cả hai trong *cùng một phiên / giao dịch*.

**e) Nguyên tắc đặc quyền tối thiểu và truy cập đúng lúc (Least privilege, JIT/PAM).** Quyền chỉ được cấp vừa đủ, có thời hạn, và tự thu hồi khi hết hạn. Quyền khẩn cấp (break-glass) được cấp nhanh nhưng phải giám sát phiên và hậu kiểm.

**f) Nhật ký chống chỉnh sửa (tamper-evident log).** Mỗi bản ghi lưu mã băm của bản ghi trước (hash chain, giống ý tưởng của blockchain), nên nếu sửa hoặc xoá một dòng thì chuỗi bị đứt và phát hiện được.

**g) Phòng thủ nhiều lớp (defense in depth) và kiểm soát đồng thời lạc quan (optimistic concurrency).** Mỗi lớp kiểm tra tự đứng được, một lớp có lỗi thì lớp sau vẫn chặn. Cột `version` chống trường hợp hai người cùng sửa một bản ghi.

**h) Các sản phẩm có sẵn trên thị trường:**
- *Nền tảng quản trị định danh (IGA)* như SailPoint IdentityIQ, Saviynt, SAP GRC Access Control: có phân tích xung đột SoD theo luật, rà soát quyền định kỳ, tích hợp sâu với hệ thống nguồn.
- *Công cụ ticket / ITSM* như ServiceNow, Jira Service Management: có luồng phê duyệt cấu hình được, nhưng người duyệt thường được cấu hình cố định theo loại yêu cầu, và việc kiểm SoD phải tự viết thêm.

### 2.2. Cách giải quyết của nhóm

Ý tưởng chính: **coi ma trận SoD là dữ liệu đầu vào, và để chương trình tự suy ra luồng duyệt**, thay vì vẽ tay luồng cho từng loại phiếu.

#### Bước 1 – Phân loại phiếu (`classify`)

Từ nội dung phiếu, xác định danh sách hoạt động kiểm soát (các dòng trong ma trận):

- Phiếu cấp quyền → `[Khởi tạo, Xác nhận nhu cầu nghiệp vụ, Cấp quyền qua IAM/PAM]`.
- Phiếu thu hồi → `[Thu hồi quyền khi nhân sự nghỉ việc]`.
- Có DLCN → chèn *Phê duyệt quyền có truy cập PII*.
- Tầng dữ liệu 3 → chèn *Phê duyệt quyền đặc quyền hoặc quyền DB*.
- Xin ngoại lệ SoD → chèn *Phê duyệt ngoại lệ kiểm soát* ngay sau bước khởi tạo.
- Áp quy tắc ngoại lệ: nếu tầng 2 / DLCN mà chuỗi chưa có DPO thì "nâng" DPO thành R ở hoạt động phê duyệt phù hợp; tương tự với tầng 3 và CISO.

Mọi quyết định phân loại đều kèm **lý do bằng lời**, hiển thị cho người lập phiếu.

#### Bước 2 – Sinh chuỗi bước (`phaseSteps`, `buildChain`)

Với mỗi hoạt động, lấy các vai trò theo ký hiệu trong ma trận rồi sắp thứ tự:

- **Hoạt động phê duyệt:** R → A → P (duyệt xong mới được thực thi).
- **Hoạt động thực hiện:** P → R → A (làm xong rồi mới rà soát, nghiệm thu).
- Trong cùng nhóm R hoặc A: sắp theo **cấp thẩm quyền** tăng dần (Line Manager → Release Manager → System Owner → DPO → CISO), người cao nhất chốt cuối.
- Auditor luôn đứng cuối mỗi hoạt động (hậu kiểm độc lập).
- **Gộp bước:** nếu hai hoạt động liền nhau có cùng vai trò và cùng hành động thì gộp thành một bước, để một người không phải duyệt hai lần.
- Phiếu break-glass được thêm bước *Auditor hậu kiểm* với SLA 24 giờ.

#### Bước 3 – Tự gán người và kiểm SoD (`autoAssign`, `conflictsFor`)

- Với mỗi bước, duyệt danh sách người đang giữ vai trò đó và chọn **người đầu tiên không gây xung đột** với những bước đã gán (thuật toán tham lam).
- Xung đột gồm: người lập phiếu làm bước R/A (tự duyệt), và một người đảm nhận hai vai trò khác nhau trên cùng phiếu. Như vậy hệ thống áp **SoD động** theo từng phiếu, không cấm một người giữ nhiều vai trò trong tổ chức.
- Nếu không còn ai hợp lệ, hệ thống không cho gửi phiếu và yêu cầu xin ngoại lệ theo rule.md mục 5 và 8.
- Người lập phiếu **không được chọn người duyệt** (bỏ hẳn trường `overrides` của bản mẫu).

#### Bước 4 – Bảo đảm ở phía server và cơ sở dữ liệu

| Lớp | Cơ chế |
|---|---|
| 1. Danh tính | Người thao tác chỉ lấy từ phiên đăng nhập. Mọi trường `requestor`, `assignee` gửi lên đều bị bỏ qua |
| 2. Quyền theo hành động | Một điểm quyết định duy nhất (`lib/authz/policy.ts`). Không có quyền xem thì trả về 404 để không lộ phiếu có tồn tại |
| 3. Kiểm SoD ở server | Kiểm khi gửi phiếu và kiểm lại **ngay lúc bấm duyệt**, vì vai trò có thể vừa bị rút |
| 4. Ràng buộc trong DB | Trigger PostgreSQL `step_decision_guard`, `ticket_step_guard`, `ticket_guard`. Mỗi bước chỉ có một quyết định, quyết định chỉ được ghi thêm. Tài khoản ứng dụng không tắt được trigger |
| 5. Không chọn người duyệt | Hệ thống tự gán |
| 7. Nhật ký | Mọi quyết định và mọi lần bị chặn đều ghi vào `audit_log` trong cùng transaction, có chuỗi băm SHA-256 |

Ngoài ra:

- Nội dung phiếu lúc gửi được lưu kèm **mã băm**. Người duyệt duyệt đúng phiên bản nội dung đó, nên nội dung đã gửi không thể bị sửa lén.
- Chống bấm hai lần / mở hai tab: khoá dòng ticket (`SELECT … FOR UPDATE`) và so cột `version`.

### 2.3. So sánh với các cách đã có

| Tiêu chí | Phiếu giấy + email (hiện trạng) | ITSM thông thường (ServiceNow, Jira SM) | Nền tảng IGA (SailPoint, SAP GRC) | **SoD Flow (đề tài)** |
|---|---|---|---|---|
| Xác định người duyệt | Người lập phiếu tự chọn | Cấu hình cố định theo loại yêu cầu | Theo luật, cấu hình phức tạp | **Tự suy ra từ ma trận SoD và nội dung phiếu** |
| Kiểm xung đột SoD | Thủ công, phụ thuộc người duyệt | Không có sẵn, phải viết thêm | Có, chủ yếu SoD tĩnh trên tập quyền | **SoD động theo từng phiếu, kiểm 3 lần (gửi, gán, lúc duyệt)** |
| Chặn ở tầng dữ liệu | Không | Không | Tuỳ sản phẩm | **Trigger DB chặn kể cả khi ứng dụng có lỗi** |
| Nhật ký kiểm toán | Rải rác, sửa được | Có, quản trị viên sửa được | Có | **Chỉ ghi thêm, chuỗi băm, kiểm tra được bằng `audit_log_verify()`** |
| Bám biểu mẫu nội bộ | Đúng mẫu | Phải tuỳ biến | Phải tuỳ biến | **In đúng mẫu phiếu ban hành (Phần A–H)** |
| Tích hợp cấp quyền tự động | Không | Có qua plugin | Mạnh | Chưa có (giai đoạn 3) |
| Chi phí, độ phức tạp | Thấp | Trung bình – cao (bản quyền) | Rất cao | Thấp, tự vận hành |

**Nhận xét:**
- So với ITSM thông thường, điểm khác biệt chính là luồng duyệt **được suy ra** từ quy tắc, không phải cấu hình tay. Vì vậy khi ma trận SoD thay đổi, luồng thay đổi theo mà không phải vẽ lại.
- So với IGA thương mại, giải pháp còn thiếu phần tích hợp với hệ thống nguồn và rà soát quyền quy mô lớn, nhưng nhẹ hơn nhiều và bám đúng quy trình, biểu mẫu nội bộ.
- Thuật toán gán người theo kiểu tham lam đơn giản, chạy nhanh và cho kết quả giống hệt bản mẫu đã được nghiệp vụ duyệt. Tuy nhiên, thuật toán không bảo đảm tìm được cách gán hợp lệ trong mọi trường hợp. Bài toán gán tổng quát tương đương bài toán thoả mãn ràng buộc (CSP); nếu cần có thể thay bằng tìm kiếm quay lui.

---

## 3. Mô tả phần mềm cài đặt

### 3.1. Kiến trúc và công nghệ

| Tầng | Công nghệ |
|---|---|
| Ngôn ngữ | TypeScript |
| Web | Next.js 16 (App Router, Server Actions), React 19 |
| Cơ sở dữ liệu | PostgreSQL 16, Prisma ORM 7 (migration + SQL viết tay cho trigger) |
| Kiểm tra dữ liệu | Zod |
| Email | Nodemailer (SMTP); chưa cấu hình SMTP thì in mã ra console |
| Test | `node:test` + tsx |

Cấu trúc mã nguồn theo nguyên tắc phân tầng:

- `web/app/` chỉ hiển thị và nhận form.
- `web/lib/sod/` gồm các hàm thuần (phân loại, sinh chuỗi, kiểm SoD), không đọc DB nên test độc lập được.
- `web/lib/authz/policy.ts` là nơi duy nhất quyết định quyền.
- `web/lib/tickets/service.ts` là nơi duy nhất ghi ticket.

Chi tiết xem [README_web.md](README_web.md) và [DATABASE.md](DATABASE.md).

### 3.2. Chức năng chính

- **Đăng nhập / đăng ký** có mã xác nhận email. Khoá tạm sau 5 lần sai mật khẩu, phiên hết hạn sau 12 giờ.
- **Tạo phiếu** theo đúng biểu mẫu giấy, có khung xem trước chuỗi duyệt và lý do phân loại, có chữ ký tay trên màn hình.
- **Hộp việc:** các phiếu chờ tôi xử lý / đã xử lý, kèm thanh SLA.
- **Chi tiết phiếu:** các bước, ai làm, lúc nào, nút duyệt / từ chối (chỉ hiện với đúng người được giao).
- **Ma trận SoD** (chỉ đọc), **nhật ký kiểm toán** (chỉ Auditor xem).
- **Thông báo** (chuông): có việc mới, sắp hết / quá hạn SLA, đã duyệt, bị từ chối, hoàn tất.
- **In / lưu PDF phiếu** đúng mẫu ban hành: Phần A–C (thông tin, nội dung đề nghị, cam kết), Phần D (phê duyệt theo cấp), Phần E (thẩm định và thực thi). Phần F (thu hồi quyền) chỉ in khi loại phiếu là Thu hồi; Phần G–H (break-glass và hậu kiểm) chỉ in khi loại phiếu là Break-glass.

### 3.3. Cài đặt

Yêu cầu: Node.js và PostgreSQL đã cài sẵn. Tạo file `web/.env` gồm `DATABASE_URL` (tài khoản chủ sở hữu schema), `APP_DATABASE_URL` (tài khoản ứng dụng `sod_app`) và `SEED_PASSWORD`.

```bash
cd web
npm install
npx prisma migrate deploy   # tạo bảng, trigger, phân quyền
npx prisma db seed          # nạp 11 vai trò và tài khoản dùng thử
npm run dev                 # mở http://localhost:3000
```

Chạy test:

```bash
npm test                    # test logic, so với bản mẫu
npm run test:security       # tạo DB sod_test riêng rồi chạy test bảo mật
```

### 3.4. Tài khoản dùng thử

Lệnh seed tạo 15 tài khoản, mỗi vai trò có ít nhất một người. Đăng nhập bằng tên đăng nhập hoặc email (`<tên đăng nhập>@sod.local`). Mật khẩu chung cho cả 15 tài khoản là giá trị `SEED_PASSWORD` trong `web/.env` (file này không đưa lên git). Chỉ dùng cho môi trường thử trên máy cục bộ; đổi trước khi đưa lên môi trường thật.

| Tên đăng nhập | Họ tên | Vai trò |
|---|---|---|
| `an.nguyen` | Nguyễn An | REQ – Người yêu cầu |
| `oanh.mai` | Mai Oanh | REQ, LM – Quản lý trực tiếp |
| `binh.tran` | Trần Bình | LM |
| `chi.le` | Lê Chi | DPO – Cán bộ bảo vệ dữ liệu |
| `dung.pham` | Phạm Dũng | SO – Chủ hệ thống |
| `son.ho` | Hồ Sơn | SO |
| `giang.hoang` | Hoàng Giang | CISO |
| `ha.vu` | Vũ Hà | IAM – Người cấp quyền |
| `phong.ta` | Tạ Phong | IAM, OPS |
| `khoa.do` | Đỗ Khoa | REQ, DEV |
| `quan.ly` | Lý Quân | DEV, OPS |
| `lan.bui` | Bùi Lan | REL – Quản lý phát hành |
| `minh.ngo` | Ngô Minh | REQ, OPS |
| `nam.dang` | Đặng Nam | AUD – Kiểm toán viên |
| `admin` | Quản trị SoD | ADMIN – Quản trị cấu hình |

Vai trò khác REQ chỉ đổi được qua phiếu cấp / thu hồi vai trò (RBAC), nên danh sách trên có thể khác sau khi chạy thử. Vai trò hiện tại của mình hiện ở mục "Vai trò của bạn" trên trang chủ sau khi đăng nhập.

**Kiểm tra tra cứu của Auditor** (đăng nhập `nam.dang`):

1. Mở **Nhật ký** (`/nhat-ky`): thấy mọi thao tác, kể cả thao tác bị chặn.
2. Mở **Bằng chứng** (`/nhat-ky/bang-chung`): lọc theo kỳ, trạng thái, loại phiếu. Mỗi phiếu hiện người duyệt, thời điểm, phiên bản nội dung và mã băm đã duyệt.
3. Bấm **Xuất CSV** và **In / lưu PDF**.
4. Quay lại **Nhật ký**: mỗi lần xem, xuất CSV, in PDF có một dòng `evidence.viewed` / `evidence.exported` kèm bộ lọc và số phiếu.
5. Đăng nhập tài khoản khác (ví dụ `an.nguyen`) và mở `/nhat-ky`, `/nhat-ky/bang-chung` hoặc đường tải CSV: đều trả 404 như trang không tồn tại.

---

## 4. Kết quả đạt được, hướng phát triển

### 4.1. Kết quả

- Hoàn thành bước 1–4 trong lộ trình ([KE_HOACH.md](KE_HOACH.md) mục 9.7): chuyển logic sang server, có bảng ticket và trigger DB, có lớp phân quyền và nghiệp vụ, có giao diện cho luồng tạo – duyệt – hoàn tất.
- Bịt được 6 lỗ hổng của bản mẫu (L1–L6: mạo danh người lập phiếu, ai cũng duyệt thay được, tự chọn người duyệt, ai cũng sửa cấu hình, kiểm SoD ở trình duyệt, nhật ký sửa được).
- **Kết quả test (chạy ngày 06/10/2026): 20/20 test đạt.**
  - 4 test logic: chuỗi xử lý, người được gán và vi phạm SoD **giống hệt bản mẫu** trên 1.260 tổ hợp phiếu; `phaseSteps` khớp cho cả 19 hoạt động.
  - 16 test bảo mật và thông báo trên DB thật, gồm các kịch bản: T1/T2 người không được giao gửi request duyệt; T3 giả mạo người lập phiếu; người lập phiếu tự duyệt; T8 bấm hai lần / hai tab; T9 bị rút vai trò vẫn bấm duyệt; T11 ghi thẳng vào DB bằng tài khoản ứng dụng; T15 xem phiếu của người khác; luồng đầy đủ đến hoàn tất với nhật ký nguyên vẹn.
- Phiếu in ra khớp biểu mẫu ban hành, có thể nộp kèm hồ sơ giấy khi cần.

### 4.2. Kỹ năng và kiến thức thu được

> *Nhóm điều chỉnh theo thực tế từng người.*

- **Nghiệp vụ:** hiểu nguyên tắc SoD, ma trận trách nhiệm, quy trình cấp / thu hồi quyền, break-glass, yêu cầu về dữ liệu cá nhân và bằng chứng kiểm toán.
- **Phân tích:** chuyển quy định viết bằng lời thành dữ liệu và thuật toán; phát hiện chỗ quy định còn mơ hồ (ví dụ thứ tự giữa nhiều người cùng phê duyệt) và đưa thành câu hỏi cần chốt.
- **Kỹ thuật:**
  - Next.js App Router / Server Actions, TypeScript, Prisma.
  - Thiết kế ràng buộc và trigger PostgreSQL, phân quyền tài khoản DB, nhật ký chuỗi băm.
  - Xử lý đồng thời (khoá dòng, optimistic locking), xử lý múi giờ giữa ứng dụng và DB.
- **Bảo mật ứng dụng:** tư duy theo kịch bản tấn công, phòng thủ nhiều lớp, không tin dữ liệu từ trình duyệt.
- **Kiểm thử:** viết test so sánh với bản tham chiếu và test bảo mật chạy trên DB tách riêng.

### 4.3. Hướng phát triển

Theo lộ trình còn lại ([KE_HOACH.md](KE_HOACH.md) mục 7 và 9.7):

1. **Đủ tình huống nghiệp vụ:** trả lại để bổ sung (tạm dừng SLA, duyệt lại phần bị ảnh hưởng), huỷ phiếu, ủy quyền vắng mặt có kiểm SoD với người nhận.
2. **Quản trị có kiểm soát:** cấu hình ma trận / SLA có phiên bản, thay đổi phải qua hai người (admin đề xuất, CISO duyệt); cấp vai trò chỉ qua ticket RBAC.
3. **SLA chạy nền** bằng pg-boss: nhắc ở mốc 75%, leo thang ở 100%, báo CISO và Auditor ở 200%; gửi email và Teams/Slack.
4. **Break-glass đúng quy định:** cấp quyền tạm ngay qua PAM/JIT rồi duyệt sau, tự thu hồi khi hết phiên, hậu kiểm trong 24 giờ.
5. **Kiểm toán và tích hợp:** trang Auditor, xuất bằng chứng, báo cáo kiểm soát định kỳ, đẩy log sang SIEM, tích hợp IAM/PAM để cấp và thu hồi tự động, đăng nhập SSO (OIDC).
6. **Mở rộng đủ 11 loại ticket** đã có trong ma trận (thay đổi mã nguồn lên Production, xuất / truy vấn PII, sự cố bảo mật, rà soát quyền định kỳ…).
7. **Cải tiến thuật toán gán người:** thay thuật toán tham lam bằng tìm kiếm quay lui để luôn tìm được cách gán hợp lệ nếu có, và cân bằng tải giữa những người cùng vai trò.
8. **Chốt các giả định còn mở** với người có thẩm quyền (định nghĩa tầng dữ liệu, SLA, thứ tự duyệt, thời hạn lưu trữ, nơi đặt máy chủ) – danh sách ở [KE_HOACH.md](KE_HOACH.md) mục 8 và 9.8.

### 4.4. Ý kiến cải tiến chức năng phiếu và cách hoạt động

**Chức năng phiếu**

1. **Danh mục hệ thống.** Ô "Hệ thống" ở Phần B đang nhập tự do. Nên chuyển thành ô chọn từ danh mục (kể cả các thành phần của P086), kèm tầng dữ liệu mặc định và mức quyền hợp lệ theo cấp bậc. Khi đó mục "đúng tầng dữ liệu theo vai trò và cấp bậc" ở Phần E kiểm tự động được.
2. **Phần D–H thành dữ liệu có cấu trúc.** Hiện các phần này chỉ để xem và in. Phần D có thể lấy từ `ticket_steps` / `step_decisions` đã lưu (người, ý kiến, thời gian) thay cho ký tay. Phần E có thể tự đề xuất Đạt / Không đạt cho các mục hệ thống đã biết (đủ cấp phê duyệt, không vi phạm SoD), người thẩm định chỉ xác nhận.
3. **Tách luồng theo loại phiếu.** Điều chỉnh, Gia hạn, Break-glass, Thu hồi hiện đi chung luồng với Cấp mới và Thu hồi (`type_id` chỉ có `access` và `offboard`). Nên tách luồng riêng theo [KE_HOACH.md](KE_HOACH.md) mục 3.
4. **Thu hồi và gia hạn tự động.** Quyền có thời hạn thì nhắc gia hạn trước hạn và tự tạo phiếu thu hồi khi hết hạn. Nhận sự kiện nghỉ việc, điều chuyển từ HR để mở phiếu thu hồi.
5. **Break-glass đúng quy định.** Cấp quyền trước, duyệt sau, tự thu hồi khi hết phiên, có đồng hồ đếm ngược 24 giờ hậu kiểm. Hiện mới có bước Auditor với SLA 24 giờ.
6. **Nối với biên bản rà soát UAR (BM06).** Xuất danh sách quyền hiện hữu để điền Phần III, tự tính Phần I–II. Dòng có kết luận Thu hồi sinh phiếu thu hồi tương ứng. Xem [BM06_Bien_ban_UAR.md](BM06_Bien_ban_UAR.md).
7. **Bản in và trải nghiệm.** In kèm mã băm `form_hash` hoặc mã QR để đối chiếu bản giấy với bản trên hệ thống. Lưu nháp tự động và nhân bản phiếu.

**Cách hoạt động**

8. **Thuật toán gán người.** Hiện dùng cách tham lam và rơi về người đầu tiên khi không còn ai hợp lệ (sau đó buộc xin ngoại lệ). Nên dùng tìm kiếm quay lui, cảnh báo sớm khi một vai trò thiếu người, và cân bằng tải giữa những người cùng vai trò.
9. **Hoàn thiện phần còn thiếu theo lộ trình.** Trả lại / bổ sung, ủy quyền, SLA chạy nền và leo thang, SSO, gắn tài khoản với mã nhân viên (kịch bản T4), xác thực lại khi duyệt tầng 3 (kịch bản T14).
10. **Cấu hình có phiên bản.** Thay đổi ma trận và SLA phải qua hai người (admin đề xuất, CISO duyệt), ticket giữ phiên bản cấu hình lúc tạo.

**Nối với dự án P086** (xem [P086.md](P086.md))

11. **Cấp và thu hồi quyền tự động.** Khi phiếu cấp quyền P086 hoàn tất, SoD Flow gọi API cấp vai trò Admin / Steward / Analyst / Viewer và ACL dataset. Phiếu thu hồi hoàn tất thì thu hồi tương ứng.
12. **Quyết định thay đổi (CAB).** P086 yêu cầu "propose ≠ approve ≠ execute" và chỉ ghi nhận quyết định CAB qua API (`rfc_id`, `decision`, `actor_org`, `timestamp`). Loại phiếu "Thay đổi mã nguồn → Production" của SoD Flow có thể là nguồn cung cấp quyết định này, thay cho nhập tay.
13. **Phân loại sự cố.** P086 phân biệt lỗi hệ thống, lỗi dữ liệu và sự cố ATTT, mỗi loại có ca trực và người chịu trách nhiệm riêng. Có thể dùng làm ba loại phiếu sự cố.


Tên đăng nhập	Email	Vai trò
an.nguyen	an.nguyen@sod.local	REQ
oanh.mai	oanh.mai@sod.local	REQ, LM
binh.tran	binh.tran@sod.local	LM
chi.le	chi.le@sod.local	DPO
dung.pham	dung.pham@sod.local	SO
son.ho	son.ho@sod.local	SO
giang.hoang	giang.hoang@sod.local	CISO
ha.vu	ha.vu@sod.local	IAM
phong.ta	phong.ta@sod.local	IAM, OPS
khoa.do	khoa.do@sod.local	REQ, DEV
quan.ly	quan.ly@sod.local	DEV, OPS
lan.bui	lan.bui@sod.local	REL
minh.ngo	minh.ngo@sod.local	REQ, OPS
nam.dang	nam.dang@sod.local	AUD (Auditor)
admin	admin@sod.local	ADMIN
huyen	huyenvt43@gmail.com	REQ
nguoi.thu97507, nguoi.thu2666	test.…@sod.local	REQ (tài khoản tự đăng ký lúc thử)