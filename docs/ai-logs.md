# AI Logs (BTC #4)

## LangSmith (optional)

| Variable | Purpose |
|---|---|
| `LANGCHAIN_TRACING_V2` | `true` to enable |
| `LANGCHAIN_API_KEY` | LangSmith key |
| `LANGCHAIN_PROJECT` | e.g. `datatrust-os-v5` |
| `AI_LOG_DIR` | Local `.ai-log` (gitignored `*.jsonl`) |
| `AI_LOG_SERVER` / `AI_LOG_API_KEY` | Instructor ingest hook |

```bash
cp .env.example .env   # fill secrets locally — never commit
uv run uvicorn src.main:app --port 8000
```

Redact tests: `tests/test_ai_log_redact.py`.

## In-product traces

- UI: `#/operations/traces` · shot: [`screenshots/ops-traces.png`](screenshots/ops-traces.png)
- Live: https://t086.w9.nu · https://d086.w9.nu

## Example flows (10)

| # | Flow | Expected | Evidence |
|---|---|---|---|
| 1 | Steward HITL Approve | Proposed→Active | `hitl-steward.png` · #35–36 |
| 2 | Analyst HITL | No Approve | `hitl-analyst.png` · #35 |
| 3 | Chat `hi` | Smalltalk, no dump | #37 |
| 4 | Chat `why VIN` | Causal story | #36–37 |
| 5 | LLM provider OFF | Honest UX | `chat-llm-off.png` · **#39** |
| 6 | Sandbox preview | write:off until Steward | HITL API |
| 7 | Remember ON | No double-promote | #36–37 |
| 8 | Run All Propose | Dataset-scoped beats | #31 |
| 9 | Landing→promote | Day COUNT | Landing QA |
| 10 | steward_a↛B | ACL deny B | **#40** `6308ec4` |

Demo tip: LangSmith optional — narrate Ops→Traces + HITL shots.
