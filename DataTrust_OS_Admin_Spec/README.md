# DataTrust OS — Admin Specification Pack

Bộ đặc tả UI/UX cho **Admin**, chia từ `Pasted markdown(20261007-031107).md` theo từng chức năng để coding agent chỉ cần đọc phần liên quan.

## Ràng buộc giao diện hiện tại phải giữ

- Giữ nguyên visual identity hiện tại: palette, typography, spacing, radius, border và shadow; không redesign sang một theme mới.
- Giữ UI dual-pane hiện tại: **AI Chat cố định bên trái** như một companion và **workspace nghiệp vụ bên phải** triển khai các màn hình theo spec.
- AI Chat giữ context theo dataset/run/finding đang mở, hỗ trợ giải thích và điều hướng nhưng không thay thế thao tác hay quyết định của Admin/Auditor.
- Trên desktop, hai pane có vùng cuộn độc lập. Trên màn hình nhỏ, AI Chat chuyển thành pane/drawer có thể mở đóng để không che workspace.

## Cách sử dụng với coding agent

1. Đọc `01-product-scope.md`, `02-design-system-and-interactions.md` và `03-app-shell-and-navigation.md` để nắm phạm vi, UX và điều hướng.
2. Đọc `16-data-models.md`, `17-components-and-state.md` và `18-api-and-realtime.md` trước khi xây service layer và state.
3. Đọc file chức năng đang triển khai; mở các tài liệu liên quan khi cần.
4. Đối chiếu `19-acceptance-and-delivery.md` khi bàn giao.

Ví dụ giao việc:

> Đọc README và các phần dùng chung. Triển khai màn hình Quarantine theo `11-quarantine.md`, kết nối data model và typed service layer theo `16-data-models.md` và `18-api-and-realtime.md`. Giữ nguyên giới hạn AI/HITL; nếu backend chưa có, dùng typed mock service theo spec. Đối chiếu acceptance mục I trong `19-acceptance-and-delivery.md`.

## Danh mục tài liệu

| File | Nội dung | Phần spec gốc |
| --- | --- | --- |
| [01-product-scope.md](01-product-scope.md) | Phạm vi sản phẩm và ranh giới trách nhiệm | 0, 30 |
| [02-design-system-and-interactions.md](02-design-system-and-interactions.md) | Nguyên tắc UX, tương tác và trạng thái hiển thị | 1, 20, 21, 22 |
| [03-app-shell-and-navigation.md](03-app-shell-and-navigation.md) | App shell, routes và user journeys | 2, 3, 28 |
| [04-home-and-dataset-selection.md](04-home-and-dataset-selection.md) | Trang chủ và chọn dataset | 4 |
| [05-rules-and-policy.md](05-rules-and-policy.md) | Xem rules áp dụng và tra cứu policy | 5, 18 |
| [06-run-creation-and-monitoring.md](06-run-creation-and-monitoring.md) | Tạo run và theo dõi pipeline | 6, 7 |
| [07-run-results.md](07-run-results.md) | Dashboard kết quả run | 8 |
| [08-findings.md](08-findings.md) | Danh sách và chi tiết Finding | 9, 10 |
| [09-ai-analysis-and-hitl.md](09-ai-analysis-and-hitl.md) | AI Explanation, RCA và phê duyệt remediation | 11 |
| [10-data-lineage.md](10-data-lineage.md) | Đồ thị truy vết dữ liệu | 12 |
| [11-quarantine.md](11-quarantine.md) | Danh sách và chi tiết record cách ly | 13, 14 |
| [12-audit-evidence.md](12-audit-evidence.md) | Evidence và kiểm tra tính toàn vẹn | 15 |
| [13-compliance-dashboard.md](13-compliance-dashboard.md) | Dashboard tổng hợp | 16 |
| [14-access-control.md](14-access-control.md) | Giám sát truy cập thời gian thực | 17 |
| [15-run-history.md](15-run-history.md) | Lịch sử audit | 19 |
| [16-data-models.md](16-data-models.md) | Data model TypeScript tối thiểu | 23 |
| [17-components-and-state.md](17-components-and-state.md) | Component architecture và state management | 24, 25 |
| [18-api-and-realtime.md](18-api-and-realtime.md) | API boundaries và realtime behavior | 26, 27 |
| [19-acceptance-and-delivery.md](19-acceptance-and-delivery.md) | Acceptance criteria, ưu tiên và Definition of Done | 29, 31, 32 |

