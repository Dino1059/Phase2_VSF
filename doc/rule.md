 
. Phạm vi vai trò 
Vai trò 
Trách nhiệm chính 
Không được đồng thời đảm nhiệm 
Requestor 
Khởi tạo yêu cầu, mô tả mục đích và phạm vi truy cập 
Approver, IAM Provisioner cho cùng yêu cầu 
Line Manager 
Xác nhận nhu cầu nghiệp vụ và phạm vi công việc 
Requestor, IAM Provisioner cho cùng yêu cầu 
DPO/Compliance 
Đánh giá căn cứ xử lý, PII, chuyển dữ liệu xuyên biên giới 
Requestor, System Owner cho cùng trường hợp ngoại lệ 
System Owner 
Chịu trách nhiệm nghiệp vụ và phê duyệt quyền trong hệ thống 
Requestor, IAM Provisioner 
CISO/Security 
Đánh giá rủi ro kỹ thuật, quyền đặc quyền và ngoại lệ 
Người thực thi thay đổi nếu chính họ phê duyệt 
IAM Administrator 
Cấu hình role, group, policy và thực hiện provisioning 
Người phê duyệt yêu cầu đó 
Developer 
Phát triển và kiểm thử mã nguồn 
Production Approver, Production Deployer 
Release Manager 
Kiểm tra bằng chứng và phê duyệt phát hành 
Developer của cùng thay đổi 
Production Operator 
Triển khai hoặc vận hành thay đổi đã được phê duyệt 
Requestor và Approver của cùng thay đổi 
Auditor 
Kiểm tra độc lập và xác nhận bằng chứng 
Thực hiện hoặc phê duyệt hoạt động được kiểm toán 
2. Ký hiệu ma trận 
Ký hiệu 
Ý nghĩa 
P 
Được phép thực hiện 
A 
Được phép phê duyệt hoặc chịu trách nhiệm cuối cùng 
R 
Được phép rà soát hoặc xác nhận 
C 
Được tham vấn 
I 
Được thông báo 
X 
Cấm kết hợp với hoạt động hoặc vai trò tương ứng 
Quy tắc đọc ma trận:
Nhiều A trên một dòng = AND: tất cả người giữ A đều phải phê duyệt, lần lượt từ cấp thấp đến cấp cao.
Mỗi dòng có tối đa một P (một người thực hiện).
Auditor chỉ giữ R, C, I hoặc X, không giữ A. Auditor R = kiểm tra request có bị cấm hoặc vượt quyền không, ngay trước bước thực hiện (P).
Hai loại dữ liệu: IAM được đọc dữ liệu định danh nhân viên (mã NV, họ tên, email công vụ, phòng ban, chức danh, trạng thái làm việc) để cấp / đổi / thu hồi account (dòng 5, 6, 7). IAM không đọc dữ liệu nghiệp vụ / PII khách hàng (dòng 14, 15). Không xem lương, CCCD, sức khỏe, đánh giá nhân sự.
3. Ma trận SoD theo hoạt động 
Hoạt động kiểm soát 
Req. 
Line Mgr 
DPO 
Sys Owner 
CISO 
IAM 
Dev 
Rel. Mgr 
Prod. Op. 
Auditor 
1. Khởi tạo yêu cầu cấp quyền 
P 
X 
I 
I 
I 
X 
I 
I 
X 
I 
2. Xác nhận nhu cầu nghiệp vụ 
X 
A 
C 
R 
I 
X 
X 
X 
X 
I 
3. Phê duyệt quyền có truy cập PII 
X 
A 
A 
R 
C 
X 
X 
X 
X 
I 
4. Phê duyệt quyền đặc quyền hoặc quyền DB 
X 
C 
C 
A 
A 
X 
X 
X 
X 
I 
5. Cấp quyền qua IAM/PAM (*) 
X 
X 
X 
X 
R 
P 
X 
X 
X 
I 
6. Thu hồi quyền khi nhân sự nghỉ việc (*) 
I 
A 
I 
R 
C 
P 
X 
X 
X 
R 
7. Điều chuyển hoặc thay đổi vai trò (*) 
I 
A 
C 
R 
I 
P 
X 
X 
X 
R 
8. Tạo hoặc sửa RBAC role 
X 
X 
C 
A 
A 
P 
X 
R 
X 
I 
9. Phát triển mã nguồn 
X 
X 
X 
I 
R 
X 
P 
X 
X 
I 
10. Kiểm thử và xác nhận kết quả 
X 
X 
C 
R 
R 
X 
P 
A 
X 
I 
11. Phê duyệt phát hành Production 
X 
X 
C 
R 
A 
X 
X 
A 
X 
I 
12. Triển khai Production 
X 
X 
X 
I 
R 
X 
X 
X 
P 
I 
13. Thay đổi giá, khuyến mại hoặc chính sách vận hành (*) 
P 
A 
C 
A 
R 
X 
X 
R 
I 
I 
14. Truy vấn dữ liệu PII nghiệp vụ (khách hàng) trực tiếp (*) 
P 
X 
A 
A 
R 
X 
X 
X 
X 
I 
15. Xuất dữ liệu PII nghiệp vụ (khách hàng) (*) 
P 
A 
A 
R 
R 
X 
X 
X 
X 
I 
16. Phê duyệt ngoại lệ kiểm soát 
X 
C 
A 
A 
A 
X 
X 
X 
X 
I 
17. Điều tra sự cố bảo mật (*) 
C 
I 
C 
R 
A 
C 
C 
C 
P 
I 
18. Đóng sự cố và xác nhận khắc phục (*) 
I 
I 
C 
R 
A 
X 
X 
R 
R 
R 
19. Rà soát quyền định kỳ (*) 
I 
A 
C 
P 
R 
I 
X 
X 
X 
R 
Ghi chú điều chỉnh ma trận (10/2026) — các dòng có (*):
Dòng 5 (Cấp quyền): IAM được đọc dữ liệu định danh nhân viên để mở account, không đọc dữ liệu nghiệp vụ / khách hàng.
Dòng 6, 7 (Thu hồi, Điều chuyển): IAM đọc trạng thái nghỉ việc / phòng ban, chức danh mới của nhân viên để thu hồi / đổi quyền. Auditor giữ R = kiểm tra request có bị cấm hoặc vượt quyền không, ngay trước khi IAM thực hiện.
Dòng 13 (Giá, khuyến mại): bỏ P thứ hai, chỉ Requestor thực hiện sau khi được duyệt; Prod. Op. P → I.
Dòng 14, 15 (Truy vấn / Xuất PII nghiệp vụ): IAM P → X với dữ liệu khách hàng; IAM vẫn đọc dữ liệu định danh nhân viên qua dòng 5. Phiếu nối thêm dòng 5 (IAM mở account qua PAM/JIT) sau bước duyệt, rồi Requestor mới truy vấn / xuất.
Dòng 17 (Điều tra sự cố): bỏ P thứ hai, Prod. Op. điều tra; IAM P → C (cung cấp log truy cập, thông tin account).
Dòng 18 (Đóng sự cố): Auditor A → R, CISO duyệt cuối.
Dòng 19 (Rà soát quyền định kỳ): Sys Owner R → P (thực hiện rà soát); IAM P → I (nhận kết quả để thu hồi, không tự rà soát quyền mình cấp); Auditor A → R.
4. Các cặp xung đột bắt buộc 
Các cặp dưới đây không được gán đồng thời cho cùng một cá nhân trong cùng một phạm vi hệ thống, môi trường hoặc giao dịch. 
Requestor ↔ Approver: người tạo yêu cầu không được tự phê duyệt yêu cầu. 
Approver ↔ IAM Provisioner: người phê duyệt không được tự cấp quyền. 
Developer ↔ Production Approver: người phát triển không được tự phê duyệt phát hành mã do mình tạo. 
Developer ↔ Production Deployer: người phát triển không được tự triển khai thay đổi lên Production. 
Data Exporter ↔ Data Approver: người xuất dữ liệu PII không được tự phê duyệt việc xuất dữ liệu. 
Incident Investigator ↔ Incident Closure Approver: người điều tra không được tự xác nhận đóng sự cố nghiêm trọng. 
IAM Administrator ↔ Access Reviewer: người cấp quyền không được tự xác nhận quyền của chính mình hoặc tự hoàn tất việc rà soát. 
Auditor ↔ Control Operator: kiểm toán viên không được thực hiện hoạt động mà họ đang kiểm toán. 
5. Quy tắc xử lý ngoại lệ 
1. Chỉ cho phép ngoại lệ khi có lý do nghiệp vụ hoặc sự cố khẩn cấp được ghi nhận trong ticket. 
2. Yêu cầu phải nêu rõ phạm vi, người sử dụng, thời gian hiệu lực, rủi ro và biện pháp kiểm soát bù trừ. 
3. Quyền ngoại lệ phải là quyền tạm thời, ưu tiên kích hoạt qua PAM/JIT và tự động thu hồi. 
4. Quyền Level 2 hoặc truy cập PII cần DPO/Compliance rà soát; quyền Level 3 cần CISO/Security phê duyệt. 
5. Break-glass phải được ghi log, giám sát phiên và hoàn tất hậu kiểm trong vòng 24 giờ. 
6. Không được dùng ngoại lệ để duy trì quyền lâu dài hoặc hợp thức hóa việc thiếu nhân sự. 
6. Kiểm soát vận hành và bằng chứng 
Kiểm soát 
Tần suất 
Chủ trì 
Bằng chứng cần lưu 
Rà soát tài khoản đặc quyền, tài khoản dịch vụ và quyền PII 
Hàng tháng 
IAM + CISO/Security 
Báo cáo quyền, kết quả xác nhận, danh sách quyền thu hồi 
Rà soát toàn bộ quyền người dùng và vendor 
Hàng quý 
Line Manager + System Owner 
Biên bản attestation, ticket xử lý quyền thừa 
Kiểm tra xung đột SoD 
Hàng tháng và sau mỗi thay đổi role 
IAM + Auditor 
Báo cáo vi phạm SoD và kế hoạch khắc phục 
Kiểm tra log cấp quyền và thu hồi quyền 
Hàng tháng 
SOC/Security 
Audit log, cảnh báo SIEM, kết quả đối soát 
Đánh giá ngoại lệ 
Hàng quý 
DPO/Compliance + CISO 
Sổ đăng ký ngoại lệ, phê duyệt và bằng chứng đóng 
Lấy mẫu các request Auditor đã cho qua 
Hàng quý 
Bên độc lập với Auditor (Kiểm toán nội bộ / DPO) 
Danh sách mẫu, log quyết định của Auditor, kết quả đối chiếu 
7. Tiêu chí đạt 
Mỗi yêu cầu có người khởi tạo, người phê duyệt và người thực thi độc lập. 
Quyền PII có căn cứ xử lý, mục đích sử dụng và thời hạn rõ ràng. 
Quyền đặc quyền được cấp qua PAM/JIT và tự động thu hồi sau khi hết hạn. 
Mọi thay đổi Production có bằng chứng kiểm thử và phê duyệt trước triển khai. 
Mọi vi phạm SoD được ghi nhận, phân loại rủi ro và khắc phục trong thời hạn được phê duyệt. 
Kết quả rà soát được lưu cùng ticket và sẵn sàng cho kiểm toán. 
8. Biểu mẫu thông tin cần ghi trong ticket ngoại lệ SoD 
Trường 
Giá trị 
Mã ngoại lệ 
[SoD-Exception-ID] 
Hệ thống và môi trường 
[GSM/System/Environment] 
Người dùng hoặc nhóm bị ảnh hưởng 
[User/Group] 
Xung đột phát hiện 
[Role A] và [Role B] 
Lý do nghiệp vụ 
[Business Justification] 
Thời hạn hiệu lực 
[Start Date/Time] đến [End Date/Time] 
Biện pháp kiểm soát bù trừ 
[Compensating Controls] 
Người phê duyệt 
[Add Approver] 
Bằng chứng hậu kiểm 
[Audit Evidence] 


