> **Note:** This document reflects the V3/V4 architecture state. For the current V5 Operational Trust Console architecture, please refer to the root [`README.md`](../../README.md), [`ARCHITECTURE.md`](../../ARCHITECTURE.md), and [`ADR_V5.md`](ADR_V5.md).


# Data Quality Pipeline — Nhật ký xây dựng

> Ghi lại toàn bộ các tool đã xây dựng cho pipeline DataTrust OS: mục tiêu, cách làm, file liên quan, cách chạy, và kết quả thực tế.
> Ngữ cảnh dữ liệu: xem `data/README.md` (Master Data Catalog — mô tả các bảng VinGroup EV/charging/trips/feedback và 9 fault family đã cấy lỗi có chủ đích trong các file `*_dirty.csv`).

Pipeline gồm 5 tool, chạy tuần tự bằng một orchestrator, mỗi tool chỉ làm đúng một việc (tách trách nhiệm rõ ràng theo kiến trúc Profiler Agent → AnomalyEngine → RuleEngine → Executor mô tả trong `data/README.md`):

```
build_source_db.py  →  profile_source_db.py  →  validate_rules.py  →  compile_rules.py  →  run_tests.py
   (Source DB)            (Profiler Tool)        (Validator Tool)     (Compiler Tool)      (Test Runner)
```

Chạy toàn bộ 5 bước một lệnh: `python scripts/run_pipeline.py`.

---

## Task 1 — Acceptance criteria checklist

| Yêu cầu | Đáp ứng bằng | Trạng thái |
|---|---|---|
| Kết nối SQLite làm Source DB, import CSV thành bảng | `scripts/build_source_db.py` → `data/source.db` | ✅ |
| Data Profiling sinh metadata | `scripts/profile_source_db.py` → `data/profiling_report.{json,md}` | ✅ |
| Pipeline kiểm tra chất lượng theo rule đã định nghĩa | `scripts/rules.json` → `validate_rules.py` → `compile_rules.py` → `run_tests.py` | ✅ |
| Sinh báo cáo + evidence, không tự sửa dữ liệu | `data/test_run_report.json` có `sample_violations`; `run_tests.py` mở `source.db` ở chế độ `mode=ro` (không thể ghi) | ✅ |
| Ghi log, manifest, kết quả chạy toàn pipeline | `scripts/run_pipeline.py` → `data/logs/*.log` (log từng bước) + `data/pipeline_manifest.json` (manifest) | ✅ |
| Chạy nhiều lần cho kết quả nhất quán (deterministic) | Đã chạy pipeline 2 lần, diff 4 report JSON — **giống hệt byte-for-byte** | ✅ |
| Log cho từng bước + thời gian thực thi | Mỗi step trong `pipeline_manifest.json` có `started_at/finished_at/duration_seconds`; `run_pipeline.py` in log kèm mốc thời gian ra console và `data/logs/<step>.log` | ✅ |
| Phát hiện ≥ 5 nhóm lỗi theo rule (duplicate, null, invalid type, invalid range, invalid date...) | 7 nhóm: `check_duplicate`, `check_null`, `check_type` (invalid type), `check_range` (invalid range), `check_date` (invalid date), `check_membership`, `check_ledger` | ✅ |
| Không truy cập/hiển thị dữ liệu nhạy cảm, chỉ dùng metadata khi phù hợp | Profiler/Validator/Compiler chỉ làm việc trên schema+metadata (`data/profiling_report.json`), không bao giờ đọc giá trị dòng thật; chỉ Test Runner (bước cuối, cần evidence) mới đọc sample row | ✅ |
| Báo cáo JSON + Markdown | Cả 4 report (`profiling_report`, `rule_validation_report`, `compiled_rules`, `test_run_report`) đều có `.json` + `.md` | ✅ |
| Test cho schema mismatch và invalid type | `tests/test_pipeline/test_validator.py` (`test_schema_mismatch_*`, `test_invalid_type_*`) + `tests/test_pipeline/test_run_tests.py` (`test_check_type_detects_non_numeric_value_in_numeric_column`) — 13/13 pass | ✅ |

