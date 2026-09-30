# Từ văn bản luật → rule máy chạy trên data (Lane B)

> **Cặp với:** [`README.md`](README.md) (schema controls) · [`../FILTER_CORE_ZONE_SIGNATURE.md`](../FILTER_CORE_ZONE_SIGNATURE.md) (pack đầy đủ theo zone) · [`../ZONE_LEGAL_MAPPING.md`](../ZONE_LEGAL_MAPPING.md) §5 (cột → tem) · [`../PRODUCT_PHASE_2.md`](../PRODUCT_PHASE_2.md) §4.2.1 (toán tử hợp pack)
> **Trạng thái:** plan + ví dụ chạy tay. Chưa có runtime.

---

## 1. Vấn đề

Ma trận trong folder này (`vn/VN_Compliance_Matrix.csv`, `eu/EU_rule .csv`, `us/US_rule.csv`, `ITGC.csv`) viết **cho người đọc**:

- Là bản export Excel: có dòng tiêu đề, dòng tổng hợp, cột lệch; header mỗi zone một kiểu.
- Không khớp schema chuẩn trong `README.md`; `packs.csv` trỏ tới `pack_*_controls.csv` chưa tồn tại.
- Câu nghĩa vụ là văn xuôi ("Thiết lập RBAC…", "Lập hồ sơ DPIA…") → máy không chạy được.

Cần một đường ống lặp lại được: **điều luật → control có mã → rule khai báo → chạy trên tem cột + ngữ cảnh → Finding → kho chặn / HITL**, truy vết được `law_ref`.

Ràng buộc đã chốt, giữ nguyên:
- Mỗi zone một **pack đầy đủ**, không lõi chung, không signature.
- Luật **không** ghi lên cột. Tem cột (`pii_role`, `data_category`, `treatment`) là trigger.
- Nhiều pack cùng bật: cấm = hợp, điều kiện cho phép = giao, retention lấy min / hold thì giữ.

---

## 2. Ý chính: không phải điều luật nào cũng thành rule data

Mỗi dòng ma trận được xếp vào **1 trong 3 `scope`**:

| scope | Là gì | Ví dụ trong ma trận | Máy làm gì |
|---|---|---|---|
| `data` | Kiểm được trên cột / dòng / đích | PDP-002 (dữ liệu nhạy cảm), PDP-012 (khử nhận dạng trước khi chia sẻ), PDP-017 (chỉ hash), PDP-020 (xuyên biên giới), PDP-024 (sinh trắc & vị trí), GDPR-005 (tối thiểu hoá + retention), GDPR-009, GDPR-025 | Rule chạy trên data → Finding, chặn / cách ly |
| `event` | Kiểm trên phiếu / log, có SLA | PDP-003/004/005 (DSR 2/15/10/20 ngày), PDP-014 (sự cố 72h) | Đồng hồ trên `dsr_requests` / incident, **không** trên từng dòng |
| `evidence` | Quy trình, tổ chức, thiết kế | PDP-001, 006, 007, 008 (thông báo, consent UI), PDP-019 (DPO), PDP-021/022 (DPIA), PDP-023, toàn bộ ITGC | Checklist bằng chứng + trạng thái sẵn sàng, **không** phải filter data |

Ước tính VN: ~7 control `data`, ~5 `event`, còn lại `evidence`. **Chỉ nhóm `data` đi vào filter PII.**

Phân loại sơ bộ VN (cần pháp chế duyệt):

| scope | Mã quy tắc |
|---|---|
| `data` | PDP-002, 009, 011, 012, 017, 020, 024 |
| `event` | PDP-003, 004, 005, 014, 024 (phần thông báo 72h) |
| `evidence` | PDP-001, 006, 007, 008, 010, 013, 015, 016, 018, 019, 021, 022, 023 |

(PDP-024 có cả hai phần: phần phân loại dữ liệu vị trí là `data`, phần báo sự cố 72h là `event` → tách thành 2 control.)

