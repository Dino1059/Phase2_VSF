## Summary

Thanh+Huyền HITL causal flow: `feat/th-hitl-causal-flow` @ **`3e72d76`** (Steward chat Clean → `POST /hitl/execute`) on exclusive **`149334e`/`cd624bb`/`9461a95`** → **`v5`**. **Do not merge.** **t086 untouched.** Product work is the HITL cut — not CI. **CI wait BTC only.**

Workspace binds **`(dataset_key, ICT calendar day)`** — that day **is** `run_id`. Staging **d086 only**. Full 08:40 ordered cut (not the 20:05 mini-cut). Audit: `.loop-state/V5_TH_CUT_AUDIT.md`.

**This landing:** Steward chat Clean chip posts `POST /hitl/execute` (`3e72d76`). Prior: exclusive primary-rule COUNT + incident uniqueness (`9461a95` / `149334e` / docs `cd624bb`), warehouse rollback of `clean.*`, Analyst Execute **403**. See `.loop-state/V5_TH_CUT_NEXT.md`.

### Landings on this tip

| SHA | What |
|---|---|
| **`3e72d76`** | Steward chat Clean chip → `POST /hitl/execute` (same warehouse path as Rules Execute). Preview-before-approve unchanged |
| **`cd624bb`** | Docs: record exclusive HEAD `149334e` on TH cut next |
| **`149334e`** | Incident stories stay when primary rule is missing (cluster fallback) |
| **`9461a95`** | Exclusive primary-rule COUNT + incident uniqueness `(dataset, day, entity, primary rule)`; warehouse rollback of `clean.*`; Analyst Clean chip Steward-gated |
| **`06d725d`** | d086 frontend stamp `9461a95` |
| **`6078efe`** | CI: restored last-green Quality Gate `push`/`concurrency`/`workflow_dispatch` (`runs-on: self-hosted` unchanged) |
| **`4cf3879`** | CI: Hosted Probe is `workflow_dispatch` only; job names no longer match required Quality Gate checks |
| **`f4b6d32`** | d086 stamp + ordered-cut audit docs |
| **`c4984fc`** | Grill **1B**: real table+day SQL COUNT preview + Steward Execute warehouse |
| **`e269152`** | Steward Execute chip wrap (frontend `tsc`) |
| **`5d21b77`** | Chat **edit-rule**: sandbox preview only; no 4-dataset inventory |
| **`15619dc`** | Steward Execute role: compare JWT to `UserRole.STEWARD.value` (`"Steward"`) |
| **`deded2c`** | Chat greetings / capabilities: no `profile_dataset` / `list_datasets` |
| **`b73008a`** | GET `/hitl/sandbox/{id}` meta-first (Q=0 is 200); sample rows day-scoped; Remember default OFF |
| **`afa9826`** | d086 frontend dist stamp for `b73008a` |

### Grill 1B — Execute writes warehouse

| Stage | What it does | What it does **not** |
|---|---|---|
| **Sandbox PREVIEW** | Day-scoped SQL `COUNT(*)` for `(dataset_key, ICT day)`. | Does not approve. Does not write warehouse. Must **not** treat Q=3000 as warehouse. |
| **Approve** | Steward stamps `quality_rules.status`. **Approve ≠ Execute.** | Does not fill clean.* / quarantine partitions. |
| **Execute (Steward)** (`15619dc`) | Writes **both** `clean.*` and quarantine. `counts_kind: "warehouse"`. | Viewer / Admin / Analyst **403**. |

HITL write (Approve / Remember / Rollback / Execute) remains **Steward only**. Analyst proposes. Admin/Auditor watch. Analyst `POST /hitl/execute` is **403**. Rollback after Steward Execute moves those `clean.*` day rows back to quarantine (`9461a95`).

### Chat

- `hi` / `what can you do?` = smalltalk (`deded2c`). No profile/list.
- `edit rule:` = sandbox preview only (`5d21b77`).
- Steward **Clean & Quarantine** chip (`3e72d76`) = `POST /hitl/execute` warehouse path — **not** chat `clean database`. Analyst chip hidden (`canHitlWrite`); Analyst execute stays **403**.
- Heuristic skips SYSTEM_PROMPT catalog and Context `dataset_key`. History passed.

### Then 6–8

