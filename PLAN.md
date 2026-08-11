# DataTrust OS — PLAN.md
## Team-Aligned Multi-Layer Data Reliability, Incident Fusion, and Conditional Agentic Investigation

> **Status:** TEAM-ALIGNED IMPLEMENTATION PLAN  
> **Prepared:** 2026-08-11  
> **Program:** DATA-02 — AI Agent for Data Quality, anomaly detection, and governed investigation  
> **Current product baseline:** v4.2.x repository  
> **Feature lock:** 2026-08-26 23:59 (Asia/Ho_Chi_Minh)  
> **Post-lock:** stabilization, benchmark reruns, deployment, documentation, and demo rehearsal only  
> **Core principle:** Solve the reliability problem at the cheapest sufficient layer. AI/agents are conditional escalation mechanisms, not the product thesis.

---

# 0. Team Decision Reconciliation

This plan replaces the previous “recommended direction” section with actual team responses.

## 0.1 Decision matrix

| # | Question | Ngân | Dũng | Thanh | Huyền | Team status | Final decision |
|---|---|---|---|---|---|---|---|
| 1 | Data error vs operational anomaly | C | C | C | C | **Unanimous** | Detect an anomalous signal first; do not call it a data error until classification/RCA |
| 2 | Primary user | Data Steward | Data Steward | Dual persona, Data Steward primary | Data Engineer + Data Steward | **Strong convergence** | **Primary: Data Steward / Data Quality Manager. Secondary: Data Engineer / Analytics Engineer** |
| 3 | L2-L4 output | RCA + recommendation | RCA + recommendation | RCA + operational recommendation | RCA + preventive DQ rule + operational recommendation | **Shared core, different depth** | Always produce evidence-backed RCA hypothesis + recommendation; preventive control is conditional on cause type |
| 4 | Product pillars | Implied two-lane direction | Keep both; Monitoring/RCA primary | Keep both | Keep both; Monitoring/RCA primary | **Consensus on both pillars** | Keep both; **Monitoring/RCA is the hero recurring workflow**, rule governance is supporting/preventive capability |
| 5 | Cross-source linkage | IDs can be constructed; original sources independent | Not truly linked | See repo/README | Partial/unclear | **Important factual disagreement** | Treat original sources as **independent proxies**; any linkage is **semi-synthetic/digital-twin linkage**, never “real causal linkage” |
| 6 | Causal digital twin | Yes | Yes | Yes | No explicit objection | **Consensus among explicit responses** | Yes; use for research/evaluation/demo with provenance labels |
| 7 | History horizon | 30d preferred; reduce VIN if longer | 60d, ~20 VIN, 4 stations | 30/60/90 | ~1 month indicated | **Different preferences** | Canonical benchmark: **60 days, 30 VIN, 4 stations**, 14-day warm-up; 30/90-day sensitivity runs |
| 8 | L1 SLA / L2-L4 cadence | <1s / daily | <1s / configurable | <1s | No full answer | **L1 consensus; cadence differs** | L1 p95 <1s target; L2-L4 **configurable, daily by default** |
| 9 | Agent boundary | Agree | Agree | Agree | No explicit objection | **Strong consensus** | Detection L1-L4 = deterministic/stat/ML; Fusion = calibrated; RCA = C1/A1; execution = deterministic |
| 10 | A2 multi-agent | No explicit requirement | Conditional only | Build A2 | No explicit answer | **Real disagreement** | **A2 is optional experimental work only after A1 error analysis**; never critical-path or default product architecture |
| 11 | Main UX | Contextual assistant | Contextual assistant | Chat-first | No explicit answer | **Real disagreement** | **Workflow-first Incident Workspace; chat is persistent contextual assistant** |
| 12 | Deadline | — | — | Feature lock 26/08 | — | **Consistent with project governance** | Feature lock 26 Aug; stabilization after lock |

---

# 0.2 Why these conflict resolutions are chosen

## Conflict A — Primary user

### Final choice
**Primary:** Data Steward / Data Quality Manager  
**Secondary:** Data Engineer / Analytics Engineer  
**Downstream consumer:** Reliability / Operations / Maintenance

### Rationale

The project remains DATA-02. The user who owns data quality policy, anomaly triage, exception review, and evidence-based approval must be the primary workflow owner.

A Data Engineer is still important, but should not have to live inside every incident. Reliability/Operations becomes relevant when an incident is classified as operational rather than data-related.

This creates a clean responsibility boundary:

