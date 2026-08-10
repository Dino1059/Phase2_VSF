# 🚀 DataTrust OS v4.0 — Master Execution Plan

> **Branch:** `v4`
> **Status:** APPROVED — Ready for Agent Execution
> **Created:** 2026-08-04
> **Hard Deadline:** 2026-08-24 (DONE before 25th August)
> **Problem Bank:** DATA-02 — "AI Agent xây dựng & kiểm tra Data Quality và phát hiện bất thường"
> **Team:** Thanh (orchestrator/eval), Ngân (schema/agent), Dũng (pipeline/NLP), Huyền (UX/deploy)
> **Executor:** AI Coding Agents (phases delegated to subagents)

---

## 🎯 Strategic Problem Statement

### Lecturer Feedback
> *"Bài toán hơi yếu để xây agent — có thể không cần agent"*

### Response: Cross-Domain Root-Cause Diagnosis (True Agentic Necessity)

A static SQL/regex rule **CANNOT**:
1. Parse Vietnamese teen-code slang (`"ko sac dc"` → `"không sạc được"`)
2. Cross-correlate complaint timestamps with V-GREEN hardware logs (85.5°C)
3. Link VinFast BMS telemetry faults (0x4B) to customer-reported symptoms
4. Propose executable quarantine rules with HITL approval gate
5. Dynamically decide which tools to call based on intermediate results

**DataTrust OS v4.0** = Multi-Tool ReAct Agentic Engine solving a problem that deterministic scripts fundamentally cannot.

---

## 📐 Architecture Decisions (Locked)

| Decision | Choice | Rationale |
|---|---|---|
| **LLM** | Gemma-4 via Google AI Studio (free tier) | Open-weight, free, structured output support |
| **Backend** | FastAPI (Python) in `/src` | Existing codebase, async, auto OpenAPI |
| **Frontend** | Next.js + TypeScript + TailwindCSS + Lucide-React in `/frontend` | Production SSR, type-safe, modern |
| **Database** | DuckDB (embedded) | Zero-config, 10-100x faster analytics than SQLite, Parquet-native |
| **API Contract** | OpenAPI codegen → React Query (TanStack Query) | Type-safe, auto-generated client, secure |
| **NLP** | Custom Vietnamese teen-code dictionary (built from scratch) | Domain-specific, no external dependency |
| **i18n** | Dual language (Vietnamese + English) with toggle | Course requirement |
| **Testing** | pytest only (backend) | 125+ test gate |
| **Deployment** | Docker Compose (backend + frontend + DuckDB) | Reproducible demo |
| **Repo** | Monorepo: `/frontend` (Next.js) + `/src` (FastAPI) | Single repo, shared types |

---

## 📊 5 Lecturer Evaluation Questions — Compliance Matrix

| # | Question | Answer | Evidence Phase |
|---|---|---|---|
| 1 | Does the work need language processing? | **YES** — Vietnamese teen-code NLP + EV IoT domain literacy | Phase 3 |
| 2 | Does the input have enough context for AI? | **YES** — 4 deterministic tools provide dynamic multi-source context | Phase 5 |
| 3 | Have we set quan-metrics? | **YES** — Precision/Recall, Compile Rate, Cost/Latency, Human Time Saved | Phase 9 |
| 4 | Are AI mistakes well-considered? | **YES** — HITL gate, Quarantine isolation, Fail-safe abstention | Phase 6 |
| 5 | Are there alternatives with lower costs? | **YES** — C0/C1/A1 benchmark proves A1 is the only viable architecture | Phase 9 |

---

## 🗓️ Sprint ↔ Phase Mapping

| Sprint | Dates | Phases | Focus |
|---|---|---|---|
| **Sprint 1** | 03 Aug – 07 Aug | Phase 1, 2 | Foundation: DuckDB migration, data scraping |
| **Sprint 2** | 07 Aug – 11 Aug | Phase 3, 4 | NLP Engine + Tool Layer |
| **Sprint 3** | 11 Aug – 15 Aug | Phase 5, 6 | ReAct Engine + HITL Gate |
| **Sprint 4** | 15 Aug – 19 Aug | Phase 7, 8 | Frontend Dashboard + i18n |
| **Sprint 5** | 19 Aug – 23 Aug | Phase 9, 10, 11 | Benchmark + Docker + Demo |

---

# PHASE 1: Database Migration & Schema Foundation

> **Sprint:** 1 (03 Aug – 07 Aug)
> **Owner:** Agent-Worker-DB
> **Files:** `/src/db/`, `/src/models/schemas.py`
> **Duration:** 1 day
> **Depends on:** Nothing (first phase)

## 1.1 Objective

Replace SQLite (`datatrust.db`) with DuckDB for 10-100x analytical query performance. Create the unified schema for all 4 VinGroup data domains.

## 1.2 Tasks

### T1.1: Install DuckDB dependency
- **File:** `pyproject.toml`
- **Action:** Add `duckdb>=1.3.0` to dependencies
- **Command:** `uv add duckdb`
- **Verify:** `uv run python -c "import duckdb; print(duckdb.__version__)"`

