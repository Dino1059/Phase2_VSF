# DataTrust OS — Architecture (BTC)

> Live: [https://t086.w9.nu](https://t086.w9.nu) · Staging: [https://d086.w9.nu](https://d086.w9.nu) · Health `/health` → 200  
> Tip: `6308ec4` (PR #40 dataset ACL) · Detail: [`ARCHITECTURE.md`](../ARCHITECTURE.md)

## Context

**DataTrust OS** — Operational Trust Console for VinGroup-style telemetry (EV / charging / trips).  
Pipeline: **ingest → L1–L4 detect → fuse → RCA/agent → HITL → sandboxed execute**.

## Mermaid — runtime

```mermaid
flowchart TB
  subgraph FE["Frontend — React 19 + Vite"]
    LP[Landing]
    DASH[Dashboard / Ingestion]
    WS[Workspace Chat]
    OPS[Ops: Rules Traces Eval]
  end
  subgraph EDGE["Edge"]
    CF[Cloudflare Tunnel *.w9.nu]
    NGX[Nginx static + /api]
  end
  subgraph API["FastAPI + uv"]
    AUTH[JWT RBAC + dataset_key ACL]
    HITL[HITL propose/approve/remember/execute]
    CHAT[Chat ReAct · provider ON/OFF]
    ING[Landing ingest + promote]
    EVAL[Eval vs GT]
  end
  subgraph DATA["Storage"]
    LAND[landing.*]
    WH[Warehouse DuckDB]
    AUD[Audit / rule_memory]
  end
  subgraph LLM["LLM"]
    PROV[Groq/Gemini/OpenAI/Ollama]
    TRACE[Ops Traces · optional LangSmith]
  end
  FE --> CF --> NGX --> AUTH
  AUTH --> HITL & CHAT & ING & EVAL
  ING --> LAND --> WH
  HITL --> AUD
  CHAT --> PROV & TRACE
  HITL -.->|sandbox until Steward execute| WH
```

## Roles + ACL (Phase 2 · #40)

| Principal | Scope |
|---|---|
| Steward (global) | Cross-dataset demo |
| steward_a / steward_b | `dataset_key` A=`ev_telemetry` · B=`trips` — A↛B |
| Analyst / Viewer | Dataset-scoped |
| Admin | **Names + aggregate only**; 403 on row/HITL/ingest detail; Reset OK; **no execute** |

## Export

GitHub Mermaid OK. Optional PNG via [mermaid.live](https://mermaid.live) for pitch slides.
