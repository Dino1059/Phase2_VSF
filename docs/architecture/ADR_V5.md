# Architectural Decision Record: DataTrust OS v5 Operational Trust Architecture (ADR-V5)

- **Status:** Accepted (Finalized)
- **Date:** 2026-08-11
- **Authors:** DataTrust OS Architecture & Engineering Team
- **Target Release:** DataTrust OS v5.0
- **Primary Source Specification:** [PLAN.md](../../PLAN.md)

---

## 1. Context & Problem Statement

DataTrust OS v4 and prior iterations operated under an "agent-first" hypothesis where AI agents were assumed to be the default mechanism for data quality monitoring and root-cause analysis (RCA). Source code audits and operational reviews revealed critical failure modes in that approach:

1. **Premature & Unvalidated Autonomy:** Multi-agent architectures were introduced without empirical validation against simpler deterministic baselines (R0) or fixed LLM workflows (C1).
2. **Temporal & Model Leakage:** Detection components suffered from temporal look-ahead leakage in statistical baselines (L2) and train/score window overlap in multivariate models (L3).
3. **Alert Fatigue & Fragmented Signal Processing:** Anomaly detectors operated in isolation without a unified fusion mechanism, flooding operators with uncalibrated signals.
4. **Governance & HITL Flaws:** Approval workflows were fragmented across endpoints, allowing local frontend mutations to masquerade as backend-approved executable state without cryptographic or version binding.
5. **Chat-First Misalignment:** Enterprise data stewards require an operational control plane for systematic daily monitoring, incident triage, and evidence auditing, rather than a prompt-based chatbot interface.

**Decision Requirement:** Define an enterprise-grade, deterministic-first **Operational Trust Architecture** for DataTrust OS v5 that establishes strict architectural boundaries between Detection, Fusion, Investigation, Governance, and Execution.

---

## 2. Decision Overview: Operational Trust Control Plane

DataTrust OS v5 is repositioned as an **Operational Trust Console** engineered specifically for the **Data Steward / Data Quality Manager** (primary user) and **Data / Analytics Engineer** (secondary user).

### Core Principle
> **"Use the cheapest sufficient mechanism. Agentic behavior is an escalation path, not the product thesis."**

The platform operates on a strict **Conditional Autonomy Ladder**:
- **R0 (Deterministic Rules & Statistics):** Handled via fixed SQL/Pydantic rules, known diagnostic lookup tables, and statistical thresholds. If business SLOs are met, execution stops—no LLM is invoked.
- **C1 (Fixed LLM Workflow):** A deterministic context builder aggregates typed evidence and passes it to a single structured LLM call within a fixed DAG. Used when semantic rule generation or initial structured explanation is needed.
- **A1 (Bounded Dynamic Investigator):** A single ReAct agent that dynamically selects typed tools, evaluates support vs. contradiction, and decides whether to continue, stop, or abstain based on intermediate evidence. Escalated only when intermediate observations alter the required next action.
- **A2 (Multi-Agent Verification):** Reserved as an optional experiment admitted only when A1 error analysis proves that independent specialized agents or parallel verifiers yield measurable gains over A1.

---

## 3. Detailed Architectural Specifications

The v5 architecture enforces strict separation across five pipeline stages:

```text
+-----------------------------------------------------------------------+
|                            DETECTION LAYER                             |
|  L1: Deterministic Constraints | L2: Temporal Statistical Baselines   |
|  L3: Relational Models         | L4: Change-Point Detection (CUSUM/PELT)|
+-----------------------------------------------------------------------+
                                   | (Signals)
                                   v
+-----------------------------------------------------------------------+
|                             FUSION LAYER                              |
|  Calibrated Deterministic Admission Engine (Severity, Score, Layers) |
+-----------------------------------------------------------------------+
                                   | (Admitted Incidents)
                                   v
+-----------------------------------------------------------------------+
|                       INVESTIGATION ARCHITECTURE                       |
|  R0: Deterministic -> C1: Fixed LLM -> A1: Bounded Agent -> (A2)      |
+-----------------------------------------------------------------------+
                                   | (Evidence-Backed Hypotheses)
                                   v
+-----------------------------------------------------------------------+
|                          GOVERNANCE & HITL                            |
|  Preventive Data Control | Operational Recommendation | Abstention     |
|  Canonical Lifecycle & Immutable Audit Binding                        |
+-----------------------------------------------------------------------+
                                   | (Authorized Execution Plan)
                                   v
+-----------------------------------------------------------------------+
|                          DETERMINISTIC EXECUTION                       |
|  Sandboxed Compiler & Whitelisted Transform / Quarantine Engine       |
+-----------------------------------------------------------------------+
```

