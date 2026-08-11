# DataTrust OS v5 — Database & Persistent Schema Architecture

> **Document Status:** Authoritative Database Schema Specification  
> **Target Version:** DataTrust OS v5 (Operational Trust Console)  
> **Storage Engine:** DuckDB  
> **Last Updated:** 2026-08-11  

---

## 1. Storage & Persistence Philosophy

DataTrust OS v5 relies on **DuckDB** as the primary storage engine to manage state across the entire governance lifecycle. Unlike v4 which focused on ephemeral agents, v5 introduces persistent, isolated state for `incidents`, `evidence`, `hypotheses`, `decisions`, and `recommendations` that survives backend restarts.

### 1.1 Strict Isolation Boundaries
- **Cross-Incident Isolation:** Queries joining `incidents` to `evidence` enforce strict bounds (`project_id`, `incident_id`).
- **Read-Only Provenance:** Evidence is immutable once ingested.
- **State Checkpointing:** A1 Agent reasoning is saved continuously to `hypotheses`.

---

## 2. Core Operational Schema (DDL)

The core operational state is managed within `src/db/schema.sql` and instantiated by `src/db/connection.py`.

### 2.1 `incidents` Table
Represents a fused operational incident (e.g., L2 Temp Spike + L3 SoC mismatch).

```sql
CREATE TABLE IF NOT EXISTS incidents (
    incident_id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    status VARCHAR NOT NULL,  -- OPEN, INVESTIGATING, RESOLVED, CLOSED
    severity VARCHAR NOT NULL, -- CRITICAL, HIGH, MEDIUM, LOW
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    entity_ids JSON,          -- Target entities affected
    time_window JSON          -- Start/End bounds
);
```

### 2.2 `evidence` Table
Immutable context gathered via Signals (L1-L4) or Agent Tools.

```sql
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    project_id VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL, -- SIGNAL, TELEMETRY, LOG, HISTORY
    content VARCHAR NOT NULL,     -- String or JSON payload
    source_id VARCHAR NOT NULL,   -- Link to original record
    content_hash VARCHAR NOT NULL,-- SHA-256 hash for integrity
    time_window JSON,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);
```

### 2.3 `hypotheses` Table
Records structured diagnostic pathways evaluated by C1/A1.

```sql
CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    claim VARCHAR NOT NULL,
    classification VARCHAR NOT NULL, -- DATA, OPERATIONAL, MIXED, UNKNOWN
    confidence FLOAT,
    supporting_evidence_ids JSON,
    contradicting_evidence_ids JSON,
    status VARCHAR NOT NULL,         -- PROPOSED, ACCEPTED, REJECTED, ABSTAINED
    created_at TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);
```

### 2.4 `recommendations` & `decisions`
Records HITL sandbox proposals and finalized steward actions.

```sql
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    hypothesis_id VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL, -- PREVENTIVE_DATA_CONTROL, OPERATIONAL_RECOMMENDATION
    description VARCHAR NOT NULL,
    sandbox_status VARCHAR,       -- PENDING, PASS, FAIL
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    recommendation_id VARCHAR NOT NULL,
    decision_action VARCHAR NOT NULL, -- APPROVED, REJECTED
    authorized_by VARCHAR NOT NULL,   -- JWT User ID
    jwt_payload_hash VARCHAR NOT NULL,-- Cryptographic bind
    executed_at TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);
```

---

## 3. Data Pipeline & Ingestion Tables

Raw datasets (VinFast EV Telemetry, V-GREEN Chargers, Xanh SM Trips, UIT-VSFC Feedback) are ingested via polymorphic `DataSource` components directly into isolated DuckDB tables:
- `raw_vinfast_ev_telemetry`
- `raw_vgreen_charging_stations`
- `clean_vinfast_ev_telemetry` (After HITL Execution Partitioning)
- `quarantine_vinfast_ev_telemetry` (Violations routing)

---
*DataTrust OS v5 — Database Architecture*
