# Tool Layer cho AI Agent — Task 2

> Bọc 4 tool của Task 1 (`scripts/*.py`) thành một lớp "Agent Tool Layer" có typed input/output, timeout, error code chuẩn hóa, và whitelist — để một AI Agent (LangGraph) có thể gọi mà không thể thực thi mã tùy ý.

## Kiến trúc

```
scripts/*.py (Task 1, deterministic pipeline logic — không đổi)
        │  import trực tiếp (sys.path bootstrap trong common.py)
        ▼
src/tools/dq/                        ← lớp typed, có timeout + error code
    common.py         (ErrorCode, ToolError, run_with_timeout, execute)
    profiler_tool.py   (ProfilerInput/Output)
    validator_tool.py  (ValidatorInput/Output, whitelist)
    compiler_tool.py   (CompilerInput/Output, không đụng DB)
    test_runner_tool.py(TestRunnerInput/Output, evidence có cấu trúc)
        │
        ▼
src/agents/tools/dq_tools.py         ← 4 @tool LangChain, agent chỉ thấy 4 cái này
```

**Vì sao không viết lại logic từ đầu:** `scripts/*.py` đã deterministic, đã test, đã chạy đúng ở Task 1. Lớp mới chỉ import trực tiếp các hàm thuần (`profile_table`, `validate_rule`, `compile_rule`, `CHECKS` registry...) qua `sys.path` bootstrap trong `src/tools/dq/common.py`, không copy/paste lại logic.

## Common: `src/tools/dq/common.py`

- **`ErrorCode`** (str Enum) dùng chung cho cả 4 tool: `INVALID_INPUT, DB_NOT_FOUND, SCHEMA_NOT_FOUND, TABLE_NOT_FOUND, COLUMN_NOT_FOUND, OPERATOR_NOT_WHITELISTED, RULE_INVALID, TIMEOUT, EXECUTION_ERROR`.
- **`run_with_timeout(fn, timeout_seconds)`**: chạy `fn()` trong 1 worker thread, `future.result(timeout=...)`. Dùng thread thay vì `signal.alarm` vì Windows không có SIGALRM. Đây là **soft timeout** — thread treo sẽ không bị kill cưỡng bức (giới hạn của CPython), nhưng đủ dùng vì mọi tool ở đây chỉ làm I/O ngắn (SQLite, đọc file JSON).
- **`execute(fn, timeout_seconds)`**: chuẩn hóa MỌI kết quả về 1 tuple `(status, error_code, error_message, payload, execution_time_seconds)` — mỗi tool chỉ cần gọi hàm này rồi build Output model của riêng nó.

## 4 Tool

| Tool | File | Input chính | Output chính | Ràng buộc bắt buộc |
|---|---|---|---|---|
| Profiler | `profiler_tool.py` | `db_path`, `tables?`, `timeout_seconds` | `tables: list[TableProfile]` (row/column count, per-column type/null-rate/distinct, duplicate_count) | Mở DB ở `mode=ro`; `TableProfile` **không có field nào** cho anomaly/violation — schema Pydantic tự enforce điều này |
| Validator | `validator_tool.py` | `rules: list[RuleInput]`, `schema_path` | `results: list[RuleValidationResult]`, `valid_count`, `invalid_count` | Operator bị check với `ALLOWED_OPERATORS` **trước tiên** — operator lạ bị từ chối ngay với `OPERATOR_NOT_WHITELISTED`, không rơi vào nhánh validate chung |
| Compiler | `compiler_tool.py` | `rules: list[RuleInput]`, `schema_path` | `compiled: list[CompiledRule]` (satisfies_expr + violation_sql), `skipped` | Module này **không `import sqlite3`** — có test riêng (`test_compiler_module_never_imports_sqlite3`) khẳng định bằng cấu trúc là không thể mở kết nối DB |
| Test Runner | `test_runner_tool.py` | `compiled_rules: list[CompiledRule]`, `db_path`, `schema_path` | `passed`, `failed`, `evidence: list[Evidence]` | Mở DB ở `mode=ro`; mỗi `Evidence` có `violation_count` + `sample_violations` + `execution_status` ("completed"/"error") — lỗi SQL của 1 check bị cô lập, không làm crash cả tool call |

## Typed input/output + error code chuẩn hóa

