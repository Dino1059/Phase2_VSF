# V5 Thanh+Huyền locked spec

**Branch:** `feat/th-hitl-causal-flow` from `v5`
**Deadline:** 08:40 AM ICT 2026-08-29 — do not merge; PR `--base v5` only. Ignore 20:40 PM.
**Deploy:** d086.w9.nu only. NEVER t086. NEVER restart datatrust-cloudflared.

Do not reopen these decisions.

---

## Context (three axes, workspace owns)

- Left DB + ICT calendar-day picker = source of truth for tools AND tabs (traces, profile, rules, split, alerts, quarantine).
- Chat history dropdown lists ONLY threads for current (dataset_key, calendar_day).
- Change DB: keep day; switch to latest chat for (new DB, same day) or New chat; reload tabs.
- Change day: keep DB; latest chat for pair or New chat; reload tabs.
- Calendar day = ICT. That day IS run_id for the jury story (collapse multiple pipeline ticks that day).
- Chat may propose a rule edit as a pending patch on the rule card (before/after). Steward Confirm = HITL edit. Analyst cannot confirm.

## Must (do these first, in order)

1. Bind chat + all listed tabs to (dataset_key, ICT day). Implement the three-axis switcher above. Run Id must be visible and actually filter.
2. Rule card: evidence trail + sandbox SQL COUNT(*) for bound table+day + sample preview ≤ existing SANDBOX_SAMPLE_CAP. NEVER load full table into RAM (prior 504). No JSON wall.
3. Incident is parent: one incident = (dataset_key, calendar_day, entity_id vehicle/station, primary rule or cluster). Card copy: suspected vehicle/station, because rows…, recommend check…. Deep-link to rule + quarantine. Alerts tab is this story, not a signal dump.
4. Remember-for-later: key (dataset_key, rule_id), default OFF, Steward only. Change-mind expires memory ONLY (does not undo today). Next day’s chat for that table inherits memory.
5. Rollback: last clean decision — move THOSE rows back to quarantine, mark decision superseded. Audit action, Steward only.

## Then if time

6. Search-all → workspace with (table, day) set: incidents, rules, quarantine, traces, vehicle/station id.
7. vingroup_pivot_landing.db: live ingest writes landing only; promote into main on Run All / day close.
8. Hide unnecessary buttons (do not delete routes).

Unfinished items: SPEC section on the same PR, still ship Must.

## Then progress (post-Must)

6. Search-all: ⌘K workspace shortcuts + backend hits use `searchHitWorkspacePath` with current `(table, day)`. Ops routes remain. `?tab=` opens inspector.
7. `POST /ingestion/promote` copies `landing.*` → `main.*` for a day (no-op if landing empty). Called from Run All + day activate + warmup. Names: `vingroup_pilot` only. Live ingest (`streaming_worker`, `POST /telemetry/ingest`) writes `landing.*` only.
8. Chat review Accept/Edit/Reject hidden (`chat-hitl-hidden`); handlers + ops routes kept. HITL write stays on Rules tab.

## Roles

- HITL write (Approve/Edit/Remember/Rollback/confirm chat-edit): Data Steward ONLY.
- Admin + Auditor: watch/read.
- Analyst: propose + Execute transform only. API 403 otherwise. UI must say the gate.

## Persist

- Accept/reject + (dataset_key, calendar_day, rule_id, persona). No reject-optimizer, no fingerprint suppress tonight.

## Out of scope

Ngân fault_manifest, Dũng benchmark, t086, AI on rejects.
