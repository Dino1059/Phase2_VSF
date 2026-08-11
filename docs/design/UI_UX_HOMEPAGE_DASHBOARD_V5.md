# 🏠 DataTrust OS v5 Operational Trust Console.0 — Executive Homepage & Dashboard Wireframe Specification

> **Document Status:** Official Production Homepage & Executive Dashboard Specification  
> **Layout Model:** Full-Width Executive Dashboard + Ingestion Automation + HITL Task Queue + Anomaly Analytics  
> **Excalidraw Elements:** 28 Interactive Canvas Elements Rendered  
> **Last Updated:** 2026-08-02  

---

## 🏛️ 1. Executive Dashboard Architecture

The **Executive Homepage & Dashboard** serves as the central operational hub for DataTrust OS v5 Operational Trust Console.0, combining real-time data flow monitoring, agent auto-suggested rules, error trend analytics, and governance audit ledgers into a single, cohesive view.

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🤖 DataTrust OS v5 Operational Trust Console.0 — Executive Governance Homepage & Dashboard                   │ 🔍 Ctrl+K │ 📤 Upload DB │ 👤 Steward│
├──────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────┤
│ 🏠 Executive Homepage    │ 📊 Monitored: 8 Datasets  │ ⚡ Processed: 1.45M Rows │ ⚖️ HITL Pending: 3 Rules │ 🔥 Index: 0.89 │
├──────────────────────────┼───────────────────────────────────────────┬───────────────────────────────────────────┤
│ + New Agent Session      │ 🛡️ Agent Auto-Suggested Rules & HITL Queue  │ 🔄 Automated Data Flow & Ingestion Status │
│                          │ 1. [CRITICAL] battery_soc >= 0.0          │ 1. ST-EVCDP V-GREEN Charger Feed          │
│ GOVERNANCE THREADS       │ 2. [WARNING] duration_minutes < 720       │ 2. Telemetry JAC IEV40 EV Feed            │
│ 💬 VinFast EV Telemetry  │ 3. [INFO] total_fare >= fare_amount       │ 3. UIT-VSFC Vietnamese Feedback NLP Feed  │
│ 💬 V-GREEN Overheat      │ [✓ Approve All Pending (3)]               │ 4. Ride Hailing Transactions Feed         │
│ 💬 Xanh SM Trips Audit   ├───────────────────────────────────────────┼───────────────────────────────────────────┤
│ 💬 Customer Feedback NLP │ 📈 Error Trends & Anomaly Distribution    │ 🩺 Multi-Agent Anomaly Detector & RCA     │
├──────────────────────────┤ • 06:00 Basement Outage Spike (145/hr)    │ • Detector: MAD Z-Score + IsoForest ML    │
│ ENTERPRISE DATASETS      │ • 12:00 Charger Overheat Spike (88/hr)    │ • RCA 1: GSM Basement Drop (45%)          │
│ 📦 8 Active Sources      │ • 18:00 CAN-Bus Overvoltage Spike (32/hr) │ • RCA 2: V-GREEN Thermal Cutoff (30%)     │
│                          ├───────────────────────────────────────────┴───────────────────────────────────────────┤
│                          │ ✨ Clean DB Partitioning & Audit Ledger Manifest:                                      │
│                          │ Clean: 1,365,900 rows (94.2%) | Quarantined: 84,100 rows (5.8%) | SHA-256 Verified    │
└──────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎨 2. Component Section Breakdown

### 2.1 KPI Executive Metrics Banner (Row 0)
- **Monitored Datasets Card**: `8 Enterprise Sources (100% Active Pipeline)`.
- **Total Records Processed Card**: `1,450,000 Rows (94.2% Clean DB)`.
- **Pending HITL Tasks Card**: `3 Rules Requiring Steward Review`.
- **Composite Anomaly Index Card**: `S_composite = 0.89 (HEALTHY)`.

