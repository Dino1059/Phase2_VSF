# Graph Report - .  (2026-08-12)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 7092 nodes · 21670 edges · 236 communities (206 shown, 30 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 3160 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `58e1cd12`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- index-BaGgQfLv.js
- o
- concat
- index-CXFVbvtc.js
- index-cSvGY2XO.js
- n
- index-BRVdCVNO.js
- index-DlyLF_Ln.js
- index-DZrVSfRD.js
- index-Bh8v7zJ5.js
- index-to5fYhfR.js
- i
- Incident
- uS
- schemas.py
- pc
- i
- BenchmarkHarness
- pI
- sub_agents.py
- i
- test_agents.py
- get_db
- i
- i
- n
- VietnameseNLPService
- i
- nc
- Ingestion/ingest_vingroup_real_data.py
- n
- i
- BaseTool
- hu
- wd
- wd
- n
- ReActEngine
- wd
- n
- hT
- wd
- Signal
- t
- pc
- baselines.py
- properties
- wd
- test_tools.py
- StructuredSource
- gu
- dataset_engine.py
- test_vietnamese_nlp.py
- dependencies
- routes/__init__.py
- datetime
- ut
- test_db.py
- FastAPI
- properties
- InvestigationToolRegistry
- y
- Z
- datasets.py
- SchedulerService
- y
- y
- Hypothesis
- properties
- Z
- Au
- y
- test_anomaly_scheduler_alerting.py
- ErrorCode
- y
- DataSource
- test_nlp_eval.py
- L4ChangepointDetector
- gu
- AuditService
- test_v2_features.py
- c
- types/index.ts
- IncidentService
- dl
- Z
- run_profiler
- gu
- gu
- cc
- test_api.py
- dl
- properties
- y
- IncidentWorkspace.tsx
- api.ts
- gu
- dl
- y
- compilerOptions
- wd
- properties
- PreventiveControlManager
- Settings
- run_tests.py
- L2ContextualDetector
- properties
- executor.py
- dl
- wt
- DuckDBManager
- properties
- WebSocketManager
- log_antigravity.py
- DataFrame
- RuleExecutorTool
- test_governance.py
- properties
- authorizations.py
- sw
- useChatStore
- schema.sql
- wd
- agent-trace.schema.json
- test_hitl.py
- vc
- i18n/index.ts
- run_validator
- profile-result.schema.json
- inject_vingroup_real_faults.py
- api/hitl.py
- websocket.ts
- AgentState
- vc
- up
- repair_loop.py
- enum
- vc
- er
- string
- compile_rules.py
- Ingestion/fetch_real_public_datasets.py
- UnifiedLLMAdapter
- AgentId
- AppShell.tsx
- run_test_runner
- preventive_controls.py
- test_real_public_ingestion.py
- test_eval_rca.py
- Sidebar.tsx
- profiling.py
- li
- required
- li
- tool
- run-manifest.schema.json
- rulespec.schema.json
- profile_source_db.py
- schedules.py
- Be
- scripts/fetch_real_public_datasets.py
- ConversationStore
- Validator
- ErrorBoundary
- enum
- $schema
- $schema
- $schema
- $schema
- log_hook.py
- submit_log.py
- enum
- scrape_google_maps.py
- scrape_play_store.py
- scrape_shopee.py
- search.py
- generate_sample_dataset
- log_manual.py
- devDependencies
- build
- run_pipeline.py
- ApprovalSummary.tsx
- fetch_weather.py
- generate_scrape_report.py
- ingest_and_map_real_data
- eval/__init__.py
- demo.sh
- _pyrun.sh
- reset.sh
- seed.sh
- setup.sh
- setup_hooks.sh script
- reliability/__init__.py
- BaseModel
- ChatOpenAI
- fixture
- p-086
- post
- Enum
- Request
- str
- UploadFile
- get
- Exception
- Any
- WebSocket
- asyncio
- asyncio
- asyncio

## God Nodes (most connected - your core abstractions)
1. `o()` - 185 edges
2. `n()` - 183 edges
3. `r()` - 179 edges
4. `c()` - 154 edges
5. `t()` - 145 edges
6. `concat()` - 124 edges
7. `W` - 114 edges
8. `get_db()` - 100 edges
9. `pI` - 87 edges
10. `i()` - 85 edges

## Surprising Connections (you probably didn't know these)
- `test_react_step_creation()` --calls--> `ReActStep`  [INFERRED]
  tests/test_agents.py → src/orchestrator/engine.py
- `test_react_step_with_tool()` --calls--> `ReActStep`  [INFERRED]
  tests/test_agents.py → src/orchestrator/engine.py
- `test_react_result_creation()` --calls--> `ReActResult`  [INFERRED]
  tests/test_agents.py → src/orchestrator/engine.py
- `test_engine_creation()` --calls--> `ReActEngine`  [INFERRED]
  tests/test_agents.py → src/orchestrator/engine.py
- `BenchmarkRunRequest` --uses--> `ErrorInjector`  [INFERRED]
  src/api/routes/benchmarks.py → eval/injector.py

## Import Cycles
- None detected.

## Communities (236 total, 30 thin omitted)

### Community 0 - "index-BaGgQfLv.js"
Cohesion: 0.01
Nodes (231): $7, $8, a5(), a7(), a9(), aF(), aj(), aq() (+223 more)

### Community 1 - "o"
Cohesion: 0.03
Nodes (143): $5(), ac(), accessor(), Ad(), aee(), ag(), ak(), Al() (+135 more)

### Community 2 - "concat"
Cohesion: 0.06
Nodes (134): Te(), ue(), w(), A(), b8(), Bj(), Bk(), bP() (+126 more)

### Community 3 - "index-CXFVbvtc.js"
Cohesion: 0.03
Nodes (90): ad(), add(), addPostProcessor(), af(), bl(), bs(), clone(), cloneInstance() (+82 more)

### Community 4 - "index-cSvGY2XO.js"
Cohesion: 0.03
Nodes (93): add(), addPostProcessor(), ap(), bl(), bs(), componentDidCatch(), connect(), cp() (+85 more)

