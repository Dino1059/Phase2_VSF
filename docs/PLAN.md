# DataTrust OS — v2 Project Plan

> **Status:** Confirmed v2 Execution Plan  
> **Version:** v2.0  
> **Delivery window:** 2026-07-30 → 2026-09-03  
> **Problem bank code:** DATA-02 — "AI Agent xây dựng & kiểm tra Data Quality và phát hiện bất thường"  
> **Team:** Thanh (product/eval), Ngân (schema/agent), Dũng (pipeline/tools), Huyền (UX/deploy)

---

## 1. Why DATA-02?

### 1.1 Alignment with Problem Bank

DATA-02 asks for an AI agent that:
- Surveys a dataset → proposes quality rules (uniqueness, not-null, range, format, freshness)
- Auto-generates tests → runs on schedule → detects anomalies
- Sends alerts with root-cause diagnosis
- HITL: data steward approves rules before production
- Governance: read-only metadata, no sensitive data exposure

**DataTrust OS v2 Integration:**  
DataTrust OS v2 addresses both onboarding/contract creation AND scheduled continuous monitoring. It combines multi-source abstraction (`DataSource` supporting CSV, Parquet, JSON, JSONL), specialized sub-agents (`ProfilerAgent`, `RuleProposerAgent`, `AnomalyDetectorAgent`, `DiagnosisAgent`), `APScheduler` scheduled monitoring, `AlertService` with root-cause diagnosis and webhooks, `RoleMiddleware` RBAC (`Admin`, `Steward`, `Viewer`), and an expanded quantitative evaluation benchmark harness.

### 1.2 DATA-02 Scope vs DataTrust OS v2 Implementation

| DATA-02 Feature | DataTrust OS v2 Implementation | Status |
|---|---|---|
| Multi-source Ingestion | Polymorphic `DataSource` hierarchy (`StructuredSource` for CSV, Parquet, JSON, JSONL; stubs for PDF, Log, Image) | ✅ Delivered |
| Sub-Agent Decomposition | 4 specialized sub-agents: `ProfilerAgent`, `RuleProposerAgent`, `AnomalyDetectorAgent`, `DiagnosisAgent` | ✅ Delivered |
| Scheduled Monitoring | `SchedulerService` wrapping `APScheduler` for interval and cron scheduled checks | ✅ Delivered |
| Anomaly Detection & Alerts | Tri-detector suite (`ZScoreDetector`, `IQRDetector`, `IsolationForestDetector`) + `AlertService` with webhooks | ✅ Delivered |
| Access Control & Roles | `RoleMiddleware` enforcing `Admin`, `Steward`, and `Viewer` permissions | ✅ Delivered |
| Quantitative Benchmark | Expanded `eval/benchmark.py` testing Anomaly Precision/Recall, Root-Cause Accuracy, SLA Compliance, Human Minutes Saved | ✅ Delivered |

### 1.3 Adjacent topics absorbed in v2

| Topic | What we borrow | What we don't |
|---|---|---|
| DATA-07 (Data Contract) | Rule → contract proposal, schema validation | Producer-consumer negotiation, versioning across teams |
| DATA-12 (Data Cleaning) | Deterministic transform + audit log, HITL preview | Fuzzy matching Vietnamese entities, master dictionary |
| DATA-13 (Data Profiling) | Automated schema + aggregate profiling, sampling | NL Q&A about data characteristics |

---

## 2. Pain-Point Hypothesis — What We Believe Today

### 2.1 Core hypothesis

> Data teams onboarding a new relational source spend **60–80% of their time** on manual profiling, schema mapping, rule writing, testing, exception handling, and documentation — not on the actual business analysis the data was meant to enable.

### 2.2 Supporting observations (unvalidated)

1. **Rule explosion:** A mid-size ride-hailing dataset (like the FHVHV trip data we have — 537MB, ~20M rows) requires 50–200 quality rules. Writing them by hand in dbt/GE takes days.
2. **Context gap:** Deterministic profilers find nulls and type issues but miss *semantic* rules (e.g., "trip_miles should be 0 when PULocationID == DOLocationID" or "tips should be 0 for non-credit-card payments").
3. **Trust gap:** LLMs can *propose* semantic rules, but data engineers don't trust unverified AI output on production data.
4. **Audit gap:** Manual cleanup in spreadsheets/notebooks leaves no traceable lineage.
5. **Approval bottleneck:** Business owners must sign off on transformations but have no easy way to see *what* the system proposes and *why*.

