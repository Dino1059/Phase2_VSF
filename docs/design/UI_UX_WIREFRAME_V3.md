# 🎨 DataTrust OS v3.0 — Master UI/UX & Wireframe Specification

> **Document Status:** Official Production UI/UX Specification  
> **Design Pattern:** Agentic-Centric + Context Workspace Dashboard (Hybrid HITL Architecture)  
> **Excalidraw Canvas Elements:** 34 Interactive Canvas Elements Created  
> **Last Updated:** 2026-08-02  

---

## 🏛️ 1. Design Rationale & Team Consensus

Based on the core design discussion between **Quốc Thanh**, **Tạ Kim Ngân**, and **Huyền Vũ**:

1. **Agentic-Centric with Human-In-The-Loop (HITL)**:
   - The central stream operates as a real-time ReAct Reasoning loop (`Orchestrator` ➔ `Profiler` ➔ `Anomaly Detector` ➔ `Rule Proposer`).
   - Every rule proposal is rendered as an inline **HITL Card** (`RuleProposalCard`) allowing stewards to **Approve**, **Reject**, or **Edit** constraints before Clean DB partitioning.

2. **Multi-View Context Workspace (Dashboard-Centric Split Panel)**:
   - Solves the UX concern of missing context in plain chat interfaces by providing a persistent right-side workspace panel.
   - Tabs: `[📊 Profile]` `[🛡️ Rules]` `[⚠️ Anomaly & RCA]` `[📋 Audit Log]` `[🔀 Diff View]`.

3. **Session-Isolated Datasets**:
   - Each chat session is pinned to a specific dataset (e.g., `real_vinfast_ev_telemetry`, `vgreen_charging_stations_dirty`).

4. **Global Command & Search Bar (`Ctrl + K`)**:
   - Provides quick keyboard-navigated search across active sessions, dataset repositories, audit logs, and governance rules.

---