### 3.1 Detection Layer (L1 – L4)

Detection modules output standardized, typed `Signal` schemas across four technical layers. Signals indicate an observed anomaly; they do not automatically declare a data fault.

1. **L1 — Deterministic Constraints & Metadata Rules:**
   - Evaluates explicit schema contracts, null ratios, range checks, foreign key integrity, and SLA freshness/lateness metrics.
   - Expressed in versioned `RuleSpec` definitions.
2. **L2 — Entity-Relative Statistical Anomalies (Leakage-Free):**
   - Implements rolling median, Median Absolute Deviation (MAD), and robust Z-scores strictly using historical observations ($t_{hist} < t_{scored}$).
   - **Anti-Leakage Invariant:** $Score(entity, t)$ is strictly independent of data at $t' > t$.
3. **L3 — Relational & Multivariate Models:**
   - Captures cross-metric equations and expected domain relationships (e.g., charging energy vs. mileage).
   - Trains on a reference window, freezes model versions, and evaluates residuals on an isolated evaluation window.
   - Evaluated at `GLOBAL`, `ASSET_CLASS`, or `ENTITY` granularity based on sample volume.
4. **L4 — Change-Point Detection:**
   - Implements online CUSUM for real-time drift detection and offline PELT (Pruned Exact Linear Time) for batch baseline validation.
   - Generates explicit pre- and post-window statistical summaries, change timestamps, and magnitudes.
5. **Visual Categorization:**
   - UI renders L1–L4 signals with 4 stable categorical colors, distinct icons, and explicit tier labels to avoid visual ambiguity.

### 3.2 Fusion Layer (Fusion v5)

The Fusion Layer acts as an evidence-aware admission controller that groups multi-layer signals into actionable `Incidents`.

- **Non-LLM Core:** Fusion is entirely deterministic and rule/statistical driven, ensuring zero LLM latency or non-determinism during triage.
- **Admission Criteria:**
  - Critical L1 rule failures $\rightarrow$ Immediate incident admission.
  - Persistent high-severity single-layer anomalies ($L2/L3/L4$) $\rightarrow$ Admitted.
  - Multi-layer signal agreement ($\ge 2$ independent layers overlapping in entity scope and time window) $\rightarrow$ Admitted.
- **Goal:** Dramatically reduce alert noise and deduplicate symptoms before triggering root-cause investigation.

### 3.3 Incident Investigation Architecture (Autonomy Escalation)

When an `Incident` is admitted, investigation follows the autonomy ladder:

1. **R0 (Deterministic Resolution):**
   - Matches incidents against structured diagnostic patterns (e.g., known deployment schema drift, documented vendor status codes).
   - Resolves instantly with zero LLM API cost.
2. **C1 (Fixed AI Workflow Baseline):**
   - Aggregates an immutable context bundle (signals, profiles, change logs, entity history).
   - Executes a single structured LLM call producing validated JSON conforming to the `Hypothesis` and `Recommendation` schema.
   - Validates that all cited `evidence_ids` exist in the evidence ledger.
3. **A1 (Bounded Dynamic Investigator):**
   - Executes an observation-dependent ReAct loop using a strictly typed, read-only tool registry (`fetch_entity_history`, `fetch_telemetry_window`, `fetch_trip_history`, `fetch_charging_history`, `fetch_dq_violations`, `fetch_recent_changes`, `resolve_entity_relationships`).
   - Dynamically evaluates supporting vs. contradicting evidence and maintains a structured hypothesis state.
   - **Hard Boundaries:** Restricted by max tool calls, max tokens, wall-clock timeout, and explicit read-only allowlists.
   - **Explicit Abstention:** If available evidence is insufficient or contradictory, A1 must output an explicit `ABSTAIN` status requesting specific missing evidence rather than hallucinating a cause.