---

## 3. Đường ống 6 bước

```text
Ma trận Excel (người viết)
   │ B1 chuẩn hoá + gắn scope
   ▼
pack_<zone>_controls.csv ──────────────► scope=event/evidence → checklist / đồng hồ SLA
   │ scope=data
   │ B3 dịch câu luật → NẾU…THÌ PHẢI/CẤM…
   ▼
pack_<zone>.yaml  (rule khai báo, chỉ dùng từ vựng B2)
   │
   │   column_tags.yaml (Classify: cột → tem)   context: subject_zone, dest_id, purpose_id
   │              │                                      │
   ▼              ▼                                      ▼
            B4 engine.evaluate(tags, context, packs) → Finding[zone, control_id, law_ref, …]
   │
   ▼ B5 on_fail = block / quarantine_hitl → bảng quarantine + trạng thái review
   ▼ B6 golden test GL-01…07, P1–P7, pii_injection_manifest
```

### B1. Chuẩn hoá nguồn → `pack_<zone>_controls.csv`

- Script nhỏ đọc CSV Excel (bỏ dòng tiêu đề/tổng, map header VN/EU/US) → đúng schema `README.md`:
  `zone,pack_id,control_code,law_ref,obligation_summary,responsible_party,severity,automation,control_id,sla,expected_behavior,fail_criteria`
- Thêm cột `scope` (`data | event | evidence`).
- Thêm cột hiệu lực: `effective_from, effective_to, version, supersedes, status` (chi tiết §3.7).
- Excel là nguồn; không sửa tay CSV sinh ra.
- Output: `vn/pack_vn_controls.csv`, `eu/pack_eu_controls.csv` (đúng path `packs.csv`). US giữ stub (cắt vòng 1).

Map header:

| Chuẩn | VN | EU |
|---|---|---|
| `control_code` | Mã quy tắc (PDP-xxx) | Mã quy tắc (GDPR-xxx) |
| `law_ref` | Điều khoản tham chiếu | Điều khoản (GDPR) |
| `obligation_summary` | Hành động bắt buộc | Nghĩa vụ tuân thủ trọng yếu |
| `responsible_party` | Phòng ban phụ trách | Đối tượng áp dụng |
| `severity` | *(thiếu → điền)* | Mức độ nghiêm trọng |
| `automation` | *(thiếu → điền)* | Mức độ tự động |
| `control_id` | `CTL-VN-` + mã | Control ID |
| `sla` | Thời hạn SLA | *(thiếu)* |
| `expected_behavior` | Hành động bắt buộc | Ghi chú |
| `fail_criteria` | *(suy từ Bằng chứng kiểm toán)* | *(thiếu → điền)* |

### B2. Từ vựng tem cố định (`vocab.yaml`)

Rule chỉ được nói bằng từ vựng này, **không** nói tên cột. Thêm bảng mới (ví dụ 15 bảng thật) chỉ cần gắn tem, không sửa luật.

| Trục | Giá trị |
|---|---|
| `data_category` | identifier, contact, name, location, driving_behaviour, financial, content_feedback, credential, gov_id, vehicle_technical, working_time_proxy |
| `pii_role` | direct, linkable_identifier, contextual_personal, personal_if_linked, sensitive, forbidden, unclear |
| `treatment` | remove, pseudonymize, keep_restricted, generalize, keep |
| `dest_id` | dashboard_vn, dashboard_eu, llm_vn, llm_eu, llm_us, export_us, data_market |
| `dest_zone` | suy từ `dest_id` (VN / EU / US) |
| `subject_zone` | VN, EU, US, *(thiếu)* |
| `purpose_id` | ops_dispatch, fleet_analytics, llm_assist, marketing |

### B3. Dịch control `data` → rule khai báo (`pack_<zone>.yaml`)