```text
DataTrust OS detects and investigates
        ↓
Data Steward owns trust / classification / governance
        ↓
Data Engineer fixes data-system causes
Reliability/Operations acts on real-world operational causes
```

---

## Conflict B — What happens after RCA?

The team agrees on the shared minimum:

> **RCA hypothesis + recommendation**

The disagreement is whether every incident should then create a DQ rule or operational recommendation.

### Final product behavior

```text
Incident
→ evidence-backed RCA hypothesis
→ classify likely cause

IF DATA / PIPELINE / CONTRACT cause:
    → preventive Data Quality control proposal
    → compiler/sandbox/HITL

IF OPERATIONAL / ASSET cause:
    → maintenance / operational recommendation
    → no fake DQ rule

IF INSUFFICIENT EVIDENCE:
    → request context / abstain
```

### Why

Generating a data rule for a battery that is genuinely degrading is conceptually wrong. Likewise, recommending maintenance for a schema mismatch is wrong.

The system must not force all problems into one action type.

---

## Conflict C — Are the datasets actually linked?

### Final factual position

The source datasets are **not naturally causally linked**. They originate independently.

Some current IDs/time-series relationships are constructed for research purposes.

Therefore:

```text
Public/independent source data
        +
Causal scenario generator
        +
Shared synthetic entity/time keys
        =
SEMI-SYNTHETIC CAUSAL DIGITAL TWIN
```

This must be stated in:

- Data Card;
- evaluation report;
- benchmark metadata;
- demo narration;
- research limitations.

Do not claim “real VinFast/V-GREEN/Xanh SM linked operational data” unless the team later receives genuinely linked data.

---

## Conflict D — 30 vs 60 vs 90 days

### Final benchmark design

**Primary corpus**
- 60 days;
- 30 VIN;
- 4 stations;
- 14-day warm-up period before scored contextual detection;
- enough trip density per VIN to avoid sparse per-entity baselines.

**Sensitivity slices**
- 30-day reduced-history slice;
- 90-day long-history slice if generator/data density supports it.

### Why 60 days

30 days is enough for an MVP but weak for:
- stable rolling baselines;
- gradual drift;
- pre/post change-point windows;
- false-positive analysis.

90 days is useful but increases generated data without automatically increasing evidence quality.

60 days is the best primary compromise between:
- statistical history;
- density per entity;
- benchmark size;
- explainability.

If data density becomes sparse, **reduce entity count before fabricating more unrelated records**.

---

## Conflict E — Should A2 be built?

### Final decision

A2 is **not a required product milestone and not a required benchmark baseline**.

It may be built as an isolated experiment only if A1 shows a measurable failure mode.

Examples that can justify A2:

1. A1 regularly reaches unsupported conclusions and an independent verifier materially reduces them.
2. Sequential investigation is too slow but independent hypotheses can be evaluated in parallel.
3. A specialist domain critic materially improves one difficult benchmark slice.
4. A planner materially reduces unnecessary tool calls.

Admission rule:

```text
Observed A1 failure
+ pre-registered A2 intervention
+ measurable expected benefit
→ permit A2 experiment
```

Not:

```text
"We have coding capacity"
→ build more agents
```

This preserves Thanh's ambition to test A2 while preventing multi-agent architecture from contaminating the critical path.

---

## Conflict F — Chat-first or workflow-first UX?

### Final choice
**Workflow-first. Chat remains a persistent contextual assistant.**

### Why

The primary user is a Data Steward. Their work is stateful and governed:

- which incident?
- which signals?
- which evidence?
- which hypothesis?
- who approved?
- what changed?
- what was executed?

A blank chat is poor at representing durable operational state.

The assistant remains powerful:

```text
Incident Workspace
├── Evidence
├── Hypotheses
├── Timeline
├── Controls
├── Audit
└── Contextual Assistant
```

Chat may:
- explain the current incident;
- summarize evidence;
- request a deeper investigation;
- navigate;
- compare hypotheses;
- generate a draft control.

Chat may not:
- become the system of record;
- approve consequential actions by text alone;
- hide workflow state;
- directly authorize execution.

---

# 1. Final Product Thesis

DataTrust OS is no longer framed as:

> “An AI agent that generates data-quality rules.”

The team-aligned product thesis is:

> **DataTrust OS is a data reliability control plane that detects abnormal signals at four technical layers, fuses them into evidence-backed incidents, and conditionally escalates to AI investigation when the cause cannot be resolved by deterministic methods. Human reviewers remain the authority for consequential decisions; deterministic code performs every governed execution.**

