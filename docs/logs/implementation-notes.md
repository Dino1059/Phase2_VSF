# DataTrust OS v3 — Technical Implementation Notes & Developer Log

> **Target Audience:** Developers, Co-workers, and Future AI Agent Sessions  
> **Last Updated:** 2026-08-02  
> **Pytest Gate:** 125 / 125 Tests Passing (`54.34s`)  
> **Git Rule Constraint:** Commit locally; DO NOT execute `git push` unless explicitly ordered by user.

---

## 1. Project Context & Objectives (DATA-02)

DataTrust OS v3 is an autonomous AI data governance system built for the VinGroup enterprise ecosystem (VinFast EVs, Xanh SM Ride-Hailing, V-GREEN Charging Infrastructure, and Vietnamese Customer Feedback).

### Key Architecture Components:
1. **Single Model Enforcement (`src/services/llm.py`)**: Uses strictly `gemma-4-26b-a4b-it` with 60s timeout and 3 exponential backoff retries.
2. **Native Tool Calling (`src/api/routes.py`)**: Passes `GOVERNANCE_TOOLS` schema to Google AI Studio API for native function calls (`profile_dataset`, `detect_anomalies`, `propose_quality_rules`, `diagnose_root_cause`, `clean_database`, `list_datasets`).
3. **VinGroup 4-Domain Datasets (`data/vingroup/` & `data/vingroup_real/`)**: Standardized datasets covering EV Telemetry, V-GREEN Chargers, Xanh SM Trips, and Vietnamese Feedback.
4. **Vietnamese NLP Aspect Extractor (`src/services/vietnamese_nlp.py`)**: Normalizes teen code (`"ko sac dc"`, `"app lag vl"`), extracts aspect entities (`Location`, `Component`), and cross-validates with V-GREEN telemetry logs.
5. **Composite Anomaly Scoring (`src/tools/anomaly.py`)**: $S_{composite} = w_1 \cdot \text{Sigmoid}(Z_{robust}) + w_2 \cdot S_{isolation\_forest}$.
6. **Clean DB Creation Pipeline**: Evaluates approved rules, creates Clean DB + Quarantine table, and generates SHA-256 cryptographic lineage hashes.

---

## 2. API Endpoints & Multi-Agent Operations

### Key Routes in `src/api/routes.py`:
- `POST /api/v1/chat/send`: Main chat endpoint. Parses commands, invokes `gemma-4-26b-a4b-it` tool calling, routes execution, broadcasts WebSocket updates, and stores messages in SQLite `data/conversations.db`.
- `GET /api/v1/chat/sessions`: Lists active chat sessions.
- `GET /api/v1/chat/history`: Fetches chat history for a session.
- `POST /api/v1/datasets/upload`: Uploads CSV/Parquet datasets and registers them dynamically.
- `GET /v3`: Serves compiled React + Vite + Tailwind frontend (`src/static_v3/index.html`).

---

## 3. Dataset Registry & Schemas (`src/config.py`)

Registered keys in `dataset_registry`:
- `vinfast_ev_telemetry_dirty`: `data/vingroup/vinfast_ev_telemetry_dirty.csv`
- `vgreen_charging_stations_dirty`: `data/vingroup/vgreen_charging_stations_dirty.csv`
- `xanh_sm_trips_dirty`: `data/vingroup/xanh_sm_trips_dirty.csv`
- `xanh_sm_customer_feedback_dirty`: `data/vingroup/xanh_sm_customer_feedback_dirty.csv`
- `real_vinfast_ev_telemetry`: `data/vingroup_real/real_vinfast_ev_telemetry.csv`
- `real_vgreen_charging_stations`: `data/vingroup_real/real_vgreen_charging_stations.csv`
- `real_xanh_sm_trips`: `data/vingroup_real/real_xanh_sm_trips.csv`
- `real_xanh_sm_customer_feedback`: `data/vingroup_real/real_xanh_sm_customer_feedback.csv`

---

## 4. Key Scripts & Tools

- `scripts/generate_vingroup_dataset.py`: Generates 4 synthetic VinGroup test datasets + ground-truth fault manifest (`vingroup_fault_manifest.json` with 123 fault entries across 9 fault families).
- `scripts/fetch_real_public_datasets.py`: Ingests real public datasets (ST-EVCDP, UIT-VSFC, Telemetry, Ride Hailing).
- `scripts/ingest_vingroup_real_data.py`: VinGroup Domain Schema Mapper converting raw public datasets to enterprise VinGroup schemas.

---

## 5. Verification & Test Suite

Run unit & integration tests using:
```bash
.venv/bin/python -m pytest tests/ -v
```
- **Total Tests**: 125 Passed cleanly.
- **Coverage**:
  - `tests/test_api.py`: FastAPI endpoints & tool routing.
  - `tests/test_vingroup.py`: VinGroup datasets, NLP aspect extractor, and composite anomaly scoring.
  - `tests/test_real_public_ingestion.py`: Real public dataset ingestion & schema mapping.

---

## 6. Guidelines for Future Agent Sessions & Co-workers

1. **Model Requirement**: Always use `gemma-4-26b-a4b-it` in `GoogleAIStudioLLM` with 60s timeout per call. Do NOT add model fallbacks.
2. **Git Rule**: Do NOT execute `git push` automatically. Always stage and commit changes locally (`git commit -m "..."`), and wait for the user to explicitly command "push".
3. **Pytest Gate**: Always run `.venv/bin/python -m pytest tests/ -v` to verify zero regressions before declaring task completion.
