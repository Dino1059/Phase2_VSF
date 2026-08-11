# DataTrust OS v5 — FINAL IMPLEMENTATION PLAN
## Multi-Layer Data Reliability, Evidence-Grounded Incident Investigation, and Operational Trust UX

> **Status:** FINAL — team-aligned + current v5 implementation audit + UX decisions locked  
> **Prepared:** 2026-08-11  
> **Feature lock:** 2026-08-26 23:59 Asia/Ho_Chi_Minh  
> **Primary user:** Data Steward / Data Quality Manager  
> **Secondary user:** Data Engineer / Analytics Engineer  
> **Primary research question:** At which layer do deterministic rules, statistical/ML detection, fixed AI workflows, and bounded agents add measurable value?  
> **Core principle:** Use the cheapest sufficient mechanism. Agentic behavior is an escalation path, not the product thesis.

---

# 0. Executive Decision

DataTrust OS v5 will be developed as an **Operational Trust Console** for a Data Steward who repeatedly monitors project reliability, investigates evidence-backed incidents, decides what action is appropriate, and preserves a governed audit trail.

The system is not a chatbot that happens to run data-quality tools.

The system is not an “AI agent platform” whose success is measured by how many agents it contains.

The system is:

> **A project-level data reliability control plane that detects abnormal signals across four technical layers, fuses them into incidents, investigates uncertain causes with the minimum sufficient level of AI autonomy, and routes the result to either a preventive data control, an operational recommendation, or an explicit abstention.**

The final architecture must maintain a strict separation between:

```text
DETECTION
What looks wrong?
        ↓
L1 deterministic constraints
L2 entity-relative statistics
L3 relational models
L4 change-point detection

FUSION
Does the evidence justify an incident?
        ↓
Calibrated deterministic admission

INVESTIGATION
Why might it have happened?
        ↓
R0 deterministic resolution
C1 fixed AI workflow
A1 bounded dynamic investigator
A2 optional experiment only

DECISION
What should be done?
        ↓
Human-in-the-loop

EXECUTION
What actually changes?
        ↓
Deterministic governed execution
```

This separation is a release invariant.

---

# 1. Locked Product and UX Decisions

The following decisions are now locked.

## 1.1 User and product decisions

| Decision | Final choice |
|---|---|
| Primary user | **Data Steward / Data Quality Manager** |
| Secondary user | Data Engineer / Analytics Engineer |
| Signal semantics | Detect signal first; do not automatically call it a data error |
| Product pillars | Data Contract/Governance + Continuous Reliability Monitoring |
| Hero recurring workflow | **Monitoring → Incident → Evidence → RCA → HITL → Action** |
| RCA default output | Evidence-backed hypothesis + recommendation |
| Preventive rule | Only for data/pipeline/contract causes |
| Operational recommendation | For asset/real-world operational causes |
| Unknown cause | Explicit abstention / request more evidence |
| Agent entry point | Incident investigation, not default anomaly detection |
| A2 | Optional experiment after A1 failure analysis |
| Chat | Contextual assistant, not system of record |
| Feature lock | 26 Aug 2026 |

---

# 1.2 Locked visual / interaction decisions

User decisions:

- **Daily-use Data Steward UX first**
- **Light + dark themes, system-aware**
- Demo environment: **bright classroom/projector**
- Full visual redesign is permitted
- Product remains **brand-neutral**
- L1-L4 use **four stable categorical colors plus labels/icons**
- UI is **bilingual, Vietnamese default**
- A dedicated chart library may be added
- 1920×1080 and 1440p must both work well
- Executive Dashboard remains a major screen

Implementation consequence:

> Support both themes via semantic tokens. For the classroom demo, explicitly switch to the light theme during rehearsal because projector environments generally reward higher surface brightness and clearer printed-style contrast.

Do not hard-code light mode as the product default; respect system theme in normal use.

---

# 2. Current v5 Implementation Audit

The v5 repository has made meaningful architectural progress compared with v4.

The main positive change is the introduction of a real reliability bounded context with:

- L1-L4 detector modules;
- Fusion concepts;
- Incident models;
- R0/C1/A1 investigation classes;
- recommendation routing;
- governance primitives;
- Project/Incident-oriented frontend work.

However, architectural naming is currently ahead of implementation correctness.

The current risk is **false completeness**: classes and pages exist, but some behavior is still static, temporally invalid, duplicated, or demo-only.

---

# 2.1 Current implementation status