### T1.2: Create DuckDB connection module
- **File:** `src/db/__init__.py` [NEW]
- **File:** `src/db/connection.py` [NEW]
- **Action:** Implement `DuckDBManager` singleton class
  - `get_connection() -> duckdb.DuckDBPyConnection`
  - `init_schema()` — creates all tables on first run
  - `close()` — graceful shutdown
  - Database file: `data/datatrust_v4.duckdb`
- **Contract:**
  ```python
  class DuckDBManager:
      def __init__(self, db_path: str = "data/datatrust_v4.duckdb"): ...
      def get_connection(self) -> duckdb.DuckDBPyConnection: ...
      def init_schema(self) -> None: ...
      def execute(self, query: str, params: list = None) -> list: ...
      def close(self) -> None: ...
  ```

### T1.3: Define unified schema DDL
- **File:** `src/db/schema.sql` [NEW]
- **Tables:**
  ```sql
  -- Raw immutable snapshots
  CREATE TABLE IF NOT EXISTS raw_snapshots (
      id VARCHAR PRIMARY KEY,
      source_name VARCHAR NOT NULL,
      file_path VARCHAR NOT NULL,
      sha256_hash VARCHAR(64) NOT NULL,
      row_count INTEGER,
      column_count INTEGER,
      ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  -- Xanh SM customer feedback
  CREATE TABLE IF NOT EXISTS xanhsm_feedback (
      id INTEGER PRIMARY KEY,
      review_text VARCHAR,
      normalized_text VARCHAR,
      rating FLOAT,
      location VARCHAR,
      timestamp TIMESTAMP,
      source VARCHAR,  -- 'google_maps', 'play_store', 'shopee', 'csv'
      aspects JSON,    -- extracted aspects from NLP
      snapshot_id VARCHAR REFERENCES raw_snapshots(id)
  );

  -- V-GREEN charging station telemetry
  CREATE TABLE IF NOT EXISTS vgreen_telemetry (
      id INTEGER PRIMARY KEY,
      station_id VARCHAR,
      station_name VARCHAR,
      temperature_celsius FLOAT,
      voltage FLOAT,
      current_amps FLOAT,
      duty_cycle FLOAT,
      status VARCHAR,
      fault_code VARCHAR,
      timestamp TIMESTAMP,
      snapshot_id VARCHAR REFERENCES raw_snapshots(id)
  );

  -- VinFast EV BMS telemetry
  CREATE TABLE IF NOT EXISTS vinfast_bms (
      id INTEGER PRIMARY KEY,
      vehicle_id VARCHAR,
      battery_soc FLOAT,
      battery_voltage FLOAT,
      cell_temp_max FLOAT,
      cell_temp_min FLOAT,
      bms_fault_code VARCHAR,
      charging_station_id VARCHAR,
      timestamp TIMESTAMP,
      snapshot_id VARCHAR REFERENCES raw_snapshots(id)
  );

  -- Xanh SM ride trips
  CREATE TABLE IF NOT EXISTS xanhsm_trips (
      id INTEGER PRIMARY KEY,
      trip_id VARCHAR,
      driver_id VARCHAR,
      pickup_location VARCHAR,
      dropoff_location VARCHAR,
      distance_km FLOAT,
      fare_vnd FLOAT,
      duration_minutes FLOAT,
      rating FLOAT,
      timestamp TIMESTAMP,
      snapshot_id VARCHAR REFERENCES raw_snapshots(id)
  );

  -- Profiling results
  CREATE TABLE IF NOT EXISTS profile_results (
      id VARCHAR PRIMARY KEY,
      snapshot_id VARCHAR REFERENCES raw_snapshots(id),
      column_name VARCHAR,
      dtype VARCHAR,
      null_count INTEGER,
      null_pct FLOAT,
      unique_count INTEGER,
      min_val VARCHAR,
      max_val VARCHAR,
      mean_val FLOAT,
      std_val FLOAT,
      profiled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  -- Quality rules (proposed by agent, approved by HITL)
  CREATE TABLE IF NOT EXISTS quality_rules (
      id VARCHAR PRIMARY KEY,
      snapshot_id VARCHAR REFERENCES raw_snapshots(id),
      rule_name VARCHAR,
      rule_type VARCHAR,  -- 'range', 'null_check', 'cross_field', 'semantic', 'anomaly'
      rule_expression VARCHAR,
      confidence FLOAT,
      status VARCHAR DEFAULT 'proposed',  -- 'proposed', 'approved', 'rejected', 'edited'
      proposed_by VARCHAR,  -- 'agent_a1', 'agent_c1', 'human'
      approved_by VARCHAR,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      approved_at TIMESTAMP
  );

  -- Quarantine table
  CREATE TABLE IF NOT EXISTS quarantine (
      id VARCHAR PRIMARY KEY,
      source_table VARCHAR,
      source_row_id INTEGER,
      rule_id VARCHAR REFERENCES quality_rules(id),
      reason VARCHAR,
      original_data JSON,
      quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      lineage_hash VARCHAR(64)
  );

  -- Audit trail
  CREATE TABLE IF NOT EXISTS audit_log (
      id VARCHAR PRIMARY KEY,
      action VARCHAR,
      actor VARCHAR,
      target_table VARCHAR,
      target_id VARCHAR,
      details JSON,
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  -- Agent execution traces
  CREATE TABLE IF NOT EXISTS agent_traces (
      id VARCHAR PRIMARY KEY,
      session_id VARCHAR,
      agent_type VARCHAR,
      step_index INTEGER,
      thought VARCHAR,
      action VARCHAR,
      tool_name VARCHAR,
      tool_input JSON,
      tool_output JSON,
      observation VARCHAR,
      tokens_used INTEGER,
      cost_usd FLOAT,
      duration_ms INTEGER,
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```