4. **A2 (Optional Experimentation):**
   - Disabled by default. Admitted only if empirical A1 error analysis demonstrates specific failure modes (e.g., hypothesis blind spots) that parallel verifiers or specialist agents resolve.

### 3.4 Governance, HITL, & Action Routing

All investigation outputs route through the Human-in-the-Loop (HITL) Governance layer before any system change occurs.

1. **Typed Output Routing:**
   - **`PREVENTIVE_DATA_CONTROL`:** Recommended when root cause is a pipeline, schema, or data transformation bug (e.g., compile a new `RuleSpec` or update quarantine boundary).
   - **`OPERATIONAL_RECOMMENDATION`:** Recommended when root cause is a physical asset or business operation issue (e.g., dispatch technician for damaged charger port).
   - **`ABSTENTION`:** Issued when evidence is missing or ambiguous.
2. **Canonical Lifecycle:**
   ```text
   PROPOSED -> REVIEW_PENDING -> APPROVED | EDITED | REJECTED
     -> COMPILED -> SANDBOX_VALIDATED -> AUTHORIZED -> EXECUTED
   ```
   - Rules or actions edited by a user reset to `PROPOSED` for re-validation; `EDITED` is never an executable state.
3. **Execution Invariant:**
   - Execution requires an explicit server-side `authorization_id`.
   - Binds the execution to: `authenticated_actor` + `exact_approved_version` + `snapshot_id` + `compiled_plan_hash` + `sandbox_test_result` + `timestamp`.
   - The execution engine rejects client re-submissions of modified execution code.

### 3.5 Canonical Data & Evidence Schemas

All platform entities follow strict immutable schemas:

- **`Signal`**: `signal_id`, `project_id`, `entity_ids`, `layer` (L1-L4), `score`, `severity`, `detector_name`, `evidence_refs`, `provenance`.
- **`Incident`**: `incident_id`, `project_id`, `status`, `entity_ids`, `signal_ids`, `admission_reason`, `severity`, `time_window`, `evidence_refs`.
- **`Evidence`**: Typed, retrievable records with `evidence_id` (`ev_...`), `incident_id`, `source_type`, `source_record_ids`, `time_window`, `content_hash`, `provenance`.
- **`Hypothesis`**: `hypothesis_id`, `incident_id`, `claim`, `classification` (`DATA` | `OPERATIONAL` | `MIXED` | `UNKNOWN`), `supporting_evidence_ids`, `contradictory_evidence_ids`, `missing_evidence`, `confidence`.

Data provenance is strictly labeled as `REAL_OPERATIONAL`, `PUBLIC_PROXY`, `SEMI_SYNTHETIC`, or `SYNTHETIC`.

---

## 4. Consequences & Operational Impacts

### Positive Consequences
- **Elimination of Agent Theater:** Ensures AI autonomy is deployed only where dynamic evidence gathering yields measurable improvement over deterministic rules (R0) or fixed LLM pipelines (C1).
- **Leakage-Free Reliability:** Guarantees temporal integrity in L2 statistics and statistical isolation in L3 models, eliminating false accuracy.
- **Fail-Closed Enterprise Security:** Prevents unauthorized code execution and client-side approval tampering via server-side authorization tokens and immutable audit manifests.
- **Operational Trust for Data Stewards:** Replaces unstructured chat interfaces with a purpose-built Reliability Cockpit featuring clear evidence trails, blast-radius previews, and rollback controls.

### Trade-offs & Limitations
- **Upfront Modeling Overhead:** Requires strict historical window management for L2/L3 detectors and typed evidence indexing.
- **Abstention Enforcement:** Agents will abstain when evidence is incomplete, requiring data stewards to provide missing data or execute manual overrides.

---

## 5. References

- [DataTrust OS v5 Implementation Plan (PLAN.md)](../../PLAN.md)
- [DataTrust OS Master Architecture Specification (ARCHITECTURE.md)](../../ARCHITECTURE.md)
- [Architectural Decision Log (decision-log.md)](decision-log.md)
