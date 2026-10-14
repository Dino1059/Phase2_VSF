# Lane B: áp dụng luật 3 zone và kế hoạch tiêm lỗi

> **Trạng thái:** bản nháp, chờ chốt các mục ở §5.A. Chưa tiêm gì vào dữ liệu.
> **Liên quan:** [LEGAL_TO_RULE.md](LEGAL_TO_RULE.md) · [ZONE_LEGAL_MAPPING.md](../ZONE_LEGAL_MAPPING.md) · [packs.csv](packs.csv) · bộ dữ liệu [`data_new/vingroup_pii_faulty_testset_3zone/`](../../../data_new/vingroup_pii_faulty_testset_3zone/GHI_CHU_LOI.md)
> **Bộ luật nguồn:** [`vn/VN_Compliance_Matrix.csv`](vn/VN_Compliance_Matrix.csv) (24 kịch bản, NĐ 356/2025) · [`eu/EU_rule .csv`](eu/EU_rule%20.csv) (8 điều GDPR) · [`us/US_rule.csv`](us/US_rule.csv) (10 quy tắc CCPA/CPRA)

---

## 1. Không phải quy tắc luật nào cũng thành bộ lọc tự động

Theo [LEGAL_TO_RULE.md §2](LEGAL_TO_RULE.md), mỗi quy tắc thuộc **1 trong 3 loại**, và mỗi loại được kiểm ở một chỗ khác nhau:

| Loại | Kiểm ở đâu | Ví dụ |
|---|---|---|
| **Dữ liệu** (`data`) | **DataTrust tự lọc** trên cột / dòng / đích gửi → chặn hoặc cách ly | Toạ độ thô gửi ra nước ngoài, quá hạn lưu |
| **Sự kiện** (`event`) | **Đồng hồ hạn xử lý** trên bảng yêu cầu hoặc sự cố, không xét từng dòng dữ liệu | Yêu cầu xoá phải xong trong 1 tháng, báo sự cố trong 72 giờ |
| **Bằng chứng** (`evidence`) | **Checklist** trạng thái sẵn sàng của từng quy tắc; giấy tờ có thật hay không ghi trong **sổ đăng ký giấy tờ** (thiết kế chi tiết nằm ở phần chuyển dữ liệu đã hoãn, §8), bộ lọc chỉ đọc cờ | Có hồ sơ đánh giá tác động chưa, có chỉ định người phụ trách bảo vệ dữ liệu chưa |

SoD là hệ thống tách quyền mô tả trong `Bản sao SoD/doc/BUILD_PLAN_TICH_HOP.md`. **SoD thật sự có:** phiếu cấp / thu hồi quyền, phiếu duyệt rule theo lô, phiếu xuất PII (nội dung chỉ mô tả: dataset, cột, số dòng, đích, mục đích, mã băm), nhật ký truy cập `data_access_log`, SLA nhắc và leo thang. **SoD không có** chỗ chứa SCC, đánh giá rủi ro chuyển giao, hợp đồng xử lý, DPIA, thông báo cho tài xế, hồ sơ chỉ định DPO. Các giấy tờ này nằm ở checklist và sổ đăng ký, không phải ở SoD.

**Chỉ loại "dữ liệu" mới tiêm vào bộ dữ liệu.** Loại "sự kiện" tiêm vào bảng yêu cầu hoặc sự cố. Loại "bằng chứng" kiểm bằng checklist và cờ trong sổ đăng ký giấy tờ.

---

## 2. Bổ sung luật EU: áp dụng thế nào

### 2.1 Bộ luật EU hiện tại thiếu phần chuyển dữ liệu ra nước ngoài

File `eu/EU_rule .csv` chỉ có 8 điều: GDPR-005, 006, 009, 022, 025, 030, 032, 088. **Không có điều nào về chuyển dữ liệu ra ngoài EU** (GDPR Chương V, Điều 44–49). Vì vậy tình huống "dữ liệu EU gửi sang máy chủ nước ngoài" hiện **không có mã luật để đối chiếu**.

| Zone | Gửi toạ độ thô sang máy chủ ở Mỹ | Luật đối chiếu |
|---|---|---|
| VN | Lỗi | **PDP-020** (Đ18 K4: phải nộp hồ sơ đánh giá cho Cục A05) |
| US | Không phải lỗi chuyển ra nước ngoài | Chỉ xét **US-CCPA-05** (độ chính xác toạ độ và mục đích) |
| EU | Ngoài đời là lỗi nặng | **Chưa có** → cần thêm GDPR-044 |

### 2.2 Áp dụng 11 điều EU đề xuất bổ sung