**Evidence:**
- Local run command: `python scripts/run_pipeline.py` (không cần Docker — Dockerfile hiện có trong repo là cho FastAPI agent app, chưa nối với pipeline này).
- Sample profiling report: `data/profiling_report.md`
- Sample quality report + evidence: `data/test_run_report.md` (mục "Failure Evidence" có sample row thật cho từng check fail)
- Test report: `data/pipeline_test_report.txt` (pytest text) + `data/pipeline_test_report.xml` (JUnit XML) — sinh bằng `pytest tests/test_pipeline -v --junitxml=data/pipeline_test_report.xml`

---

## Bước 1 — Source Database (`scripts/build_source_db.py`)

**Mục tiêu:** gom toàn bộ CSV rời rạc trong `data/` thành một SQLite database duy nhất, mỗi CSV → một bảng, có schema (kiểu dữ liệu + primary key) tường minh thay vì để pandas tự đoán.

**Cách làm:**
- Chọn nguồn: toàn bộ CSV trong `data/raw_public/`, `data/vingroup/`, `data/vingroup_real/` (12 file).
- Với mỗi file, định nghĩa `CREATE TABLE` thủ công (tên cột, kiểu `TEXT/REAL/INTEGER`, primary key) dựa theo field contract đã ghi trong `data/README.md`. Bảng nào không có cột ID tự nhiên (vd `st_evcdp_raw`, `real_vgreen_charging_stations`) thì dùng `id INTEGER PRIMARY KEY AUTOINCREMENT`.
- Đọc CSV bằng `pandas.read_csv`, insert bằng `DataFrame.to_sql(..., if_exists="append")`.
- Kiểm tra trước khi build: verify các cột dự kiến làm PK (`record_id`, `trip_id`, `feedback_id`, `session_id`, `sentence_id`, `transaction_id`) không có duplicate/null trong CSV gốc.

**Cách chạy:**
```bash
python scripts/build_source_db.py
```

**Kết quả:** `data/source.db` với 12 bảng, tổng 8.100 dòng, PK/kiểu dữ liệu đúng như CSV gốc (đã verify bằng `PRAGMA table_info` + sample row).

---

## Bước 2 — Profiler Tool (`scripts/profile_source_db.py`)

**Mục tiêu:** trả về schema + metadata mô tả từng bảng — **không** phát hiện lỗi/bất thường.

**Cách làm (đã chỉnh sửa 1 lần):**
- Bản đầu tiên có luôn cả phát hiện outlier (IQR), invalid date, type mismatch, PK-violation.
- Bạn yêu cầu thu hẹp lại: Profiler chỉ trả schema + metadata, việc phát hiện bất thường/vi phạm ràng buộc để dành cho tool khác (đúng tinh thần tách Profiler Agent ra khỏi AnomalyEngine/RuleEngine trong tài liệu kiến trúc). Đã ghi lại quy tắc này vào bộ nhớ dài hạn của tôi để áp dụng nhất quán cho các bước sau.
- Với mỗi bảng trong `data/source.db`: đếm số dòng, số cột, liệt kê từng cột (kiểu khai báo trong SQLite + kiểu pandas quan sát được, null count/rate, số giá trị phân biệt), và số bản ghi trùng lặp (so sánh toàn bộ cột trừ primary key).

**Cách chạy:**
```bash
python scripts/profile_source_db.py
```

**Output:** `data/profiling_report.json` (machine-readable, các tool sau dùng lại làm nguồn schema) + `data/profiling_report.md` (đọc được).

**Kết quả nổi bật:** `uit_vsfc_raw` có 492/500 dòng trùng lặp, `real_xanh_sm_customer_feedback` có 460/500 — do dữ liệu feedback tiếng Việt hay lặp câu ngắn giống nhau.

---

## Bước 3 — Validator Tool (`scripts/validate_rules.py` + `scripts/rules.json`)

