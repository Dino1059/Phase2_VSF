# Kế hoạch 6 tuần — Autonomous E2E Testing Agent trên DataTrust OS (P-086)
 
**SUT (hệ thống bị kiểm thử):** DataTrust OS v5 — FastAPI + React 19 + DuckDB, UI `localhost:3000`, API `localhost:8000`.
**Agent kiểm thử:** lớp mới *bên cạnh* app, tái sử dụng ReAct + `agent_traces`, **không** thay stack FastAPI/React/pytest/uv/pnpm.
**Browser driver:** Playwright (thêm mới). Puppeteer đã có ở root `package.json` nhưng **không dùng cho test** (chỉ dep mồ côi). Playwright được chọn vì locator engine, trace viewer, shard/parallel, retry — lý do kỹ thuật, không phải đổi stack app.
**SKILL.md:** không có file đính kèm trong workspace; spec lấy từ prompt (reason → plan → act → observe → adapt → report; Web UI + API; self-healing locator; flaky detection; parallel; Excel/CSV/JSON; audit trail).
 
Mọi số liệu dưới đây ghi rõ **đo thực tế** vs **ước tính**. Chưa chạy baseline browser nên số tuần 1–2 chủ yếu là inventory + mục tiêu ước tính.
 
---
 
## 0. Hiện trạng (bằng chứng repo)
 
| Thành phần SKILL | Hiện trạng P-086 | Bằng chứng |
|---|---|---|
| Reason → plan → act → observe | Có ReAct **cho data quality**, không cho UI test | `src/orchestrator/engine.py` (`Thought` / `Action` / Observation, `max_steps<=10`) |
| Adapt | Repair loop bị chặn bởi HITL stop + tool allowlist; LLM trong `tests/test_e2e.py` bị **mock** | `engine.py` HITL stop; `tests/test_e2e.py` `MagicMock` |
| Report | Trace schema + eval detector/RCA; không có báo cáo journey UI | `schemas/agent-trace.schema.json`; `docs/evaluation.md` |
| Web UI E2E | **Không có** Playwright/Vitest/Cypress. Frontend CI chỉ `tsc && vite build` | `frontend/package.json`; `.github/workflows/ci.yml` job `frontend-quality` |
| API test | Nhiều TestClient pytest (~757 collected, **đo thực tế** trong `docs/evaluation.md`) | `tests/`, CI `uv run pytest tests/` |
| `test_e2e.py` | Integration backend giả (seed DuckDB + mock LLM), **không** mở browser | `tests/test_e2e.py` |
| QA UI gates | Grep `data-testid` / source string, không click UI | `tests/test_qa_t086_gates.py` |
| Self-healing locator | **Không có** | Không matcher Playwright / fallback locator |
| Flaky detection | Ghi nhận flake HITL 403, không có detector | `docs/evaluation.md`: “local may hit HITL 403 flakes on ACL-era filters” |
| Parallel UI | Không | Không job Playwright shard |
| Test data Excel/CSV/JSON cho case E2E | Domain CSV/JSON có; **không** có workbook test case. Không `openpyxl`/`xlsx` | Grep `xlsx`/`openpyxl` = 0 |
| Audit trail | `agent_traces` cho profiler/anomaly/HITL, không cho test run UI | schema + `agent_traces` DDL |
| `data-testid` | Có rải rác (auth, HITL, eval, quarantine, chat) — **không đủ** cho full journey | `frontend/src/**/*.tsx` |
| Routes UI cần cover | `/`, `/dashboard`, `/dashboard/ingestion`, `/workspace`, `/chat/:id`, `/operations/:view` | `frontend/src/App.tsx` |
 
---
 
## 1. Nhược điểm (đánh số — tham chiếu chéo tuần)
 
### W1 — Không có E2E browser thật (ảnh hưởng: **cao**)
Pytest + TestClient không bắt regression routing, RBAC chrome, ingest UI, HITL Steward vs Analyst. `test_qa_t086_gates.py` chỉ assert chuỗi source. CI frontend không chạy UI.
 
