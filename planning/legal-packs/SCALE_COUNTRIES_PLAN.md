# Kế hoạch scale Lane B: từ vùng (VN / EU / US) xuống từng quốc gia

> **Cặp với:** [`LEGAL_TO_RULE.md`](LEGAL_TO_RULE.md) (đường ống B1–B6, tem, hiệu lực) · [`../PRODUCT_PHASE_2.md`](../phase%202%20/PRODUCT_PHASE_2.md) §4.2.1 (toán tử hợp pack) · [`../ZONE_LEGAL_MAPPING.md`](../ZONE_LEGAL_MAPPING.md) (`zone_manifest`)
> **Trạng thái:** kế hoạch. Chưa có runtime. Tên luật các nước ở §6 **cần pháp chế xác minh**.

---

## 1. Mục tiêu và điều kiện bắt đầu

**Mục tiêu:** thêm một quốc gia (hoặc bang / tỉnh) mới **không sửa engine, không sửa pack của nước khác**. Chỉ thêm file cấu hình + test của nước đó.

**Điều kiện bắt đầu scale (gate G0).** Nếu chưa đạt thì chưa scale:

| # | Tiêu chí | Kiểm bằng |
|---|---|---|
| G0.1 | Engine + loader chạy cho VN, EU | `uv run pytest tests/compliance/` pass toàn bộ bảng §4.8 LEGAL_TO_RULE |
| G0.2 | Hiệu lực theo `as_of` chạy được | Test §3.7 pass |
| G0.3 | `vocab.yaml` đã được pháp chế duyệt | Có `reviewed_by` + `version` |
| G0.4 | Số dòng vào quarantine khớp manifest | S1 = 345, S2 = 30 |

Lý do: nếu mô hình còn sai mà đã nhân lên 10 nước thì phải sửa 10 lần.

---

## 2. Vấn đề khi đi xuống cấp quốc gia

Hiện tại `subject_zone ∈ {VN, EU, US}` và mỗi zone có một pack đầy đủ. Khi xuống cấp nước sẽ gặp 3 vấn đề:

1. **EU không phải một nước.** GDPR áp chung, nhưng mỗi nước thành viên có luật bổ sung riêng (tuổi đồng ý, dữ liệu nhân viên, định danh quốc gia…). Nếu mỗi nước EU giữ một pack đầy đủ thì GDPR bị **chép ra 27 bản**. Khi EDPB thay đổi hướng dẫn thì phải sửa 27 chỗ. Đây chính là cái bẫy của cách "đặt rule theo tên cột", chỉ khác là lặp ở cấp pack.
2. **Mỹ gần như không có luật liên bang chung.** Luật nằm ở cấp **bang** (California, Virginia, Colorado…). `US` không đủ để chọn pack.
3. **Chuyển dữ liệu xuyên biên giới tăng theo N².** Viết rule cho từng cặp nước (VN→DE, VN→US-CA, DE→IN…) thì 10 nước sẽ ra khoảng 90 cặp.

---

## 3. Thiết kế: pháp lý theo tầng

### 3.1 Mã pháp lý (jurisdiction) theo ISO

Dùng `subject_jurisdiction` thay cho `subject_zone`, lấy mã theo chuẩn:

| Tầng | Chuẩn mã | Ví dụ |
|---|---|---|
| Khối / vùng | tự đặt | `EU` |
| Quốc gia | ISO 3166-1 alpha-2 | `VN`, `DE`, `FR`, `ID`, `IN` |
| Bang / tỉnh | ISO 3166-2 | `US-CA`, `CA-QC` |

`zone_manifest` hiện đã có dạng `US-MI`, nên đổi sang cách này là mở rộng, không phải viết lại. Giữ `subject_zone` làm alias trong một phiên bản để không gãy dữ liệu cũ.

### 3.2 Chuỗi pack: pack vùng đầy đủ + pack nước là lớp phủ

Mỗi mã pháp lý tự suy ra **chuỗi pack** cần bật:

```yaml
# legal-packs/jurisdictions.yaml
VN:    { chain: [pack_vn],               tz: Asia/Ho_Chi_Minh }
EU:    { chain: [pack_eu],               tz: Europe/Brussels }
DE:    { chain: [pack_eu, pack_de],      tz: Europe/Berlin }
FR:    { chain: [pack_eu, pack_fr],      tz: Europe/Paris }
US-CA: { chain: [pack_us_ca],            tz: America/Los_Angeles }
CA-QC: { chain: [pack_ca, pack_ca_qc],   tz: America/Toronto }
```