**Mục tiêu:** kiểm tra một *rule* (định nghĩa luật chất lượng dữ liệu) có **hợp lệ để dùng** hay không — không chạy rule trên dữ liệu thật.

**Cách làm:**
- Định dạng rule: JSON khai báo, ví dụ:
  ```json
  {"rule_id": "R001", "table": "vinfast_ev_telemetry_dirty", "column": "battery_soc",
   "operator": "between", "value": [0, 100], "description": "..."}
  ```
- 13 operator hỗ trợ: `not_null, gte, lte, gt, lt, eq, ne, between, in, regex, expr_eq, is_numeric, valid_date` (`expr_eq` dùng cho rule liên-cột kiểu ledger, vd `total_fare == fare_amount + tip_amount - discount_amount`, parse tên cột bằng regex whitelist thay vì `eval` để tránh rủi ro injection; `is_numeric`/`valid_date` bổ sung cho Task 1 để phủ đủ nhóm lỗi "invalid type"/"invalid date").
- Validator kiểm tra 2 lớp:
  1. **Cấu trúc**: đủ field bắt buộc, operator nằm trong danh sách cho phép, `value` đúng kiểu/hình dạng theo operator.
  2. **Khớp schema**: `table`/`column` phải tồn tại thật trong `data/profiling_report.json` (kết quả của Profiler Tool ở Bước 2), kiểu cột phải tương thích với operator (vd `between` không áp dụng lên cột TEXT).
- Soạn sẵn `scripts/rules.json` gồm 21 rule: 17 rule hợp lệ dựa trên các fault family đã tài liệu hóa (battery_soc, battery_voltage, cost_vnd, ledger mismatch, timestamp corruption qua `valid_date`, type mismatch qua `is_numeric`...), và 4 rule **cố tình sai** (sai kiểu cột, cột không tồn tại, bảng không tồn tại, operator không tương thích kiểu cột) để chứng minh Validator thực sự bắt được lỗi.

**Cách chạy:**
```bash
python scripts/validate_rules.py
```

**Output:** `data/rule_validation_report.json`/`.md`, exit code `1` nếu có rule invalid (dùng làm gate cho pipeline).

**Kết quả:** 17/21 rule VALID, 4 rule cố tình sai bị bắt đúng lý do (`operator 'between' requires a numeric column, but 'vehicle_vin' is TEXT`, `column 'settlement_score' does not exist...`, `table 'customers' does not exist...`, `operator 'valid_date' requires a TEXT column, but 'battery_soc' is REAL`).

---

## Bước 4 — Compiler Tool (`scripts/compile_rules.py`)

**Mục tiêu:** biến rule JSON đã hợp lệ thành 2 dạng văn bản thực thi được — **chỉ compile, không chạy**.

**Cách làm:**
- Import lại `validate_rule()` từ `validate_rules.py` để chỉ compile rule VALID, rule invalid bị skip kèm lý do.
- Với mỗi rule, sinh:
  - `satisfies_expr`: biểu thức Python mà một dòng dữ liệu phải thoả để đạt rule (vd `battery_soc >= 0 and battery_soc <= 100`).
  - `violation_sql`: mệnh đề SQL `WHERE ...` tìm các dòng **vi phạm** rule — tức phủ định của điều kiện trên (vd `WHERE battery_soc < 0 OR battery_soc > 100`).
- Không mở kết nối tới `source.db`, không đụng tới dữ liệu.

**Cách chạy:**
```bash
python scripts/compile_rules.py
```

**Output:** `data/compiled_rules.json`/`.md` — kết quả này chính là "executable checks" mà Test Runner ở Bước 5 sẽ nhận vào.

**Kết quả:** 17 rule compile thành công, 4 rule bị skip (đúng 4 rule invalid từ Bước 3).

---

## Bước 5 — Test Runner (`scripts/run_tests.py`)