| Mã | Loại | Trong bộ dữ liệu | Giấy tờ / đồng hồ nằm ở đâu |
|---|---|---|---|
| GDPR-003 (phạm vi, định nghĩa) | Tham chiếu, dùng để **gắn nhãn** | Gắn nhãn `vehicle_vin` là định danh gián tiếp của tài xế, tức dữ liệu cá nhân. Không phải bộ lọc, nhưng là điều kiện để các quy tắc khác chạy. | — |
| GDPR-010 (vi phạm giao thông, tiền án) | **Dữ liệu** | Thêm cột `vi_pham_giao_thong` cho tài xế EU. Hệ thống phải nhận diện nhóm đặc biệt và chặn khi không có căn cứ. | — |
| GDPR-044 (Điều 44–49, chuyển ra ngoài EU) | **Dữ liệu** | Đích ở ngoài EU, nước đó chưa được công nhận đủ mức bảo vệ, và chưa có hợp đồng mẫu kèm đánh giá rủi ro chuyển giao → chặn | Sổ đăng ký giấy tờ: `scc`, `tia` theo từng luồng (hoãn, xem §8) |
| GDPR-028 (hợp đồng với bên xử lý) | **Dữ liệu** + bằng chứng | Đích "chưa có hợp đồng xử lý" → chặn gửi | Sổ đăng ký giấy tờ: `processor_agreement` |
| GDPR-021 (quyền phản đối) | **Dữ liệu** + sự kiện | Cột `ngay_phan_doi` cho tài xế. Sau ngày đó, nếu căn cứ là "lợi ích hợp pháp" thì phải ngừng xử lý → chặn các dòng sau ngày phản đối. | — |
| GDPR-015 (quyền truy cập, sửa, xoá: Điều 15–20) | **Sự kiện** | Bảng mới `yeu_cau_quyen.csv` có ngày nhận và ngày xong. Quá 1 tháng → lỗi. | Bảng `yeu_cau_quyen.csv`. SoD chưa có loại phiếu này, chỉ có đồng hồ SLA chung |
| GDPR-033 (báo vi phạm 72 giờ) | **Sự kiện** | Bảng mới `su_co.csv` có giờ phát hiện và giờ báo. Quá 72 giờ → lỗi. | Bảng `su_co.csv`. SoD chưa có loại phiếu sự cố |
| GDPR-035 (đánh giá tác động) | **Bằng chứng** (có cổng chặn) | Hợp đồng dữ liệu có ô `ma_danh_gia_tac_dong`. Trống thì không cho xử lý. | Checklist + cờ `ma_danh_gia_tac_dong` trong sổ đăng ký giấy tờ |
| GDPR-013 (thông báo cho tài xế: Điều 12–14) | **Bằng chứng** | — | Checklist (đã có bản thông báo cho tài xế) |
| GDPR-024 (trách nhiệm giải trình) | **Bằng chứng** | — | Nhật ký duyệt và nhật ký truy cập của SoD là một phần bằng chứng |
| GDPR-037 (người phụ trách bảo vệ dữ liệu) | **Bằng chứng** | — | Checklist chỉ định DPO. SoD chỉ có vai trò DPO duyệt phiếu, không xác nhận việc chỉ định |

**Kết quả:** 11 điều, chỉ **4 điều lọc tự động trên dữ liệu được** (010, 044, 028, 021), 2 điều theo đồng hồ hạn xử lý (015, 033), còn lại là checklist bằng chứng.

> **Lưu ý quan trọng:** đề xuất GDPR-044 ghi "chuyển dữ liệu từ EU **về Việt Nam**". Nếu máy chủ DataTrust đặt ở VN, thì **mọi dữ liệu zone EU nạp vào hệ thống đều đã là chuyển ra ngoài EU**, không riêng việc gửi sang máy AI ở Mỹ. Cần chốt nơi đặt máy chủ (§5.A, mục 6).

---

## 3. Hai điểm cần đính chính

### 3.1 `packs.csv` trỏ tới file chưa tồn tại (không phải trỏ nhầm)

`packs.csv` là danh mục cho hệ thống biết mỗi zone dùng bộ luật nào và đọc từ file nào:

| Zone | `packs.csv` trỏ tới | File thật đang có |
|---|---|---|
| VN | `vn/pack_vn_controls.csv` (**chưa tồn tại**) | `vn/VN_Compliance_Matrix.csv` |
| EU | `eu/pack_eu_controls.csv` (**chưa tồn tại**) | `eu/EU_rule .csv` |
| US | `us/pack_us_controls.csv` (**chưa tồn tại**) | `us/US_rule.csv` |

