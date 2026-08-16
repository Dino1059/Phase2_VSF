# 🧩 DataTrust OS v5 — Component Topology (C4 Model)

> **Document Status:** Official Production Component Topology  
> **Target Version:** DataTrust OS v5 (Operational Trust Console)  
> **Last Updated:** 2026-08-11  

---

## 1. System Context

**DataTrust OS v5** acts as the operational trust boundary between raw ingested telemetry (VinFast, V-GREEN, Xanh SM) and downstream clean analytics systems. Unlike previous iterations, it is not an open-ended multi-agent chat system; it is a strict, pipeline-driven governance console.

```mermaid
C4Context
    title System Context diagram for DataTrust OS v5

    Person(steward, "Data Steward", "Reviews fused incidents and authorizes executions via HITL Sandbox.")
    
    System(dtos, "DataTrust OS v5", "Detects anomalies, investigates root causes deterministically, and executes governed partitioning.")
    
    System_Ext(raw_db, "Enterprise Data Lakes", "Stores raw VinGroup telemetry (IoT, NLP, Trips).")
    System_Ext(clean_db, "Clean Analytics DB", "Stores trusted, partitioned data with cryptographic manifests.")

    Rel(steward, dtos, "Manages & Authorizes", "HTTPS/JWT")
    Rel(dtos, raw_db, "Ingests & Profiles", "SQL/Parquet")
    Rel(dtos, clean_db, "Partitions & Writes", "SQL")
```

---

## 2. Container Topology

The backend topology enforces physical and logical separation between Detection, Fusion, Investigation, and Execution.

```mermaid
C4Container
    title Container diagram for DataTrust OS v5

    Person(steward, "Data Steward", "Reviews fused incidents.")

    System_Boundary(c1, "DataTrust OS v5 Backend") {
        Container(api, "FastAPI Router", "Python", "Handles REST endpoints and JWT RBAC.")
        
        Container(detect, "L1-L4 Detection Engine", "Python/Pandas", "Deterministic constraints, zero-leakage stats, Isolation Forests.")
        
        Container(fusion, "Fusion v5 Engine", "Python", "Admit and deduplicate multi-layer signals into incidents.")
        
        ContainerDb(duckdb, "Persistent Incident Store", "DuckDB", "Stateful persistence for Incidents, Evidence, and Hypotheses.")
        
        Container(investigate, "R0/C1/A1 Investigator", "Python/Gemma", "Escalation ladder from rules to fixed prompts to dynamic bounded agents.")
        
        Container(gov, "HITL Governance Sandbox", "Python", "Verifies exact JWT payload hashes against execution plans.")
    }

    Rel(steward, api, "Authorizes Executions", "JSON/HTTPS")
    Rel(api, detect, "Triggers", "Internal")
    Rel(detect, fusion, "Emits Signals", "Internal")
    Rel(fusion, duckdb, "Persists Incidents", "SQL")
    Rel(duckdb, investigate, "Provides Evidence Context", "SQL")
    Rel(investigate, gov, "Proposes Typed Actions", "Internal")
```

---

## 3. Core Component Boundaries

### 3.1 Detection Engine (L1 - L4)
- **Component:** `src/reliability/detectors/`
- **Responsibility:** Identify specific statistical or relational deviations.
- **Constraints:** Must NEVER look ahead. Must separate `ref_df` from `eval_df`.
- **Outputs:** `Signal` objects.

### 3.2 Fusion v5 Engine
- **Component:** `src/reliability/fusion.py`
- **Responsibility:** Group signals by entity and time. Reduce alert fatigue.
- **Constraints:** Zero LLM usage. Purely deterministic logic.
- **Outputs:** `Incident` objects persisted to DuckDB.

### 3.3 Dynamic Investigation Ladder (R0 $\rightarrow$ C1 $\rightarrow$ A1)
- **Component:** `src/reliability/investigation/`
- **Responsibility:** Find the root cause of an Incident.
- **Constraints:** R0 and C1 run first. A1 only runs on ambiguous results. A1 uses strictly typed, read-only tools. A1 must `ABSTAIN` if evidence is lacking.
- **Outputs:** `Hypothesis` and `Recommendation` objects.

### 3.4 Governance & Execution
- **Component:** `src/reliability/governance/preventive_controls.py`
- **Responsibility:** Safely execute a recommendation.
- **Constraints:** Requires user cryptographically signed JWT hash matching the `ctrl.version_hash`. AI cannot bypass.
- **Outputs:** Clean partition / Quarantined records.

---
*DataTrust OS v5 — Component Topology*