### T1.4: Migrate existing CSV data into DuckDB
- **File:** `src/db/seed.py` [NEW]
- **Action:** Script to ingest `data/vingroup_real/*.csv` into DuckDB tables
- **Input files:**
  - `data/vingroup_real/real_xanh_sm_customer_feedback.csv` → `xanhsm_feedback`
  - `data/vingroup_real/real_vgreen_charging_stations.csv` → `vgreen_telemetry`
  - `data/vingroup_real/real_vinfast_ev_telemetry.csv` → `vinfast_bms`
  - `data/vingroup_real/real_xanh_sm_trips.csv` → `xanhsm_trips`
- **Each ingestion must:**
  1. Compute SHA-256 of source CSV
  2. Insert `raw_snapshots` record
  3. `COPY` CSV data into target table with `snapshot_id` FK
- **Command:** `uv run python -m src.db.seed`

### T1.5: Update `src/config.py` for DuckDB
- **File:** `src/config.py` [MODIFY]
- **Action:** Add `DUCKDB_PATH` setting, remove SQLite references

### T1.6: Update `src/main.py` lifespan
- **File:** `src/main.py` [MODIFY]
- **Action:** Replace SQLite initialization with `DuckDBManager.init_schema()` in lifespan

## 1.3 Verification

```bash
uv run pytest tests/test_db.py -v  # New test file
# Expected: All tables created, 4 CSVs ingested, SHA-256 hashes match
```

## 1.4 Exit Criteria

- [ ] DuckDB file created at `data/datatrust_v4.duckdb`
- [ ] All 10 tables created with correct schema
- [ ] 4 VinGroup CSVs ingested with SHA-256 lineage
- [ ] `raw_snapshots` table has 4 records
- [ ] Old SQLite code paths removed or deprecated

---

# PHASE 2: Vietnamese Customer Feedback Data Collection

> **Sprint:** 1 (03 Aug – 07 Aug)
> **Owner:** Agent-Worker-Data
> **Files:** `scripts/scrape_*.py`, `data/scraped/`
> **Duration:** 2 days
> **Depends on:** Phase 1 (DuckDB must exist to store results)

## 2.1 Objective

Collect real Vietnamese customer feedback from multiple public sources to train and validate the teen-code NLP engine. Target: 1000+ unique reviews across 3+ sources.

## 2.2 Tasks

### T2.1: Google Maps V-GREEN station reviews scraper
- **File:** `scripts/scrape_google_maps.py` [NEW]
- **Action:** Scrape Google Maps reviews for V-GREEN / VinFast charging stations in HCMC, Hanoi, Da Nang
- **Method:** Use `playwright` or `selenium` to extract review text, rating, location, timestamp
- **Output:** `data/scraped/google_maps_vgreen_reviews.csv`
- **Columns:** `review_text, rating, location, reviewer_name, timestamp, source`
- **Target:** 300+ reviews
- **Dependencies:** `uv add playwright && uv run playwright install chromium`

### T2.2: Google Play Store Xanh SM app reviews scraper
- **File:** `scripts/scrape_play_store.py` [NEW]
- **Action:** Scrape Google Play reviews for Xanh SM app (`com.xanhsm.passenger`)
- **Method:** Use `google-play-scraper` Python library
- **Output:** `data/scraped/play_store_xanhsm_reviews.csv`
- **Columns:** `review_text, rating, thumbs_up, reply_text, timestamp, source`
- **Target:** 500+ reviews
- **Dependencies:** `uv add google-play-scraper`

### T2.3: Shopee VinFast product reviews scraper
- **File:** `scripts/scrape_shopee.py` [NEW]
- **Action:** Scrape Shopee.vn reviews for VinFast accessories/chargers
- **Method:** Shopee API or browser scraping
- **Output:** `data/scraped/shopee_vinfast_reviews.csv`
- **Columns:** `review_text, rating, product_name, timestamp, source`
- **Target:** 200+ reviews