The product answers three different questions with three different technical systems:

```text
1. WHAT IS WRONG?
   → L1/L2/L3/L4 detection

2. DOES IT MATTER ENOUGH TO INVESTIGATE?
   → Fusion + incident admission

3. WHY DID IT HAPPEN?
   → R0 / C1 / A1 investigation
```

This separation is mandatory.

---

# 2. Product Pillars

## Pillar A — Data Contract & Quality Governance

Purpose:
- define known invariants;
- profile incoming data;
- govern source-to-target assumptions;
- compile reviewed controls;
- quarantine invalid data;
- preserve evidence and audit.

Core flow:

```text
Source
→ Snapshot
→ Profile
→ Rule / Contract Proposal
→ Review
→ Compile
→ Sandbox
→ Authorization
→ Deterministic Execute
→ Audit
```

This pillar remains part of the product but is not the primary differentiation.

---

## Pillar B — Continuous Reliability Monitoring

This becomes the hero recurring workflow.

```text
Project data streams / history
→ L1 Point Detection
→ L2 Contextual Detection
→ L3 Relational Detection
→ L4 Change-Point Detection
→ Fusion
→ Incident
→ Conditional Investigation
→ HITL
→ Data Control OR Operational Recommendation
→ Audit
```

The multiple datasets belong to **one project context**, not separate unrelated UX silos.

The UX should present a coherent fleet/project reliability model.

---

# 3. Signal Semantics

The system must use explicit semantics:

## 3.1 Confirmed violation

A known invariant has been violated.

Example:
```text
battery_soc = -4
```

Status:
`CONFIRMED_DATA_VIOLATION`

---

## 3.2 Suspicious signal

The observation is legal but abnormal.

Example:
```text
VIN-023 discharge rate is still globally valid
but is +4.1 MAD relative to its own baseline.
```

Status:
`SUSPICIOUS_SIGNAL`

It is not yet a data error.

---

## 3.3 Incident

One or more signals are important enough to require investigation.

Status:
`OPEN_INCIDENT`

---

## 3.4 Hypothesis

A possible cause supported by evidence.

Status:
`HYPOTHESIS`

Never present a hypothesis as a confirmed cause unless sufficient ground truth/evidence exists.

---

# 4. Four-Layer Detection Architecture

# 4.1 L1 — Point / Constraint Detection

### Purpose
Catch known invalid states.

### Methods
- schema/type validation;
- range constraints;
- nullability;
- referential rules;
- arithmetic/business invariants;
- safety thresholds.

### AI requirement
None.

### Runtime
Fast path.

### Target SLA
**p95 <1 second** from event receipt to persisted critical signal in the benchmark/demo environment.

Important:
- measure this end-to-end;
- do not claim production-scale SLA based only on function runtime.

### Output
Typed `Signal`.

---

# 4.2 L2 — Contextual / Entity-Relative Detection

### Purpose

Detect observations that are valid globally but abnormal relative to the same entity.

### Required dimensions
- `entity_id`;
- timestamp;
- metric;
- historical window;
- sufficient observations.

### First implementation

Prefer robust and interpretable detectors:

1. rolling median + MAD;
2. robust rolling Z-score;
3. EWMA;
4. STL residual only for metrics with demonstrated seasonality.

Do not start with deep models.

### Example

```text
Fleet valid discharge range: 5–20
VIN-023:
D1–D14 median = 8.1
D15–D30 rises gradually to 14.8

No point violates fleet range.
Entity-relative behavior is abnormal.
```

### Cold start

The detector must return:

```text
INSUFFICIENT_HISTORY
```

rather than scoring entities without a valid baseline.

---

# 4.3 L3 — Collective / Relational Detection

### Purpose

Detect broken relationships where individual variables remain valid.

### Example

```text
charging_frequency ↑
trip_count ↓
energy_consumption ↑
```

Each feature may individually remain valid.

### Modeling priority

1. domain-defined expected relationship;
2. interpretable regression residual;
3. robust covariance / Mahalanobis if assumptions hold;
4. Isolation Forest / LOF as comparator;
5. more complex models only after benchmark evidence.

### Why

For the product, this:

```text
Expected trips = 18
Observed trips = 8
Residual = -10
```

is more actionable than:

```text
IsolationForest anomaly score = -0.41
```

Use black-box scores only when they add measurable detection value.

---