| Area | Current status | Required action |
|---|---|---|
| L1 | Mostly usable | Harden metrics, event contracts, SLA instrumentation |
| L2 | **Statistically incorrect** | Remove look-ahead leakage; implement prior-history baseline |
| L3 | **Statistically incorrect/incomplete** | Separate train/reference and evaluation windows; model entity scope |
| L4 | Partial | Add robust lifecycle, PELT comparator, persistence |
| Signal schema | Partial | Canonicalize across all detectors |
| Fusion | Partial | Replace threshold grouping with evidence-aware calibrated fusion |
| Incident | Partial | Persist canonical incident lifecycle |
| Evidence | Partial | Replace text-like references with typed immutable evidence IDs |
| R0 | Partial | Replace fragile text matching with typed diagnostic mappings |
| C1 | Demo-strength | Build a serious fixed AI investigation baseline |
| A1 | Demo-strength | Implement observation-dependent dynamic tool loop |
| A2 | Simulated/optional | Remove from headline benchmark unless admitted |
| Governance | Duplicated | Merge old approvals/HITL/new control authorization |
| Authentication | Demo-only | Signed identity and server-side role resolution |
| WebSocket | Unsafe scope | Authenticate and scope tenant/project/session rooms |
| Frontend | Partly static | Replace hard-coded incidents/evidence/KPIs with APIs |
| Benchmark | **Invalid for research claims** | Rebuild blind empirical evaluator |
| Data provenance | Partial | Label all integrated data as real/proxy/semi-synthetic/synthetic |
| Deployment | Drifted | Reconcile path/version/nginx/frontend build |
| Documentation | Drifted | Update VERSION, architecture, PRD/PLAN alignment |

---

# 3. P0 Correctness Fixes

No new visible feature should take priority over these items.

---

# 3.1 Fix L2 temporal leakage

## Current failure

The existing approach computes statistics from a series that includes observations later than the scored timestamp.

That creates look-ahead leakage.

Invalid:

```text
all 60 days
→ median/MAD
→ score day 20
```

Valid:

```text
for each timestamp t:
    history = records strictly before t
    if history < warmup:
        INSUFFICIENT_HISTORY
    else:
        baseline = robust(history)
        score observation(t)
```

## Canonical first model

Use:

- rolling median;
- MAD;
- robust Z score;
- configurable window;
- minimum warm-up;
- no future records.

Do not add complex forecasting until this baseline is correct.

## Mandatory leakage test

Given a fixed dataset:

```text
score(entity, day=30)
```

must not change when day 31-60 values are modified.

Add this as a regression test.

---

# 3.2 Fix L3 train/score leakage

## Current failure

A relationship model is fitted and evaluated on effectively the same data, and entity structure is insufficiently represented.

## Required design

For each configured relationship:

```text
reference window
→ fit expected relationship
→ freeze model/version
→ evaluation window
→ calculate residual
→ normalize residual
→ emit L3 signal
```

Supported scopes:

```text
GLOBAL
ASSET_CLASS
ENTITY
```

Default selection should depend on sample sufficiency.

## Initial model priority

1. domain-defined equation if available;
2. linear/robust regression residual;
3. Mahalanobis/robust covariance when justified;
4. Isolation Forest as comparator;
5. no deep model for MVP.

Each signal must explain the relationship, not just expose an opaque score.

Example:

```text
Expected trip count given charging behavior: 17.8
Observed: 8
Residual: -9.8
Residual percentile: 99.4%
```

---

# 3.3 Harden L4

Current CUSUM support is not enough for a convincing sequential layer.

Implement:

- CUSUM as online/simple detector;
- PELT as offline daily-batch comparator;
- minimum segment duration;
- persistence policy;
- change magnitude;
- pre/post summaries;
- duplicate change suppression.

Output must identify:

```yaml
change_time:
pre_window:
post_window:
metric:
pre_summary:
post_summary:
magnitude:
method:
score:
```

Evaluation must include change-point timing error.

---

# 3.4 Replace fake evidence references

Evidence references must be durable typed entities.

Bad:

```text
evidence_refs = ["high severity", "recent telemetry"]
```

Required:

```yaml
evidence_id: ev_...
incident_id: inc_...
project_id: project_...
source_type: TELEMETRY|TRIP|CHARGING|PROFILE|RULE|CHANGE|COMPLAINT
source_record_ids:
entity_ids:
time_window:
content_hash:
provenance:
summary:
```

Investigation cannot cite evidence that is not retrievable.

---

# 3.5 Fix cross-incident evidence leakage

Every retrieval query must be scoped by:

```text
tenant/project
+
incident
+
allowed entity/time scope
```

An A1 tool call must never receive the entire evidence store.

Add isolation tests:

```text
Incident A evidence
∩
Incident B evidence
=
∅
```

unless explicitly linked as shared evidence.

---

# 4. Canonical Data Semantics

---

# 4.1 Signal

A signal states that a detector observed something noteworthy.

It does **not** necessarily state that a data error exists.

```yaml
signal_id:
project_id:
entity_ids:
layer: L1|L2|L3|L4
signal_type:
metric_or_relationship:
event_time:
window_start:
window_end:
score:
severity:
detector_name:
detector_version:
evidence_refs:
provenance:
created_at:
```

---

# 4.2 Incident

An Incident means the signal set deserves investigation or human attention.

```yaml
incident_id:
project_id:
status:
entity_ids:
signal_ids:
admission_reason:
severity:
time_window:
evidence_refs:
classification:
owner:
created_at:
updated_at:
```

