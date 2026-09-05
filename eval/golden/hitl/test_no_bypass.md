# Golden HITL: no unapproved rule mutates data

**Canonical test:** [`tests/test_no_hitl_bypass.py`](../../../tests/test_no_hitl_bypass.py)

This golden pointer documents the regression gate that:

- `CleanDatabaseTool` / `approved_rules_for_clean` never synthesizes approved rules
- Analysis pipeline status stops at `awaiting_hitl`
- Unapproved proposals cannot mutate warehouse data

Suite: **golden/dev** (not held-out). Do not put expected answers into prompts or heuristics.