### W2 — Vòng reason→plan→act→observe→adapt chưa tồn tại cho testing (ảnh hưởng: **cao**)
ReAct hiện phục vụ DQ agent. Không có planner sinh test graph từ Excel, không có observer DOM/network, không có adapt khi locator gãy. `test_e2e.py` kết thúc bằng mock `FINISH`.
 
### W3 — Độ phủ journey UI/API lệch (ảnh hưởng: **cao**)
API/unit dày; UI mỏng. Journey nghiệp vụ (landing ingest → promote → workspace profile → HITL propose/approve → operations eval) **chưa** được mã hóa thành case tái lập. Roles Admin/Steward/Analyst/Viewer + ACL `steward_a`/`steward_b` chỉ được test API/source.
 
### W4 — Self-healing locator = 0 (ảnh hưởng: **cao**)
Không fallback `data-testid` → role → text → CSS; không học locator mới. UI React 19 dễ gãy class Tailwind. Ước tính (chưa đo): >40% fail UI sẽ là locator drift nếu viết test CSS thuần.
 
### W5 — Flaky không đo, không phân loại (ảnh hưởng: **cao**)
`docs/evaluation.md` ghi HITL 403 flake (quan sát tài liệu, **không** có tỷ lệ N-run). Không quarantine test, không tách “product bug / timing / ACL / LLM nondeterminism”. LLM ON làm UI chat không deterministic.
 
### W6 — Không parallel UI + không baseline thời gian (ảnh hưởng: **trung bình**)
Không đo wall-clock suite vs sequential. Mục tiêu tiết kiệm song song **chưa có số thực**.
 
### W7 — Test data Excel/CSV/JSON cho agent chưa có schema (ảnh hưởng: **trung bình**)
Domain data (`data_new/`) không phải test case. Agent SKILL yêu cầu đọc Excel/CSV/JSON; thiếu contract cột (role, route, steps, expected, dataset_key).
 
### W8 — Audit trail test run thiếu (ảnh hưởng: **trung bình**)
`agent_traces` không ghi screenshot, trace Playwright, locator đã heal, fixture row. BTC/đồ án khó chứng minh vòng observe→adapt.
 
### W9 — Eval/benchmark lệch miền (ảnh hưởng: **cao** cho đồ án)
Eval hiện có: detector F1, RCA top-1 (`docs/evaluation.md`, **đo thực tế** Ngan GT P/R/F1 ~0.68/0.93/0.79). **Không** có first-pass UI pass rate, heal rate, flake rate, parallel speedup. Không thể báo cáo tiến bộ agent kiểm thử bằng số hiện có.
 
### W10 — LLM trong E2E bị mock / provider OFF path chưa là test journey (ảnh hưởng: **trung bình**)
Chat LLM OFF có screenshot (`docs/screenshots/chat-llm-off.png`) nhưng không có automated journey. Agent kiểm thử nếu gọi LLM thật sẽ tốn cost + flake.
 
### W11 — `data-testid` không đồng bộ contract (ảnh hưởng: **trung bình**)
Một số testid có (`eval-gt-metrics`, `hitl-role-gate` gián tiếp, `llm-mode-toggle`); thiếu ingest promote, landing day COUNT, operations traces, persona switch đầy đủ.
 
### W12 — Puppeteer mồ côi dễ gây nhiễu stack (ảnh hưởng: **thấp**)
Root `package.json` chỉ `puppeteer`. Không dùng trong CI. Rủi ro người mới cài nhầm driver. Quyết định: **không** xây agent trên Puppeteer; Playwright cho test; có thể gỡ Puppeteer sau (tuần 6, tùy chọn).
 
---
 
## 2. Nguyên tắc 6 tuần (không đổi stack)
 