### 2.2 Agent Auto-Suggested Rules & Pending Approval Queue (Row 1 Left)
- **Rule 1 (Critical)**: `battery_soc >= 0.0 AND battery_soc <= 100.0` on `battery_soc` column.
- **Rule 2 (Warning)**: `duration_minutes > 0.0 AND duration_minutes < 720` on `duration` column.
- **Rule 3 (Info)**: `total_fare >= fare_amount` on `total_fare` column.
- **Quick Action Bar**: `[✓ Approve All Pending Rules (3)]` and `[⚙️ Open Full Rule Engine]`.

### 2.3 Automated Data Flow & Ingestion Status (Row 1 Right)
- **ST-EVCDP V-GREEN Feed**: Real-time pipeline, 500k rows, thermal fault auto-detected at Station #VGREEN-042.
- **JAC IEV40 EV Telemetry Feed**: IoT pipeline, 450k rows, GSM basement blackout auto-flagged.
- **UIT-VSFC Customer Feedback Feed**: Aspect extraction pipeline, 250k rows, teen-code normalized (`ko sac dc` ➔ `không sạc được`).
- **Ride Hailing Trips Feed**: Trip audit pipeline, 250k rows, Clean DB and Quarantine tables partitioned.

### 2.4 Error Trends & Anomaly Distribution (Row 2 Left)
- **Time Series Trend Visualizer**:
  - `00:00 - 06:00`: Baseline (12 anomalies/hr).
  - `06:00 - 12:00`: Basement Signal Drop Spike (145 anomalies/hr @ Vincom Landmark 81).
  - `12:00 - 18:00`: Charger Overheat Spike (88 anomalies/hr @ 85.5°C).
  - `18:00 - 24:00`: CAN-Bus Overvoltage Telemetry Spike (32 anomalies/hr @ 9999V).
- **Severity Breakdown**: Critical 18%, Warning 62%, Info 20%.

### 2.5 Multi-Agent Anomaly Detector & RCA Status (Row 2 Right)
- **Detection Engine**: Dual Composite Score ($S_{composite} = w_1 \cdot \text{Sigmoid}(Z_{robust}) + w_2 \cdot S_{isolation\_forest}$).
- **Top Diagnosed Root Causes**:
  1. GSM Cellular Signal Drop in Underground Basements (45%).
  2. V-GREEN Fast Charger Thermal Throttling @ 85.5°C (30%).
  3. Teen-code NLP Ambiguity in Customer App Reviews (25%).

### 2.6 Clean DB Partitioning & Audit Ledger Manifest (Bottom Row)
- **Output Record Summary**: `Clean Records: 1,365,900 / 1,450,000 (94.2%)`.
- **Quarantine Table Isolation**: `Quarantine Table: 84,100 rows (5.8%)`.
- **Cryptographic Lineage SHA-256**: `e3b0c44298fc1c149afbf4c8996fb92427ae41e462d71dce99026daef3200a`.
- **Steward Compliance Audit**: `142 Rules Approved | 12 Rules Rejected | 100% Policy Compliant`.

---

## 🧪 3. Deliverables Summary

- **Interactive Excalidraw Shareable Web Link**:  
  🔗 [https://excalidraw.com/#json=Ksfz0yTE44fsNfcIy8gxb,vsgPaXr6Yce8qX04qEoQog](https://excalidraw.com/#json=Ksfz0yTE44fsNfcIy8gxb,vsgPaXr6Yce8qX04qEoQog)
- **Local SVG Vector Graphic**:  
  🖼️ [docs/UI_UX_HOMEPAGE_DASHBOARD_V3.svg](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086/docs/UI_UX_HOMEPAGE_DASHBOARD_V3.svg)
- **Specification Document**:  
  📝 [docs/UI_UX_HOMEPAGE_DASHBOARD_V3.md](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086/docs/UI_UX_HOMEPAGE_DASHBOARD_V3.md)
