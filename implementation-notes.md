# Implementation notes

## 2026-08-19 — ReAct loop: remaining PLAN P0

- `_log_trace`: empty thought, actor_kind from action.
- Chat WS `agent.trace` is summary-only.
- Upload proposal = `HITL_PREFIX` / profile+propose; RuleProposalCard sends session+dataset, no Accept & Execute.
- `DATATRUST_DEMO_SEED` gates taxi seed. Domain names tagged `(DEMO)`.
- `schemas/workflow-event.schema.json` (PLAN §9). GET `/traces` omits thought unless `include_thought=1`.

## 2026-08-19 — Wave 6a honesty pass + PLAN lock

- PLAN.md: §14.4/16.3/16.4/19.5/27.1 + Wave 6a. Grill lock: Q1C Q2B Q3C Q4A Q5 A then B.
- Traces: no synthesis; map `tool_name`/`tokens_used`/`observation`; WS `agent.trace`; jump-to-chat uses `.chat-stream`.
- HITL queue filter `?dataset_key=`; `quality_rules.dataset_key`.
- New Chat: VinGroup live demo, JSONL replay, upload. Auto-run stops at HITL.
- Actor labels: Orchestrator / L1–L4 / C1 / Steward. No 99% health default.

## 2026-08-19 — Grok AI log (request + response only)

- Added `.grok/hooks/ai-log.json`: `UserPromptSubmit` + `Stop` only (no `PreToolUse`/`PostToolUse`).
- `scripts/log_hook.py --tool=grok` writes prompt + `lastAssistantMessage`; drops tool events, thoughts, subagents, Stop continuations, and session-end Stop.
- Pre-push hook already submits `.ai-log/session.jsonl`. Trust project hooks once via `/hooks-trust`.

## 2026-08-15 — Upload session and dataset profiling

- Upload declarations now use the stable message ID `upload:{dataset_key}` and session `dataset:{dataset_key}`. Re-uploading the same logical dataset replaces the existing declaration instead of creating another chat row.
- Selecting an uploaded dataset runs the real profiling endpoint with a 50,000-row sample before the pipeline bootstrap starts.
- The chat stream reports profiling start, completion, and API failure; no profile/demo fallback was added.
- Verification: backend Python syntax check and frontend TypeScript/build pass.