Đây là **thiết kế có chủ đích** ([LEGAL_TO_RULE.md](LEGAL_TO_RULE.md) dòng 13 và bước B1):
- 3 file hiện có là **bảng gốc do người soạn**, mỗi file một định dạng. VN có dòng tiêu đề và dòng tổng hợp, không có cột Control ID. EU có ô xuống dòng. US có bảng phụ về thời hạn ở cuối.
- Bước **B1** sẽ chuẩn hoá chúng thành `pack_<zone>_controls.csv` theo cùng một định dạng để máy đọc. **B1 chưa làm**, nên `status = empty_csv`.
- Hiện **chưa có code nào trong `src/` đọc `packs.csv`**.
- Lệch tài liệu: LEGAL_TO_RULE.md dòng 77 ghi "US giữ stub (cắt vòng 1)", nhưng `US_rule.csv` đã đủ 10 quy tắc.

### 3.2 Hạn lưu "365 ngày" là giả định, chưa có trong luật

| Nguồn | Nói gì về hạn lưu |
|---|---|
| EU GDPR-005, cột ghi chú | "Cần định nghĩa rõ retention period… trước khi tự động hoá kiểm tra" |
| US-CCPA-07 | "khi đạt ngưỡng lưu trữ quy định trong chính sách", không nêu số |
| Bảng mốc thời gian của US | Chỉ có 12 tháng (phạm vi tra cứu) và 24 tháng (lưu nhật ký yêu cầu), không phải hạn lưu telemetry |
| LEGAL_TO_RULE.md §7 "Cần chốt" | "Số ngày retention cho từng `purpose_id`": chưa chốt |

---

## 4. Các lỗi tiêm có thực tế không

| Lỗi | Thực tế? | Căn cứ |
|---|---|---|
| Chuyển dữ liệu tài xế EU ra ngoài EU khi chưa có cơ chế hợp lệ (GDPR-044) | **Rất thực tế** | Uber bị cơ quan bảo vệ dữ liệu Hà Lan phạt 290 triệu euro (2024) vì chuyển dữ liệu tài xế châu Âu sang Mỹ |
| Bỏ qua người đã từ chối chia sẻ (US-CCPA-04) | **Rất thực tế** | Sephora bị phạt 1,2 triệu USD (2022) vì bỏ qua tín hiệu từ chối GPC |
| Dùng toạ độ chính xác ngoài mục đích (US-CCPA-05) | **Rất thực tế** | Vụ GM/OnStar bị FTC xử lý vì chia sẻ dữ liệu vị trí lái xe (2025) |
| Quá hạn lưu; rút đồng ý mà vẫn xử lý; xoá chậm | **Thực tế**, rất phổ biến | Nhóm vi phạm hay gặp nhất |
| Cột lạ chứa email hoặc số điện thoại (S1); thông tin cá nhân trong câu chữ (S2) | **Thực tế** | Cột phát sinh ngoài danh mục là chuyện thường gặp |
| Điểm mệt mỏi suy ra sức khoẻ (GDPR-009) | Có thể xảy ra, ít gặp hơn | Áp dụng khi có giám sát tài xế |
| Luồng không mã hoá | Thực tế nhưng thuộc **hạ tầng** | Nên đưa sang phần bảo mật hoặc checklist, không đưa vào bộ dữ liệu |

**Giới hạn khi báo cáo:** các tình huống giống thực tế, nhưng **dữ liệu là dựng** (ngày rút đồng ý, cờ từ chối… do nhóm tự đặt). Bộ này chứng minh hệ thống **xử lý đúng logic luật**, chưa chứng minh hệ thống **tìm ra vi phạm trên dữ liệu thật**.

---

## 5. Việc cần xử lý để hoàn chỉnh bảng lỗi tiêm

### A. Cần chốt (người phụ trách hoặc pháp chế)

| # | Việc | Ảnh hưởng tới |
|---|---|---|
| 1 | Bổ sung luật EU theo §2.2 vào `EU_rule .csv`, đặc biệt **GDPR-044** | Lỗi chuyển dữ liệu của EU |
| 2 | Gắn **loại** (dữ liệu / sự kiện / bằng chứng) cho từng quy tắc của cả 3 zone. LEGAL_TO_RULE mới có bản sơ bộ cho VN. | Quyết định lỗi nào tiêm vào dữ liệu |
| 3 | **Hạn lưu theo từng mục đích, từng zone** | Lỗi quá hạn lưu (GDPR-005, US-CCPA-07, US-CCPA-02) |
| 4 | **Ngưỡng che toạ độ** cho VN và EU. US đã có: trên 1.850 feet ≈ 564 m, tức làm tròn còn 2 số lẻ. | Lỗi toạ độ thô |
| 5 | **Danh sách đích gửi**: nước; có hợp đồng xử lý / hợp đồng chuyển giao / hợp đồng mẫu / đánh giá rủi ro chưa | GDPR-028, 044, PDP-009, 020, US-CCPA-08 |
| 6 | ~~Máy chủ DataTrust đặt ở đâu~~ **Đã chốt: VN** (2026-10-13), hệ quả xem §8 | GDPR-044 áp cho toàn bộ dữ liệu EU lúc nạp |
| 7 | **Danh sách mục đích, cột tối thiểu cho mỗi mục đích** (GDPR-005), **căn cứ pháp lý mỗi cột** (GDPR-006) | Lỗi thu thập thừa, sai căn cứ |
| 8 | VN có coi **vị trí là dữ liệu nhạy cảm mặc định** không (LEGAL_TO_RULE §7) | PDP-002, 024 |
| 9 | **US có vào vòng 1 không** | Toàn bộ lỗi zone US |
| 10 | Thêm cột **Control ID** cho ma trận VN (EU, US đã có) | Mã luật trong đáp án |

