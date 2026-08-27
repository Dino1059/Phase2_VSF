# V5 QA loop DONE — Run All propose-hang

**Verdict:** Run All proposes canonical HITL rules on **d086 only**. Playwright **20 PASS / 0 FAIL**. Ready for PR into `v5`.

| Field | Value |
|--------|--------|
| Date | 2026-08-27 |
| Branch | `fix/v5-runall-propose-hang` |
| Target | `v5` |
| Verify host | **d086 only** (`https://d086.w9.nu`, host `:8001`) |
| t086 | **untouched** — backend StartedAt `2026-08-27T05:33:09Z` |

## Root cause (locked)

`_resolve_table_target("ev_telemetry")` had `table_name=None` → detect/propose listed all schemas (`clean.trips`, `quarantine.*`). Unqualified `_TABLE_SIGNAL_CONFIG` missed `clean.trips` → skip notify. Propose re-ran detect + `profile_rows` on 86k rows → hang, HITL 0.

## Fix

- `pipeline_target_tables` / `canonical_pipeline_table` — warehouse key → one canonical table; never `clean.*` / `quarantine.*`
- Propose: no nested detect; sampled `profile_rows`; RuleProposer 8s LLM timeout → Ngan/heuristic
- Traces: dual-write `dataset:{key}`; `resolve_trace_rows` drops stale `anomaly_detect` skip rows

## Live prove (host :8001, 2026-08-27T09:03Z)

```
SID runall-prove-1787821394
elapsed 65.9s status completed steps 3
analysis: [detect_anomalies, propose_quality_rules] state RULES_PROPOSED
HITL_N 22  (battery_* / soc_range; not clean.trips)
SID traces: detect done, propose done "11 rules"
```

Public CF can 504 `/chat/send` after ~60s even when backend finishes. Prove via localhost:8001.

## Playwright (d086)

- Evidence: `.loop-state/qa-d086-loop-evidence.json`
- Shots: `.loop-state/qa-d086-loop/`
- Run All HITL **22** rules; propose beat **done**; traces **hide clean.***
- A-02: DETECTION F1 **80.0%**
- A-11 GT banner; A-09 TARGET COLUMN; A-01 375 hamburger
- A-03 viewer no Approve; A-04 Analyst 403
- B OFF inventory / B ON PONG; API match

## d086 stamp

- HTML: `<!-- d086-v5 qa-loop -->`
- backend StartedAt (this loop): `2026-08-27T09:06:19Z` (bind-mount; no image rebuild)
- frontend container StartedAt unchanged (`2026-08-21T18:16:49Z`)

## Remaining FAIL

**None** on d086 for this loop. Seeded `profile_dataset` beat can stay `running` if LLM skipped profile (HITL still lands).
