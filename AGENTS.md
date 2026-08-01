<!-- headroom:rtk-instructions -->
# RTK (Rust Token Killer) - Token-Optimized Commands

When running shell commands, **always prefix with `rtk`**. This reduces context
usage by 60-90% with zero behavior change. If rtk has no filter for a command,
it passes through unchanged — so it is always safe to use.

## Key Commands
```bash
rtk git status          rtk git diff            rtk git log
rtk ls <path>           rtk read <file>         rtk grep <pattern>
rtk pytest tests/       rtk cargo test          rtk test <cmd>
rtk tsc                 rtk lint                rtk cargo build
```
<!-- /headroom:rtk-instructions -->

---

# ReAct Multi-Model Orchestration Protocol

## Model Tier Assignment

| Role | Model Tier / Target | Responsibility |
|---|---|---|
| **Planner** | `opus` thinking | Big picture goals, architecture planning, complex feature roadmaps. |
| **Orchestrator** | `flash` high | ReAct loop control (`Thought` -> `Observation` -> `Conclusion`), phase planning, gate evaluation. |
| **Workers** | `flash` high | Fast parallel execution (`Action`), isolated file edits, 1 file/component per worker. |
| **Validator** | `flash` high | Fast read-only verification (`Verification`), checklist audit against criteria. |

## ReAct Loop Execution

```
┌─────────────────────────────────────────────────┐
│  0. PLAN (Planner / Opus Thinking)             │
│  - Big picture goals & implementation_plan.md   │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  1. THOUGHT (Orchestrator / Flash High)         │
│  - Analyze state, form step & parallel batches │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  2. ACTION (Workers / Flash High × N)           │
│  - Exclusive ownership: 1 file per worker       │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  3. OBSERVATION (Orchestrator / Flash High)     │
│  - Run deterministic gates: pytest, tsc, build  │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  4. VERIFICATION (Validator / Flash High)       │
│  - Read-only audit against criteria checklist   │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  5. CONCLUSION (Orchestrator / Flash High)      │
│  - PASS -> commit/push | FAIL -> loop back      │
└─────────────────────────────────────────────────┘
```

## Rules

1. **File Ownership:** Each worker gets exclusive ownership of specific files. Never assign the same file to 2 workers.
2. **Deterministic Gates:** Always run test/build gates between Action and Verification phases.
3. **Validator Independence:** Validator is a read-only research subagent (`Model: flash`).
4. **Max 3 Loops:** Max 3 ReAct loops before escalating to user.