### 2.3 What we DON'T know yet (→ Deep Research questions)

> [!IMPORTANT]
> These are the questions that must be answered before we can claim product-market fit. Use Gemini Deep Research to draft structured interview guides and market landscape analysis.

1. **Who actually does this work?** Is it the data engineer, analytics engineer, or analyst? Or a "data steward" role? What's their title at a Vietnamese SME?
2. **What's the current baseline?** How many hours does a real onboarding take today? What tools (dbt, GE, pandas profiling, manual SQL) do they use?
3. **What's the cost of a bad transformation?** Revenue impact? Trust erosion? Rework cycles?
4. **Would they pay?** What's the willingness-to-pay for a tool that cuts onboarding from 3 days to 3 hours?
5. **Is the Vingroup ride-hailing scenario realistic?** DATA-02 references "Dịch vụ gọi xe X" — is this Xanh SM? Be.? FastGo? The pain is real but the persona may differ.

---

## 3. Business Direction

### 3.1 Product concept

**DataTrust OS** = deterministic profiling + LLM-assisted semantic interpretation + bounded orchestration + HITL + auditability + quantitative evaluation.

**Not a chatbot. A guided workflow.**

### 3.2 Market wedge

```
Phase 1 (MVP — this project):
  One relational source → profile → contract/rule proposal → HITL → execute → clean + audit

Phase 2 (post-program validation):
  Paid pilot with 2–3 SME data teams
  Scheduled re-runs on the same source
  Basic drift detection

Phase 3 (expansion — only after validation):
  Multi-source
  Reusable domain rule packs
  dbt/GE integration
  Observability + governance dashboard
```

### 3.3 ICP (Ideal Customer Profile) — hypothesis

- Small/mid-market company in Vietnam (5–50 employees in data/BI)
- Uses PostgreSQL, MySQL, BigQuery, or recurring CSV-to-database workflows
- Repeated manual cleanup and mapping
- Needs auditability but can't afford Atlan/Collibra/Monte Carlo

### 3.4 Competitive landscape — questions for Deep Research

| Category | Players | Our angle |
|---|---|---|
| Data Quality tools | Great Expectations, Soda, dbt tests | Config-heavy; no AI-assisted rule proposal |
| Data Observability | Monte Carlo, Anomalo, Bigeye | Enterprise-priced; monitoring-first (not onboarding) |
| AI Data Prep | Trifacta/Alteryx | Legacy UI, not agent-based, expensive |
| LLM data tools | Open-source experiments | No HITL, no bounded execution, no audit |

> [!NOTE]
> Deep Research should validate: "What tools do Vietnamese data teams under 50 people actually use for data quality? Is it mostly manual SQL + notebooks?"

---

## 4. Dataset Strategy

### 4.1 Primary dataset: NYC FHVHV Trip Data

We already have [fhvhv_tripdata_2026-05.parquet](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/problem/data/fhvhv_tripdata_2026-05.parquet) (537MB) + [taxi_zone_lookup.csv](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/problem/data/taxi_zone_lookup.csv).

**Why this dataset works for DATA-02:**
- Realistic ride-hailing data — directly maps to DATA-02's "Dịch vụ gọi xe X" scenario
- Rich error surface: nulls, outliers, cross-field inconsistencies, date/time issues
- Public data — no PII concerns
- Large enough to test performance (20M+ rows)
- Has known quality issues documented by NYC TLC

**Expected error families:**
1. **Null/missing:** driver_pay, tips, congestion_surcharge fields
2. **Duplicates:** potential duplicate trip records
3. **Format/type:** date parsing edge cases, zone ID as string vs int
4. **Outliers/range:** trip_miles = 999, trip_time = 0 but distance > 0
5. **Cross-field:** tips > 0 for cash payments, pickup == dropoff but miles > 0
6. **Schema drift:** column name changes across months (known TLC issue)

### 4.2 Data Card deliverable (Sprint 1 — due 5 Aug)

Must include: source, license, columns, types, row count, known quality issues, checksum, sampling strategy.

### 4.3 Integrated Benchmark Datasets (5 Layers, ~24M rows, ~530MB)

