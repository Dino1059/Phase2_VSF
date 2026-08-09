# 🎯 DataTrust OS v3.0 — Master 5-Sprint Schedule with Hard Due Dates

> **Project Key:** `SCRUM` (`ShayNeeo's Cơm tấm Sài Gòn`)  
> **Final Submission Hard Gate:** `24 August 2026` (Completed before 25th August)  
> **Sprint Structure:** 5 Accelerated 4-Day Sprints (Sprint 0 Done, Sprint 1 Currently Running)  
> **Last Updated:** 2026-08-03  

---

## 🏃 1. Master 5-Sprint Roadmap (4 Days Each with Jira Due Dates)

| Sprint | Dates | Hard Due Date (`duedate`) | Lead Owner | Focus & Deliverables | Status | Control Issue |
|---|---|---|---|---|---|---|
| **Sprint 0** | **29 Jul – 02 Aug** | **2026-08-02** | **Phạm Quốc Thanh** | Project Charter, MVP Scope & Architecture (`ARCHITECTURE.md`). | `DONE` | [`SCRUM-6`](https://shayneeo.atlassian.net/browse/SCRUM-6) |
| **Sprint 1** | **03 Aug – 07 Aug** | **2026-08-07** | **Tạ Kim Ngân** | Real Data Ingestion (ST-EVCDP, UIT-VSFC, JAC IEV40, Ride Hailing), Schema Mapper & 9-Fault Injection. | `CURRENTLY RUNNING` | [`SCRUM-20`](https://shayneeo.atlassian.net/browse/SCRUM-20) |
| **Sprint 2** | **07 Aug – 11 Aug** | **2026-08-11** | **Trần Tiến Dũng** | Vietnamese NLP Aspect Extractor (`src/services/vietnamese_nlp.py`), Teen-code Normalizer (`ko sac dc` ➔ `không sạc được`) & V-GREEN Hardware Log Matcher. | `PLANNED` | [`SCRUM-22`](https://shayneeo.atlassian.net/browse/SCRUM-22) |
| **Sprint 3** | **11 Aug – 15 Aug** | **2026-08-15** | **Phạm Quốc Thanh** | Bounded Multi-Agent ReAct Engine (`Orchestrator`, `Profiler`, `Anomaly`, `Diagnosis`, `Rule Proposer`, `Executor`) with Gemma-4-26B & HITL Gate. | `PLANNED` | [`SCRUM-23`](https://shayneeo.atlassian.net/browse/SCRUM-23) |
| **Sprint 4** | **15 Aug – 19 Aug** | **2026-08-19** | **Vũ Thu Huyền** | Executive Dashboard, In-Stream Date Filters (`3d`, `7d`, `Tuần`, `Tháng`), Vietnamese Mentor Board & Feature Lock. | `PLANNED` | [`SCRUM-24`](https://shayneeo.atlassian.net/browse/SCRUM-24) |
| **Sprint 5** | **19 Aug – 23 Aug** | **2026-08-23** | **All Team Leads** | Final Benchmark Verification (125/125 Pytest Pass Gate), Clean DB SHA-256 Lineage Hash Audit & Demo Presentation Rehearsal. | `PLANNED` | [`SCRUM-25`](https://shayneeo.atlassian.net/browse/SCRUM-25) |
| **MILESTONE**| **24 Aug 2026** | **2026-08-24** | **Core Team** | **FINAL PROJECT SUBMISSION & HARD LOCK (DONE BEFORE AUGUST 25TH)** | `TARGET` | — |

---

## 📋 2. Live Jira Issue Backlog & Explicit Due Dates

| Jira Key | Issue Summary | Assignee | Sprint | Due Date (`duedate`) | Status | Priority |
|---|---|---|---|---|---|---|
| **[`SCRUM-31`](https://shayneeo.atlassian.net/browse/SCRUM-31)** | [P0] Open-Source Real Dataset Ingestion & VinGroup Schema Mapper | Tạ Kim Ngân | **Sprint 1** | **`2026-08-07`** | `In Progress` | `High` |
| **[`SCRUM-9`](https://shayneeo.atlassian.net/browse/SCRUM-9)** | [P0] Target Schema & Data Onboarding Pack | Tạ Kim Ngân | **Sprint 1** | **`2026-08-07`** | `In Progress` | `High` |
| **[`SCRUM-10`](https://shayneeo.atlassian.net/browse/SCRUM-10)** | [P0] Ingestion & Preprocessing Pipeline for 4 VinGroup DBs | Trần Tiến Dũng | **Sprint 1** | **`2026-08-07`** | `In Progress` | `High` |
| **[`SCRUM-29`](https://shayneeo.atlassian.net/browse/SCRUM-29)** | [P0] Vietnamese NLP Aspect Extractor & Teen-code Normalizer | Trần Tiến Dũng | **Sprint 2** | **`2026-08-11`** | `To Do` | `High` |
| **[`SCRUM-12`](https://shayneeo.atlassian.net/browse/SCRUM-12)** | [P0] Tool Layer: Profiler, Validator, Compiler, Test Runner | Trần Tiến Dũng | **Sprint 2** | **`2026-08-11`** | `To Do` | `High` |
| **[`SCRUM-14`](https://shayneeo.atlassian.net/browse/SCRUM-14)** | [P0] Error Injector & Ground-Truth Labels | Phạm Quốc Thanh | **Sprint 2** | **`2026-08-11`** | `To Do` | `High` |
| **[`SCRUM-30`](https://shayneeo.atlassian.net/browse/SCRUM-30)** | [P0] Multi-Agent ReAct Engine & HITL Permission Gate | Phạm Quốc Thanh | **Sprint 3** | **`2026-08-15`** | `To Do` | `Highest` |
| **[`SCRUM-11`](https://shayneeo.atlassian.net/browse/SCRUM-11)** | [P0] Baseline C0/C1 & Agentic A1 Prototype | Tạ Kim Ngân | **Sprint 3** | **`2026-08-15`** | `To Do` | `High` |
| **[`SCRUM-13`](https://shayneeo.atlassian.net/browse/SCRUM-13)** | [P0] HITL Review Queue & Audit Trail | Vũ Thu Huyền | **Sprint 3** | **`2026-08-15`** | `To Do` | `High` |
| **[`SCRUM-16`](https://shayneeo.atlassian.net/browse/SCRUM-16)** | [P0] Vertical Slice End-to-End Integration | Vũ Thu Huyền | **Sprint 3** | **`2026-08-15`** | `To Do` | `High` |
| **[`SCRUM-32`](https://shayneeo.atlassian.net/browse/SCRUM-32)** | [P0] Executive Dashboard & In-Stream Daily Operation Date Filters | Vũ Thu Huyền | **Sprint 4** | **`2026-08-19`** | `To Do` | `High` |
| **[`SCRUM-21`](https://shayneeo.atlassian.net/browse/SCRUM-21)** | [P0] UX Discovery & Wireframe Review Flow | Vũ Thu Huyền | **Sprint 4** | **`2026-08-19`** | `To Do` | `High` |
| **[`SCRUM-18`](https://shayneeo.atlassian.net/browse/SCRUM-18)** | [P0] Deployment, Observability & Backup Recovery | Vũ Thu Huyền | **Sprint 4** | **`2026-08-19`** | `To Do` | `High` |
| **[`SCRUM-17`](https://shayneeo.atlassian.net/browse/SCRUM-17)** | [P0] Agentic Necessity Evaluation C0 vs C1 vs A1 | Phạm Quốc Thanh | **Sprint 5** | **`2026-08-23`** | `To Do` | `Highest` |
| **[`SCRUM-15`](https://shayneeo.atlassian.net/browse/SCRUM-15)** | [P1] Anomaly Baseline & Evaluation Harness | Tạ Kim Ngân | **Sprint 5** | **`2026-08-23`** | `To Do` | `Medium` |
| **[`SCRUM-19`](https://shayneeo.atlassian.net/browse/SCRUM-19)** | [Recurring] Mentor Review & Final Report | Phạm Quốc Thanh | **Sprint 5** | **`2026-08-23`** | `To Do` | `High` |