**Cách dịch:** đọc câu luật → viết lại thành **một câu NẾU … THÌ PHẢI / CẤM …** chỉ dùng từ vựng B2 → điền YAML.

| Câu luật (ma trận) | Câu NẾU … THÌ |
|---|---|
| PDP-002: *DLCN nhạy cảm… phân quyền tối thiểu, xử lý chuyên biệt, mã hoá* | NẾU `pii_role = sensitive` THÌ PHẢI `treatment ∈ {remove, pseudonymize, keep_restricted, generalize}` |
| PDP-024: *Dữ liệu sinh trắc học & vị trí* | NẾU `data_category = location` THÌ coi như `pii_role = sensitive` (nâng hạng tem trong pack VN) |
| PDP-020: *Chuyển DLCN ra máy chủ nước ngoài → hồ sơ TIA* | NẾU `pii_role ≠ none` VÀ `dest_zone ≠ subject_zone` THÌ PHẢI `transfer_assessment = true`, không thì CẤM |
| PDP-012: *Đưa lên sàn / thương mại hoá → khử nhận dạng triệt để* | NẾU `dest_id = data_market` THÌ CẤM `treatment ∈ {keep, keep_restricted}` với mọi cột personal |
| PDP-011: *Chia sẻ nội bộ → ma trận phê duyệt + DLP* | NẾU `pii_role ∈ {direct, sensitive}` VÀ đích là LLM / export THÌ CẤM giá trị thô |
| GDPR-005: *Tối thiểu hoá, storage limitation* | NẾU `data_category ∈ {location, driving_behaviour}` THÌ PHẢI có `purpose_id` VÀ `age_days ≤ retention(purpose)` |
| GDPR-025: *Privacy by design / by default* | NẾU phép join tạo ra cặp (`linkable_identifier` + `direct`) THÌ PHẢI HITL |

DSL tối thiểu (không code tuỳ ý):

| Khoá | Ý nghĩa |
|---|---|
| `when` | điều kiện kích hoạt trên tem + ngữ cảnh |
| `require` / `forbid` | điều kiện phải đúng / không được đúng |
| `max_age_days` | retention |
| `upgrade` | nâng hạng tem trong pack (VD location → sensitive ở VN) |
| `on_fail` | `block` · `quarantine_hitl` · `finding_only` |
| `proposed_treatment` | treatment máy đề xuất khi fail |

Ví dụ `pack_vn.yaml`:

```yaml
pack_id: pack_vn
zone: VN
laws: ["Luật BVDLCN 2025", "NĐ 356/2025/NĐ-CP"]   # cần chốt, xem §7
controls:
  - control_id: CTL-VN-PDP-024
    law_ref: "NĐ 356/2025 Đ29 K1 a,c"
    when:    { data_category: location }
    upgrade: { pii_role: sensitive }
  - control_id: CTL-VN-PDP-002
    law_ref: "NĐ 356/2025 Đ4 K2"
    when:    { pii_role: sensitive }
    require: { treatment_in: [remove, pseudonymize, keep_restricted, generalize] }
    on_fail: block
    proposed_treatment: generalize
    severity: critical
  - control_id: CTL-VN-PDP-020
    law_ref: "NĐ 356/2025 Đ18 K4"
    when:    { pii_role_not: [none], dest_zone_ne: subject_zone }
    require: { transfer_assessment: true }
    on_fail: block
    severity: critical
  - control_id: CTL-VN-PDP-011
    law_ref: "NĐ 356/2025 Đ7 K4"
    when:    { pii_role_in: [direct, sensitive], dest_kind_in: [llm, export] }
    forbid:  { treatment_in: [keep] }
    on_fail: quarantine_hitl
    proposed_treatment: pseudonymize
```

Ví dụ `pack_eu.yaml` (trích):