---

# 4.3 Hypothesis

```yaml
hypothesis_id:
incident_id:
claim:
classification: DATA|OPERATIONAL|MIXED|UNKNOWN
supporting_evidence_ids:
contradicting_evidence_ids:
missing_evidence:
confidence:
status:
```

Confidence must be calibrated or explicitly described as model confidence; do not invent values such as `0.95`.

---

# 4.4 Decision

```yaml
decision_id:
incident_id:
actor_id:
decision_type:
accepted_hypothesis_id:
reason:
timestamp:
```

---

# 4.5 Recommendation

Two typed classes:

```text
PREVENTIVE_DATA_CONTROL
OPERATIONAL_RECOMMENDATION
```

They must not be conflated.

---

# 5. Fusion v5

Fusion is responsible for deciding whether multiple signals justify an Incident.

It is not an LLM.

## 5.1 Fusion inputs

- severity;
- detector score;
- persistence;
- number of independent layers;
- time overlap;
- entity relationship;
- evidence quality;
- criticality;
- recency.

## 5.2 Fusion policies

Start with deterministic policies:

```text
critical L1
→ admit immediately

persistent strong single-layer signal
→ admit

agreement from >=2 independent layers
→ admit

manual promotion
→ admit
```

Do not claim a sophisticated learned Fusion model until enough labeled incidents exist.

## 5.3 Calibration study

Evaluate alternative fusion policies against:

- incident precision;
- incident recall;
- missed critical incidents;
- alerts reduced;
- duplicate incidents.

Pick the simplest policy on the Pareto frontier.

---

# 6. Incident Investigation Architecture

---

# 6.1 R0 — deterministic resolution

Use when the incident matches a known diagnostic pattern.

Examples:

```text
schema changed after deployment
known mapping mismatch
known null-producing transformation
known charger status code
```

R0 must use typed fields, not fragile substring matching.

---

# 6.2 C1 — strongest fixed-workflow baseline

Current C1 is too weak to be a scientifically useful comparator.

Implement:

```text
incident
→ deterministic context builder
→ fixed evidence bundle:
     signals
     entity history
     profile
     known changes
     relevant rule violations
→ one structured LLM call
→ output schema validation
→ evidence-ID validation
→ recommendation routing
```

The LLM receives no hidden ground truth.

C1 must be good enough that A1 can legitimately lose.

---

# 6.3 A1 — real bounded dynamic investigator

A1 becomes legitimate only when tool selection depends on observations.

Required loop:

```text
initialize incident state
        ↓
review known evidence
        ↓
form competing hypotheses
        ↓
choose next typed tool
        ↓
receive observation
        ↓
update support / contradiction
        ↓
continue / stop / abstain
```

Minimum tool registry:

- fetch entity history;
- fetch telemetry window;
- fetch trip history;
- fetch charging history;
- fetch profile;
- fetch DQ violations;
- fetch recent changes;
- resolve entity relationships;
- calculate detector detail;
- retrieve domain reference.

Each tool must query real project data.

No constant sample outputs.

## Bounds

- max tool calls;
- max wall-clock time;
- max tokens;
- max hypothesis revisions;
- explicit tool allowlist;
- evidence-ID requirement;
- no mutation tool;
- stop/abstain behavior.

---

# 6.4 A2 — optional only

A2 is not part of the required product architecture.

A2 may be implemented behind a feature flag only if an A1 failure report identifies:

```yaml
failure_mode:
frequency:
impact:
why_A1_fails:
proposed_specialist_or_verifier:
expected_metric_gain:
allowed_cost_increase:
```

Then compare A1 vs A2 on the same failure subset.

Do not implement multi-agent solely for presentation.

---

# 7. Unified Governance

Current approval/control systems must converge.

Canonical lifecycle:

```text
PROPOSED
→ REVIEW_PENDING
→ APPROVED | EDITED | REJECTED

APPROVED
→ COMPILED
→ SANDBOX_VALIDATED
→ AUTHORIZED
→ EXECUTED
```

If edited, the new version returns to review.

## Execution invariant

```text
EXECUTE
⇒ authenticated actor
∧ exact approved proposal version
∧ matching project/data snapshot
∧ compiled plan
∧ sandbox validation where required
∧ valid non-expired authorization
∧ immutable audit event
```

Execution API must accept:

```json
{
  "authorization_id": "..."
}
```

The client must not re-submit executable logic after authorization.

---

# 8. Security Remediation

For the course/demo, full enterprise SSO is unnecessary, but the security model must be structurally correct.

Implement:

- signed local JWT;
- seeded users;
- server-side role lookup;
- role claims verified server-side;
- no `X-User-Role` authority;
- no frontend `Admin` fallback;
- token-authenticated WebSocket;
- project/session-scoped WebSocket rooms;
- endpoint permission checks;
- execution authorization checks;
- audit actor identity.

Immediately:

- rotate any real-looking API key in repository/example env;
- replace with placeholders;
- scan repository history.

---

# 9. Data Strategy and Causal Digital Twin

The underlying source datasets are independent.

Do not present constructed joins as naturally observed cross-domain causal data.

Canonical provenance values:

```text
REAL_OPERATIONAL
PUBLIC_PROXY
SEMI_SYNTHETIC
SYNTHETIC
```

The integrated benchmark must be labeled:

> **Semi-Synthetic Causal Digital Twin**

---

# 9.1 Primary benchmark corpus

Target:

- 60 days;
- 30 VIN;
- 4 stations;
- 14-day detector warm-up;
- coherent trip/charging/telemetry timelines;
- fixed seed;
- versioned generator.

If density becomes insufficient, reduce VIN count rather than adding unrelated random records.

Sensitivity:

- 30-day slice;
- 90-day slice if statistically useful.

---

# 9.2 Generate causes before symptoms

Correct generator:

```text
latent cause
→ downstream correlated effects
→ detector-visible signals
```

Example:

```text
Battery degradation starts D35
        ↓
energy efficiency worsens
charging frequency rises
trip productivity falls
thermal behavior changes
optional complaint appears later
```

Do not inject independent anomalies and retroactively claim they share a root cause.

---

# 10. Research-Valid Benchmark

The legacy benchmark must not be used as project evidence.

Remove all logic that:

- preassigns detector capability to C0/C1/A1;
- gives ground truth to C1;
- makes A1 detect all fault families by definition;
- derives human time from recall;
- fabricates token counts;
- fabricates latency;
- returns fixed precision/recall/RCA accuracy;
- gives A1 richer evidence than C1.

---

# 10.1 Evaluation structure

```text
Frozen hidden case
        ↓
R0
C1
A1
        ↓
Persist raw predictions
        ↓
Independent evaluator
        ↓
Compare to hidden ground truth
```

---

# 10.2 Detection metrics

Per layer:

- precision;
- recall;
- F1;
- false positives per entity/day;
- detection delay;
- calibration where applicable.

Additional:

**L2**
- performance by warm-up/history length.

**L3**
- relationship residual ranking;
- performance by model scope.

**L4**
- change-point timing error.

---

# 10.3 Fusion metrics

- incident precision;
- incident recall;
- critical incident miss rate;
- duplicate incident rate;
- raw-signal-to-incident reduction.

Fusion must prove it reduces operator burden without hiding important cases.

---

# 10.4 RCA metrics

- Top-1 RCA accuracy;
- Top-3 RCA recall;
- MRR;
- evidence precision;
- evidence recall;
- unsupported claim rate;
- contradictory evidence coverage;
- abstention precision;
- abstention recall;
- unnecessary tool calls;
- time to diagnosis;
- token/cost per incident;
- human correction time.

---

# 10.5 Agent admission gate

A1 stays in the product only if:

### Safety guardrails

- evidence precision >= 90%;
- unsupported claim rate <= 5%;
- zero unauthorized mutation/execution;
- complete traceability;
- bounded latency/cost.

### And at least one meaningful value criterion

- Top-1 RCA >= C1 + 10 percentage points; OR
- evidence recall >= C1 + 15 percentage points; OR
- median human correction time <= 75% of C1.

If A1 does not pass:

> Ship C1.

This is a valid research outcome.

---

# 11. v5 UX Theme — Operational Trust

The visual system must communicate:

```text
trust
monitoring
evidence
uncertainty
human control
auditability
```

AI must be visible but visually subordinate to operational state.

---

# 11.1 Theme strategy

Implement semantic tokens, not literal page colors.

Token groups:

```text
SURFACE
canvas
surface-primary
surface-secondary
surface-elevated
border-subtle
border-strong

TEXT
text-primary
text-secondary
text-muted
text-inverse

BRAND
trust-primary
trust-primary-hover
trust-secondary

STATUS
status-info
status-success
status-warning
status-critical

AI
ai-assist
ai-assist-subtle

DATA LAYERS
layer-l1
layer-l2
layer-l3
layer-l4

PROVENANCE
provenance-real
provenance-public
provenance-semi-synthetic
provenance-synthetic
```

Both light and dark themes map these semantic tokens independently.

Do not place raw hex values inside feature components.

---

# 11.2 Visual character

## Light theme

Designed to work well on classroom projectors:

- neutral/white canvas;
- graphite primary text;
- subtle borders;
- calm blue trust accent;
- restrained status colors;
- no translucent glass panels;
- no low-contrast gray-on-gray text.

## Dark theme

Designed for sustained analytical work:

- graphite/navy surfaces;
- no pure-black page;
- calm blue primary actions;
- restrained violet AI accent;
- semantic status colors maintain contrast.

---

# 11.3 L1-L4 color system

Use four stable categorical colors.

Rules:

1. Every layer also has a visible `L1`, `L2`, `L3`, or `L4` badge/icon.
2. Layer color never means severity.
3. Criticality is encoded separately.
4. Charts must remain interpretable without color.
5. Tooltip/legend includes layer name and detector type.