- **Pack vùng** (`pack_eu`) vẫn là pack **đầy đủ**, như hiện nay.
- **Pack nước** (`pack_de`) chỉ chứa **phần khác biệt** so với pack vùng: control thêm, `upgrade` thêm, retention ngắn hơn.
- Engine bật **mọi pack trong chuỗi cùng lúc** và gộp bằng **toán tử §4.2.1 đã có**: cấm lấy hợp, điều kiện cho phép lấy giao, retention lấy min. **Không cần toán tử mới.**

> ⚠ **Cần chốt (D1):** ràng buộc hiện tại là *"mỗi zone một pack đầy đủ, không lõi chung"*. Thiết kế này **giữ** nó ở cấp vùng, và thêm pack lớp phủ ở cấp nước. Đây không phải "lõi chung + signature": pack nước không kế thừa hay ghi đè gì, nó chỉ là một pack nữa được bật song song. Vì toán tử gộp chỉ **siết thêm** (cấm hợp, cho phép giao), pack nước **không thể nới** luật vùng. Nếu luật nước thật sự nới hơn GDPR ở điểm nào đó thì ghi thành Finding `finding_only` để pháp chế xem, không tự nới.

### 3.3 Chuyển xuyên biên giới: bảng, không phải rule theo cặp

Thêm `dest_jurisdiction` cho mỗi `dest_id`, và **một** bảng cơ chế chuyển:

```yaml
# legal-packs/transfer_mechanisms.yaml
EU:                     # nguồn
  adequacy: [JP, KR, GB, CH, CA, US-DPF]      # ⚠ cần xác minh danh sách hiện hành
  default_require: [scc, tia]
VN:
  default_require: [tia]                       # PDP-020
  localization: []                             # ⚠ cần xác minh
```

Mỗi pack chỉ cần **một** control chuyển dữ liệu, dạng: *"NẾU `dest_jurisdiction` không có trong adequacy của nguồn THÌ PHẢI có đủ `default_require`"*. Thêm nước mới = thêm 1 dòng vào bảng, không sinh thêm cặp rule nào.

### 3.4 Tem (vocab) khi thêm nước

Nguyên tắc: **tem dùng chung toàn cầu, luật theo từng nước.** Đại đa số nước mới **không cần tem mới**, vì khác biệt nằm ở luật (pack), không nằm ở loại dữ liệu.

Chỉ thêm tem khi luật một nước **phân biệt được một loại dữ liệu mà bộ tem hiện tại không phân biệt được** (ví dụ luật tách riêng sinh trắc học trong khi `data_category` chưa có `biometric`). Quy trình:

1. Mở đề xuất đổi vocab, có trích điều luật cần tem đó.
2. Tăng `vocab.version`.
3. Tem mới mặc định là `unclear` ở **mọi** pack cho tới khi từng pack viết rule cho nó. Mặc định an toàn là **chặn**, không lọt.
4. Gắn lại tem cho các cột liên quan trong `column_tags.yaml`.

Loader từ chối pack dùng tem không có trong vocab (như §B4 hiện tại).

---

## 4. Bộ onboarding cho một nước (đơn vị lặp lại)

Mỗi nước đi qua cùng một quy trình, có sản phẩm cụ thể ở từng bước:

| Bước | Việc | Sản phẩm | Ai |
|---|---|---|---|
| O1 | Xác định tầng (vùng / nước / bang) và chuỗi pack | 1 dòng trong `jurisdictions.yaml` | Pháp chế |
| O2 | Điền ma trận luật theo **template Excel chuẩn** (một header cho mọi nước, không còn map header theo từng nước như B1 hiện tại) | `<cc>/<cc>_matrix.xlsx` | Pháp chế nước đó |
| O3 | Sinh CSV + phân `scope` (data / event / evidence) | `pack_<cc>_controls.csv` | Script B1 + pháp chế duyệt |
| O4 | Dịch control `data` sang NẾU…THÌ, chỉ ghi phần **khác** pack vùng | `pack_<cc>.yaml` | Nhóm data viết, pháp chế ký |
| O5 | Cơ chế chuyển dữ liệu ra ngoài và yêu cầu lưu trữ trong nước | Dòng trong `transfer_mechanisms.yaml` | Pháp chế |
| O6 | Tem mới? (thường là không, xem §3.4) | Đề xuất vocab nếu cần | Data + pháp chế |
| O7 | Test: mỗi control `data` có ≥1 case pass và ≥1 case fail, cộng 1 case chuyển dữ liệu ra ngoài | `tests/compliance/<cc>/` | Dev |
| O8 | Chạy `dry_run` trên dữ liệu thật ≥ 2 tuần, pháp chế xem Finding | Báo cáo dry-run | Data + pháp chế |
| O9 | Bật `active` | `status: active` + `effective_from` | Pháp chế ký |

