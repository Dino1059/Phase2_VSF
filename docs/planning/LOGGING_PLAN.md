# Logging & Observability Plan — DataTrust OS

Status: Implemented (core runtime, audit search, agent trace boundary)  
Scope: Backend runtime logging, request tracing, agent/pipeline observability, frontend debug cleanup  
Last reviewed: 2026-09-05

Implementation status (2026-09-05): completed the observability foundation, JSON runtime output, request correlation ID, redaction/truncation, structured LLM events, audit API filters, and frontend debug-log cleanup. Existing service loggers now flow through the centralized runtime handler; future work is limited to adding more domain-specific events where operational evidence requires them.

## 1. Quyết định đề xuất

Tách rõ ba loại dữ liệu quan sát:

| Loại | Mục đích | Nơi lưu hiện tại | Có thay đổi không? |
|---|---|---|---|
| Runtime log | Debug/vận hành: request, lỗi, thời gian, worker | stdout/stderr của process/container | Chuẩn hóa bằng Python `logging` |
| Audit log | Lịch sử nghiệp vụ và hành động có trách nhiệm | DuckDB `audit_log` | Giữ `AuditService`, không thay thế bằng runtime log |
| Agent trace | Timeline của agent/tool/session | DuckDB `agent_traces` | Giữ schema và bổ sung log liên kết nếu cần |

Phương án ưu tiên là dùng Python standard library, ghi runtime log ra stdout/stderr, không thêm ELK/Loki/database mới trong phiên bản đầu. Đây là phương án ít thay đổi nhưng vẫn giải quyết được truy vết.

## 1.1. Storage Contract — nơi lưu chính thức

Ba loại log phải được lưu tách biệt như sau:

| Loại log | Nơi lưu chính thức | Dữ liệu chính | Khóa truy vết | Cách tìm kiếm |
|---|---|---|---|---|
| Runtime log | `stdout/stderr` của backend process; Docker thu qua container logs | level, event, message, timestamp, request/run context | `request_id`, `run_id` | `docker compose logs`, log collector hoặc external log platform |
| Audit log | DuckDB table `audit_log` trong database đang cấu hình bởi `DUCKDB_PATH` | action, actor, target, details, timestamp, hash-chain | `id`/`audit_id`, `actor`, `action`, `target_id` | API `/api/v1/audit`, SQL filter theo action/actor/target/time |
| Agent trace | DuckDB table `agent_traces` trong cùng database | session, step, agent, tool, status, duration, token, summary, timestamp | `session_id` + `step_index`; liên kết thêm `run_id` nếu có | API `/api/v1/traces/{session_id}`, timeline UI, SQL filter theo session/time |

Quy tắc lưu:

- Runtime log **không lưu vào DuckDB** trong phiên bản đầu vì có khối lượng lớn và là dữ liệu vận hành ngắn/trung hạn. Production có thể chuyển stdout vào Loki/ELK/Cloud Logging mà không đổi business code.
- Audit log **lưu bền vững trong DuckDB**, không ghi đè, không dùng runtime log thay thế. Mỗi event mutation phải có `event_hash` liên kết với `previous_event_hash`.
- Agent trace **lưu bền vững trong DuckDB** để UI đọc lại timeline theo `session_id`. Không lưu raw secret; thought/tool output phải theo safe-summary/redaction policy hiện có.
- Cả ba loại đều có `timestamp`, nhưng timestamp không thay thế khóa nghiệp vụ: runtime dùng `request_id`, audit dùng `audit_id`, agent trace dùng `session_id + step_index`.

Đường truy vết chuẩn:

```text
Runtime log: request_id=req-123
       -> Agent trace: session_id=sess-456, run_id=run-789
              -> Audit log: audit_id=aud-012
```

Nếu một flow không tạo audit mutation thì chỉ có runtime log và agent trace; không tạo audit record giả.

## 2. Nghiệp vụ gốc của các file hiện tại

### 2.1. Entry point và cấu hình