Tra cứu sql 

cd "/Users/vuthuhuyen/SoD /web"
set -a; . ./.env; set +a
psql "${DATABASE_URL%%\?*}" -c "SELECT username,status,failed_login_count,locked_until,last_login_at FROM users WHERE username='nam.dang';"


Đặt lại mk thủ công 

psql "${DATABASE_URL%%\?*}" -c "UPDATE users SET password_hash='<1234>', failed_login_count=0, locked_until=NULL, must_change_password=false WHERE username='nam.dang';"

1. Xem tài khoản, vai trò, trạng thái và dấu vết lần cập nhật

psql "${DATABASE_URL%%\?*}" -c "
SELECT u.username, u.email, u.status,
       u.failed_login_count AS sai, u.locked_until AS khoa_den,
       u.must_change_password AS bat_doi_mk,
       left(u.password_hash, 24) || '…' AS ma_bam,
       u.updated_at,
       coalesce(string_agg(r.role_code, ', ' ORDER BY r.role_code)
         FILTER (WHERE r.valid_from <= now() AND (r.valid_to IS NULL OR r.valid_to > now())), '-') AS vai_tro
FROM users u LEFT JOIN user_roles r ON r.user_id = u.id
GROUP BY u.id ORDER BY u.created_at;"


3. Kiểm tra mật khẩu trong .env có khớp mã băm của từng tài khoản không


npx tsx -e '
import("./lib/auth/password.ts").then(async (m) => {
  const pg = (await import("pg")).default;
  const c = new pg.Client({ connectionString: process.env.DATABASE_URL.split("?")[0] });
  await c.connect();
  const { rows } = await c.query("SELECT username, password_hash FROM users ORDER BY created_at");
  for (const u of rows) console.log(u.username.padEnd(16), (await m.verifyPassword(process.env.SEED_PASSWORD, u.password_hash)) ? "KHỚP" : "không khớp");
  await c.end();
});'

Lệnh dùng từ giờ, chỉ tắt cờ và không đụng bộ đếm hay khoá:


cd "/Users/vuthuhuyen/SoD /web"
set -a; . ./.env; set +a
H=$(npx tsx -e 'import("./lib/auth/password.ts").then(async m => console.log(await m.hashPassword(process.env.SEED_PASSWORD)))')
psql "${DATABASE_URL%%\?*}" -v h="$H" -c "UPDATE users SET password_hash=:'h', must_change_password=false WHERE username IN ('an.nguyen','oanh.mai','binh.tran','chi.le','dung.pham','son.ho','giang.hoang','ha.vu','phong.ta','khoa.do','quan.ly','lan.bui','minh.ngo','nam.dang','admin');"