#### Đã làm 2026-10-13: bản nháp, chờ duyệt

| # | Kết quả | Ở đâu |
|---|---|---|
| 1 | Thêm 11 điều GDPR (003, 010, 013, 015, 021, 024, 028, 033, 035, 037, 044). File EU từ 8 lên 19 quy tắc. | [`eu/EU_rule .csv`](eu/EU_rule%20.csv) |
| 2 | Gắn loại cho 53 quy tắc **thẳng vào 3 file luật**, thêm 3 cột cuối: loại kiểm, tiêm lỗi Lane B (`co` = tiêm vào dữ liệu hoặc cấu hình, `checklist` = kiểm bằng checklist và sổ đăng ký giấy tờ, `khong` = chưa tiêm được), lý do. VN lấy theo bản sơ bộ LEGAL_TO_RULE §2; EU và US là phán đoán mới. | cột cuối của 3 file luật |
| 3 | Hạn lưu: xem §6. **Không có số nào từ luật.** | [`retention_by_purpose.csv`](retention_by_purpose.csv) |
| 4 | Ngưỡng che toạ độ: xem §7. | [`geo_mask_thresholds.csv`](geo_mask_thresholds.csv) |
| 5 | **Hoãn** (2026-10-14): danh sách đích gửi và luồng chuyển dữ liệu. Máy chủ DataTrust ở **VN** (xác nhận 2026-10-13). | [`hoan/destinations.csv`](hoan/destinations.csv), [`hoan/flows.csv`](hoan/flows.csv) |

Kết quả phân loại (quy tắc ghép đếm ở cả hai loại): VN 7 dữ liệu, 5 sự kiện, 13 bằng chứng. EU 7 dữ liệu, 3 sự kiện, 10 bằng chứng, 1 tham chiếu. US 5 dữ liệu, 3 sự kiện, 4 bằng chứng.

### B. Cần thêm vào bộ dữ liệu khi tiêm

> Bản kế hoạch ban đầu. Đã làm theo cách **gộp vào file sẵn có**, xem §9.

Mọi thay đổi chỉ ở **cột mới hoặc file mới**, không đụng các cột Lane A đang dùng, nên đáp án Lane A (`fault_manifest.json`, 465 lỗi) giữ nguyên.

| Thêm gì | Phục vụ lỗi |
|---|---|
| `dim_customers.csv` + 4 cột: `thoi_diem_dong_y`, `ngay_rut_dong_y`, `ngay_yeu_cau_xoa`, `tu_choi_chia_se` | PDP-003, 005, 006, US-CCPA-04 |
| `dim_drivers.csv` + 2 cột: `ngay_phan_doi`, `vi_pham_giao_thong` (chỉ tài xế EU) | GDPR-021, GDPR-010 |
| File mới `yeu_cau_quyen.csv`: yêu cầu truy cập / sửa / xoá, ngày nhận, ngày xong | GDPR-015, PDP-004/005, US-CCPA-01/02 (đồng hồ 30 / 20 / 45 ngày) |
| File mới `su_co.csv`: giờ phát hiện, giờ báo | GDPR-033, PDP-014 (72 giờ) |
| File mới `telemetry_qua_han.csv`: chép vài ngày, lùi thời gian quá hạn | GDPR-005, US-CCPA-07, ngoại lệ giữ pháp lý US-CCPA-02 |
| File mới `telemetry_met_moi_eu.csv`: cột điểm mệt mỏi | GDPR-009 |
| `lane_b_contract.json`: mục đích, cột theo mục đích, căn cứ pháp lý, hạn lưu, giữ pháp lý, mã đánh giá tác động, danh sách đích (nước, các loại hợp đồng) | Mọi lỗi loại dữ liệu |
| `lane_b_runs.json`: mỗi lần chạy gồm dữ liệu nào, đích nào, mục đích gì, vai trò nào | Lỗi chuyển dữ liệu, vai trò, mục đích |
| `lane_b_fault_manifest.json`: đáp án, mỗi tình huống ghi mã luật, loại, kết quả đúng của Lane A và Lane B | Chấm điểm |

### C. Sổ đăng ký giấy tờ và checklist (không nằm trong bộ dữ liệu)