### Community 5 - "n"
Cohesion: 0.04
Nodes (113): $2(), _6(), A0(), aE(), Ah(), am(), av(), ay() (+105 more)

### Community 6 - "index-BRVdCVNO.js"
Cohesion: 0.03
Nodes (93): addPostProcessor(), af(), as(), ba(), bl(), Bo(), bs(), ca() (+85 more)

### Community 7 - "index-DlyLF_Ln.js"
Cohesion: 0.03
Nodes (77): ad(), add(), addPostProcessor(), af(), ap(), bs(), bu(), connect() (+69 more)

### Community 8 - "index-DZrVSfRD.js"
Cohesion: 0.03
Nodes (86): ad(), add(), addPostProcessor(), af(), bl(), Br(), bs(), bu() (+78 more)

### Community 9 - "index-Bh8v7zJ5.js"
Cohesion: 0.03
Nodes (73): ad(), addPostProcessor(), af(), An(), ap(), bs(), bu(), connect() (+65 more)

### Community 10 - "index-to5fYhfR.js"
Cohesion: 0.04
Nodes (76): add(), addPostProcessor(), af(), at(), bl(), Bo(), bs(), bu() (+68 more)

### Community 11 - "i"
Cohesion: 0.09
Nodes (82): a(), aa(), ae(), as(), b(), bd(), bi(), Bo() (+74 more)

### Community 12 - "Incident"
Cohesion: 0.06
Nodes (66): Any, Executes red-team adversarial scenarios: 1. Prompt Injection / Malicious…, run_red_team_harness(), A1BoundedInvestigator, Any, Determines target entity domain based on entity IDs, admission reason, signals,…, Executes bounded dynamic tool iterations to produce an evidence-backed…, A1 Dynamic Bounded Investigator. Uses typed read-only tool registry, maintains… (+58 more)

### Community 13 - "uS"
Cohesion: 0.07
Nodes (45): a6(), ba(), bc(), BS(), cm(), dE(), eg(), Ei() (+37 more)

### Community 14 - "schemas.py"
Cohesion: 0.06
Nodes (57): ContextBuilder, Any, execute_endpoint(), execute_transform_endpoint(), list_executions(), Any, get, post (+49 more)

### Community 15 - "pc"
Cohesion: 0.05
Nodes (84): aa(), Ac(), ao(), ap(), at(), bc(), be(), cf() (+76 more)

### Community 16 - "i"
Cohesion: 0.06
Nodes (85): aa(), ac(), add(), ao(), ba(), be(), bi(), Bo() (+77 more)

### Community 17 - "BenchmarkHarness"
Cohesion: 0.06
Nodes (40): BenchmarkHarness, BenchmarkMetrics, compute_f1(), Path, Benchmark harness for C0 vs C1 vs A1 comparison., Dynamically compute cross-system link rate from multi-domain fault predictions., Run deterministic baseline (C0)., Run single LLM call baseline (C1). (+32 more)

### Community 18 - "pI"
Cohesion: 0.03
Nodes (75): a4, ap(), ax(), bx(), $d(), dn(), DT(), Du() (+67 more)

### Community 19 - "sub_agents.py"
Cohesion: 0.08
Nodes (48): LLMService, ContextBuilder, Any, Strips any potential raw row data keys from the profile., Assembles data profile + target schema into a formatted prompt context., Assembles data profile and target schema into structured prompts for LLM…, AnomalyDetectorAgent, BoundedSubAgent (+40 more)

### Community 20 - "i"
Cohesion: 0.10
Nodes (72): a(), ae(), as(), b(), bd(), bi(), Bo(), C() (+64 more)

### Community 21 - "test_agents.py"
Cohesion: 0.06
Nodes (43): Exception, AnomalyAgent, Sub-agent specialized in anomaly detection across telemetry data., BaselineC0, Legacy alias for BaselineR0 with tier C0., DiagnosisAgent, Sub-agent that cross-references NLP insights with telemetry to diagnose root…, ExecutorAgent (+35 more)

