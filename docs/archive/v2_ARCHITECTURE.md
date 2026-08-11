# DataTrust OS v5 Operational Trust Console.0 — Architecture

## Overview

DataTrust OS is an Enterprise Cross-Domain Root-Cause Diagnosis & Data Quality Governance Platform for the VinGroup EV Ecosystem.

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Next.js Frontend (v3)                      │
│  Dashboard │ HITL Queue │ Traces │ Quarantine │ Sources       │
└────────────────────────┬─────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────┼─────────────────────────────────────┐
│                    FastAPI Backend                            │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐ │
│  │Dashboard│  │   HITL   │  │  Pipeline │  │   Traces     │ │
│  │  API    │  │   API    │  │   API     │  │   API        │ │
│  └────┬────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘ │
│       └────────────┼──────────────┼────────────────┘         │
│                    ▼              ▼                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              DataTrust Orchestrator                      │ │
│  │  Profiler → Anomaly → Diagnosis → RuleProposer → HITL   │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              ReAct Engine (Bounded Loop)                │  │
│  │  Thought → Action → Observation → ... → Conclusion     │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  Tool Registry                         │  │
│  │  NLP │ Profiler │ Anomaly │ Telemetry │ Rules │ Exec   │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           ▼                                  │
│  ┌──────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ Gemma-4  │  │  Vietnamese NLP  │  │   Audit Service  │   │
│  │ LLM      │  │  (353 teencode)  │  │   (SHA-256)      │   │
│  └──────────┘  └──────────────────┘  └──────────────────┘   │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                       DuckDB                                 │
│  Telemetry │ BMS │ Feedback │ Trips │ Rules │ Quarantine     │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Ingest**: Scrape/import data from 5 sources → DuckDB raw_snapshots
2. **Profile**: DataProfilerTool computes column statistics
3. **Analyze**: AnomalyDetectorTool + NLPExtractorTool find issues
4. **Diagnose**: DiagnosisAgent cross-references NLP + telemetry
5. **Propose**: C1/A1 Investigators suggests quality rules
6. **Review**: HITL queue for human approval
7. **Execute**: RuleExecutorTool applies approved rules, quarantines violations
8. **Audit**: Every action logged with SHA-256 state hash

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Database | DuckDB | Embedded, zero-config, fast analytics |
| LLM | Gemma-4 via Google AI Studio | Free tier, function calling |
| NLP | Custom Vietnamese pipeline | Teen-code dictionary, domain ontology |
| Architecture | ReAct loop | Bounded, traceable, tool-grounded |
| Frontend | Next.js + Tailwind | SSR, i18n, modern stack |
| HITL | Approve/Reject/Edit gate | Safety before rule execution |

## Directory Structure

```
P-086/
├── src/
│   ├── api/          # FastAPI routes
│   ├── agents/       # 5 sub-agents + baselines
│   ├── db/           # DuckDB connection + schema
│   ├── models/       # Pydantic models
│   ├── orchestrator/ # ReAct engine + orchestrator
│   ├── services/     # NLP, LLM, audit, WebSocket
│   ├── tools/        # 6 deterministic tools
│   └── main.py       # FastAPI app
├── eval/             # Benchmark & evaluation
├── tests/            # 200+ tests
├── docs/             # Architecture, demo, evaluation
├── frontend-v3/      # Next.js dashboard
└── data/             # DuckDB + scraped data
```
