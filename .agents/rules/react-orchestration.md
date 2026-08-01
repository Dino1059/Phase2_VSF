# ReAct Multi-Model Orchestration Rule

## MUST: Model Tier Assignment
- **Orchestrator** (you): Always use highest reasoning tier available (Opus Thinking / Pro Thinking)
- **Workers**: Always use `flash` tier (fastest available model) via `invoke_subagent(Model="flash")`
- **Verifier**: Always use `pro` tier via `invoke_subagent(Model="pro")` as a `research` subagent (read-only)

## MUST: Phase Discipline
1. NEVER commit code without running deterministic gates (`pytest`, `tsc`, `build`)
2. NEVER assign two workers to the same file
3. NEVER skip the Pro verification phase — even if gates pass, the verifier catches logic errors
4. ALWAYS dispatch workers with explicit file ownership and "do NOT modify" constraints
5. ALWAYS give the verifier an explicit checklist (not vague "review this")

## MUST: Loop Control
- Max 3 ReAct loops per task. If unresolved after 3, escalate to user.
- Each loop must have a measurable observation (test count, error count, verdict table).

## SHOULD: Skill Loading
- Check `.agents/skills/SKILLS_INDEX.md` before starting complex tasks
- Load full `SKILL.md` only when the task matches a trigger keyword
- Prefer existing skills over ad-hoc prompting