| File | Nghiệp vụ gốc | Liên quan đến logging | Hướng xử lý |
|---|---|---|---|
| `src/main.py` | Khởi tạo FastAPI, startup/shutdown, middleware, mount API/UI | Đang có `print()` cho startup, exception, request timing, slow API | Là điểm tích hợp logging trung tâm; giữ middleware nhưng đổi sang logger |
| `src/config.py` | Đọc settings từ `.env` và environment; cung cấp DB, LLM, Sentry, CORS | Đã có `LOG_LEVEL` trong `.env.example` nhưng Settings chưa thể hiện rõ field này | Bổ sung `log_level`; không để module khác tự đọc environment |
| `.env.example` | Hợp đồng cấu hình dành cho developer/deployment | Đã khai báo `LOG_LEVEL`, Sentry và AI log settings | Cập nhật mô tả level, môi trường và dữ liệu nhạy cảm |
| `Dockerfile` | Đóng gói backend | Process/container là nơi thu stdout/stderr | Không ghi file log trong image; kiểm tra log qua container runtime |
| `docker-compose.yml` | Chạy các service | Quyết định cách xem/giới hạn log container | Chỉ bổ sung cấu hình nếu cần giới hạn rotation; không đổi nghiệp vụ |

### 2.2. API và middleware

| File | Nghiệp vụ gốc | Log cần truy vết |
|---|---|---|
| `src/api/middleware.py` | Role/permission middleware và kiểm soát quyền | Access denied, role, endpoint; không log token |
| `src/middleware/auth.py` | JWT decode, user identity, authentication/authorization helper | Token invalid/expired, auth failure; chỉ log lý do an toàn |
| `src/api/routes/auth.py` | API login/authentication | Login success/failure, user identifier đã redacted |
| `src/api/routes/ingestion.py` | Endpoint bắt đầu/điều khiển ingestion | Dataset, ingestion run, batch, row count, duration, lỗi |
| `src/api/pipeline.py` | API điều phối pipeline | Pipeline run, dataset/table, stage, status |
| `src/api/routes/profiling.py` | API profiling dataset | Dataset, sample size, duration, result status |
| `src/api/routes/executions.py` | API thực thi rule/pipeline action | Rule, target table, execution result; mutation phải đi qua audit |
| `src/api/hitl.py` | Human-in-the-loop review, approval, reset | HITL request/result; nghiệp vụ chính ghi audit |
| `src/api/quarantine_api.py` | Quarantine, remediate, reject dữ liệu | Error kỹ thuật bằng runtime log; hành động nghiệp vụ giữ audit hash |
| `src/api/routes/audit.py` | Đọc lịch sử audit | Log lỗi query nếu có; không tạo runtime log thay cho dữ liệu trả về |
| `src/api/audit_store.py` | CRUD/abstraction cho audit store | Chỉ log lỗi persistence; không duplicate mọi audit event |
| `src/api/traces.py` | Chuẩn hóa và trả workflow/agent trace cho UI | Log lỗi đọc/normalize trace; không log toàn bộ thought/tool output |
| `src/api/dashboard.py` | Dashboard stats và audit/trace summaries | Log lỗi query và thời gian bất thường nếu cần |
| `src/api/routes/system.py` | Health/system/reset operations | Reset và state-changing action phải audit; lỗi kỹ thuật runtime log |

### 2.3. Orchestrator, agent và LLM

| File | Nghiệp vụ gốc | Log cần truy vết |
|---|---|---|
| `src/orchestrator/orchestrator.py` | Điều phối reliability pipeline, detector L1-L4, notification/progress | Run ID, table, stage, detector result, duration, exception; thay `print()` trong `_notify` bằng logger |
| `src/orchestrator/engine.py` | ReAct loop, tool call, decision record, ghi `agent_traces` | Session, step, agent, tool, status, duration, provider/model; không log raw prompt/secret |
| `src/orchestrator/state_machine.py` | Quản lý state transition và gọi audit store | Invalid transition, state change; state mutation vẫn ghi audit |
| `src/orchestrator/react_engine.py` | ReAct execution path bổ sung | Start/end/error/fallback với session/run context |
| `src/agents/llm_adapter.py` | Adapter LLM của agent/rule proposal | Parse error và fallback; redact rule/prompt data |
| `src/services/llm.py` | Unified LLM provider, circuit breaker, spend/timeout | Provider, model, request ID, latency, fallback, token/cost, error class; tuyệt đối không log API key/prompt đầy đủ |
| `src/agents/*.py` | Profiler, anomaly, diagnosis, rule proposer, executor | Chỉ log boundary và kết quả tóm tắt; chi tiết trace theo `agent_traces` |
| `src/agents/tools/*.py` | Tool thao tác dataset/rules | Tool start/end/error, tên bảng/rule đã kiểm soát; không dump dataset |