**Xong một nước (DoD):** loader 0 lỗi · test O7 pass · dry-run không có Finding nào pháp chế đánh `FALSE_POSITIVE` mà chưa xử lý · có người chịu trách nhiệm theo dõi thay đổi luật nước đó.

**Ước lượng công sức (tương đối):**

| Loại | Ví dụ | Cỡ | Vì sao |
|---|---|---|---|
| Nước trong khối đã có pack vùng | DE, FR, NL | **S** | Chỉ viết phần khác biệt, phần lớn control là `evidence` |
| Bang / tỉnh có pack quốc gia hoặc liên bang mỏng | US-CA, CA-QC | **M** | Pack gần như đầy đủ, nhưng mô hình dữ liệu tương tự GDPR |
| Nước / khối hoàn toàn mới | ID, IN, PH | **L** | Pack đầy đủ từ đầu, có thể cần tem mới, cần pháp chế bản địa |

---

## 5. Thay đổi kỹ thuật (làm một lần, trước đợt 1)

| # | Việc | File / module |
|---|---|---|
| K1 | `subject_zone` → `subject_jurisdiction` (giữ alias), `dest_id` → thêm `dest_jurisdiction` | `zone_manifest`, `vocab.yaml` |
| K2 | `jurisdictions.yaml` + loader: kiểm chuỗi pack tồn tại, không vòng lặp, múi giờ hợp lệ | loader |
| K3 | Engine: `evaluate` bật cả chuỗi pack, gộp bằng §4.2.1 | engine |
| K4 | `transfer_mechanisms.yaml` + control chuyển dữ liệu dùng chung dạng | engine + pack |
| K5 | Finding thêm `jurisdiction`, `pack_chain` | Finding + bảng `quarantine` |
| K6 | `packs.csv` thêm cột `level` (region / country / subnational), `parent`, `owner` | `packs.csv` |
| K7 | Template Excel chuẩn + script B1 đọc một header duy nhất | `legal-packs/_template/` |
| K8 | CI: pack mới không có test thì fail | CI |

Mã pháp lý chưa có trong `jurisdictions.yaml` thì xử lý giống `US` hiện nay: `NO_ACTIVE_PACK`, `finding_only`, **không** mượn pack nước khác (§4.6 LEGAL_TO_RULE).

---

## 6. Chọn nước và chia đợt

**Tiêu chí ưu tiên** (chấm 1–3, cộng lại):

| Tiêu chí | Câu hỏi |
|---|---|
| Có dữ liệu chủ thể thật | Đã / sắp có xe, tài xế, khách ở nước đó chưa? |
| Khối lượng | Số VIN, số chuyến |
| Rủi ro pháp lý | Mức phạt, yêu cầu lưu trữ trong nước, cơ quan quản lý có hay thanh tra không |
| Chi phí | S / M / L ở §4 |
| Có người duyệt | Có pháp chế / luật sư địa phương ký được không |

**Đề xuất đợt** (dựa trên các thị trường VinFast công bố; **cần đối chiếu với nơi thật sự có dữ liệu**):

| Đợt | Nước | Luật chính (⚠ cần xác minh) | Cỡ | Mục đích |
|---|---|---|---|---|
| 0 | VN, EU | Luật BVDLCN 2025 / NĐ 13 hoặc 356; GDPR | — | Vòng 1 hiện tại, gate G0 |
| 1 | DE, FR, NL | GDPR + BDSG; Loi Informatique et Libertés; UAVG | S × 3 | Kiểm mô hình lớp phủ với chi phí thấp |
| 1 | US-CA | CCPA / CPRA | M | Kiểm tầng bang, thay stub US |
| 2 | CA + CA-QC | PIPEDA; Law 25 (Québec) | M | Liên bang + tỉnh cùng lúc |
| 3 | ID, PH, IN | UU PDP 27/2022; Data Privacy Act 2012; DPDP Act 2023 | L × 3 | Khối mới, có thể cần tem mới và yêu cầu lưu trữ trong nước |