## 📐 2. Excalidraw Wireframe Layout Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🤖 DataTrust OS v3.0 — VinGroup Enterprise AI Governance  │ 📦 real_vinfast_ev_telemetry │ 🔍 Ctrl+K │ 📤 Upload DB │ 👤 Steward│
├──────────────────────────┬───────────────────────────────────────────────────────┬───────────────────────────────┤
│ + New Chat Session       │ ⚖️ Pending Governance Review (3 rules)  | [✓ Approve All] │ [📊 Profile] [🛡️ Rules]       │
├──────────────────────────┤ 👤 User: Detect anomalies & propose quality rules     │ [⚠️ Anomaly & RCA] [📋 Audit] │
│ ACTIVE SESSIONS          │ 🤖 Orchestrator Agent (Gemma-4-26b):                 ├───────────────────────────────┤
│ 💬 VinFast EV Telemetry  │    Executing Tri-Detector Suite                       │ 🔥 Dual Composite Anomaly     │
│ 💬 V-GREEN Overheat      │ ⚠️ Anomaly Detector Agent:                            │    Score: S_composite = 0.89   │
│ 💬 Xanh SM Trips Audit   │    Flagged 28 anomalies (Basement Blackout, SOC -12%)│ (MAD Z: 6.50 | IsoForest: 0.92)│
│ 💬 Customer Feedback NLP │ 🛡️ Rule Proposer Agent Proposal #1:                   ├───────────────────────────────┤
├──────────────────────────┤    Column: battery_soc  | Type: range_check           │ 📌 Detected Defects Breakdown:│
│ DATASET REPOSITORY       │    Expression: battery_soc >= 0.0 AND <= 100.0        │ 1. GSM Basement Blackout (25) │
│ 📦 real_vinfast_ev_telem │    [✓ Approve]  [✗ Reject]  [✏️ Edit]  [▶ Clean DB]   │ 2. Negative Battery SOC (15)  │
│                          ├───────────────────────────────────────────────────────┤ 3. Overvoltage Spikes (8)     │
│                          │ 💬 Type command or ask AI steward...        [📎 Upload]│ 4. Motor RPM Mismatch (12)    │
│                          │                                                       ├───────────────────────────────┤
│                          │                                                       │ 🩺 Diagnosis Agent RCA:       │
│                          │                                                       │ Root Cause: VinFast VF8       │
│                          │                                                       │ entered Vincom Basement.      │
│                          │                                                       ├───────────────────────────────┤
│                          │                                                       │ ✨ Clean DB Summary:          │
│                          │                                                       │ Clean: 940/1000 (94.0%)       │
│                          │                                                       │ Quarantine: 60 (6.0%)         │
└──────────────────────────┴───────────────────────────────────────────────────────┴───────────────────────────────┘
```

---

## 🎨 3. Structural Component Breakdown

### 3.1 Top Header & Global Bar
- **Application Title**: `DataTrust OS v3.0 — VinGroup Enterprise AI Governance`.
- **Dataset Context Selector**: Pinned dataset badge `[📦 real_vinfast_ev_telemetry]`.
- **Command Palette (`Ctrl + K`)**: Instant semantic search across chat history, rules, and audit manifests.
- **Upload DB Action**: Triggers file picker for `.csv`, `.parquet`, `.json`, and `.sqlite` uploads.

### 3.2 Left Navigation Sidebar (Session & Dataset Manager)
- **New Chat Action**: `[+ New Chat Session]` resets session state and creates a isolated context thread.
- **Active Session Thread List**:
  - `💬 VinFast EV Telemetry Scan` (Active)
  - `💬 V-GREEN Charger Overheat`
  - `💬 Xanh SM Trips Ledger Audit`
  - `💬 Customer Feedback NLP`
- **Dataset Repository Selector**: Quick switcher for the 8 registered enterprise datasets in `src/config.py`.

### 3.3 Center Panel (Agentic Stream & HITL Approval Queue)
- **Sticky Batch Approval Bar**: Appears at top of chat stream when pending rule proposals exist (`⚖️ Pending Governance Review (3 rules)  |  [✓ Approve All]  [✗ Reject]`).
- **User Prompt & Agent Stream**: Displays user prompts, Orchestrator ReAct thought reasoning, and sub-agent observation cards.
- **Inline RuleProposalCard (HITL Card)**:
  - Displays rule metadata (Column, Rule Type, Expression, Severity).
  - Actions: `[✓ Approve]` (turns card green), `[✗ Reject]` (turns card red), `[✏️ Edit]` (opens modal), `[▶ Run Clean DB Pipeline]` (triggers partitioning).
- **Chat Input Bar**: Input textarea with file attachment `[📎 Upload]` button.

### 3.4 Right Panel (Multi-View Context Dashboard)
- **Tab Switcher**: Switch between Profile, Rules, Anomaly & RCA, Audit Log, and Diff View.
- **Active Tab: Anomaly & RCA Inspector**:
  - **Composite Score Card**: Displays $S_{composite} = 0.89$ combining Robust Z-Score ($6.50$) and Isolation Forest ML ($0.92$).
  - **Defect Breakdown Table**: Categorized list of detected anomalies (GSM Basement Blackout, Negative SOC, Overvoltage Spikes, Motor RPM Mismatch).
  - **RCA Lineage Box**: Diagnosis Agent root-cause explanation generated from dbt lineage graph.
  - **Clean DB Execution Summary**: Clean record count ($940$), Quarantine count ($60$), and SHA-256 cryptographic lineage hash.

---

## 🧪 4. System Verification & Integration

- **Excalidraw Canvas Generation**: 34 visual elements rendered on canvas via Excalidraw MCP tool suite.
- **Frontend Code Integration**: Compiled into production frontend `frontend-v3` (`src/components/workspace/`, `src/components/hitl/`).
- **Pytest Gate**: **125 / 125 Tests Passing** (`51.53s`).