### 2.4. Dữ liệu, ingestion và background service

| File | Nghiệp vụ gốc | Log cần truy vết |
|---|---|---|
| `src/db/connection.py` | DuckDB connection, schema/migration, locking | Init/open/close, migration failure, query/connection error; không log connection string |
| `src/db/schema.sql` | Schema của `audit_log`, `agent_traces` và domain tables | Không cần sửa cho runtime logging bản đầu |
| `src/db/migrations/*.sql` | Migration schema | Chỉ log migration success/failure từ connection layer |
| `src/services/audit.py` | Tạo audit event SHA-256 hash-chain và verify chain | Không biến mỗi audit row thành runtime log; chỉ log lỗi ghi/verify |
| `src/services/dataset_engine.py` | Profiling/rule execution/quarantine transaction | Dataset/table, row counts, transaction status, duration, errors |
| `src/services/ingestion/realtime_runner.py` | Realtime ingestion tick/state/day switching | Runner lifecycle, tick, dataset, day index, rows/errors, duration |
| `src/services/ingestion/streaming_worker.py` | Background ingestion worker | Worker lifecycle, batch, retry, exception |
| `src/services/ingestion/rule_applier.py` | Áp rule trên dữ liệu | Rule/table, affected/rejected count, transaction result |
| `src/services/ingestion/reset_service.py` | Reset ingestion state/data | Start/end/error; destructive reset phải được audit ở caller |
| `src/services/scheduler.py` | APScheduler lifecycle và scheduled task | Schedule ID/name, task status, duration, next run, exception |
| `src/services/alerting.py` | Tạo alert và dispatch webhook | Alert ID/severity/status; redact webhook URL và payload |
| `src/services/algolia_search.py` | Index/search/clear Algolia, fallback DuckDB | Provider, operation, count, duration, fallback/error |
| `src/services/websocket.py` / `ws_manager.py` | WebSocket connection/message routing | Connect/disconnect/error; không log payload chat đầy đủ |

### 2.5. Frontend và monitoring

| File | Nghiệp vụ gốc | Hướng xử lý |
|---|---|---|
| `frontend/src/main.tsx` | Bootstrap React, Sentry, ErrorBoundary | Giữ Sentry; không thêm logger phức tạp |
| `frontend/src/stores/chatStore.ts` | Chat/API/WebSocket state và audit response handling | Xóa `console.log('json:', json)`; chỉ giữ warning/error an toàn |
| `frontend/src/components/ErrorBoundary*` | Bắt lỗi render UI | Giữ error reporting; thêm context route/action nếu không nhạy cảm |
| `frontend/package.json` | Script build frontend | Dùng build/typecheck làm gate; không thêm dependency logging ở bản đầu |

## 3. Cấu trúc file đề xuất

### 3.1. Cấu trúc sau khi triển khai

```text
src/
├── observability/
│   ├── __init__.py
│   ├── logging_config.py       # Cấu hình logger một lần, đọc LOG_LEVEL
│   ├── context.py              # request_id/run_id/session_id bằng ContextVar
│   ├── redaction.py            # Che secret và giới hạn dữ liệu log
│   └── formatters.py           # Formatter thống nhất cho stdout/stderr
├── main.py                     # Gọi configure_logging; HTTP request middleware
├── config.py                   # Settings.log_level và observability settings
├── api/
├── agents/
├── db/
├── middleware/
├── orchestrator/
└── services/

tests/
├── test_logging.py             # Unit test config/context/redaction
├── test_request_logging.py     # Middleware request ID/timing/error
└── ...                         # Test hiện hữu không đổi nghiệp vụ

frontend/src/
└── stores/chatStore.ts         # Dọn debug console log; chưa cần logger module riêng

docs/
└── planning/LOGGING_PLAN.md    # Plan và source map này
```