```yaml
pack_id: pack_eu
zone: EU
laws: ["GDPR"]
controls:
  - control_id: CTL-GDPR-005
    law_ref: "GDPR Art. 5(1)(c),(e)"
    when:    { data_category_in: [location, driving_behaviour] }
    require: { purpose_id: present, treatment_in: [generalize, pseudonymize, keep_restricted] }
    max_age_days: { fleet_analytics: 90 }        # số ngày cần chốt
    on_fail: quarantine_hitl
    proposed_treatment: generalize
  - control_id: CTL-GDPR-025
    law_ref: "GDPR Art. 25"
    when:    { join_creates: [linkable_identifier, direct] }
    on_fail: quarantine_hitl
    proposed_treatment: pseudonymize
```

**LLM chỉ được dùng để gợi ý bản nháp câu NẾU…THÌ.** Pháp chế / DPO ký duyệt từng rule (`reviewed_by`, `version`). Runtime **không** gọi LLM.

### B4. Engine đánh giá

`evaluate(column_tags, context{subject_zone, dest_id, purpose_id}, packs) -> list[Finding]`

1. Chọn pack theo `subject_zone`. Thiếu zone → cờ chặn, **dừng**, không Classify (GL-04).
1b. Lọc luật và control **đang hiệu lực tại `as_of`** (§3.7).
2. Áp `upgrade` của pack lên tem cột.
3. Chạy từng control `when` → `require`/`forbid`.
4. Nhiều pack: toán tử §4.2.1. Gom trùng cùng cột + `control_id`.
5. Finding: `zone, pack_id, control_id, control_version, law_ref, as_of, table, column, row_ids, on_fail, proposed_treatment`.

Loader validate YAML bằng pydantic: tem ngoài vocab, hoặc `control_id` không có trong CSV → lỗi ngay khi nạp.

### B5. Nối kho chặn + HITL

`on_fail ∈ {block, quarantine_hitl}` → ghi bảng `quarantine` có sẵn (`src/api/quarantine_api.py`):
- `reason` = `control_id | law_ref`
- `status`: `QUARANTINED → IN_REVIEW → APPROVED / OVERRIDDEN / FALSE_POSITIVE / ESCALATED → APPLIED / RELEASED`
- `proposed_treatment` (máy) vs `user_action` (người chốt)

### B6. Kiểm thử

- GL-01…07 + P1–P7 (`ZONE_LEGAL_MAPPING.md` §7): mỗi case = (tem, context) → control nào phải bắn / không bắn.
- `vingroup_pii_testset_3zone/pii_injection_manifest.json` (S1, S2, S3) làm ground truth.
- Mỗi control `data` có ≥ 1 case pass + ≥ 1 case fail. CI fail nếu control mới không có test.

### 3.7 Ngày hiệu lực và vòng đời (thêm / sửa / xoá luật)

Luật thay đổi theo thời gian: văn bản mới thay văn bản cũ, điều khoản được sửa, có giai đoạn chuyển tiếp. Mọi luật và control đều mang **ngày hiệu lực**, để engine biết **tại một thời điểm, rule nào đang áp dụng**, và để chạy lại dữ liệu cũ vẫn ra đúng kết quả của thời điểm đó.

#### Hai tầng hiệu lực

| Tầng | Ở đâu | Trường |
|---|---|---|
| Văn bản luật | `laws[]` trong `pack_<zone>.yaml` | `law_id, title, effective_from, effective_to, superseded_by` |
| Control | `pack_<zone>_controls.csv` + `pack_<zone>.yaml` | `effective_from, effective_to, version, supersedes, status, change_note` |

Control chỉ chạy khi **cả** văn bản gốc **và** chính control đó đang hiệu lực.