### T2.4: UIT-VSFC dataset integration
- **File:** `scripts/integrate_uit_vsfc.py` [NEW]
- **Action:** Download and integrate UIT-VSFC (Vietnamese Students' Feedback Corpus) as supplementary training data
- **Source:** Public dataset from UIT (University of Information Technology HCMC)
- **Output:** `data/scraped/uit_vsfc_feedback.csv`
- **Purpose:** Provides labeled Vietnamese sentiment data for NLP validation

### T2.5: Unified feedback ingestion into DuckDB
- **File:** `scripts/ingest_scraped_data.py` [NEW]
- **Action:** Merge all scraped CSVs → deduplicate → ingest into `xanhsm_feedback` table
- **Deduplication:** Hash of `review_text + source + timestamp`
- **Command:** `uv run python scripts/ingest_scraped_data.py`

### T2.6: Data quality report for scraped data
- **File:** `data/scraped/SCRAPE_REPORT.md` [NEW]
- **Action:** Auto-generate report with:
  - Total reviews per source
  - Language distribution (Vietnamese/English/Mixed)
  - Teen-code density (% reviews containing slang)
  - Rating distribution histogram
  - Sample teen-code examples found

## 2.3 Verification

```bash
uv run python scripts/ingest_scraped_data.py
uv run python -c "
import duckdb
con = duckdb.connect('data/datatrust_v4.duckdb')
print(con.execute('SELECT source, COUNT(*) FROM xanhsm_feedback GROUP BY source').fetchall())
"
# Expected: Multiple sources, total > 1000 reviews
```

## 2.4 Exit Criteria

- [ ] 3+ unique data sources scraped
- [ ] 1000+ total reviews in `xanhsm_feedback` table
- [ ] At least 30% of reviews contain Vietnamese teen-code/slang
- [ ] `SCRAPE_REPORT.md` generated with statistics
- [ ] All scraped data has `source` field for provenance

---

# PHASE 3: Vietnamese NLP Engine — Teen-code Dictionary & Aspect Extractor

> **Sprint:** 2 (07 Aug – 11 Aug)
> **Owner:** Agent-Worker-NLP
> **Files:** `src/services/vietnamese_nlp.py`, `src/data/teencode_dict.json`
> **Duration:** 2 days
> **Depends on:** Phase 2 (needs scraped feedback data for validation)

## 3.1 Objective

Build a custom Vietnamese NLP engine that:
1. Normalizes teen-code/slang to standard Vietnamese
2. Extracts structured aspects (Location, Component, Severity, Symptom)
3. Classifies sentiment polarity
4. Cross-references with EV domain ontology

## 3.2 Tasks

### T3.1: Build teen-code dictionary
- **File:** `src/data/teencode_dict.json` [NEW]
- **Action:** Create comprehensive Vietnamese teen-code → standard Vietnamese mapping
- **Minimum 200 entries** covering:
  ```json
  {
    "ko": "không", "dc": "được", "nc": "nhưng", "vl": "quá",
    "cx": "cũng", "tram sac": "trạm sạc", "sac dt": "sạc điện thoại",
    "app": "ứng dụng", "lag": "chậm", "oke": "tốt", "bt": "bình thường",
    "nv": "nhân viên", "ship": "giao hàng", "fb": "phản hồi",
    "dv": "dịch vụ", "sdt": "số điện thoại", "tks": "cảm ơn",
    "k": "không", "nma": "nhưng mà", "tl": "trả lời",
    "ntn": "như thế nào", "j": "gì", "r": "rồi", "mk": "mình", "bik": "biết"
  }
  ```
- **Sources:** Analyze scraped feedback from Phase 2 for common patterns

### T3.2: Build EV domain ontology
- **File:** `src/data/ev_domain_ontology.json` [NEW]
- **Action:** Create domain-specific keyword → component mapping for EV ecosystem
  ```json
  {
    "components": {
      "charger": ["trạm sạc", "sạc", "cổng sạc", "bộ sạc", "charger"],
      "battery": ["pin", "ắc quy", "battery", "BMS", "cell"],
      "vehicle": ["xe", "ô tô", "VinFast", "VF8", "VF9", "VFe34"],
      "app": ["ứng dụng", "app", "Xanh SM", "phần mềm"],
      "driver": ["tài xế", "bác tài", "lái xe", "driver"]
    },
    "severity_keywords": {
      "critical": ["cháy", "nổ", "chết máy", "không hoạt động", "nguy hiểm"],
      "high": ["nóng", "quá nhiệt", "hỏng", "lỗi", "không sạc được"],
      "medium": ["chậm", "lag", "đợi lâu", "không ổn định"],
      "low": ["bình thường", "tạm ổn", "chấp nhận được"]
    }
  }
  ```

### T3.3: Implement VietnameseNLPService
- **File:** `src/services/vietnamese_nlp.py` [MODIFY — rewrite]
- **Action:** Complete rewrite with production-quality NLP pipeline
- **Contract:**
  ```python
  @dataclass
  class NLPResult:
      original_text: str
      normalized_text: str
      language: str  # 'vi', 'en', 'mixed'
      teencode_found: list[str]
      aspects: list[Aspect]
      sentiment: float  # -1.0 to 1.0
      confidence: float  # 0.0 to 1.0

  @dataclass
  class Aspect:
      component: str  # 'charger', 'battery', 'vehicle', 'app', 'driver'
      location: str | None
      symptom: str
      severity: str  # 'critical', 'high', 'medium', 'low'

  class VietnameseNLPService:
      def __init__(self, teencode_path: str, ontology_path: str): ...
      def normalize(self, text: str) -> str: ...
      def extract_aspects(self, text: str) -> list[Aspect]: ...
      def analyze(self, text: str) -> NLPResult: ...
      def batch_analyze(self, texts: list[str]) -> list[NLPResult]: ...
  ```

### T3.4: Create NLP test suite
- **File:** `tests/test_vietnamese_nlp.py` [NEW]
- **Action:** 30+ test cases covering:
  ```python
  assert nlp.normalize("ko sac dc") == "không sạc được"
  assert nlp.normalize("tram sac vincom nc nóng vl") == "trạm sạc Vincom nhưng nóng quá"

  result = nlp.analyze("trạm sạc vincom nc ko vào điện nóng vl")
  assert result.aspects[0].component == "charger"
  assert result.aspects[0].severity == "high"
  assert result.aspects[0].location == "Vincom"
  ```

## 3.3 Verification

```bash
uv run pytest tests/test_vietnamese_nlp.py -v
# Expected: 30+ tests pass, teen-code normalization accuracy > 95%
```

## 3.4 Exit Criteria

- [ ] Teen-code dictionary with 200+ entries
- [ ] EV domain ontology with 5 component categories
- [ ] `VietnameseNLPService` with `normalize()`, `extract_aspects()`, `analyze()`
- [ ] 30+ test cases passing
- [ ] Can process all scraped feedback from Phase 2

---

# PHASE 4: Deterministic Tool Layer

> **Sprint:** 2 (07 Aug – 11 Aug)
> **Owner:** Agent-Worker-Tools
> **Files:** `src/tools/*.py`
> **Duration:** 2 days
> **Depends on:** Phase 1 (DuckDB), Phase 3 (NLP service)

## 4.1 Objective

Build 6 deterministic tools that the ReAct agent can call. Each tool has a strict JSON input/output schema, no side effects on raw data, and full audit logging.

## 4.2 Tasks

### T4.1: Tool base class and registry
- **File:** `src/tools/base.py` [NEW]
- **Contract:**
  ```python
  class BaseTool(ABC):
      name: str
      description: str
      input_schema: dict  # JSON Schema
      output_schema: dict  # JSON Schema
      @abstractmethod
      def execute(self, input_data: dict) -> dict: ...
      def to_function_spec(self) -> dict: ...  # OpenAI-style function calling spec

  class ToolRegistry:
      def register(self, tool: BaseTool): ...
      def get(self, name: str) -> BaseTool: ...
      def list_tools(self) -> list[dict]: ...
      def execute(self, name: str, input_data: dict) -> ToolCall: ...
  ```

### T4.2: Tool 1 — Vietnamese NLP Extractor
- **File:** `src/tools/nlp_extractor.py` [NEW]
- **Input:** `{"review_text": "string", "review_id": "int?"}`
- **Output:** `{"normalized_text": "str", "aspects": [...], "sentiment": float, "teencode_found": [...]}`

### T4.3: Tool 2 — Telemetry Query API
- **File:** `src/tools/telemetry_query.py` [NEW]
- **Input:** `{"station_id?": "str", "location_keyword?": "str", "start_time": "ISO8601", "end_time": "ISO8601", "fault_only": bool}`
- **Output:** `{"vgreen_records": [...], "bms_records": [...], "total_faults_found": int}`

### T4.4: Tool 3 — Anomaly Detector (Statistical)
- **File:** `src/tools/anomaly_detector.py` [NEW]
- **Input:** `{"table_name": "str", "column_name": "str", "method": "z_score|iqr|isolation_forest", "threshold": float}`
- **Output:** `{"anomalies_found": int, "anomaly_indices": [...], "statistics": {...}}`

### T4.5: Tool 4 — Quality Rule Proposer
- **File:** `src/tools/rule_proposer.py` [NEW]
- **Input:** `{"profile_summary": "str", "nlp_insights": {}, "anomaly_findings": {}, "target_table": "str"}`
- **Output:** `{"proposed_rules": [{"rule_name": "str", "rule_type": "str", "rule_expression": "str", "confidence": float, "rationale": "str"}]}`

### T4.6: Tool 5 — Data Profiler
- **File:** `src/tools/profiler.py` [MODIFY — enhance]
- **Input:** `{"table_name": "str", "sample_size": int}`
- **Output:** `{"table_name": "str", "row_count": int, "columns": [{"name": "str", "dtype": "str", "null_count": int, ...}]}`

### T4.7: Tool 6 — Rule Executor
- **File:** `src/tools/rule_executor.py` [NEW]
- **Input:** `{"rule_id": "str", "dry_run": bool}`
- **Output:** `{"records_checked": int, "violations_found": int, "quarantined_count": int, "clean_count": int}`

### T4.8: Tool test suite
- **File:** `tests/test_tools.py` [NEW]
- **Action:** 40+ tests covering all 6 tools (happy path, empty input, invalid input, schema validation)

## 4.3 Verification

```bash
uv run pytest tests/test_tools.py -v
```

## 4.4 Exit Criteria

- [ ] 6 tools implemented with strict JSON schema contracts
- [ ] `ToolRegistry` can list and execute all tools
- [ ] Each tool returns structured output, never crashes on bad input
- [ ] 40+ tool tests passing

---

# PHASE 5: Multi-Agent ReAct Engine (Orchestrator + Sub-Agents)

> **Sprint:** 3 (11 Aug – 15 Aug)
> **Owner:** Agent-Worker-ReAct
> **Files:** `src/agents/*.py`, `src/orchestrator/`
> **Duration:** 3 days
> **Depends on:** Phase 3 (NLP), Phase 4 (Tools)

## 5.1 Objective

Build the core bounded ReAct loop engine with 6 specialized sub-agents. This is the **heart of the agentic necessity proof**.

## 5.2 Tasks

### T5.1: Gemma-4 LLM adapter via Google AI Studio
- **File:** `src/services/llm.py` [MODIFY — rewrite]
- **Contract:**
  ```python
  class GemmaLLMAdapter:
      def __init__(self, api_key: str, model: str = "gemma-4-27b-it"): ...
      def chat(self, messages: list[dict], tools: list[dict] = None) -> LLMResponse: ...
      def structured_output(self, prompt: str, schema: dict) -> dict: ...
  ```
- **Dependencies:** `uv add google-genai`
- **Auth:** `GOOGLE_AI_API_KEY` env var

### T5.2: ReAct Loop Engine
- **File:** `src/orchestrator/react_engine.py` [NEW]
- **Contract:**
  ```python
  class ReActEngine:
      def __init__(self, llm: GemmaLLMAdapter, tools: ToolRegistry, max_steps: int = 10): ...
      def run(self, task: str, context: dict = None) -> ReActResult: ...

  @dataclass
  class ReActStep:
      step_index: int
      thought: str
      action: str  # tool name or 'FINISH' or 'ABSTAIN'
      action_input: dict
      observation: str
  ```
- **Logic:** System prompt → LLM Thought → Action (tool call) → Observation → loop until FINISH/ABSTAIN/max_steps

### T5.3: Sub-Agent — Profiler Agent
- **File:** `src/agents/profiler_agent.py` [NEW]
- **Tools:** `data_profiler`

### T5.4: Sub-Agent — Anomaly Detector Agent
- **File:** `src/agents/anomaly_agent.py` [NEW]
- **Tools:** `anomaly_detector`, `telemetry_query`

### T5.5: Sub-Agent — Diagnosis Agent
- **File:** `src/agents/diagnosis_agent.py` [NEW]
- **Tools:** `vietnamese_nlp_extractor`, `telemetry_query`, `anomaly_detector`

### T5.6: Sub-Agent — Rule Proposer Agent
- **File:** `src/agents/rule_proposer_agent.py` [NEW]
- **Tools:** `quality_rule_proposer`

### T5.7: Sub-Agent — Executor Agent
- **File:** `src/agents/executor_agent.py` [NEW]
- **Tools:** `rule_executor`

### T5.8: Top-Level Orchestrator
- **File:** `src/orchestrator/orchestrator.py` [NEW]
- **Workflow:** Profiler → Anomaly → Diagnosis → Rule Proposer → HITL queue → (after approval) → Executor

### T5.9–T5.10: Baselines C0 and C1
- **File:** `src/agents/baselines.py` [MODIFY]
- C0: Pure SQL/Pandas rules, no LLM
- C1: Single LLM call, no tools

### T5.11: Agent test suite
- **File:** `tests/test_agents.py` [NEW]
- **Action:** 30+ tests (loop termination, abstention, tool passing, orchestrator ordering)

## 5.3 Verification

```bash
uv run pytest tests/test_agents.py -v
```

## 5.4 Exit Criteria

- [ ] Gemma-4 adapter connects to Google AI Studio
- [ ] ReAct engine completes bounded loop with tool calls
- [ ] 5 sub-agents + orchestrator implemented
- [ ] C0 and C1 baselines implemented
- [ ] 30+ agent tests passing
- [ ] All steps logged to `agent_traces` table

---

# PHASE 6: HITL Permission Gate & Audit System

> **Sprint:** 3 (11 Aug – 15 Aug)
> **Owner:** Agent-Worker-HITL
> **Files:** `src/api/hitl.py`, `src/services/audit.py`
> **Duration:** 1 day
> **Depends on:** Phase 5 (agent proposes rules to HITL queue)

## 6.1 Tasks

### T6.1: HITL queue data model (`src/models/hitl.py` [NEW])
```python
class RuleProposalCard(BaseModel):
    rule_id: str
    rule_name: str
    rule_expression: str
    confidence: float
    rationale: str
    impact_preview: dict
    status: str = "pending"  # pending, approved, rejected, edited
```

### T6.2: HITL API endpoints (`src/api/hitl.py` [NEW])
```
GET  /api/v1/hitl/queue         — List pending proposals
POST /api/v1/hitl/approve/{id}  — Approve rule
POST /api/v1/hitl/reject/{id}   — Reject rule
POST /api/v1/hitl/edit/{id}     — Edit rule before approval
GET  /api/v1/hitl/history       — All reviewed proposals
```

### T6.3: Enhanced audit trail (`src/services/audit.py` [MODIFY])
- Log every HITL action with actor, action, target, SHA-256 state hash

### T6.4: WebSocket HITL notifications (`src/services/ws_manager.py` [MODIFY])
- Push events: new proposal, approved, rejected, executed

### T6.5: HITL test suite (`tests/test_hitl.py` [NEW]) — 15+ tests

## 6.2 Exit Criteria

- [ ] HITL queue stores and serves rule proposals
- [ ] Approve/Reject/Edit endpoints work
- [ ] Every action logged to audit trail
- [ ] WebSocket notifications fire on state changes
- [ ] 15+ tests passing

---

# PHASE 7: Next.js Frontend — Dashboard & HITL UI

> **Sprint:** 4 (15 Aug – 19 Aug)
> **Owner:** Agent-Worker-Frontend
> **Files:** `/frontend/**`
> **Duration:** 3 days
> **Depends on:** Phase 6 (HITL API ready)

## 7.1 Tasks

### T7.1: Initialize Next.js project
```bash
rm -rf frontend-v3
pnpm dlx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack
cd frontend && pnpm add lucide-react @tanstack/react-query axios next-intl
```

### T7.2: API client (`frontend/src/lib/api.ts` [NEW])
- Type-safe Axios client matching FastAPI OpenAPI spec

### T7.3: Dashboard page (`frontend/src/app/page.tsx`)
- KPI cards, data quality gauge, activity timeline, date filters (3d/7d/1mo)
- Dark theme, glassmorphism, Lucide icons

### T7.4: HITL Queue page (`frontend/src/app/hitl/page.tsx`)
- Rule review cards with Approve/Edit/Reject buttons
- Impact preview, agent reasoning trace

### T7.5: Agent Trace Viewer (`frontend/src/app/traces/page.tsx`)
- ReAct loop step-by-step: Thought → Action → Observation
- Token cost per step

### T7.6: Quarantine Explorer (`frontend/src/app/quarantine/page.tsx`)
- Table view, lineage hash, originating rule

### T7.7: Data Sources page (`frontend/src/app/sources/page.tsx`)
- Raw snapshots, SHA-256 hashes, "Run Pipeline" button

### T7.8: i18n (`frontend/src/i18n/`)
- `vi.json`, `en.json`, `config.ts`
- Language toggle in navbar

### T7.9: Layout (`frontend/src/app/layout.tsx`)
- Sidebar nav, top bar, dark/light mode, responsive

## 7.2 Verification

```bash
cd frontend && pnpm build && pnpm dev
```

## 7.3 Exit Criteria

- [ ] Next.js builds successfully
- [ ] 6 pages functional
- [ ] i18n toggle works (Vietnamese ↔ English)
- [ ] HITL approve/reject/edit works
- [ ] Responsive dark theme

---

# PHASE 8: API Integration & WebSocket

> **Sprint:** 4 (15 Aug – 19 Aug)
> **Owner:** Agent-Worker-API
> **Files:** `src/api/*.py`
> **Duration:** 1 day
> **Depends on:** Phase 6, Phase 7

## 8.1 Tasks

### T8.1: Dashboard stats (`src/api/dashboard.py` [NEW])
### T8.2: Pipeline trigger (`src/api/pipeline.py` [NEW])
### T8.3: Agent traces (`src/api/traces.py` [NEW])
### T8.4: Quarantine (`src/api/quarantine.py` [NEW])
### T8.5: Snapshots (`src/api/snapshots.py` [NEW])
### T8.6: Security (`src/api/middleware.py` [MODIFY]) — tighten CORS, add rate limiting
### T8.7: API tests (`tests/test_api.py` [NEW]) — 20+ tests

## 8.2 Exit Criteria

- [ ] All endpoints return correct JSON
- [ ] Frontend can hit all endpoints
- [ ] 20+ API tests passing

---

# PHASE 9: Benchmark & Evaluation — C0 vs C1 vs A1

> **Sprint:** 5 (19 Aug – 23 Aug)
> **Owner:** Agent-Worker-Benchmark
> **Files:** `eval/`
> **Duration:** 1 day
> **Depends on:** Phase 5 (all 3 baselines)

## 9.1 Tasks

### T9.1: Fault injection (`eval/fault_injector.py` [NEW])
- 9 fault families, seed=42, ground-truth labels

### T9.2: Benchmark harness (`eval/benchmark.py` [NEW])
- Measure: Precision, Recall, F1, Compile Rate, Teen-code Accuracy, Cross-system Link Rate, Cost, Latency, Human Time Saved

### T9.3: Report generator (`eval/generate_report.py` [NEW])
- Output: `docs/planning/EVALUATION_REPORT.md`

### T9.4: Benchmark pytest gate (`tests/test_benchmark.py` [NEW])
```python
assert a1.recall >= c1.recall + 0.10
assert a1.precision >= 0.80
assert a1.cost <= c1.cost * 2.0
```

## 9.2 Exit Criteria

- [ ] A1 precision ≥ 80%, recall ≥ C1 + 10pp
- [ ] `EVALUATION_REPORT.md` generated

---

# PHASE 10: Docker Compose & Deployment

> **Sprint:** 5 (19 Aug – 23 Aug)
> **Owner:** Agent-Worker-DevOps
> **Duration:** 1 day

## 10.1 Tasks

### T10.1: Backend Dockerfile [NEW]
### T10.2: Frontend Dockerfile (`frontend/Dockerfile` [NEW])
### T10.3: Docker Compose (`docker-compose.yml` [NEW])
### T10.4: Reset script (`scripts/reset.sh` [NEW])

## 10.2 Exit Criteria

- [ ] `docker compose up --build` runs
- [ ] Frontend at `localhost:3000`, Backend at `localhost:8000`

---

# PHASE 11: Final Integration & Demo

> **Sprint:** 5 (19 Aug – 23 Aug)
> **Owner:** Agent-Worker-Final
> **Duration:** 1 day
> **Depends on:** All phases

## 11.1 Tasks

### T11.1: Full test suite
```bash
uv run pytest tests/ -v --tb=short
# Gate: 150+ tests, 100% pass
```

### T11.2: E2E integration test (`tests/test_e2e.py` [NEW])
- Seed → NLP → Orchestrate → HITL → Execute → Verify

### T11.3: Update `docs/archive/v2_ARCHITECTURE.md` for v4
### T11.4: Generate evaluation report
### T11.5: Demo script (`docs/guide/DEMO_SCRIPT.md` [NEW]) — 15 min max
### T11.6: Update `README.md`

## 11.2 Exit Criteria

- [ ] 150+ tests pass (100%)
- [ ] E2E test passes
- [ ] Demo rehearsal ≤ 15 minutes
- [ ] **DONE by 24 Aug 2026**

---

# 📋 File Manifest

## New Files: 40+

| Phase | File | Type |
|---|---|---|
| 1 | `src/db/__init__.py`, `connection.py`, `schema.sql`, `seed.py` | Python/SQL |
| 2 | `scripts/scrape_google_maps.py`, `scrape_play_store.py`, `scrape_shopee.py`, `integrate_uit_vsfc.py`, `ingest_scraped_data.py` | Python |
| 3 | `src/data/teencode_dict.json`, `ev_domain_ontology.json` | JSON |
| 4 | `src/tools/base.py`, `nlp_extractor.py`, `telemetry_query.py`, `anomaly_detector.py`, `rule_proposer.py`, `rule_executor.py` | Python |
| 5 | `src/orchestrator/react_engine.py`, `orchestrator.py`, `src/agents/profiler_agent.py`, `anomaly_agent.py`, `diagnosis_agent.py`, `rule_proposer_agent.py`, `executor_agent.py` | Python |
| 6 | `src/models/hitl.py`, `src/api/hitl.py` | Python |
| 7 | `frontend/` (entire Next.js app) | TypeScript |
| 8 | `src/api/dashboard.py`, `pipeline.py`, `traces.py`, `quarantine.py`, `snapshots.py` | Python |
| 9 | `eval/fault_injector.py`, `benchmark.py`, `generate_report.py` | Python |
| 10 | `Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `scripts/reset.sh` | Docker/Shell |
| 11 | `tests/test_e2e.py`, `docs/guide/DEMO_SCRIPT.md` | Python/MD |

## Modified Files: 12

| Phase | File | Changes |
|---|---|---|
| 1 | `pyproject.toml` | Add duckdb |
| 1 | `src/config.py` | DUCKDB_PATH |
| 1 | `src/main.py` | DuckDB lifespan |
| 3 | `src/services/vietnamese_nlp.py` | Complete rewrite |
| 4 | `src/tools/profiler.py` | DuckDB-backed |
| 5 | `src/services/llm.py` | Gemma-4 adapter |
| 5 | `src/agents/baselines.py` | C0/C1 |
| 6 | `src/services/audit.py` | Enhanced |
| 6 | `src/services/ws_manager.py` | HITL WebSocket |
| 8 | `src/api/middleware.py` | CORS + security |
| 11 | `docs/archive/v2_ARCHITECTURE.md` | v4 update |
| 11 | `README.md` | Quick start |

## Test Files: 150+ tests

| File | Count |
|---|---|
| `tests/test_db.py` | 10+ |
| `tests/test_vietnamese_nlp.py` | 30+ |
| `tests/test_tools.py` | 40+ |
| `tests/test_agents.py` | 30+ |
| `tests/test_hitl.py` | 15+ |
| `tests/test_api.py` | 20+ |
| `tests/test_benchmark.py` | 5+ |
| `tests/test_e2e.py` | 1 |

---

# ⚠️ Risk Register

| # | Risk | Mitigation |
|---|---|---|
| 1 | Google AI Studio rate limits | Retry + exponential backoff; cache LLM responses |
| 2 | Web scraping blocked | Use existing CSVs as fallback |
| 3 | Gemma-4 tool-calling quality | Fallback to structured JSON output + manual parsing |
| 4 | 20-day timeline tight | Cut Phase 2 scraping if behind; prioritize P1/P3/P5 |
| 5 | Vietnamese NLP accuracy | Expand dictionary; LLM normalization fallback |

---

# 🏁 Hard Gates

| Gate | Target | Command |
|---|---|---|
| Tests | 150+, 100% pass | `uv run pytest tests/ -v` |
| A1 Precision | ≥ 80% | `eval/benchmark.py` |
| A1 vs C1 Recall | ≥ C1 + 10pp | `eval/benchmark.py` |
| Docker | Both services healthy | `docker compose up` |
| i18n | VI ↔ EN toggle works | Manual |
| HITL | Approve/Reject works | E2E test |
| Demo | ≤ 15 minutes | Rehearsal |
| Deadline | **24 Aug 2026** | Calendar |