SoD **không** có chỗ chứa các giấy tờ này (xem §1). Chúng nằm ở sổ đăng ký giấy tờ do DPO hoặc pháp chế giữ (chưa làm, gắn với phần chuyển dữ liệu đã hoãn ở §8) và ở checklist trạng thái sẵn sàng của từng quy tắc. SoD đã có bộ test T01–T26 riêng của nó, không cần thêm tình huống từ bộ dữ liệu này. Nếu sau này muốn SoD quản lý cả các giấy tờ này thì phải mở rộng kế hoạch SoD (thêm loại phiếu đăng ký cơ sở chuyển giao); hiện chưa nằm trong kế hoạch.

---

## Phụ lục: bảng lỗi Lane B dự kiến (bản nháp trước khi bổ sung luật EU)

> **Cập nhật 2026-10-14:** các dòng B01–B04 (chuyển dữ liệu), B17–B18 (hạ tầng) và B20–B26 (chuyển dữ liệu) **hoãn, không tiêm**. 13 tình huống còn lại đã tiêm xong, xem §9.

Lỗi Lane B tính **theo tình huống** (đúng hoặc sai), không theo tỉ lệ dòng như Lane A. Mỗi lỗi có ít nhất một biến thể hoặc đối chứng để chứng minh hệ thống phân biệt được, không phải lúc nào cũng chặn.

| Mã | Zone | Luật | Lỗi | Cách tiêm | Số lượng |
|---|---|---|---|---|---|
| B01 | VN | PDP-020 | Gửi toạ độ thô ra máy chủ ở Mỹ khi chưa nộp hồ sơ cho Cục A05 | Cấu hình lần chạy: đích `llm_us` | 1 + 1 đối chứng |
| B02 | VN | PDP-009 | Chia sẻ cho đối tác chưa ký hợp đồng chuyển giao | Danh sách đích | 1 + 1 đối chứng |
| B03 | VN | PDP-012 | Đưa lên sàn dữ liệu khi chưa ẩn danh | Đích `san_du_lieu` | 1 |
| B04 | US | US-CCPA-08 | Gửi nhà cung cấp chưa ký hợp đồng xử lý | Danh sách đích | 1 + 1 đối chứng |
| B05 | US | US-CCPA-05 | Toạ độ dưới 564 m dùng phân tích hành vi khi chưa có đồng ý | Cấu hình: mục đích `phan_tich_hanh_vi` | 1 + 1 đối chứng (làm tròn 2 số lẻ) |
| B06 | VN | PDP-002 | Vai trò không được phép đọc dữ liệu vị trí | Cấu hình vai trò | 1 + 1 đối chứng |
| B07 | EU | GDPR-009 | Cột suy ra sức khoẻ không gắn nhãn đặc biệt | File `telemetry_met_moi_eu.csv` | 1 cột, 1.920 dòng |
| B08 | US | US-CCPA-07 | Quá hạn lưu chưa xoá | File `telemetry_qua_han.csv` | 96 dòng |
| B09 | US | US-CCPA-02 (ngoại lệ) | Quá hạn nhưng đang giữ pháp lý → **không được xoá** | Như B08, cờ giữ pháp lý | 96 dòng |
| B10 | EU | GDPR-005 | Quá hạn lưu | Như B08 | 96 dòng |
| B11 | VN | PDP-005 | Yêu cầu xoá quá 20 ngày mà dữ liệu vẫn còn | Cột `ngay_yeu_cau_xoa` | 10 khách |
| B12 | VN | PDP-003 | Rút đồng ý mà vẫn xử lý | Cột `ngay_rut_dong_y` | 10 khách |
| B13 | VN | PDP-006 | Không có bản ghi đồng ý | Cột `thoi_diem_dong_y` trống | 10 khách |
| B14 | US | US-CCPA-04 | Đã từ chối chia sẻ mà vẫn gửi bên quảng cáo | Cột `tu_choi_chia_se` + đích `quang_cao` | 10 khách |
| B15 | EU | GDPR-006 | Dữ liệu tài xế dùng căn cứ "đồng ý" hoặc để trống | Hợp đồng dữ liệu | 2 |
| B16 | EU | GDPR-005 | Thu thập thừa: luồng tính cước kèm email, số điện thoại | Dùng lại S1 (`customer_contact`) | khoảng 115 chuyến |
| B17 | EU | GDPR-032 | Luồng không mã hoá | Cấu hình (nên chuyển sang phần bảo mật, xem §4) | 1 + 1 đối chứng |
| B18 | VN | PDP-010 | Truyền dữ liệu nhạy cảm không mã hoá | Như B17 | 1 |
| B19 | — | (đối chứng) | F1 pin âm: Lane A phải bắt, **Lane B phải đạt** | Dùng lại 108 dòng F1 | 1 |
| B20 | EU | GDPR-044 | Dữ liệu EU từ trung tâm VN gửi tiếp sang máy AI ở Mỹ khi thiếu SCC và đánh giá rủi ro chuyển giao | Danh sách đích: `llm_us` (thiếu hồ sơ); đối chứng `llm_us_ok` | 1 + 1 đối chứng |