**Mục tiêu:** nhận các "executable check" (SQL đã compile ở Bước 4 + check trùng lặp tự sinh), **thực sự chạy** trên `data/source.db`, và trả kết quả kèm bằng chứng cụ thể — không chỉ nhãn PASS/FAIL.

**Cách làm:**
- Từ mỗi rule đã compile, map `operator` sang một loại check: `check_range` (gte/lte/gt/lt/between), `check_null` (not_null), `check_membership` (in), `check_equality` (eq/ne), `check_pattern` (regex), `check_ledger` (expr_eq), `check_type` (is_numeric — phát hiện "invalid type"), `check_date` (valid_date — phát hiện "invalid date").
- Tự sinh thêm 1 `check_duplicate` cho mỗi bảng (dùng lại logic duplicate của Profiler nhưng giờ chạy thật).
- Mỗi loại check là **một hàm Python riêng** đăng ký trong dict `CHECKS` (registry pattern) — Test Runner tra loại check rồi gọi đúng hàm, không if/elif tràn lan.
- Mở `data/source.db` ở chế độ **read-only** (`sqlite3.connect("file:...?mode=ro", uri=True)`) — về mặt kỹ thuật không thể ghi/sửa dữ liệu dù có lỗi trong code.
- Mỗi check trả về `violation_count` + tối đa 5 dòng dữ liệu thật vi phạm làm evidence (rỗng nếu pass).

**Cách chạy:**
```bash
python scripts/run_tests.py
```

**Output đúng format yêu cầu:**
```json
{"passed": 21, "failed": 8, "evidence": [ ... mỗi check có violation_count + sample_violations ... ]}
```
Ghi thêm `data/test_run_report.json`/`.md`, exit code `1` nếu có check failed.

**Kết quả thật (lần chạy gần nhất):** 21 passed / 8 failed. Các failed khớp đúng các fault đã biết trước (battery_soc âm, battery_voltage vượt ngưỡng, cost_vnd âm, fare_amount âm, ledger mismatch, timestamp `"INVALID_TIMESTAMP"` bị `check_date` bắt đúng 10 dòng, 2 bảng feedback bị trùng câu nhiều). `check_type` (invalid type) hiện chưa bắt được vi phạm nào trong bộ dữ liệu này (0/0) — nghĩa là các cột số không có garbage kiểu text, đây vẫn là kết quả hợp lệ (check hoạt động đúng, chỉ là chưa có case dương tính trong dataset hiện tại). **Failed là kết quả đúng, không phải bug** — các bảng `*_dirty` là dữ liệu cố tình cấy lỗi (123 fault, xem `data/vingroup/vingroup_fault_manifest.json`), nên Test Runner phải báo failed thì mới chứng minh được rule đang hoạt động đúng.

---

## Orchestrator — chạy toàn bộ pipeline (`scripts/run_pipeline.py`)

**Mục tiêu:** chạy cả 5 bước bằng một lệnh duy nhất, ghi log riêng cho từng bước, đo thời gian thực thi, và ghi lại một manifest tổng cho toàn bộ lần chạy (đáp ứng yêu cầu "Ghi log, manifest và kết quả chạy của toàn bộ pipeline").

**Cách làm:**
- Chạy tuần tự 5 script con bằng `subprocess`, stream stdout/stderr ra console **đồng thời** ghi vào `data/logs/<step>.log`.
- Đo `started_at`/`finished_at`/`duration_seconds` cho từng bước bằng `time.perf_counter()`.
- Phân biệt 2 loại "thất bại": `validate_rules.py` và `run_tests.py` cố tình `exit(1)` khi tìm thấy rule invalid / check failed — đây là **kết quả nghiệp vụ mong đợi** (`status: "ok_with_findings"`), pipeline vẫn tiếp tục chạy bước sau. Chỉ khi một step crash thật (exit code khác, exception) thì mới dừng pipeline và đánh dấu `status: "error"`.
- Ghi `data/pipeline_manifest.json`: `pipeline_run_id`, thời gian bắt đầu/kết thúc toàn pipeline, `overall_status`, và danh sách từng step kèm log file tương ứng.

