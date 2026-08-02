import json

def build_elements():
    # Canvas Dimensions: 1600 x 950
    # Left Sidebar: x=0..280 (w=280)
    # Center Chat Panel: x=280..920 (w=640)
    # Right Workspace Panel: x=920..1600 (w=680)

    elements = [
        # Main Background & Zone Rectangles
        {"id": "bg_canvas", "type": "rectangle", "x": 0, "y": 0, "width": 1600, "height": 950, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        {"id": "hdr_zone", "type": "rectangle", "x": 0, "y": 0, "width": 1600, "height": 70, "strokeColor": "#1971c2", "strokeWidth": 2, "backgroundColor": "#a5d8ff", "text": ""},
        {"id": "side_zone", "type": "rectangle", "x": 0, "y": 70, "width": 280, "height": 880, "strokeColor": "#868e96", "strokeWidth": 2, "backgroundColor": "#e9ecef", "text": ""},
        {"id": "chat_zone", "type": "rectangle", "x": 280, "y": 70, "width": 640, "height": 880, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        {"id": "work_zone", "type": "rectangle", "x": 920, "y": 70, "width": 680, "height": 880, "strokeColor": "#0c8599", "strokeWidth": 2, "backgroundColor": "#99e9f2", "text": ""},

        # Top Header Elements
        {"id": "hdr_title", "type": "text", "x": 20, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "🤖 DataTrust OS v3.0 — VinGroup Enterprise AI Governance"},
        {"id": "hdr_ds_pill", "type": "rectangle", "x": 680, "y": 16, "width": 310, "height": 38, "backgroundColor": "#ffffff", "strokeColor": "#1971c2", "text": "📦 real_vinfast_ev_telemetry"},
        {"id": "hdr_search", "type": "rectangle", "x": 1010, "y": 16, "width": 170, "height": 38, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "🔍 Ctrl + K Search"},
        {"id": "hdr_upload", "type": "rectangle", "x": 1190, "y": 16, "width": 130, "height": 38, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "📤 Upload DB"},
        {"id": "hdr_user", "type": "rectangle", "x": 1330, "y": 16, "width": 140, "height": 38, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "👤 Steward (Admin)"},

        # Left Sidebar Controls
        {"id": "btn_new_chat", "type": "rectangle", "x": 15, "y": 85, "width": 250, "height": 45, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "+ New Chat Session"},
        {"id": "lbl_sessions", "type": "text", "x": 15, "y": 145, "fontSize": 14, "strokeColor": "#868e96", "text": "ACTIVE SESSIONS"},
        {"id": "sess_1", "type": "rectangle", "x": 15, "y": 170, "width": 250, "height": 48, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "💬 VinFast EV Telemetry Scan"},
        {"id": "sess_2", "type": "rectangle", "x": 15, "y": 228, "width": 250, "height": 48, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 V-GREEN Charger Overheat"},
        {"id": "sess_3", "type": "rectangle", "x": 15, "y": 286, "width": 250, "height": 48, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Xanh SM Trips Ledger Audit"},
        {"id": "sess_4", "type": "rectangle", "x": 15, "y": 344, "width": 250, "height": 48, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Customer Feedback NLP"},
        {"id": "lbl_repos", "type": "text", "x": 15, "y": 415, "fontSize": 14, "strokeColor": "#868e96", "text": "DATASET REPOSITORY"},
        {"id": "ds_dropdown", "type": "rectangle", "x": 15, "y": 440, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "📦 real_vinfast_ev_telemetry"},

        # Center Chat Panel Elements
        {"id": "hitl_bar", "type": "rectangle", "x": 295, "y": 80, "width": 610, "height": 48, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "text": "⚖️ Pending Governance Review (3 rules)  |  [✓ Approve All]  [✗ Reject All]"},
        {"id": "user_msg", "type": "rectangle", "x": 305, "y": 140, "width": 590, "height": 48, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "👤 User: Detect anomalies & propose quality rules for VinFast EV Telemetry"},
        {"id": "agent_msg_1", "type": "rectangle", "x": 305, "y": 200, "width": 590, "height": 70, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "🤖 Orchestrator Agent (Gemma-4-26b):\nExecuting Tri-Detector Suite (MAD Z-Score + IQR + Isolation Forest ML)"},
        {"id": "agent_msg_2", "type": "rectangle", "x": 305, "y": 280, "width": 590, "height": 80, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131", "text": "⚠️ Anomaly Detector Agent:\nFlagged 28 anomalies (GSM Basement Blackout, Negative SOC -12.5%, Overvoltage 9999V)"},
        
        # HITL Approval Card Container & Buttons
        {"id": "rule_card_bg", "type": "rectangle", "x": 305, "y": 370, "width": 590, "height": 170, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "🛡️ Rule Proposer Agent Proposal #1:\nColumn: battery_soc  |  Type: range_check  |  Severity: CRITICAL\nExpression: battery_soc >= 0.0 AND battery_soc <= 100.0\nDescription: Enforce valid non-negative battery state of charge"},
        {"id": "btn_approve", "type": "rectangle", "x": 325, "y": 480, "width": 110, "height": 40, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✓ Approve"},
        {"id": "btn_reject", "type": "rectangle", "x": 445, "y": 480, "width": 100, "height": 40, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131", "text": "✗ Reject"},
        {"id": "btn_edit", "type": "rectangle", "x": 555, "y": 480, "width": 90, "height": 40, "backgroundColor": "#e9ecef", "strokeColor": "#868e96", "text": "✏️ Edit"},
        {"id": "btn_next_step", "type": "rectangle", "x": 655, "y": 480, "width": 220, "height": 40, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "▶ Run Clean DB Pipeline"},

        # Chat Input Bar
        {"id": "chat_input", "type": "rectangle", "x": 295, "y": 880, "width": 610, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "text": "💬 Type command or ask AI steward...                                                          [📎 Upload]"},

        # Right Workspace Panel Elements
        {"id": "tab_bar", "type": "rectangle", "x": 935, "y": 80, "width": 650, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "[📊 Profile]    [🛡️ Rules]    [⚠️ Anomaly & RCA]    [📋 Audit Log]    [🔀 Diff View]"},
        {"id": "active_tab_line", "type": "rectangle", "x": 1175, "y": 120, "width": 145, "height": 5, "backgroundColor": "#0c8599", "text": ""},
        
        {"id": "anom_score_card", "type": "rectangle", "x": 945, "y": 140, "width": 630, "height": 80, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "text": "🔥 Dual Composite Anomaly Score: S_composite = 0.89\n(Robust MAD Z-Score: 6.50  |  Isolation Forest Score: 0.92)"},
        {"id": "anom_breakdown", "type": "rectangle", "x": 945, "y": 230, "width": 630, "height": 180, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "text": "📌 Detected Defects & Anomalies Breakdown:\n1. GSM Underground Blackout    | Null GPS & Timestamp           | 25 rows\n2. Negative Battery SOC        | battery_soc = -12.5%           | 15 rows\n3. CAN-Bus Overvoltage Spikes  | battery_voltage = 9999.0V      |  8 rows\n4. Motor RPM Mismatch          | Speed = 0 km/h & RPM = 14,500   | 12 rows"},
        {"id": "rca_box", "type": "rectangle", "x": 945, "y": 420, "width": 630, "height": 170, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "🩺 Diagnosis Agent Root Cause Analysis (dbt Lineage Graph):\nRoot Cause: VinFast VF8 entered Vincom Underground Basement.\nGPS connection dropped & CAN-bus voltage telemetry spiked.\nRemediation: Apply linear interpolation & quarantine corrupt records."},
        {"id": "cleandb_box", "type": "rectangle", "x": 945, "y": 600, "width": 630, "height": 140, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✨ Clean DB Execution Summary:\nClean Records Output: 940 / 1,000 rows (94.0%)\nQuarantine Table: 60 rows (6.0%)\nSHA-256 Lineage Hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4"}
    ]
    return elements

if __name__ == "__main__":
    elements = build_elements()
    with open('/tmp/excalidraw_elements.json', 'w') as f:
        json.dump(elements, f)
    print(f"Generated {len(elements)} elements")
