# Graph Report - .  (2026-08-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 6383 nodes · 20158 edges · 208 communities (173 shown, 35 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 3139 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `43df38e0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- index-BaGgQfLv.js
- n
- c
- index-CXFVbvtc.js
- test_agents.py
- index-BRVdCVNO.js
- index-cSvGY2XO.js
- index-Bh8v7zJ5.js
- get_db
- index-DZrVSfRD.js
- o
- routes/__init__.py
- index-DlyLF_Ln.js
- pc
- index-to5fYhfR.js
- StructuredSource
- i
- Be
- VietnameseNLPService
- test_v2_features.py
- i
- BenchmarkHarness
- has
- sub_agents.py
- i
- i
- i
- t
- i
- nc
- api/hitl.py
- i
- wd
- pI
- hT
- BaseTool
- wd
- n
- hu
- test_tools.py
- n
- wd
- wd
- wd
- pc
- Z
- properties
- Fn
- profiling.py
- n
- DuckDBManager
- dependencies
- test_db.py
- properties
- hu
- RuleExecutorTool
- dataset_engine.py
- gu
- y
- n
- properties
- y
- y
- ErrorCode
- y
- gu
- t
- AuditService
- Executor
- gu
- dl
- dl
- Z
- run_profiler
- SchedulerService
- y
- properties
- y
- wd
- compilerOptions
- UnstructuredSource
- index.ts
- properties
- zp
- wt
- run_tests.py
- Au
- dl
- properties
- get_settings
- log_antigravity.py
- DataFrame
- properties
- dl
- sl
- gu
- wd
- App.tsx
- useChatStore
- a
- test_nlp_eval.py
- agent-trace.schema.json
- properties
- vc
- run_validator
- Gt
- api.ts
- profile-result.schema.json
- vo
- vl
- websocket.ts
- string
- AgentState
- schema.sql
- up
- schemas.py
- enum
- .chat
- vc
- nc
- compile_rules.py
- run_test_runner
- up
- test_real_public_ingestion.py
- AgentId
- chatStore.ts
- li
- required
- li
- tool
- run-manifest.schema.json
- rulespec.schema.json
- profile_source_db.py
- AppShell.tsx
- fetch_real_public_datasets.py
- ConversationStore
- Kt
- enum
- $schema
- $schema
- $schema
- $schema
- submit_log.py
- ConnectionManager
- auth.py
- enum
- sw
- devDependencies
- build
- ApprovalSummary.tsx
- fetch_weather.py
- generate_scrape_report.py
- ingest_and_map_real_data
- .to_function_spec
- eval/__init__.py
- demo.sh
- _pyrun.sh
- reset.sh
- seed.sh
- setup.sh
- setup_hooks.sh script
- test_severity_precedence_critical
- test_tokenize_punctuation_marks
- test_severity_precedence_negated_fault
- test_eval_held_out_dataset_metrics
- test_tokenize_multiple_punctuation
- test_is_accentless_true
- test_accentless_dictionary_mapping
- test_negation_scope_multiple_negations
- nlp
- test_extract_default_component
- test_normalize_multiple
- test_normalize_preserves_standard
- test_detect_teencode_as_vi
- BaseModel
- ChatOpenAI
- fixture
- p-086
- post
- get
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
8. `get_db()` - 92 edges
9. `pI` - 87 edges
10. `i()` - 85 edges

## Surprising Connections (you probably didn't know these)
- `BenchmarkMetrics` --uses--> `VietnameseNLPService`  [INFERRED]
  eval/benchmark.py → src/services/vietnamese_nlp.py
- `BenchmarkHarness` --uses--> `VietnameseNLPService`  [INFERRED]
  eval/benchmark.py → src/services/vietnamese_nlp.py
- `BenchmarkRunRequest` --uses--> `BenchmarkHarness`  [INFERRED]
  src/api/routes/benchmarks.py → eval/benchmark.py
- `RunStore` --uses--> `BenchmarkHarness`  [INFERRED]
  src/services/dataset_engine.py → eval/benchmark.py
- `BenchmarkRunRequest` --uses--> `ErrorInjector`  [INFERRED]
  src/api/routes/benchmarks.py → eval/injector.py

## Import Cycles
- None detected.

## Communities (208 total, 35 thin omitted)

### Community 0 - "index-BaGgQfLv.js"
Cohesion: 0.01
Nodes (223): $7, $8, a5(), a7(), a9(), aF(), aj(), aq() (+215 more)

### Community 1 - "n"
Cohesion: 0.03
Nodes (151): $2(), A0(), aB(), Ah(), Al(), ap(), Ar(), b0() (+143 more)