Example semantic display:

```text
[L3] Relationship anomaly       [HIGH]
```

not:

```text
purple = severe
```

---

# 11.4 AI visual language

Remove agent-specific “personality colors” from core architecture.

Do not assign:

```text
planner = purple
validator = orange
specialist = green
```

Use one restrained `ai-assist` token.

AI activity UI should emphasize:

```text
action
evidence used
result
uncertainty
```

not a theatrical “thinking pulse.”

---

# 12. Information Architecture

Primary navigation:

```text
Overview
Reliability
Incidents
Controls
Audit
Evaluation
```

Optional:

```text
Data / Settings
```

The assistant is persistent context, not a primary route.

---

# 12.1 Executive Dashboard — remains major

The user explicitly wants the dashboard to remain important.

Its purpose is not decoration.

It answers:

1. Is the project reliable right now?
2. What changed?
3. What requires human action?
4. Which incidents are getting worse?
5. Is the system reducing noise?
6. Which metrics are measured vs demo/synthetic?

Recommended sections:

```text
PROJECT HEALTH
- open incidents
- critical incidents
- affected entities
- last successful monitoring run

SIGNAL TREND
- L1-L4 over time

INCIDENT STATUS
- new
- investigating
- awaiting review
- resolved

ATTENTION REQUIRED
- ranked real incidents

RELIABILITY TREND
- measured time series

PROVENANCE NOTICE
- real/proxy/semi-synthetic coverage
```

Do not show:
- fabricated “98.6% RCA accuracy”;
- fabricated MTTR;
- fabricated cost savings.

Research metrics belong in Evaluation unless measured.

---

# 12.2 Project Reliability Control Room

Because the datasets operate together in one project, do not force the user to select isolated datasets as if they were unrelated products.

Display:

```text
Project
├── Fleet entities
├── Charging network
├── Telemetry
├── Trips
├── Data contracts
└── Monitoring runs
```

Key views:

- entity reliability table;
- L1-L4 timeline;
- relationship chart;
- station/VIN filter;
- monitoring status;
- recent incidents.

---

# 12.3 Incident Workspace

This is the deepest operational screen.

Desktop layout:

```text
┌────────────────────────────────────────────────────────────┐
│ Incident header / status / severity / affected entities    │
├────────────────────────────┬───────────────────────────────┤
│ Main investigation area    │ Contextual Assistant          │
│                            │                               │
│ Timeline                   │ scoped to incident            │
│ Evidence                   │                               │
│ Hypotheses                 │                               │
│ Recommendations            │                               │
├────────────────────────────┴───────────────────────────────┤
│ Decision / Audit                                              │
└────────────────────────────────────────────────────────────┘
```

Assistant panel must be collapsible.

---

# 13. Responsive Targets

Equal-quality desktop targets:

- 1920×1080;
- common 1440p laptop layouts.

Do not optimize for mobile during this feature cycle.

Recommended layout rules:

- max readable content width for text panels;
- fluid analytical canvas;
- collapsible assistant;
- responsive two-column → one-column degradation at narrower desktop widths;
- no horizontal scrolling for primary workflow;
- charts resize without hiding labels.

Test at minimum:

```text
1920×1080
1536×864
1440×900 or equivalent
```

---

# 14. Bilingual UX

Vietnamese is default.

Implement a centralized locale layer.

Do not hard-code translated strings in feature components.

Terminology examples:

```text
Reliability Overview
→ Tổng quan độ tin cậy

Incident
→ Sự cố

Evidence
→ Bằng chứng

Hypothesis
→ Giả thuyết

Contradicting Evidence
→ Bằng chứng phản biện

Preventive Control
→ Kiểm soát phòng ngừa

Operational Recommendation
→ Khuyến nghị vận hành
```

Keep established acronyms where useful:

- RCA;
- L1-L4;
- VIN;
- BMS;
- HITL.

---

# 15. Charting

A dedicated chart library is allowed.

Selection criteria:

- React compatibility;
- line/scatter/timeline support;
- annotation support;
- accessible labels/tooltips;
- responsive sizing;
- theme token integration;
- reasonable bundle size;
- active maintenance.

Required chart patterns:

1. L1-L4 event timeline;
2. entity metric trend + baseline;
3. L3 relationship scatter + expected relationship/residual;
4. L4 before/after change view;
5. project incident trend;
6. evaluation comparison.

Do not implement decorative 3D/pie charts.

Every chart requires:
- title with conclusion-oriented wording;
- units;
- legend where needed;
- empty state;
- loading state;
- data provenance or source context;
- accessible table/download where practical.

---

# 16. Frontend Migration Rules

Current hard-coded frontend data must be removed from normal operation.

Examples of prohibited production/default behavior:

- seeded incident appears on fresh system;
- fixed 30 VIN displayed regardless of API;
- fixed evidence strings;
- fake activity feed;
- fake RCA confidence;
- fixed anomaly counts.