Đợt 1 cố ý chọn nước **rẻ** (lớp phủ EU) cộng **một** tầng bang để thử cả hai kiểu chuỗi pack trước khi làm nước khó.

---

## 7. Lộ trình và gate

| Pha | Nội dung | Gate ra |
|---|---|---|
| P0 | Hoàn thành vòng 1 (VN, EU) | G0 (§1) |
| P1 | K1–K8 | Test VN / EU cũ vẫn pass nguyên; test chuỗi `[pack_eu, pack_de]` với pack_de rỗng cho kết quả **y hệt** pack_eu |
| P2 | Đợt 1: DE, FR, NL, US-CA qua O1–O9 | DoD §4 cho từng nước; thời gian onboard mỗi nước S ≤ mục tiêu đặt ra sau nước đầu tiên |
| P3 | Rút kinh nghiệm: sửa template, sửa quy trình | Nước thứ 2 trở đi không phải sửa engine |
| P4 | Đợt 2, đợt 3 | DoD §4 |

**Chỉ số theo dõi scale:**
- Số dòng code engine phải sửa khi thêm một nước. Mục tiêu: **0**.
- Số file thay đổi khi thêm một nước. Mục tiêu: chỉ file của nước đó + 1 dòng trong `jurisdictions.yaml` / `transfer_mechanisms.yaml`.
- Số tem mới phát sinh cho mỗi nước. Nếu con số này cao thì vocab đang bị thiết kế theo nước, cần xem lại.
- Tỉ lệ `FALSE_POSITIVE` trong dry-run.

---

## 8. Vận hành và quản trị

| Việc | Cách làm |
|---|---|
| Người chịu trách nhiệm | Mỗi mã pháp lý có một `owner` (cột K6), là người ký rule và theo dõi luật |
| Theo dõi thay đổi luật | Rà soát theo quý cho mỗi mã pháp lý; thay đổi đi qua vòng đời §3.7 (draft → scheduled → active), không sửa đè |
| Luật sắp có hiệu lực | Chạy `dry_run` với `as_of` là ngày tương lai trước khi bật |
| Xung đột giữa hai nước | Toán tử §4.2.1 tự chọn phía chặt hơn; nếu cả hai **bắt buộc** hai việc mâu thuẫn nhau (ví dụ một nước buộc giữ, nước kia buộc xoá) thì `quarantine_hitl` gửi pháp chế, không tự quyết |

---

## 9. Rủi ro

| Rủi ro | Hậu quả | Giảm thiểu |
|---|---|---|
| Scale trước khi qua G0 | Lỗi mô hình bị nhân lên N nước | Gate G0 bắt buộc |
| Pack nước chép lại cả pack vùng | Quay lại vấn đề sửa N chỗ | Review O4: pack nước chỉ chứa phần khác biệt |
| Vocab phình theo từng nước | Mất tính "ngôn ngữ chung" | Quy trình §3.4, theo dõi chỉ số tem mới |
| Không có pháp chế địa phương | Dịch sai luật, không ai ký | Tiêu chí "Có người duyệt" ở §6; không có thì không vào đợt |
| Yêu cầu lưu trữ trong nước | Không chỉ là rule: phải có hạ tầng lưu trữ tại nước đó | Đánh dấu ở O5; đây là quyết định hạ tầng, tách khỏi Lane B |
| Chủ thể thuộc nhiều nước (tài xế EU làm việc ở VN) | Chọn sai chuỗi pack | Cho phép `subject_jurisdiction` là **danh sách**; bật hợp các chuỗi, gộp bằng §4.2.1 |

---

## 10. Cần chốt

| # | Câu hỏi | Ảnh hưởng |
|---|---|---|
| D1 | Chấp nhận mô hình *pack vùng đầy đủ + pack nước lớp phủ* (§3.2)? | Toàn bộ thiết kế |
| D2 | Danh sách nước **thật sự có dữ liệu chủ thể** trong 12 tháng tới | Thứ tự đợt §6 |
| D3 | Có pháp chế / luật sư địa phương cho từng nước đợt 1 không? | Có vào đợt được hay không |
| D4 | Có chấp nhận `subject_jurisdiction` là danh sách không? | K1, rủi ro nhiều nước |
| D5 | Yêu cầu lưu trữ trong nước xử lý ở Lane B (chỉ chặn) hay cần dự án hạ tầng riêng? | Phạm vi |