```yaml
laws:
  - law_id: VN_ND13_2023
    title: "NĐ 13/2023/NĐ-CP"
    effective_from: 2023-07-01
    effective_to:   2025-12-31        # ⚠ cần xác minh ngày NĐ 356 thay thế
    superseded_by:  VN_ND356_2025
  - law_id: VN_ND356_2025
    title: "NĐ 356/2025/NĐ-CP"
    effective_from: 2026-01-01        # ⚠ cần xác minh
    effective_to:   null              # null = còn hiệu lực
  - law_id: VN_LUAT_BVDLCN_2025
    title: "Luật Bảo vệ dữ liệu cá nhân 2025"
    effective_from: 2026-01-01        # ⚠ cần xác minh

controls:
  - control_id: CTL-VN-PDP-020
    version: 2
    law_id: VN_ND356_2025
    law_ref: "NĐ 356/2025 Đ18 K4"
    effective_from: 2026-01-01
    effective_to:   null
    supersedes: CTL-VN-PDP-020@1      # bản cũ theo NĐ 13
    status: active
    change_note: "Chuyển căn cứ từ NĐ 13 sang NĐ 356"
    when: …
```

Quy ước ngày:
- `effective_from` tính **từ đầu ngày**, `effective_to` tính **hết ngày** (đóng cả hai đầu), theo giờ của zone (VN: `Asia/Ho_Chi_Minh`, EU: theo văn bản).
- `effective_to = null` nghĩa là còn hiệu lực.
- Hai version của cùng một `control_id` **không được chồng khoảng ngày**. Loader báo lỗi nếu chồng hoặc hở mà không ghi lý do.

#### Chọn rule theo `as_of`

Engine nhận thêm `as_of`:

| Trường hợp | `as_of` |
|---|---|
| Chạy thường ngày | Ngày chạy |
| Chạy lại / backfill dữ liệu cũ để kiểm toán | Ngày của lần xử lý gốc (để ra đúng kết quả thời điểm đó) |
| Thử trước luật sắp có hiệu lực | Ngày tương lai, chế độ `dry_run` (chỉ Finding, không chặn) |

Rule được nạp khi `effective_from ≤ as_of ≤ effective_to` **và** `status ∈ {active, deprecated}`.

Retention (`max_age_days`) vẫn tính trên **ngày của dữ liệu**, còn việc chọn rule nào tính theo `as_of`. Hai mốc này tách riêng.

#### Vòng đời trạng thái

| `status` | Engine | Khi nào |
|---|---|---|
| `draft` | Không chạy; chỉ chạy khi `dry_run` | Đang dịch, chưa ký |
| `scheduled` | Không chạy tới `effective_from` | Đã ký, luật chưa có hiệu lực |
| `active` | Chạy | Đang hiệu lực |
| `deprecated` | Vẫn chạy, Finding gắn `deprecated=true` | Sắp bị thay |
| `retired` | Không chạy rule mới, **giữ** Finding cũ | Hết hiệu lực |

`scheduled → active` và `active → retired` tự chuyển theo ngày. `draft → scheduled` cần người ký duyệt.

#### Thêm / sửa / xoá

| Thao tác | Làm gì | Không làm |
|---|---|---|
| **Thêm** luật hoặc control | Thêm dòng `status=draft` → ký duyệt → `scheduled` với `effective_from` → tự `active` | Bật ngay không qua ký |
| **Sửa** nội dung (điều kiện, ngưỡng, căn cứ) | Tạo **version mới**, `supersedes` bản cũ; bản cũ nhận `effective_to` = ngày trước `effective_from` của bản mới | Sửa đè dòng cũ (mất khả năng chạy lại đúng lịch sử) |
| **Sửa** lỗi chính tả, ghi chú | Sửa tại chỗ, không tăng version, ghi `change_note` | — |
| **Xoá** (luật bị bãi bỏ) | Đặt `effective_to`; bản ghi sang `retired` sau ngày đó | Xoá dòng khi còn Finding / HITL trỏ tới |
| **Thay** văn bản (NĐ 13 → NĐ 356) | Đóng `effective_to` văn bản cũ, thêm văn bản mới, mỗi control được map sang có version mới; control không còn căn cứ → `retired` | Đổi `law_ref` trên control cũ |
| Giai đoạn **chuyển tiếp** | Cho hai version cùng tồn tại bằng cách đặt khoảng ngày nối tiếp nhau; nếu luật cho phép áp cả hai trong giai đoạn đó, tạo 2 control_id riêng thay vì chồng version | Để 2 version cùng `control_id` chồng ngày |