### Community 2 - "c"
Cohesion: 0.06
Nodes (144): c(), Te(), ue(), w(), A(), b8(), BB, Bj() (+136 more)

### Community 3 - "index-CXFVbvtc.js"
Cohesion: 0.03
Nodes (93): add(), addPostProcessor(), ap(), bl(), bs(), componentDidCatch(), connect(), cp() (+85 more)

### Community 4 - "test_agents.py"
Cohesion: 0.05
Nodes (76): LLMResponse, AnomalyAgent, Sub-agent specialized in anomaly detection across telemetry data., DiagnosisAgent, Sub-agent that cross-references NLP insights with telemetry to diagnose root…, ExecutorAgent, Sub-agent that executes approved quality rules., ProfilerAgent (+68 more)

### Community 5 - "index-BRVdCVNO.js"
Cohesion: 0.03
Nodes (88): add(), addPostProcessor(), af(), ba(), bl(), Bo(), bs(), clone() (+80 more)

### Community 6 - "index-cSvGY2XO.js"
Cohesion: 0.03
Nodes (90): ad(), add(), addPostProcessor(), af(), bl(), bs(), clone(), cloneInstance() (+82 more)

### Community 7 - "index-Bh8v7zJ5.js"
Cohesion: 0.03
Nodes (93): add(), addPostProcessor(), af(), bl(), Br(), bs(), ca(), connect() (+85 more)