Khi bổ sung luật EU theo §2.2, thêm các tình huống cho GDPR-044, 028, 021, 010 (dữ liệu) và GDPR-015, 033 (sự kiện).

---

## 6. Lỗi "quá hạn": quy tắc nào, zone nào, bao lâu

"Quá hạn" gồm **3 loại khác nhau**, mỗi loại đo từ mốc khác nhau và chỉ loại 2, 3 có số trong luật.

| Loại | Zone | Quy tắc | Bao lâu | Số có trong luật? | Đo từ đâu đến đâu |
|---|---|---|---|---|---|
| **1. Hạn lưu** (tuổi dữ liệu) | EU | GDPR-005 | chưa có | **Không** (ghi chú file: "cần định nghĩa retention period") | `as_of` trừ ngày của dòng dữ liệu |
| | US | US-CCPA-07 | chưa có | **Không** ("ngưỡng quy định trong chính sách") | như trên |
| | VN | **không có quy tắc** | — | — | PDP-024 chỉ nói lưu *hồ sơ vi phạm* 5 năm, không phải telemetry |
| **2. Hạn xử lý yêu cầu của chủ thể** | VN | PDP-003 | 2 ngày làm việc xác nhận, 15 ngày ngừng xử lý | Có | ngày nhận yêu cầu → ngày xong (chưa xong thì tới `as_of`) |
| | VN | PDP-004 | 2 ngày làm việc, 10 ngày | Có | như trên |
| | VN | PDP-005 | 2 ngày làm việc, 20 ngày | Có | như trên |
| | EU | GDPR-015 | 1 tháng | Có (trong đề xuất bổ sung, cần pháp chế xác nhận) | như trên |
| | US | US-CCPA-01/02/03 | 10 ngày làm việc xác nhận, 45 ngày, gia hạn thêm 45 ngày | Có | như trên |
| **3. Hạn báo sự cố** | VN | PDP-014, PDP-024 | 72 giờ | Có | giờ phát hiện → giờ báo |
| | EU | GDPR-033 | 72 giờ | Có | như trên |
| | US | — | file luật US không có quy tắc báo sự cố | — | — |

**Hệ quả cho việc tiêm lỗi:**
- Loại 1 chỉ tiêm được cho **EU và US**. VN không có quy tắc nên không có lỗi để tiêm, trừ khi bổ sung quy tắc.
- Loại 1 cần con số do doanh nghiệp tự chọn theo từng mục đích. Hiện chưa chọn. Bài thử dùng một thước đo chung 365 ngày, **chỉ để dựng đề**, không phải số luật. Điều cần kiểm là hệ thống so đúng tuổi dữ liệu với số được cấu hình, nên dòng tiêm lỗi chỉ cần già hơn hẳn số đó, dòng đối chứng trẻ hơn hẳn.
- Loại 2 có "ngày làm việc", nên cần một lịch ngày làm việc cố định cho bài thử.
- Các số 90 (EU) và 180 (VN, US) từng ghi trong bản trước **không có căn cứ**, đã bỏ.

### Hai đồng hồ: ngày của dữ liệu và `as_of`

Theo [LEGAL_TO_RULE.md](LEGAL_TO_RULE.md) dòng 272, hai mốc này **tách riêng**:
- **Ngày của dữ liệu**: cột thời gian của từng dòng (telemetry ngày 01–10/01/2026).
- **`as_of`**: ngày chạy kiểm tra. Chạy thường ngày thì là ngày hôm nay. Chạy lại để kiểm toán thì là ngày xử lý gốc.

Hạn lưu (loại 1) cần cả hai: tuổi = `as_of` − ngày dữ liệu. Hạn xử lý (loại 2, 3) chỉ cần hai mốc **trong bảng sự kiện**; `as_of` chỉ dùng khi yêu cầu **chưa xong**.

Bài thử phải **cố định `as_of`**, nếu không kết quả đổi theo ngày chạy: dữ liệu tháng 01/2026, chạy ngày 13/10/2026 thì mọi dòng đều già hơn 270 ngày. Đề xuất `as_of = 2026-01-11` cho bài thử. Khi chạy thật trên hệ thống, `as_of` là đồng hồ thật.

## 7. Ngưỡng che toạ độ

Quy tắc **US-CCPA-05** coi toạ độ chính xác (sai số dưới 1.850 feet ≈ 564 m) là dữ liệu nhạy cảm, chỉ dùng cho chức năng lõi của xe. Muốn dùng cho mục đích khác thì phải **làm thô** toạ độ để vùng không chắc chắn rộng hơn 564 m. "Ngưỡng che" là mức thô tối thiểu đó.