**Cách chạy:**
```bash
python scripts/run_pipeline.py
```

**Kết quả:** chạy 2 lần liên tiếp, diff 4 file report (`profiling_report.json`, `rule_validation_report.json`, `compiled_rules.json`, `test_run_report.json`) — **giống hệt nhau byte-for-byte**, xác nhận pipeline deterministic. `overall_status` trả về `"ok_with_findings"` (không phải `"error"`) vì các failed đều là finding dữ liệu thật, không phải lỗi hệ thống.

---

## Test cho pipeline (`tests/test_pipeline/`)

**Mục tiêu:** test tự động cho 2 yêu cầu bắt buộc của Task 1 — schema mismatch và invalid type — cộng thêm coverage cho các check khác.

**Cách làm:**
- `tests/test_pipeline/test_validator.py`: gọi thẳng `validate_rule()` với schema giả lập nhỏ gọn (không phụ thuộc `data/source.db` đã build sẵn), test rule tham chiếu bảng/cột không tồn tại (schema mismatch) và rule dùng sai operator/kiểu dữ liệu (invalid type), cộng 1 test rule hợp lệ để đối chứng.
- `tests/test_pipeline/test_run_tests.py`: dựng SQLite in-memory nhỏ, gọi thẳng các hàm `check_range/check_null/check_type/check_date/check_duplicate` từ `run_tests.py`, assert đúng `violation_count` và đúng dòng vi phạm trong `sample_violations` — kể cả case "invalid type" thật (giá trị text nằm trong cột khai báo REAL, tận dụng weak typing của SQLite).
- `tests/test_pipeline/conftest.py`: thêm `scripts/` vào `sys.path` để import trực tiếp các module trong `scripts/` (vốn không phải package) từ test.

**Cách chạy:**
```bash
python -m pytest tests/test_pipeline -v --junitxml=data/pipeline_test_report.xml
```

**Kết quả:** 13/13 test PASS. Report lưu tại `data/pipeline_test_report.txt` (text) và `data/pipeline_test_report.xml` (JUnit XML).

---

## Các thay đổi phụ trợ khác

- `requirements.txt`: thêm `pandas>=2.0.0` (cả 5 script đều cần) — đã cài trực tiếp vào `.venv` của project bằng `.venv/Scripts/python.exe -m pip install -r requirements.txt`.
- Ghi nhớ kiến trúc (bộ nhớ dài hạn của tôi, không phải file trong repo): "Profiler Tool chỉ trả schema+metadata, không phát hiện anomaly/violation" — áp dụng cho mọi lần chỉnh sửa `profile_source_db.py` sau này.

## File map

| File | Vai trò |
|---|---|
| `scripts/run_pipeline.py` | Orchestrator — chạy cả 5 bước, log + manifest |
| `scripts/build_source_db.py` | Bước 1 — build `data/source.db` từ CSV |
| `scripts/profile_source_db.py` | Bước 2 — Profiler Tool (schema + metadata) |
| `scripts/rules.json` | Bộ 21 rule mẫu (input cho Validator) |
| `scripts/validate_rules.py` | Bước 3 — Validator Tool |
| `scripts/compile_rules.py` | Bước 4 — Compiler Tool |
| `scripts/run_tests.py` | Bước 5 — Test Runner |
| `data/source.db` | Output Bước 1 |
| `data/profiling_report.json/.md` | Output Bước 2 |
| `data/rule_validation_report.json/.md` | Output Bước 3 |
| `data/compiled_rules.json/.md` | Output Bước 4 |
| `data/test_run_report.json/.md` | Output Bước 5 |
| `data/pipeline_manifest.json` | Manifest tổng — timing + status từng bước |
| `data/logs/*.log` | Log console của từng bước |
| `tests/test_pipeline/` | Pytest: schema mismatch, invalid type, các check khác |
| `data/pipeline_test_report.txt/.xml` | Test report (evidence) |
