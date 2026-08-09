# Graph Report - .  (2026-08-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 6383 nodes · 20158 edges · 210 communities (174 shown, 36 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 3139 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `69e756d1`
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
- index-DlyLF_Ln.js
- index-to5fYhfR.js
- pc
- index-DZrVSfRD.js
- Profiler
- i
- routes/__init__.py
- VietnameseNLPService
- test_v2_features.py
- i
- i
- Be
- BenchmarkHarness
- wd
- sub_agents.py
- i
- o
- pc
- i
- api/hitl.py
- $E
- repair_loop.py
- BaseTool
- i
- t
- r
- dl
- wd
- n
- i
- nc
- test_tools.py
- hT
- n
- wd
- wd
- hu
- wd
- properties
- Ad
- gu
- y
- DuckDBManager
- dependencies
- test_db.py
- properties
- RuleExecutorTool
- datasets.py
- y
- fn
- Z
- properties
- hu
- y
- y
- ErrorCode
- hu
- y
- gu
- AuditService
- n
- Fn
- gu
- dl
- dl
- run_profiler
- SchedulerService
- y
- properties
- Gt
- Z
- compilerOptions
- wd
- StructuredSource
- index.ts
- properties
- n
- run_tests.py
- t
- dl
- properties
- algolia_search.py
- log_antigravity.py
- DataFrame
- properties
- dl
- sl
- gu
- test_nlp_eval.py
- App.tsx
- useChatStore
- uS
- agent-trace.schema.json
- vc
- run_validator
- api.ts
- profile-result.schema.json
- string
- properties
- wd
- websocket.ts
- AgentState
- schema.sql
- up
- vl
- enum
- .chat
- vc
- dq_tools.py
- compile_rules.py
- su
- test_integration.py
- FastAPI
- er
- test_real_public_ingestion.py
- AgentId
- chatStore.ts
- li
- required
- li
- Kt
- Validator
- tool
- run-manifest.schema.json
- rulespec.schema.json
- profile_source_db.py
- ky
- AppShell.tsx
- fetch_real_public_datasets.py
- ConversationStore
- enum
- $schema
- $schema
- $schema
- $schema
- submit_log.py
- ConnectionManager
- enum
- sw
- devDependencies
- build
- ApprovalSummary.tsx
- fetch_weather.py
- generate_scrape_report.py
- ingest_and_map_real_data
- .to_function_spec
- .build_context
- eval/__init__.py
- demo.sh
- _pyrun.sh
- reset.sh
- seed.sh
- setup.sh
- setup_hooks.sh script
- test_severity_precedence_critical
- test_severity_precedence_negated_fault
- test_eval_held_out_dataset_metrics
- test_tokenize_multiple_punctuation
- test_is_accentless_true
- test_accentless_dictionary_mapping
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
- test_tokenize_punctuation_marks
- test_negation_scope_multiple_negations

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
- `_do_compile()` --calls--> `load_schema()`  [INFERRED]
  src/tools/dq/compiler_tool.py → scripts/validate_rules.py

## Import Cycles
- None detected.

## Communities (210 total, 36 thin omitted)

### Community 0 - "index-BaGgQfLv.js"
Cohesion: 0.01
Nodes (229): $3(), $7, $8, a5(), a7(), aF(), aj(), aq() (+221 more)

### Community 1 - "n"
Cohesion: 0.02
Nodes (176): a1(), a4, ac(), Ah(), Al(), ap(), Ar(), Au() (+168 more)

### Community 2 - "c"
Cohesion: 0.06
Nodes (148): c(), Te(), ue(), w(), A(), b_(), b8(), BB (+140 more)

### Community 3 - "index-CXFVbvtc.js"
Cohesion: 0.03
Nodes (93): add(), addPostProcessor(), ap(), bl(), bs(), componentDidCatch(), connect(), cp() (+85 more)

### Community 4 - "test_agents.py"
Cohesion: 0.05
Nodes (76): LLMResponse, AnomalyAgent, Sub-agent specialized in anomaly detection across telemetry data., DiagnosisAgent, Sub-agent that cross-references NLP insights with telemetry to diagnose root…, ExecutorAgent, Sub-agent that executes approved quality rules., ProfilerAgent (+68 more)

### Community 5 - "index-BRVdCVNO.js"
Cohesion: 0.03
Nodes (80): add(), addPostProcessor(), ba(), bl(), bs(), clone(), cloneInstance(), connect() (+72 more)

