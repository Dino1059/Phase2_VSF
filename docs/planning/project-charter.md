# Project Charter — DataTrust OS

> **Problem Code:** DATA-02 — "AI Agent xây dựng & kiểm tra Data Quality và phát hiện bất thường"  
> **Repository:** P-086 — DataTrust OS  
> **Target Wedge:** Data Source Onboarding & Contract Creation Wedge  
> **Team:** DataTrust OS Engineering & QA Evaluation Team  

---

## 1. Executive Summary

DataTrust OS is an AI-native data quality and contract creation system built to transform relational data source onboarding from days of manual SQL scripting into a bounded, deterministic, human-in-the-loop (HITL) workflow.

Existing data quality tools require manual test writing in dbt or Great Expectations, while traditional chat LLMs produce non-deterministic code with high hallucination risk. DataTrust OS bridges this gap through:
- **Probabilistic Rule Proposals:** LLMs analyze deterministic profiling metadata (never raw rows) to suggest semantic and data quality rules.
- **Deterministic Compilation & Execution:** Rules are validated and compiled into strictly whitelisted pandas/SQL transformation plans.
- **Fail-Closed Isolation:** Invalid or out-of-range records are routed to an isolated Quarantine table with clear lineage rather than being silently dropped.
- **Human-in-the-Loop Governance:** Every transformation proposal requires human review before production compilation.

---

## 2. Business Rationale & Pain Point

Data teams onboarding new relational sources spend **60% to 80% of their bandwidth** on manual schema profiling, mapping, rule definition, exception handling, and documentation.

### Core Problems Solved:
1. **Rule Explosion:** Mid-size ride-hailing datasets (such as NYC TLC FHVHV trip data with ~20M rows) require dozens of cross-field and range rules that are error-prone to write by hand.
2. **Semantic Rule Deficit:** Traditional profilers detect basic nulls and types but fail to propose domain rules (e.g., `PULocationID == DOLocationID` implies `trip_miles == 0`).
3. **Trust & Audit Gap:** Unverified AI outputs cannot be executed directly on production data without immutable execution manifests and audit records.

---

## 3. Team Structure & Roles

| Role | Responsibilities |
|---|---|
| **Product & Evaluation Lead** | Evaluation harness, error injector, Agentic Gate benchmarks, metrics reporting |
| **Schema & Agent Engineer** | ReAct engine, structured LLM adapters, context builder, repair loop |
| **Pipeline & Tools Engineer** | Deterministic profiler, validator, compiler, transform library, executor |
| **UX & Deployment Engineer** | FastAPI REST API, state machine, audit store, reset functionality |

---

## 4. MVP Scope & Boundaries

### In Scope for MVP:
- Single relational data source ingestion (Parquet/CSV)
- SHA-256 raw snapshot checksumming
- Deterministic profiling & correlation analysis
- Provider-agnostic structured LLM rule proposal
- Bounded ReAct engine with whitelisted tool invocation
- Maximum 3 repair retries for failing rules
- CleanDB + Quarantine table outputs
- Quantitative benchmark comparing C0 vs C1 vs A1 baselines
- Agentic Gate decision engine

### Explicit Non-Goals:
- Multi-source production DAG scheduling (Airflow/Dagster)
- Distributed cluster execution (Spark/Flink)
- Direct LLM mutation of raw data or arbitrary Python/SQL execution
- Autonomous unmonitored AI decision-making without HITL signoff

---

## 5. Key Deliverables & Milestones

- **Sprint 1:** Data Card, immutable snapshot connector, deterministic profiler
- **Sprint 2:** Whitelisted compiler, executor, quarantine engine, state machine API
- **Sprint 3:** ReAct agent engine, bounded repair loop, LLM adapter
- **Sprint 4:** Synthetic error injector, evaluation benchmark harness, Agentic Gate verification
- **Sprint 5:** Clean test suite execution, final documentation pack
