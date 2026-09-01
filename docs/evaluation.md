# Evaluation Evidence (BTC #10)

**Date:** 2026-09-01 · **Tip:** `6308ec4` · **Honest:** RAGAS **N/A** (not in deps; custom GT matchers).

## Pytest

```
757 tests collected
uv run pytest tests/test_llm_provider_status.py tests/test_ngan_gt_eval.py -q
→ 8 passed (2026-09-01, this docs lane)
```

Coverage plugin not configured (`--cov` unsupported in pytest.ini) — not claimed.

Full suite: `uv run pytest tests/` (prefer CI self-hosted; local may hit HITL 403 flakes on ACL-era filters).

## Eval vs GT (in-repo)

| Source | Result |
|---|---|
| Ngan GT adapter (`evaluate_ngan_gt`) | Detection P/R/F1 ~0.68/0.93/**0.79**; RCA top-1 ~0.93; Frozen RCA **13/13** (Slice2 notes) |
| UI `#/operations/eval` | GT banner + scores painted (#29) |
| Detector JSON `eval/results/eval_detectors_*.json` | L1 F1=1.0 sample 2026-08-19 |
| `eval/results/report.md` | Agentic gate historical PASS |

## HITL / ACL evidence

| Check | Status |
|---|---|
| Analyst cannot Approve | #35 + `hitl-analyst.png` |
| Steward Approve / Remember | #36–37 + `hitl-steward.png` |
| Provider-off | #39 + `chat-llm-off.png` |
| steward_a↛B · Admin names-only | **#40** live d086/t086 #2 · status-report Phase 2 GO |

## RAGAS

**N/A** — no `ragas` dependency. Use GT matchers + pytest above for BTC scoring.