### Community 6 - "index-cSvGY2XO.js"
Cohesion: 0.03
Nodes (97): ad(), add(), addNamespaces(), addPostProcessor(), addResource(), addResourceBundle(), addResources(), bl() (+89 more)

### Community 7 - "index-Bh8v7zJ5.js"
Cohesion: 0.04
Nodes (66): addPostProcessor(), ap(), bs(), connect(), cs(), De(), df(), dp() (+58 more)

### Community 8 - "get_db"
Cohesion: 0.03
Nodes (68): BaseSettings, compute_file_sha256(), ingest_scraped_data(), Compute SHA-256 hash of a file., Ingest all CSVs from data/scraped/*.csv into DuckDB xanhsm_feedback table., _SKIP_LLM, get_activity(), get_stats() (+60 more)

### Community 9 - "index-DlyLF_Ln.js"
Cohesion: 0.03
Nodes (86): ad(), add(), addPostProcessor(), af(), bl(), Br(), bs(), bu() (+78 more)

### Community 10 - "index-to5fYhfR.js"
Cohesion: 0.04
Nodes (55): addNamespaces(), addPostProcessor(), addResource(), addResourceBundle(), addResources(), at(), bl(), Bo() (+47 more)

### Community 11 - "pc"
Cohesion: 0.06
Nodes (75): aa(), Ac(), af(), ao(), ap(), bc(), be(), cf() (+67 more)

### Community 12 - "index-DZrVSfRD.js"
Cohesion: 0.04
Nodes (58): addPostProcessor(), bs(), ci(), componentDidCatch(), connect(), cs(), ct(), dd() (+50 more)

### Community 13 - "Profiler"
Cohesion: 0.06
Nodes (23): ErrorInjector, GroundTruthLabel, Any, BaseModel, DataFrame, Fixed-seed synthetic error injector across 15 fault families and configurable…, benchmark_info(), BenchmarkRunRequest (+15 more)

### Community 14 - "i"
Cohesion: 0.09
Nodes (82): a(), aa(), ae(), as(), b(), bd(), bi(), Bo() (+74 more)

### Community 15 - "routes/__init__.py"
Cohesion: 0.04
Nodes (91): execute_endpoint(), execute_transform_endpoint(), list_executions(), Any, get, post, Request, acknowledge_alert_endpoint() (+83 more)

### Community 16 - "VietnameseNLPService"
Cohesion: 0.05
Nodes (47): Protocol, Baseline, BaselineA1, BaselineA2, BaselineC0, BaselineC1, BaselineR0, BaselineResult (+39 more)

### Community 17 - "test_v2_features.py"
Cohesion: 0.05
Nodes (47): check_role_permission(), Check if given role has permission for a specific action., Alert, AlertService, AlertSeverity, Any, BaseModel, Enum (+39 more)

### Community 18 - "i"
Cohesion: 0.08
Nodes (67): aa(), ac(), ao(), at(), ba(), be(), bi(), Bo() (+59 more)

### Community 19 - "i"
Cohesion: 0.08
Nodes (63): aa(), Ac(), af(), bc(), be(), C(), ca(), cc() (+55 more)

### Community 20 - "Be"
Cohesion: 0.04
Nodes (94): $2(), _6(), A0(), a6(), aE(), am(), aS(), av() (+86 more)

### Community 21 - "BenchmarkHarness"
Cohesion: 0.06
Nodes (40): BenchmarkHarness, BenchmarkMetrics, compute_f1(), Path, Benchmark harness for C0 vs C1 vs A1 comparison., Dynamically compute cross-system link rate from multi-domain fault predictions., Run deterministic baseline (C0)., Run single LLM call baseline (C1). (+32 more)

### Community 22 - "wd"
Cohesion: 0.06
Nodes (61): ad(), An(), ar(), at(), Bn(), Bt(), cr(), dr() (+53 more)

### Community 23 - "sub_agents.py"
Cohesion: 0.08
Nodes (48): LLMService, ContextBuilder, Any, Strips any potential raw row data keys from the profile., Assembles data profile + target schema into a formatted prompt context., Assembles data profile and target schema into structured prompts for LLM…, AnomalyDetectorAgent, BoundedSubAgent (+40 more)

### Community 24 - "i"
Cohesion: 0.10
Nodes (72): a(), ae(), as(), b(), bd(), bi(), Bo(), C() (+64 more)

### Community 25 - "o"
Cohesion: 0.03
Nodes (105): $5(), a9(), accessor(), aee(), ag(), ak(), AW(), az (+97 more)

### Community 26 - "pc"
Cohesion: 0.08
Nodes (51): Ac(), af(), ao(), bc(), be(), cf(), dc(), Du() (+43 more)

### Community 27 - "i"
Cohesion: 0.07
Nodes (70): aa(), ac(), ao(), at(), ba(), be(), bi(), Bo() (+62 more)

### Community 28 - "api/hitl.py"
Cohesion: 0.05
Nodes (53): datetime, generate_synthetic_dataset(), Generates a realistic synthetic Vietnam ride-hailing dataset of 50,000 trips., generate_vingroup_datasets(), Generates 4 synthetic enterprise datasets for VinGroup / VinFast / Xanh SM /…, generate_sample_dataset(), main(), DataFrame (+45 more)

### Community 29 - "$E"
Cohesion: 0.08
Nodes (30): bM(), dn(), DT(), $E(), E0(), Fv(), gM(), hM() (+22 more)

### Community 30 - "repair_loop.py"
Cohesion: 0.23
Nodes (8): ExecutableTransformPlan, LLMAdapter, LLMResponse, BaseModel, Proposes data quality and transformation rules based on context., RuleSpec, RepairLoop, RepairLoopResult

### Community 31 - "BaseTool"
Cohesion: 0.09
Nodes (35): send_chat_message(), BaseModel, Enum, str, StateMachine, WorkflowState, BaseTool, BaseModel (+27 more)

### Community 32 - "i"
Cohesion: 0.07
Nodes (73): aa(), ac(), af(), ao(), ba(), be(), bi(), Bo() (+65 more)

### Community 33 - "t"
Cohesion: 0.07
Nodes (67): addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), b(), changeLanguage(), clone() (+59 more)

### Community 34 - "r"
Cohesion: 0.11
Nodes (41): addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), b(), ce(), constructor() (+33 more)

### Community 35 - "dl"
Cohesion: 0.08
Nodes (33): Br(), ca(), cn(), dl(), dt(), gl(), jr(), kl() (+25 more)

### Community 36 - "wd"
Cohesion: 0.07
Nodes (57): ar(), bn(), Bt(), Cn(), cr(), Dn(), dp(), dr() (+49 more)

### Community 37 - "n"
Cohesion: 0.08
Nodes (70): a(), addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), An(), b() (+62 more)

### Community 38 - "i"
Cohesion: 0.10
Nodes (64): a(), an(), b(), ba(), bd(), ca(), cd(), ce() (+56 more)

### Community 39 - "nc"
Cohesion: 0.08
Nodes (57): aa(), ac(), ao(), Bc(), be(), bi(), cc(), cf() (+49 more)

### Community 40 - "test_tools.py"
Cohesion: 0.06
Nodes (49): AnomalyDetectorTool, NLPExtractorTool, DataProfilerTool, RuleProposerTool, TelemetryQueryTool, mock_llm(), fixture, tmp_db() (+41 more)

### Community 41 - "hT"
Cohesion: 0.08
Nodes (18): ao(), cz(), DB(), Em(), gB(), gk(), hT(), hx() (+10 more)

### Community 42 - "n"
Cohesion: 0.08
Nodes (70): a(), addNamespaces(), addResource(), addResourceBundle(), addResources(), ae(), An(), b() (+62 more)

### Community 43 - "wd"
Cohesion: 0.07
Nodes (55): ad(), ar(), Bn(), Bt(), componentDidCatch(), cr(), deprecate(), dr() (+47 more)

### Community 44 - "wd"
Cohesion: 0.07
Nodes (55): ar(), Bn(), Bt(), componentDidCatch(), cr(), deprecate(), dr(), Ed() (+47 more)

### Community 45 - "hu"
Cohesion: 0.07
Nodes (49): ap(), Au(), bu(), cn(), Cu(), dp(), dt(), $e() (+41 more)

### Community 46 - "wd"
Cohesion: 0.08
Nodes (52): ar(), bn(), Bt(), Cn(), cr(), Dn(), Ed(), En() (+44 more)

### Community 47 - "properties"
Cohesion: 0.04
Nodes (48): columns, dataset_name, name, schema, version, description, properties, required (+40 more)

### Community 48 - "Ad"
Cohesion: 0.07
Nodes (36): aB(), Ad(), Bd(), By, c7(), dz(), H_(), Hy() (+28 more)

### Community 49 - "gu"
Cohesion: 0.07
Nodes (47): ad(), at(), Au(), bu(), cd(), Cu(), dt(), et() (+39 more)

### Community 50 - "y"
Cohesion: 0.11
Nodes (36): changeLanguage(), dir(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes(), getFixedT() (+28 more)

### Community 51 - "DuckDBManager"
Cohesion: 0.06
Nodes (18): DuckDBPyConnection, DuckDBManager, audit_db(), fixture, Create a fresh temporary database for audit chain testing., fixture, Create a temporary DuckDB database for testing., tmp_db() (+10 more)

### Community 52 - "dependencies"
Cohesion: 0.04
Nodes (44): framer-motion, dependencies, framer-motion, i18next, lucide-react, react, react-dom, react-i18next (+36 more)

### Community 53 - "test_db.py"
Cohesion: 0.05
Nodes (43): compute_sha256(), map_vgreen_telemetry(), map_vinfast_bms(), map_xanhsm_feedback(), map_xanhsm_trips(), DataFrame, Map real_xanh_sm_customer_feedback.csv to xanhsm_feedback table schema., Map real_vgreen_charging_stations.csv to vgreen_telemetry table schema. (+35 more)

### Community 54 - "properties"
Cohesion: 0.05
Nodes (44): integer, description, type, description, type, minimum, type, null (+36 more)

### Community 55 - "RuleExecutorTool"
Cohesion: 0.09
Nodes (33): run_storyline_demo(), Validate webhook URL against SSRF attacks by checking scheme and resolving DNS…, validate_webhook_url(), _check_sql_safety(), compile_rule_spec(), _parse_val(), BaseModel, Infer target table from rule expression column names. (+25 more)

### Community 56 - "datasets.py"
Cohesion: 0.06
Nodes (48): benchmark_dataset(), execute_rules_on_dataset(), get_dataset(), list_datasets(), profile_dataset(), propose_rules_for_dataset(), Any, get (+40 more)

### Community 57 - "y"
Cohesion: 0.13
Nodes (32): changeLanguage(), dir(), exists(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes() (+24 more)

### Community 58 - "fn"
Cohesion: 0.11
Nodes (34): an(), bn(), Bt(), Cn(), dn(), fd(), fn(), Gn() (+26 more)

### Community 59 - "Z"
Cohesion: 0.09
Nodes (41): bl(), Br(), cl(), dl(), Do(), el(), eo(), fl() (+33 more)

### Community 60 - "properties"
Cohesion: 0.06
Nodes (39): minimum, type, number, cost_usd, type, description, type, null (+31 more)

### Community 61 - "hu"
Cohesion: 0.06
Nodes (50): ap(), at(), bu(), cp(), dp(), dt(), Du(), $e() (+42 more)

### Community 62 - "y"
Cohesion: 0.10
Nodes (41): addNamespaces(), addResource(), addResourceBundle(), addResources(), changeLanguage(), clone(), cloneInstance(), dir() (+33 more)

### Community 63 - "y"
Cohesion: 0.14
Nodes (31): changeLanguage(), dir(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes(), getFixedT() (+23 more)

### Community 64 - "ErrorCode"
Cohesion: 0.16
Nodes (26): ErrorCode, execute(), Enum, Exception, str, Shared plumbing for the data-quality Tool Layer (Task 2). Every tool in…, Raised by tool internals; carries a standardized ErrorCode., Run fn() with a soft timeout, raising ToolError(TIMEOUT) if exceeded. Uses a… (+18 more)

### Community 65 - "hu"
Cohesion: 0.06
Nodes (57): ap(), Au(), ci(), Cu(), dd(), di(), dp(), et() (+49 more)

### Community 66 - "y"
Cohesion: 0.15
Nodes (29): changeLanguage(), dir(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes(), getLanguagePartFromCode() (+21 more)

### Community 67 - "gu"
Cohesion: 0.10
Nodes (36): Au(), ci(), ct(), Cu(), dd(), Eu(), fa(), fs() (+28 more)

### Community 68 - "AuditService"
Cohesion: 0.10
Nodes (19): AuditRecord, AuditStore, Any, BaseModel, AuditService, Any, datetime, Enhanced audit trail with SHA-256 hash-chained immutable audit ledger. (+11 more)

### Community 69 - "n"
Cohesion: 0.13
Nodes (31): Au(), bd(), cd(), Cu(), ds(), et(), Eu(), Fa() (+23 more)

### Community 70 - "Fn"
Cohesion: 0.08
Nodes (46): Bt(), Cn(), deprecate(), Dn(), dt(), en(), Er(), error() (+38 more)

### Community 71 - "gu"
Cohesion: 0.10
Nodes (34): Au(), ci(), ct(), Cu(), dd(), Eu(), fs(), ft() (+26 more)

### Community 72 - "dl"
Cohesion: 0.16
Nodes (21): cl(), dl(), fl(), Il(), kl(), Ll(), ma(), Nl() (+13 more)

### Community 73 - "dl"
Cohesion: 0.09
Nodes (33): cl(), dl(), el(), fl(), gc(), gl(), Il(), kl() (+25 more)

### Community 74 - "run_profiler"
Cohesion: 0.17
Nodes (21): profiler_tool(), Sinh schema va aggregate metadata (row/column count, null rate, distinct count,…, ColumnMetadata, ProfilerInput, ProfilerOutput, BaseModel, Profiler Tool — typed wrapper around scripts/profile_source_db.py. Returns…, run_profiler() (+13 more)

### Community 75 - "SchedulerService"
Cohesion: 0.09
Nodes (18): Any, Add a new profiling/quality check schedule and persist to DuckDB., Return all registered active schedules from DuckDB., Service to schedule dataset profiling and quality checks via APScheduler backed…, Get a specific schedule by ID from DuckDB., Delete a schedule by ID from DuckDB and APScheduler., Manually trigger a schedule immediately., Internal execution method called by APScheduler when job fires. (+10 more)

### Community 76 - "y"
Cohesion: 0.14
Nodes (31): changeLanguage(), dir(), extendTranslation(), extractFromKey(), formatLanguageCode(), getBestMatchFromCodes(), getFallbackCodes(), getFixedT() (+23 more)

### Community 77 - "properties"
Cohesion: 0.07
Nodes (30): maximum, minimum, type, format, type, type, properties, confidence (+22 more)

### Community 78 - "Gt"
Cohesion: 0.10
Nodes (29): add(), af(), ct(), df(), Du(), ef(), gf(), Gt() (+21 more)

### Community 80 - "Z"
Cohesion: 0.11
Nodes (35): cl(), dl(), ec(), el(), eo(), fl(), gl(), Hf() (+27 more)

### Community 81 - "compilerOptions"
Cohesion: 0.07
Nodes (27): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, baseUrl, ignoreDeprecations, isolatedModules, jsx, lib (+19 more)

### Community 82 - "wd"
Cohesion: 0.12
Nodes (26): ad(), ar(), cr(), dr(), Ed(), Er(), fr(), Gd() (+18 more)

### Community 83 - "StructuredSource"
Cohesion: 0.06
Nodes (28): ABC, DataFrame, SourceConnector loads CSV, Parquet, JSON, or JSONL files, computes SHA-256…, Compute SHA-256 hash of a file., Load a structured data file into a Pandas DataFrame., Loads the source file, calculates SHA-256 checksum, row count, and schema, and…, SourceConnector, DataSource (+20 more)

### Community 84 - "index.ts"
Cohesion: 0.14
Nodes (21): AGENT_ALIASES, AgentMessage(), parseBold(), renderFormattedContent(), safeFormatTime(), ChatMessage(), Props, SystemMessage() (+13 more)

### Community 85 - "properties"
Cohesion: 0.08
Nodes (27): cancelled, completed, failed, running, format, type, description, type (+19 more)

### Community 86 - "n"
Cohesion: 0.11
Nodes (40): a(), Bc(), bd(), cd(), ce(), cp(), ea(), ep() (+32 more)

### Community 87 - "run_tests.py"
Cohesion: 0.17
Nodes (24): build_specs(), check_date(), check_duplicate(), check_equality(), check_ledger(), check_membership(), check_null(), check_pattern() (+16 more)

### Community 88 - "t"
Cohesion: 0.12
Nodes (29): a(), ao(), as(), bi(), Bo(), ci(), es(), fc() (+21 more)

### Community 89 - "dl"
Cohesion: 0.13
Nodes (25): cl(), dl(), el(), eo(), fl(), gl(), ia(), Il() (+17 more)

### Community 90 - "properties"
Cohesion: 0.08
Nodes (24): format, type, $ref, properties, created_at, proposal_id, rationale, rules (+16 more)

### Community 91 - "algolia_search.py"
Cohesion: 0.13
Nodes (10): main(), SearchClientSync, Any, get, post, search_endpoint(), seed_search_index_endpoint(), AlgoliaSearchService (+2 more)

### Community 92 - "log_antigravity.py"
Cohesion: 0.17
Nodes (22): build_entry(), _conv_cwds(), _conv_matches_repo(), extract_user_prompt(), get_brain_dirs(), get_logged_entry_ids(), git(), _is_repo_dir() (+14 more)

### Community 93 - "DataFrame"
Cohesion: 0.17
Nodes (15): Series, align_schema_transform(), drop_duplicates_transform(), fill_null_transform(), Any, DataFrame, quarantine_cross_field_transform(), quarantine_range_transform() (+7 more)

### Community 94 - "properties"
Cohesion: 0.09
Nodes (22): minimum, type, description, type, format, type, properties, column_count (+14 more)

### Community 95 - "dl"
Cohesion: 0.10
Nodes (29): cl(), dl(), fl(), gc(), Il(), kl(), Kt(), Ll() (+21 more)

### Community 96 - "sl"
Cohesion: 0.26
Nodes (12): cl(), el(), eo(), fl(), ia(), Il(), Ll(), Nl() (+4 more)

### Community 97 - "gu"
Cohesion: 0.10
Nodes (32): at(), Au(), bu(), cp(), Cu(), dt(), $e(), Eu() (+24 more)

### Community 98 - "test_nlp_eval.py"
Cohesion: 0.10
Nodes (20): nlp(), fixture, Test that negation scope stops at clause boundaries or punctuation., Test high severity precedence for functional faults., Test medium severity precedence for performance degradations., Test tokenization of empty or whitespace strings., Test reduction of elongated repeated consonants., Test that legitimate double characters in preserved words are not altered. (+12 more)

### Community 99 - "App.tsx"
Cohesion: 0.12
Nodes (12): App(), ErrorBoundary, Props, State, resources, DashboardPage(), dashboardApi, ActivityFeedItem (+4 more)

### Community 100 - "useChatStore"
Cohesion: 0.17
Nodes (14): ChatPanel(), BatchApprovalBar(), AnomalyItem, AnomalyWorkspace(), ColumnProfile, HEALTH_COLORS, ProfileWorkspace(), RuleWorkspace() (+6 more)

### Community 101 - "uS"
Cohesion: 0.11
Nodes (29): ba(), bc(), BS(), bx(), dE(), gf(), H2(), Il() (+21 more)

### Community 102 - "agent-trace.schema.json"
Cohesion: 0.10
Nodes (18): agent_type, proposal_id, rules, step_index, trace_id, description, timestamp, required (+10 more)

### Community 103 - "vc"
Cohesion: 0.21
Nodes (15): Bc(), ea(), exists(), ff(), Ga(), Ji(), Ka(), mo() (+7 more)

### Community 104 - "run_validator"
Cohesion: 0.35
Nodes (12): Kiem tra rule co hop le hay khong: operator phai nam trong whitelist,…, validator_tool(), _do_validate(), run_validator(), ValidatorInput, test_failure_path_missing_db_reported_with_standard_error_code(), test_failure_invalid_input_empty_rules(), test_failure_invalid_type_operator_on_text_column() (+4 more)

### Community 105 - "api.ts"
Cohesion: 0.23
Nodes (15): ChatInput(), SessionItem, Sidebar(), approvalsApi, authApi, benchmarksApi, clearChatDatabase(), datasetsApi (+7 more)

### Community 106 - "profile-result.schema.json"
Cohesion: 0.11
Nodes (16): column_name, profile_id, sha256_hash, source_name, description, dtype, required, $schema (+8 more)

### Community 107 - "string"
Cohesion: 0.12
Nodes (18): tool_name, description, type, null, description, type, previous_event_hash, target_id (+10 more)

### Community 108 - "properties"
Cohesion: 0.11
Nodes (18): description, type, description, type, description, type, type, properties (+10 more)

### Community 109 - "wd"
Cohesion: 0.14
Nodes (22): ad(), ar(), Br(), cr(), dr(), Ed(), Gd(), ir() (+14 more)

### Community 111 - "websocket.ts"
Cohesion: 0.22
Nodes (7): agentSocket, AgentWebSocket, formatDecisionRecordSummary(), parseChainOfThoughtToRecord(), parseDecisionRecord(), AgentEvent, DecisionRecord

### Community 112 - "AgentState"
Cohesion: 0.22
Nodes (13): build_graph(), Route based on whether an error occurred during analysis., should_continue(), analyze_node(), Tạo response từ analysis., # TODO: Thêm logic tạo response thực tế, Phân tích query từ user., # TODO: Thêm logic phân tích thực tế (+5 more)

### Community 113 - "schema.sql"
Cohesion: 0.12
Nodes (15): agent_traces, audit_log, datasets, execution_authorizations, job_runs, messages, profile_results, quality_rules (+7 more)

### Community 114 - "up"
Cohesion: 0.15
Nodes (15): ap(), dp(), $e(), ft(), ip(), kp(), lp(), np() (+7 more)

### Community 115 - "vl"
Cohesion: 0.13
Nodes (20): add(), af(), bl(), ef(), gf(), Hf(), hl(), If() (+12 more)

### Community 116 - "enum"
Cohesion: 0.13
Nodes (15): deprecated, pending, proposed, superseded, approved, rejected, status, default (+7 more)

### Community 117 - ".chat"
Cohesion: 0.16
Nodes (9): LLMUnavailableException, Any, Exception, Raised when structured JSON output from LLM fails validation or parsing., Get structured JSON output from the model., Convert OpenAI-style tool specs to Gemini format., Send chat messages to the model. messages: [{"role":…, Raised when the LLM service or provider is unavailable or fails. (+1 more)

### Community 118 - "vc"
Cohesion: 0.21
Nodes (15): Bc(), ea(), exists(), ff(), Ga(), Ji(), Ka(), mo() (+7 more)

### Community 119 - "dq_tools.py"
Cohesion: 0.22
Nodes (15): compiler_tool(), Any, Agent-facing data-quality tools. These are the ONLY data-quality operations the…, Bien dich cac rule hop le thanh executable checks (Python expression + SQL…, Thuc thi cac executable check (tu compiler_tool) tren Source DB o che do READ-…, test_runner_tool(), CompilerInput, _do_compile() (+7 more)

### Community 120 - "compile_rules.py"
Cohesion: 0.32
Nodes (12): compile_rule(), format_py_literal(), format_sql_literal(), main(), render_markdown(), _is_number(), load_rules(), load_schema() (+4 more)

### Community 121 - "su"
Cohesion: 0.11
Nodes (26): cm(), D2(), eg(), Ei(), eT(), EV(), gE(), Hf() (+18 more)

### Community 122 - "test_integration.py"
Cohesion: 0.26
Nodes (15): run_test_runner(), TestRunnerInput, Integration tests: chain Profiler -> Validator -> Compiler -> Test Runner…, Even if a caller bypasses Validator/Compiler and hand-builds a CompiledRule…, test_failure_path_bad_operator_never_reaches_test_runner(), test_failure_path_hand_crafted_bad_check_caught_at_execution(), test_happy_path_full_chain_detects_known_violations(), _write_schema() (+7 more)

### Community 123 - "FastAPI"
Cohesion: 0.06
Nodes (41): BaseHTTPMiddleware, FastAPI, Response, check_user_role(), is_public_path(), Enum, Request, str (+33 more)

### Community 124 - "er"
Cohesion: 0.22
Nodes (9): b5(), er(), Fb(), gT(), i7(), ix, U_(), v5 (+1 more)

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

### Community 131 - "Kt"
Cohesion: 0.17
Nodes (16): add(), ef(), gf(), hl(), If(), jf(), jl(), kf() (+8 more)

### Community 132 - "Validator"
Cohesion: 0.43
Nodes (4): Any, RuleSpec, Validator performs deterministic structural, semantic, and type-compatibility…, Validator

### Community 133 - "tool"
Cohesion: 0.27
Nodes (9): AST, calculate(), _eval_node(), Tìm kiếm thông tin trong knowledge base. Args: query: Câu hỏi cần tìm kiếm…, # TODO: Implement actual search logic (e.g., RAG with vector store), Tính toán biểu thức toán học an toàn (không dùng eval). Hỗ trợ: +, -, *, /, //,…, Recursively evaluate AST node using safe operators only., search_knowledge() (+1 more)

### Community 134 - "run-manifest.schema.json"
Cohesion: 0.20
Nodes (9): dataset_key, run_id, started_at, description, status, required, $schema, title (+1 more)

### Community 135 - "rulespec.schema.json"
Cohesion: 0.20
Nodes (9): rule_expression, rule_id, rule_type, description, status, required, $schema, title (+1 more)

### Community 136 - "profile_source_db.py"
Cohesion: 0.42
Nodes (9): get_declared_types(), get_pk_columns(), get_tables(), log_table_summary(), main(), profile_table(), Connection, render_markdown() (+1 more)

### Community 137 - "ky"
Cohesion: 0.38
Nodes (7): f1(), fu, ky(), m1(), pP(), ug(), zy()

### Community 138 - "AppShell.tsx"
Cohesion: 0.44
Nodes (6): AppShell(), ROLE_OPTIONS, TopBar(), AppState, useAppStore, UserRole

### Community 139 - "fetch_real_public_datasets.py"
Cohesion: 0.22
Nodes (8): fetch_real_ride_hailing(), fetch_real_st_evcdp(), fetch_real_uit_vsfc(), fetch_real_vehicle_telemetry(), Fetches real ST-EVCDP charging station dataset from GitHub public repository., Fetches real Ride Hailing Transaction Dataset., Fetches real UIT-VSFC Vietnamese Sentiment/Aspect dataset from HuggingFace /…, Fetches real Vehicle Energy & Telemetry (JAC IEV40 CAN-bus time series).

### Community 142 - "enum"
Cohesion: 0.29
Nodes (7): drop, flag, impute_deterministic, quarantine, enum, type, action

### Community 143 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 144 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 145 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 146 - "$schema"
Cohesion: 0.29
Nodes (6): rules, $schema, columns, dataset_name, domain, version

### Community 147 - "submit_log.py"
Cohesion: 0.43
Nodes (6): _archive(), main(), Path, Append pending file to today's archive. Never overwrites existing data., Failure path: put pending back at LOG_FILE so the next push retries. If hook…, _restore_pending()

### Community 148 - "ConnectionManager"
Cohesion: 0.38
Nodes (3): ConnectionManager, Any, WebSocket

### Community 149 - "enum"
Cohesion: 0.33
Nodes (6): error, info, warning, severity, enum, type

### Community 151 - "devDependencies"
Cohesion: 0.50
Nodes (3): devDependencies, puppeteer, puppeteer

### Community 152 - "build"
Cohesion: 0.67
Nodes (3): build(), main(), Path

## Knowledge Gaps
- **388 isolated node(s):** `_pyrun.sh script`, `setup.sh script`, `setup_hooks.sh script`, `name`, `private` (+383 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `c()` connect `c` to `index-BaGgQfLv.js`, `n`, `ky`, `index-to5fYhfR.js`, `i`, `i`, `i`, `Be`, `i`, `o`, `i`, `$E`, `i`, `t`, `r`, `n`, `i`, `nc`, `hT`, `n`, `hu`, `Ad`, `gu`, `gu`, `n`, `Fn`, `gu`, `Z`, `n`, `gu`, `uS`, `vc`, `vc`, `su`, `er`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `Rn()` connect `fn` to `c`, `wd`, `index-BRVdCVNO.js`, `wd`, `wd`, `wd`, `wd`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `W` connect `c` to `index-BaGgQfLv.js`, `n`, `su`, `dl`, `uS`, `dl`, `dl`, `ky`, `hT`, `Z`, `Ad`, `Be`, `dl`, `Z`, `er`, `$E`, `o`, `dl`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 127 inferred relationships involving `o()` (e.g. with `index-BaGgQfLv.js` and `$5()`) actually correct?**
  _`o()` has 127 INFERRED edges - model-reasoned connections that need verification._
- **Are the 111 inferred relationships involving `n()` (e.g. with `index-BaGgQfLv.js` and `a4`) actually correct?**
  _`n()` has 111 INFERRED edges - model-reasoned connections that need verification._
- **Are the 126 inferred relationships involving `r()` (e.g. with `index-BaGgQfLv.js` and `a4`) actually correct?**
  _`r()` has 126 INFERRED edges - model-reasoned connections that need verification._
- **Are the 138 inferred relationships involving `c()` (e.g. with `b()` and `ep()`) actually correct?**
  _`c()` has 138 INFERRED edges - model-reasoned connections that need verification._