| Layer | Dataset | Source | Rows | Size | Status | Description |
|---|---|---|---|---|---|---|
| **L1** | NYC FHVHV | NYC TLC Jan 2024 | 19,663,930 | 451 MB | ✅ | High-volume ride-hailing baseline (Uber/Lyft) |
| **L2** | Grab SEA | Kaggle (AI for SEA 2019) | 4,206,321 | ~61 MB | ✅ | Regional Southeast Asia demand & geohash spatial mobility |
| **L3** | Weather Context | Open-Meteo API (HCMC 2024) | 8,784 | 0.1 MB | ✅ | Hourly weather parameters for cross-domain context |
| **L4** | Synthetic Vietnam | Generator (seed=42) | 50,000 | 8.3 MB | ✅ | Clean Vietnam ride-hailing with VND, rush-hour distribution |
| **L5** | Fault Manifest | Fault Injector (seed=42) | 50,000 | 8.4 MB | ✅ | Ground-truth dataset with 9 injected fault types (14,450 errors) |

---

## 5. Architecture Summary

> Full architecture details → [ARCHITECTURE.md](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/problem/ARCHITECTURE.md)

### 5.1 Core flow

```
Connect/upload single relational source
  → Immutable raw snapshot (checksum)
  → Profile schema + aggregates (deterministic)
  → Source-to-target mapping (LLM proposes, human reviews)
  → Rule/transform proposal with evidence + confidence (LLM proposes)
  → Human approve/edit/reject (HITL queue)
  → Deterministic validation + compilation
  → Deterministic execution
  → CleanDB + Quarantine + Manifest + Audit
```

### 5.2 Three baselines

| Variant | What | Ship? |
|---|---|---|
| C0 | One-shot chatbot — dump data, get rules | Baseline only |
| C1 | Fixed profiler → LLM → validator pipeline | Ship if A1 fails gate |
| A1 | Bounded tool-using agent with observation, repair, abstention, handoff | Ship only if passes gate |

### 5.3 Agentic gate (quantitative)

Keep A1 only if:
- Semantic-rule recall ≥ C1 + 10pp **OR** correction time ≤ C1 × 0.75
- Precision ≥ 80%
- Cost ≤ 2× C1

Otherwise ship C1 and remove "agentic" claim.

---

## 6. Deep Research Plan — Questions for Gemini

### 6.1 File: `DEEP_RESEARCH_painpoint_validation.md`

**Objective:** Validate that the DATA-02 pain point is real and our wedge is correctly scoped.

**Research prompts to send to Gemini Deep Research:**

1. **Market pain:**
   > "Research the current state of data quality management in small-to-mid-size data teams (5–50 people). What percentage of data engineering time is spent on data quality tasks vs. building new pipelines? What are the most common data quality tools used by teams under 50 people, especially in Southeast Asia?"

2. **Competitive landscape:**
   > "Compare the approaches of Great Expectations, Soda Core, dbt tests, Monte Carlo, Anomalo, and Bigeye for data quality. What gaps exist for AI-assisted rule generation? Are there any startups combining LLM + deterministic execution for data quality?"

3. **Willingness to pay:**
   > "What do small/mid-market companies pay for data quality tools? What's the typical ROI calculation? How do they justify the investment to leadership?"

4. **Vietnamese market:**
   > "What data infrastructure tools and practices are common in Vietnamese tech companies (ride-hailing, e-commerce, fintech)? Do they use dbt, Airflow, Great Expectations? What's the typical data team structure?"

### 6.2 File: `DEEP_RESEARCH_technical_decisions.md`

**Objective:** Inform architecture decisions before Sprint 2.

**Research prompts:**

1. **Structured output patterns:**
   > "What are the best practices for using LLMs to generate structured data quality rules? Compare function calling vs. JSON mode vs. constrained generation. What's the failure rate and how do teams handle it?"

2. **Agent vs. pipeline:**
   > "Compare bounded tool-using agents (LangGraph, AutoGen) vs. fixed LLM pipelines for data quality tasks. What evidence exists that agentic approaches produce better results? What are the cost/latency tradeoffs?"

3. **Evaluation methods:**
   > "How do data quality tool vendors evaluate their AI-assisted features? What benchmarks exist for data quality rule generation? How is precision/recall measured when ground truth is partially known?"

### 6.3 File: `MENTOR_QUESTIONS.md`

**Objective:** Structured questions for the mentor sessions (Wed/Sat).

---

## 7. Mentor Communication Plan

### 7.1 Questions for mentor — priority ordered

#### Batch 1: Scope & direction (Sat 2 Aug or Wed 5 Aug)

1. **Pain-point validation depth:** How many interviews/walkthroughs do you expect before the first demo? Is synthetic-only evaluation acceptable for the MVP, or must we show at least one real user?