- Giữ FastAPI, React 19, Vite, pytest, DuckDB, ReAct, HITL, CI self-hosted.
- Agent test chạy **process riêng** (`e2e_agent/`), gọi UI + API như user.
- Tái sử dụng `ReActEngine` (tool allowlist mới: `goto`, `click`, `fill`, `expect`, `api_request`, `heal_locator`, `record_flake`) hoặc wrapper mỏng — không viết orchestrator mới từ đầu.
- LLM chỉ dùng cho **plan + heal khi fallback hết**; bước ổn định chạy Playwright thuần (giảm flake W5/W10).
- Ưu tiên W1, W2, W3, W4, W5, W9 trước; W6/W7/W8 song song khi đã có 1 golden path.
 
**Golden journeys (tuần 1 chốt 8, mở rộng tuần 3–5):**
1. Landing public
2. Login Steward + dashboard
3. Ingest upload + promote + day COUNT
4. Workspace bind dataset + profile (LLM OFF)
5. HITL propose (Steward)
6. HITL Analyst **không** Approve (403 + UI ẩn)
7. Operations traces / eval vs GT
8. ACL steward_a ↛ dataset B
 
---
 
## 3. Lịch 6 tuần
 
| Tuần | Mục tiêu | Tech | Eval | Deliverable | Rủi ro | Xử lý |
|---|---|---|---|---|---|---|
| **1** | Baseline + skeleton agent + 8 journey spec | Inventory route/`data-testid`/API; scaffold `e2e_agent/` (Playwright + pytest plugin); schema fixture Excel/CSV/JSON; ghi trace tối thiểu vào JSONL (chưa DB) | **Đo thực tế:** đếm testid, route, pytest API. **Chạy tay** 8 journey, ghi pass/fail lần đầu (N=3). **Ước tính mục tiêu** first-pass ≥ 0.50 sau khi có 8 spec (chưa heal) | `e2e_agent/README.md`; `e2e_agent/fixtures/journeys.xlsx` + `.csv` + `.json`; `docs/e2e-agent/baseline-week1.json`; 8 spec YAML; Playwright `smoke_landing.spec.ts` 1 case xanh | Staging d086 khác local; LLM ON làm journey 4 flake → **cố định LLM OFF** tuần 1 | W1, W2, W7, W9 (baseline), W11 (inventory) |
| **2** | Vòng reason→plan→act→observe trên 8 journey (chưa heal sâu) | Tool: `plan_from_fixture`, `goto/click/fill/expect`, `api_get/post` (Test token sẵn `create_access_token`); ReAct `max_steps` riêng (ước tính 20, không đụng cap 10 của DQ agent — **wrapper riêng** để không phá HITL DQ); observe: screenshot + network HAR | First-pass pass rate trên 8 journey × 3 run (**đo**). Mean steps/journey (**đo**). So API-only vs UI+API cho journey 6 (Analyst 403) — **đo** | `e2e_agent/runner.py`; `e2e_agent/tools/pw_tools.py`; `e2e_agent/tools/api_tools.py`; report HTML Playwright; `eval/e2e_agent/week2_metrics.json` | ReAct DQ `max_steps<=10` nếu reuse nhầm class — **bắt buộc engine riêng**. Auth cookie vs Bearer | W2, W3, W10 (LLM OFF path) |
| **3** | Self-healing locator + testid contract | Locator resolver: testid → getByRole → getByText → CSS; heal ghi `locator_store.json`; PR thêm `data-testid` ingest/HITL/operations còn thiếu; cấm heal vào locator không ổn định (nth, dynamic class) | Heal success rate trên **fault set** tuần 3: cố ý đổi 10 testid (**đo**, N=10×3). False-heal rate (heal sai element) — **đo** bằng assert hậu điều kiện API | `frontend` testid patch (scoped); `e2e_agent/healing/resolver.py`; `locator_store.json`; `eval/e2e_agent/heal_faultset.json`; diff testid coverage tuần 1 vs 3 | Heal “thành công” nhưng click nhầm (false heal) nguy hiểm hơn fail — bắt buộc oracle API | W4, W11 |
| **4** | Flaky detection + parallel | Retry 2 + video on fail; detector: cùng test fail **không ổn định** trên N=5 (pass≥1 và fail≥1 → flaky); quarantine file; Playwright shard `--workers` + pytest-xdist chỉ cho API helper; LLM chat journey **cách ly** (tag `nondeterministic`) | Flake rate = flaky / total (**đo** N=5). Wall-clock sequential vs workers=2,4 (**đo**, máy CI self-hosted). Speedup **đo**, không ước | `e2e_agent/flaky.py`; `quarantine.txt`; CI job `e2e-ui` (nightly hoặc `workflow_dispatch` trước); `eval/e2e_agent/week4_parallel.json` | Self-hosted timeout 15–25 phút (`ci.yml`) — shard quá mức OOM; HITL 403 flake thật (W5) có thể là bug product → escalate, không heal | W5, W6 |
| **5** | Adapt + audit trail đầy đủ + Excel round-trip | Persist run vào DuckDB bảng `e2e_runs` / `e2e_steps` (song song `agent_traces`, **không** ghi đè schema DQ); screenshot/trace path; map step ↔ fixture row; adapt: replan tối đa 1 lần khi oracle fail (không phải locator); writer Excel report | Audit completeness = bước có (thought, action, observation, artifact) / tổng bước (**đo**, target ≥ 0.95). Replan rescue rate (**đo** trên 5 injected assertion fail) | SQL migration `e2e_runs`; `e2e_agent/report.xlsx`; UI tối thiểu **hoặc** markdown report `docs/e2e-agent/week5-audit.md`; schema JSON | Migration đụng `vingroup_pilot.db` — dùng DB riêng `data/e2e_agent.duckdb` | W8, W2 (adapt), W7 |
| **6** | Benchmark đóng băng + báo cáo đồ án | Frozen eval set 20 journey (8 core + 12 biến thể role/ACL/empty/error); so 3 mode: C0 script Playwright cố định, C1 agent không heal, A1 agent heal+flaky+parallel; không đổi metric giữa tuần | Bảng metric mục 4, **toàn bộ đo** trên frozen set. So sánh vs tuần 2. Công bố khoảng tin cậy binomial cho pass rate (n=20×5) | `eval/e2e_agent/frozen_set_v1.json`; `eval/e2e_agent/benchmark_week6.md`; slide số liệu; optional xóa Puppeteer root | Frozen set quá nhỏ → variance cao; LLM heal tốn phí — chốt provider + budget | W9, W12 |
 
