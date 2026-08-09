# Architectural Decision Log (ADR) — DataTrust OS

---

## ADR-001: Bounded Execution over Autonomous Agent

- **Status:** Accepted
- **Context:** Autonomous agents generating raw SQL or Python code can introduce non-deterministic side-effects, security vulnerabilities, or silent data corruption.
- **Decision:** Restrict the AI Agent to proposing structured rules conforming to `RuleSpec`. Execution is handled exclusively by a deterministic compiler and whitelisted transform library.
- **Consequences:** Eliminates code injection risks and guarantees 100% executable plan reproducibility.

---

## ADR-002: Metadata-Only LLM Prompting

- **Status:** Accepted
- **Context:** Ingesting production relational data raises strict PII, compliance, and governance concerns if raw customer data is passed to external LLM providers.
- **Decision:** The `ContextBuilder` sanitizes inputs and passes only deterministic statistical aggregates (min, max, null counts, cardinalities, top value distributions) to the LLM.
- **Consequences:** Zero raw row data exposure to LLM APIs while enabling rich semantic context for rule proposal.

---

## ADR-003: Three-Tier Baseline Evaluation Progression (C0 -> C1 -> A1)

- **Status:** Accepted
- **Context:** To prove the value of an agentic architecture, we must objectively compare simple and pipeline baselines against tool-using agents.
- **Decision:** Implement and benchmark three variants:
  1. **C0:** One-shot LLM prompt without profiler or validation tool calls.
  2. **C1:** Fixed 4-step pipeline (Profiler -> LLM -> Validator -> HITL) without repair loops.
  3. **A1:** Bounded tool-using agent with ReAct engine, observation traces, repair loop, and abstention.
- **Consequences:** Provides quantitative empirical evidence required to validate the agentic claim.

---

## ADR-004: Fail-Closed Quarantine Isolation Architecture

- **Status:** Accepted
- **Context:** Deleting anomalous or invalid records during onboarding creates audit gaps and data loss risks.
- **Decision:** Implement a dual-output model: valid rows are routed to `CleanDB`, while invalid or out-of-range rows are placed in a `Quarantine` dataset tagged with `quarantine_reason`.
- **Consequences:** Total row accountability is preserved (`CleanDB rows + Quarantine rows == Input rows`).

---

## ADR-005: Quantitative Agentic Gate Criterion

- **Status:** Accepted
- **Context:** Claiming an "Agentic" solution requires meeting quantitative performance thresholds over static pipelines.
- **Decision:** Enforce a hard quantitative gate:
  - **Win Condition:** A1 must outperform C1 by **>= 10 percentage points in semantic recall** OR **>= 25% reduction in correction time**.
  - **Guardrails:** A1 must maintain **>= 80% precision** and **cost <= 2.0x C1**.
  - **Fallback:** If A1 fails this gate, the project reverts to shipping C1 and removes the "agentic" product claim.
- **Consequences:** Establishes rigorous engineering accountability for AI product performance.
