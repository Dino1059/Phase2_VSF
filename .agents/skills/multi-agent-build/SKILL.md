---
name: multi-agent-build
description: Pattern for decomposing large implementation tasks into parallel subagent workers with shared codebase. Derived from DataTrust OS v2 build (5 agents, 47→84 tests).
triggers: ["build with agents", "multi-agent implementation", "parallel build", "scaffold project"]
---

# Multi-Agent Parallel Build Skill

## When to Use
- Greenfield implementation with 5+ new modules
- Major version upgrade requiring changes across all layers (backend, frontend, tests, docs)
- User says "use multi-agent" or "build with subagents"

## Pre-Flight Checklist

1. **Branch isolation:** Create new branch BEFORE dispatching agents (`git checkout -b v2`)
2. **Design decisions locked:** All architecture questions resolved (use `/grill-me` first)
3. **Existing tests pass:** Run `pytest` to establish baseline (e.g., 47 tests)
4. **File ownership map:** No two agents write the same file

## Agent Decomposition Pattern

### Layer-Based Split (Recommended for Full-Stack)

```
Agent 1: Data/Model Layer
  → schemas, data sources, connectors, profilers

Agent 2: Intelligence Layer
  → LLM adapters, sub-agents, orchestrator, context builders

Agent 3: Service Layer
  → schedulers, alerting, background services, middleware

Agent 4: Presentation Layer
  → frontend scaffold, components, API client, routing

Agent 5: Quality Layer
  → test suites, evaluation harness, benchmarks, documentation
```

### Agent Definition Template

```python
define_subagent(
  name="<layer>_builder",
  description="<1-line scope>",
  system_prompt="""You are the <Layer> Builder for <Project> in <PATH>.
Your task:
1. Create <file1>: <description>
2. Create <file2>: <description>
...
N. Ensure all imports work cleanly and existing tests pass.""",
  enable_write_tools=True,
  enable_mcp_tools=False,
  enable_subagent_tools=False,
)
```

### Key Rules

1. **System prompt = contract.** Each agent's system prompt IS the spec. Be precise about:
   - Exact file paths to create/modify
   - Class names and method signatures
   - Which existing modules to import from
   - Integration points with other agents' work

2. **Shared schemas first.** If agents share Pydantic models, the Data/Model agent must define them first. Other agents import from `src/models/schemas.py`.

3. **Monitor for conflicts.** When agents report completion, check for file conflicts:
   ```bash
   git diff --name-only  # see what changed
   pytest tests/ -v      # verify nothing broke
   ```

4. **Incremental test count.** Track test growth: 47 → 52 → 60 → 84. Each agent should ADD tests, not break existing ones.

## Post-Build Verification

```bash
# 1. Full test suite
pytest tests/ -v

# 2. TypeScript check (if frontend)
cd frontend && npx tsc --noEmit

# 3. Frontend build
npm run build

# 4. Commit and push
git add . && git commit -m "feat: <description>" && git push origin <branch>
```

## Lessons Learned (from DataTrust OS v2)

| Lesson | Detail |
|---|---|
| **Schemas are the glue** | Multiple agents editing `schemas.py` causes conflicts. Have ONE agent own it, others import. |
| **Frontend mock trap** | Frontend agent will create mock data to show UI working. This MUST be audited and wired to real APIs afterward. |
| **Role casing matters** | If middleware normalizes roles (`.capitalize()`), verify ALL role checks use the same normalization. |
| **API path prefixes** | Ensure frontend `api.ts` paths match backend route prefixes (`/api` vs `/api/v1`). |
| **5 agents is the sweet spot** | Fewer = too much per agent. More = too many coordination points. |