**Song song ít rủi ro:** tuần 2–3 viết fixture Excel; tuần 3 testid có thể tách PR frontend; tuần 4 CI `workflow_dispatch` không chặn merge cho đến khi flake rate đo được.
 
---
 
## 4. Eval metrics tổng thể (công thức)
 
Ký hiệu: \(T\) = số test trong frozen set; \(R\) = số lần lặp độc lập; \(P_{t,r}=1\) nếu test \(t\) **pass lần chạy \(r\)** (kể cả sau heal trong cùng run, trừ khi metric nói khác).
 
| # | Metric | Công thức | Dùng khi | Target tuần 6 (ước tính, sẽ thay bằng số đo) |
|---|---|---|---|---|
| M1 | **First-pass pass rate** | \(\mathrm{FP} = \frac{1}{TR}\sum_{t,r} P^{\mathrm{no\ heal}}_{t,r}\) — pass **trước** heal/replan | W1, W3, W9 | ≥ 0.70 |
| M2 | **Pass rate (kèm heal)** | \(\mathrm{PR} = \frac{1}{TR}\sum_{t,r} P_{t,r}\) | W4 | ≥ 0.90 |
| M3 | **Heal success** | \(\mathrm{HS} = \frac{N_{\mathrm{heal\ đúng}}}{N_{\mathrm{locator\ miss}}}\) — đúng = oracle API/UI hậu điều kiện pass | W4 | ≥ 0.80 trên fault set |
| M4 | **False-heal rate** | \(\mathrm{FH} = \frac{N_{\mathrm{heal\ sai\ element}}}{N_{\mathrm{heal\ attempt}}}\) | W4 | ≤ 0.05 |
| M5 | **Flake rate** | Test flaky nếu trên \(R=5\), \(0 < \sum_r P_{t,r} < R\). \(\mathrm{FR} = N_{\mathrm{flaky}} / T\) | W5 | ≤ 0.10 |
| M6 | **Parallel speedup** | \(\mathrm{SU}(w) = t_{\mathrm{seq}} / t_{w}\) ; efficiency \(= \mathrm{SU}(w)/w\) | W6 | SU(4) ≥ 2.0 (**đo** trên CI) |
| M7 | **Time saving vs sequential** | \((t_{\mathrm{seq}}-t_{w})/t_{\mathrm{seq}}\) | W6 | ≥ 0.40 tại w=4 |
| M8 | **Mean steps** | Trung bình số ReAct/Playwright steps / journey pass | W2 | không tăng >20% khi bật heal |
| M9 | **Audit completeness** | Tỷ lệ step có đủ thought, action, observation, artifact_uri | W8 | ≥ 0.95 |
| M10 | **Journey coverage** | Số route+role đã có case / số ô ma trận (6 route × 4 role = 24) | W3 | ≥ 0.70 (17/24) |
| M11 | **API–UI consistency** | Với journey RBAC: \(1\) nếu UI ẩn nút **và** API 403 khớp | W3 | 1.0 trên Analyst approve |
| M12 | **Cost/run** | Token LLM heal + thời gian CI (phút) | W10 | heal tokens ≤ 2× C1 script |
| M13 | **Quarantine precision** | Flaky thật / test bị quarantine | W5 | ≥ 0.80 |
 