2. **Dataset choice:** We plan to use NYC FHVHV trip data (public, ride-hailing, 20M+ rows). Is this acceptable as a proxy for "Dịch vụ gọi xe X" or should we find Vietnamese data?

3. **Scope boundary:** DATA-02 includes scheduled monitoring + anomaly ML. We've scoped down to one-shot onboarding + optional anomaly. Is this too narrow or is the wedge correct?

4. **Agentic claim:** The gate (A1 must beat C1 by ≥10pp recall or ≥25% time reduction) is from our internal design. Do you agree with these thresholds?

5. **Demo audience:** Who will see the final demo? Technical mentors only, or also business stakeholders? This affects whether we need a business pitch or just a technical walkthrough.

#### Batch 2: Technical (Wed 5 Aug)

6. **LLM provider:** We plan provider-agnostic adapter (Gemini/GPT-4o/Claude). Any preference for the demo?

7. **Database:** DuckDB for MVP (no infra overhead) vs. PostgreSQL (closer to production reality)?

8. **UI depth:** Guided workflow in React vs. Streamlit prototype? How polished must the UI be for the demo?

#### Batch 3: Evaluation (Sat 8 Aug)

9. **Error injection:** We plan 5%/10%/20% error rates at easy/medium/hard difficulty. Is this sufficient?

10. **Ground truth:** Should we hand-label a subset of the FHVHV data or is synthetic injection enough?

11. **Anomaly scope:** Is the anomaly ML stretch goal worth Sprint 4 time, or should we invest in polishing HITL instead?

12. **Business validation depth:** Is a competitor landscape + 3 user interviews sufficient, or do you expect a full business plan with pricing model?

---

## 8. Sprint Plan — Aligned with Handoff Context

### Sprint 1: Foundation (30 Jul – 5 Aug)

| Task | Owner | Deliverable | Due |
|---|---|---|---|
| SCRUM-6 Charter/MVP/non-goals | Thanh | Project charter | 1 Aug |
| SCRUM-7 Scrumban policy | Thanh | Process doc | 1 Aug |
| SCRUM-27 ARCHITECTURE.md | All | Architecture doc (this file + ARCHITECTURE.md) | 1 Aug |
| SCRUM-8 Dataset/Data Card | Thanh | Data card + checksum | 5 Aug |
| SCRUM-9 Schema/Onboarding Pack | Ngân | Target schema + dictionary | 5 Aug |
| SCRUM-21 UX wireframe | Huyền | Figma/wireframe of guided flow | 5 Aug |
| Deep Research kickoff | Thanh | Send research prompts to Gemini | 2 Aug |
| Mentor Q batch 1 | Thanh | MENTOR_QUESTIONS.md prepared | 2 Aug |

### Sprint 2: Deterministic Pipeline (6 – 12 Aug)

| Task | Owner | Deliverable |
|---|---|---|
| SCRUM-10 Pipeline | Dũng | Snapshot → profile → transform pipeline |
| SCRUM-12 Tool layer | Dũng | Validator, compiler, test runner |
| SCRUM-14 Error injector | Thanh | Fixed-seed injector for FHVHV data |
| Deep Research results review | Thanh | Synthesize findings, update pain-point |
| User interview #1–2 | Thanh | Interview notes |

### Sprint 3: Agent + HITL (13 – 19 Aug)

| Task | Owner | Deliverable |
|---|---|---|
| SCRUM-11 C0/C1/A1 | Ngân | Three baseline implementations |
| SCRUM-13 HITL/audit | Huyền | Approve/edit/reject UI + audit trail |
| SCRUM-16 Integration | Huyền | End-to-end flow working |
| User interview #3–4 | Thanh | Interview notes |

### Sprint 4: Hardening (20 – 26 Aug)

| Task | Owner | Deliverable |
|---|---|---|
| SCRUM-17 Agentic benchmark | Thanh | C0 vs C1 vs A1 comparison report |
| SCRUM-15 Anomaly baseline | Ngân | Optional — only if Sprint 3 clean |
| Feature lock | All | 23:59 on 26 Aug |

### Sprint 5: Stabilize & Ship (27 Aug – 3 Sep)

| Task | Owner | Deliverable |
|---|---|---|
| SCRUM-18 Deployment/recovery | Huyền | Docker Compose, reset script |
| SCRUM-19 Mentor evidence | Thanh | Final evaluation report |
| 3 dry runs | All | No critical failures |
| Demo rehearsal | All | Under 15 minutes |

---

## 9. Future Work — Post-Program Roadmap