6. Search-all / empty ⌘K → workspace inspector with current `(table, day)`.
7. Live ingest writes **`landing.*` only**; `POST /ingestion/promote` copies to `main.*`. Names: **`vingroup_pilot`**. VIN UNION landing.
8. Chat Accept / Edit / Reject hidden; HITL write on Rules tab.

## CI — wait for BTC (not a P-086 action)

**Lock (29 Aug 2026 ~21:25 ICT):** the self-hosted Quality Gate runner is owned by **BTC (organizers)**. We cannot change it. Must wait. **Not a priority. Not a P-086 action item.**

- Quality Gate stays `runs-on: self-hosted`. Overnight green = the **BTC eph-vmrunner** pool claims successor **[33255820678](https://github.com/AI20K-Build-Phase-Cohort-3/P-086/actions/runs/33255820678)** (PR) / **[33255818241](https://github.com/AI20K-Build-Phase-Cohort-3/P-086/actions/runs/33255818241)** (push). Stale **33255172365** was cancelled. **Not green until BTC’s pool claims a run and it succeeds.**
- Stop hunting `vm-runner` / the eph-vmrunner provisioner. SSH **2203** is **d086 LXC** (IPv6 + IPv4 NAT 2203), **not** the CI VPS. Do not register a runner. Do not raise hosted billing as a fix (`ubuntu-latest` is a separate dead path).
- Hosted Probe is dispatch-only (`4cf3879`); it cannot paint required QG names red. `ci.yml` already restored last-green triggers (`6078efe`) — no further workflow edits.

## Status — not merging

- **Do not merge** into `v5`.
- **t086:** not deployed, not restarted. Never restart `datatrust-cloudflared`.
- **d086:** backend StartedAt **`2026-08-29T14:45:36Z`** healthy (no restart this cut). Frontend stamp `<!-- d086-v5 th-hitl 3e72d76 -->` (container StartedAt `2026-08-21T18:16:49Z`, not recreated).

## Honest remaining (not ordered-cut FAILs)

- Live COUNT this smoke **C=47439 Q=2 S=47441** — not pytest fixture **7/3**. Not 3000/0.
- Live COUNT follows approved-rule set (not pytest fixture 7/3).
- Exclusive VIN+primary-rule Alerts need Steward Execute so quarantine has `rule_id`.
- **CI Quality Gate not green** until BTC’s eph-vmrunner pool claims **33255820678** (or later). Wait BTC only. Not a P-086 action. No t086 Playwright.

GET `/hitl/sandbox/{id}` **no longer 404s** on COUNT-only (Q=0) preview. Sample SELECT is table+day.

## Out of scope

Ngân `fault_manifest`, Dũng benchmark, t086, AI-on-rejects, merge to `v5`/`main`.

## Test plan

- [x] Ordered cut 1–7 **PASS** (see `.loop-state/V5_TH_CUT_AUDIT.md`)
- [x] Pytest `tests/test_sandbox_split.py` + `tests/test_th_hitl_causal_flow.py` + `tests/test_qa_t086_gates.py` **82 passed**
- [x] Steward chat Clean chip → `POST /hitl/execute` (`3e72d76`); d086 stamp `3e72d76`
- [x] Analyst Execute **403** (pytest + live d086)
- [x] Exclusive COUNT + incident uniqueness (`9461a95` / `149334e` / `cd624bb`); warehouse rollback
- [x] Preview-before-approve unchanged
- [x] GET sandbox meta-first; missing id 404
- [x] Sample rows day-scoped
- [x] d086 health + stamp `b73008a`; preview SQL COUNT not 3000/0; warehouse 0/0 until Execute
- [x] Analyst Execute **403**; Steward Execute JWT `.value` (`15619dc`)
- [x] Smalltalk `hi` / capabilities (`deded2c`)
- [x] Grill 1B warehouse Execute (`c4984fc`)
- [x] Hosted Probe **not** required-name (`4cf3879`)
- [ ] Quality Gate **33255820678** claimed by **BTC** eph-vmrunner and **success** (wait only; not a P-086 action)
- [ ] Pytest fixture 7/3 on live d086
- [x] Hosted billing **not** a fix (do not raise spend cap)
- [x] **Not merging.** t086 StartedAt `2026-08-27T05:33:09Z` / `05:33:40Z`. cloudflared `2026-08-16T16:30:41Z`

Deploy: **d086 only.**