### Community 22 - "get_db"
Cohesion: 0.05
Nodes (54): compute_file_sha256(), ingest_scraped_data(), Compute SHA-256 hash of a file., Ingest all CSVs from data/scraped/*.csv into DuckDB xanhsm_feedback table., get_activity(), get_stats(), get, list_quarantine() (+46 more)

### Community 23 - "i"
Cohesion: 0.07
Nodes (70): aa(), ac(), ao(), ba(), be(), bi(), Bo(), cc() (+62 more)

### Community 24 - "i"
Cohesion: 0.07
Nodes (75): Ac(), ao(), bc(), be(), C(), cc(), cf(), ci() (+67 more)

### Community 25 - "n"
Cohesion: 0.09
Nodes (66): a(), addResourceBundle(), ae(), An(), b(), bd(), C(), ca() (+58 more)

### Community 26 - "VietnameseNLPService"
Cohesion: 0.05
Nodes (35): evaluate(), _location_hit(), Accuracy eval for VietnameseNLPService against real ground-truth labels in…, A predicted location counts as a hit if it's a case-insensitive substring match…, Aspect, CrossValidationResult, NLPResult, Punctuation-aware tokenization handling !, ?, ., , cleanly without stripping… (+27 more)

### Community 27 - "i"
Cohesion: 0.07
Nodes (74): aa(), ac(), ao(), at(), ba(), be(), bi(), Bo() (+66 more)

### Community 28 - "nc"
Cohesion: 0.11
Nodes (34): aa(), ac(), ao(), Bc(), be(), componentDidCatch(), dc(), ea() (+26 more)

### Community 29 - "Ingestion/ingest_vingroup_real_data.py"
Cohesion: 0.06
Nodes (58): assign_day_index(), assign_fleet_linkage(), build_fleet_index(), build_per_vin_day_schedule(), _clamp_end(), _classify_charging_pattern(), _compute_soc_at(), _datetime_on_day() (+50 more)

### Community 30 - "n"
Cohesion: 0.09
Nodes (63): a(), addResourceBundle(), ae(), b(), bd(), ca(), cd(), ce() (+55 more)

### Community 31 - "i"
Cohesion: 0.10
Nodes (62): a(), an(), b(), ba(), bd(), ca(), ce(), constructor() (+54 more)

### Community 32 - "BaseTool"
Cohesion: 0.08
Nodes (36): ABC, main(), send_chat_message(), Enum, str, WorkflowState, AlgoliaSearchTool, BaseTool (+28 more)

### Community 33 - "hu"
Cohesion: 0.07
Nodes (55): ap(), Au(), cd(), ci(), Cu(), di(), dp(), et() (+47 more)

### Community 34 - "wd"
Cohesion: 0.07
Nodes (51): ar(), at(), Bn(), Bt(), componentDidCatch(), cr(), deprecate(), dr() (+43 more)

### Community 35 - "wd"
Cohesion: 0.07
Nodes (57): ar(), bn(), Bt(), Cn(), cr(), Dn(), dp(), dr() (+49 more)

### Community 36 - "n"
Cohesion: 0.08
Nodes (70): a(), addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), An(), b() (+62 more)

### Community 37 - "ReActEngine"
Cohesion: 0.07
Nodes (39): LLMResponse, BaseModel, Deprecated module. Redirecting exports to canonical orchestrator engine in…, StepLog, Deprecated module. Redirecting exports to canonical orchestrator engine in…, DecisionRecord, Any, Structured decision log record for ReAct step execution. (+31 more)

### Community 38 - "wd"
Cohesion: 0.07
Nodes (55): ar(), Bn(), Bt(), componentDidCatch(), cr(), deprecate(), dr(), Ed() (+47 more)

### Community 39 - "n"
Cohesion: 0.09
Nodes (60): a(), aa(), add(), addResourceBundle(), ae(), b(), bd(), bi() (+52 more)

### Community 40 - "hT"
Cohesion: 0.08
Nodes (20): ao(), cz(), DB(), Ef(), Em(), gk(), hT(), hx() (+12 more)

### Community 41 - "wd"
Cohesion: 0.08
Nodes (52): ar(), bn(), Bt(), Cn(), cr(), Dn(), Ed(), En() (+44 more)

### Community 42 - "Signal"
Cohesion: 0.09
Nodes (34): Any, Evaluates Fusion Engine signal grouping, alert reduction ratio, and incident…, run_fusion_evaluation(), generate_vingroup_signals(), hydrate_vinfast_digital_twin_scenario(), main(), Executes full VinGroup Digital Twin scenario hydration: 1. Seed base DuckDB…, Generate a comprehensive set of multi-layer (L1-L4) signals for the VinGroup… (+26 more)

### Community 43 - "t"
Cohesion: 0.10
Nodes (40): an(), ap(), bn(), Bt(), Cn(), dn(), dp(), fn() (+32 more)

### Community 44 - "pc"
Cohesion: 0.08
Nodes (51): Ac(), af(), ao(), bc(), be(), cf(), dc(), Du() (+43 more)

### Community 45 - "baselines.py"
Cohesion: 0.10
Nodes (33): asyncio, GemmaLLMAdapter, Protocol, run_storyline_demo(), Baseline, BaselineA1, BaselineA2, BaselineC1 (+25 more)

### Community 46 - "properties"
Cohesion: 0.04
Nodes (48): columns, dataset_name, name, schema, version, description, properties, required (+40 more)

### Community 47 - "wd"
Cohesion: 0.05
Nodes (72): ad(), ar(), Br(), Bt(), Cn(), cr(), deprecate(), Dn() (+64 more)

### Community 48 - "test_tools.py"
Cohesion: 0.08
Nodes (41): BaseTool, AnomalyDetectorTool, NLPExtractorTool, DataProfilerTool, RuleProposerTool, TelemetryQueryTool, test_anomaly_bms_soc(), test_anomaly_disallowed_table() (+33 more)

### Community 49 - "StructuredSource"
Cohesion: 0.07
Nodes (18): ErrorInjector, GroundTruthLabel, Any, BaseModel, DataFrame, Fixed-seed synthetic error injector across 15 fault families and configurable…, DataFrame, DataSource implementation for structured tabular formats (CSV, Parquet, JSON,… (+10 more)

### Community 50 - "gu"
Cohesion: 0.07
Nodes (47): ad(), at(), Au(), bu(), cd(), Cu(), dt(), et() (+39 more)

### Community 51 - "dataset_engine.py"
Cohesion: 0.08
Nodes (33): get_evaluation(), get, Retrieve dynamic benchmark evaluation metrics comparing C0, C1, and A1…, lifespan(), compute_benchmark_comparison(), ensure_data_dir(), execute_compiled_rules(), execute_on_dataset() (+25 more)

### Community 52 - "test_vietnamese_nlp.py"
Cohesion: 0.04
Nodes (14): nlp(), fixture, Unknown text defaults to 'service' component., A single feedback mixing a critical charger fault with a minor app gripe must…, Real dirty feedback is often accentless; severity keywords must still match., Multiple teen-codes in one sentence., Standard Vietnamese should not be changed., Teen-code text should be detected as Vietnamese. (+6 more)

### Community 53 - "dependencies"
Cohesion: 0.04
Nodes (44): framer-motion, dependencies, framer-motion, i18next, lucide-react, react, react-dom, react-i18next (+36 more)

### Community 54 - "routes/__init__.py"
Cohesion: 0.07
Nodes (41): AlertCreateRequest, AnomalyDetectRequest, ChatRequest, ChatResponse, ExecuteTransformRequest, ExecuteTransformResponse, ResetResponse, acknowledge_alert_endpoint() (+33 more)

### Community 55 - "datetime"
Cohesion: 0.10
Nodes (24): datetime, Any, Unbiased comparison harness evaluating R0 (Deterministic), C1 (Fixed AI), and…, run_unbiased_agentic_evaluation(), generate_synthetic_dataset(), Generates a realistic synthetic Vietnam ride-hailing dataset of 50,000 trips., generate_vingroup_datasets(), Generates 4 synthetic enterprise datasets for VinGroup / VinFast / Xanh SM /… (+16 more)

### Community 56 - "ut"
Cohesion: 0.09
Nodes (41): at(), Bn(), Bt(), componentDidCatch(), deprecate(), En(), error(), fd() (+33 more)

### Community 57 - "test_db.py"
Cohesion: 0.05
Nodes (41): fixture, Can insert quarantine records., Can insert agent execution traces., Can insert and query xanhsm_trips., Can insert and query profile_results., Can insert and query audit_log., Query on empty table returns empty list., seed_database populates tables and raw_snapshots. (+33 more)

### Community 58 - "FastAPI"
Cohesion: 0.11
Nodes (33): BaseHTTPMiddleware, FastAPI, Response, auth_status(), get_current_user(), login(), LoginRequest, LoginResponse (+25 more)

### Community 59 - "properties"
Cohesion: 0.05
Nodes (44): integer, description, type, description, type, minimum, type, null (+36 more)

### Community 60 - "InvestigationToolRegistry"
Cohesion: 0.08
Nodes (26): InvestigationToolRegistry, InvestigationToolResult, Any, BaseModel, datetime, Fetches trip logs and operational ride-hailing history for an entity., Fetches charging session history and power delivery events for an EV/station…, Fetches static asset metadata, specifications, and schema profile. (+18 more)

### Community 61 - "y"
Cohesion: 0.10
Nodes (41): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), clone(), cloneInstance(), dir() (+33 more)

### Community 62 - "Z"
Cohesion: 0.09
Nodes (41): bl(), cl(), dl(), Do(), el(), eo(), fl(), gl() (+33 more)

### Community 63 - "datasets.py"
Cohesion: 0.08
Nodes (32): SearchClientSync, benchmark_info(), BenchmarkRunRequest, get_benchmark_cases(), BaseModel, get, post, run_benchmark() (+24 more)

### Community 64 - "SchedulerService"
Cohesion: 0.08
Nodes (19): AuditRecord, AuditStore, Any, BaseModel, Any, Add a new profiling/quality check schedule and persist to DuckDB., Return all registered active schedules from DuckDB., Service to schedule dataset profiling and quality checks via APScheduler backed… (+11 more)

### Community 65 - "y"
Cohesion: 0.09
Nodes (42): addNamespaces(), addResource(), addResources(), changeLanguage(), clone(), cloneInstance(), dir(), emit() (+34 more)

### Community 66 - "y"
Cohesion: 0.09
Nodes (42): addNamespaces(), addResource(), addResources(), changeLanguage(), clone(), cloneInstance(), dir(), emit() (+34 more)

### Community 67 - "Hypothesis"
Cohesion: 0.12
Nodes (32): A1FailureAnalyzer, classify_a1_failure(), FailureAnalysisCase, FailureMode, generate_markdown_report(), get_failure_analysis_benchmark_cases(), main(), Any (+24 more)

### Community 68 - "properties"
Cohesion: 0.06
Nodes (39): minimum, type, number, cost_usd, type, description, type, null (+31 more)

### Community 69 - "Z"
Cohesion: 0.08
Nodes (46): bl(), Br(), cl(), dl(), ef(), el(), fl(), gf() (+38 more)

### Community 70 - "Au"
Cohesion: 0.08
Nodes (38): at(), Au(), bu(), cp(), Cu(), dt(), $e(), Eu() (+30 more)

### Community 71 - "y"
Cohesion: 0.14
Nodes (31): changeLanguage(), dir(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes(), getFixedT() (+23 more)

### Community 72 - "test_anomaly_scheduler_alerting.py"
Cohesion: 0.09
Nodes (22): AnomalyDetail, AnomalyDetector, compute_composite_anomaly_score(), DetectionResult, _extract_features(), IQRDetector, IsolationForestDetector, Any (+14 more)

### Community 73 - "ErrorCode"
Cohesion: 0.14
Nodes (33): compiler_tool(), Bien dich cac rule hop le thanh executable checks (Python expression + SQL…, ErrorCode, execute(), Enum, Exception, str, Shared plumbing for the data-quality Tool Layer (Task 2). Every tool in… (+25 more)

### Community 74 - "y"
Cohesion: 0.10
Nodes (40): addNamespaces(), addResource(), addResources(), changeLanguage(), dir(), emit(), exists(), extendTranslation() (+32 more)

### Community 75 - "DataSource"
Cohesion: 0.09
Nodes (19): DataSource, ImageSource, LogSource, PDFSource, Any, Path, Abstract base class for unstructured data sources (PDF, Log, Image, etc.)., Compute SHA-256 checksum of the source file. (+11 more)

### Community 76 - "test_nlp_eval.py"
Cohesion: 0.06
Nodes (36): nlp(), fixture, Test that negation scope stops at clause boundaries or punctuation., Test critical severity precedence for safety hazards., Test high severity precedence for functional faults., Test handling of !, ?, ., , cleanly without stripping word boundaries., Test medium severity precedence for performance degradations., Test that negated faults do not trigger high/medium severity. (+28 more)

### Community 77 - "L4ChangepointDetector"
Cohesion: 0.09
Nodes (26): Any, Computes F1 score from precision and recall without division by zero., Evaluates L1-L4 Anomaly Detectors on synthetic/pilot corpus. Calculates…, run_detector_evaluation(), _safe_f1(), L3RelationalDetector, L3 Relational / Collective Detector. Detects broken relationships between…, L4ChangepointDetector (+18 more)

### Community 78 - "gu"
Cohesion: 0.11
Nodes (33): Au(), ci(), ct(), Cu(), dd(), Eu(), fs(), Fu() (+25 more)

### Community 79 - "AuditService"
Cohesion: 0.09
Nodes (26): check_pipeline_rule_approved(), execute_pipeline(), get_pipeline_status(), BackgroundTasks, get, post, Trigger the analysis pipeline on a table., Execute pipeline for table/rule. (+18 more)

### Community 80 - "test_v2_features.py"
Cohesion: 0.09
Nodes (22): Alert, AlertService, AlertSeverity, Any, BaseModel, Enum, str, Retrieve in-app alerts filtered by severity and/or status. (+14 more)

### Community 81 - "c"
Cohesion: 0.07
Nodes (39): c(), bM(), Ca(), f1(), fj(), fm(), fu, gM() (+31 more)

### Community 82 - "types/index.ts"
Cohesion: 0.12
Nodes (27): AGENT_ALIASES, AgentMessage(), parseBold(), renderFormattedContent(), safeFormatTime(), ChatMessage(), Props, SystemMessage() (+19 more)

### Community 83 - "IncidentService"
Cohesion: 0.09
Nodes (13): IncidentChatRequest, BaseModel, Any, BaseModel, Recommendation, IncidentService, Manages persistence and retrieval of Incidents, Evidence, Hypotheses,…, Retrieves evidence strictly scoped for the given incident by: 1. Matching… (+5 more)

### Community 84 - "dl"
Cohesion: 0.09
Nodes (33): cl(), dl(), dt(), fl(), gc(), gl(), Il(), kl() (+25 more)

### Community 85 - "Z"
Cohesion: 0.15
Nodes (27): cl(), dl(), el(), eo(), fl(), gl(), ia(), Il() (+19 more)

### Community 86 - "run_profiler"
Cohesion: 0.14
Nodes (28): profiler_tool(), Sinh schema va aggregate metadata (row/column count, null rate, distinct count,…, ColumnMetadata, ProfilerInput, ProfilerOutput, BaseModel, Profiler Tool — typed wrapper around scripts/profile_source_db.py. Returns…, run_profiler() (+20 more)

### Community 87 - "gu"
Cohesion: 0.16
Nodes (22): Au(), bu(), cp(), Cu(), $e(), Eu(), Fa(), gu() (+14 more)

### Community 88 - "gu"
Cohesion: 0.12
Nodes (30): Au(), cs(), Cu(), dd(), Eu(), Fu(), gu(), id() (+22 more)

### Community 89 - "cc"
Cohesion: 0.12
Nodes (29): bi(), cc(), cf(), Du(), ec(), fa(), fc(), gi() (+21 more)

### Community 90 - "test_api.py"
Cohesion: 0.08
Nodes (13): _SKIP_LLM, BaseModel, StateMachine, test_benchmark_dataset_endpoint(), test_chat_send_list_datasets(), test_chat_send_react_loop_anomaly(), test_chat_send_react_loop_diagnose(), test_chat_send_react_loop_profile() (+5 more)

### Community 91 - "dl"
Cohesion: 0.09
Nodes (33): cl(), dl(), el(), fl(), gl(), Il(), kl(), Ll() (+25 more)

### Community 92 - "properties"
Cohesion: 0.07
Nodes (30): maximum, minimum, type, format, type, type, properties, confidence (+22 more)

### Community 93 - "y"
Cohesion: 0.09
Nodes (46): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), clone(), cloneInstance(), dir() (+38 more)

### Community 94 - "IncidentWorkspace.tsx"
Cohesion: 0.13
Nodes (22): ChatMessageItem, ContextualAssistant(), ContextualAssistantProps, HITLAuthModal(), HITLAuthModalProps, ActionPanel(), ActionPanelProps, RecommendationActionItem (+14 more)

### Community 95 - "api.ts"
Cohesion: 0.12
Nodes (26): approvalsApi, auditApi, AuditEntry, authApi, AuthorizationInfo, authorizationsApi, benchmarksApi, controlsApi (+18 more)

### Community 96 - "gu"
Cohesion: 0.12
Nodes (29): Au(), cs(), Cu(), dd(), Eu(), Fu(), gu(), is() (+21 more)

### Community 97 - "dl"
Cohesion: 0.10
Nodes (29): cl(), dl(), fl(), gc(), Il(), kl(), Kt(), Ll() (+21 more)

### Community 98 - "y"
Cohesion: 0.11
Nodes (37): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), dir(), emit(), extendTranslation() (+29 more)

### Community 99 - "compilerOptions"
Cohesion: 0.07
Nodes (27): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, baseUrl, ignoreDeprecations, isolatedModules, jsx, lib (+19 more)

### Community 100 - "wd"
Cohesion: 0.11
Nodes (28): ad(), ar(), cr(), dr(), Ed(), Er(), fd(), fr() (+20 more)

### Community 101 - "properties"
Cohesion: 0.08
Nodes (27): cancelled, completed, failed, running, format, type, description, type (+19 more)

### Community 102 - "PreventiveControlManager"
Cohesion: 0.14
Nodes (11): GovernanceAuthorization, PreventiveControlManager, PreventiveControlProposal, Any, BaseModel, Backwards-compatible approval and authorization token generation., Updates a control's rule expression, incrementing its version and invalidating…, Executes an approved preventive control. Enforces: - Requirement of… (+3 more)

### Community 103 - "Settings"
Cohesion: 0.11
Nodes (16): BaseSettings, Settings, compute_sha256(), map_vgreen_telemetry(), map_vinfast_bms(), map_xanhsm_feedback(), map_xanhsm_trips(), DataFrame (+8 more)

### Community 104 - "run_tests.py"
Cohesion: 0.17
Nodes (24): build_specs(), check_date(), check_duplicate(), check_equality(), check_ledger(), check_membership(), check_null(), check_pattern() (+16 more)

### Community 105 - "L2ContextualDetector"
Cohesion: 0.12
Nodes (17): L2ContextualDetector, Any, DataFrame, Evaluates a DataFrame of observations per entity. Returns a list of L2…, Module-level score function for scoring an entity observation at day or…, Calculates the robust Z-score for a specific entity observation at day or…, L2 Contextual Anomaly Detector. Detects observations that are valid globally…, score() (+9 more)

### Community 106 - "properties"
Cohesion: 0.11
Nodes (18): description, type, description, type, description, type, type, properties (+10 more)

### Community 107 - "executor.py"
Cohesion: 0.13
Nodes (14): ExecutionResult, RawSnapshot, RunManifest, DataFrame, SourceConnector loads CSV, Parquet, JSON, or JSONL files, computes SHA-256…, Compute SHA-256 hash of a file., Load a structured data file into a Pandas DataFrame., Loads the source file, calculates SHA-256 checksum, row count, and schema, and… (+6 more)

### Community 108 - "dl"
Cohesion: 0.13
Nodes (25): cl(), dl(), el(), eo(), fl(), gl(), ia(), Il() (+17 more)

### Community 109 - "wt"
Cohesion: 0.10
Nodes (26): Bd(), bz(), c7(), dz(), gz(), H_(), Hy(), IR() (+18 more)

### Community 110 - "DuckDBManager"
Cohesion: 0.16
Nodes (12): DuckDBPyConnection, DuckDBManager, audit_db(), fixture, Create a fresh temporary database for audit chain testing., e2e_db(), fixture, fixture (+4 more)

### Community 111 - "properties"
Cohesion: 0.08
Nodes (24): format, type, $ref, properties, created_at, proposal_id, rationale, rules (+16 more)

### Community 112 - "WebSocketManager"
Cohesion: 0.14
Nodes (12): Any, WebSocket, Broadcast message to user-scoped room `user:{id}`., Broadcast message to project-scoped room `project:{id}`., Broadcast message to incident-scoped room `incident:{id}`., Broadcast message to room or all connections., Validate and decode JWT token for WebSocket connection., Authenticate token and accept WebSocket connection with scoped room… (+4 more)

### Community 113 - "log_antigravity.py"
Cohesion: 0.17
Nodes (22): build_entry(), _conv_cwds(), _conv_matches_repo(), extract_user_prompt(), get_brain_dirs(), get_logged_entry_ids(), git(), _is_repo_dir() (+14 more)

### Community 114 - "DataFrame"
Cohesion: 0.17
Nodes (15): Series, align_schema_transform(), drop_duplicates_transform(), fill_null_transform(), Any, DataFrame, quarantine_cross_field_transform(), quarantine_range_transform() (+7 more)

### Community 115 - "RuleExecutorTool"
Cohesion: 0.15
Nodes (19): _check_sql_safety(), compile_rule_spec(), _parse_val(), BaseModel, Infer target table from rule expression column names., Compile a RuleSpec into a safe, parameterized SQL clause (e.g. 'WHERE NOT (col…, RuleExecutorTool, RuleSpec (+11 more)

### Community 116 - "test_governance.py"
Cohesion: 0.09
Nodes (22): client(), fixture, Test P0-02: Executing unapproved rules returns HTTP 403 Forbidden with 'Rule…, Test P0-05: Uploading files with directory traversal paths (../malicious.csv)…, Test P0-06: Dispatching webhooks to private IP ranges (10.0.0.1, 127.0.0.1,…, Test Wave 6: Unified proposal, review, compilation, sandbox validation,…, Test Wave 6: Execution fails if authorization_id is missing., Test Wave 6: Enforce strict exact-version matching (rejecting modified rules or… (+14 more)

### Community 117 - "properties"
Cohesion: 0.09
Nodes (22): minimum, type, description, type, format, type, properties, column_count (+14 more)

### Community 118 - "authorizations.py"
Cohesion: 0.15
Nodes (21): execute_control(), ExecuteControlRequest, generate_authorization(), get_authorization(), IssueAuthorizationRequest, list_authorizations(), PipelineRequest, BaseModel (+13 more)

### Community 120 - "useChatStore"
Cohesion: 0.17
Nodes (14): ChatPanel(), BatchApprovalBar(), AnomalyItem, AnomalyWorkspace(), ColumnProfile, HEALTH_COLORS, ProfileWorkspace(), RuleWorkspace() (+6 more)

### Community 121 - "schema.sql"
Cohesion: 0.10
Nodes (20): agent_traces, audit_log, datasets, decisions, evidence, execution_authorizations, hypotheses, incidents (+12 more)

### Community 122 - "wd"
Cohesion: 0.14
Nodes (21): ar(), Br(), cn(), cr(), dr(), Ed(), ir(), kr() (+13 more)

### Community 123 - "agent-trace.schema.json"
Cohesion: 0.10
Nodes (18): agent_type, proposal_id, rules, step_index, trace_id, description, timestamp, required (+10 more)

### Community 124 - "test_hitl.py"
Cohesion: 0.10
Nodes (3): client(), fixture, test_audit_state_hash()

### Community 125 - "vc"
Cohesion: 0.21
Nodes (15): Bc(), ea(), exists(), ff(), Ga(), Ji(), Ka(), mo() (+7 more)

### Community 126 - "i18n/index.ts"
Cohesion: 0.13
Nodes (11): App(), resources, CentralizedLocaleKey, DEFAULT_EN_STRINGS, DEFAULT_VI_STRINGS, LAYER_TOKENS, LayerTokenMeta, DashboardPage (+3 more)

### Community 127 - "run_validator"
Cohesion: 0.25
Nodes (16): Agent-facing data-quality tools. These are the ONLY data-quality operations the…, Kiem tra rule co hop le hay khong: operator phai nam trong whitelist,…, validator_tool(), _do_validate(), BaseModel, Validator Tool — typed wrapper around scripts/validate_rules.py. Checks whether…, RuleValidationResult, run_validator() (+8 more)

### Community 128 - "profile-result.schema.json"
Cohesion: 0.11
Nodes (16): column_name, profile_id, sha256_hash, source_name, description, dtype, required, $schema (+8 more)

### Community 129 - "inject_vingroup_real_faults.py"
Cohesion: 0.22
Nodes (17): choose_fault_type(), generate_synthetic_feedback_scenario_driven(), inject_charging_faults(), inject_ev_telemetry_faults(), inject_nlp_teencode_corruption(), inject_trip_faults(), main(), mark_fault() (+9 more)

### Community 130 - "api/hitl.py"
Cohesion: 0.23
Nodes (16): approve_rule(), check_rule_approved(), edit_rule(), execute_hitl_rule(), execute_hitl_rules(), get_history(), get_queue(), get (+8 more)

### Community 135 - "websocket.ts"
Cohesion: 0.22
Nodes (7): agentSocket, AgentWebSocket, formatDecisionRecordSummary(), parseChainOfThoughtToRecord(), parseDecisionRecord(), AgentEvent, DecisionRecord

### Community 136 - "AgentState"
Cohesion: 0.22
Nodes (13): build_graph(), Route based on whether an error occurred during analysis., should_continue(), analyze_node(), Tạo response từ analysis., # TODO: Thêm logic tạo response thực tế, Phân tích query từ user., # TODO: Thêm logic phân tích thực tế (+5 more)

### Community 137 - "vc"
Cohesion: 0.19
Nodes (16): Bc(), ea(), exists(), fc(), ff(), Ga(), Ic(), Ji() (+8 more)

### Community 138 - "up"
Cohesion: 0.16
Nodes (14): ap(), dp(), $e(), ft(), ip(), kp(), lp(), np() (+6 more)

### Community 139 - "repair_loop.py"
Cohesion: 0.23
Nodes (8): ExecutableTransformPlan, LLMAdapter, LLMResponse, BaseModel, Proposes data quality and transformation rules based on context., RuleSpec, RepairLoop, RepairLoopResult

### Community 140 - "enum"
Cohesion: 0.13
Nodes (15): deprecated, pending, proposed, superseded, approved, rejected, status, default (+7 more)

### Community 141 - "vc"
Cohesion: 0.21
Nodes (15): Bc(), ea(), exists(), ff(), Ga(), Ji(), Ka(), ks() (+7 more)

### Community 142 - "er"
Cohesion: 0.07
Nodes (28): a1(), aB(), AW(), b5(), BW(), By, cB(), er() (+20 more)

### Community 143 - "string"
Cohesion: 0.12
Nodes (18): description, type, observation, null, description, type, previous_event_hash, target_id (+10 more)

### Community 144 - "compile_rules.py"
Cohesion: 0.32
Nodes (12): compile_rule(), format_py_literal(), format_sql_literal(), main(), render_markdown(), _is_number(), load_rules(), load_schema() (+4 more)

### Community 145 - "Ingestion/fetch_real_public_datasets.py"
Cohesion: 0.32
Nodes (12): _download(), fetch_real_ride_hailing(), fetch_real_st_evcdp(), fetch_real_uit_vsfc(), fetch_real_vehicle_telemetry(), fetch_real_public_datasets.py ============================== Layer 1 - FETCH…, Download raw bytes from url. Raises on any HTTP/network failure., _record() (+4 more)

### Community 146 - "UnifiedLLMAdapter"
Cohesion: 0.22
Nodes (4): Any, Unified LLM Adapter supporting OpenAI, OpenRouter, Google Gemini, and…, Send chat messages to active LLM provider. Priority: 1. OpenAI (if…, UnifiedLLMAdapter

### Community 148 - "AgentId"
Cohesion: 0.23
Nodes (10): AgentAvatar(), ICON_MAP, ICON_SIZES, Props, SIZES, TypingIndicator(), AuditEntry, AuditWorkspace() (+2 more)

### Community 149 - "AppShell.tsx"
Cohesion: 0.27
Nodes (8): AgentStatusBar(), ICON_MAP, AppShell(), ROLE_OPTIONS, TopBar(), AppState, useAppStore, UserRole

### Community 150 - "run_test_runner"
Cohesion: 0.32
Nodes (12): Any, Thuc thi cac executable check (tu compiler_tool) tren Source DB o che do READ-…, test_runner_tool(), run_test_runner(), TestRunnerInput, A malformed check's SQL error must not crash the whole tool call — it should…, test_failure_db_not_found(), test_failure_invalid_input_empty_compiled_rules() (+4 more)

### Community 151 - "preventive_controls.py"
Cohesion: 0.19
Nodes (11): approve_control(), get_control(), list_controls(), propose_control(), Any, get, post, List all preventive controls. (+3 more)

### Community 152 - "test_real_public_ingestion.py"
Cohesion: 0.15
Nodes (12): Verify all 4 VinGroup mapped real datasets exist in data/vingroup_real/., Verify mapped real VinFast EV Telemetry contains VINs, Speed, SOC, and Voltage., Verify mapped real V-GREEN Charging Stations contains Station ID, Power kW, and…, Verify mapped real Xanh SM Trips contains Trip ID, Vehicle VIN, Latitude,…, Verify mapped real Xanh SM Feedback contains Feedback ID, Customer ID, and Raw…, Verify all 4 raw public datasets exist in data/raw_public/., test_raw_public_datasets_exist(), test_real_vgreen_charging_stations_schema() (+4 more)

### Community 153 - "test_eval_rca.py"
Cohesion: 0.33
Nodes (10): get_hidden_rca_ground_truth_cases(), Any, Returns hidden ground-truth evaluation cases for Root Cause Analysis (RCA)…, Evaluates Root Cause Analysis (RCA) hypothesis accuracy, evidence precision,…, RCAGroundTruthCase, run_rca_evaluation(), test_get_hidden_rca_ground_truth_cases(), test_run_rca_evaluation_custom_cases() (+2 more)

### Community 154 - "Sidebar.tsx"
Cohesion: 0.32
Nodes (10): ChatInput(), SessionItem, Sidebar(), clearChatDatabase(), fetchChatHistory(), fetchChatSessions(), getRoleHeader(), request() (+2 more)

### Community 155 - "profiling.py"
Cohesion: 0.26
Nodes (11): get_profiling_job_status(), profile_async_endpoint(), profile_endpoint(), BackgroundTasks, get, post, Retrieve async profiling job status., Profile data synchronously or asynchronously via HTTP 202 Accepted when… (+3 more)

### Community 156 - "li"
Cohesion: 0.23
Nodes (12): ba(), ci(), dd(), di(), fi(), Ii(), is(), li() (+4 more)

### Community 157 - "required"
Cohesion: 0.18
Nodes (10): action, actor, event_hash, event_id, target_table, description, required, $schema (+2 more)

### Community 158 - "li"
Cohesion: 0.24
Nodes (11): ba(), ci(), dd(), di(), fi(), Ii(), is(), li() (+3 more)

### Community 159 - "tool"
Cohesion: 0.27
Nodes (9): AST, calculate(), _eval_node(), Tìm kiếm thông tin trong knowledge base. Args: query: Câu hỏi cần tìm kiếm…, # TODO: Implement actual search logic (e.g., RAG with vector store), Tính toán biểu thức toán học an toàn (không dùng eval). Hỗ trợ: +, -, *, /, //,…, Recursively evaluate AST node using safe operators only., search_knowledge() (+1 more)

### Community 160 - "run-manifest.schema.json"
Cohesion: 0.20
Nodes (9): dataset_key, run_id, started_at, description, status, required, $schema, title (+1 more)

### Community 161 - "rulespec.schema.json"
Cohesion: 0.20
Nodes (9): rule_expression, rule_id, rule_type, description, status, required, $schema, title (+1 more)

### Community 162 - "profile_source_db.py"
Cohesion: 0.42
Nodes (9): get_declared_types(), get_pk_columns(), get_tables(), log_table_summary(), main(), profile_table(), Connection, render_markdown() (+1 more)

### Community 163 - "schedules.py"
Cohesion: 0.31
Nodes (9): create_schedule_endpoint(), delete_schedule_endpoint(), get_schedule_by_id(), get_schedules_endpoint(), delete, get, post, ScheduleCreate (+1 more)

### Community 164 - "Be"
Cohesion: 0.06
Nodes (53): $3(), aS(), Be(), bi(), cf(), D2(), Di, Dl() (+45 more)

### Community 165 - "scripts/fetch_real_public_datasets.py"
Cohesion: 0.22
Nodes (8): fetch_real_ride_hailing(), fetch_real_st_evcdp(), fetch_real_uit_vsfc(), fetch_real_vehicle_telemetry(), Fetches real ST-EVCDP charging station dataset from GitHub public repository., Fetches real Ride Hailing Transaction Dataset., Fetches real UIT-VSFC Vietnamese Sentiment/Aspect dataset from HuggingFace /…, Fetches real Vehicle Energy & Telemetry (JAC IEV40 CAN-bus time series).

### Community 168 - "Validator"
Cohesion: 0.43
Nodes (4): Any, RuleSpec, Validator performs deterministic structural, semantic, and type-compatibility…, Validator

### Community 170 - "ErrorBoundary"
Cohesion: 0.29
Nodes (3): ErrorBoundary, Props, State

### Community 171 - "enum"
Cohesion: 0.29
Nodes (7): drop, flag, impute_deterministic, quarantine, enum, type, action

### Community 172 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 173 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 174 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 175 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 176 - "log_hook.py"
Cohesion: 0.43
Nodes (6): detect_tool(), git(), main(), normalize(), Detect which AI tool sent this hook event. Priority: 1. --tool=NAME CLI…, Normalize tool-specific payload to common log entry.

### Community 177 - "submit_log.py"
Cohesion: 0.43
Nodes (6): _archive(), main(), Path, Append pending file to today's archive. Never overwrites existing data., Failure path: put pending back at LOG_FILE so the next push retries. If hook…, _restore_pending()

### Community 178 - "enum"
Cohesion: 0.33
Nodes (6): error, info, warning, severity, enum, type

### Community 179 - "scrape_google_maps.py"
Cohesion: 0.47
Nodes (5): generate_samples(), main(), Playwright Google Maps scraping logic. Executes live search and extraction when…, Generate sample dataset of V-GREEN reviews with realistic teen-code mix., scrape_google_maps_playwright()

### Community 180 - "scrape_play_store.py"
Cohesion: 0.47
Nodes (5): generate_samples(), main(), Generate sample dataset of Play Store reviews for Xanh SM., Live scraper using google-play-scraper package., scrape_play_store_live()

### Community 181 - "scrape_shopee.py"
Cohesion: 0.47
Nodes (5): generate_samples(), main(), Generate sample dataset of Shopee reviews for VinFast products., Live scraper structure using Shopee public API endpoints., scrape_shopee_live()

### Community 182 - "search.py"
Cohesion: 0.40
Nodes (5): Any, get, post, search_endpoint(), seed_search_index_endpoint()

### Community 183 - "generate_sample_dataset"
Cohesion: 0.50
Nodes (4): generate_sample_dataset(), main(), DataFrame, Generate 200 realistic Vietnamese student feedback records.

### Community 184 - "log_manual.py"
Cohesion: 0.60
Nodes (4): git(), interactive_mode(), main(), Prompt user for log info interactively.

### Community 185 - "devDependencies"
Cohesion: 0.50
Nodes (3): devDependencies, puppeteer, puppeteer

### Community 186 - "build"
Cohesion: 0.67
Nodes (3): build(), main(), Path

### Community 187 - "run_pipeline.py"
Cohesion: 1.00
Nodes (3): main(), now_iso(), run_step()

## Knowledge Gaps
- **411 isolated node(s):** `setup.sh script`, `setup_hooks.sh script`, `name`, `private`, `version` (+406 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `c()` connect `c` to `index-BaGgQfLv.js`, `o`, `concat`, `n`, `vc`, `index-to5fYhfR.js`, `i`, `vc`, `uS`, `er`, `i`, `pI`, `i`, `i`, `i`, `n`, `i`, `nc`, `n`, `i`, `hu`, `n`, `Be`, `n`, `hT`, `wd`, `gu`, `gu`, `Z`, `gu`, `gu`, `cc`, `gu`, `wt`, `vc`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `api/hitl.py`, `schemas.py`, `test_agents.py`, `BaseTool`, `ReActEngine`, `ConversationStore`, `Signal`, `baselines.py`, `test_tools.py`, `dataset_engine.py`, `datetime`, `datasets.py`, `SchedulerService`, `AuditService`, `IncidentService`, `test_api.py`, `Settings`, `DuckDBManager`, `RuleExecutorTool`, `test_governance.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `Rn()` connect `t` to `wd`, `wd`, `concat`, `index-BRVdCVNO.js`, `wd`, `wd`, `ut`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 127 inferred relationships involving `o()` (e.g. with `index-BaGgQfLv.js` and `$5()`) actually correct?**
  _`o()` has 127 INFERRED edges - model-reasoned connections that need verification._
- **Are the 111 inferred relationships involving `n()` (e.g. with `index-BaGgQfLv.js` and `a4`) actually correct?**
  _`n()` has 111 INFERRED edges - model-reasoned connections that need verification._
- **Are the 126 inferred relationships involving `r()` (e.g. with `index-BaGgQfLv.js` and `a4`) actually correct?**
  _`r()` has 126 INFERRED edges - model-reasoned connections that need verification._
- **Are the 138 inferred relationships involving `c()` (e.g. with `b()` and `ep()`) actually correct?**
  _`c()` has 138 INFERRED edges - model-reasoned connections that need verification._