Create an explicit command:

```text
seed-demo-data
```

or equivalent.

Demo state must be visibly labeled.

Fresh system state:

```text
No monitoring results yet
```

is correct.

---

# 17. Backend/API Consolidation

Canonical API namespace:

```text
/api/v1
```

Suggested resources:

```text
/projects
/projects/{id}/summary
/signals
/incidents
/incidents/{id}
/incidents/{id}/evidence
/incidents/{id}/investigate
/incidents/{id}/hypotheses
/incidents/{id}/decisions
/incidents/{id}/recommendations
/controls
/authorizations
/audit
/evaluation
```

Do not create parallel v5 endpoints if equivalent functionality already exists under v1.

Migrate internally, then deprecate duplicates.

---

# 18. Persistence

Replace global/in-memory authoritative stores.

Persist:

- Signals;
- Incidents;
- Evidence;
- Hypotheses;
- Decisions;
- Recommendations;
- Controls;
- Authorizations;
- Agent runs;
- Evaluation runs.

Browser state is a projection only.

Order of authority:

```text
Database
>
append-only evidence/audit
>
API
>
WebSocket
>
browser state
```

---

# 19. WebSocket Model

Every connection must resolve:

```text
user_id
tenant/project_id
session/incident scope
```

Broadcast topics:

```text
project:{project_id}
incident:{incident_id}
user:{user_id}
```

Never globally broadcast evidence or chat messages.

---

# 20. Repository Cleanup

After canonical paths work:

Remove/deprecate:

- obsolete duplicate ReAct engines;
- simulated benchmark winner logic;
- duplicate approval/HITL paths;
- static dashboard mock data;
- old UI build path if unused;
- redundant API aliases;
- stale v4 architecture docs;
- misleading old agent descriptions.

Do not clean these before tests cover the replacement path.

---

# 21. Implementation Waves

---

# Wave 0 — Truth Reset
## Deadline: 11-12 Aug

### Tasks

- update VERSION to v5 development state;
- replace root PLAN with this plan;
- mark old benchmark results invalid/simulated;
- remove fake metrics from default UI;
- rotate exposed-looking keys;
- lock provenance definitions;
- create architecture decision record for v5.

### Exit criteria

No demo or report can accidentally present fabricated performance as measured evidence.

---

# Wave 1 — Statistical Correctness
## Deadline: 12-15 Aug

### L2

- strict prior-history baseline;
- 14-day warm-up;
- MAD/robust Z;
- leakage test;
- entity-specific scoring.

### L3

- reference/evaluation separation;
- entity/class/global scope;
- interpretable residual;
- Isolation Forest comparator only.

### L4

- CUSUM;
- PELT;
- persistence;
- change timing;
- pre/post summary.

### Exit criteria

Each layer has:
- unit tests;
- positive cases;
- negative cases;
- no temporal leakage;
- measured detector results.

---

# Wave 2 — Causal Corpus + Fusion
## Deadline: 15-18 Aug

### Data

- versioned 60-day digital twin;
- 30 VIN / 4 stations target;
- shared causal scenario IDs;
- provenance;
- generator seed;
- 30/90-day slices optional.

### Fusion

- typed signal normalization;
- project/entity/time grouping;
- deterministic admission policies;
- calibration experiment;
- duplicate suppression.

### Exit criteria

A known latent scenario reproducibly generates L1-L4 signals and one correctly linked Incident.

---

# Wave 3 — Persistent Incident Model
## Deadline: 17-19 Aug

Implement:

- persistent Incident;
- Evidence;
- Hypothesis;
- Recommendation;
- Decision;
- audit links;
- incident-specific retrieval;
- cross-incident isolation tests.

### Exit criteria

Restarting backend does not destroy incident state.

---

# Wave 4 — Strong C1
## Deadline: 19-20 Aug

Implement:

- deterministic context builder;
- fixed evidence retrieval;
- one structured LLM analysis;
- schema validation;
- evidence-ID checking;
- contradiction extraction;
- abstention;
- typed recommendation.

### Exit criteria

C1 provides a credible baseline that is not deliberately weakened.

---

# Wave 5 — Dynamic A1
## Deadline: 20-22 Aug

Implement:

- typed tool registry;
- observation-dependent tool selection;
- competing hypotheses;
- contradiction checks;
- dynamic time/entity scope;
- stop/continue/abstain;
- budgets;
- real trace instrumentation.

### Exit criteria

At least three benchmark cases produce materially different tool paths due to intermediate observations.

---

# Wave 6 — Governance + Security
## Deadline: 21-23 Aug

Unify:

- approval;
- control;
- sandbox;
- execution authorization.

Add:

- signed JWT;
- server role resolution;
- authenticated WS;
- scoped rooms;
- exact-version authorization;
- audit identity.

### Exit criteria

Security test demonstrates that an unapproved or modified control cannot execute.

---