## Quan hệ giữa các chức năng

- Chọn dataset → xem rules đang áp dụng → tạo run → monitoring → results.
- Results → Finding → AI analysis/HITL, Rule/Policy, Lineage, Evidence hoặc Quarantine.
- Run History mở lại monitoring/results của run được chọn.
- Dashboard và Access Control là các màn hình tổng hợp/giám sát riêng.
- Khi chuyển màn hình, giữ context dataset/run/finding theo các định danh trong spec; không tự đoán context từ tên hiển thị.

## Các ranh giới phải giữ

- AI chỉ Explain, RCA và đề xuất remediation/treatment; không sinh/đề xuất rule, policy hay compliance test case.
- Rule Engine thực hiện evaluation; Airflow điều phối execution; Admin quyết định tại bước HITL.
- Source database chỉ đọc; evidence không được sửa/xóa.
- Approval không đồng nghĩa execution đã thành công.

## Những điểm bản gốc chưa thống nhất

Việc chia file giữ nguyên nội dung nghiệp vụ, ví dụ, data model và API; các mục dưới đây là ghi chú bàn giao, không phải bổ sung chức năng.

1. **Rules sau khi chọn dataset chỉ để xem:** UI hiển thị các rule đang áp dụng cho dataset để Admin/Auditor biết phạm vi kiểm tra. Không có chọn/bỏ chọn, approve/reject hay chỉnh sửa rule trước run.
2. **Pending execution:** AI/HITL mô tả `Approved → Pending execution`, nhưng enum remediation tối thiểu chưa có giá trị này. Cần thống nhất mapping với backend; không hiển thị Completed ngay sau approval.
3. **Quarantine actions:** spec có Đánh dấu đã xem và Export, nhưng API mới liệt kê GET cho quarantine. Chỉ kích hoạt thao tác có contract backend, không giả lập thành công.
4. **Data model tối thiểu:** model chưa mô tả đầy đủ payload cho lineage graph, evidence, access metrics, pipeline steps và mọi metadata được minh họa trên UI. Các model hiện có là nền tảng, chưa phải contract backend đầy đủ.
5. **Lineage qua Quarantine tới Silver:** sơ đồ gốc minh họa đường đi này. Không suy ra record tự được release; remediation phải qua HITL và trạng thái execution thực tế.
6. **Giá trị minh họa:** policy/version, record count, confidence và thời gian trong spec là ví dụ hiển thị. Không coi đó là kiểm chứng pháp lý, kết quả audit hay số liệu realtime thực tế.
7. **Phân quyền Admin vs Auditor (Viewer):** Hệ thống tích hợp Role Switcher tại Topbar hỗ trợ chuyển đổi giữa Admin (`Nguyễn Quốc Bảo`) và Auditor (`Trần Minh Hoàng`). Auditor hoạt động ở chế độ Viewer (chỉ đọc): có quyền xem toàn bộ bằng chứng, kết quả kiểm toán và Lineage, nhưng không có quyền khởi chạy pipeline (`startPipelineRun`) hay thay đổi/duyệt rule. Nút chính tại Trang chủ cho Auditor là `[ Xem kết quả kiểm toán ]`.
8. **Tinh gọn giao diện theo feedback người dùng:** Đã bỏ hiển thị thông tin số lượng cột (columns count) tại Quick Access chips, Dataset Selector modal và Dataset Selected state card (chỉ giữ 3 chỉ số PII trọng yếu: personal data fields, direct identifiers, contextual fields). Đã bỏ ô tìm kiếm dataset tại thẻ chào mừng Initial State. AI Chat companion hiển thị đầy đủ danh mục cả 8 bộ dữ liệu PostgreSQL thực tế trong quick actions.

## Thứ tự triển khai

- **P0:** AppShell, Sidebar, Topbar, dual-pane AI Chat + workspace, routing, giữ design system hiện tại, dataset selector.
- **P1:** Run creation, monitoring, results, findings.
- **P2:** AI explanation, HITL remediation, lineage, quarantine, evidence.
- **P3:** Access Control, dashboard, run history, export khi backend hỗ trợ.

## Tính đầy đủ

19 file chuyên biệt chứa đủ 33 phần được đánh số từ 0 đến 32 của spec nguồn; mỗi phần được phân vào đúng một file. Số mục gốc được giữ để dễ đối chiếu. README bổ sung hướng dẫn đọc, liên kết và các điểm cần thống nhất, không thay thế nội dung nguồn.