Finding ghi `control_version` + `as_of`, nên luôn biết nó bắn theo bản luật nào.

#### Test cho hiệu lực

| Case | as_of | Kỳ vọng |
|---|---|---|
| GPS keep → llm_us, VN | 2025-06-01 | Bắn `CTL-VN-PDP-020@1` (căn cứ NĐ 13) |
| GPS keep → llm_us, VN | 2026-03-01 | Bắn `CTL-VN-PDP-020@2` (căn cứ NĐ 356) |
| Control `scheduled` từ 2027-01-01 | 2026-10-01 | Không bắn; `dry_run` thì ra Finding `dry_run=true` |
| Control `retired` | sau `effective_to` | Không bắn; Finding cũ vẫn còn |
| Hai version chồng ngày | — | Loader báo lỗi |

---

## 4. Ví dụ áp dụng trên data mẫu

Nguồn: `data_new/vingroup_pii_testset_3zone/`. Dòng dưới là dòng thật trong file.

### 4.1 Tem cột (bước Classify, tách khỏi luật)

| Bảng.cột | `data_category` | `pii_role` | Ghi chú |
|---|---|---|---|
| trips.`pickup_latitude/longitude` | location | contextual_personal | Pack VN nâng thành `sensitive` (PDP-024) |
| trips.`vehicle_vin`, `driver_id`, `customer_id` | identifier | linkable_identifier | |
| trips.`fare_amount`, `total_fare` | financial | personal_if_linked | |
| trips.`customer_contact` | *(không có trong catalog)* | **unclear** | S1 |
| feedback_pii.`raw_comment_text` | content_feedback | unclear → detector quét span | S2 |
| dim_customers / dim_drivers.`first_name,last_name` | name | direct | |
| dim_*.`email`, `phone_number` | contact | direct | |
| users.csv.`password_hash` *(raw_public)* | credential | forbidden | |

### 4.2 Ví dụ 1 — cùng cột GPS, khác zone → khác luật

Dòng VN:
```
XANH_TRIP_3423, VF8VNF_0021, DRV_XANH_0021, …, pickup 20.966068,105.829966, subject_zone=VN
```
Dòng EU:
```
XANH_TRIP_0000, VF8VNF_0001, DRV_XANH_0001, …, pickup 52.519207,13.361677, subject_zone=EU
```

| Ngữ cảnh | Pack | Control bắn | Kết quả |
|---|---|---|---|
| VN, `dest_id=dashboard_vn`, treatment=keep_restricted | VN | PDP-024 nâng GPS → sensitive; PDP-002 **pass** (keep_restricted hợp lệ) | Đi tiếp |
| VN, `dest_id=dashboard_vn`, treatment=keep | VN | PDP-002 **fail** | `block`, đề xuất `generalize` |
| VN, `dest_id=llm_us`, treatment=keep | VN | PDP-002 fail + PDP-020 fail (VN → US, không có TIA) + PDP-011 fail | `block` (**GL-01**) |
| EU, `dest_id=dashboard_eu`, có `purpose_id=fleet_analytics`, generalize | EU | GDPR-005 pass | Đi tiếp |
| EU, không có `purpose_id` | EU | GDPR-005 fail | `quarantine_hitl`, đề xuất `generalize` |

Điểm cần thấy: **luật khác nhau nhưng cột không đổi, tem không đổi.** Chỉ pack khác. Pack VN coi vị trí là nhạy cảm (PDP-024); pack EU không map GPS vào GDPR Art. 9 mà xử lý theo tối thiểu hoá (Art. 5).

