import json

def build_homepage_elements():
    # Canvas Dimensions: 1600 x 950
    # Sidebar: x=0..280 (w=280)
    # Homepage Main Dashboard Area: x=280..1600 (w=1320)

    elements = [
        # Main Background & Zone Rectangles
        {"id": "bg_canvas", "type": "rectangle", "x": 0, "y": 0, "width": 1600, "height": 950, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        {"id": "hdr_zone", "type": "rectangle", "x": 0, "y": 0, "width": 1600, "height": 70, "strokeColor": "#1971c2", "strokeWidth": 2, "backgroundColor": "#a5d8ff", "text": ""},
        {"id": "side_zone", "type": "rectangle", "x": 0, "y": 70, "width": 280, "height": 880, "strokeColor": "#868e96", "strokeWidth": 2, "backgroundColor": "#e9ecef", "text": ""},
        {"id": "home_zone", "type": "rectangle", "x": 280, "y": 70, "width": 1320, "height": 880, "strokeColor": "#0c8599", "strokeWidth": 2, "backgroundColor": "#f8f9fa", "text": ""},

        # Top Header Elements
        {"id": "hdr_title", "type": "text", "x": 20, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "🤖 DataTrust OS v3.0 — Executive Governance Homepage & Dashboard"},
        {"id": "hdr_search", "type": "rectangle", "x": 1010, "y": 16, "width": 170, "height": 38, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "🔍 Ctrl + K Search"},
        {"id": "hdr_upload", "type": "rectangle", "x": 1190, "y": 16, "width": 130, "height": 38, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "📤 Upload DB"},
        {"id": "hdr_user", "type": "rectangle", "x": 1330, "y": 16, "width": 240, "height": 38, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "👤 Steward (Admin Governance)"},

        # Left Sidebar Controls (With Active Homepage Tab)
        {"id": "btn_home", "type": "rectangle", "x": 15, "y": 85, "width": 250, "height": 45, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "🏠 Executive Homepage / Dashboard"},
        {"id": "btn_new_chat", "type": "rectangle", "x": 15, "y": 140, "width": 250, "height": 45, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "+ New Agent Chat Session"},
        {"id": "lbl_sessions", "type": "text", "x": 15, "y": 200, "fontSize": 14, "strokeColor": "#868e96", "text": "GOVERNANCE AGENT THREADS"},
        {"id": "sess_1", "type": "rectangle", "x": 15, "y": 225, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 VinFast EV Telemetry Scan"},
        {"id": "sess_2", "type": "rectangle", "x": 15, "y": 280, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 V-GREEN Charger Overheat"},
        {"id": "sess_3", "type": "rectangle", "x": 15, "y": 335, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Xanh SM Trips Ledger Audit"},
        {"id": "sess_4", "type": "rectangle", "x": 15, "y": 390, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Customer Feedback NLP"},
        {"id": "lbl_repos", "type": "text", "x": 15, "y": 455, "fontSize": 14, "strokeColor": "#868e96", "text": "ENTERPRISE DATASETS"},
        {"id": "ds_dropdown", "type": "rectangle", "x": 15, "y": 480, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "📦 8 Datasets Active (VinGroup)"},

        # Top KPI Metrics Banner (Row 0)
        {"id": "kpi_1", "type": "rectangle", "x": 300, "y": 85, "width": 300, "height": 80, "backgroundColor": "#ffffff", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "📊 Monitored Datasets:\n8 Enterprise Sources (100% Active)"},
        {"id": "kpi_2", "type": "rectangle", "x": 620, "y": 85, "width": 310, "height": 80, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "⚡ Total Records Processed:\n1,450,000 Rows (94.2% Clean DB)"},
        {"id": "kpi_3", "type": "rectangle", "x": 950, "y": 85, "width": 310, "height": 80, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "⚖️ Pending HITL Tasks:\n3 Rules Requiring Steward Review"},
        {"id": "kpi_4", "type": "rectangle", "x": 1280, "y": 85, "width": 300, "height": 80, "backgroundColor": "#ffffff", "strokeColor": "#9c36b5", "strokeWidth": 2, "text": "🔥 Composite Anomaly Index:\nS_composite = 0.89 (HEALTHY)"},

        # Row 1 Left: Auto-Suggested Rules & Pending Approval Queue
        {"id": "panel_rules_queue", "type": "rectangle", "x": 300, "y": 180, "width": 630, "height": 275, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "🛡️ Agent Auto-Suggested Rules & Pending Approval Tasks (HITL Queue):\n\n1. [CRITICAL] battery_soc >= 0.0 AND battery_soc <= 100.0  (Column: battery_soc)\n   Description: Enforce non-negative state of charge on EV telemetry.\n   Actions: [✓ Approve]   [✗ Reject]   [✏️ Edit]\n\n2. [WARNING] duration_minutes > 0.0 AND duration_minutes < 720 (Column: duration)\n   Description: Flag abnormal charging duration exceeding 12 hours.\n   Actions: [✓ Approve]   [✗ Reject]   [✏️ Edit]\n\n3. [INFO] total_fare >= fare_amount (Column: total_fare)\n   Description: Cross-check discount calculation integrity on Xanh SM trips.\n   Actions: [✓ Approve]   [✗ Reject]   [✏️ Edit]"},
        {"id": "btn_approve_all_queue", "type": "rectangle", "x": 315, "y": 415, "width": 260, "height": 32, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✓ Approve All Pending Rules (3)"},
        {"id": "btn_open_rules_engine", "type": "rectangle", "x": 590, "y": 415, "width": 220, "height": 32, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "⚙️ Open Full Rule Engine"},

        # Row 1 Right: Automated Data Flow & Ingestion Status
        {"id": "panel_ingestion_flow", "type": "rectangle", "x": 950, "y": 180, "width": 630, "height": 275, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "strokeWidth": 2, "text": "🔄 Automated Data Flow & Pipeline Ingestion Status:\n\n1. ST-EVCDP V-GREEN Charging Feed (Real-Time Pipeline)\n   Status: [ACTIVE] Ingested 500,000 rows | Thermal fault auto-detected @ Station #VGREEN-042.\n\n2. Telemetry JAC IEV40 EV Feed (IoT Telemetry Pipeline)\n   Status: [ACTIVE] Ingested 450,000 rows | GSM Basement blackout auto-flagged.\n\n3. UIT-VSFC Vietnamese Feedback NLP Feed (Aspect Extraction Pipeline)\n   Status: [ACTIVE] Ingested 250,000 rows | Teen-code normalized ('ko sac dc' -> 'không sạc được').\n\n4. Ride Hailing Transactions Feed (Trip Audit Pipeline)\n   Status: [ACTIVE] Ingested 250,000 rows | Clean DB & Quarantine tables partitioned."},

        # Row 2 Left: Error Trends & Anomaly Analytics Chart Box
        {"id": "panel_error_trends", "type": "rectangle", "x": 300, "y": 470, "width": 630, "height": 260, "backgroundColor": "#ffffff", "strokeColor": "#e03131", "strokeWidth": 2, "text": "📈 Error Trends & Anomaly Distribution (Last 24 Hours):\n\n[Time Series Trend Visualizer]\n• 00:00 - 06:00 ─── Normal Baseline (12 anomalies/hr)\n• 06:00 - 12:00 ─────── GSM Basement Blackout Spike (145 anomalies/hr @ Vincom Landmark 81)\n• 12:00 - 18:00 ───── Charger Overheat Spike (88 anomalies/hr @ 85.5°C Thermal Fault)\n• 18:00 - 24:00 ──── CAN-Bus Overvoltage Telemetry Spike (32 anomalies/hr @ 9999V)\n\nSeverity Breakdown: 🔴 Critical: 18%  |  🟡 Warning: 62%  |  🔵 Info: 20%"},

        # Row 2 Right: Multi-Agent Anomaly Detector & RCA Status
        {"id": "panel_agent_rca", "type": "rectangle", "x": 950, "y": 470, "width": 630, "height": 260, "backgroundColor": "#ffffff", "strokeColor": "#9c36b5", "strokeWidth": 2, "text": "🩺 Multi-Agent Anomaly Detector & Diagnosis Status (dbt Lineage Graph):\n\nDetector Engine: Dual Composite Score (Robust MAD Z-Score + Isolation Forest ML)\n\nTop Diagnosed Root Causes:\n1. GSM Cellular Signal Drop in Underground Basements (45% of total faults)\n   Root Cause: Vehicles entering underground parking areas lose GPS/cellular connectivity.\n2. V-GREEN Fast Charger Thermal Throttling @ 85.5°C (30% of total faults)\n   Root Cause: Ambient temperature combined with high-current charging triggers safety cutoff.\n3. Teen-code NLP Ambiguity in Customer App Reviews (25% of total faults)\n   Root Cause: Colloquial Vietnamese slang requires custom entity normalizer dictionary."},

        # Bottom Banner: Clean DB Partitioning & Audit Ledger Manifest
        {"id": "panel_audit_ledger", "type": "rectangle", "x": 300, "y": 745, "width": 1280, "height": 190, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "✨ Clean DB Execution & Governance Audit Ledger Manifest:\n\n• Clean Records Output: 1,365,900 / 1,450,000 rows (94.2% Passed Quality Checks)\n• Quarantine Table: 84,100 corrupt rows isolated (5.8% Quarantined for Repair)\n• Cryptographic Lineage SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e462d71dce99026daef3200a\n• Steward Governance Audit: 142 Rules Approved | 12 Rules Rejected | 100% Policy Compliant"}
    ]
    return elements

if __name__ == "__main__":
    elements = build_homepage_elements()
    with open('/tmp/excalidraw_homepage_elements.json', 'w') as f:
        json.dump(elements, f)
    print(f"Generated {len(elements)} homepage elements")