# Wave 7 — Operational Trust UX
## Deadline: 20-24 Aug

Parallel frontend stream.

Implement:

1. semantic token system;
2. light/dark themes;
3. Vietnamese default i18n;
4. redesigned Executive Dashboard;
5. Project Reliability Control Room;
6. L1-L4 timeline;
7. Incident Workspace;
8. evidence/hypothesis panels;
9. contextual assistant;
10. HITL decision flow;
11. audit view;
12. measured Evaluation view.

Replace static data with APIs.

### Exit criteria

Data Steward completes full flow without knowing prompt syntax.

---

# Wave 8 — Blind Benchmark + Human Evaluation
## Deadline: 23-25 Aug

Run:

- L1-L4 detection benchmark;
- Fusion benchmark;
- R0/C1/A1 comparison;
- human evaluation subset;
- 30/60/90 sensitivity where useful;
- red-team cases.

Persist raw outputs.

Generate tables from artifacts, not constants.

---

# Wave 9 — Feature Lock
## 26 Aug

Allowed:

- P0 bug fixes;
- benchmark rerun;
- deployment fixes;
- accessibility fixes;
- documentation;
- demo-data freezing.

Not allowed after lock:

- new detector family;
- new agent role;
- new data source;
- new workspace;
- new major schema;
- A2 becoming a dependency.

---

# 22. Red-Team Matrix

Required test cases:

### Data/statistics
- insufficient L2 history;
- sparse VIN;
- extreme future values do not alter past score;
- unrelated entity does not alter per-entity baseline;
- L3 relationship breaks while all individual features remain valid;
- temporary L4 spike does not become persistent change.

### Fusion
- duplicate signals;
- contradictory detectors;
- one noisy detector;
- critical L1;
- multi-layer agreement.

### Investigation
- ambiguous entity;
- insufficient evidence;
- conflicting evidence;
- misleading complaint;
- irrelevant telemetry;
- no valid RCA.

### Agent
- unnecessary tool loop;
- tool failure;
- LLM failure;
- hallucinated evidence ID;
- unsupported hypothesis;
- budget exhaustion.

### Governance
- edited rule after approval;
- expired authorization;
- wrong snapshot;
- wrong project;
- unauthorized actor;
- direct execution payload tampering.

### Security
- spoofed role;
- invalid JWT;
- WebSocket cross-project subscription;
- cross-incident evidence access.

---

# 23. Definition of Done

v5 is done only when all of the following are true.

## Product

- primary workflow is monitor → incident → investigate → decide → act → audit;
- Data Steward can use product without prompt knowledge;
- chat is contextual.

## Detection

- L1-L4 have distinct semantics;
- L2 has no look-ahead leakage;
- L3 uses held reference relationship;
- L4 produces change time and before/after evidence.

## Fusion

- incident admission is explainable;
- duplicate/noisy signals are controlled;
- signal reduction is measured.

## Investigation

- R0/C1/A1 use equivalent evidence;
- C1 is a valid strong baseline;
- A1 chooses tools dynamically;
- agent may lose.

## Evidence

- all claims reference retrievable evidence;
- contradictions are visible;
- cross-incident leakage tests pass.

## Data

- provenance is explicit;
- digital twin causality is generated, not narrated afterward.

## Governance

- no AI path can directly mutate production state;
- exact approved version is required;
- execution uses authorization;
- audit is durable.

## UX

- light/dark;
- Vietnamese default;
- 1080p/1440p usable;
- Executive Dashboard uses measured data;
- L1-L4 colors include labels/icons;
- no fake KPIs.

## Research

- benchmark uses hidden ground truth;
- no result constants;
- raw case-level predictions saved;
- detector/Fusion/RCA metrics generated reproducibly.

---

# 24. Coding-Agent Protocol

Use this block as the default instruction for coding agents.

```text
You are implementing DataTrust OS v5.

Before coding:
1. Read PLAN_V5_FINAL.md.
2. Inspect existing modules for equivalent functionality.
3. Do not create a parallel architecture when one can be migrated.
4. Identify the exact invariant/metric this change satisfies.

Rules:
- No fake metrics.
- No hard-coded benchmark wins.
- No ground-truth leakage into investigated systems.
- No temporal leakage.
- No unauthenticated execution.
- No client-declared authority.
- No agent mutation.
- No unscoped evidence retrieval.
- No silent production mock fallback.
- Preserve provenance.
- Persist authoritative state.
- Add positive, negative, and failure tests.

When complete, report:
- files changed;
- architecture affected;
- tests added;
- command/output summary;
- measured result;
- assumptions;
- unresolved risk;
- next dependency.

Do not claim completion if tests or measurement were not run.
```

---

# 25. Team Ownership