Finding sinh ra (dòng VN → `llm_us`):
```json
{"zone":"VN","pack_id":"pack_vn","control_id":"CTL-VN-PDP-020",
 "law_ref":"NĐ 356/2025 Đ18 K4","table":"trips",
 "column":"pickup_latitude","row_ids":["XANH_TRIP_3423"],
 "on_fail":"block","proposed_treatment":"generalize"}
```

### 4.3 Ví dụ 2 — S1: cột lạ `customer_contact`

```
XANH_TRIP_0049, VF8VNF_0001, DRV_XANH_0001, …, subject_zone=EU, CUS_01785, 858-516-0332
```

- Cột không có trong `column_tags.yaml` → `pii_role = unclear`.
- Mọi pack coi `unclear` là chặn với **mọi đích** (manifest: *"column not in catalog → Unclear → blocked for every dest"*).
- Kết quả: 345 dòng có giá trị → `quarantine`, `status=QUARANTINED`, `reason="UNCATALOGUED_COLUMN"`.
- Người review: gắn tem `contact / direct` → `OVERRIDDEN`, treatment `pseudonymize` → `APPLIED`. Lần chạy sau cột đã có tem, không vào HITL nữa.

### 4.4 Ví dụ 3 — S2: PII trong văn bản tự do

VN:
```
FB_PII_0014, VF8VNF_0021, …, "khách Ashil Tynnan để quên đồ trên xe, sđt 531-161-2156", VN, XANH_TRIP_3533, CUS_04537
```
EU:
```
FB_PII_0002, VF8VNF_0002, …, "app không gửi hóa đơn về lgilsthorpe2x@mtv.com, nhờ kiểm tra giúp", EU, …, CUS_02106
```

- Detector quét span trong `raw_comment_text`: tìm thấy tên + SĐT (FB_PII_0014), email (FB_PII_0002) → tem **theo ô**: `pii_role = direct`.
- `dest_id=llm_vn` (VN): PDP-011 cấm `keep` với `direct` → `quarantine_hitl`, đề xuất `pseudonymize` (thay span thành `[TÊN]`, `[SĐT]`).
- `dest_id=llm_eu` (EU): GDPR-005 (không cần span này cho mục đích phân tích cảm xúc) → `quarantine_hitl`, đề xuất `remove` span.
- Người review thấy văn bản sau khi che: *"khách [TÊN] để quên đồ trên xe, sđt [SĐT]"* → `APPROVED` → `APPLIED`.

### 4.5 Ví dụ 4 — S3: join làm lộ danh tính

```
trips:         XANH_TRIP_0000 … driver_id=DRV_XANH_0001, customer_id=CUS_00729, subject_zone=EU
dim_drivers:   DRV_XANH_0001, VF8VNF_0001, Noellyn, De Beauchamp, ndebeauchamp0@home.pl, 884-707-5045, EU
```

- Mỗi bảng riêng đều qua được: trips chỉ có ID, dim_drivers là bảng hồ sơ có ACL.
- Phép join `trips.driver_id = dim_drivers.driver_id` tạo cặp `linkable_identifier + direct` → GPS + giờ đón gắn với **tên, email, SĐT** của tài xế.
- EU: GDPR-025 bắn → `quarantine_hitl` trên **phép join / view**, không phải trên từng dòng; đề xuất chỉ join trên bản đã `pseudonymize`.
- VN (tài xế `DRV_XANH_0021` Andrej Furley, VN) với `dest_id=data_market`: PDP-012 cấm `keep` → `block`.

### 4.6 Ví dụ 5 — US và thiếu zone

```
XANH_TRIP_6938, VF8VNF_0041, DRV_XANH_0041, …, 40.72323,-73.981591, subject_zone=US
```
- Pack US **cắt vòng 1** → không có control nào chạy. Engine ghi `finding_only`: `"NO_ACTIVE_PACK zone=US"`. **Không** tự áp pack VN / EU thay (không nới, không suy).
- Nếu một lô **không có** `subject_zone` → cờ chặn trước Classify (GL-04), không đánh giá luật nào.