Dữ liệu hiện có toạ độ 6 số lẻ (sai số khoảng 0,1 m), nên rất chính xác. Làm tròn xuống còn bao nhiêu số lẻ thì đủ che:

| Số lẻ | Ô lưới (theo kinh độ) tại Berlin 52,5° / Hà Nội 21° / New York 40,7° | Đạt ngưỡng 564 m? |
|---|---|---|
| 2 | khoảng 678 m / 1.040 m / 844 m | **Đạt** |
| 3 | khoảng 68 m / 104 m / 84 m | Không đạt |

Cạnh ô lưới theo vĩ độ luôn khoảng 1.110 m với 2 số lẻ. Vì vậy quy ước "tối đa 2 số lẻ" đạt ở cả 3 zone. Đây là **xấp xỉ kỹ thuật** của mình, chưa phải cách luật định nghĩa. Chỉ US có số trong luật. VN và EU không có số, đang lấy theo US, ghi `gia_dinh_chua_duyet`.

## 8. Phạm vi: hoãn phần chuyển dữ liệu xuyên biên giới (2026-10-14)

Mô hình hãng taxi ở 3 thị trường, xử lý tập trung tại VN, vẫn đúng. Nhưng bài thử Lane B **không tiêm** phần dữ liệu đi qua biên giới (lúc nạp về VN, và lúc gửi đi tiếp). Lý do: 6 trong 53 quy tắc cần "đích gửi" mới chạy được, và SoD không có chỗ chứa SCC, đánh giá rủi ro, hợp đồng xử lý (xem §1).

- **Quy tắc bị hoãn** (cột "Tiêm lỗi Lane B" ghi `hoan` trong 3 file luật): PDP-009, 012, 020; GDPR-028, 044; US-CCPA-08.
- **Quy tắc cứu được bằng mục đích** thay cho đích gửi: US-CCPA-04 (người từ chối chia sẻ không được có trong tập mục đích `marketing`, tình huống B14) và PDP-011 (mục đích `llm_assist` không dùng giá trị thô).
- **Ngữ cảnh bộ lọc rút gọn:** `{subject_zone, purpose_id, role, as_of}`, không còn `dest_id` hay `from_id`.
- **Thiết kế đầy đủ hai chiều vẫn giữ để dùng sau:** [`hoan/flows.csv`](hoan/flows.csv), [`hoan/destinations.csv`](hoan/destinations.csv).
- **Báo cáo phải ghi một câu về giới hạn này:** dữ liệu EU nằm ở máy chủ VN là sự thật của kiến trúc. Bài thử không kiểm điều kiện chuyển giao, mà giả định điều kiện đó đã được đáp ứng. Giả định này cần pháp chế xác nhận.

## 9. Bộ dữ liệu Lane B đã tiêm (2026-10-14)

**Vị trí:** gộp ngay trong [`data_new/vingroup_pii_faulty_testset_3zone/`](../../../data_new/vingroup_pii_faulty_testset_3zone/), không có thư mục riêng. **Sinh bằng một lệnh** cho cả Lane A và Lane B: `uv run python data_new/Ingestion/build_testset_3zone.py` (bước Lane B là `inject_lane_b.py`). Seed 42, ngày chạy cố định `as_of = 2026-01-11`.

### 9.1 Lane B nằm ở đâu

| Chỗ | Thêm gì |
|---|---|
| `dim_customers.csv` (5.106 khách) | 5 cột: `consent_at`, `consent_withdrawn_at`, `delete_requested_at`, `delete_completed_at`, `opt_out_sharing` |
| `dim_drivers.csv` (60 tài xế) | Cột `legal_basis` (chỉ EU bị GDPR-006 chi phối, zone khác ghi `n/a`) |
| `synthetic_ev_telemetry_ved_ref.csv` | Cột `fatigue_score` cho 19.200 dòng của 20 xe EU (xe có thiết bị giám sát tài xế); zone khác để trống |
| `synthetic_ev_telemetry_archive_2024-12.csv` (**file mới duy nhất**) | Phân vùng lưu trữ cũ: 288 dòng, ngày 0 của 3 xe lùi về 15/12/2024 (392 ngày so với `as_of`). Để riêng vì trộn dòng năm 2024 vào telemetry 10 ngày sẽ làm Lane A báo nhầm lỗi thời gian |
| `lane_b_manifest.json` (**đáp án**) | Tham số hợp đồng, 21 lần chạy, kết quả đúng của từng lần |

Lane B chỉ **thêm cột**, không đổi thứ tự dòng. Đã kiểm: sinh lại cả bộ từ đầu, mọi cột gốc của Lane A, danh sách 465 lỗi và đáp án PII giống hệt bản trước.

### 9.2 13 tình huống, 21 lần chạy

