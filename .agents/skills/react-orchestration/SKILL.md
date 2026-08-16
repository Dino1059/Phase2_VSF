---
name: react-orchestration
description: Multi-model ReAct loop for complex multi-file tasks. Orchestrator thinks, Flash workers execute, Pro verifier validates.
triggers: ["multi-agent", "react loop", "orchestrate", "parallel workers", "verify fix"]
---

# ReAct Multi-Model Orchestration Skill

## When to Use
- Task requires editing 3+ files with potential cross-file dependencies
- User requests "multi-agent" or "parallel" execution
- Audit/review found multiple issues to fix simultaneously
- Any task where quality verification is critical before commit

## Model Assignment

```
Orchestrator (YOU) = highest reasoning model (Opus/Pro Thinking)
Workers            = flash (fastest, one file per worker)
Verifier           = pro (deep review, read-only research subagent)
```

## Phase Protocol

### Phase 1: THOUGHT (Orchestrator)
```
1. Read audit/requirements
2. Identify ALL files that need changes
3. Map dependencies: which changes depend on others?
4. Group into parallelizable batches (no file conflicts)
5. Check for false positives in audit findings
6. Output: Phase plan with worker assignments
```

### Phase 2: ACTION (Flash Workers × N)
```
1. Define one worker per file (or tightly coupled file pair)
2. Give each worker:
   - Exact file path(s) they OWN
   - What API methods/imports already exist
   - Explicit "do NOT modify" file list
   - Clear success criteria
3. Dispatch all workers in single invoke_subagent call
4. Wait for all completion messages
```

### Phase 3: OBSERVATION (Orchestrator)
```
1. Run deterministic gates:
   - pytest tests/ -q
   - tsc --noEmit (for TS projects)
   - npm run build (if frontend)
2. Check: Do all gates pass?
   - YES → proceed to verification
   - NO → identify failing worker, loop back to Phase 2 for that worker only
```

### Phase 4: VERIFICATION (Pro Verifier)
```
1. Dispatch research subagent with Model=pro
2. Give explicit checklist of criteria to verify per file:
   | Check | Expected | File |
3. Verifier reads ALL modified files and outputs verdict table
4. Must end with overall PASS/FAIL
```

### Phase 5: CONCLUSION (Orchestrator)
```
IF PASS:
  - git add <changed files> && git commit -m "..." && git push
  - Update audit report / walkthrough artifact
IF FAIL:
  - Extract failing criteria
  - Loop back to Phase 2 with targeted fix workers (max 3 total loops)
IF 3 LOOPS EXHAUSTED:
  - Escalate to user with findings
```

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Do Instead |
|---|---|---|
| Two workers editing same file | Merge conflicts, lost edits | Strict file ownership |
| Worker editing a dependency before it exists | Import errors | Phase dependency ordering |
| Skipping deterministic gates | Silent breakage | Always run pytest + tsc between phases |
| Verifier as a write agent | Bias — it should be independent | Verifier = research (read-only) subagent |
| Committing before verification | Ships broken code | Only commit after PASS verdict |
| Silent mock fallbacks in catch blocks | Hides real failures during demo | Throw errors, show error toasts |

## Example Worker Prompt Template

```
Fix `{COMPONENT}.tsx` in `{PROJECT_PATH}/frontend/src/components/`.

The API methods ALREADY EXIST in `frontend/src/services/api.ts`:
- `apiService.{method1}()` → `{HTTP_METHOD} {ENDPOINT}`
- `apiService.{method2}()` → `{HTTP_METHOD} {ENDPOINT}`

Your task:
1. Read the current file to understand its structure.
2. Replace hardcoded mock arrays with data fetched from `apiService.{method}()` on mount.
3. Wire user actions to corresponding API calls.
4. Add loading states (`Spin`) and error handling (`message.error()`).
5. Keep the existing UI layout — only change the data source.

Do NOT modify any other files. Only edit `{COMPONENT}.tsx`.
```

## Example Verifier Prompt Template

```
You are a code quality verifier. Read these {N} files and check:

### {File 1}
- Does it call `apiService.{method}()` on mount?
- Is there a loading spinner during API calls?
- Are errors caught and shown?
- Is there ANY remaining hardcoded mock array as PRIMARY data source?

For EACH file, output:
| Check | Status | Notes |

End with overall PASS/FAIL verdict.
```