### 4.7 Ví dụ 6 — cấm tuyệt đối

`raw_public/Ride Hailing/users.csv.password_hash` → `credential / forbidden` → mọi pack: `block` với mọi đích, không vào HITL (không có treatment nào hợp lệ ngoài `remove`).

### 4.8 Tổng hợp kỳ vọng (dùng làm test B6)

| Case | Zone | dest | Control phải bắn | on_fail |
|---|---|---|---|---|
| GPS keep → llm_us | VN | llm_us | PDP-002, PDP-020, PDP-011 | block |
| GPS keep_restricted → dashboard | VN | dashboard_vn | *(không)* | — |
| GPS thiếu purpose | EU | dashboard_eu | GDPR-005 | quarantine_hitl |
| S1 `customer_contact` | mọi | mọi | UNCATALOGUED | quarantine (HITL) |
| S2 SĐT trong feedback → LLM | VN | llm_vn | PDP-011 | quarantine_hitl |
| S2 email trong feedback → LLM | EU | llm_eu | GDPR-005 | quarantine_hitl |
| S3 join trips × dim_drivers | EU | dashboard_eu | GDPR-025 | quarantine_hitl |
| S3 join → data_market | VN | data_market | PDP-012 | block |
| Trip US | US | bất kỳ | NO_ACTIVE_PACK | finding_only |
| Lô thiếu zone | — | bất kỳ | ZONE_MISSING (GL-04) | block |
| `password_hash` | mọi | mọi | FORBIDDEN | block |

---

## 5. Thứ tự làm (vòng 1)

1. B1 + B2 cho **VN** → pháp chế duyệt bảng phân loại `scope` (§2).
2. B3 cho 7 control VN `data` + B4 + B6 (GL-01, GL-04, S1 trước).
3. Lặp cho **EU**. US giữ stub. `event` → đồng hồ DSR; `evidence` + ITGC → checklist, làm sau.
4. B5 khi engine ổn định.

## 6. File dự kiến

| File | Ai sửa |
|---|---|
| `legal-packs/vn/pack_vn_controls.csv`, `eu/pack_eu_controls.csv` | Sinh từ Excel (B1) |
| `legal-packs/vocab.yaml` | Nhóm data + pháp chế |
| `legal-packs/vn/pack_vn.yaml`, `eu/pack_eu.yaml` | Nhóm data viết, pháp chế ký |
| `legal-packs/column_tags.yaml` | Nhóm data (Classify) |
| Engine + loader (module mới trong `src/`) | Dev |
| `tests/compliance/` | Dev |

## 7. Cần chốt

- Ma trận VN ghi **NĐ 356/2025/NĐ-CP**, `packs.csv` ghi **Luật BVDLCN 2025 + NĐ 13/2023** → thống nhất `law_ref`.
- Ai ký duyệt bản dịch luật → rule (pháp chế / DPO / mentor)?
- Số ngày retention cho từng `purpose_id` (GDPR-005, `max_age_days`).
- Ngày hiệu lực chính xác của NĐ 356/2025 và Luật BVDLCN 2025, và NĐ 13/2023 hết hiệu lực từ ngày nào (§3.7, đang để ⚠).
- VN có coi vị trí là **nhạy cảm** mặc định (PDP-024) cho mọi mục đích không?

## 8. Kiểm chứng

- Loader: 0 lỗi validate trên `pack_vn.yaml`, `pack_eu.yaml`.
- `uv run pytest tests/compliance/`: toàn bộ bảng §4.8 cho đúng Finding.
- Chạy engine trên `vingroup_pii_testset_3zone`: S1 = 345 dòng, S2 = 30 dòng vào `quarantine` với `status=QUARANTINED`, khớp `pii_injection_manifest.json`.
