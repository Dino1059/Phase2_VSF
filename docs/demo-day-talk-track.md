# DataTrust OS — 3:00 spoken demo (thanh)

**For:** live DEV at `https://vocals-creative-vegetable-chemistry.trycloudflare.com` (`index-BHGq8Agv.js`)  
**Not** d086.  
**Written:** 2026-08-20 04:13 Asia/Saigon  
**Rule:** app numbers are `data_new` only. Industry stays in your mouth. Do not point at a tile and say Gartner / IBM / Monte Carlo.

If the room is already looking at the glass, skip the why and start at **0:15 Happy**.

---

## 0:00 — Why this exists (≤15 seconds, no click)

**Say:** Stewards are still drowning in noisy quality work, and charging data is where drivers feel it — a charger marked available that is dead is not a glitch, it is a failed stop. We do not put those industry figures on this screen. This screen is one VinGroup estate.

**Click:** nothing.  
**See:** whatever is up. Do not linger on a marketing slide.

---

## 0:15 — Happy (25 seconds)

**Click:** Happy / clean snapshot. Land on Command Center so Profiler is visible.

**See:** 60 VIN, 15-day batch. Profiler **99.1% Excellent**. **SoC = 0**. **OPEN = 0**.

**Say:** Same sixty vehicles, fifteen days. Completeness is already fine. Profiler calls it excellent — ninety-nine point one. Zero negative state of charge. Zero open incidents. This is the fleet when physics holds.

Do not open HITL here. Do not talk incidents.

---

## 0:40 — Unhappy (40 seconds)

**Click:** flip to `vingroup_pilot` / unhappy. Wait one beat so they see health **hold**, then go Critical. Open the incident list. Click the first Critical (SOC / VF8VNF_0006 if it is on top).

**See:** **99.1 is gone** — do not let a stale Excellent flash. Then **Critical**. **172 SoC < 0**. **103 V > 1000**. **8 OPEN**.

**Say:** Same grain. Health does not pretend. It holds, then it goes critical. One hundred seventy-two rows with state of charge below zero. One hundred three over a thousand volts. Fusion does not throw six hundred pings at you. It admits eight open incidents.

Point at the row. Do not recite Gartner.

---

## 1:20 — Traces (30 seconds)

**Click:** open the trace / evidence trail on that incident.

**See:** a real `event_hash` chain. Example shape: `75aeed132322…` — use whatever hash is on screen. Action, tool, evidence, elapsed. No raw model thought.

**Say:** This is the trail. Every step hashed. You can audit what the agent touched. Nothing writes yet.

---

## 1:50 — Honest batch (30 seconds)

**Click:** none required. If the batch-window chip is on the header, point at it.

**See / read aloud:** “Batch window 2026-01-01 → 2026-01-15 · not a live Kafka stream.”

**Say:** What you are looking at is a fifteen-day batch. First of January through the fifteenth. Production is the same detectors on a stream, frozen after a human. We are not showing you a fake Kafka cluster.

---

## 2:20 — HITL gate (35 seconds)

**Click:** HITL / proposed rule (`soc_pct >= 0` or `cost_vnd >= 0`). Show **Execute** disabled. **Approve**. Then **Run sandbox**. Point at the new `payload_hash`.

**See:** Execute grey until Approve. After Approve: sandbox run, real `payload_hash`. **Zero execute** before Approve.

**Say:** Approve is not execute. The button stays dead until a human signs. Then we run it in the sandbox and you get a payload hash you can check. No write before that.

---

## 2:55 — Close (5 seconds)

**Say:** The human still owns the write. The numbers on this glass came from this estate. Stop.

---

## If they interrupt

- “Production VinFast?” — No. Pilot mapped from public sources. Provenance is on the card.
- “Why 99.1 on unhappy?” — It must not flash. If it does, you already lost the beat; refresh and start unhappy again.
- Recycled twelve-point-nine million — that is twenty twenty. Do not say it.
- Industry % on a tile — never.
