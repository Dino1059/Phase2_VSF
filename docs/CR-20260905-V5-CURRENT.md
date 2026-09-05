# CR-20260905-V5-CURRENT

**Base:** `origin/v5` @ `2d18739`
**Branch:** `feat/v5-current-system`
**PR target (later):** `v5` — never `main`
**Park:** `feat/d086-corp-landing` @ `2d18739` (do not merge)

## Scope
1. Cherry-pick t086 auth/ACL (`29b82ef` `623eaac` `743888d`).
2. Restore sheep `LandingPage.tsx`.
3. Force AuthModal on AppLayout routes when logged out.
4. Execute PLAN.md Waves 1–3 (HITL, context budget, traces, eval).

## Out of scope
- Merging d086 corp LP into v5
- git push / PR until the user asks
- Restarting cloudflared / wiping warehouse