**Gate đồ án (tuần 6), tương tự Agentic Gate DQ nhưng cho testing:**
 
- Bắt buộc: \(\mathrm{PR} \ge 0.85\), \(\mathrm{FH} \le 0.05\), \(\mathrm{FR} \le 0.15\), \(\mathrm{Audit} \ge 0.90\)
- Thắng thêm **một** trong hai: \(\mathrm{FP}_{A1}-\mathrm{FP}_{C1} \ge 0.10\) **hoặc** \(\mathrm{SU}(4) \ge 2.0\)
 
Baseline C0/C1/A1 **đo từ tuần 2 và tuần 6**, không dùng số detector F1 0.79 (khác miền).
 
---
 
## 5. Cấu trúc thư mục đề xuất (không đụng `src/` DQ trừ testid)
 
```
e2e_agent/
  runner.py              # reason→plan→act→observe→adapt→report
  tools/pw_tools.py
  tools/api_tools.py
  healing/resolver.py
  flaky.py
  fixtures/journeys.xlsx|csv|json
  locator_store.json
eval/e2e_agent/          # metrics theo tuần
data/e2e_agent.duckdb    # audit riêng
docs/e2e-agent/          # baseline + báo cáo
```
 
CI: job mới `e2e-ui` `workflow_dispatch` tuần 4; gắn vào PR **chỉ sau** khi FR đo ≤ 0.15 (tuần 6). Không nhồi vào `backend-quality` 25 phút.
 
---
 
## 6. Việc không làm trong 6 tuần
 
- Không thay ReAct DQ, HITL, DuckDB warehouse.
- Không Selenium, không Cypress, không viết lại frontend.
- Không dùng LLM để assert nghiệp vụ (oracle = Playwright expect + API JSON).
- Không claim số heal/flake trước khi có `eval/e2e_agent/*.json`