### 3.2. Vai trò từng file mới

| File mới | Trách nhiệm | Không làm |
|---|---|---|
| `src/observability/logging_config.py` | Setup root logger, level, handler, formatter; idempotent khi import nhiều lần | Không ghi audit DB, không xử lý business logic |
| `src/observability/context.py` | Set/get/clear `request_id`, `run_id`, `session_id`, `actor` | Không tự decode JWT hoặc tự query DB |
| `src/observability/redaction.py` | Redact key nhạy cảm, truncate string/JSON lớn | Không thay đổi object nghiệp vụ gốc |
| `src/observability/formatters.py` | Chuyển LogRecord thành một dòng ổn định, có context | Không gửi log ra external service |
| `tests/test_logging.py` | Test độc lập cho các helper mới | Không phụ thuộc DB thật/LLM thật |
| `tests/test_request_logging.py` | Test middleware với FastAPI TestClient | Không kiểm tra nội dung business audit |

## 4. Đường truy gốc đề xuất

### 4.1. HTTP request

```text
Client
  -> src/main.py: log_request_timing
     -> tạo/nhận request_id
     -> src/api/middleware.py: kiểm tra role
        -> src/api/routes/*.py: nghiệp vụ API
           -> src/services/*.py hoặc src/orchestrator/*.py
              -> runtime logger + agent_traces/audit_log tùy loại sự kiện
     -> response: status, duration, X-Request-ID
```

### 4.2. Pipeline/agent

```text
API hoặc scheduler
  -> DataTrustOrchestrator / ReActEngine
     -> profiler/anomaly/diagnosis/rule proposer/executor
        -> services/dataset_engine.py hoặc tools
           -> agent_traces: timeline chi tiết của agent
           -> audit.py: mutation/hành động nghiệp vụ
           -> runtime logger: vận hành, lỗi, latency, fallback
```

### 4.3. HITL mutation

```text
User/Steward
  -> src/api/hitl.py
     -> permission check
     -> state_machine / executor
     -> src/services/audit.py
        -> audit_log + previous_event_hash + event_hash
     -> runtime logger chỉ ghi kết quả kỹ thuật và audit_id
```

## 5. Kế hoạch triển khai theo phase

### Phase 0 — Baseline và phạm vi

1. Chụp trạng thái test/lint/build hiện tại.
2. Lập danh sách `print()` thuộc runtime backend.
3. Phân loại mỗi log thành runtime, audit hoặc agent trace.
4. Xác nhận không thay đổi schema domain trong phase đầu.

### Phase 1 — Logging foundation

1. Tạo `src/observability/` và các file mới.
2. Thêm `Settings.log_level`.
3. Configure logger tại startup trước khi chạy lifespan.
4. Chọn stdout/stderr làm output duy nhất.
5. Thiết kế redaction/truncation.
6. Viết unit test cho setup, level và redaction.

### Phase 2 — HTTP correlation và middleware

1. Thêm `request_id` cho mọi HTTP request, trừ khi framework/health path cần xử lý đặc biệt.
2. Gắn context vào log record.
3. Đổi `print()` trong `log_request_timing()` thành logger.
4. Log method/path/status/duration.
5. Log exception bằng stack trace.
6. Trả `X-Request-ID` trong response.
7. Không ghi full query string nếu có nguy cơ chứa thông tin nhạy cảm.

### Phase 3 — Core business flow

Triển khai theo thứ tự ít rủi ro đến nhiều rủi ro:

