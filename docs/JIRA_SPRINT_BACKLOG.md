# 🎯 DataTrust OS v3.0 — Master Jira Organization & Sprint Backlog

> **Project Key:** `DATA`  
> **Project Lead:** DataTrust OS Core Team  
> **Framework:** Agile Scrum (2-Week Sprints)  
> **Last Updated:** 2026-08-03  

---

## 🏃 1. Sprint Architecture & Timeline

| Sprint Name | Status | Start Date | End Date | Sprint Goal |
|---|---|---|---|---|
| **Sprint 1: Core Multi-Agent Engine & Data Ingestion** | `ACTIVE` | 03 Aug 2026 | 17 Aug 2026 | Deliver 4 VinGroup datasets, ReAct Multi-Agent loop with Gemma-4 26B, and Vietnamese NLP Aspect Extractor. |
| **Sprint 2: HITL Workflow & Executive Dashboard** | `PLANNED` | 17 Aug 2026 | 31 Aug 2026 | Build full Executive Dashboard, daily log date filters (`3d`, `7d`), 125/125 pytest suite, and production deployment. |

---

## 📌 2. Epic Breakdown

1. `DATA-EPIC-1`: **Vietnamese NLP & Aspect Extraction Engine** (Lead: Dũng)
2. `DATA-EPIC-2`: **Multi-Agent ReAct Engine & HITL Governance** (Lead: Quốc Thanh)
3. `DATA-EPIC-3`: **Real Data Ingestion & Fault Injection Pipeline** (Lead: Tạ Kim Ngân)
4. `DATA-EPIC-4`: **Frontend UI/UX & Executive Dashboard** (Lead: Huyền Vũ)

---

## 📋 3. Detailed Jira Issue Backlog & Task Specifications

### 🏷️ EPIC 1: Vietnamese NLP & Aspect Extraction (`DATA-EPIC-1`)

#### 🔹 `DATA-101`: Implement Vietnamese NLP Aspect Extractor & Teen-code Normalizer
- **Issue Type:** `Story`
- **Assignee:** `Dũng`
- **Component:** `NLP Engine`
- **Story Points:** `5`
- **Priority:** `High`
- **Description:**
  Build a specialized Vietnamese NLP processing module (`src/services/vietnamese_nlp.py`) to parse unstructured customer feedback from the Xanh SM app (`xanh_sm_customer_feedback_dirty`). The engine must normalize teen-code slang (e.g. `"ko sac dc"` ➔ `"không sạc được"`), extract aspect entities (Location, Component, Error Type, Severity), and cross-validate customer complaints against V-GREEN charging station hardware logs.
- **Acceptance Criteria:**
  - [x] Teen-code dictionary normalizes 50+ common Vietnamese slang patterns (`"ko"`, `"dc"`, `"tram sac"`, `"app lag"`, `"vl"`).
  - [x] Aspect Extractor correctly parses Location (`Vincom Bà Triệu`), Component (`Trạm sạc V-GREEN`), and Error Severity (`CRITICAL`).
  - [x] Telemetry Cross-Validation correlates feedback text with charger hardware log temperature (`85.5°C THERMAL_FAULT`).
  - [x] Pytest suite passes: `tests/test_vingroup.py::test_vietnamese_nlp_aspect_extraction_and_cross_validation`.

---

### 🏷️ EPIC 2: Multi-Agent ReAct Engine & HITL Governance (`DATA-EPIC-2`)

#### 🔹 `DATA-102`: Build Multi-Agent ReAct Bounded Loop with Gemma-4 Function Calling
- **Issue Type:** `Story`
- **Assignee:** `Quốc Thanh`
- **Component:** `Agentic Orchestrator`
- **Story Points:** `8`
- **Priority:** `Highest`
- **Description:**
  Implement the 6-agent ReAct orchestration architecture in `src/api/routes.py` using single model `gemma-4-26b-a4b-it` via Google AI Studio API. Agents include Orchestrator, Profiler, Anomaly Detector, Diagnosis, Rule Proposer, and Executor.
- **Acceptance Criteria:**
  - [x] Single model configuration with 60s max timeout and 3 exponential backoff retries.
  - [x] Native `GOVERNANCE_TOOLS` function calling schema.
  - [x] HITL approval gate: `RuleProposalCard` with `Approve`, `Reject`, `Edit` actions.

---

### 🏷️ EPIC 3: Real Data Ingestion & Fault Injection (`DATA-EPIC-3`)

#### 🔹 `DATA-103`: Open-Source Data Fetcher & VinGroup Domain Schema Mapper
- **Issue Type:** `Story`
- **Assignee:** `Tạ Kim Ngân`
- **Component:** `Data Pipeline`
- **Story Points:** `5`
- **Priority:** `High`
- **Description:**
  Create automated data fetchers (`scripts/fetch_real_public_datasets.py`) for open-source datasets (ST-EVCDP, UIT-VSFC, JAC IEV40 Telemetry, Ride Hailing) and map them to VinGroup enterprise schemas in `data/vingroup_real/`.
- **Acceptance Criteria:**
  - [x] 4 datasets fetched and mapped into enterprise schemas.
  - [x] Ground-truth `vingroup_fault_manifest.json` generated containing 123 faults across 9 Vietnam real-world fault families.

---

### 🏷️ EPIC 4: Frontend UI/UX & Executive Dashboard (`DATA-EPIC-4`)

#### 🔹 `DATA-104`: Executive Dashboard & In-Stream Daily Operation Date Filters
- **Issue Type:** `Story`
- **Assignee:** `Huyền Vũ`
- **Component:** `Frontend v3`
- **Story Points:** `5`
- **Priority:** `High`
- **Description:**
  Develop the React 19 + Vite + Tailwind CSS frontend dashboard (`frontend-v3`). Include Executive Dashboard with KPI banners, 24-hour error trend visualizer, and in-stream date filters (`[Hôm Nay]`, `[3d]`, `[7d]`, `[Tuần]`, `[Tháng]`) for dedicated 1-DB-per-chat sessions. Render a simplified Vietnamese workflow description board for mentor review.
- **Acceptance Criteria:**
  - [x] Executive Dashboard shows KPI banners, 24h trend visualizer, and audit manifest.
  - [x] Dedicated 1-DB chat sessions feature an in-stream date filter bar for quick 3-day history lookups.
  - [x] Excalidraw wireframes (`docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.svg`) updated and synced.