# 4.4 L4 — Sequential / Change-Point Detection

### Purpose

Detect a persistent change in behavioral regime.

### Candidate methods

- CUSUM;
- PELT (`ruptures`);
- Bayesian online change-point only if required.

### Example

```text
Days 1–35:
~1 charging session/day

From day 36:
~3 charging sessions/day continuously
```

Each day may still be valid individually.

### Required outputs

- detected change time;
- pre-period summary;
- post-period summary;
- magnitude;
- persistence;
- detector confidence/evidence.

---

# 5. Runtime Architecture: Fast and Slow Paths

## 5.1 Fast path

For L1 only.

```text
Incoming record/event
→ validate known invariants
→ persist violation
→ critical?
→ immediate alert
```

Properties:
- deterministic;
- no LLM;
- minimal state;
- <1s target.

---

## 5.2 Slow intelligence path

Default **daily**, configurable per project/detector.

```text
Historical data
→ entity feature builder
→ L2
→ L3
→ L4
→ normalize signals
→ Fusion
→ Incident admission
```

Why default daily:
- group preference includes daily and configurable;
- L2-L4 require historical context;
- investigation/maintenance is not usually a millisecond decision;
- reduces unnecessary compute.

Configuration must support:
- hourly;
- 6-hourly;
- daily;
- manual;
- cron.

---

# 6. Fusion Layer

Fusion converts signals into incidents.

It must initially be deterministic and explainable.

## 6.1 Inputs

- L1 signals;
- L2 signals;
- L3 signals;
- L4 signals;
- entity metadata;
- time overlap;
- criticality;
- optional change/deployment context.

## 6.2 Grouping keys

At minimum:

```text
project_id
entity_id / related_entity_ids
time_window
metric / relationship
```

## 6.3 Fusion factors

Start with calibrated configurable factors:

- severity;
- detector strength;
- persistence;
- multi-layer agreement;
- evidence quality;
- entity/business criticality;
- recency.

Do not pretend one arbitrary weighted formula is scientifically final.

## 6.4 Fusion output

```yaml
incident_candidate_id:
project_id:
entities:
time_window:
signals:
supporting_layers:
conflicting_signals:
severity:
fusion_score:
evidence_refs:
admission_reason:
```

---

# 7. Incident Admission

Create an Incident when any configured policy holds:

1. critical L1 signal;
2. persistent L2 anomaly;
3. high-confidence L3 relationship break;
4. persistent L4 regime shift;
5. agreement across >=2 layers;
6. repeated signals across related entities;
7. manual promotion by user.

Every admission must store **why** the incident exists.

---

# 8. Incident Investigation

Agent intelligence begins only here.

## 8.1 R0 — deterministic investigation

Resolve with:
- lookup;
- known rule;
- fixed diagnostic mapping;
- known ownership/action.

If R0 resolves the incident, stop.

---

## 8.2 C1 — fixed AI workflow

Use when semantics are useful but investigation structure is predetermined.

Example:

```text
Incident facts
→ fetch relevant profile
→ fetch recent changes
→ summarize evidence
→ one structured LLM analysis
→ validate
→ human review
```

C1 is the strongest baseline.

---

## 8.3 A1 — bounded dynamic investigator

A1 is justified only when next actions cannot be fully known in advance.

Capabilities:
- choose typed tools dynamically;
- change entity/time scope;
- retrieve additional evidence;
- maintain multiple hypotheses;
- gather supporting and contradictory evidence;
- stop/continue;
- request context;
- abstain.

Bounds:
- max tool calls;
- max hypothesis revisions;
- token budget;
- wall-clock timeout;
- tool allowlist;
- evidence references required;
- no mutation.

---

## 8.4 A2 — optional experimental multi-agent

Do not put A2 in the required implementation dependency graph.

Possible architecture:

```text
Planner
→ parallel hypothesis investigators
→ independent verifier
```

But only implement after an A1 benchmark report states:

```yaml
failure_mode:
frequency:
business_impact:
proposed_A2_component:
expected_metric_improvement:
extra_cost_budget:
```

A2 is allowed before feature lock only if it does not block R0/C1/A1, UX, security, or benchmark completion.

---

# 9. Investigation Output Contract

Every qualified investigation returns:

```yaml
incident_id:
classification:
  data_quality_probability:
  operational_probability:
  unresolved_probability:

confirmed_facts:
supporting_evidence:
contradicting_evidence:

hypotheses:
  - hypothesis:
    confidence:
    evidence_refs:
    counter_evidence_refs:
    missing_evidence:

recommended_action:
abstention_reason:
```