1. `src/services/llm.py`: provider/model/latency/fallback/error.
2. `src/orchestrator/orchestrator.py`: pipeline stage và detector boundaries.
3. `src/orchestrator/engine.py`: session/step/tool/duration.
4. `src/services/ingestion/*`: worker/run/batch lifecycle.
5. `src/services/scheduler.py`: scheduled task lifecycle.
6. `src/services/dataset_engine.py`: transaction, row count và outcome.
7. `src/api/hitl.py` và `src/services/audit.py`: liên kết runtime event với `audit_id`, không duplicate audit record.

### Phase 4 — Dọn các `print()` và frontend

1. Chuyển `print()` runtime trong `src/main.py`, routes và services sang logger.
2. Giữ `print()` ở seed/CLI/render script nếu nó là output chủ đích cho người chạy lệnh.
3. Xóa debug `console.log()` trong `frontend/src/stores/chatStore.ts`.
4. Giữ Sentry cho unhandled exception và ErrorBoundary.

### Phase 5 — Verification và tài liệu

1. Chạy test logging mới.
2. Chạy test liên quan auth, HITL, audit, tools, e2e.
3. Chạy ruff backend.
4. Chạy frontend build/typecheck.
5. Kiểm tra container logs thủ công trong development.
6. Grep lại secret patterns và các `print()` runtime còn sót.
7. Cập nhật README/.env.example nếu contract cấu hình thay đổi.

## 5.1. Implementation checklist — thứ tự thực hiện

### Step 1 — Runtime logging foundation

Files tạo mới/sửa:

```text
src/observability/__init__.py
src/observability/logging_config.py
src/observability/context.py
src/observability/redaction.py
src/observability/formatters.py
src/config.py
src/main.py
```

Kết quả bắt buộc:

- `LOG_LEVEL` điều khiển runtime logger.
- Output mặc định đi `stdout/stderr`.
- Không tạo bảng DuckDB cho runtime log.
- Có timestamp, level, logger name, event và request/run context.
- Có redaction trước khi output.
- Có test cho level, formatter, context và secret masking.

### Step 2 — HTTP request correlation

Files sửa:

```text
src/main.py
src/api/middleware.py
src/middleware/auth.py
```

Kết quả bắt buộc:

- Mỗi request có `request_id`.
- Response trả header `X-Request-ID`.
- Runtime log của request có method, path, status và duration.
- Exception dùng `logger.exception()` và không log token/body nhạy cảm.

### Step 3 — LLM và orchestrator runtime events

Files sửa:

```text
src/services/llm.py
src/agents/llm_adapter.py
src/orchestrator/orchestrator.py
src/orchestrator/engine.py
src/orchestrator/react_engine.py
src/orchestrator/state_machine.py
```

Kết quả bắt buộc:

- Log provider/model/latency/fallback/error class.
- Log pipeline `run_id`, stage, table/dataset và outcome.
- Không log API key, full prompt, full completion hoặc dataframe.
- `agent_traces` tiếp tục ghi vào DuckDB, không bị thay bằng runtime log.

### Step 4 — Ingestion, scheduler và database runtime events

Files sửa:

```text
src/services/ingestion/realtime_runner.py
src/services/ingestion/streaming_worker.py
src/services/ingestion/rule_applier.py
src/services/ingestion/reset_service.py
src/services/scheduler.py
src/services/dataset_engine.py
src/db/connection.py
src/services/alerting.py
src/services/algolia_search.py
```

Kết quả bắt buộc:

- Có lifecycle start/end/error cho worker, scheduler, ingestion và DB.
- Có batch/run ID, row count, duration và retry/fallback.
- Webhook URL, DB URL và payload nhạy cảm được redaction.

### Step 5 — Audit và agent trace contract

Files kiểm tra/sửa có kiểm soát:

```text
src/services/audit.py
src/api/audit_store.py
src/api/routes/audit.py
src/api/traces.py
src/db/schema.sql
src/db/migrations/                 # chỉ thêm migration nếu thật sự cần
```

Kết quả bắt buộc:

- Audit tiếp tục lưu tại DuckDB `audit_log`.
- Agent trace tiếp tục lưu tại DuckDB `agent_traces`.
- Không duplicate một audit event thành nhiều runtime/audit record.
- Tìm audit theo action/actor/target/time.
- Tìm trace theo session/step/time.
- Chỉ thêm `request_id` hoặc `run_id` vào schema bằng migration nếu việc đưa vào `details`/trace context không đủ.