### Community 8 - "get_db"
Cohesion: 0.03
Nodes (68): BaseSettings, compute_file_sha256(), ingest_scraped_data(), Compute SHA-256 hash of a file., Ingest all CSVs from data/scraped/*.csv into DuckDB xanhsm_feedback table., _SKIP_LLM, get_activity(), get_stats() (+60 more)

### Community 9 - "index-DZrVSfRD.js"
Cohesion: 0.04
Nodes (62): addPostProcessor(), bs(), ci(), connect(), cs(), ct(), dd(), df() (+54 more)

### Community 10 - "o"
Cohesion: 0.03
Nodes (110): $5(), accessor(), Ad(), aee(), ag(), ak(), AW(), az (+102 more)

### Community 11 - "routes/__init__.py"
Cohesion: 0.05
Nodes (72): BaseHTTPMiddleware, FastAPI, Response, check_role_permission(), check_user_role(), is_public_path(), Enum, Request (+64 more)

### Community 12 - "index-DlyLF_Ln.js"
Cohesion: 0.03
Nodes (74): ad(), addPostProcessor(), af(), Br(), bs(), bu(), ca(), cn() (+66 more)

### Community 13 - "pc"
Cohesion: 0.05
Nodes (84): aa(), Ac(), ao(), ap(), at(), bc(), be(), cf() (+76 more)

### Community 14 - "index-to5fYhfR.js"
Cohesion: 0.04
Nodes (65): addPostProcessor(), af(), at(), bl(), Bo(), bs(), bu(), connect() (+57 more)

### Community 15 - "StructuredSource"
Cohesion: 0.04
Nodes (45): ABC, ErrorInjector, GroundTruthLabel, Any, BaseModel, DataFrame, Fixed-seed synthetic error injector across 15 fault families and configurable…, ContextBuilder (+37 more)

### Community 16 - "i"
Cohesion: 0.09
Nodes (82): a(), aa(), ae(), as(), b(), bd(), bi(), Bo() (+74 more)

### Community 17 - "Be"
Cohesion: 0.05
Nodes (58): $3(), aS(), av(), Be(), bi(), cf(), D2(), Dl() (+50 more)

### Community 18 - "VietnameseNLPService"
Cohesion: 0.05
Nodes (47): Protocol, Baseline, BaselineA1, BaselineA2, BaselineC0, BaselineC1, BaselineR0, BaselineResult (+39 more)

### Community 19 - "test_v2_features.py"
Cohesion: 0.05
Nodes (47): detect_anomalies_endpoint(), Alert, AlertService, AlertSeverity, Any, BaseModel, Enum, str (+39 more)

### Community 20 - "i"
Cohesion: 0.07
Nodes (75): aa(), ac(), ao(), at(), ba(), be(), bi(), Bo() (+67 more)

### Community 21 - "BenchmarkHarness"
Cohesion: 0.06
Nodes (40): BenchmarkHarness, BenchmarkMetrics, compute_f1(), Path, Benchmark harness for C0 vs C1 vs A1 comparison., Dynamically compute cross-system link rate from multi-domain fault predictions., Run deterministic baseline (C0)., Run single LLM call baseline (C1). (+32 more)

### Community 22 - "has"
Cohesion: 0.06
Nodes (73): _6(), a6(), aE(), am(), ay(), bo(), c2(), c3() (+65 more)

### Community 23 - "sub_agents.py"
Cohesion: 0.08
Nodes (48): LLMService, ContextBuilder, Any, Strips any potential raw row data keys from the profile., Assembles data profile + target schema into a formatted prompt context., Assembles data profile and target schema into structured prompts for LLM…, AnomalyDetectorAgent, BoundedSubAgent (+40 more)

### Community 24 - "i"
Cohesion: 0.10
Nodes (72): a(), ae(), as(), b(), bd(), bi(), Bo(), C() (+64 more)

### Community 25 - "i"
Cohesion: 0.07
Nodes (69): aa(), as(), bc(), ca(), cc(), cf(), ci(), dc() (+61 more)

### Community 26 - "i"
Cohesion: 0.08
Nodes (61): aa(), ac(), af(), ao(), ba(), be(), bi(), Bo() (+53 more)

### Community 27 - "t"
Cohesion: 0.08
Nodes (61): addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), b(), changeLanguage(), clone() (+53 more)

### Community 28 - "i"
Cohesion: 0.07
Nodes (73): aa(), ac(), ao(), at(), ba(), be(), bi(), Bo() (+65 more)

### Community 29 - "nc"
Cohesion: 0.07
Nodes (57): aa(), ac(), ao(), Bc(), be(), bi(), cc(), cf() (+49 more)

### Community 30 - "api/hitl.py"
Cohesion: 0.05
Nodes (53): datetime, generate_synthetic_dataset(), Generates a realistic synthetic Vietnam ride-hailing dataset of 50,000 trips., generate_vingroup_datasets(), Generates 4 synthetic enterprise datasets for VinGroup / VinFast / Xanh SM /…, generate_sample_dataset(), main(), DataFrame (+45 more)

### Community 31 - "i"
Cohesion: 0.10
Nodes (63): a(), an(), b(), ba(), bd(), ca(), cd(), ce() (+55 more)

### Community 32 - "wd"
Cohesion: 0.05
Nodes (73): ad(), An(), ar(), at(), Bn(), Br(), Bt(), cn() (+65 more)

### Community 33 - "pI"
Cohesion: 0.04
Nodes (67): a1(), a4, ac(), ax(), By, Cc(), $d(), Dp() (+59 more)

### Community 34 - "hT"
Cohesion: 0.08
Nodes (15): ao(), cz(), Em(), gB(), gk(), hT(), hx(), lC() (+7 more)

### Community 35 - "BaseTool"
Cohesion: 0.08
Nodes (42): chat(), ClearChatRequest, BaseModel, send_chat_message(), BaseModel, Enum, str, StateMachine (+34 more)

### Community 36 - "wd"
Cohesion: 0.07
Nodes (57): ar(), bn(), Bt(), Cn(), cr(), Dn(), dp(), dr() (+49 more)

### Community 37 - "n"
Cohesion: 0.10
Nodes (57): a(), addResourceBundle(), ae(), An(), b(), bd(), C(), cd() (+49 more)

### Community 38 - "hu"
Cohesion: 0.06
Nodes (62): ap(), Au(), ci(), Cu(), dd(), di(), dp(), et() (+54 more)

### Community 39 - "test_tools.py"
Cohesion: 0.06
Nodes (49): AnomalyDetectorTool, NLPExtractorTool, DataProfilerTool, RuleProposerTool, TelemetryQueryTool, mock_llm(), fixture, tmp_db() (+41 more)

### Community 40 - "n"
Cohesion: 0.08
Nodes (73): a(), addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), An(), b() (+65 more)

### Community 41 - "wd"
Cohesion: 0.07
Nodes (55): ad(), ar(), Bn(), Bt(), componentDidCatch(), cr(), deprecate(), dr() (+47 more)

### Community 42 - "wd"
Cohesion: 0.07
Nodes (55): ar(), Bn(), Bt(), componentDidCatch(), cr(), deprecate(), dr(), Ed() (+47 more)

### Community 43 - "wd"
Cohesion: 0.08
Nodes (52): ar(), bn(), Bt(), Cn(), cr(), Dn(), Ed(), En() (+44 more)

### Community 44 - "pc"
Cohesion: 0.08
Nodes (51): Ac(), af(), ao(), bc(), be(), cf(), dc(), Du() (+43 more)

### Community 45 - "Z"
Cohesion: 0.09
Nodes (40): bl(), cl(), dl(), Do(), el(), eo(), fl(), gl() (+32 more)

### Community 46 - "properties"
Cohesion: 0.04
Nodes (48): columns, dataset_name, name, schema, version, description, properties, required (+40 more)

### Community 47 - "Fn"
Cohesion: 0.10
Nodes (38): Bt(), Cn(), deprecate(), Dn(), dt(), en(), Er(), error() (+30 more)

### Community 48 - "profiling.py"
Cohesion: 0.24
Nodes (12): get_profiling_job_status(), profile_async_endpoint(), profile_endpoint(), BackgroundTasks, get, post, Retrieve async profiling job status., Profile data synchronously or asynchronously via HTTP 202 Accepted when… (+4 more)

### Community 49 - "n"
Cohesion: 0.10
Nodes (57): a(), addResourceBundle(), ae(), b(), bd(), bi(), C(), cd() (+49 more)

### Community 50 - "DuckDBManager"
Cohesion: 0.06
Nodes (18): DuckDBPyConnection, DuckDBManager, audit_db(), fixture, Create a fresh temporary database for audit chain testing., fixture, Create a temporary DuckDB database for testing., tmp_db() (+10 more)

### Community 51 - "dependencies"
Cohesion: 0.04
Nodes (44): framer-motion, dependencies, framer-motion, i18next, lucide-react, react, react-dom, react-i18next (+36 more)

### Community 52 - "test_db.py"
Cohesion: 0.05
Nodes (43): compute_sha256(), map_vgreen_telemetry(), map_vinfast_bms(), map_xanhsm_feedback(), map_xanhsm_trips(), DataFrame, Map real_xanh_sm_customer_feedback.csv to xanhsm_feedback table schema., Map real_vgreen_charging_stations.csv to vgreen_telemetry table schema. (+35 more)

### Community 53 - "properties"
Cohesion: 0.05
Nodes (44): integer, description, type, description, type, minimum, type, null (+36 more)

### Community 54 - "hu"
Cohesion: 0.06
Nodes (54): ap(), Au(), bu(), Cu(), dp(), dt(), Du(), $e() (+46 more)

### Community 55 - "RuleExecutorTool"
Cohesion: 0.09
Nodes (33): run_storyline_demo(), Validate webhook URL against SSRF attacks by checking scheme and resolving DNS…, validate_webhook_url(), _check_sql_safety(), compile_rule_spec(), _parse_val(), BaseModel, Infer target table from rule expression column names. (+25 more)

### Community 56 - "dataset_engine.py"
Cohesion: 0.10
Nodes (28): propose_rules_for_dataset(), Propose data quality rules for a registered dataset., lifespan(), compute_benchmark_comparison(), ensure_data_dir(), execute_on_dataset(), execute_rules_transactional(), generate_rules_for_baseline() (+20 more)

### Community 57 - "gu"
Cohesion: 0.07
Nodes (47): ad(), at(), Au(), bu(), cd(), Cu(), dt(), et() (+39 more)

### Community 58 - "y"
Cohesion: 0.11
Nodes (38): addNamespaces(), addResource(), addResources(), changeLanguage(), dir(), emit(), exists(), extendTranslation() (+30 more)

### Community 59 - "n"
Cohesion: 0.15
Nodes (27): add(), bd(), cd(), ce(), cp(), es(), et(), Ge() (+19 more)

### Community 60 - "properties"
Cohesion: 0.06
Nodes (39): minimum, type, number, cost_usd, type, description, type, null (+31 more)

### Community 61 - "y"
Cohesion: 0.10
Nodes (41): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), clone(), cloneInstance(), dir() (+33 more)

### Community 62 - "y"
Cohesion: 0.10
Nodes (39): addNamespaces(), addResource(), addResources(), changeLanguage(), clone(), cloneInstance(), dir(), emit() (+31 more)

### Community 63 - "ErrorCode"
Cohesion: 0.14
Nodes (33): compiler_tool(), Bien dich cac rule hop le thanh executable checks (Python expression + SQL…, ErrorCode, execute(), Enum, Exception, str, Shared plumbing for the data-quality Tool Layer (Task 2). Every tool in… (+25 more)

### Community 64 - "y"
Cohesion: 0.11
Nodes (37): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), dir(), emit(), extendTranslation() (+29 more)

### Community 65 - "gu"
Cohesion: 0.11
Nodes (33): Au(), ci(), ct(), Cu(), dd(), Eu(), fs(), Fu() (+25 more)

### Community 66 - "t"
Cohesion: 0.10
Nodes (40): an(), ap(), bn(), Bt(), Cn(), dn(), dp(), fn() (+32 more)

### Community 67 - "AuditService"
Cohesion: 0.10
Nodes (19): AuditRecord, AuditStore, Any, BaseModel, AuditService, Any, datetime, Enhanced audit trail with SHA-256 hash-chained immutable audit ledger. (+11 more)

### Community 68 - "Executor"
Cohesion: 0.09
Nodes (16): ExecutionPlan, ExecutionResult, Any, RawSnapshot, RunManifest, DataFrame, SourceConnector loads CSV, Parquet, JSON, or JSONL files, computes SHA-256…, Compute SHA-256 hash of a file. (+8 more)

### Community 69 - "gu"
Cohesion: 0.11
Nodes (33): Au(), ci(), ct(), Cu(), dd(), Eu(), fs(), Fu() (+25 more)

### Community 70 - "dl"
Cohesion: 0.10
Nodes (31): cl(), dl(), fl(), gl(), Il(), kl(), Ll(), Lu() (+23 more)

### Community 71 - "dl"
Cohesion: 0.09
Nodes (33): cl(), dl(), dt(), fl(), gc(), gl(), Il(), kl() (+25 more)

### Community 72 - "Z"
Cohesion: 0.12
Nodes (32): cl(), dl(), ec(), el(), eo(), fl(), gl(), Hf() (+24 more)

### Community 73 - "run_profiler"
Cohesion: 0.14
Nodes (28): profiler_tool(), Sinh schema va aggregate metadata (row/column count, null rate, distinct count,…, ColumnMetadata, ProfilerInput, ProfilerOutput, BaseModel, Profiler Tool — typed wrapper around scripts/profile_source_db.py. Returns…, run_profiler() (+20 more)

### Community 74 - "SchedulerService"
Cohesion: 0.09
Nodes (18): Any, Add a new profiling/quality check schedule and persist to DuckDB., Return all registered active schedules from DuckDB., Service to schedule dataset profiling and quality checks via APScheduler backed…, Get a specific schedule by ID from DuckDB., Delete a schedule by ID from DuckDB and APScheduler., Manually trigger a schedule immediately., Internal execution method called by APScheduler when job fires. (+10 more)

### Community 75 - "y"
Cohesion: 0.14
Nodes (31): changeLanguage(), dir(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes(), getFixedT() (+23 more)

### Community 76 - "properties"
Cohesion: 0.07
Nodes (30): maximum, minimum, type, format, type, type, properties, confidence (+22 more)

### Community 77 - "y"
Cohesion: 0.11
Nodes (38): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), clone(), cloneInstance(), dir() (+30 more)

### Community 79 - "wd"
Cohesion: 0.11
Nodes (28): ad(), ar(), cr(), dr(), Ed(), Er(), fd(), fr() (+20 more)

### Community 80 - "compilerOptions"
Cohesion: 0.07
Nodes (27): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, baseUrl, ignoreDeprecations, isolatedModules, jsx, lib (+19 more)

### Community 81 - "UnstructuredSource"
Cohesion: 0.12
Nodes (13): ImageSource, LogSource, PDFSource, Any, Path, Abstract base class for unstructured data sources (PDF, Log, Image, etc.)., DataSource stub for PDF document ingestion. Extracts text, metadata, and tables…, DataSource stub for system/application log file ingestion. Parses semi-… (+5 more)

### Community 82 - "index.ts"
Cohesion: 0.14
Nodes (21): AGENT_ALIASES, AgentMessage(), parseBold(), renderFormattedContent(), safeFormatTime(), ChatMessage(), Props, SystemMessage() (+13 more)

### Community 83 - "properties"
Cohesion: 0.08
Nodes (27): cancelled, completed, failed, running, format, type, description, type (+19 more)

### Community 84 - "zp"
Cohesion: 0.07
Nodes (37): b2(), d6(), dm(), e2(), f1(), fl(), fu, hi() (+29 more)

### Community 85 - "wt"
Cohesion: 0.15
Nodes (15): c7(), dz(), Hy(), IR(), KF(), n4, OR(), p7() (+7 more)

### Community 86 - "run_tests.py"
Cohesion: 0.17
Nodes (24): build_specs(), check_date(), check_duplicate(), check_equality(), check_ledger(), check_membership(), check_null(), check_pattern() (+16 more)

### Community 87 - "Au"
Cohesion: 0.07
Nodes (42): at(), Au(), bu(), cp(), cs(), Cu(), $e(), Eu() (+34 more)

### Community 88 - "dl"
Cohesion: 0.13
Nodes (25): cl(), dl(), el(), eo(), fl(), gl(), ia(), Il() (+17 more)

### Community 89 - "properties"
Cohesion: 0.08
Nodes (24): format, type, $ref, properties, created_at, proposal_id, rationale, rules (+16 more)

### Community 90 - "get_settings"
Cohesion: 0.12
Nodes (11): main(), SearchClientSync, Any, get, post, search_endpoint(), seed_search_index_endpoint(), get_settings() (+3 more)

### Community 91 - "log_antigravity.py"
Cohesion: 0.17
Nodes (22): build_entry(), _conv_cwds(), _conv_matches_repo(), extract_user_prompt(), get_brain_dirs(), get_logged_entry_ids(), git(), _is_repo_dir() (+14 more)

### Community 92 - "DataFrame"
Cohesion: 0.17
Nodes (15): Series, align_schema_transform(), drop_duplicates_transform(), fill_null_transform(), Any, DataFrame, quarantine_cross_field_transform(), quarantine_range_transform() (+7 more)

### Community 93 - "properties"
Cohesion: 0.09
Nodes (22): minimum, type, description, type, format, type, properties, column_count (+14 more)

### Community 94 - "dl"
Cohesion: 0.10
Nodes (29): cl(), dl(), fl(), gc(), Il(), kl(), Kt(), Ll() (+21 more)

### Community 95 - "sl"
Cohesion: 0.26
Nodes (12): cl(), el(), eo(), fl(), ia(), Il(), Ll(), Nl() (+4 more)

### Community 96 - "gu"
Cohesion: 0.16
Nodes (22): Au(), bu(), cp(), Cu(), $e(), Eu(), Fa(), gu() (+14 more)

### Community 97 - "wd"
Cohesion: 0.09
Nodes (34): ad(), add(), ar(), Br(), cr(), dr(), Ed(), fd() (+26 more)

### Community 98 - "App.tsx"
Cohesion: 0.12
Nodes (12): App(), ErrorBoundary, Props, State, resources, DashboardPage(), dashboardApi, ActivityFeedItem (+4 more)

### Community 99 - "useChatStore"
Cohesion: 0.17
Nodes (14): ChatPanel(), BatchApprovalBar(), AnomalyItem, AnomalyWorkspace(), ColumnProfile, HEALTH_COLORS, ProfileWorkspace(), RuleWorkspace() (+6 more)

### Community 100 - "a"
Cohesion: 0.22
Nodes (16): a(), Bc(), ea(), ff(), hc(), id(), Ji(), Ka() (+8 more)

### Community 101 - "test_nlp_eval.py"
Cohesion: 0.10
Nodes (20): nlp(), fixture, Test that negation scope stops at clause boundaries or punctuation., Test high severity precedence for functional faults., Test medium severity precedence for performance degradations., Test tokenization of empty or whitespace strings., Test reduction of elongated repeated consonants., Test that legitimate double characters in preserved words are not altered. (+12 more)

### Community 102 - "agent-trace.schema.json"
Cohesion: 0.10
Nodes (18): agent_type, proposal_id, rules, step_index, trace_id, description, timestamp, required (+10 more)

### Community 103 - "properties"
Cohesion: 0.11
Nodes (18): description, type, description, type, description, type, type, properties (+10 more)

### Community 104 - "vc"
Cohesion: 0.21
Nodes (15): Bc(), ea(), exists(), ff(), Ga(), Ji(), Ka(), mo() (+7 more)

### Community 105 - "run_validator"
Cohesion: 0.25
Nodes (16): Agent-facing data-quality tools. These are the ONLY data-quality operations the…, Kiem tra rule co hop le hay khong: operator phai nam trong whitelist,…, validator_tool(), _do_validate(), BaseModel, Validator Tool — typed wrapper around scripts/validate_rules.py. Checks whether…, RuleValidationResult, run_validator() (+8 more)

### Community 106 - "Gt"
Cohesion: 0.27
Nodes (12): ef(), gf(), Gt(), If(), j(), jf(), kf(), Lf() (+4 more)

### Community 107 - "api.ts"
Cohesion: 0.23
Nodes (15): ChatInput(), SessionItem, Sidebar(), approvalsApi, authApi, benchmarksApi, clearChatDatabase(), datasetsApi (+7 more)

### Community 108 - "profile-result.schema.json"
Cohesion: 0.11
Nodes (16): column_name, profile_id, sha256_hash, source_name, description, dtype, required, $schema (+8 more)

### Community 109 - "vo"
Cohesion: 0.22
Nodes (14): cm(), eg(), Ei(), eT(), gE(), jd(), kp(), kS() (+6 more)

### Community 110 - "vl"
Cohesion: 0.14
Nodes (18): add(), bl(), ef(), gf(), Hf(), hl(), If(), jf() (+10 more)

### Community 112 - "websocket.ts"
Cohesion: 0.22
Nodes (7): agentSocket, AgentWebSocket, formatDecisionRecordSummary(), parseChainOfThoughtToRecord(), parseDecisionRecord(), AgentEvent, DecisionRecord

### Community 113 - "string"
Cohesion: 0.12
Nodes (18): description, type, observation, null, description, type, previous_event_hash, target_id (+10 more)

### Community 114 - "AgentState"
Cohesion: 0.22
Nodes (13): build_graph(), Route based on whether an error occurred during analysis., should_continue(), analyze_node(), Tạo response từ analysis., # TODO: Thêm logic tạo response thực tế, Phân tích query từ user., # TODO: Thêm logic phân tích thực tế (+5 more)

### Community 115 - "schema.sql"
Cohesion: 0.12
Nodes (15): agent_traces, audit_log, datasets, execution_authorizations, job_runs, messages, profile_results, quality_rules (+7 more)

### Community 116 - "up"
Cohesion: 0.16
Nodes (14): ap(), dp(), $e(), ft(), ip(), kp(), lp(), np() (+6 more)

### Community 117 - "schemas.py"
Cohesion: 0.07
Nodes (42): ExecutableTransformPlan, LLMAdapter, LLMResponse, BaseModel, Proposes data quality and transformation rules based on context., RuleSpec, RepairLoop, RepairLoopResult (+34 more)

### Community 118 - "enum"
Cohesion: 0.13
Nodes (15): deprecated, pending, proposed, superseded, approved, rejected, status, default (+7 more)

### Community 119 - ".chat"
Cohesion: 0.16
Nodes (9): LLMUnavailableException, Any, Exception, Raised when structured JSON output from LLM fails validation or parsing., Get structured JSON output from the model., Convert OpenAI-style tool specs to Gemini format., Send chat messages to the model. messages: [{"role":…, Raised when the LLM service or provider is unavailable or fails. (+1 more)

### Community 120 - "vc"
Cohesion: 0.15
Nodes (19): Bc(), cn(), ea(), exists(), ff(), Ga(), Ji(), Ka() (+11 more)

### Community 121 - "nc"
Cohesion: 0.29
Nodes (14): Ac(), ao(), be(), ea(), fc(), fo(), k(), mo() (+6 more)

### Community 122 - "compile_rules.py"
Cohesion: 0.32
Nodes (12): compile_rule(), format_py_literal(), format_sql_literal(), main(), render_markdown(), _is_number(), load_rules(), load_schema() (+4 more)

### Community 123 - "run_test_runner"
Cohesion: 0.32
Nodes (12): Any, Thuc thi cac executable check (tu compiler_tool) tren Source DB o che do READ-…, test_runner_tool(), run_test_runner(), TestRunnerInput, A malformed check's SQL error must not crash the whole tool call — it should…, test_failure_db_not_found(), test_failure_invalid_input_empty_compiled_rules() (+4 more)

### Community 124 - "up"
Cohesion: 0.19
Nodes (12): ap(), dp(), $e(), ft(), ip(), kp(), lp(), rp() (+4 more)

### Community 125 - "test_real_public_ingestion.py"
Cohesion: 0.15
Nodes (12): Verify all 4 VinGroup mapped real datasets exist in data/vingroup_real/., Verify mapped real VinFast EV Telemetry contains VINs, Speed, SOC, and Voltage., Verify mapped real V-GREEN Charging Stations contains Station ID, Power kW, and…, Verify mapped real Xanh SM Trips contains Trip ID, Vehicle VIN, Latitude,…, Verify mapped real Xanh SM Feedback contains Feedback ID, Customer ID, and Raw…, Verify all 4 raw public datasets exist in data/raw_public/., test_raw_public_datasets_exist(), test_real_vgreen_charging_stations_schema() (+4 more)

### Community 126 - "AgentId"
Cohesion: 0.23
Nodes (9): AgentAvatar(), ICON_MAP, ICON_SIZES, Props, SIZES, TypingIndicator(), AuditEntry, AuditWorkspace() (+1 more)

### Community 127 - "chatStore.ts"
Cohesion: 0.26
Nodes (9): AgentStatusBar(), ICON_MAP, autoRepairJson(), ChatState, extractAllValidJsons(), extractObservationJsons(), syncWorkspaceFromMessages(), AgentStatus (+1 more)

### Community 128 - "li"
Cohesion: 0.23
Nodes (12): ba(), ci(), dd(), di(), fi(), Ii(), is(), li() (+4 more)

### Community 129 - "required"
Cohesion: 0.18
Nodes (10): action, actor, event_hash, event_id, target_table, description, required, $schema (+2 more)

### Community 130 - "li"
Cohesion: 0.24
Nodes (11): ba(), ci(), dd(), di(), fi(), Ii(), is(), li() (+3 more)

### Community 131 - "tool"
Cohesion: 0.27
Nodes (9): AST, calculate(), _eval_node(), Tìm kiếm thông tin trong knowledge base. Args: query: Câu hỏi cần tìm kiếm…, # TODO: Implement actual search logic (e.g., RAG with vector store), Tính toán biểu thức toán học an toàn (không dùng eval). Hỗ trợ: +, -, *, /, //,…, Recursively evaluate AST node using safe operators only., search_knowledge() (+1 more)

### Community 132 - "run-manifest.schema.json"
Cohesion: 0.20
Nodes (9): dataset_key, run_id, started_at, description, status, required, $schema, title (+1 more)

### Community 133 - "rulespec.schema.json"
Cohesion: 0.20
Nodes (9): rule_expression, rule_id, rule_type, description, status, required, $schema, title (+1 more)

### Community 134 - "profile_source_db.py"
Cohesion: 0.42
Nodes (9): get_declared_types(), get_pk_columns(), get_tables(), log_table_summary(), main(), profile_table(), Connection, render_markdown() (+1 more)

### Community 135 - "AppShell.tsx"
Cohesion: 0.44
Nodes (6): AppShell(), ROLE_OPTIONS, TopBar(), AppState, useAppStore, UserRole

### Community 136 - "fetch_real_public_datasets.py"
Cohesion: 0.22
Nodes (8): fetch_real_ride_hailing(), fetch_real_st_evcdp(), fetch_real_uit_vsfc(), fetch_real_vehicle_telemetry(), Fetches real ST-EVCDP charging station dataset from GitHub public repository., Fetches real Ride Hailing Transaction Dataset., Fetches real UIT-VSFC Vietnamese Sentiment/Aspect dataset from HuggingFace /…, Fetches real Vehicle Energy & Telemetry (JAC IEV40 CAN-bus time series).

### Community 139 - "Kt"
Cohesion: 0.25
Nodes (11): ef(), gf(), If(), jf(), jl(), kf(), Kt(), Lf() (+3 more)

### Community 140 - "enum"
Cohesion: 0.29
Nodes (7): drop, flag, impute_deterministic, quarantine, enum, type, action

### Community 141 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 142 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 143 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 144 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 145 - "submit_log.py"
Cohesion: 0.43
Nodes (6): _archive(), main(), Path, Append pending file to today's archive. Never overwrites existing data., Failure path: put pending back at LOG_FILE so the next push retries. If hook…, _restore_pending()

### Community 146 - "ConnectionManager"
Cohesion: 0.38
Nodes (3): ConnectionManager, Any, WebSocket

### Community 147 - "auth.py"
Cohesion: 0.31
Nodes (9): auth_status(), get_current_user(), login(), LoginRequest, LoginResponse, logout(), BaseModel, get (+1 more)

### Community 148 - "enum"
Cohesion: 0.33
Nodes (6): error, info, warning, severity, enum, type

### Community 150 - "devDependencies"
Cohesion: 0.50
Nodes (3): devDependencies, puppeteer, puppeteer

### Community 151 - "build"
Cohesion: 0.67
Nodes (3): build(), main(), Path

## Knowledge Gaps
- **388 isolated node(s):** `_pyrun.sh script`, `setup.sh script`, `setup_hooks.sh script`, `name`, `private` (+383 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **35 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `c()` connect `c` to `index-BaGgQfLv.js`, `n`, `o`, `index-to5fYhfR.js`, `i`, `Be`, `i`, `has`, `i`, `i`, `i`, `t`, `i`, `nc`, `i`, `pI`, `hT`, `n`, `n`, `Fn`, `n`, `hu`, `gu`, `n`, `gu`, `gu`, `Z`, `zp`, `wt`, `gu`, `a`, `vc`, `vo`, `vc`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `Rn()` connect `t` to `wd`, `c`, `wd`, `index-BRVdCVNO.js`, `wd`, `wd`, `wd`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `W` connect `c` to `index-BaGgQfLv.js`, `n`, `pI`, `dl`, `dl`, `index-Bh8v7zJ5.js`, `Z`, `o`, `Z`, `vo`, `Be`, `zp`, `wt`, `has`, `dl`, `dl`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 127 inferred relationships involving `o()` (e.g. with `index-BaGgQfLv.js` and `$5()`) actually correct?**
  _`o()` has 127 INFERRED edges - model-reasoned connections that need verification._
- **Are the 111 inferred relationships involving `n()` (e.g. with `index-BaGgQfLv.js` and `a4`) actually correct?**
  _`n()` has 111 INFERRED edges - model-reasoned connections that need verification._
- **Are the 126 inferred relationships involving `r()` (e.g. with `index-BaGgQfLv.js` and `a4`) actually correct?**
  _`r()` has 126 INFERRED edges - model-reasoned connections that need verification._
- **Are the 138 inferred relationships involving `c()` (e.g. with `b()` and `ep()`) actually correct?**
  _`c()` has 138 INFERRED edges - model-reasoned connections that need verification._