No free-form “root cause” sentence without evidence IDs.

---

# 10. Conditional Outcome Policy

## Data/system cause

Examples:
- schema drift;
- unit mismatch;
- invalid transformation;
- ingestion lag;
- broken referential mapping.

Output:
```text
RCA
→ Preventive Data Quality Control
→ compile
→ sandbox
→ HITL
→ activation
```

## Operational cause

Examples:
- battery degradation;
- charging hardware issue;
- unusual fleet usage pattern.

Output:
```text
RCA
→ operational / maintenance recommendation
→ human routing
```

Do not generate a fake DQ rule merely to demonstrate rule generation.

## Unknown cause

```text
RCA inconclusive
→ abstain
→ specify missing evidence
```

---

# 11. Data Strategy

## 11.1 Provenance is mandatory

Use:

```text
REAL_OPERATIONAL
PUBLIC_PROXY
SEMI_SYNTHETIC
SYNTHETIC
```

for every source/case.

## 11.2 Current truth

The project's underlying sources are independent.

Shared vehicle/station/time relationships used for joint evaluation are constructed.

Therefore the integrated research corpus must be labeled:

> **SEMI_SYNTHETIC CAUSAL DIGITAL TWIN**

## 11.3 Digital twin generation principle

Generate the latent event first.

Example:

```text
LATENT CAUSE:
battery degradation begins at D35
        ↓
discharge trend increases
charging frequency rises
trip efficiency falls
thermal risk rises
optional complaint appears
```

Do not independently inject random anomalies and later invent an RCA story.

Causality must be encoded at generation time.

---

# 12. Benchmark Corpus

## 12.1 Primary corpus

Target:
- 60-day timeline;
- 30 VIN;
- 4 charging stations;
- coherent trips/charging/telemetry;
- 14-day warm-up;
- fixed random seed;
- versioned generator.

Use fewer entities if necessary to preserve per-entity density.

## 12.2 Sensitivity sets

If time permits:

- 30-day corpus;
- 90-day corpus.

Purpose:
- test detector sensitivity to history length;
- not inflate headline numbers.

---

# 13. Fault and Incident Families

The current benchmark over-represents L1 faults.

The new benchmark must contain balanced slices.

## L1
- negative value;
- null;
- invalid type;
- arithmetic mismatch;
- referential failure;
- hard safety threshold.

## L2
- gradual per-entity drift;
- abnormal relative level;
- entity-specific variance increase;
- recovery/transient vs persistent drift;
- cold-start negative cases.

## L3
- charging vs trip relationship break;
- energy use vs distance residual;
- fare vs trip relation break;
- station utilization vs sessions mismatch.

Crucially:
**each individual input remains valid in these cases.**

## L4
- persistent level shift;
- frequency regime shift;
- post-change variance shift;
- behavioral state transition.

## RCA cases
- data pipeline cause;
- data contract cause;
- operational asset cause;
- ambiguous case;
- conflicting evidence;
- insufficient evidence.

---

# 14. Benchmark Design — Research Integrity

The old self-fulfilling benchmark must be retired.

Never:
- give C1 `ground_truth_faults`;
- preassign which fault families a model is “allowed” to detect;
- derive human time from recall;
- fabricate token cost;
- fabricate latency;
- give A1 richer hidden context than C1.

All systems receive equivalent available evidence.

---

# 15. Evaluation Ladder

# 15.1 Detector evaluation

Per layer:

- precision;
- recall;
- F1;
- false positives/entity/day;
- detection delay;
- calibration where score exists.

For L4:
- change-point timing error.

For L3:
- residual-based ranking quality.

---

# 15.2 Fusion evaluation

Measure:
- incident precision;
- incident recall;
- alert reduction vs raw signals;
- missed critical incidents;
- duplicate incident rate.

Fusion must prove it improves signal-to-noise.

---

# 15.3 RCA evaluation

Measure:
- Top-1 cause accuracy;
- Top-3 cause recall;
- evidence precision;
- evidence recall;
- unsupported-claim rate;
- contradictory-evidence coverage;
- abstention precision/recall;
- human correction time.

---

# 15.4 Agentic comparison

Compare:
- R0;
- C1;
- A1.

A2 only if admitted.

### A1 value gate

Keep A1 only if all safety guardrails pass and it materially beats C1 on at least one high-value dimension.