| Mã | Zone | Quy tắc | Lỗi tiêm | Đối chứng |
|---|---|---|---|---|
| B05 | US | US-CCPA-05 | Toạ độ 6 số lẻ của xe US dùng cho `fleet_analytics` | Cùng dữ liệu nhưng làm tròn 2 số lẻ; toạ độ chính xác nhưng mục đích `ops_dispatch` |
| B06 | VN | PDP-002/024 | Vai trò `analyst` đọc cột vị trí | Vai trò `data_steward` |
| B07 | EU | GDPR-009 | `fatigue_score` (19.200 dòng EU) chưa gắn nhãn dữ liệu đặc biệt | Cùng cột đã gắn nhãn |
| B08 | US | US-CCPA-07 | Xe `VF8VNF_0041` trong file lưu trữ cũ, 96 dòng, 392 ngày > 365 | Telemetry ngày 1–10/01 (tối đa 10 ngày) |
| B09 | US | US-CCPA-07 + 02 | Xe `VF8VNF_0042` quá hạn nhưng đang giữ pháp lý: **không xoá, chặn dùng phân tích** (kết quả thứ ba `hold_block`) | — |
| B10 | EU | GDPR-005 | Xe `VF8VNF_0001`, 96 dòng, 392 ngày > 365 | Telemetry ngày 1–10/01 |
| B11 | VN | PDP-005 | 10 khách yêu cầu xoá 01/12/2025 (41 ngày > 20) | 5 khách yêu cầu 05/01/2026 (6 ngày) |
| B12 | VN | PDP-003 | 10 khách rút đồng ý 01/12/2025 mà chuyến tháng 1 vẫn còn (> 15 ngày) | 5 khách rút 08/01/2026 (3 ngày) |
| B13 | VN | PDP-006 | 10 khách có chuyến nhưng không có bản ghi đồng ý | Các khách VN còn lại đều có |
| B14 | US | US-CCPA-04 | 10 khách từ chối chia sẻ; dùng toàn bộ 2305 chuyến US cho mục đích `marketing` thì 20 chuyến của họ lọt vào | Cùng lần chạy nhưng đã loại người từ chối |
| B15 | EU | GDPR-006 | 2 tài xế: 1 căn cứ `consent`, 1 để trống | 18 tài xế còn lại hợp lệ (13 `contract`, 5 `legitimate_interest`) |
| B16 | EU | GDPR-005 | 109 chuyến EU có `customer_contact`, cột ngoài danh sách của mục đích | Lần chạy không dùng cột đó |
| B19 | VN | (đối chứng F1) | 33 dòng pin âm: **Lane A phải bắt, Lane B phải đạt** | — |

Kết quả đúng của 21 lần chạy: 11 `fail`, 9 `pass`, 1 `hold_block`.

### 9.3 Độ tin cậy của đáp án

- Đáp án dựng theo thực thể đã chọn lúc tiêm, rồi `verify()` **tính lại từ file đã ghi** và so khớp. Lệch thì script dừng, không ghi đáp án.
- Kiểm độc lập bằng đếm trực tiếp (không dùng code của script): 10/5 khách ở B11 và B12, 10 khách ở B13 và B14, 20 chuyến của người từ chối ở B14, 109 chuyến ở B16, 33 dòng pin âm ở B19, `fatigue_score` chỉ có ở 19.200 dòng EU.
- Thử phá 6 chỗ trong đáp án (bỏ một khách, đổi `hold_block` thành `fail`, đổi 3 đối chứng thành lỗi, sửa số pin âm): cả 6 đều bị bắt.
- Chạy lại bước Lane B lần hai: mọi file CSV giống hệt, nên chạy bao nhiêu lần cũng ra cùng kết quả.
- Lane A không bị đụng: `fault_manifest.json` vẫn 465 lỗi, mọi bước kiểm tra vẫn đạt.

### 9.4 Giới hạn cần ghi khi báo cáo

- Mỗi tình huống chỉ có 1 đến 10 thực thể. Báo cáo theo **bắt được hay không**, không tính tỉ lệ phần trăm.
- **Số 365 ngày và ngưỡng 2 số lẻ không phải số trong luật** (chỉ US có ngưỡng 564 m). VN và EU đang lấy theo US, chờ pháp chế duyệt. VN không có quy tắc hạn lưu nên không có lỗi hạn lưu cho VN.
- B05, B06, B07 phụ thuộc tham số của lần chạy (vai trò, nhãn, mục đích), không chỉ giá trị trong dữ liệu. B05 đo được số lẻ từ dữ liệu, B06 và B07 thì không.
- **Tất cả là dữ liệu dựng và do nhóm tự đặt đề.** Bộ này chứng minh bộ lọc xử lý đúng logic luật, chưa chứng minh nó tìm ra vi phạm trên dữ liệu thật.