| Member | Primary accountability |
|---|---|
| **Phạm Quốc Thanh** | Product decisions, benchmark validity, causal corpus, experiment design, decision log, report |
| **Tạ Kim Ngân** | L2/L3/L4 methodology, Fusion calibration, investigation quality, A1/A2 error analysis |
| **Trần Tiến Dũng** | Data plane, detector runtime, persistence, API, security, governance, deterministic execution |
| **Vũ Thu Huyền** | Operational Trust UX, bilingual UI, Incident Workspace, HITL UX, integration, deployment/demo |

Coding agents accelerate implementation, but humans own experimental claims and merge approval.

---

# 26. Demo Story

The main demo should be deterministic enough to rehearse but use actual computed results.

```text
1. Open Executive Dashboard
   → project has a measurable reliability shift

2. Open Project Reliability Control Room
   → see L1-L4 signals over the same project context

3. Select a VIN/incident
   → individual values appear mostly valid
   → L2/L3/L4 reveal deeper behavior

4. Fusion creates Incident
   → admission reason is visible

5. Open Incident Workspace
   → evidence + contradictory evidence

6. Run investigation
   → show C1 or A1
   → A1 gathers additional evidence only if needed

7. Human reviews hypothesis

8. If DATA cause
   → preventive control
   → sandbox
   → approval
   → authorization

   OR

   If OPERATIONAL cause
   → operational recommendation

9. Open Audit
   → show complete trace

10. Evaluation
   → show measured R0/C1/A1 results
   → explicitly state whether agent won or lost
```

The presentation should never depend on “look, we have multiple agents.”

The strongest message is:

> **We deliberately use different technical mechanisms for different kinds of uncertainty and empirically test when autonomy is worth its complexity.**

---

# 27. External UX Design Evidence Used for v5

The theme direction is informed by current official design-system guidance:

- **IBM Carbon Design System** — dashboard guidance emphasizes reducing distraction and assigning colors consistently; its theme system supports tokenized light/dark themes.
- **Atlassian Design System** — recommends semantic design tokens and predefined categorical chart colors for consistency/accessibility.
- **GOV.UK / Government Analysis Function** — emphasizes user-centered dashboard design, accessible visualizations, and not relying on color alone to communicate information.

These references support the implementation choice to use:
- semantic tokens;
- light/dark mappings;
- stable categorical L1-L4 chart colors;
- status color separate from data-series color;
- strong hierarchy and low decorative noise;
- accessible labels in addition to color.

---

# 28. Final Architecture

```text
                     ┌────────────────────────────┐
                     │        DATA STEWARD        │
                     └──────────────┬─────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │      OPERATIONAL TRUST UX      │
                    │                                │
                    │ Executive Dashboard            │
                    │ Project Reliability            │
                    │ Incident Workspace             │
                    │ Contextual Assistant           │
                    │ Controls / Audit / Evaluation  │
                    └───────────────┬────────────────┘
                                    │
                   Authenticated API / Scoped WebSocket
                                    │
                    ┌───────────────▼────────────────┐
                    │     RELIABILITY DATA PLANE     │
                    │                                │
                    │ L1 constraints                 │
                    │ L2 contextual                  │
                    │ L3 relational                  │
                    │ L4 change point                │
                    └───────────────┬────────────────┘
                                    │
                          Typed Signals + Evidence
                                    │
                    ┌───────────────▼────────────────┐
                    │            FUSION              │
                    │ grouping / admission / dedupe  │
                    └───────────────┬────────────────┘
                                    │
                                 Incident
                                    │
              ┌─────────────────────▼─────────────────────┐
              │               INVESTIGATION               │
              │                                           │
              │ R0 deterministic                           │
              │     ↓ unresolved                           │
              │ C1 fixed AI workflow                       │
              │     ↓ agent-worthy                         │
              │ A1 bounded dynamic investigation           │
              │                                           │
              │ A2 only if experimentally admitted         │
              └─────────────────────┬─────────────────────┘
                                    │
                       Evidence-backed hypothesis
                                    │
                         ┌──────────▼──────────┐
                         │       HITL          │
                         └───────┬───────┬─────┘
                                 │       │
                       DATA CAUSE│       │OPERATIONAL CAUSE
                                 │       │
                ┌────────────────▼─┐   ┌─▼─────────────────┐
                │ Preventive       │   │ Operational       │
                │ Data Control     │   │ Recommendation    │
                └────────┬─────────┘   └─────────┬─────────┘
                         │                       │
                  compile/sandbox               │
                  authorization                 │
                         │                       │
                    deterministic               │
                     execution                  │
                         └───────────┬───────────┘
                                     │
                              Immutable Audit
```

---

# 29. Final Research Thesis

The project should be evaluated around this falsifiable thesis:

> **Simple rules are sufficient for explicit point violations, but entity-relative, relational, and sequential anomalies require richer statistical context. Once such signals form an incident, bounded agentic investigation is useful only when the next evidence-gathering action cannot be fixed in advance and when the resulting improvement in RCA/evidence quality or human effort outweighs added cost and complexity.**

The project succeeds if it proves this thesis **or disproves the agentic part honestly** while still delivering a useful reliability system.

That is the v5 product and engineering definition through feature lock.