Candidate gates:

- Top-1 RCA accuracy >= C1 + 10 percentage points; OR
- evidence recall >= C1 + 15 percentage points; OR
- median human correction time <= 75% of C1.

Guardrails:
- evidence precision >= 90%;
- unsupported claim rate <= 5%;
- zero unauthorized execution;
- bounded cost;
- bounded latency.

Do not force a winner.

---

# 16. Human Evaluation

At least two evaluators should review a blind subset.

Capture:
- task completion;
- time to decision;
- correction time;
- confidence in evidence;
- usability confusion points;
- false-positive burden.

Where possible, evaluator should not know whether the output came from C1 or A1.

---

# 17. UX Architecture

## 17.1 Primary hierarchy

```text
Reliability Portfolio
    ↓
Project Control Room
    ↓
Anomaly Timeline (L1-L4)
    ↓
Incident Workspace
    ↓
Evidence / Hypotheses / RCA
    ↓
HITL Decision
    ↓
Preventive Control OR Operational Recommendation
    ↓
Audit
```

Datasets within one project are not represented as isolated products if they jointly describe the same system.

---

## 17.2 Incident Workspace

Must show:

### Header
- incident ID;
- status;
- severity;
- affected entities;
- time window;
- owner.

### Timeline
- L1-L4 signals;
- incident admission point;
- related events.

### Evidence panel
- supporting evidence;
- contradicting evidence;
- provenance.

### Hypothesis panel
- ranked hypotheses;
- confidence;
- missing context.

### Action panel
- request investigation;
- ask for evidence;
- confirm/reject hypothesis;
- propose preventive control;
- route operational recommendation.

### Assistant
Persistent side panel, scoped to current context.

---

# 17.3 Chat migration

Do not delete existing chat.

Refactor it into:

> **Contextual Reliability Assistant**

The assistant receives:
- project ID;
- current incident;
- selected entities;
- evidence IDs;
- current user role.

It cannot:
- independently create authoritative state;
- approve;
- issue execution authorization;
- bypass HITL.

---

# 18. Governance and Execution

Execution must be separated from reasoning.

Required invariant:

```text
EXECUTE
⇒ authenticated actor
∧ approved proposal version
∧ matching project/snapshot
∧ validated compiled plan
∧ successful sandbox result where required
∧ valid execution authorization
∧ immutable audit event
```

Client requests execution using an authorization ID, not arbitrary rule code.

---

# 19. Current Repository Gap Audit

Based on the latest audited v4.2.x structure, do not rewrite the platform.

## Keep/refactor

- existing deterministic profiler;
- validator;
- compiler;
- executor;
- quarantine;
- audit foundation;
- scheduler;
- anomaly detector infrastructure;
- ReAct foundations;
- WebSocket/API foundation;
- frontend workspaces.

## Missing / incomplete

### Detection
- true per-entity L2 rolling baseline;
- interpretable L3 relationship models;
- L4 change-point service;
- common typed `Signal` schema.

### Fusion
- entity/time signal grouping;
- incident admission;
- fusion calibration.

### Incident
- canonical persistent incident model;
- evidence ledger;
- hypothesis lifecycle;
- conditional output routing.

### Evaluation
- unbiased R0/C1/A1 harness;
- true L2-L4 injected cases;
- incident-level metrics;
- actual tool/latency/cost instrumentation.

### UX
- 4-layer timeline;
- Incident Workspace;
- server-backed evidence and hypotheses;
- chat sidecar migration.

### Governance
- one canonical approval path;
- version-bound execution authorization;
- persistent state;
- authenticated scoped WebSocket.

### Integrity
- remove mock dashboard KPIs from operational views;
- simulated results must be labeled;
- remove any claim of natural causal linkage for proxy datasets.

---

# 20. Implementation Architecture

Avoid duplicating modules.

Prefer a dedicated reliability bounded context.

Suggested logical structure; adapt to existing source conventions rather than blindly duplicating files:

```text
src/
  reliability/
    models/
      signal.py
      incident.py
      evidence.py
      hypothesis.py
    detectors/
      l1_rules.py
      l2_contextual.py
      l3_relational.py
      l4_changepoint.py
    features/
      entity_features.py
      relationship_features.py
    fusion/
      engine.py
      policy.py
      calibration.py
    incidents/
      service.py
      repository.py
    investigation/
      r0.py
      c1.py
      a1.py
      tools.py
    governance/
      recommendations.py
      preventive_controls.py
```

