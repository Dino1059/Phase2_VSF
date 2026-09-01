# V5_BTC_DELIVERABLES — scoring tracker

**Updated:** 2026-09-01 ~16:10 ICT  
**Code tip:** `6308ec4` (PR #40 ACL) on `origin/v5`  
**Phase 2:** **GO · SHIPPED** · d086 + t086 #2 · steward_a↛B · Admin names-only  
**Landing surgical:** DEFER  
**Safety:** cloudflared untouched · no warehouse wipe  
**Status HTML:** https://d086.w9.nu/status-report.html  

## Scoring tips map

| BTC axis | Target | Evidence |
|---|---|---|
| Product | ≥8 | README + live t086 + screenshots |
| System | ≥7 | `docs/architecture.md` Mermaid |
| UI/UX | ≥7 | Responsive shots + roles |
| DevOps | ≥6 | Docker + CI workflows + `/health` 200 |
| Code | ≥7 | 757 tests collected; typehints; ruff path |

## Table 1–10

| # | Deliverable | Path | Status | Notes |
|---|---|---|---|---|
| 1 | Source code | repo | **DONE** | `.gitignore` + redacted `.env.example`; residual: historical `data_new/*.db` already tracked |
| 2 | README | `README.md` | **DONE** | Live URLs, shots, uv/pnpm, Docker, env NAMES, tree, tip 6308ec4 |
| 3 | Architecture | `docs/architecture.md` | **DONE** | Mermaid FE/API/HITL/landing/WH/LLM/CF + ACL |
| 4 | AI Logs | `docs/ai-logs.md` | **DONE** | LangSmith how-to + 10 flows incl ACL |
| 5 | Live URL | t086/d086 `/health` | **DONE** | 200 verified; tip ACL on v5 |
| 6 | Video | `docs/video-demo.md` | **STUB / USER** | Script+checklist; YouTube paste |
| 7 | Pitch | `docs/pitch-deck.md` | **STUB / USER** | 10-slide outline §9.6; PDF by user |
| 8 | Journal | `docs/journal.md` | **DONE** | 7 weeks incl Phase 2 GO |
| 9 | Worklog | `docs/worklog.md` | **DONE** | git milestones → #40 |
| 10 | Evaluation | `docs/evaluation.md` | **DONE** | pytest 8pass subset; GT; RAGAS N/A; HITL/ACL |

**Pack score:** 8/10 DONE · 2/10 USER stubs (video+pitch PDF) · HTML feed updated.

## Leftover for user
1. Record demo → YouTube → paste URL into `docs/video-demo.md` + README  
2. Design pitch PDF/PPTX from `docs/pitch-deck.md`  

## Deploy verify (2026-09-01)
- https://d086.w9.nu/status-report.html — BTC table 8 DONE + 2 USER stubs · tip `6308ec4`
- `/docs-screenshots/dashboard.png` 200
- `/health` d086 200 · t086 health JSON may still print `e0f877f` prefix while #2 stamp is `6308ec4` on status-report
