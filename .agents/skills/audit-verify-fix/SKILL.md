---
name: audit-verify-fix
description: Systematic audit → multi-agent verification → targeted fix cycle. Catches frontend mock traps, missing API wiring, and cross-layer inconsistencies.
triggers: ["audit", "review implementation", "check against plan", "verify wiring", "find mock data"]
---

# Audit → Verify → Fix Skill

## When to Use
- After a multi-agent build phase
- User asks "review the implementation" or "audit against the plan"
- Before pushing a release branch
- After discovering a frontend component shows data but you're not sure if it's real or mock

## Phase 1: Dispatch Parallel Audit Subagents

Split the audit into 3 orthogonal research subagents:

```
Auditor 1 (Backend): Read all source modules
  → Check: exports, imports, missing functionality, broken references, empty stubs

Auditor 2 (Frontend): Read all components + api service
  → Check: which components call real APIs vs use hardcoded mock arrays
  → Check: silent catch-block fallbacks that hide failures

Auditor 3 (Test Coverage): Read all test files
  → Cross-reference against explicit checklist of required coverage
  → Report: COVERED / MISSING per item
```

## Phase 2: Compile Audit Report

Create a structured artifact with:

```markdown
# Audit Report

## Design Decision Checklist
| # | Decision | Backend | Frontend | Tests | Status |
For each design decision from the plan, mark implementation status.

## Critical Findings
### 🔴 HIGH: <title>
### 🟡 MEDIUM: <title>  
### 🟢 LOW: <title>

## Recommended Fix Priority
| Priority | Issue | Effort | Impact |
```

### Common Finding Categories

| Category | What to Look For | Example |
|---|---|---|
| **Disconnected UI** | Component uses local state instead of API calls | `ScheduleManager.tsx` with `initialSchedules` array |
| **Silent Mock Fallback** | `catch` block returns hardcoded data instead of throwing | `api.ts` returning fake profile on error |
| **Casing Mismatch** | Role/enum values don't match across layers | `"Admin"` vs `"admin"` in middleware |
| **Simulated Metrics** | Evaluation uses hardcoded numbers instead of computed values | `benchmark.py` with random distributions |
| **Missing API Integration** | Backend endpoint exists but frontend never calls it | `/api/schedules` exists, component uses `setTimeout` |

## Phase 3: Fix with ReAct Loop

Use the `react-orchestration` skill to fix findings:

1. **Thought:** Triage findings. Check for false positives (e.g., both files normalize casing).
2. **Action:** Dispatch Flash workers — one per file that needs fixing.
3. **Observation:** Run `pytest` + `tsc --noEmit`.
4. **Verification:** Dispatch Pro verifier with explicit pass criteria per file.
5. **Conclusion:** Commit only after PASS.

## Frontend Mock Detection Checklist

When auditing a React/Vue/Angular component, check for these red flags:

```
❓ Does the component import apiService / fetch / axios?
❓ Does useEffect call an API endpoint on mount?
❓ Are action handlers (create/delete/update) calling API methods?
❓ Is there an array named `initial*`, `default*`, `mock*`, `sample*`?
❓ Are there setTimeout/setInterval faking async behavior?
❓ Does the catch block return data instead of throwing/showing error?
```

If a component has `initialSchedules = [...]` as its data source instead of
`apiService.getSchedules()`, it is a **mock component** regardless of how
polished the UI looks.