If equivalent modules already exist, extend them; do not create a parallel architecture.

---

# 21. Data Contracts

## Signal

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
detector:
detector_version:
evidence_refs:
provenance:
created_at:
```

## Incident

```yaml
incident_id:
project_id:
status:
entity_ids:
signal_ids:
admission_reason:
severity:
time_window:
confirmed_facts:
evidence_refs:
owner:
created_at:
updated_at:
```

## Evidence

```yaml
evidence_id:
source_type:
source_id:
time_range:
entity_ids:
content_hash:
summary:
provenance:
```

## Hypothesis

```yaml
hypothesis_id:
incident_id:
claim:
classification: DATA|OPERATIONAL|MIXED|UNKNOWN
supporting_evidence:
contradicting_evidence:
missing_evidence:
confidence:
status:
```

---

# 22. API Direction

Canonical API only:

```text
/api/v1/projects
/api/v1/signals
/api/v1/incidents
/api/v1/incidents/{id}
/api/v1/incidents/{id}/investigate
/api/v1/incidents/{id}/hypotheses
/api/v1/incidents/{id}/feedback
/api/v1/incidents/{id}/recommendations
/api/v1/controls
/api/v1/authorizations
/api/v1/audit
```

Do not create a second set of overlapping HITL/approval routes.

---

# 23. Coding-Agent Work Rules

Every coding agent must:

1. Inspect existing implementation before creating files.
2. Reuse canonical schemas/services.
3. Add tests with ground-truth expectations.
4. Never add a metric that is not computed.
5. Never silently fall back to mock in production mode.
6. Preserve immutable raw data.
7. Preserve governance boundaries.
8. Produce a completion note:
   - files changed;
   - tests;
   - measured results;
   - assumptions;
   - unresolved risks.

---

# 24. Execution Plan from 11 Aug to Feature Lock

## Sprint 2 Closure — 11–12 Aug
### Goal
Lock semantics, benchmark integrity, and common signal contracts.

Tasks:
- replace old PLAN with this plan;
- add provenance labels;
- create common Signal/Incident/Evidence/Hypothesis contracts;
- remove/disable self-fulfilling benchmark;
- remove mock KPI from default operational UI;
- finalize causal digital twin schema;
- define benchmark generator v1.

Exit:
- architecture has one definition of L1-L4;
- no old benchmark can be presented as real evidence.

---

## Sprint 3A — 13–15 Aug
### Goal
Implement L2 and feature foundation.

Tasks:
- entity/time feature builder;
- warm-up policy;
- rolling median/MAD;
- robust Z-score;
- L2 synthetic scenarios;
- metrics.

Owner emphasis:
- Ngân: methodology;
- Dũng: runtime/data contract;
- Thanh: ground truth;
- Huyền: timeline UX skeleton.

Exit:
- L2 independently benchmarked.

---

## Sprint 3B — 15–17 Aug
### Goal
Implement L3 and L4.

L3:
- expected-relationship definitions;
- regression residual;
- optional Isolation Forest comparator.

L4:
- PELT;
- CUSUM;
- timing metrics.

Corpus:
- relation-break scenarios;
- persistent change scenarios.

Exit:
- L3 and L4 have real output contracts and benchmark results.

---

## Sprint 3C — 17–19 Aug
### Goal
Fusion + Incident creation.

Tasks:
- signal normalization;
- entity/time grouping;
- deterministic fusion;
- admission policy;
- persistent incident store;
- evidence ledger;
- 4-layer timeline API.

Frontend:
- project reliability view;
- incident list;
- incident timeline.

Exit:
- digital twin event stream produces reproducible incidents.

---

## Sprint 4A — 19–21 Aug
### Goal
C1 fixed investigation + UX.

Backend:
- context sufficiency;
- fixed evidence retrieval;
- structured hypothesis generator;
- conditional recommendation routing.

Frontend:
- Incident Workspace;
- evidence;
- contradictions;
- hypotheses;
- contextual assistant;
- HITL.

Evaluation:
- R0 vs C1;
- human evaluation instrumentation.

Exit:
- a Data Steward can complete the core journey without needing chat commands.

---

## Sprint 4B — 21–23 Aug
### Goal
A1 bounded investigation.

Tasks:
- dynamic typed tool selection;
- change time/entity scope;
- hypothesis challenge;
- evidence references;
- stop/continue;
- request context;
- abstention;
- cost/time budgets.

Evaluation:
- same blind cases as C1.

Exit:
- demonstrate at least several cases where A1 takes different valid tool paths based on intermediate observations.

---

## Sprint 4C — 23–25 Aug
### Goal
Benchmark, red team, and governance hardening.

Run:
- L1-L4 detector benchmark;
- Fusion benchmark;
- R0/C1/A1 benchmark;
- UX timing subset.

Red team:
- missing history;
- ambiguous entity;
- conflicting signals;
- noisy/sparse data;
- false complaint;
- prompt injection;
- stale context;
- excessive agent loop;
- approval bypass;
- unauthorized execution.

Governance:
- bind approval to exact control version;
- execution authorization only;
- immutable audit.

Exit:
- real evaluation report generated from run artifacts.

---

## Feature Freeze — 26 Aug

Use 26 Aug for:
- P0 fixes;
- final benchmark rerun;
- demo data freeze;
- documentation;
- architecture reconciliation.

At **23:59 26 Aug**:

No:
- new detector family;
- new agent role;
- new data source;
- new workspace;
- contract redesign;
- new A2 dependency.

---

# 25. A2 Decision Window

If A1 error analysis before 24 Aug reveals a qualifying failure mode, a small team may prototype A2 behind a feature flag.

A2 must not block:
- A1 benchmark;
- governance;
- Incident UX;
- feature lock.

Possible A2 experiment:

```text
A1 Planner
├── Hypothesis Investigator A
├── Hypothesis Investigator B
└── Independent Evidence Verifier
```

Required comparison:

```text
A1 vs A2
on the SAME failure subset.
```

If no measurable benefit:
- keep A1/C1;
- document negative result.

---

# 26. Post-Feature-Lock — 27 Aug to 3 Sep

No new features.

Tasks:
- rerun benchmark with frozen versions;
- fix P0 demo blockers;
- Docker/reset;
- performance tests;
- 3+ dry runs;
- documentation;
- research report;
- demo rehearsal;
- backup recording.

---

# 27. Ownership

| Member | Accountable area |
|---|---|
| **Thanh** | Product thesis, benchmark integrity, digital-twin corpus, experiment design, business interpretation, decision log |
| **Ngân** | L2/L3/L4 methodology, Fusion calibration, semantic investigation quality, C1/A1/A2 error analysis |
| **Dũng** | Data plane, feature pipeline, detector runtime, APIs, persistence, security, authorization, deterministic execution |
| **Huyền** | Project/Incident UX, contextual assistant, HITL, audit UX, E2E integration, deployment/demo |

Coding agents can produce implementation rapidly; human owners remain responsible for:
- correctness;
- experimental validity;
- source provenance;
- failure semantics;
- final merge.

---

# 28. Definition of Done

## Detection
- L1-L4 each have a clear semantic definition;
- L2-L4 include cases impossible to solve with simple point constraints;
- every signal contains evidence and detector version.

## Fusion
- reduces raw signals into useful incidents;
- admission decisions are explainable.

## Investigation
- R0, C1, A1 run on equivalent evidence;
- A1 may win or lose;
- unsupported claims are measured.

## UX
A Data Steward can:

```text
Open project
→ see reliability status
→ inspect anomaly timeline
→ open incident
→ see facts/evidence
→ inspect/request RCA
→ make HITL decision
→ issue data control OR operational recommendation
→ view audit
```

without needing to know prompt syntax.

## Data integrity
- semi-synthetic data is labeled;
- no false claim of real cross-domain causal data;
- generator version and seed stored.

## Governance
- reasoning cannot directly mutate data;
- control must be approved and authorized;
- execution is deterministic;
- every consequential action is auditable.

---

# 29. Final Team Narrative

The team should explain the architecture consistently:

> **DataTrust OS does not use AI to solve errors that simple rules already solve. L1 handles known violations deterministically and quickly. L2 detects deviations from an entity's own history. L3 detects broken relationships between otherwise valid variables. L4 detects persistent behavior changes. Fusion turns these signals into incidents. Only then do we use AI for investigation, and only when semantic reasoning or dynamic tool selection adds measurable value. The Data Steward remains in control, and all execution remains deterministic.**

The answer to “Why Agent?” is therefore:

> **The product does not need an agent everywhere. An agent is justified only in incident investigation when the next evidence source, tool, scope, or hypothesis cannot be fully predetermined. We benchmark that claim against a fixed workflow and remove the agent if it does not create enough value.**

This is the final engineering/product direction through feature lock.