### 9.1 Immediate post-program (Sep–Oct 2026)

- [ ] Conduct 8–12 user interviews (per validation plan in handoff)
- [ ] Pilot with 2 real data teams on their own datasets
- [ ] Measure baseline time vs. DataTrust OS time
- [ ] Validate willingness-to-pay

### 9.2 Product expansion (if validated)

- [ ] Scheduled re-runs (basic monitoring)
- [ ] Multi-source support (PostgreSQL, MySQL, BigQuery)
- [ ] Drift detection between runs
- [ ] Reusable domain rule packs (ride-hailing, e-commerce, fintech)
- [ ] dbt test / Great Expectations export

### 9.3 Business expansion (if pilot succeeds)

- [ ] Paid pilot program (1 source, 1 schema, fixed duration)
- [ ] Pricing model based on sources × runs × data volume
- [ ] Vietnamese market focus: target Grab VN, MoMo, Tiki, VNPay data teams
- [ ] Partnership with Vietnamese data consultancies

### 9.4 Technical debt to address

- [ ] Replace DuckDB with proper warehouse adapter
- [ ] Add authentication/RBAC
- [ ] Production-grade logging and monitoring
- [ ] Fine-tuning for Vietnamese column names and business context
- [ ] Multi-language support for rule descriptions

---

## 10. Files to Prepare for Mentor & Deep Research

### 10.1 Deliverable files (this plan generates)

| File | Purpose | Status |
|---|---|---|
| `PLAN.md` (this file) | Master project plan | ✅ Created |
| `ARCHITECTURE.md` | Technical architecture | ✅ Created |
| `DEEP_RESEARCH_painpoint_validation.md` | Prompts for Gemini Deep Research — market/pain | To create |
| `DEEP_RESEARCH_technical_decisions.md` | Prompts for Gemini Deep Research — architecture | To create |
| `MENTOR_QUESTIONS.md` | Structured questions for mentor sessions | To create |

### 10.2 Sprint 1 deliverables (due 5 Aug)

| File | Purpose | Owner |
|---|---|---|
| `docs/project-charter.md` | Scope, goals, non-goals, team | Thanh |
| `docs/data-card.md` | Dataset documentation | Thanh |
| `schemas/target-schema.json` | CleanDB target schema | Ngân |
| `docs/onboarding-pack.md` | Source-to-target mapping | Ngân |
| UX wireframe | Guided workflow mockup | Huyền |

---

## 11. Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| 1 | Pain point not validated by real users | High | Medium | Deep Research + 2 interviews before Sprint 3 |
| 2 | Agent adds complexity without measurable value | High | Medium | Build C1 first; quantitative gate |
| 3 | LLM proposes incorrect semantic rules | Medium | High | Precision ≥ 80% gate, HITL, deterministic execution only |
| 4 | 5-week timeline too tight | High | High | Strict cut order, feature lock, no scope creep |
| 5 | Dataset too clean (not enough errors) | Medium | Low | Fixed-seed error injection at 5/10/20% rates |
| 6 | Demo deployment fails | High | Medium | Docker Compose + local fallback + backup video |
| 7 | Vietnamese market assumptions wrong | Medium | Medium | Deep Research on VN data landscape |
| 8 | Team capacity (2–3h/day in Sprint 1) | Medium | Medium | ≤6h work packages, 70% capacity planning |

---

## 12. Decision Log

| # | Date | Decision | Status | Source |
|---|---|---|---|---|
| D1 | 2026-07-30 | MVP = one relational source, no multi-source | Confirmed | Handoff Context §4 |
| D2 | 2026-07-30 | Ship C1 if A1 fails benchmark | Confirmed | Handoff Context §7 |
| D3 | 2026-07-30 | No arbitrary LLM code execution | Confirmed | Handoff Context §9 |
| D4 | 2026-07-30 | Feature lock 26 Aug 23:59 | Confirmed | Handoff Context §13 |
| D5 | 2026-08-01 | Narrow DATA-02 to onboarding wedge | Working hypothesis | This plan |
| D6 | 2026-08-01 | Use FHVHV trip data as primary dataset | Working hypothesis | This plan |
| D7 | 2026-08-01 | Absorb DATA-07/12/13 partially | Working hypothesis | This plan |
| D8 | TBD | LLM provider choice | OPEN — mentor decision | — |
| D9 | TBD | Database (DuckDB vs PostgreSQL) | OPEN — mentor decision | — |
| D10 | TBD | Anomaly ML in/out of scope | OPEN — mentor decision | — |