### Step 6 — Frontend và verification

Files sửa/kiểm tra:

```text
frontend/src/stores/chatStore.ts
frontend/src/services/api.ts
frontend/src/components/workspace/AgentTracesTab.tsx
tests/test_logging.py
tests/test_request_logging.py
```

Kết quả bắt buộc:

- Frontend không còn debug `console.log` dư thừa.
- UI vẫn lấy audit từ `/api/v1/audit`.
- UI vẫn lấy trace từ `/api/v1/traces/...`.
- Backend test/lint pass và frontend build pass.

## 6. Tiêu chí nghiệm thu

- `LOG_LEVEL` thực sự điều khiển level runtime.
- Logger được cấu hình đúng một lần và không nhân đôi handler.
- Mỗi request có `request_id`, method, path, status và duration.
- Exception có stack trace trong log.
- Pipeline/LLM/ingestion/scheduler có run/session context.
- Không log API key, JWT, password, webhook secret hoặc raw prompt nhạy cảm.
- `audit_log` vẫn hash-chain và các test audit hiện hữu vẫn pass.
- `agent_traces` vẫn phục vụ được UI `/traces`.
- Không tạo thêm database/logging service ở bản đầu.
- Backend lint/test và frontend build pass.

## 7. Kế hoạch test tối thiểu

```bash
uv run pytest tests/test_logging.py tests/test_audit_chain.py tests/test_e2e.py -q
uv run pytest tests/test_hitl.py tests/test_tools.py tests/test_quarantine_idempotency.py -q
uv run ruff check src/ tests/
pnpm --dir frontend run build
```

Nếu các test mục tiêu pass, mới cân nhắc chạy toàn bộ test suite.

## 8. Rủi ro và cách giảm thiểu

| Rủi ro | Cách giảm thiểu |
|---|---|
| Log quá nhiều làm khó đọc | Chỉ log boundary, dùng level và sampling sau này nếu cần |
| Lộ dữ liệu nhạy cảm | Redaction tập trung + test key nhạy cảm |
| Duplicate log do handler/import | Setup idempotent, test số handler |
| Nhầm runtime log với audit log | Giữ ranh giới theo bảng ở Phase 0 |
| Làm hỏng trace UI | Không đổi schema `agent_traces` trong phase đầu |
| Logger làm chậm request | Không serialize payload lớn; giới hạn/truncate và không log dataframe |
| Sentry và logger ghi trùng exception | Logger cho vận hành; Sentry cho exception/monitoring, tránh capture thủ công mọi log |

## 9. Phương án tốt hơn được đề xuất

Phương án ban đầu có thể là thêm logger trực tiếp vào từng file. Cách đó nhanh nhưng dễ tạo format không đồng nhất và khó kiểm soát secret.

Phương án tốt hơn cho codebase này là:

1. Tạo lớp `src/observability/` nhỏ, chỉ chứa logging infrastructure.
2. Dùng `ContextVar` để correlation ID tự đi theo request/background context.
3. Giữ `audit_log` và `agent_traces` như hai storage nghiệp vụ hiện có.
4. Runtime log chỉ đi stdout/stderr để Docker/Sentry/collector bên ngoài xử lý sau này.
5. Triển khai theo boundary quan trọng, không rải log vào từng dòng xử lý.

Phương án này giữ ít file mới, không thêm dependency, không đụng schema và vẫn mở đường cho JSON logging hoặc OpenTelemetry sau này nếu production thực sự cần.

## 10. Những việc chưa nằm trong phiên bản đầu

- Không triển khai ELK, Loki, Grafana hoặc log database.
- Không ghi mọi thao tác đọc dữ liệu vào `audit_log`.
- Không lưu raw prompt/completion của LLM.
- Không viết logger riêng phức tạp cho frontend.
- Không sửa các script render hình ảnh chỉ vì chúng có `print()`.
- Không thay Sentry bằng logging tự xây dựng.
