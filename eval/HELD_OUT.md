# Held-out evaluation

Do not tune prompts or heuristics against individual expected answers in a frozen pack.

Preferred location (in order):
1. Mentor-provided pack outside this branch
2. CI secret artifact
3. Checksum-locked `eval/held_out/SHA256SUMS` if (1)(2) impossible

Report held-out scores separately from golden. Never blend into one weighted score.

## Current status

No external held-out pack exists on this branch yet. Do **not** invent one.

Until a mentor pack (or CI secret / checksum-locked pack) arrives:

- `eval/eval_rca.py` remains **golden/dev** (same as `eval/golden/rca/`).
- Scores from `eval/eval_rca.py` and `eval/golden/` must be reported as golden only.
- Do not blend golden + held-out into one weighted score.
