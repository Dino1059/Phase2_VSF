# DataTrust OS — Onboarding Pack

Welcome to **DataTrust OS**! This guide will help developer and QA team members set up, run, test, and evaluate the DataTrust OS platform.

---

## 1. Quickstart & Environment Setup

### Prerequisites:
- Python 3.13+
- Linux / macOS / Windows Shell
- `uv` package manager (recommended) or `pip`

### Installation Steps:

```bash
# 1. Clone repository
git clone <repo-url> P-086
cd P-086

# 2. Virtual Environment Setup with uv
uv venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install Dependencies
uv pip install -r requirements.txt
```

---

## 2. Running Test Suites

Run the complete 100% clean unit and integration test suite:

```bash
.venv/bin/pytest tests/ -v
```

### Test Suite Structure:
- `tests/test_tools.py`: Tests deterministic profiler, validator, compiler, transform library, and executor.
- `tests/test_agents.py`: Tests context builder, LLM adapter, ReAct engine, bounded repair loop, and C0/C1/A1 baselines.
- `tests/test_api.py`: Tests FastAPI REST endpoints, state machine transitions, audit store, and reset.
- `tests/test_eval.py`: Tests error injector, quantitative benchmark harness, and Agentic Gate decision logic.

---

## 3. Running Evaluation Harness & Benchmark

To execute the quantitative evaluation benchmark comparing C0 vs C1 vs A1 across Easy (5%), Medium (10%), and Hard (20%) error injection levels:

```bash
.venv/bin/python -m eval.benchmark
```

### Key Metrics Tracked:
1. **Precision:** Accuracy of detected data quality errors (`TP / (TP + FP)`).
2. **Semantic Rule Recall:** Percentage of true ground-truth semantic errors detected (`TP / (TP + FN)`).
3. **Correction Time:** Pipeline execution runtime in seconds.
4. **Compile Rate:** Percentage of proposed rules that compile into executable transform plans.
5. **Cost:** Token consumption & estimated USD cost per run.
6. **Idempotency Score:** Verification that re-running cleanup on clean output changes 0 rows.
7. **Abstention Quality:** Rate of properly sending low-confidence/unfixable errors to quarantine.

---

## 4. API Endpoints Reference

Start the FastAPI server:

```bash
.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Endpoints:
- `POST /api/v1/profile`: Profiles input JSON data rows and returns metadata summary.
- `POST /api/v1/rules/propose`: Proposes quality rules using selected variant (`C0`, `C1`, or `A1`).
- `POST /api/v1/transform/execute`: Compiles and executes rules, outputting CleanDB and Quarantine row counts.
- `GET /api/v1/audit/store`: Retrieves event audit records and transition manifests.
- `POST /api/v1/reset`: Resets state machine, clears audit store, and reseeds data in < 60 seconds.
- `GET /health`: Health check status.