Mỗi tool có đúng 1 cặp Pydantic model `XInput`/`XOutput`. `run_x()` nhận `XInput | dict`:
- Nếu là `dict` không hợp lệ (thiếu field, sai kiểu) → bắt `pydantic.ValidationError`, trả `status="error", error_code=INVALID_INPUT` — **không bao giờ raise ra ngoài cho agent**.
- Nếu hợp lệ → chạy qua `execute()` với timeout, mọi exception (kể cả bug không lường trước) đều bị chặn ở `execute()` và quy về `EXECUTION_ERROR`.

Ví dụ output thật (Validator bắt operator không whitelist):
```json
{
  "status": "success",
  "error_code": "NONE",
  "results": [
    {"rule_id": "BAD", "valid": false,
     "errors": ["operator 'evil_exec' is not in the whitelist: ['between', 'eq', ...]"]}
  ],
  "valid_count": 0, "invalid_count": 1
}
```

## Agent-facing layer: `src/agents/tools/dq_tools.py`

4 hàm `@tool` (LangChain `langchain_core.tools.tool`): `profiler_tool`, `validator_tool`, `compiler_tool`, `test_runner_tool`, gom trong `DQ_TOOLS`. Đây là **toàn bộ** bề mặt mà agent nhìn thấy cho data quality — không có tool "chạy SQL tùy ý" hay "eval Python" nào được expose, nên agent không thể thực thi mã tùy ý dù có cố tình prompt injection: nó chỉ có thể gọi 1 trong 4 hàm này với structured input, và `expr_eq` (rule liên-cột) đã được compile bằng regex whitelist từ Task 1 chứ không phải `eval()`.

## Test: `tests/test_tools/`

- **Unit test** (1 file/tool, `test_profiler_tool.py`/`test_validator_tool.py`/`test_compiler_tool.py`/`test_test_runner_tool.py`): mỗi file có cả **happy path** (input đúng → output đúng) và **failure path** (DB/schema không tồn tại, input sai kiểu, operator không whitelist, rule sai kiểu cột, timeout — ép timeout bằng `monkeypatch` làm chậm hàm bên trong thay vì dựa vào timeout cực nhỏ dễ flaky).
- **Integration test** (`test_integration.py`): chạy chuỗi thật Profiler → Validator → Compiler → Test Runner trên 1 SQLite tạm (`temp_db` fixture), xác nhận: rule sai không bao giờ lọt tới Compiler/Test Runner (`test_failure_path_bad_operator_never_reaches_test_runner`), và kể cả khi ai đó tự chế 1 `CompiledRule` trỏ tới cột không tồn tại (bỏ qua Validator/Compiler), Test Runner vẫn không crash mà cô lập lỗi vào evidence (`test_failure_path_hand_crafted_bad_check_caught_at_execution`) — minh họa phòng thủ nhiều lớp.
- Fixture dùng chung (`tests/test_tools/conftest.py`): `temp_db` (SQLite tmp_path với dữ liệu biết trước lỗi gì), `temp_schema` (chạy Profiler thật để sinh schema, không hard-code).

**Kết quả:** 27/27 test pass (`data/tool_layer_test_report.txt`/`.xml`). Toàn bộ 45 test của repo (Task 1 + Task 2 + template gốc) vẫn pass, `ruff check` sạch.

**Cách chạy:**
```bash
python -m pytest tests/test_tools -v --junitxml=data/tool_layer_test_report.xml
```

## Đối chiếu Acceptance Criteria

| Yêu cầu | Đáp ứng bằng |
|---|---|
| Mỗi tool có typed input/output | 4 cặp Pydantic `XInput`/`XOutput` trong `src/tools/dq/` |
| Timeout + error code chuẩn hóa | `common.run_with_timeout` + `ErrorCode` enum dùng chung |
| Profiler chỉ trả schema + aggregate metadata | `TableProfile`/`ColumnMetadata` không có field anomaly nào; test `test_happy_path_profiles_all_tables` assert đúng field set |
| Validator chỉ cho phép operation trong whitelist | Check `ALLOWED_OPERATORS` tường minh trước khi validate, trả `OPERATOR_NOT_WHITELISTED` |
| Compiler không thực thi dữ liệu | Module không `import sqlite3`; test cấu trúc xác nhận |
| Test Runner trả evidence có cấu trúc (violation count, sample, execution status) | `Evidence` model có đủ 3 field, mỗi check lỗi thực thi bị cô lập riêng |
| Unit + integration test cho happy path và failure path | `tests/test_tools/` — 4 file unit + 1 file integration, mỗi file có cả 2 loại |
